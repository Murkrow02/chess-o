"""Win probability, move classification, accuracy and a rough rating estimate.

All formulas are documented in docs/ANALYSIS.md.
"""

import math
import statistics

import chess

MATE_CP = 10000
CLASSES = ["brilliant", "great", "best", "excellent", "good", "book",
           "inaccuracy", "mistake", "miss", "blunder"]


def cp_of(score: dict) -> int:
    """White-POV centipawns, mates mapped to +-MATE_CP."""
    if "mate" in score:
        m = score["mate"]
        return MATE_CP if m > 0 else -MATE_CP
    return score["cp"]


def win_white(score: dict) -> float:
    """Lichess win probability for White, 0..100."""
    if "mate" in score:
        return 100.0 if score["mate"] > 0 else 0.0
    cp = max(-MATE_CP, min(MATE_CP, score["cp"]))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def win_for(score: dict, color: chess.Color) -> float:
    w = win_white(score)
    return w if color == chess.WHITE else 100 - w


def terminal_score(board: chess.Board) -> dict | None:
    if board.is_checkmate():
        return {"cp": -MATE_CP if board.turn == chess.WHITE else MATE_CP, "terminal": "checkmate"}
    if board.is_game_over(claim_draw=False):
        return {"cp": 0, "terminal": "draw"}
    return None


def base_class(loss: float, is_best: bool) -> str:
    if is_best:
        return "best"
    if loss <= 2:
        return "excellent"
    if loss <= 5:
        return "good"
    if loss <= 10:
        return "inaccuracy"
    if loss <= 20:
        return "mistake"
    return "blunder"


def classify(*, color: chess.Color, is_book: bool, is_best: bool, loss: float,
             win_best: float, win_played: float, win_second: float | None,
             win_before_opp: float | None, sacrifice: bool, best_is_mate: bool,
             played_keeps_mate: bool) -> str:
    """Classify one move. All win values are from the mover's point of view (0..100).

    win_before_opp is the mover's win chance before the opponent's previous move, so
    `win_best - win_before_opp` is how much that move handed over.
    """
    if is_book:
        return "book"
    cls = base_class(loss, is_best)
    good = loss <= 2

    if good and sacrifice and win_best < 85 and win_played >= 45:
        return "brilliant"

    if good:
        only_move = win_second is not None and win_best - win_second >= 15 and win_second < 90
        turning = win_before_opp is not None and win_before_opp < 50 and win_played >= 60
        if only_move or turning:
            return "great"
        return cls

    chance = win_before_opp is not None and win_best - win_before_opp >= 15
    missed_mate = best_is_mate and not played_keeps_mate and win_best >= 99
    if (chance and loss >= 10) or (missed_mate and loss >= 5):
        if cls != "blunder" or (win_before_opp is not None and win_played >= win_before_opp - 5):
            return "miss"
    return cls


# --- accuracy (lichess method) -------------------------------------------------

def move_accuracy(win_before: float, win_after: float) -> float:
    """Accuracy of one move from the mover's win% before and after, 0..100."""
    diff = max(0.0, win_before - win_after)
    raw = 103.1668100711649 * math.exp(-0.04354415386753951 * diff) - 3.166924740191411
    return max(0.0, min(100.0, raw + 1))  # +1 is lichess' uncertainty bonus


def _harmonic(values: list[float]) -> float:
    vals = [max(v, 1e-3) for v in values]
    return len(vals) / sum(1 / v for v in vals) if vals else 0.0


def game_accuracy(wins_white: list[float], first_color: chess.Color = chess.WHITE) -> dict:
    """Per-side accuracy from the White win% of every position (index 0 = start).

    Each move is weighted by the volatility (standard deviation) of the win% in a window
    around it, then the weighted mean and the harmonic mean are averaged.
    """
    n_moves = len(wins_white) - 1
    if n_moves < 1:
        return {"white": None, "black": None}
    window = max(2, min(8, n_moves // 10))
    padded = [wins_white[0]] * (window - 2) + wins_white
    windows = [padded[i:i + window] for i in range(max(1, len(padded) - window + 1))]
    weights = [max(0.5, min(12.0, statistics.pstdev(w))) for w in windows][:n_moves]
    while len(weights) < n_moves:
        weights.append(weights[-1] if weights else 1.0)

    per = {chess.WHITE: [], chess.BLACK: []}
    color = first_color
    for i in range(n_moves):
        wb, wa = wins_white[i], wins_white[i + 1]
        if color == chess.BLACK:
            wb, wa = 100 - wb, 100 - wa
        per[color].append((move_accuracy(wb, wa), weights[i]))
        color = not color

    out = {}
    for c, key in ((chess.WHITE, "white"), (chess.BLACK, "black")):
        items = per[c]
        if not items:
            out[key] = None
            continue
        accs = [a for a, _ in items]
        weighted = sum(a * w for a, w in items) / sum(w for _, w in items)
        out[key] = round((weighted + _harmonic(accs)) / 2, 1)
    return out


def rating_estimate(avg_cp_loss: float) -> int:
    """Very rough performance estimate from average centipawn loss; shown as an estimate."""
    r = 3100 * math.exp(-0.01 * avg_cp_loss)
    return int(round(max(100, min(3000, r)) / 50) * 50)
