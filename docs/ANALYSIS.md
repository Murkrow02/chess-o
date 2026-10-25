# How chess-o judges a game

Everything here is computed by Stockfish and plain Python. The language model (Giacomino)
never calculates anything: it only puts these facts into words.

## Engine passes

1. **Scan.** Every position of the game is analysed at depth 14 with MultiPV 3, spread over a
   pool of single-threaded Stockfish processes (one per CPU core minus one). For each position
   the app also runs a *threat probe*: a null move followed by a depth-10 search, which shows
   what the side that just moved would play if it could move again.
2. **Deep pass.** The key moments (below) are re-analysed at depth 20 and reclassified.
3. **Cache.** Results are stored by `FEN (first four fields) | depth | multipv`, so the same
   position is never searched twice, across games too. In-flight requests for the same position
   are merged.

Depths and MultiPV are set through `ENGINE_DEPTH`, `ENGINE_DEEP_DEPTH` and `ENGINE_MULTIPV`.

## Win probability

The lichess formula, from White's side, with centipawns clamped to ±10000:

```
win% = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)
```

A forced mate counts as 100 or 0. Every move is judged by the drop in the mover's win%:

```
loss = win%(best move) - win%(played move)       # both from the mover's side, never negative
```

## Classification

| Class | Rule |
|---|---|
| Book | The position after the move is in the opening table (lichess chess-openings, CC0) and every earlier move was book too. |
| Best | The engine's first choice, or the only legal move. |
| Excellent | loss ≤ 2 |
| Good | loss ≤ 5 |
| Inaccuracy | loss ≤ 10 |
| Mistake | loss ≤ 20 |
| Blunder | loss > 20 |
| Brilliant | loss ≤ 2, the move is a sacrifice, the mover was not already winning (best < 85%) and stays at 45% or better. |
| Great | loss ≤ 2 and either the only good move (the second line is at least 15 points worse and below 90%) or a turnaround (below 50% before the opponent's last move, 60% or better now). |
| Miss | The opponent's previous move handed over at least 15 points and this move gives at least 10 of them back, or a forced mate was missed (loss ≥ 5). A blunder stays a blunder unless the position ends up no worse than before the opponent's error. |

A move is a **sacrifice** when, after it, the mover's material that the opponent can win by
capture (static exchange evaluation) exceeds what the move captured by at least two pawns and
went up compared with before. Promotions and mating moves do not count.

## Accuracy

Per move, from the mover's win% before and after (the lichess curve with its +1 bonus):

```
accuracy = 103.1668 * exp(-0.04354 * max(0, before - after)) - 3.1669 + 1      # clamped 0..100
```

Per game and side, the move accuracies are combined two ways and averaged:

- a mean weighted by volatility: each move's weight is the standard deviation of the win%
  over a window around it (window = moves / 10, between 2 and 8; weight clamped 0.5 to 12),
  so moves in sharp positions count more;
- a harmonic mean, which punishes a single collapse.

## Rating estimate

```
rating = 3100 * exp(-0.01 * average centipawn loss)       # rounded to 50, clamped 100..3000
```

Book moves are left out of the average. This is a rough indication of how well the game was
played, not a rating.

## Key moments

Up to five plies: mistakes, misses and blunders ordered by how much they cost, then brilliant
and great moves. If a game has fewer than three, the largest swings fill the list. These get
the deep pass and are what "Review key moments" steps through.

## Facts per move

The coach receives a facts object for each move. The main fields:

- `san`, `color`, `ply`, `phase` (opening, middlegame or endgame by material and move number);
- `classification`, `win_before`, `win_after`, `win_delta`, `cp_loss`, `is_best`;
- `best_move_san` and its line `best_pv_san`, the opponent's reply line `reply_pv_san`, other
  candidate lines `alt_lines`;
- `mover_threat`: what the mover threatens next (only if it would gain 15+ points);
  `opponent_threat_before`: what the opponent threatened before the move; `mate_threat`;
- `hanging_own`, `hanging_opponent`: pieces that can be won by capture;
- `material_change`, `captured_value`, `sacrifice`, `tactic_themes` (fork, pin, skewer,
  discovered attack or check, sacrifice, back rank, promotion, castling, checkmate);
- `opening` name and ECO code.

## What the coach may say

The prompt lists the only moves Giacomino may name (the played move, the best move, the
first reply and the threats). After generation every move in the text is checked against
all the engine lines supplied; if one is foreign the model gets a stricter second try, and if
that fails too a fixed template is shown instead. Emoji and markdown are stripped.

## Background knowledge

For moves with something to teach (a pattern, a loose piece, a big swing, the endgame) the
coach also receives one short passage from the knowledge base: the Wikibooks page for the
exact position in the opening (matched by position, so transpositions count), or the closest
Wikipedia/book passage by meaning (bge-m3 embeddings, cosine distance ≤ 0.29). The sources
are shown under the explanation.
