# Othello Retro — Source, weights, and benchmarks

[日本語](README.md) | [English](README.en.md)

This experiment reconstructs one legal Othello move sequence from the standard opening position to a given board. It does not identify the original game or calculate optimal play.

- [Browser SAT/WebAssembly preview — publication pending](https://wand125.github.io/othello-retro/) — [browser build and usage guide](browser-wasm/README.en.md)
- [Original server-backed experimental app](https://othello-retro.logicpuzzle.app/) / [Created records](https://othello-retro.logicpuzzle.app/examples)
- Interactive article: [日本語](https://othello-retro.logicpuzzle.app/paper?lang=ja) / [English](https://othello-retro.logicpuzzle.app/paper?lang=en)

The Rust/Python reconstruction, search, training and UI source is published in [`solver/`](solver/README.en.md); the vertical UI source is in [`short/`](short/README.md). Trained weights are assets of the [first experimental Release, v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0). Git tracks only model cards, license information and identifiers in `models/`, not `.pt` binaries.

Download [source.tar.gz](https://github.com/wand125/othello-retro/releases/download/v0.1.0/source.tar.gz), [models.tar.gz](https://github.com/wand125/othello-retro/releases/download/v0.1.0/models.tar.gz) and [SHA256SUMS](https://github.com/wand125/othello-retro/releases/download/v0.1.0/SHA256SUMS), then follow the [build, SAT and auto instructions](solver/README.en.md). Put weights in `solver/ml/`. That native v0.1.0 source distribution excludes compiled executables, third-party dependency binaries and original training files. The separate [`browser-wasm/`](browser-wasm/README.en.md) contains compiled Rust-encoder and Kissat WASM, rebuild sources and applicable notices. The original training files are absent, so exact retraining of the historical weights is not guaranteed.

Test boards, reference records, measured results and **measurement tools for connecting another program or environment to the same frozen banks** are also published. The tools use the Python 3.10+ standard library on Linux/macOS/WSL. Their integration fixture only looks up reference records; it does not measure reconstruction performance.

`SHA256SUMS` checks the two individual weights. [RELEASE_SHA256SUMS](https://github.com/wand125/othello-retro/releases/download/v0.1.0/RELEASE_SHA256SUMS) covers all other assets, including both source and model archives.

## Tools and documentation

| Topic | 日本語 | English |
|---|---|---|
| Browser SAT, static distribution and offline use | [ブラウザ版手順](browser-wasm/README.md) | [Browser guide](browser-wasm/README.en.md) |
| Build, SAT, auto and training | [本体手順](solver/README.md) | [Engine guide](solver/README.en.md) |
| Model provenance, download and terms | [モデルカード](models/MODEL_CARD.ja.md) | [Model card](models/MODEL_CARD.en.md) |
| Connect, run, analyze, and export an external program's results | [runner利用手順](runner/README.md) | [Runner guide](runner/README.en.md) |
| Validate generation, records, logs, summaries, and public bundles | [検証手順](runner/VALIDATION.md) | [Validation guide](runner/VALIDATION.en.md) |
| Formal measurement progress and results | [測定結果](BENCHMARK_RESULTS.md) | [Results](BENCHMARK_RESULTS.en.md) |
| Sampling, repetitions, timing, and statistics | [測定設計](MEASUREMENT_DESIGN.md) | [Measurement design](MEASUREMENT_DESIGN.en.md) |
| Solvers and dependencies | [ソルバー情報](SOLVERS.md) | [Solvers](SOLVERS.en.md) |
| Published code and remaining checks | [公開状況](CODE_PUBLICATION.md) | [Publication status](CODE_PUBLICATION.en.md) |

The formal banks measure 400 midgame boards and 20 terminal boards separately, with a fixed schedule of three repetitions each for `sat` and `auto`. Both methods give 2,400 midgame trials and 120 terminal trials. The original program's four-environment comparison targets M4, M1, WSL, and Intel, using the same boards, schedule, model, and search code, with CPU/FP32, two inference threads, Torch 2.2.2, and NumPy 1.26.4. There is no overall trial deadline or time limit on the final general SAT solve. See the results documentation for completion status and actual conditions.

All four environments completed 2,400 midgame and 120 terminal trials each (10,080 total), with independent replay of every record. Both suites have 100% common coverage. Recorded nice values were 19 for M4/WSL and 20 for M1/Intel, a deviation from the intended 19. See [results and control limitations](BENCHMARK_RESULTS.en.md).

External programs do not have to use the original model or search implementation. Preserve the fixed inputs and schedule, and record your implementation, environment, internal limits, and timing mode. Do not compare oneshot startup-inclusive times and resident post-preparation times as matched conditions. Source and model hashes for the original program in the bank are separate from the external program's own identity records.

The [eight-board, three-repetition comparison](COMPARISON_3X.md) and [its protocol](benchmarks/protocol-3x.json) are preliminary experiments with Torch 2.6, NumPy 2.2.6, and a 60-second limit. They are separate from the formal unbounded measurements. They distinguish model loading from post-loading time and record unresolved trials. Earlier single-run comparisons were withdrawn. The first Mac measurements did not record the actual inference device and are not treated as MPS measurements.

## Published data

- [400 midgame boards and ten pilot boards](benchmarks/study-midgame-cpu222-unbounded-v1.json)
- [20 terminal boards](benchmarks/study-endgame-cpu222-unbounded-v1.json)
- [Eight fixed cases](benchmarks/cases.json): seven reachable and one unreachable.
- [Seven created records](records/created-games.json): independently replayed to check legality and the target board. Any attached computation time records that creation event; it is not a controlled cross-environment performance measurement.
- [Article supplementary data](paper-data/README.en.md): boards, records, and verification conditions used in the article's explanations and figures.

Boards are 64 characters in row-major order from a1 to h8: `X` for black, `O` for white, and `-` for empty. Move coordinates use the same orientation. `pass` denotes a forced pass by a player with no legal move. A reference record proves reachability; it does not imply a unique solution. The unreachable eight-case example leaves one of the four opening center squares empty, violating the invariant that occupied squares never become empty.

Eight-case SHA-256: `292d782cdd23d794e33bc829286a9c0dd4d11979e1db06b27bbf362b0d1a8d64`

## License and publication scope

Original source in `solver/`, `short/`, `runner/` and `browser-wasm/` (except third-party components and fixture-specific terms), plus ordinary original project documentation, is [MIT](LICENSE). The two synthetic banks retain their existing [MIT scope](BENCHMARK_LICENSE.md). Weights/model cards and original article prose/figures are [CC BY 4.0](licenses/CC-BY-4.0.txt), with attribution **wand125** and changes indicated when modified. See [LICENSE_SCOPE.md](LICENSE_SCOPE.md) for the distinction between functional article code, prose and third-party material. External software and cited works retain their own terms.

The browser preview computes locally and stores new records in the browser; sharing requires JSON export or another explicit step. Existing public records are bundled as a static snapshot.

The original server-backed experimental app collects and stores newly created boards, move sequences, computation times, and related creation information, and publishes them as created records. Past usage jobs are not bulk-published.

Usage logs, browser identifiers, credentials, and private infrastructure configuration are excluded from publication. Keep private runner output in `.runs/` and user configuration in `*.local.json`; use the runner's export tool to write a separate public directory. Third-party implementations are obtained as dependencies; see the [publication scope](CODE_PUBLICATION.en.md) for the shipped files and notices.
