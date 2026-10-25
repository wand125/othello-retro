# Uncapped benchmark results

[日本語](BENCHMARK_RESULTS.md) | English

Updated 2026-10-26. All four environments completed the frozen schedule: 10,080 trials. Every record passed independent legal replay and full 64-cell target matching. Midgame and terminal suites are analyzed separately; each board has three repeats per slot. See the [design](MEASUREMENT_DESIGN.en.md) and each run's manifest.

## Four environments: 400 midgames

Each environment completed 2,400 trials, 9,600 total. Common complete-case coverage is 400/400 (100%). Three repeats do not turn 400 independent cases into 1,200.

| 環境 / Environment | SAT平均 / mean (s) | auto平均 / mean (s) | auto/SAT | 95%CI |
|---|---:|---:|---:|---|
| [WSL](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/summary.json) | 0.62050 | 0.59461 | 0.9583 | [0.8586, 1.0594] |
| [M4 Pro](benchmarks/m4-cpu222-unbounded-midgame-main-20261025/summary.json) | 1.56193 | 2.45550 | 1.5721 | [1.3799, 1.7940] |
| [M1](benchmarks/m1-cpu222-unbounded-midgame-main-20261025/summary.json) | 0.95663 | 1.16378 | 1.2165 | [1.0403, 1.3998] |
| [Intel i9](benchmarks/intel-cpu222-unbounded-midgame-main-20261025/summary.json) | 1.27192 | 1.45680 | 1.1454 | [1.0064, 1.2987] |

Intervals compare auto/SAT within each environment. Auto has a larger mean on M4, M1 and Intel, with intervals above one. Relative 95% interval radii range from 10.55% to 15.06%. Individual intervals are not adjusted for multiple comparisons. Valid proofs for every case and precise speed-difference estimates are separate outcomes.

[Paired four-environment report](benchmarks/four-environment-midgame-comparison-20261025.json). Auto starts directly with SAT on the 320 cases below 44 discs; eligible 44-disc cases may also finish in the initial SAT probe. The overall mean does not isolate model-only benefit.

<details>
<summary>WSL breakdown by occupied squares</summary>

| Occupied squares | SAT mean (s) | auto mean (s) | auto/SAT | 95%CI |
|---|---:|---:|---:|---|
| 12 | 0.00421 | 0.00418 | 0.9935 | [0.9650, 1.0210] |
| 20 | 0.00442 | 0.00445 | 1.0070 | [0.9830, 1.0353] |
| 28 | 0.10812 | 0.10509 | 0.9720 | [0.8885, 1.0424] |
| 36 | 0.75857 | 0.83124 | 1.0958 | [0.9536, 1.2630] |
| 44 | 2.22717 | 2.02808 | 0.9106 | [0.7880, 1.0456] |

Each stratum has 80 independent cases and a fixed 20% weight. Individual 95% intervals are not simultaneous coverage. The [original summary JSON](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/summary.json) retains all overall and stratum statistics.

</details>

## Four environments: 20 terminal boards

Each environment completed 120 trials, 480 total. Common complete-case coverage is 20/20 (100%). Independent N remains 20, not 60 per slot. This auxiliary suite is separate from the 400 midgames.

| Environment | SAT mean (s) | auto mean (s) | auto/SAT | 95%CI |
|---|---:|---:|---:|---|
| [WSL](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/summary.json) | 9.20460 | 9.14890 | 0.9939 | [0.7963, 1.2605] |
| [M4 Pro](benchmarks/m4-cpu222-unbounded-endgame-main-20261025/summary.json) | 16.74105 | 43.69341 | 2.6100 | [2.0733, 3.2491] |
| [M1](benchmarks/m1-cpu222-unbounded-endgame-main-20261025/summary.json) | 11.50916 | 31.21702 | 2.7124 | [2.1779, 3.4251] |
| [Intel i9](benchmarks/intel-cpu222-unbounded-endgame-main-20261025/summary.json) | 17.63237 | 32.69917 | 1.8545 | [1.4588, 2.3634] |

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

The [distribution JSON](benchmarks/terminal-time-distribution-20261026.json) retains the calculation rule, every case mean, extremal case IDs, the two median case IDs, separate 60-trial distributions and raw hashes. The table rounds seconds to three decimal places.

Terminal individual 95% intervals are above one for M4, M1 and Intel and include one for WSL. Relative 95% interval radii range from 24.49% to 27.44%. This fixed 20-case auxiliary suite does not establish general terminal-position performance or simultaneous multiple-comparison coverage. A pass in a reference game does not prove that every valid reconstruction needs a pass.

[Paired four-environment report](benchmarks/four-environment-endgame-comparison-20261025.json). Every linked environment folder contains all records, controls, verification and its manifest. The mean tables retain the original NumPy intervals, with [independent CI reproduction reports](benchmarks/validation/). The public standard-library analyzer uses another RNG, so finite-bootstrap endpoints may differ slightly while arithmetic means agree.

## Recorded control deviations and interpretation

The intended nice value was 19; metadata in both suites records **19 for M4/WSL and 20 for M1/Intel**. The [eight-dataset audit](benchmarks/execution-controls-20261026.json) preserves observations rather than rewriting them to the plan. These are runner setup observations, not per-child priority measurements or proof of equivalent scheduler behavior across OSes.

Cross-environment differences combine priority, OS, numerical backend, CPU allocation and background activity. M4 recorded high load and a between-trial diagnostic pause, separate from search time. Whole-program duration and case search costs are different clocks. These results do not isolate CPU speed. 100% common coverage is not a matched-controls or precision guarantee.

Earlier finite-time, Torch 2.6, eight-case and invalid-gate runs are not pooled into these results. No unfinished trial receives a finite failure cost. The corresponding source and existing weights are available in [Release v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0).
