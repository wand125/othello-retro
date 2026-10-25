# 使用ソルバーと依存関係

[日本語](SOLVERS.md) | [English](SOLVERS.en.md)

## 公開測定ツールと元の復元器

公開済みの `runner/` はPython 3.10以降の標準ライブラリだけを使う汎用測定ツールで、SATソルバーや学習モデルを含みません。自分の外部復元プログラムを接続できます。接続仕様は [日本語](runner/README.md) / [English](runner/README.en.md) を参照してください。

復元器のRust/Pythonソース、UI・サーバーと凍結測定harnessは[`solver/`](solver/README.md)、縦長UIは`short/`に公開しています。学習済み重みは[試験公開Release v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0)の添付ファイルです。公開runnerの標準ライブラリ依存と、復元器のRust・ML・動画関連依存を区別します。

## 別のブラウザSAT版

[`browser-wasm/`](browser-wasm/README.md)にはRust製CNF encoderとKissat 4.0.3のcompiled WASM、再ビルド用ソース、通知を収録します。学習モデル・Python・計算サーバーを使わず、単一Worker内でSATを実行します。短いパスなしSAT probeで見つからなければ、パスを許す一般形へ進みます。限定probeのUNSATだけで一般到達不能とは判定せず、必要条件違反または一般形UNSATだけを到達不能とします。`found`は独立JavaScriptで合法再生します。

自作コードMITと、Kissat・Rust標準ライブラリ・Emscripten等のバイナリ通知は別に保持します。受入れfixtureのbank由来MITと論文由来2件のCC BY 4.0は[fixture条件](browser-wasm/tests/LICENSE.md)へ明示しています。元の4環境native測定をブラウザの性能値とは扱わず、モバイル性能は未測定です。

## 現在のnative軽量auto

現在の`solver/`は候補幅16・対称数1・refine0の単段policyとCPU Conv–BN融合／channels-lastをopt-inで選べます。未満盤終局は一般SATへ直行し、返却witnessを厳密再生します。WSLでは適用済みです。[32盤面診断](AUTO_DIAGNOSIS.md)は元400／20例とは別集計で、同じcheckpointを使い、新規学習は行いません。`RETRO_AUTO_POLICY=baseline RETRO_INFERENCE_OPT=baseline`は従来のPython policyを選びますが、native逆算修正は戻しません。元の測定sourceはv0.1.0／commit`32e472e`で再現し、凍結bankは変更しません。ビルド検証は現在11native＋17Pythonテスト、旧9nativeは歴史記録です。

## 元プログラムの復元の流れ

1. 石数、初期配置の中央4マスなどの必要条件を調べる。
2. 少ない石数では短時間の直接探索を試す。
3. SAT系では合法な着手・反転・強制パスと目標盤面を制約へ変換する。パスなし、後半のみパスあり、一般形の3種類を並列に探索する。
4. 自動方式では石数の多い盤面に学習モデルによる逆向きビーム探索も用いる。候補が見つからなければ元の盤面からSAT系へ戻す。
5. 見つかった棋譜は標準初期配置から独立したルール実装で順方向に再生し、合法性と全64マスの目標一致を検証する。

限定したパス条件のUNSATや学習誘導探索の失敗だけでは到達不能とは判定しません。時間制限を使う運用で制限時間が切れた場合は `unknown` です。SAT系の `found` も、モデルを棋譜へ変換した後に再生検証します。一般形の充足不能、または不変条件違反だけを到達不能とする設計です。これは証明トレースの第三者検証を公開したという意味ではありません。

正式な無制限ベンチマークでは試行全体と最後の一般SATの時間上限を外し、最終Kissat呼出しにも `--time` を渡しません。内部の短いprobeや候補SATの予算は探索方針として残ります。3種類のSATポートフォリオに対し、共通ベンチマーク用gateで同時実行する実Kissatを最大2本に制御し、待機・起動時間も計時します。公開サービスの既定設定とは別条件です。詳細は[測定設計](MEASUREMENT_DESIGN.md)を参照してください。

## 元プログラムのソルバー

| ソフトウェア | 使用バージョン | 役割 | ライセンス確認状況 |
|---|---|---|---|
| [Kissat](https://github.com/arminbiere/kissat/tree/rel-4.0.3) | 4.0.3 | 外部SATソルバー、並列ポートフォリオ | 当該タグの[MIT LICENSE](https://github.com/arminbiere/kissat/blob/rel-4.0.3/LICENSE)を確認 |
| [CaDiCaL Rust binding](https://github.com/mmaroti/cadical-rs) | crate cadical 0.1.16 | RustからのSAT呼出し | crateのMIT表記を確認 |
| [CaDiCaL](https://github.com/arminbiere/cadical) | 上記crate同梱1.9.5 | 組込みSATソルバー | 同梱VERSIONとMITライセンスを確認 |
| [PyTorch](https://github.com/pytorch/pytorch) | 4環境比較2.2.2 / 本番参考2.6.0 CPU | 自前学習モデルの推論 | BSD-3-Clauseと上流第三者通知。ソース配布へ通知を添付し、wheel本体は同梱しない |

復元探索本体と制約生成は独自のRust/Python実装です。学習モデルは逆向き候補の順位付けに使い、到達可能性の証明を代替しません。元の対局の歴史を一意に特定するモデルでもありません。

学習・コピー記録の対応では、主 `model.pt` は混合38,504行、`model_passes.pt` はパスなし25,796行由来の旧モデルを退避したものです。後者の名前はパス専用の訓練を意味しません。原訓練データは現物不在で、重み固有の評価精度・完全な再学習再現は未確認です。重みはCC BY 4.0・著作者wand125としてReleaseへ配布し、詳細は[モデルカード](models/MODEL_CARD.ja.md)に記録しています。教師にはパスなし／直前12手のみパス可という限定条件と、未解決を正例として学習する方針があり、一般到達可能性の精度とは区別します。

## 配布条件と外部依存

自作ソースは[MIT](LICENSE)、既存二つの合成bankは従来の[MIT範囲](BENCHMARK_LICENSE.md)です。重み・モデルカード、自作論文本文・自作図には[CC BY 4.0](licenses/CC-BY-4.0.txt)を適用します。第三者のソルバー・ライブラリ・引用はそれぞれの条件を保持します。[LICENSE_SCOPE.md](LICENSE_SCOPE.md)へ対象を分けて明示しています。

[`solver/THIRD_PARTY_NOTICES.md`](solver/THIRD_PARTY_NOTICES.md)にRust依存9件とソルバー通知を、[`solver/PYTHON_DEPENDENCIES.md`](solver/PYTHON_DEPENDENCIES.md)にPythonの版・通知・requirementsの根拠を記載しています。r-efi6.0.0のMIT本文と著作権表示はAUTHORSから保持しました。Cargo.toml/lockは不変です。旧測定のRust・主要推論source hashは歴史記録へ保持し、現在の軽量版sourceとは区別します。補助bench_fix.pyの広域pkill除去は配布差分として記録しています。

ビルドはRust1.98.0とC++17、Kissatは別途4.0.3を用意します。v0.1.0はlocked release build・9単体テスト・有限／無制限SATを確認した歴史記録です。現在の変更には別の11native＋17Python検証を記録しています。実行手順は[本体README](solver/README.md)、重みの取得・来歴は[モデルカード](models/MODEL_CARD.ja.md)を参照してください。

native版Release v0.1.0のソース配布には依存の実行バイナリ・Python wheel・WASM・コンテナを同梱しません。別のブラウザ版には上記のcompiled WASMと対応通知を含めます。元訓練JSONLは現物がなく配布しません。teacherの限定条件、未知ラベルを正例にする学習処理、最終重みのholdout精度と完全再学習の未確認は、コード公開によって解消したとは扱いません。動画依存などを含むバイナリを別に配布する場合は、その実際の同梱物の通知確認が必要です。[公開範囲](CODE_PUBLICATION.md)を参照してください。
