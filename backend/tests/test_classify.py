import chess
import pytest

from app import classify as C


def cls(**kw):
    base = dict(color=chess.WHITE, is_book=False, is_best=False, loss=0.0, win_best=50.0, win_played=50.0,
                win_second=None, win_before_opp=None, sacrifice=False, best_is_mate=False, played_keeps_mate=False)
    return C.classify(**{**base, **kw})


def test_win_probability_is_symmetric_and_bounded():
    assert C.win_white({"cp": 0}) == pytest.approx(50)
    assert C.win_white({"cp": 300}) + C.win_white({"cp": -300}) == pytest.approx(100)
    assert C.win_white({"mate": 3}) == 100 and C.win_white({"mate": -1}) == 0
    assert C.win_for({"cp": 300}, chess.BLACK) < 50


@pytest.mark.parametrize("loss,expected", [(0.5, "excellent"), (4, "good"), (8, "inaccuracy"),
                                           (15, "mistake"), (30, "blunder")])
def test_base_thresholds(loss, expected):
    assert cls(loss=loss) == expected


def test_book_and_best():
    assert cls(is_book=True, loss=40) == "book"
    assert cls(is_best=True) == "best"


def test_brilliant_needs_a_sound_sacrifice():
    assert cls(is_best=True, sacrifice=True, win_best=70, win_played=70) == "brilliant"
    # already completely winning: a sacrifice there is not brilliant
    assert cls(is_best=True, sacrifice=True, win_best=97, win_played=97) == "best"
    # unsound: loses too much
    assert cls(loss=12, sacrifice=True, win_best=70, win_played=58) == "mistake"


def test_great_only_move_and_turnaround():
    assert cls(is_best=True, win_best=70, win_played=70, win_second=40) == "great"
    assert cls(is_best=True, win_best=65, win_played=65, win_before_opp=40) == "great"
    assert cls(is_best=True, win_best=70, win_played=70, win_second=66) == "best"


def test_miss_after_opponent_error():
    # the opponent's previous move handed over 30%, we failed to take it
    assert cls(loss=25, win_best=80, win_played=55, win_before_opp=50) == "miss"
    # a plain blunder that also makes things worse than before stays a blunder
    assert cls(loss=60, win_best=80, win_played=20, win_before_opp=50) == "blunder"


def test_missed_mate():
    assert cls(loss=8, win_best=100, win_played=92, best_is_mate=True) == "miss"
    assert cls(loss=8, win_best=100, win_played=92, best_is_mate=True, played_keeps_mate=True) == "inaccuracy"


def test_move_accuracy_curve():
    assert C.move_accuracy(60, 60) == 100
    assert C.move_accuracy(60, 70) == 100  # improving is never penalised
    assert 70 < C.move_accuracy(60, 54) < 80
    assert C.move_accuracy(90, 10) < 5


def test_game_accuracy_perfect_and_bad():
    assert C.game_accuracy([50, 50, 50, 50, 50]) == {"white": 100.0, "black": 100.0}
    acc = C.game_accuracy([50, 30, 32, 10, 12, 5])  # White drops on each of its own moves
    assert acc["white"] < 60 < acc["black"]


def test_game_accuracy_black_moves_first():
    # positions from a FEN with Black to move: the first move belongs to Black
    acc = C.game_accuracy([50, 80, 80], first_color=chess.BLACK)
    assert acc["black"] < 50 and acc["white"] == 100


def test_rating_estimate_monotonic():
    assert C.rating_estimate(10) > C.rating_estimate(40) > C.rating_estimate(100)
    assert C.rating_estimate(10_000) == 100
