"""正解経路の兄弟候補に到達可能性ラベルを付ける（パスなし仮定）。

正解の子 → 1。それ以外は短時間 SAT（nopass+occ）: UNSAT → 0、SAT → 1、時間切れ → -1（不明）。
到達不能な局面は SAT が 1 秒前後で否定できる、という実測に基づく。

usage: python3 ml/label_spine.py spine.jsonl out.jsonl [--per 8] [--limit 2] [--workers 8]
"""
import json, os, random, subprocess, sys, tempfile
from multiprocessing import Pool

BIN = os.path.abspath("./target/release/othello-retro")


def sat_label(hexpos, limit):
    with tempfile.NamedTemporaryFile(suffix=".cnf", delete=True) as f:
        subprocess.run([BIN, "cnf", hexpos, "--enc", "nopass,occ"], stdout=f, check=True, stdin=subprocess.DEVNULL)
        f.flush()
        r = subprocess.run(["kissat", "-q", f"--time={limit}", f.name], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    for line in r.stdout.splitlines():
        if line.startswith("s SATISFIABLE"):
            return 1
        if line.startswith("s UNSATISFIABLE"):
            return 0
    return -1


def reach_label(hexpos, c, limit):
    """パスありのデータ用: 次に c が打つ状態で到達できるか（パスは直前 12 手の中だけ許す近似）"""
    out = subprocess.run([BIN, "reach", hexpos, str(c), "--time", str(limit)], capture_output=True, text=True,
                         stdin=subprocess.DEVNULL).stdout.strip()
    return {"sat": 1, "unsat": 0}.get(out, -1)


def work(job):
    meta, child, limit = job
    if child["t"]:
        y = 1
    elif "c" in child:
        y = reach_label(child["q"], child["c"], limit)
    else:
        y = sat_label(child["q"], limit)
    return {**meta, **child, "y": y}


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    opt = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
    per, LIMIT, workers = opt("--per", 8), opt("--limit", 2), opt("--workers", 8)
    rnd = random.Random(1)
    jobs = []
    for line in open(src):
        d = json.loads(line)
        if d["n"] <= 12:
            continue
        kids = d["children"]
        others = [c for c in kids if not c["t"]]
        pick = [c for c in kids if c["t"]] + rnd.sample(others, min(per, len(others)))
        meta = {"g": d["g"], "style": d["style"], "n": d["n"], "parent": d["parent"], "nsib": len(kids)}
        jobs += [(meta, c, LIMIT) for c in pick]
    print(f"{len(jobs)} labels to compute", flush=True)
    counts = {}
    with Pool(workers) as pool, open(dst, "w") as f:
        for i, row in enumerate(pool.imap_unordered(work, jobs, chunksize=4)):
            counts[row["y"]] = counts.get(row["y"], 0) + 1
            f.write(json.dumps(row) + "\n")
            if (i + 1) % 500 == 0:
                f.flush()
                print(f"{i + 1}/{len(jobs)} {counts}", flush=True)
    print("done", counts)
