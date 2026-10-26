# WSL：終盤12手にパスを限定したSAT診断

[English](README.en.md)

M4で60秒以内に解けなかった既知の終局3盤面を選んだ、事後の原因診断です。各設定1回で、一般的な成功率やスマホ性能を測る標本ではありません。モデル・CNN・LTOは使用していません。

| 盤面末尾ID | late12・通常設定 | SAT向け設定 |
|---|---:|---:|
| 200028 | 成功 9.868秒 | 未確定 19.115秒 |
| 200107 | 成功 7.821秒 | 成功 7.492秒 |
| 300185 | 成功 14.418秒 | 未確定 15.905秒 |

WSL2 / Ryzen 9 9950X / Node 24.19、nice19、guest CPU16–19、単一solver Workerを順次実行しました。通常設定はKissat4.0.3の既定、SAT向け設定は`target=2,restartint=50`です。両設定とも上限は100,000 conflicts / 1,000,000 decisions。これは秒数ではありません。未確定2件はKissatのwork-limitによる戻り値0であり、外側60秒watchdogには達していません。

成功4件は別実装で全手を再生し、64マスの目標一致を確認しました。制限付きCNFのUNSATや未確定から一般到達不能を結論してはいけません。公開アプリでは、見つからなければ一般SATへ継続する必要があります。WSLの秒数をM4・スマホの秒数として扱わないでください。

`results.jsonl`は実測6行をbyte exactで保持し、全棋譜・費用・未確定を含みます。`conditions.json`はホスト条件の公開用allowlistで、SSH・私有IP・ユーザーパス・サービス設定を含みません。元入力bankのhashは保持し、公開bankとのケース完全一致は`data-provenance.json`へ記録しました。`check_results.py`でraw hash・予定順・成功棋譜を独立検証できます。

```sh
python3 browser-wasm/benchmarks/wsl-late-probe-20261026/check_results.py
```

再実行にはRust1.98.0のwasm32 target、Python3、Node24と、既存`browser-wasm/ui`のKissat/verifyが必要です。ONNXやモデル取得は不要です。ここにはbinaryを重複収録していません。実測に使った実験encoderのwrapper・native5モジュールを`encoder-source/`に保持しており、現在のmain encoderへ置き換えずにビルドします。

```sh
rustup target add --toolchain 1.98.0 wasm32-unknown-unknown
python3 browser-wasm/benchmarks/wsl-late-probe-20261026/build_encoder.py --require-measured-hash
nice -n 19 taskset -c 16-19 node browser-wasm/benchmarks/wsl-late-probe-20261026/run.cjs --output /tmp/retro-late-new-run
```

`taskset`はLinuxの例です。他OSでは外し、実際の条件を記録してください。出力先は新規ディレクトリに限定しています。別compiler等でartifactが違う場合、無断で実測と同一扱いにはせず、明示的に`--allow-artifact-change`を指定した別測定とします。`RETRO_ENCODER_WASM`で別の互換encoderを指定できます。ソースのhash・実測harnessからのpath/出力guard変更は`source-provenance.json`、制約と試行順は`protocol.json`にあります。

`measured-engine.js`から使うのは盤面をbit列へ変換する`boardWords`だけで、同ファイル内の旧UI探索policyは実行しません。実際の式・上限は`plan.json`と`run.cjs`が指定します。公開stage時には新しい重い測定やcompiler再buildを行っておらず、再build一致は上のhash照合で明示的に確認してください。

コードは[MIT](../../../LICENSE)。合成ケースは[BENCHMARK_LICENSE.md](../../../BENCHMARK_LICENSE.md)、再利用する第三者WASMは[Kissat/runtime通知](../../ui/kissat.LICENSES.txt)、Rust runtimeは[既存通知](../../ui/RUST-LICENSES.txt)を参照してください。本資料はサーバー構成やバックエンドを配布するものではありません。
