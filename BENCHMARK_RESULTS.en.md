# Uncapped benchmark results

[日本語](BENCHMARK_RESULTS.md) | English

These are completed, independently replayed suites from the frozen [benchmark design](MEASUREMENT_DESIGN.en.md). Midgames and terminal boards are reported separately. Each board is measured three times in each slot. All recorded successful games match the full target board.

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

## Remaining measurements and interpretation

The midgame suite is complete in all four environments. WSL also finished the terminal suite; M4, M1 and Intel terminal measurements continue. Terminal comparisons require at least 90% common completed-case coverage within that suite.

The original reports use the recorded NumPy bootstrap RNG. The public standard-library analyzer identifies its own RNG, so finite-bootstrap endpoints may differ when reanalyzing these same raw records. Arithmetic means remain the same.

Earlier finite-time, Torch 2.6, eight-case and invalid concurrency-gate runs are not included. These are measurement records; the original reconstruction solver and models are not distributed here.
