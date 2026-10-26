# ブラウザモデルの変換・数値fixture

このディレクトリのツールは、公開済みの二つのcheckpointをCPU evalで厳密に読み込み、推論用cloneのConv–BatchNorm9組を折り畳んでONNXへ変換します。新規学習やcheckpointの上書きは行いません。変換の一致を調べる資料であり、モデルの分類精度・スマートフォン速度を測る試験ではありません。

## 再現

Python3.12、PyTorch2.2.2、NumPy1.26.4、ONNX1.17.0、protobuf5.29.5とNode.jsを別環境へ用意します。既存の[Release重み](https://github.com/wand125/othello-retro/releases/tag/v0.1.0)を取得してhashを照合し、リポジトリルートから次を実行します。出力先は新しいfile／directoryを指定します。

```sh
node browser-wasm/model-tools/generate-edge-items.cjs --solver-repo . --output /tmp/legal-edges-new.json
python browser-wasm/model-tools/export_models.py --solver-repo . --weights-dir /path/to/weights --legal-edges /tmp/legal-edges-new.json --output /tmp/onnx-export-new
node browser-wasm/model-tools/verify-planes.cjs
```

`--solver-repo`は`ml/`のあるengine rootか、`solver/ml/`のある公開repo rootを受け付けます。generatorは対応する`browser-wasm/ui/verify.js`と`tests/cases.json`を読みます。公開bank由来の3合法参照棋譜を独立再生し、179本の本物の配置辺を逆向き候補として保存します。元の初回出力とportable再出力で、2ONNX・数値fixture・合法辺JSONのbyte一致を確認済みです。

## 入出力と照合

モデルは`model.fused.onnx`／`model_passes.fused.onnx`、inputは`planes` FP32 `[N,5,8,8]`、outputは`logits` FP32 `[N]`です。batchだけがdynamic、opset17／IR8です。物理的なchannels-lastはruntimeの選択で、論理入力はNCHWを維持します。出力はsigmoid前のraw logitです。

5面は戻した前駆局面の「着手側の石・相手石・空マス・除去した配置・反転石」。`numeric-fixtures.json`に式とrow-major順序を記録します。passあり候補では着手側を明示し、配置数の偶奇だけから推測しません。JS APIの`next`へfixtureの`mover`を渡します。

7batchは合法辺の1／16／128、強制pass直後の1、変換専用のrandom0/1入力1／16／128です。各batchにoriginal PyTorchとfolded PyTorchの期待logitを両方保持します。`verify-planes.cjs`は合法4batch・146候補・46,720個のFloat32をJSとPythonでbyte比較します。ONNX Runtimeの照合はfolded期待値を基準に、`abs(error) <= 1e-4 + 1e-4*abs(expected)`を使います。foldingによるoriginal差の最大absは主モデル0.0001564、旧モデル0.0001259で、relative許容を含めた範囲内です。近いscoreの順位までbit一致するとは主張しません。

モデル推論は候補を並べるheuristicです。合法性は別のルール再生で確認し、候補missや数値差を到達不能へ変換せず完全SATへfallbackする必要があります。

## 配布記録・条件

- `model-export-manifest.json`: **初回exportの歴史記録**をbyte保持しています。`files_sha256`は当時の出力集合で、現在のこのフォルダの全file一覧ではありません。初回exporterのhashとportableコードのhashは異なります。
- `portable-export-manifest.json`: CLI化したコードによる再出力の記録。`historical_original_export`で初回source／manifest／fixtureのhashを区別します。
- `portable-tools-manifest.json`: ここに配布する実fileのhash、再現比較、license／入力出典。
- `.pt`・`.onnx`・`.npy`はこのGitディレクトリには含みません。ONNXは元と同じ重みの派生物で、[CC BY 4.0](../tests/licenses/CC-BY-4.0.txt)・著作者 **wand125**・出典Releasev0.1.0・変換変更の表示を維持します。`model_passes.pt`という名前はpass専用学習を意味しません。[モデルカード](../../models/MODEL_CARD.ja.md)の来歴・限界を参照してください。

ツールコードは[MIT](../LICENSE)。合法辺の入力は既存合成bankの[MIT方針](../../BENCHMARK_LICENSE.md)を維持し、論文由来の不能例2件はこの生成に使いません。数値出力もモデルの著作者・出典・変換の表示を伴わせます。random入力は変換検査専用で、訓練データやreachability labelではありません。ONNX Runtime等の実装はそれぞれの通知を保持します。
