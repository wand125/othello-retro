"""後ろ向きランダム経路の各局面に到達可能性ラベルを付ける。

経路上では到達可能性が単調（ある局面が到達不能なら、さらに戻した局面も到達不能）なので、
境界を二分探索すれば経路全体にラベルが付く。判定はまず後ろ向き DFS（短時間）、決まらなければ SAT。

usage: python3 ml/label.py walks.jsonl labels.jsonl [--workers 6]
"""
import json, subprocess, sys
from multiprocessing import Pool

BIN = "./target/release/othello-retro"


def check(pos):
    """1 = 到達可能, 0 = 到達不能, None = 不明"""
    for args in (["--method", "backward", "--time", "3"], ["--method", "sat", "--prepass-ms", "0", "--time", "120"]):
        r = subprocess.run([BIN, "solve", "--quiet-board"] if False else [BIN, "solve"] + args,
                           input=pos, capture_output=True, text=True)
        line = r.stdout.splitlines()[0] if r.stdout else ""
        if line.startswith("status: found"):
            return 1, args[1]
        if line.startswith("status: unreachable"):
            return 0, args[1]
    return None, "unknown"


def label_walk(d):
    path = d["path"]
    out = []
    if d["end"] in ("true", "book"):
        return [(p, 1, d["end"]) for p in path], {}
    lo, hi = 0, len(path) - 1  # path[lo] 到達可能, path[hi] 到達不能
    stats = {}
    if d["end"] == "nobook":
        r, how = check(path[hi])
        stats[how] = stats.get(how, 0) + 1
        if r == 1:
            return [(p, 1, "nobook-reach") for p in path], stats
        if r is None:
            hi = None
    unknown = False
    while hi is not None and hi - lo > 1:
        mid = (lo + hi) // 2
        r, how = check(path[mid])
        stats[how] = stats.get(how, 0) + 1
        if r == 1:
            lo = mid
        elif r == 0:
            hi = mid
        else:
            unknown = True
            break
    for i, p in enumerate(path):
        if i <= lo:
            out.append((p, 1, "walk"))
        elif hi is not None and i >= hi and not (unknown and i < hi):
            out.append((p, 0, "walk"))
    return out, stats


def work(line):
    d = json.loads(line)
    labeled, stats = label_walk(d)
    return d["g"], d["walk"], labeled, stats


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 6
    lines = open(src).read().splitlines()
    total = {}
    with Pool(workers) as pool, open(dst, "w") as f:
        for i, (g, walk, labeled, stats) in enumerate(pool.imap_unordered(work, lines)):
            for k, v in stats.items():
                total[k] = total.get(k, 0) + v
            for p, y, src_tag in labeled:
                b, w = p.split(",")
                n = bin(int(b, 16) | int(w, 16)).count("1") - 4
                f.write(json.dumps({"g": g, "walk": walk, "b": b, "w": w, "n": n, "y": y, "src": src_tag}) + "\n")
            f.flush()
            if (i + 1) % 20 == 0:
                print(f"{i + 1}/{len(lines)} walks, checks={total}", flush=True)
    print("done", total)
