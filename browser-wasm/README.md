# Othello Retro — ブラウザSAT版

盤面から標準初期配置につながる合法棋譜を、ブラウザ内のRust製CNF生成器とKissat 4.0.3 WebAssemblyで探索します。配布物は純静的ファイルです。計算サーバーと学習モデルを使わず、SATだけを実行します。元のnative版やautoの比較試験は別の実装・測定です。

入力・再生・シーク・音声・盤面変換と、作成した棋譜のブラウザ内保存、JSON入出力を提供します。ローカルに作成した棋譜はそのブラウザに保存され、公開共有にはJSONの持ち出しなどが必要です。静的配布に含めた既存棋譜は一覧と個別URLから閲覧できます。

`found` は独立したJavaScriptのルール実装で黒先手・合法配置・反転・強制パスと目標64セルを再検証します。`unreachable` は必要条件による排除またはパスを許す一般SATのUNSATからだけ返します。制限付きno-passのUNSATを一般の到達不能とは扱いません。取消し・資源不足・エラーは到達不能ではありません。DRAT証明書の独立検査は行いません。

探索はWorker内で行います。取消しはWorkerの終了によって処理します。端末によっては計算やメモリが多く必要です。モバイルでの探索時間・メモリ性能は未測定で、nativeベンチマークの値からブラウザの速度を保証しません。

## ビルド

Rust 1.98.0、`wasm32-unknown-unknown` target、Emscripten、Python 3、Node.jsを用意します。リポジトリルートから実行します。

```sh
cargo +1.98.0 build --manifest-path browser-wasm/engine/Cargo.toml --target wasm32-unknown-unknown --release --locked -j2
cp browser-wasm/engine/target/wasm32-unknown-unknown/release/othello_retro_browser_encoder.wasm browser-wasm/ui/encoder.wasm
EMCC="$(command -v emcc)" EM_CACHE=/tmp/othello-emcache python3 browser-wasm/solver/build.py
```

Emscriptenのcacheは利用できるSDK cacheを用意してください。Kissatの元ソース、wasm32向けの小修正、使用flags・ハッシュ・通知は [solver/README.md](solver/README.md) と同ディレクトリのmanifestに記録します。

## 検証と静的配布

```sh
node --test browser-wasm/tests/test-verify.cjs
node browser-wasm/solver/smoke.cjs
python3 browser-wasm/build_static.py --public-repo /path/to/othello-retro --records /path/to/public-records-snapshot.json --output /tmp/othello-static-new
python3 -m http.server 8000 --directory /tmp/othello-static-new
```

`--public-repo` は既存論文4ファイルを含む公開リポジトリ、`--output` はまだ存在しない新しいディレクトリです。ビルダーは自動デプロイしません。`--records` は `{ "examples": [...] }` 形式の公開棋譜snapshotです。指定した全棋譜を独立再生し、安全なIDと公開用フィールドだけを配布します。省略時はUI同梱の棋譜を使用します。72件のsnapshotを指定すれば、同梱7件よりこちらが優先されます。

生成物の `/paper/` は既存論文の本文・CSS・数式・日英切替を保持し、リンクとasset参照だけを相対化します。`paper.html` と `examples/`・各棋譜URLに静的redirectを用意し、queryとhashを引き継ぎます。独自ドメインとGitHub Pagesのproject subpathの両方で利用できます。`asset-manifest.json` は配布物のversionとハッシュを記録し、Service Workerは最初の取得が成功したassetをオフライン用に保存します。初回からのオフライン利用やブラウザによる保存領域の維持は保証しません。

ブラウザsmokeには別途PlaywrightとChromiumが必要です。配布先を起動してから `OTHELLO_PREVIEW_URL=http://127.0.0.1:8000/ node browser-wasm/tests/browser-smoke.cjs` を実行します。この試験の観測用deadlineは、探索結果としての到達不能判定には使いません。`tests/cases.json` の深い61石不能例は任意のstress fixtureで、通常smokeには含めません。

## ライセンス

自作のRust・JavaScript・ビルド／検証スクリプトはMITです。Kissatは著作者のMIT通知を維持します。Rust標準ライブラリはMIT OR Apache-2.0等の適用通知、Emscripten・musl・compiler-rt等はそれぞれの通知を確認してください。生成したWebAssembly全体を自作コードだけとみなして通知を省略しません。Kissat側の通知は `ui/kissat.LICENSES.txt` と `solver/licenses/` にあります。元論文の本文・図は既存のCC BY 4.0方針を引き継ぎます。詳細は公開リポジトリの `LICENSE_SCOPE.md` を参照してください。


### 受入れfixtureの条件

`tests/cases.json`の14件はcaseごとに`license`・`attribution`・元JSONの位置と出典ハッシュを持ちます。既存bank・自作例由来12件はMIT、論文由来の`paper-two-placement-unreachable`と`paper-deep-root-61`の2件は既存のCC BY 4.0方針を維持します。著作者は **wand125**、出典は[論文](https://othello-retro.logicpuzzle.app/paper)と各caseの`source_data`です。fixture形式へ抽出し検証メタデータを追加した変更を記録し、盤面・参照棋譜は変更していません。[fixture条件](tests/LICENSE.md)と[CC BY 4.0本文](tests/licenses/CC-BY-4.0.txt)を同梱します。検証コードはMIT、第三者runtimeの通知は別です。
