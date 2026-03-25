"""Evaluation weights and search parameters for Othello AI."""

# Board position weights (8x8) — how valuable is controlling each square
POSITION_WEIGHTS = [
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
]

# Search parameters
MAX_DEPTH = 1
TIME_LIMIT = 0.08  # seconds per move (hard limit is 0.1s)

# Evaluation component weights
PIECE_COUNT_WEIGHT = 1.0
MOBILITY_WEIGHT = 0.0
CORNER_WEIGHT = 0.0
STABILITY_WEIGHT = 0.0
EDGE_WEIGHT = 0.0

# Endgame threshold (empty squares remaining)
ENDGAME_THRESHOLD = 10
ENDGAME_DEPTH = 10
