# Uncapped benchmark results

[日本語](BENCHMARK_RESULTS.md) | English

These are completed, independently replayed suites from the frozen [benchmark design](MEASUREMENT_DESIGN.en.md). Midgames and terminal boards are reported separately. Each board is measured three times in each slot. All recorded successful games match the full target board.

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

WSL has completed all 2,520 planned trials. M4, M1 and Intel measurements continue. Completed suites will be added without pooling partial runs into completed results. The tables above compare SAT and auto within WSL. Hardware comparisons require at least 90% common completed-case coverage across all four requested environments.

The original reports use the recorded NumPy bootstrap RNG. The public standard-library analyzer identifies its own RNG, so finite-bootstrap endpoints may differ when reanalyzing these same raw records. Arithmetic means remain the same.

Earlier finite-time, Torch 2.6, eight-case and invalid concurrency-gate runs are not included. These are measurement records; the original reconstruction solver and models are not distributed here.
