"""Opening lookup over the lichess chess-openings dataset (CC0), keyed by position.

Keying by position instead of move order means transpositions are recognised too.
"""

import csv
import io
from functools import lru_cache
from pathlib import Path

import chess
import chess.pgn

TSV = Path(__file__).parent / "data" / "openings.tsv"


def epd(board: chess.Board) -> str:
    return board.epd()


@lru_cache(maxsize=1)
def table() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with TSV.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            game = chess.pgn.read_game(io.StringIO(row["pgn"]))
            if game is None:
                continue
            board = game.board()
            sans = []
            for move in game.mainline_moves():
                sans.append(board.san(move))
                board.push(move)
            key = epd(board)
            # Several names can reach one position; keep the most specific (longest line).
            if key not in out or len(sans) > len(out[key]["moves"]):
                out[key] = {"eco": row["eco"], "name": row["name"], "moves": sans}
    return out


def lookup(board: chess.Board) -> dict | None:
    return table().get(epd(board))


def book_moves(board: chess.Board) -> list[str]:
    """Moves from `board` that stay inside the opening book."""
    out = []
    for move in board.legal_moves:
        board.push(move)
        hit = epd(board) in table()
        board.pop()
        if hit:
            out.append(board.san(move))
    return out
