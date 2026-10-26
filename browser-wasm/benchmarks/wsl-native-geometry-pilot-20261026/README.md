# WSL Node：native候補設定を移した予備試作

[English](README.en.md)

**正式ベンチマークや同等移植の結果ではありません。** 既知の3盤面を各1回、現行ブラウザAuto Aと、nativeの候補探索設定へ近づけた試作Bで比較しました。実行場所はWSL2 / Ryzen9950X / Node24.19、ONNX Runtime WASM FP32・1thread、nice19・guest CPU16–19。Chrome・M4・スマホの測定ではありません。

| 盤面 | A 現行V3 | B native候補設定試作 |
|---|---:|---:|
| 44石400000 | 成功4.217秒、CNN0 | 成功6.896秒、CNN28回/5,509件 |
| 64石200001 | 成功3.964秒、CNN0 | 60.018秒で観測未完、CNN166回/38,828件 |
| 36石300002 | 成功0.557秒、CNN2回/90件 | 成功2.947秒、CNN0 |

Aは幅8・親上限2・安い評価で128候補へ絞り、44石以上では長いno-pass/late12 SATを先行する現行設定です。Bは幅16・親上限4・CNN前の候補絞り/heuristic sort無し・stop30・対称1・refine0・batch256・44石以上だけML・候補上限18です。Bは短い2,000conflict/20,000decisionのprobe後、late12を挟まずCNNへ進みます。MLdeadlineは無く、外側60秒だけで観測を止めました。設定・順序は`protocol.json`/`plan.json`、完全なA→B差分は`native-geometry.patch`です。

nativeの2秒probeは2,000workと同値ではありません。nativeのSAT portfolio/並列数・候補ごとの20秒と、ブラウザの単一solver/候補work上限も異なります。CPU推論backendはTorch2threadとONNX WASM1threadで異なり、36石BのSATもnative portfolioではありません。したがって「同じnativeをブラウザへ完全移植した」とは呼びません。

Bの64石ではCNN探索が34.879秒で30手へ到達し、16候補の照合後37.002秒でgeneral SATへ移り、60秒で観測未完となりました。CNN score時間33.950秒はruntime/session準備も含みます。CNN実行エラーは0でしたが、個々の候補のUNSAT/unknown内訳は途中logに残っておらず断定できません。この3例ではBの速度改善は見られず、候補幅だけでなくrouting/probe政策も同時に変わった試作です。

`results.jsonl`は6観測のrawをbyte exactで保持し、成功5棋譜は独立Python実装でも全手・目標一致を検証しました。未完は不能や失敗に置換せず、その費用・途中CNN回数を保持しています。数値非有限値は出力しておらず、B policyの`guided_budget_seconds:null`はJSのInfinity、すなわちdeadline無効を意味します。`conditions.json`は公開用allowlistで、私有path/IP/SSH/認証情報を含みません。

`verification.json`にraw/source/patch/verifierのhashと検証記録、`summary.json`に段階経過があります。差分を再現する場合はAのsource hashを照合したcopyにpatchを適用し、Bのhashを確認してください。元コード全体・モデル・binaryは重複収録せず、試作を製品へ有効化するものでもありません。モデル再学習・本番変更・M4本試験への介入は行っていません。

コード差分はMIT、合成ケースは[公開ベンチマーク条件](https://github.com/wand125/othello-retro/blob/main/BENCHMARK_LICENSE.md)に従います。著作者はwand125。モデル・runtimeの条件は元配布物に従います。

## 検証と再実行

独立verifierを含む公開repoをcloneし、取得先を`RETRO_REPO`、この資料の場所を`DIAG`とします。まず探索を行わず、保存済み6行のhash・試行順・CNN回数の整合・成功棋譜を検証できます。

```sh
RETRO_REPO=/path/to/othello-retro
DIAG=/path/to/this-directory
python3 "$DIAG/check_results.py" --repo "$RETRO_REPO"
```

再実行にはNode24、Python3、`patch`と、repoの`browser-wasm/ui`に揃えたWASM/runtimeが必要です。モデルは[公式browser-models-v1 Release](https://github.com/wand125/othello-retro/releases/tag/browser-models-v1)から2つのONNXだけを取得し、archive SHA-256 `da61f0c2da3d518ebe6c6a5f5c02e9b6f20fe1f68a67a1258200617f17a0c248`を照合します。モデル学習や再変換は不要です。runtime/WASMのビルド手順と第三者条件は[ブラウザ版手順](https://github.com/wand125/othello-retro/blob/main/browser-wasm/README.md)を参照してください。

```sh
BROWSER_MODEL_STAGE="$(mktemp -d)"
curl -fL 'https://github.com/wand125/othello-retro/releases/download/browser-models-v1/browser-models-v1.tar.gz' -o "$BROWSER_MODEL_STAGE/models.tar.gz"
printf '%s  %s\n' 'da61f0c2da3d518ebe6c6a5f5c02e9b6f20fe1f68a67a1258200617f17a0c248' "$BROWSER_MODEL_STAGE/models.tar.gz" | shasum -a 256 -c -
tar -xzf "$BROWSER_MODEL_STAGE/models.tar.gz" -C "$BROWSER_MODEL_STAGE"
mkdir -p "$RETRO_REPO/browser-wasm/ui/models"
cp "$BROWSER_MODEL_STAGE/model.fused.onnx" "$BROWSER_MODEL_STAGE/model_passes.fused.onnx" "$RETRO_REPO/browser-wasm/ui/models/"
RETRO_BROWSER_UI="$RETRO_REPO/browser-wasm/ui" nice -n 19 taskset -c 16-19 node "$DIAG/run.cjs" --output /tmp/retro-geometry-new-run
python3 "$DIAG/check_results.py" --repo "$RETRO_REPO" --results /tmp/retro-geometry-new-run/results.jsonl
```

`taskset`はLinux用です。他OSでは外して実条件を記録してください。出力先は存在しないディレクトリが必須です。Bは出力先のcopyへpatchで生成し、repoやモデルを変更しません。測定時artifactとのhash不一致は既定で拒否します。変更版を意図的に試す場合だけ`--allow-artifact-change`を追加し、別測定として扱ってください。`runner-port.json`と`runner-port.patch`に実測runnerからのpath/出力先保護差分を明示しています。再現時のfound/unknown件数は同じとは限りません。今回の公開準備では重い再実行は行っていません。
