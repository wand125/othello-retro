# Othello Retro

[日本語](README.md) | [English](README.en.md)

オセロの盤面から、標準初期配置につながる合法な棋譜を復元します。ブラウザ版、Rust/Pythonの復元器、固定盤面を使う測定・検証ツールを公開しています。

- [ブラウザ試験版](https://wand125.github.io/othello-retro/)：SAT／軽量Autoを端末内で実行。計算バックエンドは不要です。
- [端末での速度測定](https://wand125.github.io/othello-retro/benchmark.html)：スマホでも実行でき、結果をJSONで保存できます。
- [サーバー版試験公開アプリ](https://othello-retro.logicpuzzle.app/)・[作成された棋譜](https://othello-retro.logicpuzzle.app/examples)
- インタラクティブ論文：[日本語](https://othello-retro.logicpuzzle.app/paper?lang=ja) / [English](https://othello-retro.logicpuzzle.app/paper?lang=en)

## 使う・ビルドする

| 目的 | 入口 |
|---|---|
| ブラウザ版を使う・静的サイトとして配布する | [ブラウザ版の手順](browser-wasm/README.md) |
| native復元器をビルドし、SAT／Autoを実行する | [復元器の手順](solver/README.md) |
| 別のプログラム・環境で同じ盤面を測定する | [共通runner](runner/README.md)・[検証手順](runner/VALIDATION.md) |
| ブラウザを共通runnerへ接続する | [ブラウザ測定アダプター](browser-wasm/benchmarks/README.md) |
| 学習済み重みを取得する | [モデルと利用条件](models/README.md) |

配布物は [Releases](https://github.com/wand125/othello-retro/releases) から取得できます。ブラウザ静的版は [v0.3.0](https://github.com/wand125/othello-retro/releases/tag/v0.3.0)、変換済みONNX重みは [browser-models-v1](https://github.com/wand125/othello-retro/releases/tag/browser-models-v1) にあります。ビルド時の取得・ハッシュ照合は各手順に記載しています。

## 結果と資料

- [文書一覧](docs/README.md)：探索手法、測定設計、使用ソルバー、公開範囲。
- [ベンチマークのデータ一覧](benchmarks/README.md)：固定bank・正式結果・予備試験の所在。
- [native 4環境の正式測定結果](docs/benchmarks/results.md)
- [ブラウザ正式測定の条件と開始記録](docs/benchmarks/browser.md)・[先行40盤面の結果](browser-wasm/benchmarks/browser-pilot-40-20261026/README.md)
- [native軽量Autoの診断](docs/algorithms/auto-diagnosis.md)

ブラウザ版はnative版と実装・起動条件が異なります。PCの測定値からスマホの1分以内を保証するものではありません。実機は上記の端末測定ページで別に確認します。

## 配置

| ディレクトリ | 内容 |
|---|---|
| `browser-wasm/` | ブラウザアプリ、WASMビルド、ONNX変換、ブラウザ測定 |
| `solver/` | Rust/Pythonの復元器、学習・探索、サーバーUI |
| `runner/` | 固定bankを使う共通の実行・独立検証・集計・公開用export |
| `benchmarks/` | 固定入力、条件、公開済みの測定結果 |
| `docs/` | 日英の説明文書と過去の公開・測定記録 |
| `models/`・`licenses/` | モデルカード、配布物の識別情報、利用条件 |
| `short/` | サーバー版の縦長UI |
| `paper-data/`・`records/` | 論文の補足データ、作成された棋譜 |

## ライセンス

自作コードは[MIT](LICENSE)、重み・自作論文の本文と図は[CC BY 4.0](licenses/CC-BY-4.0.txt)です。第三者runtime等はそれぞれの通知を保持します。[適用範囲](LICENSE_SCOPE.md)・[ベンチマークデータの条件](BENCHMARK_LICENSE.md)を参照してください。
