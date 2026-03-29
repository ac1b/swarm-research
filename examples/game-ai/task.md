---
target: [target/strategy.py, target/weights.py]
eval: python3 eval.py
direction: maximize
rounds: 10
timeout: 45
eval_runs: 1
mode: full
backtrack: 3
max_backtracks: 3
---

# Othello AI Optimization

Optimize an Othello (Reversi) AI to maximize win rate against 4 opponents
of increasing strength.

## Game Rules
- 8x8 board. Black (1) goes first. White (2) second.
- Place a piece to outflank and flip opponent pieces (must flip >= 1).
- Skip turn if no legal moves. Game ends when neither can move.
- Most pieces wins.

## Interface
`choose_move(board, color, legal_moves)` in `strategy.py`:
- `board`: 8x8 list of lists (0=empty, 1=black, 2=white)
- `color`: your color (1 or 2)
- `legal_moves`: list of (row, col) tuples — guaranteed non-empty
- Returns: `(row, col)` — must be in `legal_moves`
- Game timeout: 15s total (keep per-move time reasonable)

## Opponents
1. **Random** — picks uniformly from legal moves
2. **Greedy** — maximizes immediate flips
3. **Positional** — weighted board positions (corners=100, edges=10, X-squares=-25)
4. **Minimax-2** — 2-ply search with piece count + mobility + positional eval

## Scoring
20 games per opponent (10 as black, 10 as white), seeded deterministically.
Score = total_wins / total_games * 100.

## Files
- `target/strategy.py` — search algorithm, move selection, evaluation
- `target/weights.py` — board position weights, search depth, evaluation parameters

## Optimization Space
- Alpha-beta pruning with iterative deepening
- Positional evaluation (corners, edges, stability, mobility)
- Move ordering (killer moves, history heuristic)
- Endgame exact solve
- Time management (deeper search in critical positions)

Baseline (random moves): ~25-30 points. Expert level: 85+.
