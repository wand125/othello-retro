# 時間無制限ベンチマークの測定結果

[日本語](BENCHMARK_RESULTS.md) | [English](BENCHMARK_RESULTS.en.md)

2026-10-25。途中400盤面と終局20盤面を別々に、SAT・autoで各3回測定しています。条件と固定予定表は[測定設計](MEASUREMENT_DESIGN.md)を参照してください。ここには完了し、独立再生検査を通過したセットを掲載します。

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

WSLは途中・終局の計2,520試行が完了しました。M4・M1・Intelは測定中で、完了したセットから追記します。上の結果はWSL内のSAT／auto比較です。4環境で共通完了したケースが90%以上という条件を満たすまでは、機器間の優劣を結論しません。

旧8盤面・有限時間・Torch2.6の予備測定や、ゲート不具合のあった実行を、この正式結果へ混ぜていません。公開しているのは測定データで、復元プログラムとモデルの公開ではありません。
