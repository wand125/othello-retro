# Publication scope: code, weights and article

[日本語](CODE_PUBLICATION.md) | English

Source and the existing weights are published in the [first experimental Release, v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0).

| Material | Location | Terms |
|---|---|---|
| Rust CLI, Python search/training, UI/server and frozen benchmark harness | [`solver/`](solver/README.en.md) | Original code MIT; third-party notices retain their terms |
| Browser SAT and static distribution | [`browser-wasm/`](browser-wasm/README.en.md) | Original code MIT; compiled WASM retains third-party notices and fixture-specific terms |
| Vertical UI source | [`short/`](short/README.md) | Original code MIT |
| General-purpose measurement, verification, analysis and export | [`runner/`](runner/README.en.md) | MIT |
| Two fixed synthetic banks | [`benchmarks/`](BENCHMARK_LICENSE.md) | Existing MIT scope; bytes/hashes unchanged |
| model.pt and model_passes.pt | Release assets, not Git binaries | CC BY 4.0, attribution wand125 |
| Model cards, identifiers and license information | [`models/`](models/MODEL_CARD.en.md) | CC BY 4.0 |
| Original article prose/figures and original supplementary analysis | [Article](https://othello-retro.logicpuzzle.app/paper?lang=en), `paper-data/` | CC BY 4.0 |

See [LICENSE_SCOPE.md](LICENSE_SCOPE.md), [MIT](LICENSE) and the [CC BY 4.0 text](licenses/CC-BY-4.0.txt). Functional code, article prose and third-party quotations/material are distinguished rather than relicensed together.

## Native Release v0.1.0 assets

- [source.tar.gz](https://github.com/wand125/othello-retro/releases/download/v0.1.0/source.tar.gz): source distribution, without compiled executables or dependency binaries.
- [models.tar.gz](https://github.com/wand125/othello-retro/releases/download/v0.1.0/models.tar.gz): two existing weights, model cards, licenses and identifiers.
- [model.pt](https://github.com/wand125/othello-retro/releases/download/v0.1.0/model.pt) and [model_passes.pt](https://github.com/wand125/othello-retro/releases/download/v0.1.0/model_passes.pt): individual downloads.
- [CC-BY-4.0.txt](https://github.com/wand125/othello-retro/releases/download/v0.1.0/CC-BY-4.0.txt) and [SHA256SUMS](https://github.com/wand125/othello-retro/releases/download/v0.1.0/SHA256SUMS).

Check downloaded hashes and place weights in `solver/ml/`. Follow the [build and execution guide](solver/README.en.md). A documented release-only patch removes bench_fix.py's broad pkill, which could stop unrelated SAT processes. The v0.1.0 frozen source hashes remain in historical records. Current `solver/` contains the subsequent lightweight update and has its own hashes.

## Shipped notices and validation

For native v0.1.0, notices for nine locked Rust crates, CaDiCaL 1.9.5 and Kissat 4.0.3 are in [`solver/THIRD_PARTY_NOTICES.md`](solver/THIRD_PARTY_NOTICES.md). Their implementations and binaries are not vendored in that native source distribution. cadical 0.1.16 compiles its bundled CaDiCaL during the dependency build; Kissat runs as a separate process. r-efi 6.0.0's MIT permission and copyright are retained from AUTHORS.

The historical v0.1.0 Rust source passed a Rust 1.98.0 locked release build, all nine tests with Kissat 4.0.3, finite/unbounded SAT smoke checks and independent replay. Inference and optional training-comparison requirements, version evidence and Python notices are documented in [`solver/PYTHON_DEPENDENCIES.md`](solver/PYTHON_DEPENDENCIES.md). Existing benchmark conditions, values and raw records are unchanged.

## Subsequent native lightweight source

Current `solver/` adds opt-in lightweight search/inference, incomplete-terminal undo correction, diagnosis/resume, analysis and tests. See [AUTO_DIAGNOSIS.en.md](AUTO_DIAGNOSIS.en.md) and the [new data](benchmarks/native-lightweight-32x3-20261026/EXPORT_MANIFEST.json). Current validation covers 11 native and 17 Python tests plus independent replay of 288 records. The original nine-test v0.1.0 [historical record](solver/history/v0.1.0/README.md) retains its numbers and is distinct from [current validation](solver/NATIVE_LIGHTWEIGHT_VALIDATION.json). Checkpoints, Cargo, original banks/raw/results tables and manuscript are unchanged. This does not replace the existing v0.1.0 source asset.

## Separate browser SAT / lightweight Auto distribution

[`browser-wasm/`](browser-wasm/README.en.md) is static, with SAT and optional lightweight Auto, without a computation server. Auto uses ONNX Runtime Web 1.30.0, CPU FP32 and one inference thread, retaining complete SAT fallback. It includes compiled WASM for the Rust CNF encoder and Kissat 4.0.3, rebuild sources, build records, licenses and runtime notices. Kissat, Rust standard-library and Emscripten terms remain separate from the original-code MIT grant; retain `ui/kissat.LICENSES.txt`, `ui/RUST-LICENSES.txt` and their referenced files.

ONNX models are a [separate browser-models-v1 Release](https://github.com/wand125/othello-retro/releases/tag/browser-models-v1), converted by eval Conv–BN folding without changing original checkpoints. See [download/archive checksum/two-model copy instructions](browser-wasm/README.en.md) and [portable conversion/numeric fixtures](browser-wasm/model-tools/README.en.md). The roughly 14.24MB runtime and needed model load lazily, without a CDN or computation API. Model derivatives retain CC BY 4.0, wand125 attribution and conversion changes; ONNX Runtime retains its shipped notices.

Of the 14 acceptance fixtures, 12 derived from the existing banks/original examples retain MIT terms; the two article-derived fixtures retain the existing CC BY 4.0 policy. Their case metadata names wand125, the [article](https://othello-retro.logicpuzzle.app/paper), source data and extraction changes. See [fixture terms](browser-wasm/tests/LICENSE.md). This browser distribution does not change the old native benchmark conditions, values, hashes or manuscript.

## Exclusions and reproducibility limits

The original training JSONL files are absent and are not distributed. The public banks are separate data. Recorded lineage associates the main weight with 38,504 mixed-data rows and the retained old model_passes.pt with 25,796 no-pass rows; its filename does not establish pass-only training. Artifact-specific holdout accuracy and exact retraining remain unconfirmed; see the [model card](models/MODEL_CARD.en.md).

The native v0.1.0 source distribution excludes compiled executables, WASM, distribution containers, external solver binaries, Python wheels and video-library binaries. That exclusion does not apply to the separate browser WASM distribution above. Binary distribution retains the notices applicable to its actual bundled components. Credentials, cookies, usage logs, private infrastructure and personal video/audio are excluded.

`SHA256SUMS` checks the two individual weights and is also included in the models archive. [RELEASE_SHA256SUMS](https://github.com/wand125/othello-retro/releases/download/v0.1.0/RELEASE_SHA256SUMS) covers all other Release assets. [LICENSE-WEIGHTS.md](https://github.com/wand125/othello-retro/releases/download/v0.1.0/LICENSE-WEIGHTS.md) is also supplied.
