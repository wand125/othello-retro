"""評価器（CNN）で導く後ろ向きビームサーチ ＋ SAT（パスなし仮定）。

最終盤面から 1 手ずつ戻し、各段で「到達可能らしさ」の高い上位 width 局面を残す。
手数が n_stop まで下がったら上位 k 個を SAT に並列で渡し、解けたものに戻した手順をつなげる。
完全性は無い（見つからなくても到達不能とは言えない）。

usage: python3 ml/search.py model.pt boards.txt [--width 32] [--cap 4] [--stop 30] [--k 6] [--sat-time 20] [--compare]
boards.txt は 1 行 1 盤面 "黒hex,白hex"。--compare で SAT 単独（solve）とも比べる。
"""
import json, os, subprocess, sys, time
import numpy as np
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train import Net, planes, SYMS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "target", "release", "othello-retro")
DEV = os.environ.get("OTHELLO_DEVICE") or ("mps" if torch.backends.mps.is_available() else "cpu")
if DEV not in {"cpu", "mps"}:
    raise ValueError("OTHELLO_DEVICE must be cpu or mps")
if DEV == "mps" and not torch.backends.mps.is_available():
    raise RuntimeError("MPS was requested but is not available")


def opt(name, default):
    return type(default)(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


class Undo:
    """Rust の undo-server（パスなしの 1 手戻し）"""

    def __init__(self):
        self.p = subprocess.Popen([BIN, "undo-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def many(self, positions):
        self.p.stdin.write("".join(p + "\n" for p in positions))
        self.p.stdin.flush()
        return [self.p.stdout.readline().split() for _ in positions]


def popcount(h):
    b, w = h.split(",")
    return bin(int(b, 16) | int(w, 16)).count("1")


def placed_square(parent, child):
    pb, pw = (int(x, 16) for x in parent.split(","))
    qb, qw = (int(x, 16) for x in child.split(","))
    d = (pb | pw) & ~(qb | qw)
    s = d.bit_length() - 1
    return "abcdefgh"[s % 8] + str(s // 8 + 1)


def unpack(hexes):
    """"黒hex,白hex" の列 → (N, 64) の黒・白 0/1 配列（bit i = マス i）"""
    v = np.array([[int(x, 16) for x in h.split(",")] for h in hexes], dtype=np.uint64)
    bytes_ = v.view(np.uint8).reshape(len(hexes), 2, 8)  # リトルエンディアン
    bits_ = np.unpackbits(bytes_, axis=2, bitorder="little").astype(np.float32)
    return bits_[:, 0], bits_[:, 1]


def planes_batch(items):
    """train.planes と同じ 5 面をまとめて作る。items の 4 番目（あれば）は戻した手を打った側（0 黒 / 1 白）。
    無ければパスなし仮定で手数の偶奇から決める"""
    QB, QW = unpack([it[0] for it in items])
    PB, PW = unpack([it[1] for it in items])
    mover_black = np.array([(it[3] == 0) if len(it) > 3 else (it[2] - 1) % 2 == 0 for it in items])[:, None]
    own = np.where(mover_black, QB, QW)
    opp = np.where(mover_black, QW, QB)
    removed = (PB + PW) - (QB + QW)
    flipped = np.clip(np.abs(PB - QB) - removed, 0, 1)
    empty = 1 - QB - QW
    return np.stack([own, opp, empty, removed, flipped], 1).reshape(len(items), 5, 8, 8)


# 評価の設定（環境変数で変えられる）: 平均を取る対称変換の数（1〜4）と半精度
NSYM = int(os.environ.get("RETRO_NSYM", "1"))
REFINE = int(os.environ.get("RETRO_REFINE", "4"))  # 上位 width×REFINE 個だけ 4 対称の平均で評価し直す（0 で無効）
HALF = os.environ.get("RETRO_HALF", "1") == "1" and DEV == "mps"
# 初期配置を保つ対称変換（train.SYMS と同じ順）を GPU 上で行う
TSYMS = [lambda x: x, lambda x: x.transpose(2, 3), lambda x: x.transpose(2, 3).flip(2, 3), lambda x: x.flip(2, 3)]


def prepare(net):
    """推論用の設定（半精度など）を適用したモデルを返す"""
    if HALF:
        return net.half()
    variant = os.environ.get("RETRO_INFERENCE_OPT", "baseline")
    if DEV == "cpu" and variant != "baseline":
        from inference_opt import optimize
        return optimize(net, variant)
    return net


class SearchBudgetExpired(TimeoutError):
    pass


def check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise SearchBudgetExpired("model search budget exhausted")


def score(net, items, nsym=None, deadline=None, skip_identity=False):
    """items: [(child, parent, n_parent[, mover])] → 到達可能らしさの logit（nsym 個の対称変換の平均）"""
    nsym = nsym or NSYM
    if not items:
        return np.zeros(0)
    check_deadline(deadline)
    x = torch.from_numpy(planes_batch(items)).to(DEV)
    if HALF:
        x = x.half()
    out = 0
    transforms = TSYMS[1:nsym] if skip_identity else TSYMS[:nsym]
    batch = 8192 if DEV == "mps" else 256
    with torch.inference_mode():
        for f in transforms:
            xs = f(x)
            parts = []
            for i in range(0, len(xs), batch):
                check_deadline(deadline)
                parts.append(net(xs[i:i + batch], None))
            out = out + torch.cat(parts).float()
    return (out / len(transforms)).cpu().numpy()


PASS_ZONE = int(os.environ.get("RETRO_PASS_ZONE", "48"))  # パスを含む手順を考えるのはこの手数以降だけ


def beam(net, undo, target, width, cap, stop, nsym=None, refine=None, passes=False, deadline=None, progress=None):
    """target から stop 手まで戻した候補を評価順に返す。各要素は (局面, 目標までの着手列)。
    passes=True ならパスを含む戻し方も扱う（状態は「局面＋次の手番」）。
    最後は、パスなしの手順で作れる手番（手数の偶奇どおり）の候補だけを返す（SAT はパスなしで解くため）"""
    nsym = nsym or NSYM
    refine = REFINE if refine is None else refine
    beam_ = [(target, 3, [])]  # (局面, 次の手番 0 黒 / 1 白 / 3 不問, 着手列)
    evaluated, target_moves = 0, popcount(target) - 4
    while popcount(beam_[0][0]) - 4 > stop:
        check_deadline(deadline)
        n = popcount(beam_[0][0]) - 4
        step_start = time.monotonic()
        if progress:
            progress({"phase": "generate", "remaining_moves": n, "target_moves": target_moves, "goal_moves": stop,
                      "evaluated": evaluated, "kept": len(beam_)})
        lines = [f"{s} {nx}" for s, nx, _ in beam_] if passes else [s for s, _, _ in beam_]
        kids = undo.many(lines)
        items, owners, seen = [], [], set()
        for (s, _, path), ks in zip(beam_, kids):
            for tok in ks:
                q, _, c = tok.partition(":")
                c = int(c) if c else (n - 1) % 2
                # 手番が手数の偶奇とずれた局面は「それより前にパスが奇数回あった」ことを意味する。
                # パスはほぼ終盤でしか起きないので、PASS_ZONE より前ではこうした局面を捨てる
                if c != (n - 1) % 2 and n - 1 < PASS_ZONE:
                    continue
                if (q, c) in seen:
                    continue
                seen.add((q, c))
                items.append((q, s, n, c))
                owners.append(path)
        if not items:
            return []
        if progress:
            progress({"phase": "evaluate", "remaining_moves": n - 1, "target_moves": target_moves,
                      "goal_moves": stop, "candidates": len(items), "evaluated": evaluated, "kept": len(beam_)})
        sc = score(net, items, nsym, deadline=deadline)
        order = np.argsort(-sc)
        if refine and nsym < 4:
            # 二段階評価: 安い評価で絞った上位だけ、4 つの対称変換の平均で並べ直す
            top = order[: width * refine]
            # Identity was already evaluated in the fast pass; evaluate only the other 3 transforms.
            fine = (sc[top] + 3 * score(net, [items[i] for i in top], 4, deadline=deadline, skip_identity=True)) / 4 if nsym == 1 else score(net, [items[i] for i in top], 4, deadline=deadline)
            order = top[np.argsort(-fine)]
        nxt, per = [], {}
        for i in order:
            q, parent, _, c = items[i]
            if per.get(parent, 0) >= cap:  # 同じ親から取りすぎない（多様性）
                continue
            per[parent] = per.get(parent, 0) + 1
            nxt.append((q, c, [placed_square(parent, q)] + owners[i]))
            if len(nxt) >= width:
                break
        beam_ = nxt
        evaluated += len(items)
        if progress:
            progress({"phase": "selected", "remaining_moves": n - 1, "target_moves": target_moves, "goal_moves": stop,
                      "candidates": len(items), "evaluated": evaluated, "kept": len(nxt),
                      "step_seconds": round(time.monotonic() - step_start, 3)})
    return [(q, path) for q, c, path in beam_ if c == (popcount(q) - 4) % 2]


def findany(cands, sat_time):
    out = subprocess.run([BIN, "findany", *cands, "--time", str(sat_time)], capture_output=True, text=True).stdout
    return json.loads(out.strip().splitlines()[-1])


def verify(moves, target):
    """パスを補いながら初期局面から再生し、目標と一致するか（Rust の solve --json の形式と同じ着手名）"""
    b, w = (1 << 28) | (1 << 35), (1 << 27) | (1 << 36)
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]

    def flips(p, o, s):
        r0, c0, f = s // 8, s % 8, 0
        for dr, dc in dirs:
            r, c, line = r0 + dr, c0 + dc, 0
            while 0 <= r < 8 and 0 <= c < 8 and o >> (r * 8 + c) & 1:
                line |= 1 << (r * 8 + c)
                r, c = r + dr, c + dc
            if line and 0 <= r < 8 and 0 <= c < 8 and p >> (r * 8 + c) & 1:
                f |= line
        return f

    side = 0
    for m in moves:
        s = (int(m[1]) - 1) * 8 + "abcdefgh".index(m[0])
        p, o = (b, w) if side == 0 else (w, b)
        f = flips(p, o, s)
        if not f:  # この側に合法手が無い → パス
            side = 1 - side
            p, o = (b, w) if side == 0 else (w, b)
            f = flips(p, o, s)
            if not f:
                return False
        p, o = p | f | (1 << s), o & ~f
        b, w = (p, o) if side == 0 else (o, p)
        side = 1 - side
    tb, tw = (int(x, 16) for x in target.split(","))
    return (b, w) == (tb, tw)


def main():
    model, boards = sys.argv[1], sys.argv[2]
    width, cap, stop, k, sat_time = opt("--width", 32), opt("--cap", 4), opt("--stop", 30), opt("--k", 6), opt("--sat-time", 20)
    net = Net(False).to(DEV)
    net.load_state_dict(torch.load(model, map_location=DEV))
    net = prepare(net.eval())
    undo = Undo()
    rows = []
    for line in open(boards):
        target = line.split()[0]
        t0 = time.time()
        cands = beam(net, undo, target, width, cap, stop, nsym=opt("--nsym", NSYM), passes="--passes" in sys.argv)
        t_beam = time.time() - t0
        found, tried = None, 0
        for i in range(0, min(len(cands), 3 * k), k):  # 上位から k 個ずつ SAT に渡す
            chunk = cands[i:i + k]
            tried += len(chunk)
            r = findany([c for c, _ in chunk], sat_time)
            if r["index"] is not None:
                found = r["moves"] + chunk[r["index"]][1]
                break
        t = time.time() - t0
        ok = found is not None and verify(found, target)
        res = {"board": target, "beam_s": round(t_beam, 2), "total_s": round(t, 2), "found": found is not None, "verified": ok, "sat_tried": tried}
        if "--compare" in sys.argv:
            t1 = time.time()
            d = json.loads(subprocess.run([BIN, "solve", target, "--json", "--time", "300"], capture_output=True, text=True).stdout.strip().splitlines()[-1])
            res["direct_status"], res["direct_s"] = d["status"], round(time.time() - t1, 2)
        rows.append(res)
        print(json.dumps(res, ensure_ascii=False), flush=True)
    f = [r for r in rows if r["verified"]]
    print(f"--- found {len(f)}/{len(rows)}; median total (found) = {np.median([r['total_s'] for r in f]) if f else float('nan'):.2f}s")
    if "--compare" in sys.argv:
        print(f"    direct SAT median = {np.median([r['direct_s'] for r in rows]):.2f}s")


if __name__ == "__main__":
    main()
