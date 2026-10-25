"""A pool of single-threaded Stockfish processes with a position cache.

Many one-thread engines searching different positions in parallel scale better than one
engine with many threads, because a game review is a batch of independent positions.
"""

import asyncio
import logging
from collections import OrderedDict

import chess
import chess.engine

from .config import settings
from .db import db

log = logging.getLogger(__name__)

Line = dict  # {"uci": [str], "score": {"cp": int} | {"mate": int}, "depth": int}


def cache_key(board: chess.Board, depth: int, multipv: int) -> str:
    # Move counters do not change the search, so they stay out of the key.
    return f"{' '.join(board.fen().split()[:4])}|{depth}|{multipv}"


def score_json(score: chess.engine.PovScore) -> dict:
    white = score.white()
    if white.is_mate():
        return {"mate": white.mate()}
    return {"cp": white.score()}


class EnginePool:
    def __init__(self, size: int):
        self.size = size
        self.idle: asyncio.Queue[chess.engine.UciProtocol] = asyncio.Queue()
        self.memo: OrderedDict[str, list[Line]] = OrderedDict()
        self.inflight: dict[str, asyncio.Future] = {}

    async def _spawn(self) -> chess.engine.UciProtocol:
        _, engine = await chess.engine.popen_uci(settings.stockfish_path)
        await engine.configure({"Threads": 1, "Hash": settings.engine_hash_mb})
        return engine

    async def start(self) -> None:
        engines = await asyncio.gather(*(self._spawn() for _ in range(self.size)))
        for engine in engines:
            self.idle.put_nowait(engine)
        log.info("engine pool ready: %d x %s", self.size, engines[0].id.get("name"))

    async def stop(self) -> None:
        while not self.idle.empty():
            engine = self.idle.get_nowait()
            try:
                await engine.quit()
            except Exception:
                pass

    def _remember(self, key: str, lines: list[Line]) -> None:
        self.memo[key] = lines
        self.memo.move_to_end(key)
        if len(self.memo) > 20000:
            self.memo.popitem(last=False)

    async def analyse(self, board: chess.Board, depth: int, multipv: int) -> list[Line]:
        if board.is_game_over():
            return []
        key = cache_key(board, depth, multipv)
        if key in self.memo:
            return self.memo[key]
        cached = db.engine_get(key)
        if cached is not None:
            self._remember(key, cached)
            return cached
        if key in self.inflight:
            return await self.inflight[key]

        future = asyncio.get_running_loop().create_future()
        self.inflight[key] = future
        try:
            lines = await self._search(board, depth, multipv)
            self._remember(key, lines)
            db.engine_put(key, lines)
            future.set_result(lines)
            return lines
        except Exception as exc:
            future.set_exception(exc)
            future.exception()  # mark retrieved so a lone failure does not warn
            raise
        finally:
            del self.inflight[key]

    async def _search(self, board: chess.Board, depth: int, multipv: int) -> list[Line]:
        engine = await self.idle.get()
        try:
            infos = await engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
        except chess.engine.EngineError:
            log.exception("engine crashed, respawning")
            engine = await self._spawn()
            infos = await engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
        finally:
            self.idle.put_nowait(engine)
        lines = []
        for info in infos:
            if "pv" not in info or "score" not in info:
                continue
            lines.append({
                "uci": [m.uci() for m in info["pv"][:12]],
                "score": score_json(info["score"]),
                "depth": info.get("depth", depth),
            })
        return lines

    async def threat(self, board: chess.Board, depth: int) -> Line | None:
        """What the side that just moved would play if it could move again (null-move probe)."""
        if board.is_check() or board.is_game_over():
            return None
        probe = board.copy(stack=False)
        probe.push(chess.Move.null())
        if not probe.is_valid():
            return None
        lines = await self.analyse(probe, depth, 1)
        return lines[0] if lines else None


pool: EnginePool | None = None


def get_pool() -> EnginePool:
    assert pool is not None, "engine pool not started"
    return pool


async def start_pool() -> EnginePool:
    global pool
    pool = EnginePool(settings.workers)
    await pool.start()
    return pool
