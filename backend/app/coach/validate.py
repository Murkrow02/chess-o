"""Reject coach output that mentions moves the engine did not supply."""

import re

SAN = re.compile(
    r"(?<![\w-])(O-O-O|O-O|[KQRBN][a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?|[a-h]x[a-h][1-8](?:=[QRBN])?|[a-h][1-8]=[QRBN])[+#]?(?![\w-])"
)


def normalize(san: str) -> str:
    return san.rstrip("+#!?")


def allowed_set(facts: dict) -> set[str]:
    moves = {facts["san"]}
    if facts.get("best_move_san"):
        moves.add(facts["best_move_san"])
    moves.update(facts.get("best_pv_san") or [])
    moves.update(facts.get("reply_pv_san") or [])
    for line in facts.get("alt_lines") or []:
        moves.update(line.get("pv_san") or [])
    for key in ("mover_threat", "opponent_threat_before"):
        moves.update(facts.get(key) or [])
    return {normalize(m) for m in moves}


def foreign_moves(text: str, allowed: set[str]) -> list[str]:
    """Moves in `text` that are not in `allowed`. Bare squares like e4 are not checked."""
    return [m for m in (normalize(x) for x in SAN.findall(text)) if m not in allowed]


# Pictographs, dingbats and variation selectors: the prompt forbids emoji but small models slip.
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")


def tidy(text: str) -> str:
    """Strip emoji, markdown emphasis and the whitespace they leave behind."""
    text = re.sub(r"(\*{1,2}|_{1,2})(\S[^*_]*?)\1", r"\2", EMOJI.sub("", text))  # markdown emphasis
    return re.sub(r"\s+([.,!?])", r"\1", re.sub(r"[ \t]{2,}", " ", text)).strip()
