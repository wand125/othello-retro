# auto診断と軽量探索の32盤面比較

[日本語](auto-diagnosis.md) | [English](auto-diagnosis.en.md)

WSLの選択32盤面では軽量版が従来autoより終局20盤面の平均を短縮しました。44石中盤12盤面の差は不確実です。checkpointの再学習は行わず、推論・候補探索・終局の経路を変更した実験です。既存の途中400／終局20盤面・4環境・10,080試行の測定を置き換えません。

## ヒット率だけでは分からなかった費用

元のWSL測定では、実CNNを実行した中盤75試行（独立25盤面）と終局36試行（独立12盤面）は、すべて最終一般SATへのfallback前にguided候補から合法棋譜を得ていました。したがって条件付きguidedヒット率は75/75・36/36です。これは初期probeだけで解けた試行やCNNを使わないfallbackを除く値で、分類精度、AUC、個々の候補の正解率ではありません。

ヒットしても候補生成・評価・候補SATの費用が増えれば直接SATより遅くなります。元ログは段階別の秒数を保持していないため、この部分を推測で分解しません。新しい診断では同じ45組のcase×repeatでCNN計時が記録され、従来／軽量のforward呼出しは18,048／7,167、score pipelineの合計は310.777／107.119秒でした。pipelineには特徴量生成・テンソル処理・CNN評価等が含まれます。より少ない候補・呼出しと推論最適化を併用した値で、融合だけの単独効果ではありません。`planes`・`cnn_forward`は`score_pipeline`に含まれ、`beam`はscoreとundoを含むため、各timerを総和しません。

## 変更した探索

- CPUのevalモデルをcloneし、Conv–BatchNormを折り畳んでchannels-last形式へ変換します。checkpointのファイルhashは従来と同一です。推論用係数の変換は行いますが、新規学習・checkpointの上書きは行いません。
- 候補幅16、対称変換数1、refine0、単段の逆向きビームへ縮小します。候補からのSATと一般SATを残し、合法棋譜だけを採用します。
- 空マスが残る終局は両色の合法手がないことをルール評価し、モデル経路を通さず一般SATへ送ります。
- 未満盤終局の逆算で「次の手番なし」を扱うnative側修正を含みます。`baseline`と`lightweight`のnative binary hashは異なります。
- すべての返却棋譜を標準初期配置から厳密再生します。任意パスや手番のすり替えは許可しません。

`baseline`は従来のnative・CNN探索、`lightweight`は修正native・融合推論・縮小policy・終局routingの組合せです。この3方式比較から各変更の因果寄与を分離できません。限定SAT probeや候補探索の不成功は、一般の到達不能判定には使いません。内部probeの2秒・候補SATの20秒はKissat各呼出しへの要求値で、CNF生成・gate待機を含むchunk全体のdeadlineではありません。最後の一般SATと試行全体には時間上限を設けていません。

## 32盤面・各3反復の結果

44石の既存80盤面からIDの固定hash順で12盤面を選び、既存終局bank20盤面と合わせました。選択規則は結果時間に依存しません。各caseに`sat`／`baseline`／`lightweight`を各3回、回転順序で実行し、全288試行が合法棋譜を返しました。各caseで3方式が各順序位置を1回ずつ占めます。32caseは32独立対局であり、各方式96試行でも独立盤面数は32です。

| 対象・独立盤面数 | SAT (s) | 従来auto (秒) | 軽量auto (秒) | 軽量／従来比 [95% CI] | 軽量／SAT比 [95% CI] |
|---|---:|---:|---:|---:|---:|
| 44石中盤／12 | 2.5873 | 1.7012 | 1.5776 | 0.9273 [0.7990, 1.0760] | 0.6097 [0.4677, 0.8430] |
| 終局／20 | 9.9502 | 9.9076 | 6.8658 | 0.6930 [0.5646, 0.8511] | 0.6900 [0.5252, 0.9245] |

秒数は各盤面の3反復平均を盤面間で等重み平均した、受理した棋譜を受信するまでのwall時間です。最終の独立再生はこの時計の外、instrumentationは時計内です。CIは層内の独立caseを再標本化するpaired cluster bootstrap 5,000回で、同じcaseの全反復と方式を保持します。CIは表の平均**比**に対する区間です。中盤の軽量／従来比の区間は1をまたぎます。終局の層は満盤参照パスなし7・あり7・未満盤6です。参照棋譜のパスは、すべての解にパスが必要という意味ではありません。固定予定表を完走し、CIに基づく打切りは行いません。

| 経路（全96試行／方式） | 従来auto | 軽量auto |
|---|---:|---:|
| 初期SAT probeで成功 | 33 | 33 |
| CNN後のguided成功 | 45 | 39 |
| CNN後の候補miss→一般SAT | 0 | 6 |
| CNNなしの非予定fallback | 18 | 0 |
| 予定した未満盤終局→一般SAT | 0 | 18 |

両autoのCNN実行集合は同じ45試行・15独立盤面です。軽量の条件付きguided hitは39/45（86.7%）、従来は45/45です。軽量の6missは2盤面×3反復で、一般SATですべて合法解を得ました。予定exact18は6盤面×3反復であり、CNN失敗・モデル実行eligibleの分母から除外します。中盤だけでは両方式9/9、終局だけでは従来36/36・軽量30/36です。最終found率100%は一般SATを含むpipelineの結果です。

## 条件・中断費用・再現範囲

WSL、Python3.12.13、Torch2.2.2+cpu／NumPy1.26.4、CPU FP32、推論・BLAS2スレッド、nice19、guest CPU16–19、Kissat4.0.3・実SAT同時2本で計測しました。常駐モデルを方式ごとに読み込み、batch256を3回warmupしてから計時します。冷起動やダウンロードの短縮はこの表で測っていません。別guest CPU集合との分離は記録していますが、Windows hostの物理core独占は未検証です。

42試行のdurable prefixを残して制御上の中断があり、同じアルゴリズム・重み・native・環境hashを確認して43試行目から再開しました。driverだけresume機能を追加した旧新sourceを保持しています。実行program wallは112.525822＋1,715.195025＝1,827.720847秒、受理された288試行の合計は1,814.591218秒、model準備は計0.600065秒です。残差13.129629秒には準備・検証・保存・清掃・中断作業などが含まれ、中断試行だけの正確な時間は残っていません。最後の行からの間隔や残差を、特定caseの費用・失敗・timeoutとして補完しません。休止を含むcalendar span3,628.747476秒は別記録です。

32盤面に限定した探索的な比較です。候補ランキングや経路は浮動小数点の再構成と探索縮小で変わり得ます。全ランキング、NaN/score分布、真の候補labelは記録しておらず、モデルの分類精度・新規盤面一般への性能を評価したものではありません。元訓練データが不在という制約も解消しません。

## 公開する検証資料

- [原288行・metadata・再開前prefix記録](../../benchmarks/native-lightweight-32x3-20261026/data/run/metadata.json)、[独立集計](../../benchmarks/native-lightweight-32x3-20261026/data/analysis/analysis.json)、[追加監査](../../benchmarks/native-lightweight-32x3-20261026/data/analysis/independent-audit.json)
- [選別と原／公開hashの対応](../../benchmarks/native-lightweight-32x3-20261026/EXPORT_MANIFEST.json)：main rawはbyte同一、auditの制御PID・運用情報だけを明示的に除去します。
- 実行時のsource snapshotとdriver旧新、型付きmiss理由・段階timerを保存します。モデル・native binary実体はGitに含めず、実測時hashと既存[重みRelease](https://github.com/wand125/othello-retro/releases/tag/v0.1.0)を参照します。

再集計例（新しい出力先を使用）:

```sh
python3 solver/benchmarks/analyze_auto_diagnostic.py --input benchmarks/native-lightweight-32x3-20261026/data/run --midgame-bank benchmarks/study-midgame-cpu222-unbounded-v1.json --endgame-bank benchmarks/study-endgame-cpu222-unbounded-v1.json --output /tmp/native-lightweight-analysis-new
```

## 本番適用は別の機能確認

WSLのnativeサービスには`lightweight`／`fused_channels_last`を適用済みです。記録されたsmoke環境はTorch2.6.0 CPU／NumPy2.2.6で、上のTorch2.2.2／NumPy1.26.4比較とは別です。44石・未満盤終局・満盤のsmokeと、導入済みrunnerの44石確認が厳密再生に合格しました。health、既存resource条件、DB件数は維持されています。単発の機能確認を速度比較とは扱いません。[公開用rollout要約](../../benchmarks/native-lightweight-32x3-20261026/data/analysis/production-functional-summary.json)へ根拠hashを記録し、service設定・認証・私有pathは含めません。ブラウザSAT/WASM版は独立した実装です。
