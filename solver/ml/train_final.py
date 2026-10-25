"""探索用の最終モデル（盤面のみの CNN）を全データで学習して保存する。

usage: python3 ml/train_final.py labels.jsonl [labels2.jsonl ...] --out model.pt [--epochs 25]
不明ラベル（SAT が短時間で決着しなかった局面）は到達可能として扱う。
"""
import sys
import numpy as np
import torch, torch.nn as nn
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from train import Net, planes, scalars, SYMS, load

paths = [a for a in sys.argv[1:] if a.endswith(".jsonl")]
out = sys.argv[sys.argv.index("--out") + 1]
epochs = int(sys.argv[sys.argv.index("--epochs") + 1]) if "--epochs" in sys.argv else 25
rows = [r for p in paths for r in load(p, unknown_as_pos=True)]
print(f"rows={len(rows)} pos_rate={np.mean([r['y'] for r in rows]):.3f}")
X = np.stack([planes(r) for r in rows])
y = np.array([r["y"] for r in rows], dtype=np.float32)
Xa = np.concatenate([np.ascontiguousarray(f(X)) for f in SYMS])
ya = np.concatenate([y] * len(SYMS))
dev = "mps" if torch.backends.mps.is_available() else "cpu"
torch.manual_seed(0)
net = Net(False).to(dev)
opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
lossf = nn.BCEWithLogitsLoss()
X_t, y_t, S0 = torch.tensor(Xa), torch.tensor(ya), torch.zeros(1)
for ep in range(epochs):
    net.train()
    perm = torch.randperm(len(ya))
    tot = 0.0
    for i in range(0, len(ya), 256):
        idx = perm[i:i + 256]
        opt.zero_grad()
        loss = lossf(net(X_t[idx].to(dev), None), y_t[idx].to(dev))
        loss.backward()
        opt.step()
        tot += loss.item() * len(idx)
    sched.step()
    if ep % 5 == 4 or ep == epochs - 1:
        print(f"epoch {ep + 1}: loss={tot / len(ya):.4f}", flush=True)
torch.save(net.state_dict(), out)
print("saved", out)
