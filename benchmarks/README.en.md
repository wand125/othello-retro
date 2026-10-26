# Benchmark results

[日本語](README.md) | [English](README.en.md)

Updated 2026-10-26. The two main tables answer **whether the native lightweight update improves speed** and **whether Auto improves speed in the browser**.

Each row compares methods on the same environment and boards. Read horizontally to compare the methods. Lower times are faster. A ratio of 0.70 means about 30% less time; 1.20 means about 20% more. A 95% confidence interval (CI) containing one does not establish a speed difference.

<a id="native-comparison"></a>

## 1. Lightweight update: three methods on the same WSL host

**Each board is solved three times by SAT, old native Auto and lightweight native Auto.** SAT is the reference for whether Auto provides a benefit. The terminal comparison is complete. The midgame study expands the earlier twelve selected 44-disc boards to the frozen bank of 400; all three methods are measured anew.

| Inputs | SAT mean (s) | Old native Auto mean (s) | Lightweight native Auto mean (s) | Lightweight / old [95% CI] | Status |
|---|---:|---:|---:|---|---|
| All 400 midgames | — | — | — | — | Running; 3,600 trials |
| 80 boards with 44 discs, within those 400 | — | — | — | — | Subset of the row above |
| 20 terminal boards | 9.9502 | 9.9076 | 6.8658 | 0.6930 [0.5646, 0.8511] | 180/180 histories verified |

**The current conclusion: lightweight Auto reduced the terminal mean by about 31%; the 400-midgame result is pending.**

The overall midgame row represents practical performance across 80 boards each with 12, 20, 28, 36 and 44 discs. Below 44 discs both Auto variants go straight to SAT, so the update is mainly evaluated in the 44-disc row. Even there, successful SAT preprobes do not use model inference. Actual model use, guided hits and exact-SAT fallbacks are reported separately. The 80 boards are part of the 400, not additional cases.

Method order rotates while CPU allocation, inference threads, weights and SAT concurrency are held fixed. There is no overall trial or final general-SAT deadline. Timing starts after model preparation; returned histories are independently replayed for legality and an exact board match. The update combines native fixes, inference, candidate-search and routing changes; it is not a model-only effect.

[400-midgame plan (JSON)](native-lightweight-midgame-400x3-20261026-plan.json) · [Existing 32-case conditions, including terminal boards](../docs/algorithms/auto-diagnosis.en.md) · [Existing analysis (JSON)](native-lightweight-32x3-20261026/data/analysis/analysis.json) · [All 288 existing histories (生データ)](native-lightweight-32x3-20261026/data/run/runs.jsonl).

<a id="browser-comparison"></a>

## 2. Browser: SAT and Auto on the same M4 Pro and Chrome

This is **browser Auto v3**. It uses the same source weights as native lightweight Auto, with different search settings and runtime. These are distinct versions.

| Inputs | Browser SAT v3 mean (s) | Browser Auto v3 mean (s) | Auto / SAT [95% CI] | Status |
|---|---:|---:|---|---|
| 400 midgames | 1.5870 | 1.4319 | 0.9023 [0.8279, 0.9728] | 2,400/2,400 histories verified |
| 20 terminal boards | 16.4185 | 17.4604 | 1.0635 [0.9815, 1.1851] | 120/120 histories verified |

**Auto reduced the mean by about 9.8% across 400 midgames. No speed advantage is established on the 20 terminal boards.** Each method has three repeats; all 2,520 returned histories passed independent replay. The speed difference concerns the whole Auto v3 pipeline, not the model alone.

[400-midgame analysis (JSON)](m4-browser-wasm-v3-midgame-main-20261026/summary.json) · [All 2,400 histories (生データ)](m4-browser-wasm-v3-midgame-main-20261026/runs.jsonl) · [Independent verification (JSON)](m4-browser-wasm-v3-midgame-main-20261026/verification.json).

Browser timing includes fresh-Worker WASM and any required model loading; native timing starts after model preparation. Dividing times across these two tables does not establish an implementation speed multiplier. These desktop measurements also do not establish smartphone completion within one minute.

<details>
<summary>Browser terminal minimum, median, maximum, timing conditions and raw data</summary>

Actual M4 Pro / Chrome 155.0.8059.86. Same 20 independent terminal positions, three SAT and three Auto observations each; **120/120 histories independently verified**. No overall trial or final general-SAT deadline.

| Program | Verified | Mean (s) | Minimum case mean | Median case mean | Maximum case mean |
|---|---:|---:|---:|---:|---:|
| Browser SAT v3 | 60 / 60 | 16.4185 | 1.360 | 10.771 | 46.979 |
| Browser Auto v3 | 60 / 60 | 17.4604 | 1.421 | 12.644 | 67.758 |

Minimum, median and maximum are across the 20 per-case means of three repeats, not 60 individual trials. Auto/SAT ratio is 1.0635, 95% CI [0.9815,1.1851]; it includes one. Each trial starts a fresh Worker, with WASM and any needed model loading included; Chrome startup is preparation. CPU/FP32, one inference thread, HTTP cache and Service Workers disabled.

The 400-midgame bank also completed all 2,400 trials. [Conditions](../docs/benchmarks/browser.en.md) · [Summary (JSON)](m4-browser-wasm-v3-endgame-main-20261026/summary.json) · [All 120 histories (生データ)](m4-browser-wasm-v3-endgame-main-20261026/runs.jsonl) · [Runtime/hashes (JSON)](m4-browser-wasm-v3-runtime-20261026.json).

</details>

## 3. Reference: original native version across four environments

These are pre-update records. Compare old Auto with SAT within each environment; do not combine these cells with the new WSL study or browser results.

<details>
<summary>M4 Pro, M1, WSL and Intel i9: 400 midgames and 20 terminal boards</summary>

These results use the **old native Auto, before the lightweight update**. Each environment completed 400 midgames and 20 terminal boards, SAT/Auto three times each: **10,080 verified histories**. Three repeats do not multiply the independent sample size.

### 400 midgames

| Environment | SAT mean (s) | Old native Auto mean (s) | Auto/SAT | 95% CI |
|---|---:|---:|---:|---|
| WSL | 0.62050 | 0.59461 | 0.9583 | [0.8586, 1.0594] |
| M4 Pro | 1.56193 | 2.45550 | 1.5721 | [1.3799, 1.7940] |
| M1 | 0.95663 | 1.16378 | 1.2165 | [1.0403, 1.3998] |
| Intel i9 | 1.27192 | 1.45680 | 1.1454 | [1.0064, 1.2987] |

### 20 terminal boards

| Environment | SAT mean (s) | Old native Auto mean (s) | Auto/SAT | 95% CI |
|---|---:|---:|---:|---|
| WSL | 9.20460 | 9.14890 | 0.9939 | [0.7963, 1.2605] |
| M4 Pro | 16.74105 | 43.69341 | 2.6100 | [2.0733, 3.2491] |
| M1 | 11.50916 | 31.21702 | 2.7124 | [2.1779, 3.4251] |
| Intel i9 | 17.63237 | 32.69917 | 1.8545 | [1.4588, 2.3634] |

Old Auto was slower than SAT on M4 Pro, M1 and Intel i9; the WSL difference was uncertain. These are the results before the lightweight update.

Priority, OS, backend and background-load differences are recorded in the detailed report. These are not hardware-only rankings. This original study also has no overall trial or final general-SAT deadline.

[Detailed results and terminal distributions](../docs/benchmarks/results.en.md#midgame-results) · [Midgame aggregate (JSON)](four-environment-midgame-comparison-20261025.json) · [Terminal aggregate (JSON)](four-environment-endgame-comparison-20261025.json) · [Terminal distributions (JSON)](terminal-time-distribution-20261026.json).

</details>

## 4. Preliminary experiments and diagnostics

<details>
<summary>Lightweight Auto: twelve midgames before expansion to the 400-case study</summary>

| Inputs | SAT mean (s) | Old native Auto mean (s) | Lightweight native Auto mean (s) | Lightweight / old [95% CI] |
|---|---:|---:|---:|---|
| Twelve selected 44-disc boards | 2.5873 | 1.7012 | 1.5776 | 0.9273 [0.7990, 1.0760] |

All 108 histories from three repeats were verified. The interval includes one, so the advantage was uncertain. These twelve cases do not establish overall midgame performance; the new 400-case study above addresses that question. [Conditions and analysis](../docs/algorithms/auto-diagnosis.en.md) · [Analysis (JSON)](native-lightweight-32x3-20261026/data/analysis/analysis.json).

</details>

<details>
<summary>Browser 40-case preliminary comparison: three versions, one observation per case</summary>

| Browser program | Verified histories | Unknown at 60s | Errors |
|---|---:|---:|---:|
| Auto v1, old | 38 / 40 | 2 | 0 |
| SAT v2, old | 37 / 40 | 3 | 0 |
| Auto v3, improved | 40 / 40 | 0 | 0 |

v3 mean/median/maximum: 9.289 / 6.308 / 44.340 seconds. All 115 returned histories across the three versions were independently replayed. There are 40 independent positions, not 120. The watchdog means unknown, not unreachability. This one-repeat driver/profile is separate from the formal study above.

[Full tables and conditions](../browser-wasm/benchmarks/browser-pilot-40-20261026/README.en.md) · [Summary (JSON)](../browser-wasm/benchmarks/browser-pilot-40-20261026/summary.json).

</details>

<details>
<summary>Prototype using native Auto candidate settings: WSL Node, three boards</summary>

| Case suffix / stones | A: current browser Auto v3 | B: native-candidate prototype |
|---|---:|---:|
| 400000 / 44 | Found 4.217s | Found 6.896s |
| 200001 / 64 | Found 3.964s | Unknown at 60.018s |
| 300002 / 36 | Found 0.557s | Found 2.947s |

Six observations, one per configuration and case; all five returned histories were independently verified. B did not improve speed in these three pairs. It uses width 16, parent cap 4 and no shortlist before CNN inference. The SAT preprobe policy also changed, so this is neither an isolated width experiment nor an equivalent native port. The runtime is WASM under WSL Node, not Chrome or a phone.

[Settings, stages and limitations](../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/README.en.md) · [Summary (JSON)](../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/summary.json) · [All six observations (生データ)](../browser-wasm/benchmarks/wsl-native-geometry-pilot-20261026/results.jsonl).

</details>

<details>
<summary>WSL late-pass diagnosis: three selected hard boards, two settings</summary>

| Case suffix | Default late12 | SAT preset |
|---|---:|---:|
| 200028 | Found 9.868s | Unknown 19.115s |
| 200107 | Found 7.821s | Found 7.492s |
| 300185 | Found 14.418s | Unknown 15.905s |

Four legal histories, two work-limit unknowns. Each configuration ran once with 100,000 conflicts / 1,000,000 decisions. These are post-hoc selected hard cases, not a representative success-rate or phone-speed sample.

[Reproduction](../browser-wasm/benchmarks/wsl-late-probe-20261026/README.en.md) · [Summary (JSON)](../browser-wasm/benchmarks/wsl-late-probe-20261026/summary.json).

</details>

<details>
<summary>Historical 8-case comparison: three repetitions, 60-second trial requests</summary>

| Environment | Model loading | SAT correct / trials | Old Auto correct / trials | Unknowns |
|---|---|---:|---:|---:|
| Mac CPU | Included | 23 / 24 | 13 / 24 | 12 |
| WSL CPU | Included | 24 / 24 | 24 / 24 | 0 |
| Cloud Run CPU | Included | 24 / 24 | 21 / 24 | 3 |
| WSL CPU | Preloaded | — | 24 / 24 | 0 |

168 observations in total. Correct decisions include the sound missing-center rejection as well as valid histories. Torch 2.6/NumPy 2.2.6 and finite-time conditions are separate from the formal unbounded banks.

[Per-case tables and conditions](../docs/history/comparison-3x.md) · [Mac (JSON)](results/mac-cpu3-20261025/summary.json) · [WSL (JSON)](results/wsl-cpu3-20261025/summary.json) · [Cloud Run (JSON)](results/cloud-cpu3-20261025/summary.json) · [Warm WSL (JSON)](results/wsl-cpu3-warm-20261025/summary.json).

</details>

## Reproduce and inspect data

[Common runner](../runner/README.en.md) · [Independent verification](../runner/VALIDATION.en.md) · [Browser adapter](../browser-wasm/benchmarks/README.en.md) · [Measurement design](../docs/benchmarks/design.en.md).

- [Frozen 400-midgame bank and schedule (JSON)](study-midgame-cpu222-unbounded-v1.json), with ten separate pilot positions.
- [Frozen 20-terminal bank and schedule (JSON)](study-endgame-cpu222-unbounded-v1.json).
- [Eight historical fixed inputs (JSON)](cases.json).

Native formal raw folders use `{m4,m1,wsl,intel}-cpu222-unbounded-{midgame,endgame}-main-20261025/`; browser formal results use `m4-browser-wasm-v3-{endgame,midgame}-main-20261026/`. Existing inputs, schedules and raw bytes are retained. Reference-lookup fixtures test the harness, not solver performance. [Data terms](../BENCHMARK_LICENSE.md).
