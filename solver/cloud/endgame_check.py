"""Generate fresh legal terminal positions, solve from board only, replay independently.

Run in the image: python cloud/endgame_check.py --time 90 --output /tmp/endgames.json
The original game record is kept only as evidence and is never passed to the solver.
"""
import argparse
import json
import os
import random
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = os.environ.get("OTHELLO_BIN", str(ROOT / "target/release/othello-retro"))
DIRS = [(r, c) for r in (-1, 0, 1) for c in (-1, 0, 1) if r or c]
INITIAL = ["-"] * 64
for s, color in ((27, "O"), (28, "X"), (35, "X"), (36, "O")):
    INITIAL[s] = color


def flips(board, square, color):
    if board[square] != "-":
        return []
    opponent = "O" if color == "X" else "X"
    r0, c0 = divmod(square, 8)
    result = []
    for dr, dc in DIRS:
        line = []
        r, c = r0 + dr, c0 + dc
        while 0 <= r < 8 and 0 <= c < 8 and board[r * 8 + c] == opponent:
            line.append(r * 8 + c)
            r, c = r + dr, c + dc
        if line and 0 <= r < 8 and 0 <= c < 8 and board[r * 8 + c] == color:
            result.extend(line)
    return result


def legal(board, color):
    return [(s, f) for s in range(64) if (f := flips(board, s, color))]


def replay(record):
    board, color = INITIAL.copy(), "X"
    for move in record:
        if move == "pass":
            assert not legal(board, color), "illegal pass"
            assert legal(board, "O" if color == "X" else "X"), "move after game end"
        else:
            assert len(move) == 2 and move[0] in "abcdefgh" and move[1] in "12345678"
            square = (int(move[1]) - 1) * 8 + "abcdefgh".index(move[0])
            changed = flips(board, square, color)
            assert changed, f"illegal {color} move {move}"
            for s in [square, *changed]:
                board[s] = color
        color = "O" if color == "X" else "X"
    return board


def fixtures():
    rng = random.Random(20261025)
    selected = {"full-no-pass": [], "full-with-pass": [], "early-terminal": []}
    for game in range(1000):
        board, color, record = INITIAL.copy(), "X", []
        while True:
            choices = legal(board, color)
            opponent = "O" if color == "X" else "X"
            if not choices:
                if not legal(board, opponent):
                    break
                record.append("pass")
            else:
                square, changed = rng.choice(choices)
                for s in [square, *changed]:
                    board[s] = color
                record.append("abcdefgh"[square % 8] + str(square // 8 + 1))
            color = opponent
        kind = "early-terminal" if "-" in board else "full-with-pass" if "pass" in record else "full-no-pass"
        needed = 1 if kind == "early-terminal" else 2
        if len(selected[kind]) < needed:
            assert replay(record) == board
            selected[kind].append({"name": f"{kind}-{len(selected[kind]) + 1}", "board": "".join(board),
                                   "original_record": record, "generation_game": game})
        if all(len(selected[k]) == (1 if k == "early-terminal" else 2) for k in selected):
            break
    assert all(selected.values())
    return [case for cases in selected.values() for case in cases]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--time", type=int, default=90)
    parser.add_argument("--output", default="/tmp/endgames.json")
    args = parser.parse_args()
    results = []
    for case in fixtures():
        board = list(case["board"])
        assert not legal(board, "X") and not legal(board, "O"), "not terminal"
        start = time.monotonic()
        proc = subprocess.Popen([BIN, "solve", "--json", "--time", str(args.time)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, start_new_session=True)
        try:
            output, error = proc.communicate(case["board"], timeout=args.time + 15)
            result = json.loads(output.strip().splitlines()[-1])
        except subprocess.TimeoutExpired:
            import os
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            result = {"status": "unknown", "moves": [], "reason": "external deadline"}
        if result["status"] == "found":
            assert replay(result["moves"]) == board, "independent replay mismatch"
        # The independent forward game proves reachability, so 'unreachable' is a bug.
        assert result["status"] != "unreachable", result
        row = {**case, "empty": board.count("-"), "original_passes": case["original_record"].count("pass"),
               "result": result, "wall_s": round(time.monotonic() - start, 3),
               "replay_verified": result["status"] == "found"}
        results.append(row)
        Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(json.dumps({k: v for k, v in row.items() if k not in {"board", "original_record", "result"}} |
                         {"status": result["status"], "recovered_passes": result.get("moves", []).count("pass")}), flush=True)


if __name__ == "__main__":
    main()
