"""Follow-up questions to Giacomino about the move on screen.

The answer is held to the same rule as the explanation: facts in, words out. Moves the player
names in the question are checked by the engine first, so "what about Nf3?" gets a real answer
instead of a guess.
"""

import logging
from collections.abc import AsyncIterator

import chess
import httpx

from .. import analysis
from .. import classify as C
from ..config import settings
from ..engine import get_pool
from ..locale import load
from . import llm
from .prompt import build_messages, describe, verbal
from .service import coach
from .validate import SAN, foreign_moves, normalize, tidy

log = logging.getLogger(__name__)

MAX_PROBES = 2
MAX_QUESTION = 300
MAX_TURN = 500


async def _probe(f: dict, san: str) -> tuple[str, set[str]]:
    """One line of facts about a move the player asked about, plus the moves it may name."""
    color = f["color"]
    other = "black" if color == "white" else "white"
    for fen, mover, instead in ((f["fen_before"], color, True), (f["fen_after"], other, False)):
        board = chess.Board(fen)
        try:
            move = board.parse_san(san)
        except ValueError:
            continue
        said = board.san(move)
        after = board.copy(stack=False)
        after.push(move)
        lines = await get_pool().analyse(after, settings.engine_depth, 1)
        score = C.terminal_score(after) or (lines[0]["score"] if lines else {"cp": 0})
        reply = analysis.pv_san(after, lines[0]["uci"], 1) if lines else []
        when = "instead of the game move" if instead else "in the position after the game move"
        text = f"If {mover.capitalize()} plays {describe(board, said)} {when}, {mover.capitalize()} is {verbal(score, mover)}"
        text += f"; the best answer is {describe(after, reply[0])}." if reply else "."
        # Keep the player's spelling too: they may write Nf4 where the board needs Nhf4.
        return text, {normalize(said), normalize(san), *map(normalize, reply)}
    return f"{san} is not a legal move in this position.", {normalize(san)}


async def answer(f: dict, side: str | None, question: str, history: list[dict]) -> AsyncIterator[dict]:
    loc = load()
    question = question.strip()[:MAX_QUESTION]
    asked = list(dict.fromkeys(normalize(m) for m in SAN.findall(question)))[:MAX_PROBES]
    probes, extra_moves = [], set()
    for san in asked:
        text, moves = await _probe(f, san)
        probes.append(text)
        extra_moves |= moves
    extra = "\n".join(["ASKED MOVES (checked by the engine)", *probes]) if probes else ""
    messages, allowed = build_messages(f, "move", side, [], extra=extra, max_words=70)
    allowed |= extra_moves
    talk = [("Player" if h.get("role") == "player" else loc["coach_name"]) + ": " + str(h.get("text", ""))[:MAX_TURN]
            for h in history[-6:]]
    ask = loc["ask"]
    task = ask["task"].format(question=question)
    content = messages[1]["content"].rsplit("\nTASK: ", 1)[0]
    content += ("\n\nMOVES ALSO ALLOWED: " + ", ".join(sorted(extra_moves)) if extra_moves else "")
    content += "\n\nCONVERSATION SO FAR\n" + "\n".join(talk) if talk else ""
    messages = [{"role": "system", "content": messages[0]["content"] + "\n" + ask["rules"]},
                {"role": "user", "content": content + "\n\nTASK: " + task}]

    tokens: list[str] = []
    coach.cancel_prefetches()
    async with coach.gpu:
        try:
            async for token in llm.stream_chat(messages, max_tokens=200, temperature=0.4):
                tokens.append(token)
                yield {"event": "token", "data": token}
        except (httpx.HTTPError, OSError):
            log.warning("LLM unreachable for a follow-up question")
            yield {"event": "replace", "data": {"text": ask["offline"], "offline": True}}
            return
        text = "".join(tokens).strip()
        bad = foreign_moves(text, allowed)
        if bad:
            log.info("follow-up answer named moves outside the facts %s; regenerating", bad)
            retry = messages + [{"role": "assistant", "content": text}, {"role": "user", "content": loc["stricter"]}]
            try:
                text = (await llm.chat(retry, max_tokens=200, temperature=0.2)).strip()
            except (httpx.HTTPError, OSError):
                text = ""
            if not text or foreign_moves(text, allowed):
                text = ask["fallback"]
            yield {"event": "replace", "data": {"text": tidy(text)}}
        elif tidy(text) != text:
            yield {"event": "replace", "data": {"text": tidy(text)}}
