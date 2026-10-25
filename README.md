# Othello Retro — テストケース・測定ツール・結果

[日本語](README.md) | [English](README.en.md)

オセロの盤面から、標準初期配置を出発点とする合法な棋譜を一つ復元する実験です。元の対局の特定や、最善手の計算を目的としていません。

- [試験公開アプリ](https://othello-retro.logicpuzzle.app/) / [作成された棋譜](https://othello-retro.logicpuzzle.app/examples)
- インタラクティブ論文: [日本語](https://othello-retro.logicpuzzle.app/paper?lang=ja) / [English](https://othello-retro.logicpuzzle.app/paper?lang=en)

このリポジトリでは、テスト盤面・参照棋譜・実測結果・使用ソルバー情報に加え、**別環境・別プログラムを同じ固定bankへ接続する測定ツール**を公開しています。測定ツールはPython 3.10以降の標準ライブラリだけで動作します（Linux・macOS・WSL）。自分の外部プログラムをJSONで接続してください。

元の復元器本体、実行ファイル、学習済みモデルは未配布です。したがって、このリポジトリだけから元の復元プログラムを再現・実行することはできません。接続確認用fixtureは参照解の検索だけを行い、復元性能を測るものではありません。

## 測定ツールと資料

| 内容 | 日本語 | English |
|---|---|---|
| 外部プログラムの接続・実行・解析・公開用export | [runner利用手順](runner/README.md) | [Runner guide](runner/README.en.md) |
| 生成規則・棋譜・ログ・集計・公開ファイルの検証 | [検証手順](runner/VALIDATION.md) | [Validation guide](runner/VALIDATION.en.md) |
| 正式測定の完了状況・結果 | [測定結果](BENCHMARK_RESULTS.md) | [Results](BENCHMARK_RESULTS.en.md) |
| 標本・反復・計時・統計の設計 | [測定設計](MEASUREMENT_DESIGN.md) | [Measurement design](MEASUREMENT_DESIGN.en.md) |
| 使用ソルバーと依存関係 | [ソルバー情報](SOLVERS.md) | [Solvers](SOLVERS.en.md) |
| コードの公開範囲と残る確認 | [公開状況](CODE_PUBLICATION.md) | [Publication status](CODE_PUBLICATION.en.md) |

正式bankは、途中400盤面と終局20盤面を別々に、`sat` / `auto` 各3回の固定予定表で測定します。両方式なら途中2,400試行、終局120試行です。元プログラムの4環境比較はM4・M1・WSL・Intelを対象に、同じ盤面・予定表・モデル・探索コード、CPU/FP32、推論2スレッド、Torch2.2.2/NumPy1.26.4を使う設計です。試行全体と最後の一般SATには時間上限を設けません。完了状況と実際の条件は結果資料を参照してください。

外部プログラムは元のモデル・探索実装に合わせる必要はありません。固定入力と予定表を維持し、自分の実装・環境・内部制限・計時modeを記録します。oneshotの起動込み時間とresidentの準備後時間を同じ条件として比較しません。bank内の元プログラムのソース・モデルhashと、外部プログラム自身の記録は区別します。

[固定8盤面・各3回の比較](COMPARISON_3X.md)と[その条件](benchmarks/protocol-3x.json)は、Torch2.6/NumPy2.2.6・各60秒の予備実験です。正式な無制限測定へ混ぜません。モデル読込込みと読込後を分け、未解決数を記録しています。以前の各1回の比較は取り下げました。初回Mac測定は実際の推論デバイスを記録しておらず、MPS実測としては扱いません。

## 公開データ

- [途中400盤面とpilot10盤面](benchmarks/study-midgame-cpu222-unbounded-v1.json)
- [終局20盤面](benchmarks/study-endgame-cpu222-unbounded-v1.json)
- [固定8ケース](benchmarks/cases.json): 到達可能7例、到達不能1例。
- [作成された棋譜7例](records/created-games.json): 合法性と到達盤面を独立に再生検証しています。付属する計算時間はその作成時の記録で、環境間の性能比較用ではありません。
- [論文の補足データ](paper-data/README.md): 本文の説明・図で使う盤面、棋譜、検証条件。

盤面はa1からh8まで行優先の64文字です。`X`=黒、`O`=白、`-`=空。棋譜の座標も同じ向きで、`pass` は合法手がない側の強制パスです。参照棋譜は到達可能性の証拠であり、唯一解を意味しません。固定8ケースの到達不能例は初期配置の中央4マスの一つが空で、石が除去されないという不変条件に違反します。

固定8ケースのSHA-256: `292d782cdd23d794e33bc829286a9c0dd4d11979e1db06b27bbf362b0d1a8d64`

## 利用条件と公開範囲

新規測定ツール `runner/` と、上記の途中・終局の二つの合成bankは[MITライセンス](BENCHMARK_LICENSE.md)で利用・改変・再配布できます。詳しい対象範囲と通知義務は同文書と [runner/LICENSE](runner/LICENSE) を参照してください。この許諾は、論文本文や未配布の復元器・モデルなどへ一括してライセンスを付与するものではありません。

試験公開アプリでは、新規に作成する盤面・棋譜・計算時間などを取得・保存し、作成された棋譜として公開します。過去の利用ジョブを一括公開することはしません。

利用記録、ブラウザ識別子、認証情報、私有インフラ設定は公開物へ含めません。測定ツールの私用出力は `.runs/`、利用者設定は `*.local.json` へ置き、公開時はrunnerのexportで別ディレクトリへ出力してください。元の復元器・モデルと第三者依存の配布条件の確認は継続しています。
