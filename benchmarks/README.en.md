# Benchmark data

[日本語](README.md) | [English](README.en.md) | [Interpreting results](../docs/benchmarks/results.en.md)

This directory holds fixed inputs and published results. Existing bank, schedule, and raw-result paths and bytes are preserved for reproduction and hash checks. Use the [common runner](../runner/README.en.md) for execution, verification, and analysis.

## Formal banks

| Inputs | Independent positions | Repetitions and methods | File |
|---|---:|---|---|
| Midgame | 400, plus ten separate pilot cases | Three SAT / Auto repetitions each; 2,400 main trials | [Midgame bank](study-midgame-cpu222-unbounded-v1.json) |
| Terminal | 20 | Three SAT / Auto repetitions each; 120 trials | [Terminal bank](study-endgame-cpu222-unbounded-v1.json) |

Both include schedules and reference histories. Repetitions are not independent positions. The original formal study has no overall trial deadline or final general-SAT limit. See the [measurement design](../docs/benchmarks/design.en.md).

## Formal results

- Native: `{m4,m1,wsl,intel}-cpu222-unbounded-{midgame,endgame}-main-20261025/`, totaling 10,080 trials across four environments.
- [Four-environment midgame summary](four-environment-midgame-comparison-20261025.json), [terminal summary](four-environment-endgame-comparison-20261025.json), and [terminal-time distribution](terminal-time-distribution-20261026.json).
- Browser: [conditions and start record](../docs/benchmarks/browser.en.md). It uses the same banks and schedules; verified results will be added as `m4-browser-wasm-v3-{endgame,midgame}-main-20261026/` with a runtime record.

Read each dataset's metadata, verification, and manifest for its conditions and completion status. Different implementations, inference thread counts, or startup boundaries do not establish a hardware-only speed comparison.

## Separate experiments and preliminary records

| Experiment | Entry |
|---|---|
| Native lightweight Auto: 32 positions, three repetitions, 288 trials | [Data](native-lightweight-32x3-20261026/README.md), [diagnosis](../docs/algorithms/auto-diagnosis.en.md) |
| Browser: 40 preliminary positions, one repetition per version | [All 120 observations and verification](../browser-wasm/benchmarks/browser-pilot-40-20261026/README.en.md) |
| Browser late-pass diagnosis on WSL: three hard positions | [Six trials and reproduction](../browser-wasm/benchmarks/wsl-late-probe-20261026/README.en.md) |
| Eight fixed cases and the old 60-second preliminary comparison | [Inputs](cases.json), [historical comparison](../docs/history/comparison-3x.md) |

`study-*-v1.json`, `study-*-cpu222-v1.json`, `protocol-3x.json`, and `results/` also include historical conditions and preliminary records. The current formal, unbounded banks are the `*-cpu222-unbounded-v1.json` files above. Do not pool older timing profiles into the main study.

## Format and terms

Boards contain 64 row-major cells from a1 to h8: `X` for black, `O` for white, `-` for empty. Histories use lower-case coordinates and forced `pass` moves. A reference proves reachability, not uniqueness. See [data terms](../BENCHMARK_LICENSE.md) and [independent verification](../runner/VALIDATION.en.md).
