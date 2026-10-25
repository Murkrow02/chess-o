# chess-o — build plan

Self-hosted chess game review with an engine-grounded AI coach. Stockfish does all
the chess; a small local LLM only puts the engine's facts into words.

## Stack

| Piece | Choice |
|---|---|
| Frontend | React + Vite + TypeScript, chessground (GPL-3.0), Zustand, hand-written SVG eval graph and icons, WebAudio-synthesized sounds (no third-party audio) |
| Backend | Python 3.12, FastAPI, python-chess, Stockfish (CPU), SQLite (games, analysis cache, drills) |
| Vector store | sqlite-vec inside the backend's SQLite file (no extra container) |
| Embeddings | `bge-m3` on Ollama |
| Coach LLM | Ollama through its OpenAI-compatible API (`LLM_BASE_URL`, `LLM_MODEL`); model chosen by benchmark |
| Serving | nginx serves the SPA and proxies `/api` to the backend; the frontend only uses relative URLs |
| Deploy | docker compose (`frontend`, `backend`), `restart: unless-stopped` |

## Data flow

```
PGN / Lichess / Chess.com import
        │
        ▼
 POST /api/games ──► parse (python-chess) ──► game row
        │
        ▼
 GET /api/games/{id}/analyze  (SSE)
   pass 1: every position, depth ~14, MultiPV 3, engine pool (cores-1 workers, 1 thread each)
   pass 2: key moments only (biggest swings), depth ~20
   position cache: (normalized FEN, depth, multipv) ──► lines
        │
        ▼
 facts builder ──► classification ──► accuracy / rating estimate ──► stored
        │
        ▼
 coach: GET /api/games/{id}/coach/{ply} (SSE)
   facts + retrieved knowledge chunks ──► prompt ──► LLM tokens ──► validator ──► UI
   cached per (game, ply, kind); the UI prefetches the next plies
```

## Engine "brain": more engine calls, aimed at learning

1. **Full-game pass**: fast MultiPV-3 sweep for the eval graph and classification.
2. **Key moments**: deeper re-analysis of the 3–5 biggest win-probability swings; these
   become a short "key moments" review path.
3. **Threat probe**: a null-move search ("what would the opponent do if it were their
   turn?") gives the threat behind a move, used in facts and hints.
4. **Explore variations**: any move played on the board opens a branch; the engine
   answers and the coach explains the refutation ("why not Nxe5?").
5. **Guided retry**: the user retries a mistake with progressive hints (which piece,
   then which square, then the move); each attempt is evaluated live.
6. **Drill deck (SRS)**: the user's own mistakes, blunders and misses become puzzles
   with spaced repetition (SM-2), plus a weakness profile by theme and game phase.

## Classification

- Win probability (lichess sigmoid): `W(cp) = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)`.
  Mate scores map to ±10000 cp before the sigmoid.
- Expected-points loss `Δ = W_best − W_played` (from the mover's side), in [0, 100]:
  Best = engine top move; Excellent ≤ 2; Good ≤ 5; Inaccuracy ≤ 10; Mistake ≤ 20; Blunder > 20.
- **Book**: position found in the lichess chess-openings set (CC0), until the first non-book move.
- **Brilliant**: best or near-best (Δ ≤ 2), gives up material that is not won back
  immediately (static exchange), the mover was not already winning (W < 85 before), and
  the position is not lost after it.
- **Great**: the only good move (second line ≥ 15 points worse) or a turning point
  (losing/equal to winning).
- **Miss**: the opponent's previous move gave a big chance (best line ≥ 15 points better
  than before) and the played move lost ≥ 10 of it, or a forced mate was available and missed.
- **Accuracy**: lichess formula. Per move `103.1668 * exp(-0.04354 * Δ) − 3.1669`, clamped to
  [0, 100]; game accuracy is the mean of the volatility-weighted mean and the harmonic mean.
- **Rating estimate**: a rough curve from accuracy and average loss, clearly labelled as an estimate.

## Facts object (per ply)

`ply, san, uci, color, fen_before/after, eval_before/after (cp|mate), win_before/after,
win_delta, classification, best_move_san, best_pv_san[], alt_lines[{san, eval, pv_san}],
material_before/after/change, capture, check, mate_threat, threat_san (null-move),
hanging_pieces[], tactic_themes[] (fork, pin, skewer, discovered attack, back rank, promotion,
sacrifice), opening {eco, name}, phase (opening|middlegame|endgame), is_key_moment`.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/games` | `{pgn}` → `{id, headers, moves}` |
| GET | `/api/games/{id}` | stored game plus analysis |
| GET | `/api/games/{id}/analyze` | SSE: `progress`, `ply`, `summary`, `done` |
| GET | `/api/import/{lichess\|chesscom}/{user}` | recent public games |
| POST | `/api/engine/position` | `{fen, multipv, depth}` → lines (explore and retry) |
| POST | `/api/games/{id}/retry/{ply}` | `{uci}` → verdict of the attempt |
| GET | `/api/games/{id}/hint/{ply}?level=1..3` | progressive hint |
| GET | `/api/games/{id}/coach/{ply}?kind=move\|retry\|explore` | SSE: `token`, `replace`, `sources`, `done` |
| GET/POST | `/api/drills/due`, `/api/drills/{id}/review` | SRS deck |
| GET | `/api/profile` | weakness profile |

## Coach

- The prompt holds the facts, the allowed move set (played move, best move, PV and
  alternative-line moves) and up to 3 retrieved chunks. It asks for 1–3 sentences, coach tone,
  and only moves from the allowed set.
- Validator: extracts SAN-looking tokens; any move outside the allowed set triggers one
  stricter regeneration, then a templated fallback (`replace` SSE event).
- If the LLM is unreachable, the templated explanation is used, so the app still works.

## RAG

- Sources, all freely licensed, downloaded by `scripts/ingest.py` and not committed:
  lichess chess-openings (CC0); Wikibooks *Chess* and *Chess Opening Theory* (CC BY-SA, pages
  keyed by move sequence, so they map onto positions); a curated list of Wikipedia chess articles
  (CC BY-SA); public-domain classics from Project Gutenberg (Capablanca, *Chess Fundamentals*;
  Edward Lasker, *Chess Strategy*).
- Drop-in folder: `knowledge/custom/` (PDF, Markdown, text); re-run ingest to index it.
- Chunks of about 400 tokens with metadata (source, license, ECO, move path, themes).
- Retrieval: exact opening/move-path lookup first, then vector search on a query built from
  themes, phase and position features; top 2–3 chunks go into the prompt and appear as sources.

## Milestones

- **a**: board, PGN input, engine analysis, classification, eval graph, move list
- **b**: coach with LLM streaming, caching, prefetch, validator; guided retry, explore variations
- **c**: RAG ingest and retrieval, openings
- **d**: summary screen, key moments, drill deck, profile, sounds, polish, README
- Deploy on a home server, then test with real PGNs.
