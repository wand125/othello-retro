# 公開bankを別の環境・プログラムで測る

[日本語](README.md) | [English](README.en.md)

盤面生成・棋譜・計測ログ・集計結果を個別／一括で調べるコマンドは、[検証手順](VALIDATION.md)にまとめています。

このフォルダは標準ライブラリだけを使う Python 3.10 以降向けの測定ツールです。実行対象はPOSIX環境（Linux・macOS・WSL）です。外部プログラムをJSONの入出力で接続し、同じbank・試行順・盤面で測れます。逆算ソルバー、学習モデル、既存サービスの実装は含みません。`runner/` の新規ツールは [MITライセンス](LICENSE) です。公開された合成テスト盤面bankの再利用条件は [BENCHMARK_LICENSE.md](../BENCHMARK_LICENSE.md) を参照してください。

## 自分のプログラムを接続する

リポジトリのルートで実行します。

```sh
python3 runner/benchmark.py run \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --config my-programs.local.json \
  --split pilot \
  --output .runs/my-environment-pilot
```

`examples/external-program.json` を設定のひな形にしてください。`programs` の `sat` と `auto` は、固定scheduleが参照する比較枠の名前です。接続先が実際にSATやCNNを使うことをツールが認定する名前ではありません。別のアルゴリズムでも、それぞれの枠へ接続できます。

- `command` は実行ファイルと引数のJSON配列です。シェル文字列ではなく、引数を個別に指定します。
- `cwd` の相対パスは設定ファイルの親から解決します。省略時はrunnerを起動した作業ディレクトリです。例の `../..` は `runner/examples/` からリポジトリのルートを指します。
- 共通 `env` とプログラム別 `env` を指定できます。例のOMP/BLAS設定を外部プログラムが実際に採用するかは実装次第です。CPU数・スレッド数・デバイス・モデル・ライブラリ版・OS・コンパイラ・内部探索上限を別途記録してください。ラベルや自己申告は実測による保証ではありません。
- 設定に秘密情報を入れないでください。実コマンド・作業パス・指定環境変数は `private-runtime.json`、stderr等は `.private-logs/` に保存されます。これらのprivateファイルを公開結果へ混ぜないでください。

設定の各プログラムには `declared_environment` と `artifacts` も指定できます。例えば次の項目を `programs.sat` / `programs.auto` へ追加し、実際の条件とファイル名へ置き換えます。

```json
{
  "declared_environment": {"device":"cpu", "dtype":"float32", "inference_threads":2, "solver_parallelism":2},
  "artifacts": [{"name":"model", "path":"my-model.bin"}]
}
```

`artifacts` の相対パスはそのプログラムの `cwd` 基準です。実行ファイル、ファイルとして指定された引数、追加artifactsのSHA-256を記録します。自動では依存関係を全て列挙できないため、必要なソース・モデル・設定なども追加してください。公開metadataには許可された環境項目とhashを残し、私用パスを分離します。再開時は設定・runner・接続先・artifactsの同一性を確認します。

元bankの `protocol` にあるソース・モデル・ライブラリのhashは、元プログラムの実験条件の記録です。汎用接続先に同じモデルやソースを要求するものではありません。入力の `cases`・`schedule`・bank hashを固定し、接続するプログラムの識別情報・hash・環境・計時modeをrunner側metadataと分けて記録します。

元実験に近い条件の例はCPU・FP32・推論2スレッドと `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2` です。設定例はFP32やCPU affinity、SAT子プロセス数を強制しません。外部プログラム側でも設定して、実際の条件を確認してください。

pilotは主試験とは異なる10盤面で、接続と所要時間の予備確認用です。終局bankにはpilotはありません。主試験は `--split main` へ変更します。途中盤面400例と終局20例は別bank・別結果ディレクトリで測ります。途中は各方式3回の2400試行、終局は各方式3回の120試行です。

```sh
python3 runner/benchmark.py run --bank benchmarks/study-midgame-cpu222-unbounded-v1.json --config my-programs.local.json --split main --output .runs/my-midgame
python3 runner/benchmark.py run --bank benchmarks/study-endgame-cpu222-unbounded-v1.json --config my-programs.local.json --split main --output .runs/my-endgame
```

`--method sat` または `--method auto` で一方の枠だけにも接続できます。再開時は同じ設定・bank・出力先で `--resume` を指定します。予定を変えたり、速く解けた盤面だけを選び直したりせず、元scheduleと対応を保ってください。`--pause-file FILE` は試行間の休止用です。既定は出力ディレクトリ内の `PAUSE` です。ファイルが存在する間は次の試行へ進まず、削除すると再開します。実行中の試行に時間上限を追加する機能ではありません。

```sh
touch .runs/my-midgame/PAUSE
# 再開時
rm .runs/my-midgame/PAUSE
```

Ctrl-Cなどの手動中断では、未完了試行を成功rowへ加えず、再開時に同じ試行を実行し直します。既に使った計算時間は別記して実効時間へ加えます。SIGKILLなどで未完了試行の時間を正確に保全できなかった場合は、過小計上を避けるため再開を拒否します。手動中断や休止は記録し、試行の計算時間と全体経過時間を混同しません。

## JSON adapter仕様

入力は1行1JSONです。参照棋譜は渡しません。

```json
{"id":"trial-identifier","board":"---------------------------OX------XO---------------------------"}
```

`board` は改行なしの64文字で、1文字目がa1、8文字目がh1、最後がh8です。黒 `X`、白 `O`、空 `-`。標準初期配置から黒先手で、その盤面に至る手順を求めます。

成功時は次の形を返します。

```json
{"status":"found","moves":[]}
```

上の初期盤面には空の棋譜が対応します。一般には要求された盤面に完全一致する棋譜が必要です。座標は小文字 `a1`〜`h8`、パスは文字列 `pass`。終局を示すためだけの二重パスは付けません。置ける場所がある側の手番を勝手に変えることはできません。合法手がなく相手に合法手がある強制パスだけは、省略してもverifierが補います。

`unknown` や `error` は `found` と同等ではありません。不正な棋譜、JSON不正、結果前の終了、`found` 以外の応答ではrunnerはエラーを記録して停止し、次のcaseへ黙って進みません。bankには合法な参照棋譜があります。到達可能な入力への `unreachable` は誤った判定になります。外部プログラムに内部の時間上限や候補打切りがあれば、その方針を記録してください。このrunnerに全試行の時間cutoffを設けなくても、外部プログラムが同じ条件とは限りません。

### oneshot

1要求ごとに `command` を新しく起動し、stdinへJSONを渡します。stdoutへ結果JSONを1行出して終了してください。**プロセス起動・モデル読込などもその試行時間に含まれます。**

### resident

`command` を起動したら、必要なモデル読込と固定warmupを終えてから次を出します。

```json
{"event":"ready"}
```

以降はstdinの要求ごとに結果を返します。

```json
{"event":"result","payload":{"status":"found","moves":["d3","c3"]}}
```

結果直返しも受理しますが、上の形式を推奨します。途中経過は `{"event":"progress","payload":{...}}` として出せます。`ready` 前の準備は試行時間と分けて記録されます。oneshotの起動込み時間とresidentの準備後時間は異なる測定条件です。混ぜて速さの順位を付けず、mode・warmup方針・環境条件を併記してください。

stdoutにはJSONプロトコル以外のメッセージを出さず、説明やdebug出力はstderrへ送ってください。

## 接続だけを確かめるfixture

```sh
python3 runner/benchmark.py run --bank benchmarks/study-midgame-cpu222-unbounded-v1.json --config runner/examples/fixture-oneshot.json --split pilot --output .runs/fixture-oneshot
python3 runner/benchmark.py run --bank benchmarks/study-midgame-cpu222-unbounded-v1.json --config runner/examples/fixture-resident.json --split pilot --output .runs/fixture-resident
```

`fixture_adapter.py` は公開bankの**参照解を検索して返すだけで、逆算探索を行いません**。JSON接続、固定順序、再生検証、出力を確認するためのfixtureです。config・応答に `fixture:true` を付け、`measurement_kind:harness-smoke-only` を返します。fixtureの速度をソルバー性能として公開したり、正式結果と混ぜたりしないでください。

## 解析と公開用export

同じbankの測定だけを同じ解析へ渡します。`--run LABEL=DIR` は繰り返し指定できます。次は1環境でsat/autoを解析する例です。

```sh
python3 runner/analyze.py \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --run local=.runs/my-midgame \
  --split main --output .runs/my-midgame-analysis.json
```

複数環境では `--run hostA=.runs/hostA --run hostB=.runs/hostB` とし、必要なら `--require-label hostA --require-label hostB` で比較に必要な環境を明示します。解析は各棋譜・盤面・固定順序・hashを再確認し、層内の独立caseを単位にしたpaired bootstrapの95%区間を出します。既定は3000回、seed 730253で、`--bootstrap-replicates` / `--bootstrap-seed` で明示できます。各caseの反復はまとめて扱います。90%共通完了は精度保証でも早期終了の許可でもありません。時間比の区間幅や、1をまたぐかを併記し、終局20例は補助測定として扱います。

公開前は私用の出力先とは別のディレクトリへexportします。

```sh
python3 runner/export.py \
  --input .runs/my-midgame \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --split main --output public-results/my-midgame
```

exportは再検証した棋譜・時間・許可されたmetadataを出し、実コマンド、私用ログ、指定環境変数、秘密情報らしい項目、絶対パスを除外します。`metadata.json`、`runs.jsonl`、`verification.json`、`manifest.json` と、完成時の `summary.json` などが出ます。公開前に内容を確認してください。途中までの結果は `incomplete`、fixtureはfixtureとして区別します。1環境の完了だけでは、複数環境を比較できる状態とは判定しません。pilotの解析・exportでは両方に `--split pilot` を指定します。

## 独立した再生検証

`verify.py` の `verify(moves, target)` は標準ルールで全手を再生し、全64マスの一致を検査します。戻り値は正規化した `moves`、終局判定 `terminal`、置石数 `placements`、パス数 `passes`。不正な手や盤面は `InvalidRecord`（`ValueError` の派生）です。

```sh
python3 -m unittest discover -s runner/tests -p 'test_verify.py'
```

同じcaseの3反復を独立3盤面とは数えません。途中400と終局20、未完成の進捗と完成済み結果、fixtureと性能測定を分けて扱ってください。

[ブラウザのWebAssembly版を接続する手順](../browser-wasm/benchmarks/README.md)もあります。
