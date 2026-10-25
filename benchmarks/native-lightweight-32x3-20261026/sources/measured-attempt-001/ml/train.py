"""到達可能性の評価器を学習し、局所（盤面 CNN）と大域（数値特徴）の寄与を比べる。

入力: label_spine.py の出力（y = 1 到達可能 / 0 到達不能 / -1 不明。不明は除外）
モデル:
  (a) scalars : 大域の数値特徴だけ（勾配ブースティング）
  (b) cnn     : 盤面のみ（戻した後の盤面＋戻した差分）
  (c) cnn+sc  : 両方
評価はゲーム単位で分割したテストデータで、AUC と「兄弟候補の中で最高評価のものが到達可能な割合」。

usage: python3 ml/train.py labels.jsonl [--epochs 30] [--save model.pt]
"""
import json, sys, random, math
import numpy as np
import torch, torch.nn as nn


def bits(h):
    x = int(h, 16)
    return np.array([(x >> i) & 1 for i in range(64)], dtype=np.float32).reshape(8, 8)


def load(path, unknown_as_pos=False):
    rows = [json.loads(l) for l in open(path)]
    if unknown_as_pos:
        for r in rows:
            if r["y"] == -1:
                r["y"] = 1
    return [r for r in rows if r["y"] in (0, 1)]


def planes(r):
    qb, qw = r["q"].split(",")
    pb, pw = r["parent"].split(",")
    QB, QW, PB, PW = bits(qb), bits(qw), bits(pb), bits(pw)
    # 戻した手を打った側を「自分」とする（記録があればそれ、無ければパスなし仮定で親の手数 n の n-1 の偶奇）
    mover_black = r["c"] == 0 if "c" in r else (r["n"] - 1) % 2 == 0
    own, opp = (QB, QW) if mover_black else (QW, QB)
    removed = (PB + PW) - (QB + QW)
    flipped = np.abs(PB - QB) - removed * 0  # 色が変わったマス（戻したマスは除く）
    flipped = np.clip(flipped - removed, 0, 1)
    empty = 1 - QB - QW
    return np.stack([own, opp, empty, removed, flipped])


def scalars(r):
    return np.array([r["n"] / 60, math.log1p(r["kids"]), r["mb"] / 20, r["mw"] / 20, r["fr"] / 40,
                     r["nf"] / 10, math.log1p(r["nsib"])], dtype=np.float32)


# 初期配置を保つ対称変換（恒等、主対角、反対角、180 度回転）
SYMS = [lambda a: a, lambda a: np.swapaxes(a, -1, -2), lambda a: np.rot90(np.swapaxes(a, -1, -2), 2, axes=(-2, -1)),
        lambda a: np.rot90(a, 2, axes=(-2, -1))]


class Net(nn.Module):
    def __init__(self, use_scalars, ch=64, blocks=4):
        super().__init__()
        self.use_scalars = use_scalars
        self.stem = nn.Sequential(nn.Conv2d(5, ch, 3, padding=1), nn.BatchNorm2d(ch), nn.ReLU())
        self.blocks = nn.ModuleList([nn.Sequential(
            nn.Conv2d(ch, ch, 3, padding=1), nn.BatchNorm2d(ch), nn.ReLU(),
            nn.Conv2d(ch, ch, 3, padding=1), nn.BatchNorm2d(ch)) for _ in range(blocks)])
        self.head = nn.Sequential(nn.Linear(2 * ch + (7 if use_scalars else 0), 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, x, s):
        h = self.stem(x)
        for b in self.blocks:
            h = torch.relu(h + b(h))
        z = torch.cat([h.mean((2, 3)), h.amax((2, 3))] + ([s] if self.use_scalars else []), 1)
        return self.head(z).squeeze(1)


def top1_reachable(rows, score):
    """各段の兄弟候補（ラベル付きのもの）のうち、最高評価が到達可能だった割合と、ランダムに選んだ場合の期待値"""
    groups = {}
    for r, s in zip(rows, score):
        groups.setdefault((r["g"], r["n"]), []).append((s, r["y"]))
    hit, base = [], []
    for v in groups.values():
        if len(v) < 2 or len({y for _, y in v}) < 2:
            continue
        hit.append(max(v)[1])
        base.append(np.mean([y for _, y in v]))
    return np.mean(hit), np.mean(base), len(hit)


def main():
    # Inference workers only import Net/planes; training dependencies need not load there.
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    path = sys.argv[1]
    epochs = int(sys.argv[sys.argv.index("--epochs") + 1]) if "--epochs" in sys.argv else 30
    rows = load(path, "--unknown-pos" in sys.argv)
    games = sorted({r["g"] for r in rows})
    random.Random(0).shuffle(games)
    test_g = set(games[: max(2, len(games) // 4)])
    tr = [r for r in rows if r["g"] not in test_g]
    te = [r for r in rows if r["g"] in test_g]
    print(f"rows={len(rows)} train={len(tr)} test={len(te)} pos_rate={np.mean([r['y'] for r in rows]):.3f}")

    ytr = np.array([r["y"] for r in tr])
    yte = np.array([r["y"] for r in te])
    Str = np.stack([scalars(r) for r in tr])
    Ste = np.stack([scalars(r) for r in te])

    results = {}
    gb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05).fit(Str, ytr)
    p = gb.predict_proba(Ste)[:, 1]
    results["(a) scalars"] = p
    # 参考: 単一特徴（戻せる手の数）
    results["kids only"] = Ste[:, 1]

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    Xtr = np.stack([planes(r) for r in tr])
    Xte = np.stack([planes(r) for r in te])
    for name, use_s in (("(b) cnn", False), ("(c) cnn+scalars", True)):
        torch.manual_seed(0)
        net = Net(use_s).to(dev)
        opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
        lossf = nn.BCEWithLogitsLoss()
        Xa = np.concatenate([np.ascontiguousarray(f(Xtr)) for f in SYMS])
        Sa = np.concatenate([Str] * len(SYMS))
        ya = np.concatenate([ytr] * len(SYMS)).astype(np.float32)
        X_t, S_t, y_t = torch.tensor(Xa), torch.tensor(Sa), torch.tensor(ya)
        n = len(ya)
        for ep in range(epochs):
            net.train()
            perm = torch.randperm(n)
            for i in range(0, n, 256):
                idx = perm[i:i + 256]
                opt.zero_grad()
                loss = lossf(net(X_t[idx].to(dev), S_t[idx].to(dev)), y_t[idx].to(dev))
                loss.backward()
                opt.step()
        net.eval()
        with torch.no_grad():
            # テスト時も対称変換の平均
            ps = [torch.sigmoid(net(torch.tensor(np.ascontiguousarray(f(Xte))).to(dev), torch.tensor(Ste).to(dev))).cpu().numpy()
                  for f in SYMS]
        results[name] = np.mean(ps, 0)
        if "--save" in sys.argv and use_s:
            torch.save(net.state_dict(), sys.argv[sys.argv.index("--save") + 1])

    print(f"{'model':18} {'AUC':>6} {'top1-reachable':>15} {'random':>7} {'groups':>6}")
    for name, p in results.items():
        auc = roc_auc_score(yte, p)
        h, b, k = top1_reachable(te, p)
        print(f"{name:18} {auc:6.3f} {h:15.3f} {b:7.3f} {k:6d}")
    # 段ごとの内訳（cnn+scalars）
    p = results["(c) cnn+scalars"]
    print("\nAUC by move count (cnn+scalars):")
    for lo, hi in ((50, 61), (40, 50), (30, 40), (13, 30)):
        m = np.array([lo <= r["n"] < hi for r in te])
        if m.sum() and len(set(yte[m])) == 2:
            print(f"  n={lo}-{hi - 1}: AUC={roc_auc_score(yte[m], p[m]):.3f} pos_rate={yte[m].mean():.3f} count={m.sum()}")


if __name__ == "__main__":
    main()
