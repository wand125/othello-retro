# データ・棋譜・測定結果の検証

[日本語](VALIDATION.md) | [English](VALIDATION.en.md)

実行するプログラムとは別に、公開データと出力を検証できます。通常の検証はPython 3.10以降の標準ライブラリだけで動きます。元のWSL結果のNumPy信頼区間をそのまま再計算する場合だけ、任意の追加パッケージが必要です。

## 固定盤面と予定表

```sh
python3 runner/check.py bank \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --bank benchmarks/study-endgame-cpu222-unbounded-v1.json \
  --require-disjoint seed
```

protocol・盤面集合・予定表・参照棋譜のハッシュを照合し、独立したルール実装で参照棋譜を再生します。盤面の64マス、石数、終局性、case ID・seed、caseごとの方式と反復の過不足、宣言された先順の均衡を調べます。偶然同じ盤面が異なるseedから作られることはあるため、盤面重複は既定では報告だけです。必要な非重複条件だけを`--require-disjoint`で指定します。

hashだけでは、改変したデータとhashを一緒に更新した場合を検出できません。生成規則からも照合するには次を使います。

```sh
python3 runner/check_generation.py \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --bank benchmarks/study-endgame-cpu222-unbounded-v1.json \
  --output .runs/generation-check.json
```

各seedから合法手の選択を再現し、430件の盤面・参照棋譜を照合します。この430件は途中main400・pilot10・終局20の検査数であり、性能集計の独立標本数ではありません。途中の採用順と拒否seed、先順と予定表も再生成します。終局20例の元になった非公開候補poolからの抽出自体は検証対象外で、reportにも明記します。

## 一つの復元棋譜

`record.json`に着手の配列、または`moves`を持つJSONを保存します。case IDはbankに記載されたものを使います。

```sh
python3 runner/check.py record \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --case main-n12-s202610250000000 \
  --moves record.json
```

初期配置から全着手を再生し、反転・手番・強制パス・到達盤面を検査します。省略された正当な強制パスは補完しますが、打てる手がある側を飛ばす色の切替は認めません。正規化した棋譜と検証結果をJSONで返します。

## 測定ログと公開用ファイル

```sh
python3 runner/check.py run \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --input .runs/my-midgame

python3 runner/check.py published \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --input public-results/my-midgame
```

`run`は全結果の棋譜を再検証し、case・方式・反復の順序、入力hash、時間値、中断消費の加算を確認します。`published`はmanifestのファイルhash、危険なファイル参照や私用ファイルの混入も調べます。平均時間と比などを再計算し、汎用runnerの集計は同じbootstrap条件でも再照合します。

元のWSL集計はNumPy版のbootstrapです。標準ライブラリの検証だけでは、そのCIを検証済みとせず、reportに`not_checked`相当の状態を残します。CIの再計算は次の専用コマンドで行います。

```sh
# 原集計と同じNumPy 1.26.4を利用できるPython 3.12環境で実行します。
python3 runner/check_numpy_ci.py \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --input benchmarks/wsl-cpu222-unbounded-midgame-main-20261025 \
  --output .runs/wsl-midgame-ci-check.json
```

終局版はbankとinputを対応するendgame版へ置き換えます。元の反復数・seed・層順でCI端点まで再計算し、公開集計との差を検査します。NumPyがなければ、CI検証を済ませた扱いにはしません。

複数のデータをまとめて検査することもできます。

```sh
python3 runner/check.py all \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --bank benchmarks/study-endgame-cpu222-unbounded-v1.json \
  --run local=.runs/my-midgame \
  --published wsl=benchmarks/wsl-cpu222-unbounded-midgame-main-20261025
```

## 判定の読み方と自己テスト

正常なら終了コード0、失敗なら非0です。reportの検査合格と、試行の全件完了は別です。未完了のログでも、保存された範囲の整合性が正しければ検査は合格し、未完了であることを別に報告します。fixtureの整合性が通っても、復元性能の証拠にはなりません。

検査はルールの正しさ・データの整合性を確認します。外部プログラムが参照解を見ていないこと、自己申告した計算資源を守ること、結果が母集団を代表することまでは証明しません。90%の共通完了率とCIの精度も、それぞれ確認してください。

```sh
python3 -m unittest discover -s runner/tests -v
```

自己テストは、不正なパス・棋譜、hashを更新した改変、順序のずれ、不正な時計、fixtureの混入、中断・再開、子プロセス清掃、私用情報の混入、集計の改変を検査します。NumPy依存の自己テストは、追加パッケージがない環境ではskipと表示します。
