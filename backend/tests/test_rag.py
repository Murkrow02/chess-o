import chess

from app.rag import retrieve, sources


def test_chunk_sizes():
    text = "\n\n".join(["word " * 60] * 10)  # ten 300-char paragraphs
    chunks = sources.chunk(text, target=650, hard=900)
    assert len(chunks) >= 4
    assert all(120 <= len(c) <= 900 for c in chunks)


def test_strip_wikitext():
    raw = ("{{Chess Opening Theory/Position\n|Ruy López\n|eco=[[Chess/ECOC|C60]]\n}}\n"
           "== 3. Bb5 ==\n'''3. Bb5''' attacks the [[/3...a6|knight]] on c6.<ref>NCO</ref>\n\n"
           "==References==\n{{reflist}}\nNunn.\n[[fi:Shakki]]")
    out = sources.strip_wikitext(raw)
    assert "3. Bb5 attacks the knight on c6." in out
    assert "Nunn" not in out and "{{" not in out and "fi:" not in out


def test_path_board():
    board = sources._path_board("Chess Opening Theory/1. e4/1...e5/2. Nf3")
    expected = chess.Board()
    for san in ("e4", "e5", "Nf3"):
        expected.push_san(san)
    assert board.epd() == expected.epd()
    assert sources._path_board("Chess Opening Theory/1. e4/1...Ke3") is None


def test_prose_filter_drops_game_scores():
    assert sources._prose("The pawn on K 5 cramps Black, and the advance must be prepared carefully " * 3)
    assert not sources._prose("1. P - K 4 P - K 4 2. Kt - KB 3 Kt - QB 3 3. B - Kt 5 P - QR 3 4. B x Kt QP x B")
    assert not sources._prose("In checkers the king row matters a great deal for the endgame " * 3)


def test_query_only_for_teaching_moments():
    quiet = {"classification": "good", "tactic_themes": [], "hanging_own": [{"piece": "knight"}],
             "phase": "middlegame", "is_best": True}
    assert retrieve.query_for(quiet) is None
    blunder = {**quiet, "classification": "blunder", "is_best": True}
    assert "knight" in retrieve.query_for(blunder)
    fork = {**quiet, "tactic_themes": ["fork"]}
    assert "fork" in retrieve.query_for(fork)
