# ベンチマーク結果

[日本語](README.md) | [English](README.en.md)

2026-10-26更新。このページでは、**軽量化で速くなったか**と、**ブラウザ版でAutoを使うと速くなるか**を、次の2つの表で確認できます。

| 表記 | 動く場所 | 関係 |
|---|---|---|
| 従来Auto | native：PC・サーバーのPython/Rust | 改良前の基準版 |
| 軽量Auto | native：PC・サーバーのPython/Rust | 従来Autoの推論・候補探索・経路を軽量化した改良版 |
| ブラウザAuto v3 | ブラウザ：JavaScript/WASM/ONNX | 軽量化の方針をブラウザ向けに実装し、候補数・SATの試し方も調整した版 |

**v3はブラウザ実装内の版番号です。** native版が「従来→軽量→v3」と順に更新されたという意味ではありません。学習元の重みは共通で、再学習はしていません。native軽量版の速度を、そのままブラウザv3の速度として扱うことはできません。

各行は、同一環境・同一盤面での比較です。横に並ぶ方式どうしを比べてください。時間は短いほど高速です。時間比0.70なら約30%短縮、1.20なら約20%増を意味します。95%信頼区間（CI）が1を含む場合は速度差を断言しません。

<a id="native-comparison"></a>

## 1. 軽量化の効果：同じWSLで3方式を比較

**同じ盤面を、SAT・従来native Auto・軽量native Autoで各3回解きます。** SAT列は、Autoを使う利点があるか確認する基準です。 終局の比較は完了しています。中盤は既存の44石12盤面から、固定bank全400盤面へ広げて、3方式とも新しく測定します。

| 対象 | SAT平均（秒） | 従来native Auto平均（秒） | 軽量native Auto平均（秒） | 軽量／従来 [95%CI] | 状況 |
|---|---:|---:|---:|---|---|
| 中盤400盤面・全体 | — | — | — | — | 測定中・3,600試行 |
| うち44石80盤面 | — | — | — | — | 上の400盤面の内訳 |
| 終局20盤面 | 9.9502 | 9.9076 | 6.8658 | 0.6930 [0.5646, 0.8511] | 180/180試行を検証済み |

**終局20盤面では、軽量Autoの平均が従来より約31%短縮しました。中盤400盤面は結果待ちです。**

中盤の全体行は、普段使う範囲での速さを見るための値です。12・20・28・36・44石を各80盤面含みます。44石未満は両Autoとも最初からSATへ進むため、軽量化の違いは主に44石の行で確認します。44石でも先行SATで解けた試行はモデル推論を使いません。実際の推論使用数・復元成功数・SATへ戻った数も別に集計します。44石80盤面は400盤面に含まれ、追加の80盤面ではありません。

3方式の実行順を入れ替え、CPU・推論スレッド数・モデル・SATの同時実行数を揃えます。試行全体と最後の一般SATは時間無制限です。計時はモデル準備後からで、返された棋譜は別実装でも合法性と入力一致を確認します。軽量化にはnativeの修正・推論・候補探索・経路の変更を含み、モデル単独の効果ではありません。

[中盤400盤面の測定計画 (JSON)](native-lightweight-midgame-400x3-20261026-plan.json)・[終局を含む32盤面比較の条件](../docs/algorithms/auto-diagnosis.md)・[既存比較の集計 (JSON)](native-lightweight-32x3-20261026/data/analysis/analysis.json)・[既存全288棋譜 (生データ)](native-lightweight-32x3-20261026/data/run/runs.jsonl)。

<a id="browser-comparison"></a>

## 2. ブラウザ版：同じM4 Pro・ChromeでSATとAutoを比較

これは**ブラウザAuto v3**です。上のnative軽量Autoとは探索設定・実行系が異なります。同じ元重みを使いますが、同一版ではありません。

| 対象 | ブラウザSAT v3平均（秒） | ブラウザAuto v3平均（秒） | Auto／SAT [95%CI] | 状況 |
|---|---:|---:|---|---|
| 中盤400盤面 | 1.5870 | 1.4319 | 0.9023 [0.8279, 0.9728] | 2,400/2,400試行を検証済み |
| 終局20盤面 | 16.4185 | 17.4604 | 1.0635 [0.9815, 1.1851] | 120/120試行を検証済み |

**中盤400盤面ではAutoの平均が約9.8%短縮しました。終局20盤面では速度優位は示されていません。** 両方とも各方式3反復、全2,520棋譜を独立検証済みです。これはAuto v3全体の差で、モデル単体の効果ではありません。

[中盤400盤面の集計 (JSON)](m4-browser-wasm-v3-midgame-main-20261026/summary.json)・[全2,400棋譜 (生データ)](m4-browser-wasm-v3-midgame-main-20261026/runs.jsonl)・[独立検証 (JSON)](m4-browser-wasm-v3-midgame-main-20261026/verification.json)。

ブラウザは新WorkerからのWASM・必要なモデルの読込を含み、nativeはモデル準備後の計時です。2つの表の秒数を直接割って実装間の速度倍率とはしません。スマホ実機の1分以内も、このPC測定からは判断しません。

<details>
<summary>ブラウザ終局の最短・中央値・最長、計時条件と生データ</summary>

実M4 Pro／Chrome155.0.8059.86。同じ独立20盤面をSAT・Auto各3回測定し、**120/120試行の合法棋譜を独立検証**しました。試行全体・最後の一般SATは時間無制限です。

| 方式 | 検証済み | 平均（秒） | 盤面平均の最短 | 盤面平均の中央値 | 盤面平均の最長 |
|---|---:|---:|---:|---:|---:|
| ブラウザSAT v3 | 60 / 60 | 16.4185 | 1.360 | 10.771 | 46.979 |
| ブラウザAuto v3 | 60 / 60 | 17.4604 | 1.421 | 12.644 | 67.758 |

最短・中央値・最長は、20盤面それぞれの3反復平均の分布です。単発60試行の最短・最長とは異なります。Auto/SAT比は1.0635、95%CIは [0.9815,1.1851] で、1を含みます。各試行は新Workerから実行し、WASM・必要なモデルの読込を含み、Chrome起動は準備として除きます。CPU/FP32・推論1スレッド、HTTP cache・Service Workerなしです。

途中400盤面・2,400試行も完了しました。[測定条件](../docs/benchmarks/browser.md)・[集計 (JSON)](m4-browser-wasm-v3-endgame-main-20261026/summary.json)・[全120棋譜 (生データ)](m4-browser-wasm-v3-endgame-main-20261026/runs.jsonl)・[実行環境・hash (JSON)](m4-browser-wasm-v3-runtime-20261026.json)。

</details>

## 3. 参考：従来native版の4環境比較

ここは軽量化前の記録です。上のWSL再測定やブラウザ版の値と混ぜず、各環境内で従来AutoとSATを比べます。

<details>
<summary>M4 Pro・M1・WSL・Intel i9の中盤400／終局20盤面</summary>

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

</details>

## 4. 予備試験と原因診断

<details>
<summary>軽量Autoの中盤12盤面：400盤面へ拡張する前の予備比較</summary>

| 対象 | SAT平均（秒） | 従来native Auto平均（秒） | 軽量native Auto平均（秒） | 軽量／従来 [95%CI] |
|---|---:|---:|---:|---|
| 選択した44石12盤面 | 2.5873 | 1.7012 | 1.5776 | 0.9273 [0.7990, 1.0760] |

各3回の108試行を検証済みです。区間が1を含むため、速度優位は不確実でした。この12盤面だけで中盤全体を判断せず、上の400盤面比較を新たに測定します。[条件と分析](../docs/algorithms/auto-diagnosis.md)・[集計 (JSON)](native-lightweight-32x3-20261026/data/analysis/analysis.json)。

</details>

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
