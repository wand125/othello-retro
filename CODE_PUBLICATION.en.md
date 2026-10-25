# Publication scope: code, weights and article

[日本語](CODE_PUBLICATION.md) | English

Source and the existing weights are published in the [first experimental Release, v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0).

| Material | Location | Terms |
|---|---|---|
| Rust CLI, Python search/training, UI/server and frozen benchmark harness | [`solver/`](solver/README.en.md) | Original code MIT; third-party notices retain their terms |
| Vertical UI source | [`short/`](short/README.md) | Original code MIT |
| General-purpose measurement, verification, analysis and export | [`runner/`](runner/README.en.md) | MIT |
| Two fixed synthetic banks | [`benchmarks/`](BENCHMARK_LICENSE.md) | Existing MIT scope; bytes/hashes unchanged |
| model.pt and model_passes.pt | Release assets, not Git binaries | CC BY 4.0, attribution wand125 |
| Model cards, identifiers and license information | [`models/`](models/MODEL_CARD.en.md) | CC BY 4.0 |
| Original article prose/figures and original supplementary analysis | [Article](https://othello-retro.logicpuzzle.app/paper?lang=en), `paper-data/` | CC BY 4.0 |

See [LICENSE_SCOPE.md](LICENSE_SCOPE.md), [MIT](LICENSE) and the [CC BY 4.0 text](licenses/CC-BY-4.0.txt). Functional code, article prose and third-party quotations/material are distinguished rather than relicensed together.

## Release assets

- [source.tar.gz](https://github.com/wand125/othello-retro/releases/download/v0.1.0/source.tar.gz): source distribution, without compiled executables or dependency binaries.
- [models.tar.gz](https://github.com/wand125/othello-retro/releases/download/v0.1.0/models.tar.gz): two existing weights, model cards, licenses and identifiers.
- [model.pt](https://github.com/wand125/othello-retro/releases/download/v0.1.0/model.pt) and [model_passes.pt](https://github.com/wand125/othello-retro/releases/download/v0.1.0/model_passes.pt): individual downloads.
- [CC-BY-4.0.txt](https://github.com/wand125/othello-retro/releases/download/v0.1.0/CC-BY-4.0.txt) and [SHA256SUMS](https://github.com/wand125/othello-retro/releases/download/v0.1.0/SHA256SUMS).

Check downloaded hashes and place weights in `solver/ml/`. Follow the [build and execution guide](solver/README.en.md). A documented release-only patch removes bench_fix.py's broad pkill, which could stop unrelated SAT processes. Frozen Cargo/Rust and primary inference-source hashes remain unchanged.

## Shipped notices and validation

Notices for nine locked Rust crates, CaDiCaL 1.9.5 and Kissat 4.0.3 are in [`solver/THIRD_PARTY_NOTICES.md`](solver/THIRD_PARTY_NOTICES.md). Their implementations and binaries are not vendored. cadical 0.1.16 compiles its bundled CaDiCaL during the dependency build; Kissat runs as a separate process. r-efi 6.0.0's MIT permission and copyright are retained from AUTHORS.

The same Rust source passed a Rust 1.98.0 locked release build, all nine tests with Kissat 4.0.3, finite/unbounded SAT smoke checks and independent replay. Inference and optional training-comparison requirements, version evidence and Python notices are documented in [`solver/PYTHON_DEPENDENCIES.md`](solver/PYTHON_DEPENDENCIES.md). Existing benchmark conditions, values and raw records are unchanged.

## Exclusions and reproducibility limits

The original training JSONL files are absent and are not distributed. The public banks are separate data. Recorded lineage associates the main weight with 38,504 mixed-data rows and the retained old model_passes.pt with 25,796 no-pass rows; its filename does not establish pass-only training. Artifact-specific holdout accuracy and exact retraining remain unconfirmed; see the [model card](models/MODEL_CARD.en.md).

Compiled executables, WASM, distribution containers, external solvers, Python wheels and video-library binaries are not included. Redistributing them would require checking the actual bundled components and their notices. Credentials, cookies, usage logs, private infrastructure and personal video/audio are excluded.

`SHA256SUMS` checks the two individual weights and is also included in the models archive. [RELEASE_SHA256SUMS](https://github.com/wand125/othello-retro/releases/download/v0.1.0/RELEASE_SHA256SUMS) covers all other Release assets. [LICENSE-WEIGHTS.md](https://github.com/wand125/othello-retro/releases/download/v0.1.0/LICENSE-WEIGHTS.md) is also supplied.
