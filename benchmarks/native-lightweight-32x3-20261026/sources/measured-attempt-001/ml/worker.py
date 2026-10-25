"""UI サーバー用の常駐ワーカー: 評価器付きビームサーチ ＋ SAT（パスなし仮定）。

モデルの読み込み（torch の import を含む）に数秒かかるので、起動したまま 1 行 1 リクエストで処理する。
入力:  {"board": "X/O/- の 64 文字", "time": 秒}
出力:  {"status": "found", "moves": [...]} または {"status": "miss", "reason": "..."}
起動完了時に {"status": "ready"} を 1 行出す。
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch
from train import Net
from search import DEV, Undo, beam, findany, prepare, verify, SearchBudgetExpired


def to_hex(board):
    b = sum(1 << i for i, v in enumerate(board) if v == "X")
    w = sum(1 << i for i, v in enumerate(board) if v == "O")
    return f"{b:016x},{w:016x}"


# 段階ごとの設定: 速い評価 → 丁寧な評価。パスが必要な盤面はパス対応の広いビームだけ
FAST = dict(width=32, nsym=1, refine=4, passes=False)
CAREFUL = dict(width=32, nsym=4, refine=0, passes=False)
WITH_PASSES = dict(width=64, nsym=4, refine=0, passes=True)


def handle(net, undo, req, net_passes=None, progress=None):
    """net_passes: パス対応ビームに使うモデル（無ければ net）"""
    if os.environ.get("RETRO_AUTO_POLICY", "baseline") == "lightweight":
        from lightweight import handle as lightweight_handle
        return lightweight_handle(net, undo, req, net_passes, progress)
    t0, limit = time.monotonic(), float(req.get("time", 60))
    target = to_hex(req["board"])
    left = lambda: limit - (time.monotonic() - t0)
    emit = lambda stage, message, **kw: progress({"stage": stage, "message": message, "device": DEV, **kw}) if progress else None
    # パスなしで作れない盤面は SAT が 1 秒前後で分かる。それならパスなしのビームは無駄なので飛ばす
    emit("pass_check", "パスなしの手順で作れるか確認しています")
    r = findany([target], min(2, max(1, int(left()))))
    if r["index"] is not None:
        return {"status": "found", "moves": r["moves"], "stage": "direct"}
    stages = [("with-passes", WITH_PASSES)] if r.get("unsat") else [("fast", FAST), ("careful", CAREFUL)]
    for name, cfg in stages:
        if left() < 5:
            break
        model = net_passes if (cfg["passes"] and net_passes is not None) else net
        message = {"fast": "学習モデルで手順の候補を絞っています", "careful": "対称な盤面も評価して候補を選び直しています",
                   "with-passes": "パスを含む手順の候補を絞っています"}[name]
        emit("beam_" + name, message)
        try:
            cands = beam(model, undo, target, cfg["width"], cap=4 if cfg["width"] <= 32 else 8, stop=30,
                         nsym=cfg["nsym"], refine=cfg["refine"], passes=cfg["passes"], deadline=t0 + limit - 2,
                         progress=lambda data: emit("beam_" + name, message, **data))
        except SearchBudgetExpired:
            emit("model_budget", "モデル探索の持ち時間に達したため、別の方式に切り替えます")
            break
        for i in range(0, min(len(cands), 18), 6):
            if left() < 2:
                break
            chunk = cands[i:i + 6]
            emit("candidate_sat", "絞った候補から初期配置につながる手順を調べています", tested=i, total_candidates=min(len(cands), 18))
            r = findany([c for c, _ in chunk], int(min(20, left())))
            if r["index"] is not None:
                moves = r["moves"] + chunk[r["index"]][1]
                if verify(moves, target):
                    return {"status": "found", "moves": moves, "stage": name}
    return {"status": "miss", "reason": "学習モデルでは見つからなかった"}


def load(path):
    net = Net(False).to(DEV)
    net.load_state_dict(torch.load(path, map_location=DEV))
    return prepare(net.eval())


def main():
    # model.pt: パスなし・パスありの局面で学習したモデル（速い・丁寧な段階）
    # model_passes.pt があればパス対応ビームに使う（実測ではパスが必要な盤面でこちらが良かった）
    net = load(sys.argv[1])
    p2 = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "model_passes.pt")
    net_passes = load(p2) if os.path.exists(p2) else None
    undo = Undo()
    print(json.dumps({"status": "ready"}), flush=True)
    for line in sys.stdin:
        try:
            req = json.loads(line)
            callback = (lambda data: print(json.dumps({"event": "progress", **data}), flush=True)) if req.get("progress") else None
            out = handle(net, undo, req, net_passes, progress=callback)
        except Exception as e:  # 1 件の失敗でワーカーを落とさない
            out = {"status": "miss", "reason": f"エラー: {e}"}
        print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
