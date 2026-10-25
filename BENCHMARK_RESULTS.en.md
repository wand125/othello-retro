# Uncapped benchmark results

[日本語](BENCHMARK_RESULTS.md) | English

Updated 2026-10-26. All four environments completed the entire schedule: 10,080 verified trials in total. These are completed, independently replayed suites from the frozen [benchmark design](MEASUREMENT_DESIGN.en.md). Midgames and terminal boards are reported separately. Each board is measured three times in each slot. All recorded successful games match the full target board.

## Four environments: 400 midgames

All four environments completed 2,400 trials each (9,600 total). Every record passed independent legality and target checks. Common complete-case coverage is 400/400 (100%).

| 環境 / Environment | SAT平均 / mean (s) | auto平均 / mean (s) | auto/SAT | 95%CI |
|---|---:|---:|---:|---|
| [WSL](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/summary.json) | 0.62050 | 0.59461 | 0.9583 | [0.8586, 1.0594] |
| [M4 Pro](benchmarks/m4-cpu222-unbounded-midgame-main-20261025/summary.json) | 1.56193 | 2.45550 | 1.5721 | [1.3799, 1.7940] |
| [M1](benchmarks/m1-cpu222-unbounded-midgame-main-20261025/summary.json) | 0.95663 | 1.16378 | 1.2165 | [1.0403, 1.3998] |
| [Intel i9](benchmarks/intel-cpu222-unbounded-midgame-main-20261025/summary.json) | 1.27192 | 1.45680 | 1.1454 | [1.0064, 1.2987] |

Intervals compare auto and SAT within each environment. Auto has a larger mean on M4, M1 and Intel, with individual intervals above one. All four miss the 5% relative-CI-radius target. Individual intervals are not adjusted for multiple comparisons.

Differences include OS, native numerical backends, scheduling and background load. M4 had a logged between-trial diagnostic pause, separate from search time. Distinguish whole-program duration from corresponding per-case search costs. Actual model use in the 44-disc stratum and direct SAT on the other 320 cases also require separate analysis.

The [paired four-environment report](benchmarks/four-environment-midgame-comparison-20261025.json) is reproducible with the public standard-library analyzer. The table retains the original NumPy intervals; finite-bootstrap endpoints can vary slightly with the RNG, while means agree. Each linked dataset contains all records, controls, load and hashes.

[Independent reports reproducing the original confidence intervals](benchmarks/validation/) are also available.

## Four environments: 20 terminal boards

All four environments completed 120 trials each (480 total), with every game independently replayed against its full target. Common complete-case coverage is 20/20 (100%). The independent N remains 20, not 60 per slot. This suite is analyzed separately from the 400 midgames.

| Environment | SAT mean (s) | auto mean (s) | auto/SAT | 95%CI |
|---|---:|---:|---:|---|
| [WSL](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/summary.json) | 9.20460 | 9.14890 | 0.9939 | [0.7963, 1.2605] |
| [M4 Pro](benchmarks/m4-cpu222-unbounded-endgame-main-20261025/summary.json) | 16.74105 | 43.69341 | 2.6100 | [2.0733, 3.2491] |
| [M1](benchmarks/m1-cpu222-unbounded-endgame-main-20261025/summary.json) | 11.50916 | 31.21702 | 2.7124 | [2.1779, 3.4251] |
| [Intel i9](benchmarks/intel-cpu222-unbounded-endgame-main-20261025/summary.json) | 17.63237 | 32.69917 | 1.8545 | [1.4588, 2.3634] |

These are within-environment auto/SAT ratios and the original individual NumPy 95% intervals. Intervals are above one for M4, M1 and Intel and include one for WSL. All four miss the 5% relative-radius target. This fixed 20-case auxiliary suite does not establish general terminal-position performance or simultaneous multiple-comparison coverage. A pass in a reference game does not prove that every valid reconstruction requires a pass.

The [paired four-environment report](benchmarks/four-environment-endgame-comparison-20261025.json) and [independent reproduction of every original CI](benchmarks/validation/) are available. Every linked environment folder also contains all records, metadata, verification and a manifest.

## Recorded control deviations

The intended nice value was 19. Metadata for both suites records **19 for M4/WSL and 20 for M1/Intel**. The [execution-controls audit](benchmarks/execution-controls-20261026.json) lists all eight datasets. Observations were preserved rather than rewritten to match the plan. These are runner setup observations, not per-child priority measurements or proof of equivalent scheduler behavior across operating systems.

Within-environment SAT/auto results describe that recorded configuration. Cross-environment differences combine the priority deviation, OS, numerical backend, CPU allocation and background activity. M4 also recorded high background load. These results do not isolate CPU speed or model-only effects. 100% common coverage establishes matched inputs, not identical execution controls or a precision guarantee.

## WSL: 400 midgames

Both SAT and auto completed **1200/1200** trials with legal matching game records. There are **400 independent cases**; repeats do not triple that sample size.

| Slot | Verified trials | Mean search wall time |
|---|---:|---:|
| SAT | 1200/1200 | 0.62050 s |
| auto | 1200/1200 | 0.59461 s |

The auto/SAT ratio of arithmetic means is **0.95828**, with paired stratified case-cluster bootstrap 95%CI **[0.85859, 1.05939]**. The interval includes one, so this experiment does not establish a speed advantage. Its relative CI radius is 10.55%, missing the 5% target. Correctly reconstructing every record and precisely estimating a speed difference are separate outcomes.

Whole-program duration, including setup and analysis: 1479.71 seconds.

| Occupied squares | SAT mean (s) | auto mean (s) | auto/SAT | 95%CI |
|---|---:|---:|---:|---|
| 12 | 0.00421 | 0.00418 | 0.9935 | [0.9650, 1.0210] |
| 20 | 0.00442 | 0.00445 | 1.0070 | [0.9830, 1.0353] |
| 28 | 0.10812 | 0.10509 | 0.9720 | [0.8885, 1.0424] |
| 36 | 0.75857 | 0.83124 | 1.0958 | [0.9536, 1.2630] |
| 44 | 2.22717 | 2.02808 | 0.9106 | [0.7880, 1.0456] |

Overall stratum weights are 20% each. Individual 95% intervals are not simultaneous coverage. Auto starts directly with SAT on the 320 cases below 44 discs. The overall mean is not a stand-alone estimate of CNN benefit.

[Every trial and reconstructed record](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/runs.jsonl) · [Summary and intervals](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/summary.json) · [Environment](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/metadata.json) · [Independent verification](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/verification.json) · [Hashes](benchmarks/wsl-cpu222-unbounded-midgame-main-20261025/manifest.json)

## WSL: 20 terminal boards

Both SAT and auto completed **60/60** trials with legal matching game records. There are **20 independent cases**; repeats do not triple that sample size.

| Slot | Verified trials | Mean search wall time |
|---|---:|---:|
| SAT | 60/60 | 9.20460 s |
| auto | 60/60 | 9.14890 s |

The auto/SAT ratio of arithmetic means is **0.99395**, with paired stratified case-cluster bootstrap 95%CI **[0.79626, 1.26047]**. The interval includes one, so this experiment does not establish a speed advantage. Its relative CI radius is 26.81%, missing the 5% target. Correctly reconstructing every record and precisely estimating a speed difference are separate outcomes.

Whole-program duration, including setup and analysis: 1103.95 seconds.

This 20-case suite is auxiliary and does not guarantee the same precision as the 400 midgame cases.

[Every trial and reconstructed record](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/runs.jsonl) · [Summary and intervals](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/summary.json) · [Environment](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/metadata.json) · [Independent verification](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/verification.json) · [Hashes](benchmarks/wsl-cpu222-unbounded-endgame-main-20261025/manifest.json)

## Completion and interpretation

Both suites are complete in all four environments, with 100% common coverage separately for 400 midgames and 20 terminal boards. No unfinished trial was assigned a finite timeout cost. These are descriptive comparisons of the recorded configurations, including the disclosed priority deviation.

The original reports use the recorded NumPy bootstrap RNG. The public standard-library analyzer identifies its own RNG, so finite-bootstrap endpoints may differ when reanalyzing these same raw records. Arithmetic means remain the same.

Earlier finite-time, Torch 2.6, eight-case and invalid concurrency-gate runs are not included. The corresponding reconstruction source and existing weights are available in [Release v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0); source and model manifests identify their relationship to these unchanged measurements.
