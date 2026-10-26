# 論文の補足データ

[日本語](README.md) | [English](README.en.md)

[論文（日本語）](https://othello-retro.logicpuzzle.app/paper?lang=ja)・[English](https://othello-retro.logicpuzzle.app/paper?lang=en)の図の入力、盤面・棋譜、検証用ファイルです。11段の逆算例は本文にも掲載しています。説明は本文を参照してください。

| ファイル | 内容 |
|---|---|
| [article-data.json (JSON)](article-data.json) | 論文が読み込む図のJSONと同一。7局の棋譜、浅い逆算候補、パスの例、11段の逆算鎖 |
| [deep-reverse-chain.json (JSON)](deep-reverse-chain.json) | 61石→50石の12局面・11辺、次手番、一般SATの記録と主張範囲 |
| [deep-root-general.cnf.gz](deep-root-general.cnf.gz) | 起点61石の一般形CNF（gzip圧縮） |
| [deep-root-general-solver.log](deep-root-general-solver.log) | 既存のKissat UNSAT出力。利用者のアクセスログではありません |
| [check_deep_reverse_chain.py](check_deep_reverse_chain.py) | 標準ライブラリだけの独立配列ルール検証。CNF・ログのhashも照合可能 |
| [test_deep_reverse_chain.py](test_deep_reverse_chain.py) | 違法手、偽パス、手番・主張範囲の改竄などの拒否テスト |
| [forced-pass-reference.json (JSON)](forced-pass-reference.json) | 明示／省略した強制パスの検証用棋譜 |
| [deep-reverse-chain-report.json (JSON)](deep-reverse-chain-report.json) | 独立再生・必要条件・既存CNF／ログ照合の結果 |
| [adversarial-check-report.json (JSON)](adversarial-check-report.json) | 改竄拒否・強制パス・初期配置条件のテスト結果 |
| [manifest.json (JSON)](manifest.json) | このディレクトリの各ファイルと、対応する論文4アセットのSHA-256・検証範囲 |

## 検証を再実行

リポジトリのルートで実行します。Python標準ライブラリとgzipを使い、SATソルバーや学習モデルは起動しません。出力は一時ディレクトリへ置き、保存済みデータを上書きしません。

```sh
check_dir="$(mktemp -d)"
gzip -dc paper-data/deep-root-general.cnf.gz > "$check_dir/deep-root-general.cnf"
python3 -B paper-data/check_deep_reverse_chain.py \
  --input paper-data/deep-reverse-chain.json \
  --cnf "$check_dir/deep-root-general.cnf" \
  --solver-output paper-data/deep-root-general-solver.log
python3 -B paper-data/test_deep_reverse_chain.py \
  --input paper-data/deep-reverse-chain.json \
  --pass-example paper-data/forced-pass-reference.json \
  --output "$check_dir/adversarial-check-report.json"
```

checkerは11辺の合法性、強制パスと次手番、12局面の記載した必要条件、参照棋譜、既存ファイルのhashを検査します。**UNSATの再計算、CNF符号化の意味論的証明、DRAT検証は行いません。** 61石起点には一般形・次手番非指定のUNSAT記録がありますが、DRATは未生成・未検査です。下流の不能性はその記録を前提に指定手番付き状態に限定し、別手番の盤面単独、全分岐の生存深さ、最小必要深さは主張しません。

検証スクリプトは[MIT](../LICENSE)。データ・自作補足分析等の条件は[LICENSE_SCOPE.md](../LICENSE_SCOPE.md)を参照してください。性能測定のbank・予定表・実測値は[`benchmarks/`](../MEASUREMENT_DESIGN.md)、復元器ソースと重みは[Release v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0)で別に管理します。
