"""Pick background passages for one move: opening theory by position first, then concepts by meaning.

The coach only gets a passage when the move has something to teach (a pattern, a loose piece,
a big swing, the endgame). Ordinary moves get nothing, which keeps the 4B model on the facts.
"""

import logging
from collections import OrderedDict

import chess
import httpx

from .. import features as F
from . import store
from .embed import embed

log = logging.getLogger(__name__)

# Cosine distance (1 - similarity). Measured on bge-m3 over this corpus: a passage about the
# exact concept lands at 0.18-0.28, loosely related ones from 0.30 up.
MAX_DISTANCE = 0.29
OPENING_PLIES = 24
TEACHING = ("brilliant", "great", "inaccuracy", "mistake", "miss", "blunder")

PHRASES = {
    "fork": "a fork: one piece attacks two enemy pieces at the same time",
    "pin": "a pin: a piece cannot move without exposing a more valuable piece behind it",
    "skewer": "a skewer: a valuable piece is attacked and must move, exposing a piece behind it",
    "discovered attack": "a discovered attack: moving one piece uncovers an attack by another",
    "discovered check": "a discovered check: moving a piece uncovers check from another piece",
    "sacrifice": "a sacrifice: giving up material to gain an attack or a decisive advantage",
    "back rank": "a back-rank weakness: the king is trapped behind its own pawns",
    "promotion": "pawn promotion: a passed pawn reaching the last rank",
    "checkmate": "a checkmating pattern against the king",
    "castling": "castling to bring the king to safety and connect the rooks",
}

_qcache: OrderedDict[str, list[float]] = OrderedDict()


def _themes_of_best(f: dict) -> list[str]:
    if f.get("is_best") or not f.get("best_move_uci"):
        return []
    before = chess.Board(f["fen_before"])
    move = chess.Move.from_uci(f["best_move_uci"])
    if move not in before.legal_moves:
        return []
    after = before.copy(stack=False)
    after.push(move)
    return F.tactic_themes(before, move, after)


def query_for(f: dict) -> str | None:
    """A short description of what the move is about, or None when there is nothing to look up."""
    teaching = f.get("classification") in TEACHING
    bits = []
    themes = f.get("tactic_themes", []) + (_themes_of_best(f) if teaching else [])
    for theme in dict.fromkeys(themes):
        if theme in PHRASES:
            bits.append(PHRASES[theme])
    hanging = [h for h in f.get("hanging_own") or [] if h["piece"] != "pawn"]
    if teaching and hanging:
        bits.append(f"an undefended {hanging[0]['piece']} left hanging that the opponent can win")
    if teaching and f.get("mate_threat"):
        bits.append("a checkmate threat against the king")
    if teaching and f.get("phase") == "endgame":
        bits.append("endgame technique: king activity, passed pawns, opposition")
    if not bits:
        return None
    return "Chess: " + "; ".join(bits[:3]) + "."


async def _vector(text: str) -> list[float]:
    if text in _qcache:
        _qcache.move_to_end(text)
        return _qcache[text]
    vec = (await embed([text], timeout=10.0))[0]
    _qcache[text] = vec
    if len(_qcache) > 512:
        _qcache.popitem(last=False)
    return vec


def _opening(f: dict) -> dict | None:
    if f.get("ply", 99) > OPENING_PLIES:
        return None
    # Only the position actually reached: the page for the previous one lists other moves,
    # which tempts the coach to name moves the engine never suggested.
    return store.by_epd(chess.Board(f["fen_after"]).epd())


async def for_facts(f: dict, k: int = 1) -> list[dict]:
    if store.count() == 0:
        return []
    out = []
    opening = _opening(f)
    if opening:
        out.append(opening)
    q = query_for(f)
    if q:
        try:
            hits = store.search(await _vector(q), k=8, max_distance=MAX_DISTANCE)
        except (httpx.HTTPError, OSError, KeyError):
            log.warning("embedding service unreachable; coaching without background")
            hits = []
        # Prefer Wikipedia/books for concepts: opening pages matched by meaning are usually noise here.
        hits = [h for h in hits if h["source"] != "wikibooks"]
        seen = {o["title"] for o in out}
        for h in hits:
            if h["title"] not in seen and len(out) < k + (1 if opening else 0):
                out.append(h)
                seen.add(h["title"])
    return out
