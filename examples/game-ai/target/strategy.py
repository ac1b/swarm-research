"""Othello AI strategy. Optimize this to beat stronger opponents."""
import random


def choose_move(board, color, legal_moves):
    """Pick a move from legal_moves.

    Args:
        board: 8x8 list of lists (0=empty, 1=black, 2=white)
        color: your color (1 or 2)
        legal_moves: list of (row, col) tuples
    Returns:
        (row, col) tuple from legal_moves
    """
    return random.choice(legal_moves)
