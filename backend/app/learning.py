"""Learning features on top of the analysis: explore, guided retry, hints, drills, profile."""

import json
import math

import chess

from . import analysis
from . import classify as C
from . import features as F
from .config import settings
from .db import db, now
from .engine import get_pool
from .locale import load

DAY = 86400.0


async def quick_facts(fen: str, uci: str) -> dict:
    """Facts for one move played from any position (used for explored variations)."""
    pool = get_pool()
    before = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    if move not in before.legal_moves:
        raise ValueError("Illegal move")
    after = before.copy()
    after.push(move)
    depth, multipv = settings.engine_depth, settings.engine_multipv
    evals = [await pool.analyse(before, depth, multipv), await pool.analyse(after, depth, multipv)]
    threats = [await pool.threat(before, analysis.THREAT_DEPTH), await pool.threat(after, analysis.THREAT_DEPTH)]
    return analysis.build_facts([before, after], [move], evals, threats, set())[0]


def facts_for(gid: str, ply: int) -> dict:
    _, result = analysis.load_game(gid)
    if not result:
        raise LookupError("Analyse the game first")
    if not 1 <= ply <= len(result["facts"]):
        raise LookupError("No such move")
    return result["facts"][ply - 1]


# --- side --------------------------------------------------------------------

def get_side(gid: str) -> str | None:
    return db.kv_get(f"side:{gid}")


def set_side(gid: str, side: str | None) -> None:
    db.kv_set(f"side:{gid}", side)
    _, result = analysis.load_game(gid)
    if result and side:
        create_drills(gid, result, side)


# --- hints and retry -----------------------------------------------------------

def hint(f: dict, level: int) -> dict:
    loc = load()
    h = loc["hints"]
    board = chess.Board(f["fen_before"])
    move = chess.Move.from_uci(f["best_move_uci"])
    piece = F.NAMES[board.piece_type_at(move.from_square)]
    piece = loc.get("pieces", {}).get(piece, piece)
    square = chess.square_name(move.to_square)
    out: dict = {"piece_square": chess.square_name(move.from_square)}
    if level <= 1:
        out["text"] = h["1"].format(piece=piece)
        if f.get("opponent_threat_before"):
            out["text"] += " " + h["threat"].format(threat=f["opponent_threat_before"][0])
    elif level == 2:
        out["text"] = h["2"].format(piece=piece, square=square)
        out["square"] = square
    else:
        out["text"] = h["3"].format(san=f["best_move_san"])
        out["square"] = square
        out["uci"] = f["best_move_uci"]
    return out


async def retry(f: dict, uci: str) -> dict:
    r = load()["retry"]
    board = chess.Board(f["fen_before"])
    move = chess.Move.from_uci(uci)
    if move not in board.legal_moves:
        raise ValueError("Illegal move")
    san = board.san(move)
    color = board.turn
    if uci == f["best_move_uci"]:
        return {"verdict": "correct", "san": san, "text": r["correct"].format(san=san), "score": f["eval_before"]}
    board.push(move)
    score = C.terminal_score(board)
    reply = None
    if score is None:
        lines = await get_pool().analyse(board, settings.engine_depth, 1)
        score = lines[0]["score"] if lines else {"cp": 0}
        reply = analysis.pv_san(board, lines[0]["uci"], 1)[0] if lines else None
    loss = C.win_for(f["eval_before"], color) - C.win_for(score, color)
    if loss <= 2:
        return {"verdict": "close", "san": san, "text": r["close"].format(san=san), "score": score}
    return {"verdict": "wrong", "san": san, "reply": reply, "score": score,
            "text": r["wrong"].format(san=san, reply=reply or r["strong_answer"])}


# --- drills (SM-2 spaced repetition) ---------------------------------------------

def create_drills(gid: str, result: dict, side: str) -> int:
    rows = []
    for f in result["facts"]:
        if f["color"] != side or f["classification"] not in ("mistake", "blunder", "miss") or not f["best_move_uci"]:
            continue
        before = chess.Board(f["fen_before"])
        best = chess.Move.from_uci(f["best_move_uci"])
        after = before.copy()
        after.push(best)
        themes = F.tactic_themes(before, best, after)
        rows.append((gid, f["ply"], f["fen_before"], f["san"], f["best_move_uci"], f["best_move_san"],
                     f["classification"], json.dumps(themes), f["phase"], now(), now()))
    db.executemany("""INSERT OR IGNORE INTO drills (game_id, ply, fen, played_san, solution_uci, solution_san,
                      classification, themes, phase, due, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", rows)
    return len(rows)


def _drill_json(row) -> dict:
    d = dict(row)
    d["themes"] = json.loads(d["themes"])
    headers = json.loads(db.one("SELECT headers FROM games WHERE id=?", (d["game_id"],))["headers"])
    d["side"] = "white" if d["fen"].split()[1] == "w" else "black"
    d["opponent"] = headers.get("Black" if d["side"] == "white" else "White", "?")
    return d


def due_drills(limit: int = 20) -> list[dict]:
    rows = db.all("SELECT * FROM drills WHERE due <= ? ORDER BY due LIMIT ?", (now(), limit))
    return [_drill_json(r) for r in rows]


def drill_stats() -> dict:
    total = db.one("SELECT COUNT(*) AS n FROM drills")["n"]
    due = db.one("SELECT COUNT(*) AS n FROM drills WHERE due <= ?", (now(),))["n"]
    return {"total": total, "due": due}


def review_drill(drill_id: int, grade: int) -> dict:
    """Grade 0 again, 1 hard, 2 good, 3 easy (SM-2 with quality 2/3/4/5)."""
    row = db.one("SELECT * FROM drills WHERE id=?", (drill_id,))
    if not row:
        raise LookupError("No such drill")
    q = {0: 2, 1: 3, 2: 4, 3: 5}[max(0, min(3, grade))]
    ease, interval, reps, lapses = row["ease"], row["interval"], row["reps"], row["lapses"]
    if q < 3:
        reps, interval, lapses = 0, 10 / 1440, lapses + 1  # see it again in ten minutes
    else:
        reps += 1
        interval = 1 if reps == 1 else 3 if reps == 2 else math.ceil(interval * ease)
        if q == 3:
            interval = max(1, interval * 0.6)
    ease = max(1.3, ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    due = now() + interval * DAY
    db.execute("UPDATE drills SET ease=?, interval=?, reps=?, lapses=?, due=? WHERE id=?",
               (ease, interval, reps, lapses, due, drill_id))
    return {"due": due, "interval_days": interval}


# --- profile ---------------------------------------------------------------------

def profile() -> dict:
    games = 0
    accs: list[float] = []
    phases: dict[str, dict] = {}
    counts: dict[str, int] = {c: 0 for c in C.CLASSES}
    for row in db.all("SELECT id, analysis FROM games WHERE analysis IS NOT NULL"):
        side = get_side(row["id"])
        if side not in ("white", "black"):
            continue
        result = json.loads(row["analysis"])
        games += 1
        if result["summary"]["accuracy"].get(side) is not None:
            accs.append(result["summary"]["accuracy"][side])
        for f in result["facts"]:
            if f["color"] != side or f["classification"] == "book":
                continue
            p = phases.setdefault(f["phase"], {"phase": f["phase"], "moves": 0, "loss": 0.0, "mistakes": 0})
            p["moves"] += 1
            p["loss"] += -f["win_delta"]
            p["mistakes"] += f["classification"] in ("mistake", "blunder", "miss")
            counts[f["classification"]] += 1
    themes: dict[str, int] = {}
    for row in db.all("SELECT themes FROM drills"):
        for t in json.loads(row["themes"]):
            if t not in ("castling",):
                themes[t] = themes.get(t, 0) + 1
    order = {"opening": 0, "middlegame": 1, "endgame": 2}
    return {
        "games": games,
        "avg_accuracy": round(sum(accs) / len(accs), 1) if accs else None,
        "by_phase": sorted(({"phase": p["phase"], "moves": p["moves"], "mistakes": p["mistakes"],
                             "avg_loss": round(p["loss"] / p["moves"], 1)} for p in phases.values()),
                           key=lambda p: order.get(p["phase"], 9)),
        "by_theme": sorted(({"theme": t, "count": n} for t, n in themes.items()), key=lambda x: -x["count"]),
        "counts": counts,
    }
