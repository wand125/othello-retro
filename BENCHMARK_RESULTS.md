# 時間無制限ベンチマークの測定結果

[日本語](BENCHMARK_RESULTS.md) | [English](BENCHMARK_RESULTS.en.md)

2026-10-26更新。全4環境で、途中400盤面と終局20盤面を別々にSAT・auto各3回測定し、予定した全10,080試行が完了しました。条件と固定予定表は[測定設計](MEASUREMENT_DESIGN.md)を参照してください。ここには完了し、独立再生検査を通過したセットを掲載します。

## 4環境：途中400盤面

全4環境で各2,400試行、合計9,600試行が完了し、全棋譜の合法性と盤面一致を確認しました。共通完了ケースは400／400（100%）です。

| 環境 / Environment | SAT平均 / mean (s) | auto平均 / mean (s) | auto/SAT | 95%CI |
|---|---:|---:|---:|---|
| [WSL](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/summary.json) | 0.62050 | 0.59461 | 0.9583 | [0.8586, 1.0594] |
| [M4 Pro](benchmarks/m4-cpu222-unbounded-midgame-main-20261025/summary.json) | 1.56193 | 2.45550 | 1.5721 | [1.3799, 1.7940] |
| [M1](benchmarks/m1-cpu222-unbounded-midgame-main-20261025/summary.json) | 0.95663 | 1.16378 | 1.2165 | [1.0403, 1.3998] |
| [Intel i9](benchmarks/intel-cpu222-unbounded-midgame-main-20261025/summary.json) | 1.27192 | 1.45680 | 1.1454 | [1.0064, 1.2987] |

表の区間は各環境内のauto／SAT比です。M4・M1・Intelではautoの平均がSATを上回り、その個別区間も1より大きくなりました。CI相対半幅5%目標は4環境とも未達です。個別区間には複数比較補正をしていません。

差にはOS、ネイティブ数値処理、スケジューラ、背景負荷などが含まれます。M4の診断用休止は試行間で、探索時間と分けて記録しています。全プログラムの経過時間と、ケースごとの探索時間を区別してください。44石層の実際のモデル利用と、残る320例の直接SATも分けて分析します。

[4環境の対応付き集計JSON](benchmarks/four-environment-midgame-comparison-20261025.json)は公開の標準ライブラリ版analyzerで再計算しています。表の原CIはNumPy版で、有限回bootstrapの端点はRNGにより少し異なり得ます。平均値は一致します。各環境のリンク先で全記録・条件・負荷・hashを確認できます。

[元の信頼区間まで独立再計算した検証レポート](benchmarks/validation/)も公開しています。

## 4環境：終局20盤面

全4環境で各120試行、合計480試行が完了し、全棋譜の合法性と盤面一致を確認しました。共通完了ケースは20／20（100%）です。独立盤面数は20であり、各方式の60試行を60例とは数えません。途中400例とは別に集計します。

| 環境 | SAT平均（秒） | auto平均（秒） | auto／SAT | 95%CI |
|---|---:|---:|---:|---|
| [WSL](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/summary.json) | 9.20460 | 9.14890 | 0.9939 | [0.7963, 1.2605] |
| [M4 Pro](benchmarks/m4-cpu222-unbounded-endgame-main-20261025/summary.json) | 16.74105 | 43.69341 | 2.6100 | [2.0733, 3.2491] |
| [M1](benchmarks/m1-cpu222-unbounded-endgame-main-20261025/summary.json) | 11.50916 | 31.21702 | 2.7124 | [2.1779, 3.4251] |
| [Intel i9](benchmarks/intel-cpu222-unbounded-endgame-main-20261025/summary.json) | 17.63237 | 32.69917 | 1.8545 | [1.4588, 2.3634] |

表は各環境内のauto／SAT比と、元のNumPy版の個別95%CIです。M4・M1・Intelでは区間が1より大きく、WSLでは1を含みます。相対半幅5%目標は4環境すべて未達です。これは固定20例の補助試験で、一般の終局盤面へ一律に外挿せず、複数比較の同時保証とも扱いません。参照棋譜にパスがあることは、すべての復元棋譜にパスが必須という意味ではありません。

[対応付き4環境集計](benchmarks/four-environment-endgame-comparison-20261025.json)と[各環境の元CIを再計算した検証](benchmarks/validation/)を掲載しています。各環境のリンク先と同じフォルダに、全棋譜・metadata・検証・manifestがあります。

## 実行条件の逸脱と解釈

niceの予定値は19でしたが、両セットのmetadataに記録された値は**M4・WSLが19、M1・Intelが20**でした。[実行条件の監査JSON](benchmarks/execution-controls-20261026.json)に8セット分を保存しています。実測値を19へ書き換えたり、条件が完全一致したと扱ったりしていません。これはrunner開始時の記録で、全子プロセスの優先度やOS間で同じスケジューラ効果を保証するものでもありません。

各環境内のSAT・autoはその環境で記録された設定の結果です。環境間の差にはniceの逸脱、OS、背景負荷、数値backend、CPU割当てなどが混在します。M4には高い背景loadの記録もあり、独立したCPU性能順位やモデル単独の効果とは解釈しません。共通完了率100%は入力の揃い方を示し、条件の完全一致やCI精度を保証しません。

## WSL：途中400盤面

SAT・autoとも1,200／1,200試行で、入力と一致する合法な棋譜を返しました。独立盤面数は400で、3反復を1,200の独立盤面とは数えません。準備と集計を含む全プログラムの所要時間は24分39.7秒でした。

| 方式 | 検証済み完了 | 平均探索wall time |
|---|---:|---:|
| SAT | 1,200 / 1,200 | 0.62050秒 |
| auto | 1,200 / 1,200 | 0.59461秒 |

auto／SATの平均時間比は **0.9583**、層別の対応するcase-cluster bootstrapによる95%信頼区間は **[0.8586, 1.0594]** です。区間が1を含むため、この結果からautoの優位は断言できません。CIの相対半幅は10.55%で、事前の5%目標には届きませんでした。全件の棋譜が正しいことと、速度差の推定が十分に狭いことを区別します。

| 石数 | SAT平均（秒） | auto平均（秒） | auto／SAT | 95%CI |
|---|---:|---:|---:|---|
| 12 | 0.00421 | 0.00418 | 0.9935 | [0.9650, 1.0210] |
| 20 | 0.00442 | 0.00445 | 1.0070 | [0.9830, 1.0353] |
| 28 | 0.10812 | 0.10509 | 0.9720 | [0.8885, 1.0424] |
| 36 | 0.75857 | 0.83124 | 1.0958 | [0.9536, 1.2630] |
| 44 | 2.22717 | 2.02808 | 0.9106 | [0.7880, 1.0456] |

層別区間も個別の95%CIであり、全区間の同時95%保証ではありません。全体値は各層20%の重みで集計しています。44石未満の320例では、autoも最初からSAT経路へ入ります。全体値だけで学習モデルの効果を評価しません。

- [全2,400試行の棋譜・時間・段階ログ](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/runs.jsonl)

- [集計と信頼区間](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/summary.json)

- [実行条件](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/metadata.json)、[独立検証](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/verification.json)、[ファイルハッシュ](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/manifest.json)

## WSL：終局20盤面

SAT・autoとも60／60試行で、入力と一致する合法な棋譜を返しました。独立盤面数は20です。全プログラムの所要時間は18分23.95秒でした。

| 方式 | 検証済み完了 | 平均探索wall time |
|---|---:|---:|
| SAT | 60 / 60 | 9.20460秒 |
| auto | 60 / 60 | 9.14890秒 |

auto／SAT比は **0.99395**、95%CIは **[0.79626, 1.26047]** です。こちらも区間が1を含み、速度差を断言できません。CI相対半幅は26.81%で、5%目標は未達です。20例の補助試験を、途中400例と同じ精度とは扱いません。

[全120試行](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/runs.jsonl)・[集計](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/summary.json)・[条件](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/metadata.json)・[独立検証](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/verification.json)・[ハッシュ](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/manifest.json)

## 他の測定と環境比較

途中400盤面・終局20盤面とも、4環境の全予定試行が完了し、共通カバー率はそれぞれ100%です。時間上限による未解決を有限コストへ置き換えていません。niceの逸脱を含む実条件を併記した、完了した実行構成同士の記述的な比較です。

旧8盤面・有限時間・Torch2.6の予備測定や、ゲート不具合のあった実行を、この正式結果へ混ぜていません。公開しているのは測定データで、復元プログラムとモデルの公開ではありません。
