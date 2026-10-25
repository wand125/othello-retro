# Benchmark design: four execution environments, 400 midgames and 20 terminal boards

[日本語](MEASUREMENT_DESIGN.md) | English

The fixed benchmark has two separate suites. Each environment runs both program slots three times on every board. Trials and the final exact SAT solve have no time limit. The goal is to finish the entire frozen schedule.

The earlier WSL-only plan with 8-second midgame and 60-second terminal cutoffs is superseded. Unfinished work is not assigned a finite failure cost or PAR2 score.

## Fixed inputs and schedule

| Item | Midgames | Terminal boards |
|---|---:|---:|
| Independent games / boards | 400 | 20 |
| Strata | 12, 20, 28, 36 and 44 occupied squares; 80 each | Full board, reference without passes: 7; full board, reference with passes: 7; early termination: 6 |
| Program slots | `sat`, `auto` | `sat`, `auto` |
| Repeats per board and slot | 3 | 3 |
| Trials per environment | 2,400 | 120 |
| Trials across four environments | 9,600 | 480 |
| Fixed stratum weights | 20% each | 35%, 35%, 30% |
| Trial / final-SAT deadline | None | None |

There is one board per independently seeded game. Repeated runs and multiple prefixes of the same game are not independent input samples. Every main-suite board is reachable from the standard four-disc initial position. This benchmark measures reconstruction; difficult unreachable positions require a separate study. Reference records prove reachability and are never passed to the program under test.

- [Frozen midgame dataset and schedule](benchmarks/study-midgame-cpu222-unbounded-v1.json)
- [Frozen terminal dataset and schedule](benchmarks/study-endgame-cpu222-unbounded-v1.json)
- [Original implementation / protocol hashes](benchmarks/unbounded-manifest.json)

With N occupied squares, N−4 placements have occurred; passes do not increase this count. The midgame strata therefore represent 8, 16, 24, 32 and 40 placements. A reference record containing passes does not establish that every reconstruction requires a pass. The six early terminal positions have 62 discs once and 63 discs five times.

The two suites describe different input distributions. Do not combine them into a single 420-board mean.

## Generation and order

Games choose uniformly among legal moves. Midgame generation is conditioned on reaching the specified occupancy without termination. Rejected seeds and the rule for advancing to the next seed are recorded. Equal stratum weights describe this artificial distribution, not real user inputs or a uniform distribution over all Othello boards.

Terminal boards were sampled before measuring reconstruction performance, from independently generated pools with fixed selection seeds. Terminal and midgame main/pilot inputs are disjoint in board and game seed. Timing and solver success were not used for acceptance or selection. New seeds do not prove disjointness from a model's training data.

Repeats are the outer loop. The frozen schedule randomizes paired-board order and balances which slot runs first within each stratum and repeat. Odd terminal strata alternate the extra first-slot allocation, with ten pairs per first slot overall in every repeat. The uncapped revision preserves the original case and schedule arrays exactly. Do not drop slow cases or reorder them after observing results.

Run one trial at a time in each environment. Do not overlap the two suites or another heavy experiment on the same allocation. Other existing applications remain running; log background load and memory. Load average is not CPU utilization.

## Original four-environment configuration

The baseline comparison uses M4 Mac, M1 Mac, WSL and Intel Mac, with Python 3.12, PyTorch 2.2.2, NumPy 1.26.4, CPU/FP32, two Torch/OMP/BLAS threads, Rust 1.98.0 and Kissat 4.0.3. The `cadical` 0.1.16 crate bundles CaDiCaL 1.9.5. Native executable hashes differ across OS and instruction sets; source, input, schedule and model hashes are checked separately.

WSL benchmark processes use guest logical CPUs 16–19; the public service uses 20–23. Guest topology reports two core IDs for the benchmark's four logical CPUs. This is guest CPU-set separation. Windows-host physical-core exclusivity or pinning has not been configured or verified. macOS affinity is not equivalently pinned. Actual controls, nice values, memory, device/dtype and load are logged. These are execution-configuration comparisons, not isolated causal effects of the CPU or OS.

The original native portfolio prepares three variants: no passes, late passes and general passes. The benchmark gate permits at most two real Kissat processes concurrently. A third job may wait for a slot; gate startup and waiting remain in measured time. The final native call uses `--no-time-limit`, and final Kissat arguments omit `--time` entirely.

Auto can enter the model path at 44 occupied squares or more. Only 80 of the 400 midgame cases are eligible. An eligible trial can still finish in an initial SAT probe without CNN inference. Stage diagnostics distinguish actual completed CNN forwards from direct SAT. The initial two-second probe and twenty-second candidate-SAT probes are algorithm switching policies, not whole-trial limits. Beam search has no global deadline; unsuccessful guidance falls back to unrestricted-time exact SAT on the original target.

The public [generic runner](runner/README.en.md) also accepts other programs. Historical model/source hashes and algorithm settings in the original protocol identify that implementation; another program need not reproduce those internals. Record its own code, artifacts, controls and timing profile. Sharing inputs alone does not establish that all other conditions match.

## Timing

The original model worker loads before timing and remains resident. The standard model receives three fixed, synchronized forwards with batch size 256. The pass model is loaded, but is not claimed to receive the same three-forward warmup. Model loading, warmup and restarts are logged separately.

Trial time runs from request initiation to receipt of the proof subsequently accepted by independent replay. It includes process creation during the trial, IPC, inference, solver switching and gate waiting. Final independent replay is outside this clock. Checking a rejected guided candidate and continuing to exact SAT remains inside it. Public-API network latency and queues are outside this local benchmark. Cleanup, preparation, analysis and whole-program time are reported separately.

The generic runner offers startup-inclusive one-shot and ready-before-timing resident profiles. Do not silently treat them as the same clock. A resident adapter should load and warm its program before reporting `ready`.

## Correctness, interruption and completion

A successful result must replay legally from the initial position, including forced passes, and match all 64 target squares. It need not match the reference game. The checker normalizes legitimately omitted forced passes; it rejects an arbitrary color switch when the current player has a legal move.

Running, paused or interrupted work is unfinished, not a completed timeout. Unknown is not unreachable. Setup errors, process failure, invalid records, target mismatches and an unreachable answer on these known-reachable inputs are recorded separately and stop normal completion. A retry retains its previous attempt history and resumes the same schedule position.

`PAUSE` acts between trials. A manual interruption records consumed work; after resuming, `effective_wall_seconds = wall_seconds + interrupted_work_seconds`. Idle pause time and preparation remain separate. Do not replace unfinished trials with zero, an old cutoff, or another finite penalty. Stop only owned child processes during cleanup.

## Coverage and statistics

Let C contain cases whose two slots and all three repeats have completed and passed verification in every compared run. Report `|C| / planned cases`, per-environment trial counts and stratum coverage. The original four-environment comparison requires at least 90% common coverage, including the slowest environment. This is a minimum for conditional comparison, not a stopping rule or a precision guarantee. Finish the entire frozen schedule.

For each case and slot, first average the three effective times. Average case means within each stratum, then apply the original fixed weights. The primary ratio is the arithmetic mean for the numerator slot divided by the arithmetic mean for the denominator slot. It is not the average of case-wise ratios or a geometric mean. Medians and tail times are secondary.

Use paired, stratified case-cluster bootstrap intervals: retain all compared programs/environments and all repeats of a sampled case together. The original analysis uses 3,000 replicates and seed 730253 with NumPy's RNG. The dependency-free public analyzer uses Python `random.Random` (MT19937), explicitly reports that RNG, and therefore need not reproduce identical finite-bootstrap endpoints. Its percentile endpoints use linear quantiles.

The independent sample sizes remain 400 and 20, not 1,200 and 60. The relative 95%CI radius target of 5% is a reporting target; report a miss as a miss. Do not declare zero uncertainty from a degenerate interval or all-success sample. A Wilson interval, when shown, concerns the separate binary outcome "all repeats for this case succeeded." Twenty terminal cases do not guarantee 5% precision.

A partial common-case estimate is conditional on completed cases. If slow cases remain unfinished, their final times and the full mean remain unknown. Keep original stratum weights and withhold an overall estimate when a stratum has no common cases. Repeatedly checking for a narrow interval is not a reason to end early. Case bootstrap does not remove temporal load correlations, establish another-day reproducibility, or turn individual 95% intervals into simultaneous coverage.

## Published data and scope

Completed results are in [BENCHMARK_RESULTS.en.md](BENCHMARK_RESULTS.en.md). Historical finite-time, Torch 2.6, eight-case, pilot and Cloud Run results remain separate. Runs affected by the previous concurrency-gate bug are invalidated and are not included.

Dataset SHA-256 values:

| Suite | SHA-256 |
|---|---|
| Midgame | `98b78ec6b2b02d4b8a6986441109c0d4b70d257b9b88be3b535c49a7af740909` |
| Terminal | `9e6e594ce89e3e1b30bbb5072b9bf6dcd202195303d5c0c729a6b95588b0d409` |

Cases, references, schedules, verified records, timing, controls and hashes are public. The reusable measurement runner is published separately from the original reconstruction program and model. See [runner documentation](runner/README.en.md), [license scope](BENCHMARK_LICENSE.md) and [publication scope](CODE_PUBLICATION.en.md).

## Completed runs and deviations (2026-10-26)

All four environments completed both frozen suites: 2,400 midgame trials and 120 terminal trials per environment, 10,080 trials in total. Every proof was independently replayed. Common complete-case coverage is 400/400 and 20/20 respectively; the suites are not pooled.

The intended nice value was 19; metadata records 19 on M4/WSL and 20 on M1/Intel for both suites. The measurements retain this deviation rather than claiming exact priority matching. OS priority semantics and all child-process priorities were not established as equivalent. See the [execution-controls audit](benchmarks/execution-controls-20261026.json) and [results](BENCHMARK_RESULTS.en.md). Complete coverage does not guarantee matched controls or 5% CI precision.
