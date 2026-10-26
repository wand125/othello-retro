# ベンチマークの利用条件 / Benchmark license scope

測定・独立検証・解析・exportの`runner/`と、次の二つの合成テストデータには、従来どおり[MIT](runner/LICENSE)を適用します。別環境・別プログラムでの測定、改変、再配布に利用できます。著作権表示と許諾文を保持してください。

- `benchmarks/study-midgame-cpu222-unbounded-v1.json`
- `benchmarks/study-endgame-cpu222-unbounded-v1.json`

対象データは盤面、生成条件、参照棋譜、予定表を含みます。本体ソースと重みの公開に伴って、凍結済みbankの内容・hash・MIT条件を変更していません。これは原訓練データの許諾・復元を意味せず、元訓練JSONLは現存していません。

自作復元器ソースのMIT、重み・自作論文本文等のCC BY 4.0、第三者素材は別の対象です。[LICENSE_SCOPE.md](LICENSE_SCOPE.md)、[コード公開範囲](docs/distribution/publication.md)、[CC BY 4.0本文](licenses/CC-BY-4.0.txt)を参照してください。

---

The measurement, independent-verification, analysis and export tools in `runner/` and the two synthetic banks above retain their existing [MIT License](runner/LICENSE). You may benchmark another environment or program, modify and redistribute them while retaining the copyright and permission notice.

The banks include boards, generation conditions, reference records and schedules. Publishing the engine and weights does not change their frozen bytes, hashes or MIT terms. This does not recover or license the absent original training JSONL files.

Original engine-source MIT terms, CC BY 4.0 for weights/original article prose, and third-party rights apply to different material. See [LICENSE_SCOPE.md](LICENSE_SCOPE.md), [publication scope](docs/distribution/publication.en.md), and the [CC BY 4.0 text](licenses/CC-BY-4.0.txt).
