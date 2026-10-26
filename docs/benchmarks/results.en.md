# Benchmark results

[日本語](results.md) | [English](results.en.md)

This page collects all published benchmark studies, including measurements after the Auto improvements. Tables are for reading; links marked `(JSON)` or `(生データ)` provide machine-readable data. Each study keeps its own inputs, implementation version, repetitions, and timing boundary.

| Study | Cases and repetitions | Completion | Results |
|---|---|---|---|
| Browser v3, formal | Same 400/20 banks; SAT/Auto × 3 | All 2,520 histories verified: 2,400 midgame and 120 terminal | [Formal browser results](#browser-formal) |
| Native lightweight Auto, full midgame rerun | 400 boards × 3 methods × 3 repeats | Running; 3,600 trials | [Main comparison table](../../benchmarks/README.en.md#native-comparison) |
| Improved native lightweight Auto, WSL | 32 positions × 3 methods × 3 repetitions | 288 verified histories | [Improved Auto](#lightweight-auto) |
| Original native, M4 / M1 / WSL / Intel | 400 midgames and 20 terminal positions; SAT/Auto × 3 | 10,080 verified histories | [Midgames](#midgame-results), [terminal](#terminal-results) |
| Improved browser v3, preliminary | 40 positions × 1; three versions, 120 observations total | v3: 40/40; earlier versions include unknowns | [Browser comparison](#browser-v3) |
| Native-candidate browser prototype, WSL Node | Three boards × two settings × 1 | Five verified histories, one observation unknown at 60s | [Prototype diagnosis](#native-geometry-pilot) |
| WSL late-pass diagnosis | Three hard boards × two settings × 1 | Four histories, two work-limit unknowns | [Diagnostic results](#late-pass) |
| Historical 60-second preliminary study | Eight cases × 3; Mac / WSL / Cloud Run, plus warm WSL | 168 observations | [Historical results](#historical) |

<a id="lightweight-auto"></a>

## After the native Auto improvements

A separate WSL experiment measured 12 selected 44-disc midgames and all 20 terminal positions, with SAT, old Auto, and lightweight Auto repeated three times each. All 288 trials returned independently verified legal histories. The weights were not retrained.

| Inputs | SAT mean (s) | Old native Auto mean (s) | Lightweight native Auto mean (s) | Lightweight / old Auto [95% CI] |
|---|---:|---:|---:|---|
| 12 midgames, 44 discs | 2.5873 | 1.7012 | 1.5776 | 0.9273 [0.7990, 1.0760] |
| 20 terminal boards | 9.9502 | 9.9076 | 6.8658 | 0.6930 [0.5646, 0.8511] |

The terminal mean fell by about 31%. The midgame interval includes one, so this experiment does not establish a midgame speed advantage over old Auto. This 32-case experiment does not replace the original 400/20-case study. It combines native undo, inference, beam-width, and routing changes. [Full analysis and conditions](../algorithms/auto-diagnosis.en.md), [analysis data (JSON)](../../benchmarks/native-lightweight-32x3-20261026/data/analysis/analysis.json).

<a id="browser-formal"></a>

## Browser v3: formal results

This is **browser Auto v3**. It uses the same source weights as native lightweight Auto, with different search settings and runtime. These are distinct versions.

| Inputs | Browser SAT v3 mean (s) | Browser Auto v3 mean (s) | Auto / SAT [95% CI] | Status |
|---|---:|---:|---|---|
| 400 midgames | 1.5870 | 1.4319 | 0.9023 [0.8279, 0.9728] | 2,400/2,400 histories verified |
| 20 terminal boards | 16.4185 | 17.4604 | 1.0635 [0.9815, 1.1851] | 120/120 histories verified |

**Auto reduced the mean by about 9.8% across 400 midgames. No speed advantage is established on the 20 terminal boards.** Each method has three repeats; all 2,520 returned histories passed independent replay. The speed difference concerns the whole Auto v3 pipeline, not the model alone.

[400-midgame analysis (JSON)](../../benchmarks/m4-browser-wasm-v3-midgame-main-20261026/summary.json) · [All 2,400 histories (生データ)](../../benchmarks/m4-browser-wasm-v3-midgame-main-20261026/runs.jsonl) · [Independent verification (JSON)](../../benchmarks/m4-browser-wasm-v3-midgame-main-20261026/verification.json).

Browser timing includes fresh-Worker WASM and any required model loading; native timing starts after model preparation. Dividing times across these two tables does not establish an implementation speed multiplier. These desktop measurements also do not establish smartphone completion within one minute.

<details>
<summary>Browser terminal minimum, median, maximum, timing conditions and raw data</summary>

Actual M4 Pro / Chrome 155.0.8059.86. Same 20 independent terminal positions, three SAT and three Auto observations each; **120/120 histories independently verified**. No overall trial or final general-SAT deadline.

| Program | Verified | Mean (s) | Minimum case mean | Median case mean | Maximum case mean |
|---|---:|---:|---:|---:|---:|
| Browser SAT v3 | 60 / 60 | 16.4185 | 1.360 | 10.771 | 46.979 |
| Browser Auto v3 | 60 / 60 | 17.4604 | 1.421 | 12.644 | 67.758 |

Minimum, median and maximum are across the 20 per-case means of three repeats, not 60 individual trials. Auto/SAT ratio is 1.0635, 95% CI [0.9815,1.1851]; it includes one. Each trial starts a fresh Worker, with WASM and any needed model loading included; Chrome startup is preparation. CPU/FP32, one inference thread, HTTP cache and Service Workers disabled.

The 400-midgame bank also completed all 2,400 trials. [Conditions](browser.en.md) · [Summary (JSON)](../../benchmarks/m4-browser-wasm-v3-endgame-main-20261026/summary.json) · [All 120 histories (生データ)](../../benchmarks/m4-browser-wasm-v3-endgame-main-20261026/runs.jsonl) · [Runtime/hashes (JSON)](../../benchmarks/m4-browser-wasm-v3-runtime-20261026.json).

</details>

<a id="browser-v3"></a>

## After the browser improvements: 40-case preliminary study

Actual M4 Pro / desktop Chrome, one observation per board and version. Inputs are 20 midgames and 20 terminal boards. Every returned history was independently replayed. The 60-second watchdog records unknown, not unreachability.

| Browser version | Verified histories | Unknown at 60 seconds | Errors |
|---|---:|---:|---:|
| Browser Auto v1, old | 38 / 40 | 2 | 0 |
| Browser SAT v2, old | 37 / 40 | 3 | 0 |
| Browser Auto v3, improved | 40 / 40 | 0 | 0 |

| Improved v3 inputs | Mean (s) | Minimum | Median | Maximum |
|---|---:|---:|---:|---:|
| All 40 | 9.289 | 0.039 | 6.308 | 44.340 |
| 20 midgames | 3.596 | 0.039 | 0.852 | 29.132 |
| 20 terminal boards | 14.982 | 1.334 | 9.954 | 44.340 |

v3 combines SAT-budget changes, late-pass formulas, and optional guidance; four cases used model inference and one finished by the guided route. These are desktop observations and do not establish smartphone completion within one minute. The separate formal study has completed 120 terminal trials; midgames remain in progress without an overall deadline. [Preliminary details](../../browser-wasm/benchmarks/browser-pilot-40-20261026/README.en.md), [summary data (JSON)](../../browser-wasm/benchmarks/browser-pilot-40-20261026/summary.json), [formal conditions](browser.en.md).

The original native measurements below completed all 10,080 trials with independent replay and full 64-cell target matching. See the [measurement design](design.en.md).

<a id="midgame-results"></a>

## Original native version: 400 midgames across four environments

Each environment completed 2,400 trials, 9,600 total. Common complete-case coverage is 400/400 (100%). Three repeats do not turn 400 independent cases into 1,200.

| 環境 / Environment | SAT平均 / mean (s) | Old native Auto mean (s) | auto/SAT | 95%CI | Raw data |
|---|---:|---:|---:|---|---|
| WSL | 0.62050 | 0.59461 | 0.9583 | [0.8586, 1.0594] | [Summary (JSON)](../../benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/summary.json) |
| M4 Pro | 1.56193 | 2.45550 | 1.5721 | [1.3799, 1.7940] | [Summary (JSON)](../../benchmarks/m4-cpu222-unbounded-midgame-main-20261025/summary.json) |
| M1 | 0.95663 | 1.16378 | 1.2165 | [1.0403, 1.3998] | [Summary (JSON)](../../benchmarks/m1-cpu222-unbounded-midgame-main-20261025/summary.json) |
| Intel i9 | 1.27192 | 1.45680 | 1.1454 | [1.0064, 1.2987] | [Summary (JSON)](../../benchmarks/intel-cpu222-unbounded-midgame-main-20261025/summary.json) |

Intervals compare auto/SAT within each environment. Auto has a larger mean on M4, M1 and Intel, with intervals above one. Relative 95% interval radii range from 10.55% to 15.06%. Individual intervals are not adjusted for multiple comparisons. Valid proofs for every case and precise speed-difference estimates are separate outcomes.

[Paired four-environment (JSON)](../../benchmarks/four-environment-midgame-comparison-20261025.json). Auto starts directly with SAT on the 320 cases below 44 discs; eligible 44-disc cases may also finish in the initial SAT probe. The overall mean does not isolate model-only benefit.

<details>
<summary>WSL breakdown by occupied squares</summary>

| Occupied squares | SAT mean (s) | Old native Auto mean (s) | auto/SAT | 95%CI |
|---|---:|---:|---:|---|
| 12 | 0.00421 | 0.00418 | 0.9935 | [0.9650, 1.0210] |
| 20 | 0.00442 | 0.00445 | 1.0070 | [0.9830, 1.0353] |
| 28 | 0.10812 | 0.10509 | 0.9720 | [0.8885, 1.0424] |
| 36 | 0.75857 | 0.83124 | 1.0958 | [0.9536, 1.2630] |
| 44 | 2.22717 | 2.02808 | 0.9106 | [0.7880, 1.0456] |

Each stratum has 80 independent cases and a fixed 20% weight. Individual 95% intervals are not simultaneous coverage. The [original summary (JSON)](../../benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/summary.json) retains all overall and stratum statistics.

</details>

<a id="terminal-results"></a>

## Original native version: 20 terminal boards across four environments

Each environment completed 120 trials, 480 total. Common complete-case coverage is 20/20 (100%). Independent N remains 20, not 60 per slot. This auxiliary suite is separate from the 400 midgames.

| Environment | SAT mean (s) | Old native Auto mean (s) | auto/SAT | 95%CI | Raw data |
|---|---:|---:|---:|---|---|
| WSL | 9.20460 | 9.14890 | 0.9939 | [0.7963, 1.2605] | [Summary (JSON)](../../benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/summary.json) |
| M4 Pro | 16.74105 | 43.69341 | 2.6100 | [2.0733, 3.2491] | [Summary (JSON)](../../benchmarks/m4-cpu222-unbounded-endgame-main-20261025/summary.json) |
| M1 | 11.50916 | 31.21702 | 2.7124 | [2.1779, 3.4251] | [Summary (JSON)](../../benchmarks/m1-cpu222-unbounded-endgame-main-20261025/summary.json) |
| Intel i9 | 17.63237 | 32.69917 | 1.8545 | [1.4588, 2.3634] | [Summary (JSON)](../../benchmarks/intel-cpu222-unbounded-endgame-main-20261025/summary.json) |

<a id="terminal-distribution"></a>

### Terminal minimum, median and maximum

First **average effective_wall_seconds across the three repeats of each case/slot; then take the minimum, median and maximum across those 20 case means**. The median averages the 10th and 11th sorted case means. These are not extrema of the 60 individual trials. Effective time retains interrupted attempt work.

| Environment | Slot | Minimum (s) | Median (s) | Maximum (s) |
|---|---|---:|---:|---:|
| WSL | SAT | 1.296 | 9.024 | 18.918 |
| WSL | auto | 0.753 | 9.593 | 16.431 |
| M4 Pro | SAT | 2.729 | 16.021 | 33.395 |
| M4 Pro | auto | 1.074 | 46.509 | 114.104 |
| M1 | SAT | 2.283 | 11.028 | 20.839 |
| M1 | auto | 0.934 | 33.227 | 73.017 |
| Intel i9 | SAT | 5.259 | 18.291 | 33.890 |
| Intel i9 | auto | 1.695 | 34.710 | 66.101 |

The [distribution (JSON)](../../benchmarks/terminal-time-distribution-20261026.json) retains the calculation rule, every case mean, extremal case IDs, the two median case IDs, separate 60-trial distributions and raw hashes. The table rounds seconds to three decimal places.

Terminal individual 95% intervals are above one for M4, M1 and Intel and include one for WSL. Relative 95% interval radii range from 24.49% to 27.44%. This fixed 20-case auxiliary suite does not establish general terminal-position performance or simultaneous multiple-comparison coverage. A pass in a reference game does not prove that every valid reconstruction needs a pass.

[Paired four-environment (JSON)](../../benchmarks/four-environment-endgame-comparison-20261025.json). The folders containing the linked summary JSON files contain all records, controls, verification and its manifest. The mean tables retain the original NumPy intervals, with [independent CI reproduction reports](../../benchmarks/validation). The public standard-library analyzer uses another RNG, so finite-bootstrap endpoints may differ slightly while arithmetic means agree.

## Recorded control deviations and interpretation

The intended nice value was 19; metadata in both suites records **19 for M4/WSL and 20 for M1/Intel**. The [eight-dataset audit (JSON)](../../benchmarks/execution-controls-20261026.json) preserves observations rather than rewriting them to the plan. These are runner setup observations, not per-child priority measurements or proof of equivalent scheduler behavior across OSes.

Cross-environment differences combine priority, OS, numerical backend, CPU allocation and background activity. M4 recorded high load and a between-trial diagnostic pause, separate from search time. Whole-program duration and case search costs are different clocks. These results do not isolate CPU speed. 100% common coverage is not a matched-controls or precision guarantee.

Earlier finite-time, Torch 2.6, eight-case and invalid-gate runs are not pooled into these results. No unfinished trial receives a finite failure cost. The corresponding source and existing weights are available in [Release v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0).

<a id="native-geometry-pilot"></a>

## Browser prototype using native candidate settings

| Case suffix / stones | A: current browser Auto v3 | B: native-candidate prototype |
|---|---:|---:|
| 400000 / 44 | Found 4.217s | Found 6.896s |
| 200001 / 64 | Found 3.964s | Unknown at 60.018s |
| 300002 / 36 | Found 0.557s | Found 2.947s |

Six observations, one per configuration and case; all five returned histories were independently verified. B did not improve speed in these three pairs. It uses width 16, parent cap 4 and no shortlist before CNN inference. The SAT preprobe policy also changed, so this is neither an isolated width experiment nor an equivalent native port. The runtime is WASM under WSL Node, not Chrome or a phone.

[Settings, stages and limitations](../../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/README.en.md) · [Summary (JSON)](../../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/summary.json) · [All six observations (生データ)](../../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/results.jsonl).

<a id="late-pass"></a>

## WSL late-pass diagnosis

Three terminal cases that were unresolved within 60 seconds on M4 were selected for a post-hoc diagnostic. Each setting was run once on WSL / Ryzen 9 9950X / Node, with 100,000 conflicts and 1,000,000 decisions as internal work limits.

| Case suffix | Default late12 | SAT preset |
|---|---:|---:|
| 200028 | Found, 9.868 s | Unknown, 19.115 s |
| 200107 | Found, 7.821 s | Found, 7.492 s |
| 300185 | Found, 14.418 s | Unknown, 15.905 s |

All four histories were independently replayed. The two unknowns exhausted work limits, not the 60-second outer watchdog. This selected diagnostic is not a representative success-rate or smartphone benchmark. [Conditions and reproduction](../../browser-wasm/benchmarks/wsl-late-probe-20261026/README.en.md), [summary (JSON)](../../browser-wasm/benchmarks/wsl-late-probe-20261026/summary.json).

<a id="historical"></a>

## Historical eight-case, three-repeat comparison

These runs use Torch 2.6 / NumPy 2.2.6 and a 60-second trial request. Inputs are seven reachable boards and one missing-center unreachable board. Correct decisions below include independently validated histories and the sound rejection of the missing-center example. Unknown is not an incorrect unreachability verdict. Cold/model-load-inclusive and preloaded runs have distinct timing boundaries.

| Environment | Model loading | SAT correct / trials | Auto correct / trials | Unknowns | Raw data |
|---|---|---:|---:|---:|---|
| Mac CPU | Included | 23 / 24 | 13 / 24 | 12 | [Summary (JSON)](../../benchmarks/results/mac-cpu3-20261025/summary.json) |
| WSL CPU | Included | 24 / 24 | 24 / 24 | 0 | [Summary (JSON)](../../benchmarks/results/wsl-cpu3-20261025/summary.json) |
| Cloud Run CPU | Included | 24 / 24 | 21 / 24 | 3 | [Summary (JSON)](../../benchmarks/results/cloud-cpu3-20261025/summary.json) |
| WSL CPU | Preloaded | — | 24 / 24 | 0 | [Summary (JSON)](../../benchmarks/results/wsl-cpu3-warm-20261025/summary.json) |

See the [per-case tables and full conditions](../history/comparison-3x.md). These 168 observations are historical preliminary measurements, separate from the unbounded formal banks. [Measurement/verification tools](../../runner/README.en.md) document integration fixtures as harness checks.
