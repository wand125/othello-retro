# Formal browser benchmark

[日本語](browser.md) | [English](browser.en.md)

Actual Chrome on an M4 Pro has been added as a separate program/runtime from the four native environments. Measurement started on26 October2026. See the [frozen conditions and start record (JSON)](../../browser-wasm/benchmarks/formal-study-plan.json) and [reproduction guide](../../browser-wasm/benchmarks/README.en.md).

| Inputs | Independent positions | Repetitions per method | Methods | Trials |
|---|---:|---:|---|---:|
| Terminal | 20 | 3 | SAT / Auto | 120 |
| Midgame | 400 | 3 | SAT / Auto | 2,400 |

The existing banks, references and schedules are unchanged. Terminal and midgame banks run sequentially, without an overall trial or final general-SAT deadline. Every returned history is independently replayed by JavaScript and the common Python verifier. A completed bank is published only after raw-run and safe-export checks pass.

Browser startup is preparation; each trial includes a fresh Worker, WASM initialization and any needed model loading. This differs from native measurements with models already prepared, and the search policies also differ. Comparisons are not hardware-only. Browser inference is CPU/FP32 with one thread.

Completion records will appear at `benchmarks/m4-browser-wasm-v3-runtime-20261026.json`, `benchmarks/m4-browser-wasm-v3-endgame-main-20261026/` and `benchmarks/m4-browser-wasm-v3-midgame-main-20261026/`. This document and the start record are not live counters.

The [40-case preliminary checks](../../browser-wasm/benchmarks/browser-pilot-40-20261026/README.en.md) are separate one-repeat experiments. The final version independently verified40/40 histories, averaging9.29 seconds with a44.34-second maximum. Smartphone hardware can be measured separately with the [on-device page](https://wand125.github.io/othello-retro/benchmark.html). Desktop times do not guarantee smartphone completion within a minute.

[Completed terminal results](results.en.md#browser-formal): all 120 trials independently verified. The 400-midgame bank continues. See the [runtime record (JSON)](../../benchmarks/m4-browser-wasm-v3-runtime-20261026.json).
