# Othello Retro engine

[日本語](README.md) | [English](README.en.md)

Rustによる一般SAT復元と、学習したCNNで候補を絞るPython探索・学習コードです。
Cargoは不変ですが、現在版はnative終局逆算修正と軽量autoのopt-inを含み、元の正式測定sourceとは異なります。[後続診断](../AUTO_DIAGNOSIS.md)と[歴史記録](history/v0.1.0/README.md)を参照してください。
自作コードは[MIT](LICENSE)、第三者依存は[個別の通知](THIRD_PARTY_NOTICES.md)と
[Python依存情報](PYTHON_DEPENDENCIES.md)を参照してください。

## 配置とビルド

この`solver/`を作業ディレクトリにします。`Cargo.toml`、`src/`、`ml/`は同階層です。
Linux／macOS、Rust1.98.0、C++17コンパイラ、別途インストールしたKissat4.0.3が必要です。
Kissatは https://github.com/arminbiere/kissat/tree/rel-4.0.3 から取得し、そのソースで
`./configure CC=clang -O3`、`make -j2`を実行して`build/`をPATHへ加えます。
Cargoはロックされた`cadical0.1.16`を取得し、同梱CaDiCaL1.9.5もビルドします。

```sh
rustup toolchain install 1.98.0 --profile minimal
nice -n 19 cargo +1.98.0 build --release --locked -j2
kissat --version
nice -n 19 cargo +1.98.0 test --release --locked -j2 -- --test-threads=1
```

既存の1.98.0があればtoolchain installは不要です。現在の11単体テストはKissat4.0.3付きで確認済みです。旧v0.1.0の9テストは歴史記録へ保持しています。Kissatが無い場合、SAT統合テストはskipメッセージを出すため、
その状態をSAT実行成功とは数えません。ソルバーのportfolioは複数プロセスを
起動し得るので`--jobs1`は1CPU保証ではありません。配布の元benchmarksで使う
同時2本ゲート等は、その測定手順に従って別途適用してください。

## SATで復元

盤面はa1からh8まで行優先の64文字。黒X、白O、空-。改行・空白は無視します。

```sh
./target/release/othello-retro solve examples/one-move.board --json --method sat --time 10 --prepass-ms 0 --jobs 1
./target/release/othello-retro solve examples/one-move.board --json --method sat --no-time-limit --prepass-ms 0 --jobs 1
```

例の合法棋譜は`["d3"]`です。`found`は棋譜あり、`unknown`は未解決であり不能証明
ではありません。`--no-time-limit`は`solve --method sat`で最終SATの時間上限を外します。
省略時の既定は10秒です。解けるまでの短さやCPU割当ては保証しません。

## Python依存と重み

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-inference.txt
```

別のRelease添付ファイルから`model.pt`と`model_passes.pt`を取得し、`ml/`直下へ置きます。
このソース配布に重み・元学習データ・pycacheは含みません。[MODEL_FILES.json](MODEL_FILES.json)
のSHA-256とサイズを照合してください。推論は重みを使い、学習元JSONLを読みません。
Torch2.2.2／NumPy1.26.4は正式CPU試験の版です。これは過去の訓練環境の完全な復元
を意味しません。CPU／FP32を明示する例は次のとおりです。

## autoの二つのopt-in設定

次のflagはPythonの探索・推論policyを選びます。`baseline`でも現在のRust逆算修正は有効です。元nativeを再現する場合はv0.1.0／commit`32e472e`を別checkoutでビルドしてください。

```sh
# 従来policy・従来推論（現在の修正nativeを使用）
OTHELLO_DEVICE=cpu RETRO_HALF=0 RETRO_AUTO_POLICY=baseline RETRO_INFERENCE_OPT=baseline OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python ml/worker.py ml/model.pt
# 軽量policy＋CPU融合推論
OTHELLO_DEVICE=cpu RETRO_HALF=0 RETRO_AUTO_POLICY=lightweight RETRO_INFERENCE_OPT=fused_channels_last OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python ml/worker.py ml/model.pt
```

未満盤終局の`miss`理由`incomplete_terminal_exact_route`は予定した一般SAT直行です。worker単独は最後の一般SATを実行しないため、呼出側でSATへ渡してください。`ui/server.py`はこの経路をmodelの冷起動より前に判断します。checkpointは同じで、新規学習は行いません。CPU以外へ融合opt-inを無条件に適用しないでください。

関連Python17テストは`python -m unittest benchmarks/test_lightweight.py benchmarks/test_analyze_auto_diagnostic.py`です。実行証拠とsource hashは[NATIVE_LIGHTWEIGHT_VALIDATION.json](NATIVE_LIGHTWEIGHT_VALIDATION.json)、3方式の測定・再開手順は[benchmarks/README.md](benchmarks/README.md)にあります。

## auto／学習探索

```sh
OTHELLO_DEVICE=cpu RETRO_HALF=0 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python ml/worker.py ml/model.pt
```

起動時の`{"status":"ready"}`を待ち、標準入力へ1行1JSONで、
`{"board":"64文字のX/O/-盤面","time":60}`を渡します。board文字列は実データへ
置き換えます。`model_passes.pt`が同じフォルダにあればパス対応経路で読み込みます。
このworkerは制限時間付きの候補探索で、`miss`は到達不能の証明ではありません。
worker単独は一般SATへの最終fallbackを行いません。未解決なら上記Rust SATへ渡します。

既存のauto→SATの評価パイプライン（結果は棋譜そのものではなく段階と時間）:

```sh
OTHELLO_DEVICE=cpu RETRO_HALF=0 python ml/eval_pipeline.py examples/one-move.hex --model ml/model.pt --model-passes ml/model_passes.pt --time 60
```

これは時間配分付きの従来実装です。全試行・最終SATを無制限にした正式ベンチマーク
とは別であり、固定bank・凍結harness・ゲート・環境条件を揃えずに同じ実験とは呼びません。
`ml/search.py`にも単独beam+SATの研究用CLIがあります。ビーム候補が尽きても不能証明に
なりません。パスを含む返却棋譜の受入れには、公開runnerの厳密な独立再生検査を使います。
歴史的な`search.verify`だけを汎用合法性チェッカーとして使わないでください。

## 自分で学習する場合とteacherの限界

```sh
./target/release/othello-retro spine 10 mix --seed 1 > spine.jsonl
python ml/label_spine.py spine.jsonl labels.jsonl --per 8 --limit 2 --workers 2
python ml/train_final.py labels.jsonl --out my-model.pt --epochs 25
```

これは生成・学習の操作例で、配布重みの完全再学習レシピではありません。
`spine ... --passes`はパスあり全64石対局に条件付けた生成で、64石未満の早期終局は
その生成対象ではありません。元の訓練集合・選択条件・環境の完全再現性は別の来歴資料を
参照してください。`ml/label.py`のwalkラベルは別形式で、上のspine特徴行と同じではありません。

- `label_spine.py`のパスなしUNSATはパスなし条件下だけの否定です。`reach`は指定手番と
  直前12着手に限定したパス許容の近似であり、そのUNSATを一般盤面の不能証明にしません。
- `train_final.py`は未知ラベル`y=-1`をpositiveへ置き換えます。学習用ヒューリスティックで、
  正しい到達可能性の証明ではありません。未知率とteacher条件を記録してください。
- `train.py`は評価比較用で、保存するモデルはscalar特徴付きです。その`--save`出力を
  `worker.py`の`Net(False)`へそのまま読み込めません。推論用には`train_final.py`を使います。
  比較用の追加依存は`pip install -r requirements-training.txt`です。
- 補助研究コードの既定並列数・探索時間は大きいことがあります。必要な資源を明示します。
  `bench_fix.py`の広域pkillだけは配布版から除き、他のSATプロセスを止めないようにしました。
  変更は[RELEASE_PATCHES.json](RELEASE_PATCHES.json)へ記録しています。

元400／20盤面の測定データとcheckpointは変更していません。現在のsource更新とWSL本番への適用は後続診断・rollout要約へ記録しています。
各ソースhashと除外範囲は[ENGINE_SOURCE_MANIFEST.json](ENGINE_SOURCE_MANIFEST.json)に記録します。
