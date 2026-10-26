# License scope / ライセンスの適用範囲

Copyright (c) 2026 wand125 and contributors.

| Material / 対象 | Terms / 条件 |
|---|---|
| Original source in `solver/`, `short/`, `runner/`, and the verification scripts in `paper-data/` and original project documentation (except model documentation and article content below) | [MIT](LICENSE), except the article text and third-party material below |
| Original code in `browser-wasm/`, including Rust encoder wrappers, JavaScript, build scripts and tests | [MIT](LICENSE); third-party source/runtime and the two article-derived fixtures below are exceptions |
| `browser-wasm/tests/cases.json`: 12 bank-derived/original-example fixtures | Existing MIT scope; original boards and references unchanged, per-case source metadata retained |
| `browser-wasm/tests/cases.json`: `paper-two-placement-unreachable` and `paper-deep-root-61` | Existing [CC BY 4.0](licenses/CC-BY-4.0.txt) article-content policy; attribution **wand125**, source https://othello-retro.logicpuzzle.app/paper ; extraction changes and original JSON locations in case metadata |
| Compiled WASM and third-party/runtime material in `browser-wasm/` | Original code retains MIT; Kissat, Rust standard library, Emscripten and other components retain their respective terms. See `browser-wasm/ui/kissat.LICENSES.txt`, `browser-wasm/ui/RUST-LICENSES.txt`, referenced runtime notices and `browser-wasm/tests/LICENSE.md` |
| Original generated case/record/measurement data in `benchmarks/` and `records/`, including the two fixed synthetic benchmark banks | Existing [MIT scope](BENCHMARK_LICENSE.md); frozen bytes and hashes are unchanged |
| `model.pt` and `model_passes.pt` distributed in Release v0.1.0; accompanying original model cards and README documents | [CC BY 4.0](licenses/CC-BY-4.0.txt), attribution **wand125**, source https://github.com/wand125/othello-retro/releases/tag/v0.1.0 |
| Converted browser ONNX weights (`browser-models-v1` Release) | CC BY 4.0, attribution **wand125**; original checkpoint source v0.1.0; Conv/BatchNorm folding and format conversion recorded in `browser-wasm/ui/models/model-export-manifest.json` and `LICENSE-MODELS.md` |
| ONNX Runtime Web in `browser-wasm/ui/inference/` | Microsoft MIT and retained third-party notices; see `LICENSE`, `ThirdPartyNotices.txt` and `runtime-manifest.json` in that directory |
| Original article prose and original figures in `solver/ui/paper.html`, and original supplementary analysis in `paper-data/` | [CC BY 4.0](licenses/CC-BY-4.0.txt), attribution **wand125**, source https://othello-retro.logicpuzzle.app/paper |
| Third-party software, license texts, quotations and cited works | Their respective terms; see `solver/THIRD_PARTY_NOTICES.md` and the web notices. No third-party rights are reassigned |

The MIT license also covers original functional code/markup, JavaScript and CSS in the article; CC BY 4.0 covers its original prose and figures. Quoted text and referenced papers are excluded from that original-content grant.

重みはReleaseの添付ファイルとして配布します。変更・再配布時は作者、ライセンスと出典を示し、変更がある場合は明記してください。訓練データの原ファイルは残っておらず、重みの配布に含みません。外部ソルバー、Python依存、動画ライブラリのバイナリを一括してMITへ変更するものではありません。

Weights are Release assets, not Git-tracked binaries. Preserve attribution, license/source information and indicate modifications when redistributing them. The original training files are absent and are not included. External solver, Python-library and video-library binaries retain their own licenses; they are not relicensed as MIT by this document.

ブラウザ版のcompiled WASMを一括して自作コードMITへ変更しません。fixtureの条件は出典の既存方針を維持した配布区分です。

The browser WASM is not collectively relicensed as original MIT code. Fixture terms preserve the existing source-distribution policy.
