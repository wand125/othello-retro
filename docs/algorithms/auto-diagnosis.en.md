# Auto diagnosis and the 32-case lightweight comparison

[日本語](auto-diagnosis.md) | [English](auto-diagnosis.en.md)

On the selected WSL cases, lightweight auto reduced mean time for the 20 terminal positions. Its difference from old auto on the 12 midgame positions remains uncertain. This changes inference, candidate search and terminal routing without retraining checkpoints. It does not replace the existing 400/20-case, four-environment, 10,080-trial benchmark.

## Why hit rate alone did not explain cost

In the original WSL logs, all 75 midgame CNN trials (25 independent cases) and all 36 terminal CNN trials (12 cases) returned a guided witness before final general-SAT fallback. Conditional guided hit rates were 75/75 and 36/36. These denominators exclude initial-probe hits and fallback without CNN. They are not classification accuracy, AUC or individual-candidate precision.

A successful candidate route can still cost more than direct SAT. The original counters do not retain stage durations, so those costs cannot be reconstructed precisely. In the new diagnosis, both auto variants executed CNN in the same 45 case×repeat pairs. Old/lightweight recorded 18,048/7,167 forward calls and 310.777/107.119 total seconds in the score pipeline. That pipeline includes feature construction, tensor work and inference. Fewer candidates/calls and inference optimization are combined here; this does not isolate fusion. `planes` and `cnn_forward` are inside `score_pipeline`; `beam` includes score and undo. Do not add these nested timers.

## Algorithm changes

- Clone eval-mode CPU models, fold Conv–BatchNorm and use channels-last. Checkpoint file hashes remain unchanged. Runtime coefficients are transformed, but there is no retraining or checkpoint overwrite.
- Reduce reverse search to width 16, one symmetry, refine 0 and one stage. Retain candidate SAT and general exact fallback; accept only strictly replayed witnesses.
- Route incomplete terminal boards directly to general SAT after checking that neither color has a legal move.
- Include the native correction for an incomplete terminal target's absent next-player marker. Baseline and lightweight native binary hashes differ.
- Independently replay from the standard opening, rejecting voluntary passes and illegal color switching.

`baseline` combines old native/inference/search; `lightweight` combines corrected native, fused inference, narrower policy and routing. The three-variant experiment cannot identify each change's separate causal effect. Restricted-probe failure does not establish general unreachability. Internal 2-second probe and 20-second candidate-SAT settings request limits per Kissat invocation, not deadlines for the entire chunk including CNF setup and gate queue. Final general SAT and overall trials have no time limit.

## Results: 32 independent cases, three repetitions

Twelve 44-disc cases were selected from the existing 80 cases by a fixed hash ordering of IDs, independently of observed time. They were paired with all 20 fixed terminal cases. Each case ran `sat`, `baseline` and `lightweight` three times, with rotating order. All 288 trials returned legal witnesses. Each case places each variant in every order slot once. Each variant has 96 trials, but the independent-case count remains 32.

| Suite / independent cases | SAT (s) | Old auto (s) | Lightweight (s) | Light / old ratio [95% CI] | Light / SAT ratio [95% CI] |
|---|---:|---:|---:|---:|---:|
| 44-disc midgame /12 | 2.5873 | 1.7012 | 1.5776 | 0.9273 [0.7990, 1.0760] | 0.6097 [0.4677, 0.8430] |
| Terminal /20 | 9.9502 | 9.9076 | 6.8658 | 0.6930 [0.5646, 0.8511] | 0.6900 [0.5252, 0.9245] |

Times are equal-case averages of each case's three-repeat accepted-proof receipt wall time. Final independent replay is outside this clock; instrumentation is inside it. The 95% intervals concern the mean **ratio**: 5,000 stratified paired case-cluster bootstrap samples retain every repeat and variant together. The midgame light/old interval includes 1. Terminal strata comprise seven full boards with no reference pass, seven with a reference pass, and six incomplete terminals. A reference pass does not imply all possible witnesses need a pass. The fixed schedule was completed without CI-based stopping.

| Route (96 trials per auto variant) | Old auto | Lightweight |
|---|---:|---:|
| Initial SAT-probe hit | 33 | 33 |
| Guided hit after CNN | 45 | 39 |
| Candidate miss after CNN → general SAT | 0 | 6 |
| Unplanned fallback without CNN | 18 | 0 |
| Planned incomplete-terminal → general SAT | 0 | 18 |

The CNN sets match: 45 trials across 15 independent cases. Lightweight conditional guided hit is 39/45 (86.7%), versus 45/45 for old auto. The six misses are two cases repeated three times; general SAT found valid witnesses for all. Planned exact routing covers six cases×three repetitions and is excluded from CNN-failure and model-eligible denominators. Midgame hits are 9/9 for both; terminal hits are 36/36 old and 30/36 lightweight. 100% final found rate describes the complete pipeline including exact SAT.

## Conditions, interruption costs and limits

WSL, Python 3.12.13, Torch 2.2.2+cpu/NumPy1.26.4, CPU FP32, two inference/BLAS threads, nice 19, guest CPUs 16–19 and Kissat 4.0.3 with at most two real SAT processes were used. Each variant's resident models received three batch 256 warmups before timing. The table does not measure cold startup or downloads. Separate guest CPU sets are recorded; Windows-host physical-core exclusivity is unverified.

A control interruption retained 42 durable rows. Identical algorithm, weight, native and environment hashes were checked before resuming at trial 43; only the driver gained resume support. Both driver sources are retained. Executed program wall was 112.525822+1,715.195025=1,827.720847 seconds. Accepted 288-trial time totals 1,814.591218 seconds; combined model preparation is 0.600065 seconds. The 13.129629-second residual contains preparation, replay, serialization, cleanup and interrupted work. Exact unfinished-trial time was not persisted. Neither the residual nor the last-row boundary interval is assigned to a completed case, failure or timeout. The 3,628.747476-second calendar span includes the pause and is recorded separately.

This is an exploratory fixed 32-case comparison. Floating-point transformations and narrower search can alter rankings and paths. Full rankings, score/NaN distributions and true candidate labels were not logged. The experiment does not measure classifier accuracy or performance on arbitrary new boards, and it does not resolve missing original training data.

## Verification material

- [Original rows, metadata and pre-resume prefix (JSON)](../../benchmarks/native-lightweight-32x3-20261026/data/run/metadata.json), [independent analysis (JSON)](../../benchmarks/native-lightweight-32x3-20261026/data/analysis/analysis.json), [additional audit (JSON)](../../benchmarks/native-lightweight-32x3-20261026/data/analysis/independent-audit.json)
- [Export correspondence (JSON)](../../benchmarks/native-lightweight-32x3-20261026/EXPORT_MANIFEST.json): main raw files remain byte-identical; removed audit PID/operational fields and original/exported hashes are explicit.
- Measured source snapshots, both driver versions, typed misses and stage timers are retained. Model/native binary payloads are excluded from Git; use measured hashes and the existing [weight Release](https://github.com/wand125/othello-retro/releases/tag/v0.1.0).

Recompute into a new directory:

```sh
python3 solver/benchmarks/analyze_auto_diagnostic.py --input benchmarks/native-lightweight-32x3-20261026/data/run --midgame-bank benchmarks/study-midgame-cpu222-unbounded-v1.json --endgame-bank benchmarks/study-endgame-cpu222-unbounded-v1.json --output /tmp/native-lightweight-analysis-new
```

## Production application is a separate functional check

The native WSL service has adopted `lightweight`/`fused_channels_last`. Its recorded smoke environment is Torch 2.6.0 CPU / NumPy 2.2.6, distinct from the Torch 2.2.2 / NumPy 1.26.4 comparison above. Recorded 44-disc, incomplete-terminal and full-terminal smoke witnesses passed strict replay; the installed runner also passed a 44-disc check. Health, existing resource controls and database counts remained unchanged. These single functional checks are not speed comparisons. The [allowlisted rollout summary (JSON)](../../benchmarks/native-lightweight-32x3-20261026/data/analysis/production-functional-summary.json) records their evidence hashes without copying service configuration, credentials or private paths. The browser SAT/WASM edition remains a separate implementation.
