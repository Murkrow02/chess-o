from app.coach.validate import allowed_set, foreign_moves, tidy

FACTS = {"san": "Nxe5", "best_move_san": "Bb5+", "best_pv_san": ["Bb5+", "c6", "O-O"],
         "reply_pv_san": ["Qd4"], "alt_lines": [{"pv_san": ["d4", "exd4"]}], "mover_threat": ["Qh5"]}


def test_allowed_moves_strip_check_marks():
    allowed = allowed_set(FACTS)
    assert {"Nxe5", "Bb5", "O-O", "Qd4", "Qh5", "exd4"} <= allowed


def test_foreign_moves_found():
    allowed = allowed_set(FACTS)
    assert foreign_moves("Nxe5 was fine but Bb5+ was stronger, then O-O.", allowed) == []
    assert foreign_moves("You should play Nf3 or Rxe1+ instead.", allowed) == ["Nf3", "Rxe1"]
    assert foreign_moves("Your e4 pawn and the f7 square.", allowed) == []  # bare squares are fine
    assert foreign_moves("Promote with e8=Q.", allowed) == ["e8=Q"]


def test_tidy_removes_emoji_and_markdown():
    assert tidy("A *sneaky* fork 🐟 . Wow ✨") == "A sneaky fork. Wow"
    assert tidy("**Bold** move") == "Bold move"
