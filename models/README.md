# Othello Retro モデル重み

[日本語](README.md) | [English](README.en.md)

二つの重みはGitHub Releaseのassetsとして配布します。重みをGitの履歴へ含める必要はありません。[モデルカード](MODEL_CARD.ja.md)の来歴・教師・評価の限界を確認してください。推論時に元の訓練JSONLは不要です。

## 入手と整合性確認

1. [プロジェクトのReleases](https://github.com/wand125/othello-retro/releases)から、このモデルと対応するソース版、`model.pt`、`model_passes.pt`、`SHA256SUMS`を取得します。モデル用アーカイブがある場合は展開します。
2. 二つの重みと`SHA256SUMS`を同じディレクトリへ置き、そこで検証します。`SHA256SUMS`の対象はこの二つの重みだけです。

```sh
# Linux
sha256sum -c SHA256SUMS
# macOS
shasum -a 256 -c SHA256SUMS
```

3. ソースリポジトリから使う場合、二つの重みを `solver/ml/model.pt`、`solver/ml/model_passes.pt` に置きます。両者を同じディレクトリに置いてください。主モデルは混合データ、`model_passes.pt` は旧パスなしモデルです。名前を取り違えないでください。
4. 以下の例は、実装ROOTであるソース側の `solver/` へ移動して実行します。モデルtarを展開したフォルダから直接実行する場合も、対応するソースの `solver/` へ移動してください。

```sh
# ソースリポジトリのルートから
cd solver
```

## CPUでの読込例

Python3.12、Torch2.2.2、NumPy1.26.4で読込確認しています。PyTorchとNumPyは利用するプラットフォーム向けに別途インストールしてください。以下は対応するソースの実装ROOT（リポジトリ内の `solver/`）で実行します。`Net` のimport・読込には学習用のscikit-learnは不要です。

```python
from pathlib import Path
import sys
import torch

sys.path.insert(0, "ml")
from train import Net

torch.set_num_threads(2)
model_dir = Path("ml")
for filename in ("model.pt", "model_passes.pt"):
    state = torch.load(
        str(model_dir / filename),
        map_location="cpu",
        weights_only=True,
    )
    net = Net(False).to(device="cpu", dtype=torch.float32)
    net.load_state_dict(state, strict=True)
    net.eval()
    print(filename, sum(p.numel() for p in net.parameters()))
```

正常時は各モデルで307841パラメータと表示されます。保存deviceがMPSでもCPU mappingで読めます。これは読込の確認で、逆算探索やモデル精度の試験ではありません。5入力面の定義はモデルカードと `ml/train.py` の `planes` を参照してください。

完全な復元探索にはRust実行ファイルやKissat等が別途必要です。モデルをリポジトリの `solver/ml/`（実装ROOTからは `ml/`）へ置いた後のビルド・探索手順は、対応するソース版の `solver/README.md` に従ってください。

## ライセンスと同梱範囲

二つの重みと、同梱の自作README・モデルカードは **CC BY 4.0、著作者表示wand125** です。[LICENSE-WEIGHTS.md](LICENSE-WEIGHTS.md)、[同梱本文](CC-BY-4.0.txt)、[公式ライセンス](https://creativecommons.org/licenses/by/4.0/)を参照してください。プロジェクトの自作コードのMITとは別です。

このモデル用assetは、2重み、checksum・manifest、日英の説明・モデルカード、ライセンス情報を含みます。原訓練データ、私用実行ログ、認証情報、PyTorch/NumPyやSATソルバー本体は含みません。原訓練ファイルは現物不在で、完全な再学習再現や最終重み固有のholdout精度は未確認です。
