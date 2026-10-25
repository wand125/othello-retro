"""修正補助（到達不能な盤面を到達可能に直す）の高速化ベンチマーク。1 盤面ずつ、方法を 1 つずつ順に実行する。

直し方を 1 つ見つけるまで:
  従来   : 1 マス裏返した候補を、一般版エンコードの kissat で判定（jobs 並列、到達可能が出たら終了）
  A      : 「色を変えるのは 1 個以下」を CNF に入れ、kissat 3 本並列（パスなし・終盤パス許可・一般版）で 1 回解く
  A'     : 事前チェックを通った候補を、kissat 3 本並列で判定（jobs 並列）
  B      : 候補を学習モデル＋SAT（UI と同じ探索）で当たる
  C      : 事前チェック（辺・置き順）で落ちる候補の数
全マスの地図（各マスを裏返せば到達可能か）:
  従来   : 1 マスずつ一般版エンコードの kissat（jobs 並列）
  D'     : CaDiCaL のインクリメンタル求解（1 回 5 秒まで）で「直らない」マスを確定 → 残りを kissat 3 本並列（jobs 並列）
実時間と、子プロセスの CPU 時間（ほかの処理の負荷に左右されにくい）を記録する。

usage: python3 ml/bench_fix.py boards.txt out.md [--fix-budget 600] [--map-budget 2400] [--jobs 3] [--map-boards 3] [--bin path]
boards.txt は 1 行 1 盤面 "黒hex,白hex"（到達不能と分かっているもの）。
"""
import json, os, random, resource, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def opt(name, d):
    return type(d)(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else d


BIN = opt("--bin", os.path.join(os.path.dirname(HERE), "target", "release", "othello-retro"))
import unsat_core
unsat_core.BIN = BIN


def child_cpu():
    r = resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime + r.ru_stime


def measured(fn):
    t, c = time.time(), child_cpu()
    out = fn()
    return out, time.time() - t, child_cpu() - c


def events(cmd, timeout):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    res = []
    for l in out.splitlines():
        try:
            res.append(json.loads(l))
        except json.JSONDecodeError:
            pass
    return res


def baseline_fix(board, cands, budget, jobs):
    """従来: 候補を一般版 kissat で判定（並列）。到達可能が 1 つ出たら終了"""
    order = cands[:]
    random.Random(0).shuffle(order)
    t0, tried = time.time(), 0
    with ThreadPoolExecutor(jobs) as ex:
        pending = set()
        it = iter(order)
        def submit():
            nonlocal tried
            c = next(it, None)
            if c is None:
                return False
            left = int(budget - (time.time() - t0))
            if left < 5:
                return False
            tried += 1
            pending.add(ex.submit(unsat_core.check, c["board"], set(range(64)), left))
            return True
        for _ in range(jobs):
            submit()
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for f in done:
                pending.discard(f)
                if f.result() is False:  # 色の条件をすべて課して到達可能 = この候補で直る
                    # Release safety: let this executor join its own bounded tasks; never kill unrelated solver processes.
                    return time.time() - t0, tried
                submit()
    return None, tried


def fmt(t, wall, cpu, extra=""):
    return (f"{t:.0f} 秒" if t is not None else "見つからず") + f"（実 {wall:.0f} 秒・CPU {cpu:.0f} 秒{extra}）"


def main():
    src, out = sys.argv[1], sys.argv[2]
    fixb, mapb, jobs, nmap = opt("--fix-budget", 600.0), opt("--map-budget", 2400.0), opt("--jobs", 3), opt("--map-boards", 3)
    boards = [l.split()[0] for l in open(src) if l.strip()]
    rows = []
    for i, h in enumerate(boards):
        r = {"board": h}
        c = json.loads(subprocess.run([BIN, "fix", h, "--mode", "candidates"], capture_output=True, text=True).stdout)
        cands = [x for x in c["items"] if x["ok"]]
        r["C"] = f"{c['total']} → {len(cands)}（{c['time'] * 1000:.0f} ms）"
        (t, tried), wall, cpu = measured(lambda: baseline_fix(h, cands, fixb, jobs))
        r["base_fix"] = fmt(t, wall, cpu, f"・{tried} 候補")
        ev, wall, cpu = measured(lambda: events([BIN, "fix", h, "--mode", "nearest", "--k", "1", "--solutions", "1", "--opt-time", str(fixb)], fixb + 60))
        fx = [e for e in ev if e.get("event") == "fix"]
        r["A"] = fmt(fx[0]["time"] if fx else None, wall, cpu, f"・{'・'.join(fx[0]['changed'])}" if fx else "")
        ev, wall, cpu = measured(lambda: events([BIN, "fix", h, "--mode", "nearest-cand", "--jobs", str(jobs), "--solutions", "1",
                                                 "--each-kissat", str(fixb), "--opt-time", str(fixb)], fixb + 60))
        hit = next((e for e in ev if e.get("event") == "try" and e["result"] == "fix"), None)
        r["A2"] = fmt(hit["time"] if hit else None, wall, cpu, f"・{hit['sq']}" if hit else "")
        ev, wall, cpu = measured(lambda: events([sys.executable, os.path.join(HERE, "fix_beam.py"), h, "--each", "20", "--total", "300", "--want", "1"], 420))
        hit = next((e for e in ev if e.get("event") == "try" and e["found"]), None)
        r["B"] = fmt(hit["time"] if hit else None, wall, cpu)
        if i < nmap:
            def base_map():
                with ThreadPoolExecutor(jobs) as ex:
                    return list(ex.map(lambda s: unsat_core.check(h, set(range(64)) - {s}, 600), range(64)))
            res, wall, cpu = measured(base_map)
            r["base_map"] = f"実 {wall:.0f} 秒・CPU {cpu:.0f} 秒（R {sum(x is False for x in res)}・? {sum(x is None for x in res)}）"
            ev, wall, cpu = measured(lambda: events([BIN, "fix", h, "--mode", "map", "--each", "5", "--each-kissat", "600", "--jobs", str(jobs),
                                                     "--opt-time", str(mapb)], mapb + 120))
            done = next((e for e in ev if e.get("event") == "done"), None)
            g = "".join(done["grid"]) if done else ""
            quick = sum(1 for e in ev if e.get("event") == "cell" and e.get("why") != "kissat")
            r["D"] = f"実 {wall:.0f} 秒・CPU {cpu:.0f} 秒（R {g.count('R')}・? {g.count('?')}・CaDiCaL で確定 {quick}）" if done else "未完了"
        else:
            r["base_map"] = r["D"] = "-"
        rows.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        with open(out, "w") as f:
            f.write(f"# 修正補助ベンチマーク\n\n直し方の探索は上限 {fixb:.0f} 秒、地図は上限 {mapb:.0f} 秒、並列数 {jobs}。"
                    "「CPU」は子プロセスが使った CPU 時間の合計（ほかの処理の負荷に左右されにくい）。\n\n")
            f.write("| 盤面 | C: 候補 | 従来: 直し方 | A: k≤1 を 1 回の SAT | A': 候補を並列 | B: 学習モデル | 従来: 地図 | D': CaDiCaL＋kissat |\n|---|---|---|---|---|---|---|---|\n")
            for x in rows:
                f.write(f"| `{x['board'][:8]}…` | {x['C']} | {x['base_fix']} | {x['A']} | {x['A2']} | {x['B']} | {x['base_map']} | {x['D']} |\n")


if __name__ == "__main__":
    main()
