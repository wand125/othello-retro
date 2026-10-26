# Othello Retro — ブラウザSAT／軽量Auto版

[日本語](README.md) | [English](README.en.md) · [試験版を開く](https://wand125.github.io/othello-retro/)

盤面から標準初期配置につながる合法棋譜を、端末内で探索します。方式はSATと任意の軽量Autoです。Rust encoder・Kissat 4.0.3と、Auto用ONNX Runtime Web 1.30.0を同一originの静的assetとして配布し、計算サーバーやCDNを使いません。AutoはCPU FP32・推論1スレッドで既存checkpointの候補順位を評価し、見つからなければ完全な一般SATへ戻ります。native版の400／20盤面測定・後続32盤面診断は別の実装・条件です。

盤面の入力と白黒反転・回転・鏡映、棋譜の再生・シーク、音色と音出力（標準／画面収録向け）、ブラウザ内保存、JSON入出力、圧縮URLでの棋譜共有に対応します。作成した棋譜はそのブラウザへ保存し、既存公開棋譜のsnapshotは一覧・個別URLから開けます。

## 探索と端末での確認

`found`は別のJavaScriptルール実装で黒先手・反転・強制パス・目標64セルを厳密再生します。限定probeやAutoのmissは到達不能ではありません。必要条件違反か、パスを許す完全一般式のUNSATだけを`unreachable`とします。通常探索の一般SATには時間上限を設けず、取消しはWorkerを終了します。DRATの独立検査は行いません。

現在のAutoは36石以上を対象に候補を絞り、幅8・親ごと2・事前選択128・30配置まで戻す探索と約12秒のガイド予算を使います。候補SATは制限付きで、失敗は一般SATへ戻します。SAT側も44石以上では強めのパスなしprobeを試し、未解決なら占有の冗長制約を省いた完全一般式へ進みます。work単位のprobe制限はwall秒数の保証ではありません。

スマートフォン実機での60秒以内を保証していません。[この端末で比較する](https://wand125.github.io/othello-retro/benchmark.html)から、まず5石数層のquick5、必要なら途中20・終局20・全40盤面をSAT／Autoで試せます。新しいWorkerで計算し、保存済みwitnessを再利用せず独立再生します。観測上限は1盤面60秒で、打切りは未解決です。結果は端末内でJSON保存し、POSTしません。Pythonで制御する実Chrome比較もスマートフォン実測とは区別します。

## モデル取得とビルド

Rust1.98.0（wasm32 target）・Emscripten・Python3・Node.jsを用意し、repo rootから実行します。まず[browser-models-v1](https://github.com/wand125/othello-retro/releases/tag/browser-models-v1)を取得し、archiveのSHA-256を照合して、**2個のONNXだけ**を`ui/models/`へコピーします。元の学習済みcheckpointは変えず、eval Conv–BN foldingで変換したモデルです。

```sh
BROWSER_MODEL_STAGE="$(mktemp -d)"
curl -fL 'https://github.com/wand125/othello-retro/releases/download/browser-models-v1/browser-models-v1.tar.gz' -o "$BROWSER_MODEL_STAGE/browser-models-v1.tar.gz"
printf '%s  %s\n' 'da61f0c2da3d518ebe6c6a5f5c02e9b6f20fe1f68a67a1258200617f17a0c248' "$BROWSER_MODEL_STAGE/browser-models-v1.tar.gz" | shasum -a 256 -c -
tar -xzf "$BROWSER_MODEL_STAGE/browser-models-v1.tar.gz" -C "$BROWSER_MODEL_STAGE"
mkdir -p browser-wasm/ui/models
cp "$BROWSER_MODEL_STAGE/model.fused.onnx" "$BROWSER_MODEL_STAGE/model_passes.fused.onnx" browser-wasm/ui/models/
```

```sh
cargo +1.98.0 build --manifest-path browser-wasm/engine/Cargo.toml --target wasm32-unknown-unknown --release --locked -j2
cp browser-wasm/engine/target/wasm32-unknown-unknown/release/othello_retro_browser_encoder.wasm browser-wasm/ui/encoder.wasm
EMCC="$(command -v emcc)" EM_CACHE=/tmp/othello-emcache python3 browser-wasm/solver/build.py
```

`EM_CACHE`には利用できるSDK cacheを用意するか、既存の適切なcacheへ変更してください。Kissatのソース・wasm32差分・flags・通知は[solver/README.md](solver/README.md)、モデル再変換と数値fixtureは[model-tools/README.md](model-tools/README.md)にあります。`model_passes`という名前はpass専用学習を意味しません。

## 検証・静的配布・オフライン

```sh
node --test browser-wasm/tests/test-verify.cjs browser-wasm/tests/test-policy.cjs browser-wasm/tests/test-auto.cjs
node browser-wasm/model-tools/verify-planes.cjs
node browser-wasm/tests/test-solver.cjs --smoke
node browser-wasm/solver/smoke.cjs
python3 browser-wasm/build_static.py --public-repo . --output /tmp/othello-static-new
python3 -m http.server 8000 --directory /tmp/othello-static-new
```

最初のcommandはルール・probe制御・Autoの27単体テストです。重い全受入れ検査は`node browser-wasm/tests/test-solver.cjs --stress`を別途実行します。commandの掲載は、その全stressを全端末で完走したという主張ではありません。

モデル取得を済ませてから`build_static.py`を実行します。`--output`は新しいdirectory、`--public-repo`は論文を含む公開repoです。任意の`--records`で`{"examples":[...]}`snapshotを指定でき、省略時は同梱棋譜を使います。ビルダーはデプロイしません。論文の本文・CSS・数式・日英切替を保持し、asset/linkだけを相対化します。

約14.24MBの推論runtimeと、必要なモデル1個約1.232MBはAutoで初めて必要になった時に読み込み、初回の一括precacheへ含めません。Service Workerに制御された状態で取得が成功したmodel/runtimeは、cacheが保持される間オフラインで利用できます。初回からオフラインでは取得できず、読込・推論のエラーはSATへfallbackします。

## ライセンス

自作Rust・JS・ビルド／検証コードは[MIT](LICENSE)。Kissat・Rust標準ライブラリ・Emscripten・ONNX Runtimeと同梱runtimeは各通知を保持します。`ui/kissat.LICENSES.txt`、`ui/RUST-LICENSES.txt`と参照先、`ui/inference/LICENSE`を確認してください。ONNX派生物は[CC BY 4.0](tests/licenses/CC-BY-4.0.txt)、著作者 **wand125**、元Releaseと変換変更を表示します。

[受入れfixture条件](tests/LICENSE.md)はMIT12件・既存論文CC BY 4.0由来2件を区別し、[model-tools](model-tools/README.md)の数値fixtureはMIT bank入力とmodel帰属を区別します。元論文本文・図、元bank、元測定値・hashは変更しません。全体の[LICENSE_SCOPE](../LICENSE_SCOPE.md)を参照してください。

44石以上では、制限付きのパスなし式、終盤12配置だけパスを許す式の順に試してから、一般SATまたはモデル誘導へ進みます。制限付きのUNSATを一般の到達不能とは扱いません。最後の一般式は無制限です。内部制限は衝突数・決定数であり、実時間の保証ではありません。
