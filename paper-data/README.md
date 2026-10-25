# 論文の補足データ

[論文（日本語）](https://othello-retro.logicpuzzle.app/paper?lang=ja)・[English](https://othello-retro.logicpuzzle.app/paper?lang=en)の根拠となる盤面、棋譜、図表の元データ、検証条件を、このディレクトリで公開します。分析の説明は論文本文にまとめます。

| ファイル | 内容 |
|---|---|
| [article-data.json](article-data.json) | 論文の図が読み込むデータと同一のJSON。復元棋譜、浅い逆算候補、11手の鎖、パスの例を収録 |
| [deep-reverse-chain.json](deep-reverse-chain.json) | 11手の逆算鎖と直前の経路、手番、独立再生検査、一般SATの設定・結果・CNFハッシュ |
| [manifest.json](manifest.json) | データと対応する論文アセットのSHA-256、検証範囲 |

各データには検証済みの範囲と未検証の範囲を残します。プログラム、モデル、CNF本体、個人の利用記録は、この補足データの公開に含めません。

性能測定の固定盤面・予定表・実測値は、[測定設計](../MEASUREMENT_DESIGN.md)と`benchmarks/`で別に管理します。
