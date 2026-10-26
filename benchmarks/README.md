# ベンチマーク結果

[日本語](README.md) | [English](README.en.md)

2026-10-26更新。主要結果を重要度順に掲載しています。

## 先に分かること

- **現行ブラウザ版**：正式な終局120試行は全件検証済み。ブラウザAuto v3は平均17.46秒、SATは16.42秒で、Autoの速度優位は示されていません。
- **native軽量Auto**：別のWSL比較では終局の平均が従来9.91秒→6.87秒、約31%短縮しました。中盤の改善は不確実です。
- **測定中**：ブラウザの途中400盤面・2,400試行。PCの結果からスマホの1分以内を保証するものではありません。

SATは盤面と着手の条件を数理制約として解く方式です。AutoはSATと学習モデルによる候補選別を組み合わせます。native版はブラウザ外で動くPython/Rust版を指します。

ブラウザAuto v3、native軽量Auto、従来native Autoは別の版です。同じ元重みを使いますが、実行系と探索設定が異なります。以下の表では版名を明記します。機械処理用のリンクには `(JSON)` または `(生データ)` を付けています。

表の時間は短いほど高速です。時間比は1未満なら分子側が高速で、95%信頼区間（CI）が1を含む場合は速度差を断言しません。「検証済み」は、返された棋譜を独立に再生し、合法性と入力盤面との一致を確認した数です。

## 1. 現行ブラウザv3：正式な終局測定

実M4 Pro／Chrome155.0.8059.86。同じ独立20盤面をSAT・Auto各3回測定し、**120/120試行の合法棋譜を独立検証**しました。試行全体・最後の一般SATは時間無制限です。

| 方式 | 検証済み | 平均（秒） | 盤面平均の最短 | 盤面平均の中央値 | 盤面平均の最長 |
|---|---:|---:|---:|---:|---:|
| ブラウザSAT v3 | 60 / 60 | 16.4185 | 1.360 | 10.771 | 46.979 |
| ブラウザAuto v3 | 60 / 60 | 17.4604 | 1.421 | 12.644 | 67.758 |

最短・中央値・最長は、20盤面それぞれの3反復平均の分布です。単発60試行の最短・最長とは異なります。Auto/SAT比は1.0635、95%CIは [0.9815,1.1851] で、1を含みます。各試行は新Workerから実行し、WASM・必要なモデルの読込を含み、Chrome起動は準備として除きます。CPU/FP32・推論1スレッド、HTTP cache・Service Workerなしです。

途中400盤面は継続中です。[測定条件](../docs/benchmarks/browser.md)・[集計 (JSON)](m4-browser-wasm-v3-endgame-main-20261026/summary.json)・[全120棋譜 (生データ)](m4-browser-wasm-v3-endgame-main-20261026/runs.jsonl)・[実行環境・hash (JSON)](m4-browser-wasm-v3-runtime-20261026.json)。

## 2. native軽量Auto：改善前後のWSL比較

44石中盤12盤面と終局20盤面を、3方式・各3回測定し、**288/288試行を検証**しました。重みの再学習はなく、nativeの逆算修正・推論・候補幅・経路変更を併用した改善です。

| 対象 | SAT平均（秒） | 従来native Auto平均（秒） | 軽量native Auto平均（秒） | 軽量／従来比 [95%CI] |
|---|---:|---:|---:|---|
| 44石中盤12盤面 | 2.5873 | 1.7012 | 1.5776 | 0.9273 [0.7990,1.0760] |
| 終局20盤面 | 9.9502 | 9.9076 | 6.8658 | 0.6930 [0.5646,0.8511] |

終局の平均は約31%短縮しました。中盤の区間は1を含むため、従来Autoに対する速度優位は断言できません。32盤面の別実験で、元の途中400盤面を全件測り直したものではありません。モデル準備後のnative計時と、新Workerからのブラウザ計時は条件が異なります。

[詳細な分析・条件](../docs/algorithms/auto-diagnosis.md)・[集計 (JSON)](native-lightweight-32x3-20261026/data/analysis/analysis.json)・[全288棋譜 (生データ)](native-lightweight-32x3-20261026/data/run/runs.jsonl)。

## 3. 元のnative版：4環境の正式比較

**軽量化前の従来native Auto**です。各環境で途中400盤面・終局20盤面をSAT・Auto各3回測定し、**合計10,080試行を独立検証**しています。反復を独立盤面として数えません。

### 途中400盤面

| 環境 | SAT平均（秒） | 従来native Auto平均（秒） | Auto/SAT | 95%CI |
|---|---:|---:|---:|---|
| WSL | 0.62050 | 0.59461 | 0.9583 | [0.8586, 1.0594] |
| M4 Pro | 1.56193 | 2.45550 | 1.5721 | [1.3799, 1.7940] |
| M1 | 0.95663 | 1.16378 | 1.2165 | [1.0403, 1.3998] |
| Intel i9 | 1.27192 | 1.45680 | 1.1454 | [1.0064, 1.2987] |

### 終局20盤面

| 環境 | SAT平均（秒） | 従来native Auto平均（秒） | Auto/SAT | 95%CI |
|---|---:|---:|---:|---|
| WSL | 9.20460 | 9.14890 | 0.9939 | [0.7963, 1.2605] |
| M4 Pro | 16.74105 | 43.69341 | 2.6100 | [2.0733, 3.2491] |
| M1 | 11.50916 | 31.21702 | 2.7124 | [2.1779, 3.4251] |
| Intel i9 | 17.63237 | 32.69917 | 1.8545 | [1.4588, 2.3634] |

従来AutoはM4 Pro・M1・Intel i9でSATより遅く、WSLでは速度差が不確実でした。軽量化後の結果と混同しないでください。

nice・OS・backend・背景負荷の差は詳細資料に記録しています。単純なCPU性能順位としては解釈しません。この正式測定も試行全体・最後の一般SATは無制限です。

[詳しい結果・終局の分布](../docs/benchmarks/results.md#midgame-results)・[途中4環境集計 (JSON)](four-environment-midgame-comparison-20261025.json)・[終局4環境集計 (JSON)](four-environment-endgame-comparison-20261025.json)・[最短・中央値・最長 (JSON)](terminal-time-distribution-20261026.json)。

## 4. 予備試験と原因診断

<details>
<summary>ブラウザ40盤面：各版1回の予備比較</summary>

| ブラウザ版 | 検証済み復元 | 60秒で未確定 | エラー |
|---|---:|---:|---:|
| Auto v1・旧版 | 38 / 40 | 2 | 0 |
| SAT v2・旧版 | 37 / 40 | 3 | 0 |
| Auto v3・改良後 | 40 / 40 | 0 | 0 |

v3の平均／中央値／最長は9.289／6.308／44.340秒でした。3版で得られた115棋譜を独立再生しています。独立盤面数は40であり、120ではありません。60秒超は未確定です。各1回の予備試験と、上記の正式測定は実行・計時条件が異なります。

[全結果と条件](../browser-wasm/benchmarks/browser-pilot-40-20261026/README.md)・[集計 (JSON)](../browser-wasm/benchmarks/browser-pilot-40-20261026/summary.json)。

</details>

<details>
<summary>native軽量Autoの候補設定をブラウザ向けに移す試作：WSL Node・3盤面</summary>

| 盤面末尾ID・石数 | A：現行ブラウザAuto v3 | B：native候補設定の試作 |
|---|---:|---:|
| 400000・44石 | 成功4.217秒 | 成功6.896秒 |
| 200001・64石 | 成功3.964秒 | 60.018秒で未確定 |
| 300002・36石 | 成功0.557秒 | 成功2.947秒 |

各1回の6観測で、成功5棋譜を独立検証しました。この3例ではBの高速化は見られませんでした。Bは候補幅を16、親ごとの上限を4に広げ、CNN前の候補絞りを外した試作です。SATの先行探索も変えており、候補幅だけの効果やnative版の同等移植を評価したものではありません。WSL Nodeで動かしたWASMで、Chrome・スマホの測定ではありません。

[設定・段階ログ・限界](../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/README.md)・[集計 (JSON)](../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/summary.json)・[全6観測 (生データ)](../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/results.jsonl)。

</details>

<details>
<summary>WSLのlate-pass診断：難例3盤面・2設定</summary>

| 盤面末尾ID | 通常late12 | SAT向け設定 |
|---|---:|---:|
| 200028 | 成功9.868秒 | 未確定19.115秒 |
| 200107 | 成功7.821秒 | 成功7.492秒 |
| 300185 | 成功14.418秒 | 未確定15.905秒 |

成功4・work-limit未確定2。各設定1回、100,000 conflicts／1,000,000 decisionsです。事後に選んだ難例の診断であり、一般の成功率やスマホ性能の標本ではありません。

[再実行手順](../browser-wasm/benchmarks/wsl-late-probe-20261026/README.md)・[集計 (JSON)](../browser-wasm/benchmarks/wsl-late-probe-20261026/summary.json)。

</details>

<details>
<summary>旧8盤面比較：各3回・旧60秒条件</summary>

| 環境 | モデル読込 | SAT 正しい判定／試行 | 従来Auto 正しい判定／試行 | 未確定 |
|---|---|---:|---:|---:|
| Mac CPU | 読込込み | 23 / 24 | 13 / 24 | 12 |
| WSL CPU | 読込込み | 24 / 24 | 24 / 24 | 0 |
| Cloud Run CPU | 読込込み | 24 / 24 | 21 / 24 | 3 |
| WSL CPU | 読込後 | 対象外 | 24 / 24 | 0 |

全168観測です。正しい判定には合法棋譜と中央石欠落例の排除を含みます。Torch2.6／NumPy2.2.6の旧有限時間条件で、正式な無制限bankとは別の測定です。

[盤面ごとの結果・条件](../docs/history/comparison-3x.md)・[Mac (JSON)](results/mac-cpu3-20261025/summary.json)・[WSL (JSON)](results/wsl-cpu3-20261025/summary.json)・[Cloud Run (JSON)](results/cloud-cpu3-20261025/summary.json)・[読込後WSL (JSON)](results/wsl-cpu3-warm-20261025/summary.json)。

</details>

## 再実行とデータ

[共通runner](../runner/README.md)・[独立検証](../runner/VALIDATION.md)・[ブラウザアダプター](../browser-wasm/benchmarks/README.md)・[測定設計](../docs/benchmarks/design.md)。

- [固定した途中400盤面・予定表 (JSON)](study-midgame-cpu222-unbounded-v1.json)：別にpilot10盤面。
- [固定した終局20盤面・予定表 (JSON)](study-endgame-cpu222-unbounded-v1.json)。
- [旧固定8ケース (JSON)](cases.json)。

native正式結果は`{m4,m1,wsl,intel}-cpu222-unbounded-{midgame,endgame}-main-20261025/`、ブラウザ正式結果は`m4-browser-wasm-v3-{endgame,midgame}-main-20261026/`です。既存入力・予定表・rawは保持しています。参照解を検索するfixtureは測定ツールの接続確認用です。[データの利用条件](../BENCHMARK_LICENSE.md)も参照してください。
