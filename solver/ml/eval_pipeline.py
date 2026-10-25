"""UI と同じ探索の流れ（ワーカー → 見つからなければ SAT）を盤面の一覧で評価する。

usage: python3 ml/eval_pipeline.py boards.txt [--time 120]
"""
import json, os, statistics, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch
from train import Net
from search import BIN, DEV, Undo, prepare
import worker

net = Net(False).to(DEV)
model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.pt")
net.load_state_dict(torch.load(model, map_location=DEV))
net = prepare(net.eval())
p2 = sys.argv[sys.argv.index("--model-passes") + 1] if "--model-passes" in sys.argv else None
net_passes = None
if p2:
    net_passes = Net(False).to(DEV); net_passes.load_state_dict(torch.load(p2, map_location=DEV)); net_passes = prepare(net_passes.eval())
undo = Undo()
limit = int(sys.argv[sys.argv.index("--time") + 1]) if "--time" in sys.argv else 120
rows = []
for line in open(sys.argv[1]):
    h = line.split()[0]
    b, w = (int(x, 16) for x in h.split(","))
    board = "".join("X" if b >> i & 1 else "O" if w >> i & 1 else "-" for i in range(64))
    t0 = time.time()
    r = worker.handle(net, undo, {"board": board, "time": limit * 0.6}, net_passes)
    stage = r.get("stage")
    if r["status"] != "found":
        d = json.loads(subprocess.run([BIN, "solve", h, "--json", "--time", str(int(limit - (time.time() - t0)))],
                                      capture_output=True, text=True).stdout.strip().splitlines()[-1])
        stage = "sat" if d["status"] == "found" else d["status"]
    rows.append({"board": h, "stage": stage, "s": round(time.time() - t0, 2)})
    print(json.dumps(rows[-1]), flush=True)
ok = [r for r in rows if r["stage"] in ("direct", "fast", "careful", "with-passes", "sat")]
print(f"--- solved {len(ok)}/{len(rows)}  median {statistics.median(r['s'] for r in ok):.2f}s  max {max(r['s'] for r in ok):.2f}s")
print("    by stage:", {k: sum(r["stage"] == k for r in rows) for k in sorted({r["stage"] for r in rows})})
