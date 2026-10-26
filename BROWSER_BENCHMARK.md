# ブラウザ版の正式ベンチマーク

[日本語](BROWSER_BENCHMARK.md) | [English](BROWSER_BENCHMARK.en.md)

M4 Pro上の実Chromeを、既存のnative4環境とは別の実装・実行環境として追加しました。2026年10月26日に測定を開始しています。[固定した条件・開始記録](browser-wasm/benchmarks/formal-study-plan.json)と[再実行手順](browser-wasm/benchmarks/README.md)を公開しています。

| 入力 | 独立盤面数 | 反復 | 方式 | 全試行数 |
|---|---:|---:|---|---:|
| 終局 | 20 | 各3回 | SAT / Auto | 120 |
| 途中 | 400 | 各3回 | SAT / Auto | 2,400 |

既存bankの盤面・棋譜・予定表は変更していません。終局、途中の順に一つずつ実行し、試行全体と最後の一般SATには時間上限を設けません。合法な棋譜をJavaScriptと共通runnerのPythonで独立に再生します。各bankが完了し、再検証・公開用exportの検査に合格してから結果を公開します。

ブラウザ起動を準備として除き、各試行の新Worker・WASM・必要なモデルの読込を含めます。nativeのモデル準備後の測定とは起動境界や探索方針が異なるため、値を純粋なハードウェア差とは扱いません。ブラウザ版はCPU/FP32・推論1スレッドです。

完了結果は`benchmarks/m4-browser-wasm-v3-runtime-20261026.json`と、同じフォルダの`m4-browser-wasm-v3-endgame-main-20261026/`・`m4-browser-wasm-v3-midgame-main-20261026/`へ追加します。この文書と開始記録は、逐次更新する進捗カウンターではありません。

[先行40盤面試験](browser-wasm/benchmarks/browser-pilot-40-20261026/README.md)は各版1回の予備試験で、正式試験へ混ぜません。最終版は40/40件の合法棋譜を返し、平均9.29秒、最長44.34秒でした。スマホ実機は[端末内の測定ページ](https://wand125.github.io/othello-retro/benchmark.html)で別に測れます。PCの値からスマホの1分以内を保証しません。
