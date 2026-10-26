# ブラウザ版を共通runnerで測定する

`adapter.py` は実Chrome/Chromiumで静的ブラウザ版を動かすresident JSONLアダプターです。SATと軽量Autoを選べます。Python 3.10以降、Python Playwright、Chrome/Chromium、およびモデルを含む完全な静的snapshotが必要です。依存の自動インストールや外部サービスへの接続は行いません。

測定前にsnapshotを別ディレクトリへ固定してください。例の `browser-programs.json` はリポジトリ直下を作業ディレクトリにし、`browser-wasm/ui` を読みます。本測定では両programの `--ui-dir` と13個の `artifacts[].path` を同じ固定snapshotへ置き換え、設定ファイルの `cwd` も配置先に合わせます。`python3` はPlaywrightが使える実行環境に置き換えられます。Chromeを明示する場合は各commandへ `--chrome PATH` を追加してください。モデルの入手・静的ビルドは [ブラウザ版README](../README.md) を参照してください。

```sh
python3 runner/benchmark.py run \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --config browser-wasm/benchmarks/browser-programs.json \
  --split pilot --output .runs/browser-pilot

# pilotを確認後、mainは固定された400盤面・各法3反復。
# 終局20盤面は別outputで、対応するendgame bankのmainを測定する。
python3 runner/benchmark.py run \
  --bank benchmarks/study-endgame-cpu222-unbounded-v1.json \
  --config browser-wasm/benchmarks/browser-programs.json \
  --split main --output .runs/browser-endgame
```

順序・反復・再開・結果のPython独立再生は共通 [runner](../../runner/README.md) が管理します。再開は同じコマンドとoutputへ `--resume` を追加します。未完の試行を成功時間や到達不能として扱わないでください。40盤面・観測上限付きの `run_browser.py` とは別の測定です。その既存コードや結果は変更しません。

## 時計と隔離

Chrome、loopback静的サーバー、空の検証ページの準備後に `ready` を返します。各要求は新しいWorkerを作り、WASMと必要なモデルの読み込み・初期化を試行へ含めます。HTTPキャッシュ、Service Worker、履歴、保存済み解は使いません。元のnative residentモデル温存測定とは異なる条件なので、residentというラベルだけで時間を混ぜないでください。`stats.timing_profile` は `fresh-worker-cold-wasm-models-browser-ready-v1` です。共通runnerの時間にはブラウザ外とのJSONL通信とメインページでの追加JS検証も含みます。`stats.proof_receipt_seconds` はWorker応答受領までの補助時計です。

時間上限を設けません。内部の制限付き候補探索が失敗しても、完全な一般SATへ戻ります。到達不能は一般式の確定UNSATだけです。エラーは `error` としてrunnerを止め、打切りをUNSATにしません。Ctrl-C/SIGTERMでアダプターは自身のブラウザとサーバーを終了し、runnerも自身のプロセス群を片付けます。

WorkerはCPU/WASM、推論FP32・1 threadで、GPUを使いません。新しいブラウザcontextを使い、同じloopback originにある許可された13資産へのGETのみ許可します。WebSocket、CDN、APIへのアクセスは拒否します。読み込む13資産すべてのSHA-256と実Chromeバージョンをreadyと各結果のstatsへ記録します。モデル・コードの配布条件はブラウザ版READMEと同梱通知に従います。

```json
{"event":"ready","stats":{"timing_profile":"fresh-worker-cold-wasm-models-browser-ready-v1"}}
```

stdinの各行は `{"id":"trial-1","board":"64文字のX/O/-"}`、stdoutは `{"event":"result","id":"trial-1","payload":{"status":"found","moves":["d3"],"stats":{}}}` の形式です。`found` はWorker、検証ページ、共通runnerで独立に再生します。`unreachable` には棋譜がありません。stdoutにはJSONLだけを出します。

## 小さい受入れテスト

```sh
python3 -m unittest discover -s browser-wasm/benchmarks -p test_adapter.py -v
RETRO_BROWSER_TEST_UI=/path/to/immutable-snapshot \
  python3 -m unittest discover -s browser-wasm/benchmarks -p test_adapter.py -v
```

後者はSAT/Auto各々で5石・12石の実探索、即時不能、不正入力と終了処理を確認します。テスト監督用の45秒待ち上限はアダプターの探索上限ではありません。400/20盤面の本測定やスマートフォン性能の保証ではありません。

コードとテストはMIT。参照盤面の出典・ライセンスは `../tests/cases.json` にあります。
