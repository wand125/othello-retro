# 測定結果

[日本語](results.md) | [English](results.en.md)

Auto改善後を含む、公開済みの全ベンチマークをまとめています。閲覧用の数値はこのページの表に示し、機械処理用のリンクには `(JSON)` または `(生データ)` を付けます。各測定の入力、実装版、反復数、計時条件を併記します。

| 測定 | 盤面・反復 | 完了状況 | 結果 |
|---|---|---|---|
| ブラウザv3・正式測定 | 同じ400／20盤面、SAT/Auto各3回 | 終局120/120検証済み・途中は実行中 | [正式ブラウザ結果](#browser-formal) |
| native軽量Auto改善後・WSL | 32盤面 × 3方式 × 各3回 | 全288試行を検証済み | [改善後Auto](#lightweight-auto) |
| 元のnative版・M4 / M1 / WSL / Intel | 途中400・終局20、SAT/Auto各3回 | 全10,080試行を検証済み | [途中](#midgame-results)・[終局](#terminal-results) |
| ブラウザ改良後v3・予備試験 | 40盤面 × 各1回、3版で全120観測 | v3は40/40、旧版には未確定あり | [ブラウザ比較](#browser-v3) |
| native候補設定のブラウザ向け試作・WSL Node | 3盤面 × 2設定 × 各1回 | 成功5・60秒観測未完1 | [試作の診断](#native-geometry-pilot) |
| WSL上のlate-pass診断 | 難例3盤面 × 2設定 × 各1回 | 成功4・work-limit未確定2 | [診断結果](#late-pass) |
| 旧60秒条件の予備比較 | 固定8盤面 × 各3回、Mac / WSL / Cloud Runと読込後WSL | 全168観測 | [過去の結果](#historical) |

<a id="lightweight-auto"></a>

## nativeのAuto改善後

WSLで44石中盤12盤面と終局20盤面を選び、SAT・従来Auto・軽量Autoを各3回測定しました。全288試行が入力と一致する合法棋譜を返し、独立に再生検証しています。重みの再学習は行っていません。

| 対象 | SAT平均（秒） | 従来native Auto平均（秒） | 軽量native Auto平均（秒） | 軽量／従来比 [95% CI] |
|---|---:|---:|---:|---|
| 44石中盤12盤面 | 2.5873 | 1.7012 | 1.5776 | 0.9273 [0.7990, 1.0760] |
| 終局20盤面 | 9.9502 | 9.9076 | 6.8658 | 0.6930 [0.5646, 0.8511] |

終局の平均は約31%短縮しました。中盤の区間は1を含むため、従来Autoに対する速度優位は断言できません。この32盤面の別実験は、元の途中400／終局20盤面の測定を置き換えません。nativeの逆算修正・推論・候補幅・経路の変更を併用した結果です。[詳細な分析と条件](../algorithms/auto-diagnosis.md)・[集計データ (JSON)](../../benchmarks/native-lightweight-32x3-20261026/data/analysis/analysis.json)。

<a id="browser-formal"></a>

## ブラウザv3：正式な終局20盤面の結果

予定した全120試行が完了しました。同じ独立20盤面をSAT・Auto各3回測定し、全棋譜が共通の独立検証を通過しています。途中400盤面・2,400試行は引き続き実行中です。

| 方式 | 検証済み試行 | 平均（秒） | 盤面平均の最短 | 盤面平均の中央値 | 盤面平均の最長 |
|---|---:|---:|---:|---:|---:|
| ブラウザSAT v3 | 60 / 60 | 16.4185 | 1.360 | 10.771 | 46.979 |
| ブラウザAuto v3 | 60 / 60 | 17.4604 | 1.421 | 12.644 | 67.758 |

最短・中央値・最長は、**各盤面の3反復を平均した20個の値**の分布です。単発60試行の最短・最長ではありません。Auto／SAT平均比は1.0635、対応するcase-cluster bootstrapの95%CIは [0.9815,1.1851] です。区間が1を含むため、Autoの速度優位は示されていません。

実M4 ProのChrome155.0.8059.86、CPU/FP32・推論1スレッドです。毎試行を新Workerで実行し、HTTP cache・Service Workerは使いません。Chrome起動は準備として除き、WASM・モデル読込と通信処理は試行時間に含めます。試行全体と最後の一般SATに時間上限はありません。nativeのモデル準備後や、各1回の予備試験とは条件が異なり、スマホ1分以内を示すものでもありません。

[集計 (JSON)](../../benchmarks/m4-browser-wasm-v3-endgame-main-20261026/summary.json)・[全120棋譜 (生データ)](../../benchmarks/m4-browser-wasm-v3-endgame-main-20261026/runs.jsonl)・[独立検証 (JSON)](../../benchmarks/m4-browser-wasm-v3-endgame-main-20261026/verification.json)・[実行環境とasset hash (JSON)](../../benchmarks/m4-browser-wasm-v3-runtime-20261026.json)・[測定条件](browser.md)。

<a id="browser-v3"></a>

## ブラウザ改良後：40盤面の予備試験

実M4 ProのデスクトップChromeで、途中20・終局20の同じ40盤面を各版1回ずつ測定しました。返った全棋譜を独立再生しています。60秒の観測上限は未確定を意味し、到達不能の判定ではありません。

| ブラウザ版 | 検証済み復元 | 60秒で未確定 | エラー |
|---|---:|---:|---:|
| ブラウザAuto v1・旧版 | 38 / 40 | 2 | 0 |
| ブラウザSAT v2・旧版 | 37 / 40 | 3 | 0 |
| ブラウザAuto v3・改良後 | 40 / 40 | 0 | 0 |

| 改良v3の対象 | 平均（秒） | 最短 | 中央値 | 最長 |
|---|---:|---:|---:|---:|
| 全40盤面 | 9.289 | 0.039 | 6.308 | 44.340 |
| 途中20盤面 | 3.596 | 0.039 | 0.852 | 29.132 |
| 終局20盤面 | 14.982 | 1.334 | 9.954 | 44.340 |

v3はSATの予算配分・late-pass式・必要時の学習誘導を組み合わせた版です。実際のモデル推論は4件、学習補助経路での完了は1件でした。PCの測定であり、スマホでの1分以内を保証しません。正式測定は終局120試行が完了し、途中局面は時間無制限で継続中です。[予備試験の詳細](../../browser-wasm/benchmarks/browser-pilot-40-20261026/README.md)・[集計データ (JSON)](../../browser-wasm/benchmarks/browser-pilot-40-20261026/summary.json)・[正式測定の条件](browser.md)。

以下の元native版は、全4環境で予定した10,080試行が完了し、全棋譜の合法性と目標64マスの一致を独立検証しています。[測定設計](design.md)を参照してください。

<a id="midgame-results"></a>

## 元のnative版：途中400盤面・4環境

各環境2,400試行、計9,600試行です。共通完了ケースは400／400（100%）です。3反復を独立1,200盤面とは数えません。

| 環境 / Environment | SAT平均 / mean (s) | 従来native Auto平均（秒） | auto/SAT | 95%CI | 生データ |
|---|---:|---:|---:|---|---|
| WSL | 0.62050 | 0.59461 | 0.9583 | [0.8586, 1.0594] | [集計 (JSON)](../../benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/summary.json) |
| M4 Pro | 1.56193 | 2.45550 | 1.5721 | [1.3799, 1.7940] | [集計 (JSON)](../../benchmarks/m4-cpu222-unbounded-midgame-main-20261025/summary.json) |
| M1 | 0.95663 | 1.16378 | 1.2165 | [1.0403, 1.3998] | [集計 (JSON)](../../benchmarks/m1-cpu222-unbounded-midgame-main-20261025/summary.json) |
| Intel i9 | 1.27192 | 1.45680 | 1.1454 | [1.0064, 1.2987] | [集計 (JSON)](../../benchmarks/intel-cpu222-unbounded-midgame-main-20261025/summary.json) |

表は各環境内のauto／SAT比と個別95%CIです。M4・M1・Intelではauto平均がSATを上回り、区間も1より大きくなりました。95%CIの相対半径は10.55–15.06%で、複数比較補正はしていません。全件の棋譜が正しいことと、速度差の推定精度を区別します。

[4環境の対応付き集計 (JSON)](../../benchmarks/four-environment-midgame-comparison-20261025.json)。44石未満の320例ではautoも直接SATへ入り、44石層でも初期SATで完了する場合があります。全体平均だけをモデル単独の効果と解釈しません。

<details>
<summary>WSLの石数別内訳</summary>

| 石数 | SAT平均（秒） | 従来native Auto平均（秒） | auto／SAT | 95%CI |
|---|---:|---:|---:|---|
| 12 | 0.00421 | 0.00418 | 0.9935 | [0.9650, 1.0210] |
| 20 | 0.00442 | 0.00445 | 1.0070 | [0.9830, 1.0353] |
| 28 | 0.10812 | 0.10509 | 0.9720 | [0.8885, 1.0424] |
| 36 | 0.75857 | 0.83124 | 1.0958 | [0.9536, 1.2630] |
| 44 | 2.22717 | 2.02808 | 0.9106 | [0.7880, 1.0456] |

各層20%の固定重み、各80独立盤面です。層別区間も個別の95%CIで、同時95%保証ではありません。[元の集計 (JSON)](../../benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/summary.json)に全体・層別の統計を保持しています。

</details>

<a id="terminal-results"></a>

## 元のnative版：終局20盤面・4環境

各環境120試行、計480試行です。共通完了ケースは20／20（100%）。独立盤面数は20であり、各方式の60試行を60例とは数えません。途中400例とは別に集計します。

| 環境 | SAT平均（秒） | 従来native Auto平均（秒） | auto／SAT | 95%CI | 生データ |
|---|---:|---:|---:|---|---|
| WSL | 9.20460 | 9.14890 | 0.9939 | [0.7963, 1.2605] | [集計 (JSON)](../../benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/summary.json) |
| M4 Pro | 16.74105 | 43.69341 | 2.6100 | [2.0733, 3.2491] | [集計 (JSON)](../../benchmarks/m4-cpu222-unbounded-endgame-main-20261025/summary.json) |
| M1 | 11.50916 | 31.21702 | 2.7124 | [2.1779, 3.4251] | [集計 (JSON)](../../benchmarks/m1-cpu222-unbounded-endgame-main-20261025/summary.json) |
| Intel i9 | 17.63237 | 32.69917 | 1.8545 | [1.4588, 2.3634] | [集計 (JSON)](../../benchmarks/intel-cpu222-unbounded-endgame-main-20261025/summary.json) |

<a id="terminal-distribution"></a>

### 終局の最短・中央値・最長

各盤面・方式の`effective_wall_seconds`を**3反復で平均し、得られた20個の値の最小値・中央値・最大値**を示します。中央値は小さい順の10番目と11番目の平均です。単発60試行の最短・最長とは異なり、時間には中断前に消費した探索時間も含みます。

| 環境 | 方式 | 最短（秒） | 中央値（秒） | 最長（秒） |
|---|---|---:|---:|---:|
| WSL | SAT | 1.296 | 9.024 | 18.918 |
| WSL | auto | 0.753 | 9.593 | 16.431 |
| M4 Pro | SAT | 2.729 | 16.021 | 33.395 |
| M4 Pro | auto | 1.074 | 46.509 | 114.104 |
| M1 | SAT | 2.283 | 11.028 | 20.839 |
| M1 | auto | 0.934 | 33.227 | 73.017 |
| Intel i9 | SAT | 5.259 | 18.291 | 33.890 |
| Intel i9 | auto | 1.695 | 34.710 | 66.101 |

[分布 (JSON)](../../benchmarks/terminal-time-distribution-20261026.json)に計算規則、各盤面平均、最短・最長のcase ID、中央値を構成するcase ID、別集計の単発60試行分布とraw hashを保持しています。表は小数第3位までの丸め値です。

終局の個別95%CIはM4・M1・Intelで1より大きく、WSLでは1を含みます。95%CIの相対半径は24.49–27.44%です。この固定20例の補助試験を一般の終局盤面へ一律に外挿せず、複数比較の同時保証とも扱いません。参照棋譜のパスは、すべての復元棋譜にパスが必須という意味ではありません。

[対応付き4環境集計 (JSON)](../../benchmarks/four-environment-endgame-comparison-20261025.json)。各平均表の「集計JSON」と同じフォルダに全棋譜・条件・検証・manifestがあります。表のCIは元のNumPy版で、[独立再計算レポート](../../benchmarks/validation)も公開しています。公開の標準ライブラリ版analyzerは別RNGのため有限回bootstrapの端点が少し異なり得ますが、平均値は一致します。

## 実行条件の逸脱と解釈

niceの予定値は19でしたが、両セットのmetadataは**M4・WSLが19、M1・Intelが20**を記録しています。[実条件監査 (JSON)](../../benchmarks/execution-controls-20261026.json)へ8セット分を保存し、予定値へ書き換えていません。これはrunner開始時の記録で、全子プロセスの優先度やOS間のスケジューラ効果の一致を保証しません。

環境間の差にはnice、OS、数値backend、CPU割当て、背景負荷が混在します。M4には高い背景loadと試行間の診断用休止が記録され、休止は探索時間と分けて扱います。全プログラムの経過時間とケースの探索時間を区別し、独立したCPU性能順位とは解釈しません。共通完了率100%も条件の完全一致やCI精度の保証ではありません。

旧8盤面・有限時間・Torch2.6の予備測定や、不具合のあったゲートの実行は正式結果へ混ぜていません。未完了を有限の失敗コストへ置き換えていません。対応する復元ソースと既存重みは[Release v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0)で公開しています。

<a id="native-geometry-pilot"></a>

## native候補設定をブラウザ向けに移す試作

| 盤面末尾ID・石数 | A：現行ブラウザAuto v3 | B：native候補設定の試作 |
|---|---:|---:|
| 400000・44石 | 成功4.217秒 | 成功6.896秒 |
| 200001・64石 | 成功3.964秒 | 60.018秒で未確定 |
| 300002・36石 | 成功0.557秒 | 成功2.947秒 |

各1回の6観測で、成功5棋譜を独立検証しました。この3例ではBの高速化は見られませんでした。Bは候補幅を16、親ごとの上限を4に広げ、CNN前の候補絞りを外した試作です。SATの先行探索も変えており、候補幅だけの効果やnative版の同等移植を評価したものではありません。WSL Nodeで動かしたWASMで、Chrome・スマホの測定ではありません。

[設定・段階ログ・限界](../../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/README.md)・[集計 (JSON)](../../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/summary.json)・[全6観測 (生データ)](../../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/results.jsonl)。

<a id="late-pass"></a>

## WSLのlate-pass診断

M4で60秒以内に解けなかった終局3盤面を事後に選び、WSL / Ryzen 9 9950X / Nodeで各設定1回測定しました。内部上限は100,000 conflicts・1,000,000 decisionsです。

| 盤面末尾ID | 通常late12 | SAT向け設定 |
|---|---:|---:|
| 200028 | 成功 9.868秒 | 未確定 19.115秒 |
| 200107 | 成功 7.821秒 | 成功 7.492秒 |
| 300185 | 成功 14.418秒 | 未確定 15.905秒 |

成功4件は独立に再生検証しています。未確定2件はwork-limitに達したもので、外側の60秒watchdogによる打切りではありません。選択した難例の診断であり、一般の成功率やスマホの速度を示す測定ではありません。[条件・再実行手順](../../browser-wasm/benchmarks/wsl-late-probe-20261026/README.md)・[集計 (JSON)](../../browser-wasm/benchmarks/wsl-late-probe-20261026/summary.json)。

<a id="historical"></a>

## 旧8盤面・各3回の予備比較

Torch2.6／NumPy2.2.6、各試行60秒の旧条件です。入力は到達可能7例と、中央石欠落による到達不能1例。下表の「正しい判定」には合法棋譜と、この不能例の排除を含みます。未確定を誤った到達不能判定とは数えません。モデル読込込みと読込後は計時条件が異なります。

| 環境 | モデル読込 | SAT 正しい判定／試行 | Auto 正しい判定／試行 | 未確定 | 生データ |
|---|---|---:|---:|---:|---|
| Mac CPU | 読込込み | 23 / 24 | 13 / 24 | 12 | [集計 (JSON)](../../benchmarks/results/mac-cpu3-20261025/summary.json) |
| WSL CPU | 読込込み | 24 / 24 | 24 / 24 | 0 | [集計 (JSON)](../../benchmarks/results/wsl-cpu3-20261025/summary.json) |
| Cloud Run CPU | 読込込み | 24 / 24 | 21 / 24 | 3 | [集計 (JSON)](../../benchmarks/results/cloud-cpu3-20261025/summary.json) |
| WSL CPU | 読込後 | 対象外 | 24 / 24 | 0 | [集計 (JSON)](../../benchmarks/results/wsl-cpu3-warm-20261025/summary.json) |

[盤面ごとの表と詳細条件](../history/comparison-3x.md)も公開しています。168観測の予備試験であり、正式な無制限測定とは別です。[実行・独立検証ツール](../../runner/README.md)には接続確認用fixtureの説明もあります。
