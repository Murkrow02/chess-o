"""Turn a facts object into a compact prompt. The LLM sees facts, never a board to analyse.

Small models misread raw engine lines, so moves are spelled out in words and the material
outcome of each line is computed here, from the engine's own PV.
"""

import chess

from .. import classify as C
from ..features import NAMES, material_balance
from ..locale import load
from .validate import allowed_set


def fmt_eval(score: dict | None) -> str:
    if not score:
        return "?"
    if score.get("terminal") == "checkmate":
        return "checkmate"
    if score.get("terminal") == "draw":
        return "draw"
    if "mate" in score:
        m = score["mate"]
        return f"White mates in {m}" if m > 0 else f"Black mates in {-m}"
    return f"{score['cp'] / 100:+.2f}"


def _who(color: str, player_side: str | None) -> str:
    if player_side is None:
        return color.capitalize()
    return f"you ({color.capitalize()})" if color == player_side else f"your opponent ({color.capitalize()})"


def verbal(score: dict, color: str) -> str:
    """The position from `color`'s point of view, in words."""
    w = C.win_for(score, chess.WHITE if color == "white" else chess.BLACK)
    if score.get("terminal") == "checkmate":
        return "won (checkmate)" if w > 50 else "lost (checkmated)"
    if "mate" in score:
        return "winning by force (mate is coming)" if w > 50 else "lost to a forced mate"
    for limit, text in ((90, "winning"), (70, "clearly better"), (58, "slightly better"), (42, "about equal"),
                        (30, "slightly worse"), (10, "clearly worse")):
        if w >= limit:
            return text
    return "losing"


def describe(board: chess.Board, san: str) -> str:
    """'Bxg5' -> 'Bxg5 (bishop takes the pawn on g5, check)'."""
    try:
        move = board.parse_san(san)
    except ValueError:
        return san
    piece = NAMES[board.piece_type_at(move.from_square)]
    to = chess.square_name(move.to_square)
    if board.is_castling(move):
        words = "castles"
    elif board.is_capture(move):
        victim = "pawn" if board.is_en_passant(move) else NAMES[board.piece_type_at(move.to_square)]
        words = f"{piece} takes the {victim} on {to}"
    else:
        words = f"{piece} to {to}"
    if move.promotion:
        words += f", promotes to a {NAMES[move.promotion]}"
    if board.gives_check(move):
        words += ", checkmate" if _mates(board, move) else ", check"
    return f"{san} ({words})"


def _mates(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    try:
        return board.is_checkmate()
    finally:
        board.pop()


def line_outcome(board: chess.Board, sans: list[str], color: str, plies: int = 4,
                 start: int | None = None) -> str | None:
    """Material won or lost by `color` if the line is played out for a few plies.

    `start` is the material balance to compare with; by default the one on `board`.
    """
    b = board.copy(stack=False)
    start = material_balance(b) if start is None else start
    for san in sans[:plies]:
        try:
            b.push_san(san)
        except ValueError:
            break
    diff = (material_balance(b) - start) * (1 if color == "white" else -1)
    if b.is_checkmate():
        return "it ends in checkmate"
    if diff == 0:
        return None
    unit = "pawn" if abs(diff) == 1 else "pawns"
    return f"{color.capitalize()} {'wins' if diff > 0 else 'loses'} about {abs(diff)} {unit} of material"


def facts_text(f: dict, player_side: str | None) -> str:
    lab = load("en")["labels"]  # the prompt itself stays English; only the answer is localized
    color, other = f["color"], ("black" if f["color"] == "white" else "white")
    before = chess.Board(f["fen_before"])
    after = chess.Board(f["fen_after"])
    lines = [
        f"Mover: {_who(color, player_side)}.",
        f"Move played: {f['move_number']}{'.' if color == 'white' else '...'} {describe(before, f['san'])}.",
        f"Verdict: {lab.get(f['classification'], f['classification'])}.",
        f"Before the move {color.capitalize()} was {verbal(f['eval_before'], color)}; "
        f"after it {color.capitalize()} is {verbal(f['eval_after'], color)}.",
    ]
    if f["is_best"]:
        lines.append("This was the engine's top choice.")
    elif f.get("best_move_san"):
        best = f"Better was {describe(before, f['best_move_san'])}."
        outcome = line_outcome(before, f["best_pv_san"], color)
        if outcome:
            best += f" With it, {outcome}."
        lines.append(best)
    if f.get("reply_pv_san") and not f.get("checkmate"):
        reply = f"{other.capitalize()}'s best answer now: {describe(after, f['reply_pv_san'][0])}."
        if not f["is_best"]:
            outcome = line_outcome(after, f["reply_pv_san"], other, start=material_balance(before))
            if outcome:
                reply += f" After that, {outcome}."
        lines.append(reply)
    if f.get("tactic_themes"):
        lines.append(f"Patterns in the move: {', '.join(f['tactic_themes'])}.")
    if f.get("mover_threat"):
        lines.append(f"{color.capitalize()} now threatens {describe(_null(after), f['mover_threat'][0])}.")
    if f.get("opponent_threat_before"):
        lines.append(f"Before the move, {other.capitalize()} was threatening "
                     f"{describe(_null(before), f['opponent_threat_before'][0])}.")
    if f.get("mate_threat"):
        lines.append(f"{color.capitalize()} now threatens mate in {f['mate_threat']}.")
    if f.get("hanging_own"):
        h = f["hanging_own"][0]
        lines.append(f"After the move, {color.capitalize()}'s {h['piece']} on {h['square']} is unprotected and can be won.")
    if f.get("opening"):
        lines.append(f"Opening: {f['opening']['name']} ({f['opening']['eco']}).")
    lines.append(f"Game phase: {f['phase']}.")
    return "\n".join(lines)


def _null(board: chess.Board) -> chess.Board:
    b = board.copy(stack=False)
    b.push(chess.Move.null())
    return b


def build_messages(f: dict, kind: str, player_side: str | None, chunks: list[dict],
                   extra: str = "", max_words: int = 45) -> tuple[list[dict], set[str]]:
    loc = load()
    system = loc["system_prompt"].format(max_words=max_words, language=loc["language"])
    allowed = allowed_set(f)
    parts = ["FACTS", facts_text(f, player_side)]
    mention = [f["san"]] + [m for m in (f.get("best_move_san"), *(f.get("reply_pv_san") or [])[:1],
                                       *(f.get("mover_threat") or [])[:1], *(f.get("opponent_threat_before") or [])[:1])
                            if m and m != f["san"] and (m != f.get("best_move_san") or not f["is_best"])]
    if extra:
        parts += ["", extra]
    if chunks:
        parts += ["", loc["background"]]
        parts += [f"- {c['text'][:600]}" for c in chunks]
    joke = f["classification"] in ("brilliant", "blunder") or f["ply"] % 3 == 0
    if player_side is None:
        subject = loc["subjects"]["neutral"].format(color=f["color"].capitalize())
        voice = loc["voice"]["neutral"]
    else:
        whose = "own" if f["color"] == player_side else "opponent"
        subject = loc["subjects"][whose]
        voice = loc["voice"][whose].format(mover=f["color"].capitalize(), player=player_side.capitalize())
    task = loc["kinds"][kind].format(subject=subject, san=f["san"], best=f.get("best_move_san") or f["san"],
                                     label=load("en")["labels"].get(f["classification"], f["classification"]))
    parts += ["", "MOVES: " + ", ".join(dict.fromkeys(mention)), "", "TASK: " + task, voice,
              loc["style"]["joke" if joke else "plain"]]
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(parts)}], allowed


def template(f: dict) -> str:
    """Deterministic explanation used when the LLM is unavailable or keeps inventing moves."""
    t = load()["templates"]
    reply = ""
    if f.get("reply_pv_san"):
        reply = t["reply_hint"].format(reply=f["reply_pv_san"][0])
    opening = t["opening"].format(opening_name=f["opening"]["name"]) if f.get("opening") else ""
    return t[f["classification"]].format(san=f["san"], best=f.get("best_move_san") or f["san"],
                                         reply_hint=reply, opening=opening)
