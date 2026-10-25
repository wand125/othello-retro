"""到達不能な盤面の修正補助（B）: 1 マスだけ裏返した候補を、UI と同じ探索（学習モデルのビーム → SAT）で当たる。

到達可能な候補なら全マス盤面でも数秒〜数十秒で棋譜が見つかる。到達不能の証明はしない（見つからない＝おそらく不能）。
候補は先に事前チェック（辺・置き順・中央）で絞る（C）。

usage: python3 ml/fix_beam.py 黒hex,白hex [--each 20] [--total 600] [--want 3] [--seed 0]
1 行 1 イベントの JSON を出す。
"""
import json, os, random, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch
from train import Net
from search import BIN, DEV, Undo, prepare
import worker


def opt(name, d):
    return type(d)(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else d


def main():
    board = sys.argv[1]
    each, total, want, seed = opt("--each", 20.0), opt("--total", 600.0), opt("--want", 3), opt("--seed", 0)
    t0 = time.time()
    cands = json.loads(subprocess.run([BIN, "fix", board, "--mode", "candidates"], capture_output=True, text=True).stdout)
    items = [c for c in cands["items"] if c["ok"]]
    random.Random(seed).shuffle(items)
    print(json.dumps({"event": "candidates", "total": cands["total"], "ok": len(items), "time": round(time.time() - t0, 3)}), flush=True)
    here = os.path.dirname(os.path.abspath(__file__))
    net = Net(False).to(DEV); net.load_state_dict(torch.load(os.path.join(here, "model.pt"), map_location=DEV)); net = prepare(net.eval())
    p2 = os.path.join(here, "model_passes.pt")
    net_p = None
    if os.path.exists(p2):
        net_p = Net(False).to(DEV); net_p.load_state_dict(torch.load(p2, map_location=DEV)); net_p = prepare(net_p.eval())
    undo = Undo()
    print(json.dumps({"event": "loaded", "time": round(time.time() - t0, 3)}), flush=True)
    found = 0
    for c in items:
        if time.time() - t0 > total or found >= want:
            break
        b, w = (int(x, 16) for x in c["board"].split(","))
        bd = "".join("X" if b >> i & 1 else "O" if w >> i & 1 else "-" for i in range(64))
        t = time.time()
        r = worker.handle(net, undo, {"board": bd, "time": each}, net_p)
        ok = r["status"] == "found"
        found += ok
        print(json.dumps({"event": "try", "sq": c["sq"], "found": ok, "stage": r.get("stage"), "secs": round(time.time() - t, 2),
                          "time": round(time.time() - t0, 2)}), flush=True)
    print(json.dumps({"event": "done", "found": found, "time": round(time.time() - t0, 2)}), flush=True)


if __name__ == "__main__":
    main()
