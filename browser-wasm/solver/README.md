# Kissat WebAssembly C API

Kissat 4.0.3 の公式release sourceの既存local copyを `vendor/kissat-4.0.3/` に保持しています。KissatはMIT（著作権表示は `KISSAT-LICENSE`）。本プロジェクトのadapter・build script・smoke testもMITです。Emscripten/musl/compiler-rt等のruntime通知は `licenses/` と配布用 `../ui/kissat.LICENSES.txt` に同梱しています。学習モデル、外部プロセス、サーバーは使用しません。

wasm32では元の `(size_t)1 << 32` が未定義になるため、`congruence.c` の上限定数のみ `uint64_t` に変更しています。`wasm32-portability.patch` と `source-origin.json` に元sourceのhash・差分を記録しました。32bitのsize_tは当該上限に到達できず比較が常にfalseというcompiler警告が残りますが、未定義shiftは解消されています。元archiveそのもののhash再検証を今回行ったという主張はしていません。

`python3 build.py` で `../ui/kissat.js` と `../ui/kissat.wasm` を生成します。Emscriptenの既存cacheを私用 `EM_CACHE` に用意してください。既定は `/private/tmp/othello-browser-wasm-emcache`、compilerは `EMCC` で指定できます。ホストのglobal cacheは変更しません。`node smoke.cjs` がSAT・UNSAT・空節・値取得・bulk投入・quiet動作を確認します。

classicJSのfactory名は `createKissat`。Workerでは `importScripts('kissat.js'); const k = await createKissat();`、Nodeでは `require('../ui/kissat.js')` で利用できます。同じディレクトリの `kissat.wasm` をロードします。

公開関数は `_kissat_init`, `_kissat_add`, `_kissat_add_buffer`, `_kissat_solve`, `_kissat_value`, `_kissat_release`, `_kissat_set_option`, `_kissat_get_option`, `_kissat_terminate`, `_kissat_reserve`, `_kissat_set_conflict_limit`, `_kissat_set_decision_limit`, `_kissat_version`, `_kissat_signature`, `_malloc`, `_free`。`_kissat_add_buffer(solver, ptr, length)` のlengthはint32要素数でありバイト数ではありません。signed DIMACS literalを `k.HEAP32` に置き、各節を0で区切ります。空節は0一つです。bufferは投入直後に解放できます。solveはSAT=10、UNSAT=20、未確定=0、valueは符号付きliteralを返します。

single-thread、`-O3`、quiet、stack 1MiB、初期memory 32MiB、growth許可、上限1GiBです。同期solve中に同じWorkerへmessageを送って `_kissat_terminate` を呼ぶことはできないため、UIからの強制取消しはWorker自体を終了してください。停止したSolverは再利用せず、新Workerを初期化します。

`build-manifest.json` にsource tree・compiler・flags・出力hash/sizeを、`smoke-result.json` に実行結果を記録します。既存native solverと本番サービスには変更を加えていません。
