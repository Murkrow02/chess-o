"""Coach generation: lazy, cached, streamed, validated, with background look-ahead.

One LLM job runs at a time (a small GPU serves one request fastest). Whatever the player is
waiting for goes first; look-ahead for the next moves fills the GPU while they read, in move
order. Two requests for the same text share one job.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from ..db import db
from ..locale import load
from ..rag import retrieve
from . import llm
from .prompt import build_messages, template
from .validate import foreign_moves, tidy

log = logging.getLogger(__name__)


class Job:
    def __init__(self, key: tuple, foreground: bool):
        self.key = key
        self.foreground = foreground
        self.tokens: list[str] = []
        self.final: str | None = None
        self.replaced = False
        self.running = False  # holds the GPU
        self.offline = False
        self.sources: list[dict] = []
        self.changed = asyncio.Condition()
        self.task: asyncio.Task | None = None

    async def push(self, token: str | None = None) -> None:
        async with self.changed:
            if token:
                self.tokens.append(token)
            self.changed.notify_all()


class Coach:
    def __init__(self):
        self.jobs: dict[tuple, Job] = {}
        self.gpu = asyncio.Lock()
        self.urgent = 0  # foreground work holding or waiting for the GPU
        self.queue: list[Job] = []  # look-ahead jobs waiting for an idle GPU, oldest first

    @staticmethod
    def cached(key: tuple) -> dict | None:
        row = db.one("SELECT text, sources FROM coach_cache WHERE game_id=? AND ply=? AND kind=? AND extra=?", key)
        return {"text": row["text"], "sources": json.loads(row["sources"])} if row else None

    def _start(self, key: tuple, facts: dict, kind: str, side: str | None, foreground: bool) -> Job:
        job = self.jobs.get(key)
        if job:
            job.foreground = job.foreground or foreground
            return job
        job = Job(key, foreground)
        self.jobs[key] = job
        job.task = asyncio.create_task(self._run(job, facts, kind, side))
        return job

    @asynccontextmanager
    async def slot(self, job: Job | None = None):
        """The GPU. Look-ahead only takes it when nothing on screen is waiting, one job at a time in order."""
        if job and not job.foreground:
            self.queue.append(job)
            try:
                while not job.foreground and (self.urgent or self.gpu.locked() or self.queue[0] is not job):
                    await asyncio.sleep(0.2)
            finally:
                self.queue.remove(job)
            if not job.foreground:
                await self.gpu.acquire()  # free and nobody waiting, so this returns at once
                try:
                    yield
                finally:
                    self.gpu.release()
                return
        self.urgent += 1
        try:
            async with self.gpu:
                yield
        finally:
            self.urgent -= 1

    def look_ahead(self, wanted: list[tuple[tuple, dict, str, str | None]]) -> None:
        """Explain the next moves in the background, dropping look-ahead the player has moved away from."""
        keep = {key for key, *_ in wanted}
        game = {key[0] for key in keep}
        for job in list(self.jobs.values()):
            if not job.foreground and job.key[0] in game and job.key not in keep and job.task and not job.tokens:
                job.task.cancel()
        for key, facts, kind, side in wanted:
            if key not in self.jobs and not self.cached(key):
                self._start(key, facts, kind, side, foreground=False)

    async def _run(self, job: Job, facts: dict, kind: str, side: str | None) -> None:
        try:
            chunks = await retrieve.for_facts(facts)
            job.sources = [{"title": c["title"], "source": c["source"], "url": c.get("url"), "license": c.get("license")}
                           for c in chunks]
            messages, allowed = build_messages(facts, kind, side, chunks)
            async with self.slot(job):
                job.running = True
                text = tidy(await self._generate(job, messages, allowed, facts))
            job.final = text
            db.execute("INSERT OR REPLACE INTO coach_cache (game_id, ply, kind, extra, text, sources) VALUES (?,?,?,?,?,?)",
                       (*job.key, text, json.dumps(job.sources)))
        except asyncio.CancelledError:
            job.final = ""
            raise
        except Exception:
            log.exception("coach job failed")
            job.final = template(facts)
            job.replaced = job.offline = True
        finally:
            await job.push()
            self.jobs.pop(job.key, None)

    async def _generate(self, job: Job, messages: list[dict], allowed: set[str], facts: dict) -> str:
        try:
            async for token in llm.stream_chat(messages, temperature=0.4):
                await job.push(token)
        except (httpx.HTTPError, OSError):
            log.warning("LLM unreachable, using the template")
            job.replaced = job.offline = True
            return template(facts)
        text = "".join(job.tokens).strip()
        bad = foreign_moves(text, allowed)
        if not bad:
            return text
        log.info("coach mentioned moves outside the engine lines %s; regenerating", bad)
        retry_msgs = messages + [{"role": "assistant", "content": text}, {"role": "user", "content": load()["stricter"]}]
        try:
            text2 = (await llm.chat(retry_msgs, temperature=0.2)).strip()
        except (httpx.HTTPError, OSError):
            text2 = ""
        job.replaced = True
        return text2 if text2 and not foreign_moves(text2, allowed) else template(facts)

    async def stream(self, key: tuple, facts: dict, kind: str, side: str | None) -> AsyncIterator[dict]:
        hit = self.cached(key)
        if hit:
            yield {"event": "sources", "data": hit["sources"]}
            yield {"event": "replace", "data": {"text": hit["text"], "cached": True}}
            yield {"event": "done", "data": {}}
            return
        job = self._start(key, facts, kind, side, foreground=True)
        sent = 0
        sources_sent = False
        while True:
            async with job.changed:
                if job.final is None and sent == len(job.tokens):
                    await job.changed.wait()
            if job.sources and not sources_sent:
                sources_sent = True
                yield {"event": "sources", "data": job.sources}
            while sent < len(job.tokens):
                yield {"event": "token", "data": job.tokens[sent]}
                sent += 1
            if job.final is not None:
                if job.replaced or job.final != "".join(job.tokens).strip():
                    yield {"event": "replace", "data": {"text": job.final, "offline": job.offline}}
                yield {"event": "done", "data": {}}
                return

    def ahead(self, keys: list[tuple]) -> list[str]:
        """Where each look-ahead key stands: ready, writing, queued or idle."""
        def state(key):
            job = self.jobs.get(key)
            if job:
                return "writing" if job.running else "queued"
            return "ready" if self.cached(key) else "idle"
        return [state(k) for k in keys]


coach = Coach()
