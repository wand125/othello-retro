# Code publication scope and remaining checks

[日本語](CODE_PUBLICATION.md) | [English](CODE_PUBLICATION.en.md)

## Published measurement tools

Alongside boards, reference records, measurement data, and solver information, `runner/` now publishes new general-purpose measurement tools. They use only the Python 3.10+ standard library. Connect your own external program through JSON to run a frozen bank and schedule, independently replay records, analyze measurements, and export public results.

- Usage: [日本語](runner/README.md) / [English](runner/README.en.md)
- [MIT terms and scope for the tools and two synthetic banks](BENCHMARK_LICENSE.md)

The measurement tools are not a reconstruction engine. The fixture only looks up reference records, and its speed is not reconstruction performance. The original Rust/Python reconstruction engine, training code, executables, and trained models are not distributed. This repository alone cannot reproduce or run the original program. The MIT permission for the tools and banks does not license those undistributed components or the article text.

## Potential publication of the original engine

A 31-file source-only candidate has been prepared for the Rust board operations, reversal logic, necessary conditions, SAT encoding, and CLI. It preserves Cargo.toml/lock and nine Rust modules, with notices for nine locked dependencies, external-solver information, examples, and file hashes. Python search/training/UI code, models, original training data, executables, WASM, and containers are excluded.

Using the same source as the candidate, a WSL locked release build with Rust 1.98.0 passed, along with all nine unit tests using Kissat 4.0.3 and finite/unbounded SAT smoke tests. The resulting records were independently replayed. Validation is separate from release approval. **The original reconstruction engine remains undistributed**, pending the owner's review of provenance, attribution/scope, and publication.

MIT licenses have been checked for Kissat 4.0.3, CaDiCaL 1.9.5, and the cadical 0.1.16 Rust binding. Redistributed components must retain the copyright and license notices for those versions. MIT terms are proposed for the original custom Rust code, pending the owner's decision. The proposal is not an existing grant. It is separate from the MIT permission already applied to the measurement tools and two banks.

## Checks performed

- [Declared licenses and notice-file inventory for nine locked Rust dependencies](licenses/rust-dependency-inventory.json). Exact-version archive checksums and notices were checked, and required notices were packaged in the source-only candidate. r-efi 6.0.0 contains its MIT permission text and copyright attributions in `AUTHORS`, resolving the earlier missing-notice issue. It declares MIT OR Apache-2.0 OR LGPL-2.1-or-later; the candidate selects MIT. It is a conditional dependency and not an actual build dependency for the Apple targets.
- [Metadata inventory for eleven inference-environment packages](licenses/python-inference-inventory.json). This covers the CPU benchmark environment, not a completed audit of the Cloud Run Google SDK or all training/video distribution dependencies. These inference packages are not required by the standard-library-only public runner.
- The [official PyTorch 2.2.2 license](https://github.com/pytorch/pytorch/blob/v2.2.2/LICENSE) has been checked. Binary distribution would require separate checks of bundled native-library notices, including those accompanying NumPy and other packages.

## Remaining checks for undistributed components

| Component | Status |
|---|---|
| Rust source-only candidate | 31 files; dependency notices, build, nine tests, and smoke validation prepared. Proposed custom-code MIT terms and publication await the owner's decision |
| Python search/training/UI | Separate from the Rust candidate; undistributed |
| Trained `.pt` weights | Training/copy records checked against artifacts. An explicit weight license and publication decision remain pending |
| Original training data | Original files are absent and cannot currently be distributed. Exact retraining reproduction is unconfirmed; these are separate from the two MIT-licensed test banks |
| Compiled executables, WASM, and distribution containers | Decision follows preparation of bundled dependency notices |
| Video-production version | Separate from the simple public version; additional dependencies such as Mediabunny require review |
| Credentials, private keys, cookies, usage logs, and private infrastructure configuration | Excluded from publication |

The recorded lineage associates the main `model.pt` with 38,504 mixed-data rows and `model_passes.pt`, retained from the old model, with 25,796 no-pass rows. Its filename does not establish pass-only training. Original training files are absent; artifact-specific predictive accuracy and exact retraining reproduction remain unconfirmed. Full model cards, raw logs, evidence, and checkpoints have not been added to these public materials.

Checking a license name, packaging notices, and deciding distribution terms for custom code are separate tasks. This document does not represent a completed distribution audit of the original program as a whole. See also [solver information](SOLVERS.en.md).
