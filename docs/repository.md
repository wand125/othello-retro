# 配置と記録の扱い

[日本語](repository.md) | [English](repository.en.md)

`browser-wasm/`、`solver/`、`short/` はそれぞれ静的ブラウザ版、native復元器、サーバー向け縦長UIです。利用とビルドの手順は各ディレクトリにあります。共通の測定・検証コードは `runner/`、方式や結果の説明は `docs/` に置きます。

## 固定したデータとソース

`benchmarks/` の既存bank・予定表・rawと、検証manifestを持つ実験snapshotは、参照先のパスとバイトを保ちます。新しい測定は別の名前の結果ディレクトリへ追加し、[共通runnerの検証・export](../runner/VALIDATION.md)を通します。過去の結果に現在のコードを使ったという意味を与えないよう、測定時のソースhashも保持します。

`browser-wasm/engine/native/` はWASM生成に用いる固定snapshotです。`solver/history/` は古い配布の検証記録です。これらを現行ソースや現行テスト結果と混ぜず、更新する場合は由来と新しい検証を明示します。ブラウザ用モデル変換は `browser-wasm/model-tools/` にあります。

Releaseの添付ファイルとtagは過去の配布物です。現在のGit管理ファイルはルートの `RELEASE_FILES.json` が列挙します。文書を動かす場合も、各実験のmanifestを現在の配置に合わせて書き換えません。

## 私用出力と配布物

実行中の出力は `.runs/` 等、利用者の設定は `*.local.json` へ置きます。認証情報、利用ログ、ブラウザ識別子、私有インフラ設定は公開物へ含めません。重みの `.pt` と変換した `.onnx` はReleaseの配布物で、Gitには識別情報と利用条件を置きます。

第三者runtimeと通知は実装と一緒に保持します。適用範囲は [LICENSE_SCOPE.md](../LICENSE_SCOPE.md) にまとめています。
