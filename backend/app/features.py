"""Static position features: material, hanging pieces, phase and simple tactic patterns.

These are heuristics that describe a position in words the coach can use. They never
decide whether a move is good; the engine does that.
"""

import chess

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
NAMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
         chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}


def material(board: chess.Board) -> dict:
    """Material count per side in pawn units."""
    out = {}
    for color, key in ((chess.WHITE, "white"), (chess.BLACK, "black")):
        out[key] = sum(VALUES[p] * len(board.pieces(p, color)) for p in VALUES)
    return out


def material_balance(board: chess.Board) -> int:
    m = material(board)
    return m["white"] - m["black"]


def phase(board: chess.Board, ply: int) -> str:
    non_pawn = sum(VALUES[p] * len(board.pieces(p, c)) for p in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
                   for c in chess.COLORS)
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    if non_pawn <= 26 or (queens == 0 and non_pawn <= 30):
        return "endgame"
    if ply <= 20 and non_pawn >= 56:
        return "opening"
    return "middlegame"


def see(board: chess.Board, square: chess.Square, attacker_color: chess.Color) -> int:
    """Static exchange evaluation of capturing on `square` by `attacker_color` (pawn units)."""
    target = board.piece_at(square)
    if target is None:
        return 0
    attackers = [s for s in board.attackers(attacker_color, square)]
    if not attackers:
        return 0
    attacker = min(attackers, key=lambda s: VALUES[board.piece_type_at(s)] or 100)
    move = chess.Move(attacker, square)
    if board.piece_type_at(attacker) == chess.PAWN and chess.square_rank(square) in (0, 7):
        move.promotion = chess.QUEEN
    if move not in board.pseudo_legal_moves:
        return 0
    probe = board.copy(stack=False)
    probe.turn = attacker_color
    if not probe.is_legal(move):
        return 0
    probe.push(move)
    gain = VALUES[target.piece_type] if target.piece_type != chess.KING else 0
    return max(0, gain - see(probe, square, not attacker_color))


def hanging_pieces(board: chess.Board, color: chess.Color) -> list[dict]:
    """Pieces of `color` that the opponent wins material by capturing."""
    out = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != color or piece.piece_type == chess.KING:
            continue
        loss = see(board, square, not color)
        if loss > 0:
            out.append({"piece": NAMES[piece.piece_type], "square": chess.square_name(square), "loss": loss})
    return sorted(out, key=lambda h: -h["loss"])


def _valuable_targets(board: chess.Board, from_sq: chess.Square, color: chess.Color) -> list[chess.Square]:
    mover = board.piece_type_at(from_sq)
    out = []
    for sq in board.attacks(from_sq):
        p = board.piece_at(sq)
        if p and p.color != color:
            if p.piece_type == chess.KING or VALUES[p.piece_type] > VALUES[mover] or not board.is_attacked_by(not color, sq):
                out.append(sq)
    return out


def tactic_themes(before: chess.Board, move: chess.Move, after: chess.Board) -> list[str]:
    """Patterns created by `move` (played from `before`, giving `after`)."""
    themes = []
    color = before.turn
    to = move.to_square
    piece = after.piece_at(to)

    if after.is_checkmate():
        themes.append("checkmate")
    if move.promotion:
        themes.append("promotion")
    if before.is_castling(move):
        themes.append("castling")

    if piece and piece.piece_type != chess.KING:
        targets = _valuable_targets(after, to, color)
        if len(targets) >= 2:
            themes.append("fork")

    # Discovered attack: a line piece behind the moved piece now attacks something.
    for sq in after.pieces(chess.BISHOP, color) | after.pieces(chess.ROOK, color) | after.pieces(chess.QUEEN, color):
        if sq == to:
            continue
        newly = after.attacks(sq) & ~before.attacks(sq)
        for t in newly:
            p = after.piece_at(t)
            if p and p.color != color and (p.piece_type == chess.KING or VALUES[p.piece_type] >= 3):
                themes.append("discovered attack" if not after.is_check() or t != after.king(not color) else "discovered check")
                break

    # Pins and skewers along the moved piece's lines.
    if piece and piece.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        for t in after.attacks(to):
            front = after.piece_at(t)
            if not front or front.color == color:
                continue
            if after.is_pinned(not color, t) and after.pin(not color, t) & chess.BB_SQUARES[to]:
                themes.append("pin")
            behind = _first_beyond(after, to, t)
            if behind is not None:
                back = after.piece_at(behind)
                if back and back.color != color and front.piece_type in (chess.KING, chess.QUEEN, chess.ROOK) \
                        and back.piece_type != chess.KING and VALUES[back.piece_type] >= 3 \
                        and (front.piece_type == chess.KING or VALUES[front.piece_type] > VALUES[back.piece_type]):
                    themes.append("skewer")

    if before.is_capture(move):
        captured = before.piece_at(to) or chess.Piece(chess.PAWN, not color)
        if before.is_en_passant(move):
            captured = chess.Piece(chess.PAWN, not color)
        if VALUES[captured.piece_type] < VALUES[before.piece_type_at(move.from_square)] and after.is_attacked_by(not color, to):
            if see(after, to, not color) > 0:
                themes.append("sacrifice")
    elif piece and piece.piece_type != chess.KING and not move.promotion and see(after, to, not color) >= 2:
        themes.append("sacrifice")

    king = after.king(not color)
    if king is not None and chess.square_rank(king) in (0, 7) and after.is_check():
        rank = chess.square_rank(king)
        escape = [s for s in after.attacks(king) if chess.square_rank(s) != rank and not after.piece_at(s)]
        if not escape:
            themes.append("back rank")

    return list(dict.fromkeys(themes))


def _first_beyond(board: chess.Board, a: chess.Square, b: chess.Square) -> chess.Square | None:
    """The first occupied square beyond `b` on the line from `a` through `b`."""
    df = (chess.square_file(b) > chess.square_file(a)) - (chess.square_file(b) < chess.square_file(a))
    dr = (chess.square_rank(b) > chess.square_rank(a)) - (chess.square_rank(b) < chess.square_rank(a))
    f, r = chess.square_file(b) + df, chess.square_rank(b) + dr
    while 0 <= f < 8 and 0 <= r < 8:
        sq = chess.square(f, r)
        if board.piece_at(sq):
            return sq
        f, r = f + df, r + dr
    return None


def mate_threat(threat_score: dict | None, color_moved: chess.Color) -> int | None:
    """If the null-move probe finds a forced mate for the side that just moved, its length."""
    if not threat_score or "mate" not in threat_score:
        return None
    m = threat_score["mate"]
    if (m > 0) == (color_moved == chess.WHITE):
        return abs(m)
    return None
