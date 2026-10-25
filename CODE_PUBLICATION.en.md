# Code publication scope and remaining checks

[日本語](CODE_PUBLICATION.md) | [English](CODE_PUBLICATION.en.md)

## Published measurement tools

Alongside boards, reference records, measurement data, and solver information, `runner/` now publishes new general-purpose measurement tools. They use only the Python 3.10+ standard library. Connect your own external program through JSON to run a frozen bank and schedule, independently replay records, analyze measurements, and export public results.

- Usage: [日本語](runner/README.md) / [English](runner/README.en.md)
- [MIT terms and scope for the tools and two synthetic banks](BENCHMARK_LICENSE.md)

The measurement tools are not a reconstruction engine. The fixture only looks up reference records, and its speed is not reconstruction performance. The original Rust/Python reconstruction engine, training code, executables, and trained models are not distributed. This repository alone cannot reproduce or run the original program. The MIT permission for the tools and banks does not license those undistributed components or the article text.

## Potential publication of the original engine

Potential source releases include the original Rust board operations, reversal logic, necessary conditions, SAT encoding, and CLI, plus Python search/training code and the simple UI. The intended approach is to specify external solvers and Python libraries as dependencies, without bundling executables or libraries in the first reconstruction-source release. This is not a completed release or a promised release date.

MIT licenses have been checked for Kissat 4.0.3, CaDiCaL 1.9.5, and the cadical 0.1.16 Rust binding. Redistributed components must retain the copyright and license notices for those versions. A license for the original custom reconstruction code has not yet been chosen. That work is separate from the MIT license already applied to the new measurement tools.

## Checks performed

- [Declared licenses and notice-file inventory for nine locked Rust dependencies](licenses/rust-dependency-inventory.json). MIT or alternatives such as MIT/Apache have been checked. The conditional r-efi dependency declares MIT OR Apache-2.0 OR LGPL-2.1-or-later. Its retrieved crate does not contain a separate license text, so notice packaging is not considered complete. It is not an actual build dependency for the Apple targets.
- [Metadata inventory for eleven inference-environment packages](licenses/python-inference-inventory.json). This covers the CPU benchmark environment, not a completed audit of the Cloud Run Google SDK or all training/video distribution dependencies. These inference packages are not required by the standard-library-only public runner.
- The [official PyTorch 2.2.2 license](https://github.com/pytorch/pytorch/blob/v2.2.2/LICENSE) has been checked. Binary distribution would require separate checks of bundled native-library notices, including those accompanying NumPy and other packages.

## Remaining checks for undistributed components

| Component | Status |
|---|---|
| Original Rust/Python reconstruction, search, and training code | Distribution terms for custom code and third-party notices are under review |
| Trained `.pt` weights | Distribution decision follows documentation of training data, execution conditions, and weight provenance |
| Training data | Generation sources, labeling conditions, and the actual training set are being documented; this is separate from the two MIT-licensed test banks |
| Compiled executables, WASM, and distribution containers | Decision follows preparation of bundled dependency notices |
| Video-production version | Separate from the simple public version; additional dependencies such as Mediabunny require review |
| Credentials, private keys, cookies, usage logs, and private infrastructure configuration | Excluded from publication |

Checking a license name, packaging notices, and deciding distribution terms for custom code are separate tasks. This document does not represent a completed distribution audit of the original program as a whole. See also [solver information](SOLVERS.en.md).
