# コード・重み・論文の公開範囲

[日本語](CODE_PUBLICATION.md) | [English](CODE_PUBLICATION.en.md)

[最初の試験公開Release v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0)としてソースと既存重みを公開しています。

| 対象 | 配置・取得先 | 利用条件 |
|---|---|---|
| Rust CLI、Python探索・学習、UI・サーバー、凍結測定harness | [`solver/`](solver/README.md) | 自作コードMIT、第三者は個別通知 |
| ブラウザSAT版・静的配布 | [`browser-wasm/`](browser-wasm/README.md) | 自作コードMIT、compiled WASMの第三者通知とfixture別条件を保持 |
| 縦長UI | [`short/`](short/README.md) | 自作コードMIT |
| 汎用測定・独立検証・解析・export | [`runner/`](runner/README.md) | MIT |
| 既存の途中・終局二つの合成bank | [`benchmarks/`](BENCHMARK_LICENSE.md) | 従来のMIT、内容・hash不変 |
| `model.pt`・`model_passes.pt` | Release添付。Gitには含めない | CC BY 4.0、著作者wand125 |
| モデルの説明・ライセンス・識別情報 | [`models/`](models/MODEL_CARD.ja.md) | CC BY 4.0 |
| 自作論文本文・自作図・自作補足分析 | [論文](https://othello-retro.logicpuzzle.app/paper)・`paper-data/` | CC BY 4.0 |

正確な適用範囲は[LICENSE_SCOPE.md](LICENSE_SCOPE.md)、[MIT](LICENSE)、[CC BY 4.0本文](licenses/CC-BY-4.0.txt)を参照してください。機能コードと論文本文、第三者の引用・素材を一括して同じ許諾へ変更しません。

## native版Release v0.1.0の添付ファイル

- [source.tar.gz](https://github.com/wand125/othello-retro/releases/download/v0.1.0/source.tar.gz): 配布ソース。実行バイナリや依存バイナリは含みません。
- [models.tar.gz](https://github.com/wand125/othello-retro/releases/download/v0.1.0/models.tar.gz): 既存の二つの重み、モデルカード、ライセンスと識別情報。
- [model.pt](https://github.com/wand125/othello-retro/releases/download/v0.1.0/model.pt)・[model_passes.pt](https://github.com/wand125/othello-retro/releases/download/v0.1.0/model_passes.pt): 個別取得用。
- [CC-BY-4.0.txt](https://github.com/wand125/othello-retro/releases/download/v0.1.0/CC-BY-4.0.txt)・[SHA256SUMS](https://github.com/wand125/othello-retro/releases/download/v0.1.0/SHA256SUMS)。

重みは`solver/ml/`へ置き、取得したファイルのhashを照合します。[ビルドと実行](solver/README.md)を参照してください。`solver/ml/bench_fix.py`では他のSATプロセスも止め得る広域pkillを除き、配布時の差分として記録しています。Cargo・Rust・主要推論ソースの凍結hashは保持しています。


`SHA256SUMS`は個別の二つの重み用です。モデル用archive内にも同じ一覧があります。[RELEASE_SHA256SUMS](https://github.com/wand125/othello-retro/releases/download/v0.1.0/RELEASE_SHA256SUMS)は全添付ファイル用です。[LICENSE-WEIGHTS.md](https://github.com/wand125/othello-retro/releases/download/v0.1.0/LICENSE-WEIGHTS.md)も同梱します。

## 同梱・検証の範囲

native版v0.1.0ではRustのロック依存9件と、CaDiCaL1.9.5・Kissat4.0.3の通知を[`solver/THIRD_PARTY_NOTICES.md`](solver/THIRD_PARTY_NOTICES.md)へ整理しました。このnativeソース配布の外部依存実装・バイナリは取得側で用意します。`cadical0.1.16`はビルド時にCaDiCaLを取得crateからコンパイルし、Kissatは別プロセスです。r-efi6.0.0のMIT本文と著作権表示は`AUTHORS`から保持しています。

同一RustソースでRust1.98.0 locked release build、Kissat4.0.3付き全9単体テスト、有限・無制限SATのsmokeと棋譜の独立再生を確認しています。Python依存は推論用と学習比較用のrequirementsに分け、版の根拠と第三者通知を[`solver/PYTHON_DEPENDENCIES.md`](solver/PYTHON_DEPENDENCIES.md)へ記録しています。既存ベンチマークの条件・値・rawは変更していません。

## 別配布のブラウザSAT版

[`browser-wasm/`](browser-wasm/README.md)は計算サーバー・学習モデルを使わない純静的版です。Rust製CNF encoderとKissat 4.0.3のコンパイル済みWASM、再ビルド用ソース、ビルド記録、ライセンス・runtime通知を収録します。Kissat・Rust標準ライブラリ・Emscripten等の条件は自作コードMITと区別し、`ui/kissat.LICENSES.txt`・`ui/RUST-LICENSES.txt`と参照先を保持します。

受入れfixture14件のうち、既存bank・自作例由来の12件はMIT、論文由来の2件は既存のCC BY 4.0方針です。後者は著作者wand125・[論文](https://othello-retro.logicpuzzle.app/paper)・元データ・抽出による変更をcaseメタに記載します。[fixture条件](browser-wasm/tests/LICENSE.md)を参照してください。旧nativeベンチマークの条件・値・hashと論文本文はこのブラウザ配布で変更しません。

## 同梱しないもの・再現性の限界

原訓練JSONLは現物がなく、配布できません。公開bankは元訓練ファイルとは別です。記録に基づく来歴では主重みは混合38,504行、旧モデルを退避した`model_passes.pt`はパスなし25,796行で、名前はパス専用学習を意味しません。重み固有のholdout精度と完全な再学習再現は未確認です。詳細は[モデルカード](models/MODEL_CARD.ja.md)へ。

native版Release v0.1.0のソース配布には、コンパイル済み実行ファイル・WASM・配布コンテナ・外部ソルバー・Python wheel・動画ライブラリのバイナリを含みません。この除外は、上記の別配布ブラウザ版WASMには適用しません。配布するバイナリには実際の同梱物に応じた通知を保持します。認証情報、Cookie、利用ログ、私有インフラ設定、個人の動画・音声は公開物へ含めません。
