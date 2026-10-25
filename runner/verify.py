# SPDX-License-Identifier: MIT
"""Independent standard-library Othello replay. No solver or model dependency."""
from __future__ import annotations

INITIAL = '---------------------------OX------XO---------------------------'
DIRECTIONS = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)


class InvalidRecord(ValueError):
    """A move sequence or target does not satisfy the standard Othello rules."""


def _flips(board: list[str], square: int, color: str) -> list[int]:
    if board[square] != '-':
        return []
    other = 'O' if color == 'X' else 'X'
    row, col = divmod(square, 8)
    changed: list[int] = []
    for dr, dc in DIRECTIONS:
        line: list[int] = []
        r, c = row + dr, col + dc
        while 0 <= r < 8 and 0 <= c < 8 and board[r * 8 + c] == other:
            line.append(r * 8 + c)
            r, c = r + dr, c + dc
        if line and 0 <= r < 8 and 0 <= c < 8 and board[r * 8 + c] == color:
            changed.extend(line)
    return changed


def _can_play(board: list[str], color: str) -> bool:
    return any(_flips(board, square, color) for square in range(64))


def verify(moves: list[str], target: str) -> dict:
    """Replay from the standard initial board, returning a normalized record.

    Coordinates are lower-case ``a1``..``h8``; a1 is the first target character.
    X (black) moves first. A missing forced pass is inserted only when the side
    to move has no legal placement and the opponent does. Terminal passes are
    not moves: both sides unable to play means the game has already ended.

    Raises InvalidRecord (a ValueError subclass) for invalid input, illegal
    moves/passes, actions after termination, or any mismatch in the 64 cells.
    """
    if not isinstance(target, str) or len(target) != 64 or any(c not in 'XO-' for c in target):
        raise InvalidRecord('target must be exactly 64 X/O/- characters')
    if not isinstance(moves, list):
        raise InvalidRecord('moves must be a JSON-style array of strings')
    board = list(INITIAL)
    side = 'X'
    normalized: list[str] = []
    placements = passes = 0
    for index, move in enumerate(moves):
        if not isinstance(move, str):
            raise InvalidRecord(f'move {index}: expected a coordinate or pass string')
        other = 'O' if side == 'X' else 'X'
        if move == 'pass':
            if _can_play(board, side):
                raise InvalidRecord(f'move {index}: pass is illegal while a placement exists')
            if not _can_play(board, other):
                raise InvalidRecord(f'move {index}: terminal game cannot contain another pass')
            normalized.append('pass')
            passes += 1
            side = other
            continue
        if len(move) != 2 or move[0] not in 'abcdefgh' or move[1] not in '12345678':
            raise InvalidRecord(f'move {index}: expected lower-case a1..h8 or pass')
        square = (int(move[1]) - 1) * 8 + 'abcdefgh'.index(move[0])
        changed = _flips(board, square, side)
        if not changed:
            # An illegal placement alone never authorizes changing the color.
            if _can_play(board, side):
                raise InvalidRecord(f'move {index}: illegal placement; side to move still has legal moves')
            if not _can_play(board, other):
                raise InvalidRecord(f'move {index}: game has already terminated')
            changed = _flips(board, square, other)
            if not changed:
                raise InvalidRecord(f'move {index}: placement is illegal after the forced pass')
            normalized.append('pass')
            passes += 1
            side, other = other, side
        for position in [square, *changed]:
            board[position] = side
        normalized.append(move)
        placements += 1
        side = other
    if ''.join(board) != target:
        raise InvalidRecord('replayed position does not match the complete 64-cell target')
    terminal = not _can_play(board, 'X') and not _can_play(board, 'O')
    return {'moves': normalized, 'terminal': terminal, 'placements': placements, 'passes': passes}
