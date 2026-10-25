import asyncio
import json
import logging
from contextlib import asynccontextmanager

import chess
import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from . import account, analysis, importers, learning
from .coach import ask
from .coach.service import coach
from .config import settings
from .db import db
from .engine import get_pool, start_pool
from .rag import store as rag_store
from .locale import available as locales, current as current_lang, lang as current_locale
from .rag.ingest import ingest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("chess.engine").setLevel(logging.ERROR)  # null-move probes warn on every call


ingest_state: dict = {"running": False, "error": None}


async def _ingest_background() -> None:
    ingest_state["running"] = True
    try:
        await ingest()
    except Exception as e:  # the app works without background knowledge, so only report it
        logging.getLogger(__name__).exception("knowledge ingest failed")
        ingest_state["error"] = str(e)
    finally:
        ingest_state["running"] = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await start_pool()
    task = None
    if settings.rag_auto_ingest and rag_store.count() == 0:
        task = asyncio.create_task(_ingest_background())
    yield
    if task:
        task.cancel()
    await pool.stop()


app = FastAPI(title="chess-o", lifespan=lifespan)


@app.middleware("http")
async def locale_from_cookie(request: Request, call_next):
    code = request.query_params.get("lang") or request.cookies.get("chesso_lang")
    token = current_lang.set(code if code in locales() else None)
    try:
        return await call_next(request)
    finally:
        current_lang.reset(token)


def coach_key(extra: str = "") -> str:
    """Coach texts are cached per language: English keeps the bare key so old caches stay valid."""
    code = current_locale()
    return extra if code == "en" else f"{extra}|{code}"


def sse(gen):
    async def wrap():
        sent_done = False
        async for item in gen:
            sent_done = sent_done or item["event"] == "done"
            yield {"event": item["event"], "data": json.dumps(item["data"])}
        if not sent_done:
            yield {"event": "done", "data": "{}"}  # lets EventSource close instead of reconnecting
    return EventSourceResponse(wrap(), ping=15)


class PGNIn(BaseModel):
    pgn: str


class PositionIn(BaseModel):
    fen: str
    depth: int | None = None
    multipv: int = 3


@app.get("/api/health")
async def health():
    return {"ok": True, "workers": settings.workers, "llm_model": settings.llm_model}


@app.get("/api/knowledge")
async def knowledge():
    return {"chunks": rag_store.count(), "sources": rag_store.sources(), **ingest_state}


@app.post("/api/knowledge/ingest")
async def knowledge_ingest():
    """Re-index (e.g. after dropping files in knowledge/custom). Cached downloads and embeddings are reused."""
    if not ingest_state["running"]:
        ingest_state["error"] = None
        asyncio.create_task(_ingest_background())
    return {"running": True}


@app.post("/api/games")
async def create_game(body: PGNIn):
    try:
        return analysis.store_game(body.pgn)
    except analysis.PGNError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/games")
async def list_games(limit: int = 30, player: str | None = None, analyzed: bool | None = None):
    where, params = [], []
    if player:
        where.append("(lower(json_extract(headers, '$.White')) = ? OR lower(json_extract(headers, '$.Black')) = ?)")
        params += [player.lower()] * 2
    if analyzed is not None:
        where.append("analysis IS NOT NULL" if analyzed else "analysis IS NULL")
    sql = "SELECT id, headers, summary, created_at FROM games"
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = db.all(sql + " ORDER BY created_at DESC LIMIT ?", (*params, limit))
    return [{"id": r["id"], "headers": json.loads(r["headers"]),
             "summary": json.loads(r["summary"]) if r["summary"] else None, "created_at": r["created_at"],
             "side": learning.get_side(r["id"])}
            for r in rows]


@app.get("/api/games/{gid}")
async def get_game(gid: str):
    try:
        game, result = analysis.load_game(gid)
    except KeyError:
        raise HTTPException(404, "Game not found")
    return {**(result or {"game": analysis.game_payload(gid, game)}), "side": learning.get_side(gid)}


@app.get("/api/games/{gid}/analyze")
async def analyze_game(gid: str, force: bool = False):
    try:
        analysis.load_game(gid)
    except KeyError:
        raise HTTPException(404, "Game not found")
    async def run():
        async for item in analysis.analyze(gid, force):
            if item["event"] == "analysis":
                side = learning.get_side(gid)
                item["data"] = {**item["data"], "side": side}
                if side:
                    learning.create_drills(gid, item["data"], side)
            yield item
    return sse(run())


class SideIn(BaseModel):
    side: str | None


class MoveIn(BaseModel):
    uci: str


@app.post("/api/games/{gid}/side")
async def set_side(gid: str, body: SideIn):
    if body.side not in ("white", "black", None):
        raise HTTPException(400, "side must be white, black or null")
    try:
        learning.set_side(gid, body.side)
    except KeyError:
        raise HTTPException(404, "Game not found")
    return {"side": body.side}


def _facts(gid: str, ply: int) -> dict:
    try:
        return learning.facts_for(gid, ply)
    except KeyError:
        raise HTTPException(404, "Game not found")
    except LookupError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/games/{gid}/coach/{ply}")
async def coach_move(gid: str, ply: int, kind: str = "move", prefetch: int = 2):
    if kind not in ("move", "best"):
        raise HTTPException(400, "kind must be move or best")
    facts = _facts(gid, ply)
    side = learning.get_side(gid)
    _, result = analysis.load_game(gid)
    for nxt in range(ply + 1, min(ply + 1 + prefetch, len(result["facts"]) + 1)):
        coach.prefetch((gid, nxt, "move", coach_key()), result["facts"][nxt - 1], "move", side)
    return sse(coach.stream((gid, ply, kind, coach_key()), facts, kind, side))


@app.get("/api/coach/explore")
async def coach_explore(fen: str, uci: str, side: str | None = None):
    try:
        facts = await learning.quick_facts(fen, uci)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    async def run():
        yield {"event": "facts", "data": facts}
        async for item in coach.stream(("explore", 0, "explore", coach_key(f"{fen}|{uci}")), facts, "explore", side):
            yield item
    return sse(run())


def _history(h: str) -> list[dict]:
    try:
        turns = json.loads(h) if h else []
    except json.JSONDecodeError:
        raise HTTPException(400, "h must be a JSON list")
    return [t for t in turns if isinstance(t, dict)] if isinstance(turns, list) else []


@app.get("/api/games/{gid}/ask/{ply}")
async def ask_move(gid: str, ply: int, q: str, h: str = ""):
    if not q.strip():
        raise HTTPException(400, "Empty question")
    return sse(ask.answer(_facts(gid, ply), learning.get_side(gid), q, _history(h)))


@app.get("/api/coach/explore/ask")
async def ask_explore(fen: str, uci: str, q: str, h: str = "", side: str | None = None):
    if not q.strip():
        raise HTTPException(400, "Empty question")
    try:
        facts = await learning.quick_facts(fen, uci)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return sse(ask.answer(facts, side, q, _history(h)))


@app.get("/api/games/{gid}/hint/{ply}")
async def get_hint(gid: str, ply: int, level: int = 1):
    return learning.hint(_facts(gid, ply), level)


@app.post("/api/games/{gid}/retry/{ply}")
async def post_retry(gid: str, ply: int, body: MoveIn):
    try:
        return await learning.retry(_facts(gid, ply), body.uci)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class GradeIn(BaseModel):
    grade: int


@app.get("/api/drills/due")
async def drills_due():
    return learning.due_drills()


@app.get("/api/drills/stats")
async def drills_stats():
    return learning.drill_stats()


@app.post("/api/drills/{drill_id}/review")
async def drills_review(drill_id: int, body: GradeIn):
    try:
        return learning.review_drill(drill_id, body.grade)
    except LookupError:
        raise HTTPException(404, "No such drill")


@app.get("/api/profile")
async def get_profile():
    return learning.profile()


@app.post("/api/engine/position")
async def engine_position(body: PositionIn):
    try:
        board = chess.Board(body.fen)
    except ValueError:
        raise HTTPException(400, "Invalid FEN")
    lines = await get_pool().analyse(board, body.depth or settings.engine_depth, max(1, min(5, body.multipv)))
    return {"lines": [{**l, "san": analysis.pv_san(board, l["uci"])} for l in lines]}


class AccountIn(BaseModel):
    username: str


@app.get("/api/account/chesscom")
async def get_account():
    return {"account": account.get()}


@app.put("/api/account/chesscom")
async def link_account(body: AccountIn):
    if not body.username.strip():
        raise HTTPException(400, "Username is empty")
    try:
        linked = await account.link(body.username)
    except LookupError:
        raise HTTPException(404, f"No Chess.com player called {body.username}")
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Chess.com did not answer: {exc}")
    return {"account": linked}


@app.delete("/api/account/chesscom")
async def unlink_account():
    account.unlink()
    return {"account": None}


@app.post("/api/account/chesscom/sync")
async def sync_account(force: bool = False):
    try:
        return await account.sync(force)
    except LookupError:
        raise HTTPException(404, "No Chess.com account linked")
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Chess.com did not answer: {exc}")


@app.delete("/api/data")
async def clear_data():
    db.clear_user_data()
    return {"ok": True}


@app.get("/api/import/{site}/{user}")
async def import_games(site: str, user: str, limit: int = 20):
    fetch = {"lichess": importers.lichess, "chesscom": importers.chesscom}.get(site)
    if not fetch:
        raise HTTPException(404, "Unknown site")
    try:
        return await fetch(user, min(limit, 50))
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"{site} did not answer: {exc}")
