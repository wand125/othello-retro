"""到達不能な盤面について、到達不能の原因になっているマス（色の条件）の集合を絞り込む。

最終盤面の各マスの「色」の条件を外しても（石があることは残す）到達不能のままなら、そのマスは原因ではない。
大きなまとまりから外していき（半分 → 4 分の 1 → … → 1 マス）、必要なマスだけを残す。
残った集合は常に「到達不能が証明済み」（外すのは UNSAT を確認できたときだけ）。時間切れは安全側（残す）に倒す。

usage: python3 ml/unsat_core.py 黒hex,白hex [--time 900] [--log core.jsonl]
"""
import json, os, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "target", "release", "othello-retro")


def check(board, constrained, limit):
    """constrained のマスだけ色を固定したとき: True = 到達不能, False = 到達可能, None = 時間切れ"""
    free = 0
    for s in range(64):
        if s not in constrained:
            free |= 1 << s
    with tempfile.NamedTemporaryFile(suffix=".cnf") as f:
        subprocess.run([BIN, "cnf", board, "--enc", f"free={free:016x}"], stdout=f, check=True)
        f.flush()
        out = subprocess.run(["kissat", "-q", f"--time={limit}", f.name], capture_output=True, text=True).stdout
    if "s UNSATISFIABLE" in out:
        return True
    if "s SATISFIABLE" in out:
        return False
    return None


def main():
    board = sys.argv[1]
    limit = int(sys.argv[sys.argv.index("--time") + 1]) if "--time" in sys.argv else 900
    log = open(sys.argv[sys.argv.index("--log") + 1], "a") if "--log" in sys.argv else None
    core = list(range(64))
    size = 32
    t0 = time.time()
    while size >= 1:
        i = 0
        while i < len(core):
            chunk = core[i:i + size]
            rest = [s for s in core if s not in chunk]
            t = time.time()
            r = check(board, set(rest), limit)
            rec = {"size": size, "drop": chunk, "result": {True: "unsat", False: "sat", None: "timeout"}[r],
                   "secs": round(time.time() - t, 1), "core": len(rest) if r else len(core)}
            print(json.dumps(rec), flush=True)
            if log:
                log.write(json.dumps(rec) + "\n"); log.flush()
            if r:  # 外しても到達不能 → このまとまりは原因ではない
                core = rest
            else:
                i += size
        size //= 2
    names = ["abcdefgh"[s % 8] + str(s // 8 + 1) for s in core]
    b, w = (int(x, 16) for x in board.split(","))
    colors = {n: ("黒" if b >> s & 1 else "白") for n, s in zip(names, core)}
    print(json.dumps({"core": names, "colors": colors, "total_secs": round(time.time() - t0)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
