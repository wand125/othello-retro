# Othello Retro

[日本語](README.md) | [English](README.en.md)

Reconstruct a legal Othello history from the standard initial position to a given board. This repository contains the browser app, Rust/Python engine, and tools for measuring and independently verifying programs on fixed inputs.

- [Browser preview](https://wand125.github.io/othello-retro/): SAT and lightweight Auto run on your device, without a computation backend.
- [On-device benchmark](https://wand125.github.io/othello-retro/benchmark.html): runs on smartphones too, with local JSON export.
- [Server-backed experimental app](https://othello-retro.logicpuzzle.app/) and [generated records](https://othello-retro.logicpuzzle.app/examples)
- Interactive article: [日本語](https://othello-retro.logicpuzzle.app/paper?lang=ja) / [English](https://othello-retro.logicpuzzle.app/paper?lang=en)

## Use and build

| Task | Start here |
|---|---|
| Use the browser app or deploy static files | [Browser guide](browser-wasm/README.en.md) |
| Build the native engine and run SAT / Auto | [Engine guide](solver/README.en.md) |
| Benchmark another program or environment on the same boards | [Common runner](runner/README.en.md) and [validation guide](runner/VALIDATION.en.md) |
| Connect a browser to the common runner | [Browser measurement adapter](browser-wasm/benchmarks/README.en.md) |
| Download trained weights | [Models and terms](models/README.md) |

Download artifacts from [Releases](https://github.com/wand125/othello-retro/releases). The static browser bundle is in [v0.3.0](https://github.com/wand125/othello-retro/releases/tag/v0.3.0); converted ONNX weights are in [browser-models-v1](https://github.com/wand125/othello-retro/releases/tag/browser-models-v1). The guides explain downloads and checksum verification.

## Results and documentation

- [Benchmark results](benchmarks/README.en.md): major result tables, Auto versions, running studies, reproduction and raw data.
- [Documentation index](docs/README.en.md): search methods, measurement design, solvers, and publication scope.
- [Browser formal-study conditions and start record](docs/benchmarks/browser.en.md) and [preliminary 40-case results](browser-wasm/benchmarks/browser-pilot-40-20261026/README.en.md)
- [Native lightweight-Auto diagnosis](docs/algorithms/auto-diagnosis.en.md)

Browser and native implementations have different search and startup conditions. Desktop measurements do not guarantee smartphone completion within one minute. Use the on-device page for separate hardware measurements.

## Layout

| Directory | Contents |
|---|---|
| `browser-wasm/` | Browser app, WASM builds, ONNX conversion, browser measurements |
| `solver/` | Rust/Python engine, training and search, server UI |
| `runner/` | Common execution, independent verification, analysis, and safe public export |
| `benchmarks/` | Frozen inputs, conditions, and published measurement data |
| `docs/` | Japanese/English documentation and historical records |
| `models/`, `licenses/` | Model cards, artifact identifiers, and terms |
| `short/` | Vertical UI for the server implementation |
| `paper-data/`, `records/` | Article supplements and generated game records |

## License

Original code is [MIT](LICENSE); weights and original article prose/figures use [CC BY 4.0](licenses/CC-BY-4.0.txt). Third-party runtimes retain their notices. See the [license scope](LICENSE_SCOPE.md) and [benchmark data terms](BENCHMARK_LICENSE.md).
