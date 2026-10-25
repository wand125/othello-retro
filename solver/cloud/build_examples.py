"""Publish explicitly selected, independently replayed results from this project."""
import hashlib
import json
from pathlib import Path

from endgame_check import INITIAL, flips, legal

ROOT = Path(__file__).resolve().parents[1]


def verify(moves, target=None):
    board, side, normalized = INITIAL.copy(), 'X', []
    for move in moves:
        opponent = 'O' if side == 'X' else 'X'
        if move == 'pass':
            assert not legal(board, side) and legal(board, opponent), 'illegal pass'
            normalized.append('pass'); side = opponent; continue
        assert isinstance(move, str) and len(move) == 2 and move[0] in 'abcdefgh' and move[1] in '12345678'
        square = (int(move[1]) - 1) * 8 + 'abcdefgh'.index(move[0])
        if not legal(board, side) and legal(board, opponent):
            normalized.append('pass'); side = opponent
        changed = flips(board, square, side)
        assert changed, f'illegal {side} move {move}'
        for s in [square, *changed]: board[s] = side
        normalized.append(move); side = 'O' if side == 'X' else 'X'
    if target is not None: assert ''.join(board) == target, 'target mismatch'
    return ''.join(board), normalized



def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build examples only from an explicitly supplied public record file")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "ui/public-examples.json")
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    rows = data["examples"] if isinstance(data, dict) else data
    if not isinstance(rows, list):
        parser.error("input must be a record array or an examples object")
    examples = []
    for row in rows:
        target = row.get("board")
        board, moves = verify(row.get("moves", row.get("reference_moves")), target)
        terminal = not legal(list(board), "X") and not legal(list(board), "O")
        digest = hashlib.sha256((board + "|" + "".join(moves)).encode()).hexdigest()
        examples.append({"id": "game-" + digest[:12], "title": ("終局盤面" if terminal else "途中の盤面") + f"（{64-board.count('-')}石）",
                         "board": board, "moves": moves, "terminal": terminal,
                         "source": "explicit input", "verification": {"legal": True, "target_matches": True, "record_sha256": digest}})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"version": 2, "examples": examples}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"examples": len(examples)}))


if __name__ == "__main__":
    main()
