"""到達不能な盤面の各マスについて「そのマスだけ色の条件を外す」と到達可能になるかを調べる。

到達可能になるマス = そのマスの石を裏返すだけで盤面が到達可能になる（到達不能の原因に必ず関わるマス）。
usage: python3 ml/single_free.py 黒hex,白hex [--time 900] [--jobs 5] [--log out.jsonl]
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unsat_core import check

board = sys.argv[1]
limit = int(sys.argv[sys.argv.index("--time") + 1]) if "--time" in sys.argv else 900
jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 5
log = open(sys.argv[sys.argv.index("--log") + 1], "a") if "--log" in sys.argv else None
name = lambda s: "abcdefgh"[s % 8] + str(s // 8 + 1)


def one(s):
    t = time.time()
    r = check(board, set(range(64)) - {s}, limit)
    rec = {"sq": name(s), "s": s, "result": {True: "unreachable", False: "reachable", None: "timeout"}[r], "secs": round(time.time() - t)}
    print(json.dumps(rec), flush=True)
    if log:
        log.write(json.dumps(rec) + "\n"); log.flush()
    return rec


with ThreadPoolExecutor(jobs) as ex:
    res = {r["s"]: r["result"] for r in ex.map(one, range(64))}
mark = {"reachable": "R", "unreachable": ".", "timeout": "?"}
b, w = (int(x, 16) for x in board.split(","))
print("凡例: R = そのマスを裏返せば到達可能 / . = 変えても到達不能 / ? = 時間切れ（括弧内は今の色）")
print("    a  b  c  d  e  f  g  h")
for r in range(8):
    print(f"{r + 1}  " + " ".join(mark[res[r * 8 + c]] + ("x" if b >> (r * 8 + c) & 1 else "o") for c in range(8)))
