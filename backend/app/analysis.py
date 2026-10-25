"""Game analysis pipeline: engine passes, per-move facts, classification and summary."""

import asyncio
import hashlib
import io
import json
from collections.abc import AsyncIterator

import chess
import chess.pgn

from . import classify as C
from . import features as F
from . import openings
from .config import settings
from .db import db, now
from .engine import get_pool

THREAT_DEPTH = 10
KEY_MOMENTS = 5


class PGNError(ValueError):
    pass


def parse_pgn(pgn: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(pgn.strip()))
    if game is None or game.errors:
        raise PGNError(str(game.errors[0]) if game and game.errors else "Could not read a game from this PGN.")
    if not any(True for _ in game.mainline_moves()):
        raise PGNError("This PGN has no moves.")
    return game


def game_id(pgn: str) -> str:
    return hashlib.sha1(pgn.strip().encode()).hexdigest()[:12]


def pv_san(board: chess.Board, ucis: list[str], limit: int = 8) -> list[str]:
    b = board.copy(stack=False)
    out = []
    for u in ucis[:limit]:
        move = chess.Move.from_uci(u)
        if move not in b.legal_moves:
            break
        out.append(b.san(move))
        b.push(move)
    return out


def positions_of(game: chess.pgn.Game) -> tuple[list[chess.Board], list[chess.Move]]:
    board = game.board()
    boards, moves = [board.copy()], []
    for move in game.mainline_moves():
        moves.append(move)
        board.push(move)
        boards.append(board.copy())
    return boards, moves


def store_game(pgn: str, created_at: float | None = None) -> dict:
    game = parse_pgn(pgn)
    gid = game_id(pgn)
    if not db.one("SELECT 1 FROM games WHERE id = ?", (gid,)):
        db.execute("INSERT INTO games (id, pgn, headers, created_at) VALUES (?, ?, ?, ?)",
                   (gid, pgn.strip(), json.dumps(dict(game.headers)), created_at or now()))
    return game_payload(gid, game)


def game_payload(gid: str, game: chess.pgn.Game) -> dict:
    boards, moves = positions_of(game)
    return {
        "id": gid,
        "headers": dict(game.headers),
        "start_fen": boards[0].fen(),
        "moves": [{"ply": i + 1, "san": boards[i].san(m), "uci": m.uci(), "fen": boards[i + 1].fen()}
                  for i, m in enumerate(moves)],
    }


def load_game(gid: str) -> tuple[chess.pgn.Game, dict | None]:
    row = db.one("SELECT pgn, analysis FROM games WHERE id = ?", (gid,))
    if not row:
        raise KeyError(gid)
    return parse_pgn(row["pgn"]), (json.loads(row["analysis"]) if row["analysis"] else None)


def _eval_of(board: chess.Board, lines: list) -> dict:
    return C.terminal_score(board) or (lines[0]["score"] if lines else {"cp": 0})


def _mover_material_at_risk(board: chess.Board, color: chess.Color) -> int:
    hanging = F.hanging_pieces(board, color)
    return hanging[0]["loss"] if hanging else 0


def build_facts(boards: list[chess.Board], moves: list[chess.Move], evals: list[list],
                threats: list[dict | None], key_plies: set[int]) -> list[dict]:
    facts = []
    in_book = True
    opening = None
    for i, move in enumerate(moves):
        before, after = boards[i], boards[i + 1]
        color = before.turn
        lines = evals[i]
        best = lines[0] if lines else None
        eval_before = _eval_of(before, lines)
        eval_after = _eval_of(after, evals[i + 1])

        played_line = next((l for l in lines if l["uci"] and l["uci"][0] == move.uci()), None)
        played_score = C.terminal_score(after) or (played_line["score"] if played_line else eval_after)
        only_move = before.legal_moves.count() == 1
        is_best = only_move or (best is not None and best["uci"][0] == move.uci())

        win_best = C.win_for(best["score"], color) if best else C.win_for(eval_before, color)
        win_played = C.win_for(played_score, color)
        if is_best:
            win_played = max(win_played, win_best)
        loss = max(0.0, win_best - win_played)
        win_second = C.win_for(lines[1]["score"], color) if len(lines) > 1 else None
        win_before_opp = None
        if i > 0:
            win_before_opp = C.win_for(_eval_of(boards[i - 1], evals[i - 1]), color)

        captured_value = 0
        if before.is_capture(move):
            captured = chess.PAWN if before.is_en_passant(move) else before.piece_type_at(move.to_square)
            captured_value = F.VALUES[captured]
        at_risk_before = _mover_material_at_risk(before, color)
        at_risk_after = _mover_material_at_risk(after, color)
        sacrifice = (at_risk_after - captured_value >= 2 and at_risk_after > at_risk_before
                     and not move.promotion and not after.is_checkmate())

        hit = openings.lookup(after)
        if hit:
            opening = {"eco": hit["eco"], "name": hit["name"]}
        is_book = in_book and hit is not None
        in_book = is_book

        best_mate_for_mover = bool(best and "mate" in best["score"] and (best["score"]["mate"] > 0) == (color == chess.WHITE))
        played_mate_for_mover = ("mate" in played_score and (played_score["mate"] > 0) == (color == chess.WHITE)) \
            or played_score.get("terminal") == "checkmate"

        cls = C.classify(color=color, is_book=is_book, is_best=is_best, loss=loss, win_best=win_best,
                         win_played=win_played, win_second=win_second, win_before_opp=win_before_opp,
                         sacrifice=sacrifice, best_is_mate=best_mate_for_mover,
                         played_keeps_mate=played_mate_for_mover)
        if only_move and cls not in ("book",):
            cls = "best"

        mat_before, mat_after = F.material_balance(before), F.material_balance(after)
        threat_after = threats[i + 1]
        threat_before = threats[i]
        cp_loss = 0
        if best:
            sign = 1 if color == chess.WHITE else -1
            cap = lambda s: max(-1000, min(1000, C.cp_of(s)))  # noqa: E731
            cp_loss = max(0, sign * (cap(best["score"]) - cap(played_score)))

        facts.append({
            "ply": i + 1,
            "move_number": before.fullmove_number,
            "color": "white" if color == chess.WHITE else "black",
            "san": before.san(move),
            "uci": move.uci(),
            "fen_before": before.fen(),
            "fen_after": after.fen(),
            "eval_before": eval_before,
            "eval_after": eval_after,
            "win_before": round(win_best, 1),
            "win_after": round(win_played, 1),
            "win_delta": round(-loss, 1),
            "cp_loss": cp_loss,
            "classification": cls,
            "is_best": is_best,
            "best_move_san": pv_san(before, best["uci"], 1)[0] if best else None,
            "best_move_uci": best["uci"][0] if best else None,
            "best_pv_san": pv_san(before, best["uci"]) if best else [],
            "alt_lines": [{"san": pv_san(before, l["uci"], 1)[0], "score": l["score"],
                           "pv_san": pv_san(before, l["uci"])} for l in lines[1:]],
            "reply_pv_san": pv_san(after, evals[i + 1][0]["uci"]) if evals[i + 1] else [],
            "material_before": mat_before,
            "material_after": mat_after,
            "material_change": (mat_after - mat_before) * (1 if color == chess.WHITE else -1),
            "capture": before.is_capture(move),
            "captured_value": captured_value,
            "check": after.is_check(),
            "checkmate": after.is_checkmate(),
            "mover_threat": _threat_text(after, threat_after, color, eval_after),
            "opponent_threat_before": _threat_text(before, threat_before, not color, eval_before),
            "mate_threat": F.mate_threat(threat_after["score"] if threat_after else None, color),
            "hanging_own": F.hanging_pieces(after, color),
            "hanging_opponent": F.hanging_pieces(after, not color),
            "tactic_themes": F.tactic_themes(before, move, after),
            "sacrifice": sacrifice,
            "opening": opening,
            "phase": F.phase(after, i + 1),
            "is_key_moment": (i + 1) in key_plies,
        })
    return facts


def _threat_text(board: chess.Board, threat: dict | None, color: chess.Color, current: dict) -> list[str] | None:
    """The null-move probe line for `color` (the side not to move), if it is a real threat.

    A threat counts when moving twice would gain `color` at least 15 win-% points.
    """
    if not threat or not threat["uci"]:
        return None
    if C.win_for(threat["score"], color) - C.win_for(current, color) < 15:
        return None
    probe = board.copy(stack=False)
    probe.push(chess.Move.null())
    return pv_san(probe, threat["uci"], 3) or None


def pick_key_moments(facts: list[dict]) -> set[int]:
    bad = [f for f in facts if f["classification"] in ("blunder", "mistake", "miss")]
    good = [f for f in facts if f["classification"] in ("brilliant", "great")]
    ranked = sorted(bad, key=lambda f: f["win_delta"]) + good
    if len(ranked) < 3:
        swings = sorted(facts, key=lambda f: f["win_delta"])
        ranked += [f for f in swings if f not in ranked]
    return {f["ply"] for f in ranked[:KEY_MOMENTS]}


def summarize(facts: list[dict], evals_white: list[float], headers: dict, first_color: chess.Color) -> dict:
    acc = C.game_accuracy(evals_white, first_color)
    out = {"accuracy": acc, "players": {}, "opening": None, "key_moments": []}
    for side in ("white", "black"):
        mine = [f for f in facts if f["color"] == side]
        counts = {c: 0 for c in C.CLASSES}
        for f in mine:
            counts[f["classification"]] += 1
        scored = [f["cp_loss"] for f in mine if f["classification"] != "book"]
        avg = sum(scored) / len(scored) if scored else 0
        out["players"][side] = {
            "name": headers.get(side.capitalize(), side.capitalize()),
            "elo": headers.get(f"{side.capitalize()}Elo"),
            "counts": counts,
            "avg_cp_loss": round(avg, 1),
            "rating_estimate": C.rating_estimate(avg) if scored else None,
        }
    openings_seen = [f["opening"] for f in facts if f["opening"]]
    out["opening"] = openings_seen[-1] if openings_seen else None
    out["key_moments"] = [f["ply"] for f in facts if f["is_key_moment"]]
    out["result"] = headers.get("Result", "*")
    return out


async def analyze(gid: str, force: bool = False) -> AsyncIterator[dict]:
    """Analyse a stored game, yielding progress events and finally the full result."""
    game, cached = load_game(gid)
    if cached and not force:
        yield {"event": "analysis", "data": cached}
        return

    pool = get_pool()
    boards, moves = positions_of(game)
    depth, deep, multipv = settings.engine_depth, settings.engine_deep_depth, settings.engine_multipv
    evals: list[list] = [[] for _ in boards]
    threats: list[dict | None] = [None for _ in boards]

    async def one(i: int):
        evals[i] = await pool.analyse(boards[i], depth, multipv)
        threats[i] = await pool.threat(boards[i], THREAT_DEPTH)
        return i

    total = len(boards)
    done = 0
    yield {"event": "progress", "data": {"phase": "scan", "done": 0, "total": total}}
    for fut in asyncio.as_completed([one(i) for i in range(total)]):
        i = await fut
        done += 1
        score = _eval_of(boards[i], evals[i])
        yield {"event": "eval", "data": {"index": i, "score": score, "win": round(C.win_white(score), 1)}}
        yield {"event": "progress", "data": {"phase": "scan", "done": done, "total": total}}

    facts = build_facts(boards, moves, evals, threats, set())
    key = pick_key_moments(facts)

    # Second pass: look deeper at the moments that decided the game.
    targets = sorted({p - 1 for p in key} | {p for p in key})
    yield {"event": "progress", "data": {"phase": "deep", "done": 0, "total": len(targets)}}

    async def deeper(i: int):
        evals[i] = await pool.analyse(boards[i], deep, multipv)
        return i

    done = 0
    for fut in asyncio.as_completed([deeper(i) for i in targets]):
        await fut
        done += 1
        yield {"event": "progress", "data": {"phase": "deep", "done": done, "total": len(targets)}}

    facts = build_facts(boards, moves, evals, threats, key)
    wins = [round(C.win_white(_eval_of(b, e)), 1) for b, e in zip(boards, evals)]
    result = {
        "game": game_payload(gid, game),
        "facts": facts,
        "wins": wins,
        "evals": [_eval_of(b, e) for b, e in zip(boards, evals)],
        "summary": summarize(facts, wins, dict(game.headers), boards[0].turn),
        "depth": {"scan": depth, "deep": deep, "multipv": multipv},
    }
    db.execute("UPDATE games SET analysis = ?, summary = ? WHERE id = ?",
               (json.dumps(result), json.dumps(result["summary"]), gid))
    yield {"event": "analysis", "data": result}
