# SPDX-License-Identifier: MIT
"""Cheap routing checks, usable before importing/loading the neural network."""


def incomplete_terminal(board):
    """True only when empty squares remain and neither color has a legal move."""
    if not isinstance(board, str) or len(board) != 64 or set(board) - set('XO-'):
        raise ValueError('invalid board')
    if '-' not in board:
        return False
    directions = [(r, c) for r in (-1, 0, 1) for c in (-1, 0, 1) if r or c]
    for square, value in enumerate(board):
        if value != '-':
            continue
        row, col = divmod(square, 8)
        for own, other in [('X', 'O'), ('O', 'X')]:
            for dr, dc in directions:
                r, c, captured = row + dr, col + dc, False
                while 0 <= r < 8 and 0 <= c < 8 and board[8*r+c] == other:
                    captured = True
                    r, c = r + dr, c + dc
                if captured and 0 <= r < 8 and 0 <= c < 8 and board[8*r+c] == own:
                    return False
    return True
