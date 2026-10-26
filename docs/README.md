# 文書一覧

[日本語](README.md) | [English](README.en.md) | [リポジトリの入口](../README.md)

利用・ビルド・実行の手順は各実装のREADMEに置き、方式の説明や結果の読み方をこのフォルダにまとめています。

| 分野 | 日本語 | English |
|---|---|---|
| 全ベンチマークの測定結果 | [結果](../benchmarks/README.md) | [Results](../benchmarks/README.en.md) |
| 標本、反復、計時、統計 | [測定設計](benchmarks/design.md) | [Measurement design](benchmarks/design.en.md) |
| ブラウザ正式測定の条件と開始記録 | [ブラウザ測定](benchmarks/browser.md) | [Browser study](benchmarks/browser.en.md) |
| native軽量Autoの原因分析・比較 | [Auto診断](algorithms/auto-diagnosis.md) | [Auto diagnosis](algorithms/auto-diagnosis.en.md) |
| 使用ソルバー、依存、配布範囲 | [ソルバー](distribution/solvers.md) | [Solvers](distribution/solvers.en.md) |
| ソース・重みの公開範囲と来歴 | [公開状況](distribution/publication.md) | [Publication scope](distribution/publication.en.md) |

## データと再実行

- [固定bank・結果の一覧](../benchmarks/README.md)
- [共通runner](../runner/README.md)・[生成、棋譜、集計の検証](../runner/VALIDATION.md)
- [ブラウザ測定アダプター](../browser-wasm/benchmarks/README.md)
- [モデルカード](../models/MODEL_CARD.ja.md)・[論文の補足データ](../paper-data/README.md)

## 過去の記録

- [固定8盤面・各3回の予備比較](history/comparison-3x.md)：現在の無制限の正式測定とは別です。
- [Releaseの検証記録](releases/README.md)
- [現在版と凍結したソースの区別](repository.md)

ルートの `AUTO_DIAGNOSIS*`、`MEASUREMENT_DESIGN*`、`SOLVERS*`、`BROWSER_BENCHMARK*` は、公開済み論文・Releaseや凍結資料からのリンクを保つ短い案内です。本文はこのフォルダにあります。
