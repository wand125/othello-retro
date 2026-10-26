# ベンチマークデータ

[日本語](README.md) | [English](README.en.md) | [結果の読み方](../docs/benchmarks/results.md)

固定入力と、その入力に対する公開結果を収録しています。既存bank・予定表・rawのパスと内容は、再現と照合のため維持します。実行・検証・集計には [共通runner](../runner/README.md) を使います。

## 正式bank

| 入力 | 独立盤面数 | 反復・方式 | ファイル |
|---|---:|---|---|
| 途中局面 | 400（別にpilot 10） | SAT / Auto 各3回、主試験2,400試行 | [途中bank](study-midgame-cpu222-unbounded-v1.json) |
| 終局図 | 20 | SAT / Auto 各3回、120試行 | [終局bank](study-endgame-cpu222-unbounded-v1.json) |

どちらも予定表と参照棋譜を含みます。反復を独立盤面として数えません。元の正式測定は試行全体・最後の一般SATに時間上限を設けていません。[測定設計](../docs/benchmarks/design.md)を参照してください。

## 正式結果

- native：`{m4,m1,wsl,intel}-cpu222-unbounded-{midgame,endgame}-main-20261025/`。4環境で合計10,080試行です。
- [途中局面の4環境集計](four-environment-midgame-comparison-20261025.json)・[終局図の4環境集計](four-environment-endgame-comparison-20261025.json)・[終局の時間分布](terminal-time-distribution-20261026.json)
- ブラウザ：[追加した測定の条件と開始記録](../docs/benchmarks/browser.md)。同じbank・予定表を使い、検証後に `m4-browser-wasm-v3-{endgame,midgame}-main-20261026/` とruntime記録を追加します。

各結果のmetadata・verification・manifestで条件と完了状態を確認してください。実装、推論スレッド数、準備の計時範囲などが異なる測定を、単純なハードウェア速度差とは扱いません。

## 別実験・予備資料

| 内容 | 入口 |
|---|---|
| native軽量Auto：32盤面・各3回、全288試行 | [データ](native-lightweight-32x3-20261026/README.md)・[診断](../docs/algorithms/auto-diagnosis.md) |
| ブラウザ：先行40盤面、各版1回 | [全120観測と検証](../browser-wasm/benchmarks/browser-pilot-40-20261026/README.md) |
| WSL上のブラウザ用late-pass診断：難例3盤面 | [6試行・再実行手順](../browser-wasm/benchmarks/wsl-late-probe-20261026/README.md) |
| 固定8ケース、旧60秒の予備比較 | [入力](cases.json)・[比較資料](../docs/history/comparison-3x.md) |

`study-*-v1.json`、`study-*-cpu222-v1.json`、`protocol-3x.json`、`results/` は過去の条件・予備記録も含みます。現在の正式な無制限bankは上表の `*-cpu222-unbounded-v1.json` です。古い計時条件を主試験に混ぜません。

## 表現と利用条件

盤面はa1からh8まで行優先の64文字で、`X`=黒、`O`=白、`-`=空です。棋譜は小文字座標と強制パスの `pass` を使います。参照棋譜は到達可能性の証拠であり、唯一解ではありません。[データの利用条件](../BENCHMARK_LICENSE.md)・[独立検証の手順](../runner/VALIDATION.md)を参照してください。
