"""Othello AI evaluator. Plays against 4 opponents of increasing strength."""
import importlib.util
import random
import sys
import time

# ── Othello Engine ─────────────────────────────────────────────────────
EMPTY, BLACK, WHITE = 0, 1, 2
DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def new_board():
    b = [[EMPTY] * 8 for _ in range(8)]
    b[3][3] = WHITE; b[3][4] = BLACK
    b[4][3] = BLACK; b[4][4] = WHITE
    return b


def copy_board(b):
    return [row[:] for row in b]


def opp(color):
    return WHITE if color == BLACK else BLACK


def _flips(board, r, c, color, dr, dc):
    o = opp(color)
    fl = []
    r2, c2 = r + dr, c + dc
    while 0 <= r2 < 8 and 0 <= c2 < 8 and board[r2][c2] == o:
        fl.append((r2, c2))
        r2 += dr; c2 += dc
    if fl and 0 <= r2 < 8 and 0 <= c2 < 8 and board[r2][c2] == color:
        return fl
    return []


def legal_moves(board, color):
    moves = []
    for r in range(8):
        for c in range(8):
            if board[r][c] != EMPTY:
                continue
            for dr, dc in DIRS:
                if _flips(board, r, c, color, dr, dc):
                    moves.append((r, c))
                    break
    return moves


def apply_move(board, r, c, color):
    b = copy_board(board)
    b[r][c] = color
    for dr, dc in DIRS:
        for fr, fc in _flips(board, r, c, color, dr, dc):
            b[fr][fc] = color
    return b


def count_flips(board, r, c, color):
    total = 0
    for dr, dc in DIRS:
        total += len(_flips(board, r, c, color, dr, dc))
    return total


def count_pieces(board):
    b = w = 0
    for row in board:
        for cell in row:
            if cell == BLACK: b += 1
            elif cell == WHITE: w += 1
    return b, w


def play_game(black_fn, white_fn, timeout=15.0):
    """Play one game. Returns 1.0 (black wins), 0.0 (white wins), 0.5 (tie)."""
    board = new_board()
    current = BLACK
    passes = 0
    start = time.time()
    while passes < 2 and time.time() - start < timeout:
        moves = legal_moves(board, current)
        if not moves:
            passes += 1
            current = opp(current)
            continue
        passes = 0
        fn = black_fn if current == BLACK else white_fn
        try:
            move = fn(copy_board(board), current, list(moves))
            if move not in moves:
                return 0.0 if current == BLACK else 1.0
        except Exception:
            return 0.0 if current == BLACK else 1.0
        board = apply_move(board, move[0], move[1], current)
        current = opp(current)
    b, w = count_pieces(board)
    if b > w: return 1.0
    if w > b: return 0.0
    return 0.5


# ── Opponents ──────────────────────────────────────────────────────────

def random_player(board, color, moves):
    return random.choice(moves)


def greedy_player(board, color, moves):
    """Maximize immediate flips."""
    return max(moves, key=lambda m: count_flips(board, m[0], m[1], color))


# Positional weights for the positional player
_POS_W = [
    [100, -25, 10,  5,  5, 10, -25, 100],
    [-25, -50, -2, -2, -2, -2, -50, -25],
    [ 10,  -2,  1,  1,  1,  1,  -2,  10],
    [  5,  -2,  1,  0,  0,  1,  -2,   5],
    [  5,  -2,  1,  0,  0,  1,  -2,   5],
    [ 10,  -2,  1,  1,  1,  1,  -2,  10],
    [-25, -50, -2, -2, -2, -2, -50, -25],
    [100, -25, 10,  5,  5, 10, -25, 100],
]


def positional_player(board, color, moves):
    """Pick move with highest positional weight."""
    return max(moves, key=lambda m: _POS_W[m[0]][m[1]])


def _minimax_eval(board, color):
    """Evaluation: piece count + mobility + positional."""
    b, w = count_pieces(board)
    my = b if color == BLACK else w
    their = w if color == BLACK else b
    piece_diff = my - their

    my_mob = len(legal_moves(board, color))
    their_mob = len(legal_moves(board, opp(color)))
    mob_diff = my_mob - their_mob

    pos_score = 0
    for r in range(8):
        for c in range(8):
            if board[r][c] == color:
                pos_score += _POS_W[r][c]
            elif board[r][c] == opp(color):
                pos_score -= _POS_W[r][c]

    return piece_diff + 2.0 * mob_diff + 0.5 * pos_score


def _minimax(board, color, depth, maximizing, original_color, alpha, beta):
    moves = legal_moves(board, color)
    if depth == 0 or not moves:
        return _minimax_eval(board, original_color), None

    if maximizing:
        best_score = -float("inf")
        best_move = moves[0]
        for m in moves:
            nb = apply_move(board, m[0], m[1], color)
            sc, _ = _minimax(nb, opp(color), depth - 1, False, original_color, alpha, beta)
            if sc > best_score:
                best_score = sc
                best_move = m
            alpha = max(alpha, sc)
            if beta <= alpha:
                break
        return best_score, best_move
    else:
        best_score = float("inf")
        best_move = moves[0]
        for m in moves:
            nb = apply_move(board, m[0], m[1], color)
            sc, _ = _minimax(nb, opp(color), depth - 1, True, original_color, alpha, beta)
            if sc < best_score:
                best_score = sc
                best_move = m
            beta = min(beta, sc)
            if beta <= alpha:
                break
        return best_score, best_move


def minimax_player(board, color, moves):
    """2-ply minimax with alpha-beta."""
    _, move = _minimax(board, color, 2, True, color, -float("inf"), float("inf"))
    return move if move in moves else moves[0]


# ── Evaluation ─────────────────────────────────────────────────────────

def load_strategy():
    spec = importlib.util.spec_from_file_location("strategy", "target/strategy.py")
    mod = importlib.util.module_from_spec(spec)
    # Load weights first so strategy can import them
    wspec = importlib.util.spec_from_file_location("weights", "target/weights.py")
    wmod = importlib.util.module_from_spec(wspec)
    sys.modules["weights"] = wmod
    wspec.loader.exec_module(wmod)
    spec.loader.exec_module(mod)
    return mod.choose_move


def evaluate():
    try:
        player_fn = load_strategy()
    except Exception as e:
        print(f"SCORE: 0", flush=True)
        return

    opponents = [
        ("Random", random_player),
        ("Greedy", greedy_player),
        ("Positional", positional_player),
        ("Minimax-2", minimax_player),
    ]

    games_per_opponent = 20  # 10 as black, 10 as white
    total_wins = 0.0
    total_games = 0
    rng = random.Random(42)

    for opp_name, opp_fn in opponents:
        wins = 0.0
        for game_idx in range(games_per_opponent):
            # Seed each game deterministically
            game_seed = rng.randint(0, 2**31)
            random.seed(game_seed)

            if game_idx < games_per_opponent // 2:
                # Player is black
                result = play_game(player_fn, opp_fn)
                wins += result
            else:
                # Player is white
                result = play_game(opp_fn, player_fn)
                wins += (1.0 - result)  # invert: 1=black won = player lost

        wr = wins / games_per_opponent * 100
        total_wins += wins
        total_games += games_per_opponent

    score = total_wins / total_games * 100
    print(f"SCORE: {score:.2f}", flush=True)


if __name__ == "__main__":
    evaluate()
