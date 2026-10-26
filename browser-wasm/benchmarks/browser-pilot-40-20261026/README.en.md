# 40-board browser pilot (2026-10-26)

[日本語](README.md)

Actual desktop Chrome on an Apple M4 Pro ran each of three programs once on the same 40 boards. The midgame subset contains the first four cases in each 12/20/28/36/44-disc stratum (20 total); the terminal subset contains the existing 20 cases. [Inputs and selection](../cases.json) retain their original order, without dropping cases after seeing runtimes. The programs share 40 boards: 120 observations are not 120 independent boards.

| Program | Verified reconstructions | Unknown at 60 seconds | Errors |
|---|---:|---:|---:|
| Old auto v1 | 38 / 40 | 2 | 0 |
| Old SAT v2 | 37 / 40 | 3 | 0 |
| Final auto v3 | 40 / 40 | 0 | 0 |

All 115 returned records were also replayed from the standard initial position by the independent [Python array rules implementation](../../../runner/verify.py), without SAT or model dependencies. Every placement, forced pass and final target cell passed, including all 40 v3 records. See [independent-replay.json](independent-replay.json).

## Final v3 times

| Suite | Cases | Mean seconds | Minimum | Median | Maximum |
|---|---:|---:|---:|---:|---:|
| All | 40 | 9.289 | 0.039 | 6.308 | 44.340 |
| Midgame | 20 | 3.596 | 0.039 | 0.852 | 29.132 |
| Terminal | 20 | 14.982 | 1.334 | 9.954 | 44.340 |

All 40 v3 cases finished below 60 seconds on this M4. This is neither a smartphone measurement nor a guarantee for arbitrary boards. V3 changes SAT allocation and adds a formula allowing late passes, so its results do not isolate a CNN effect. Actual inference ran on four v3 cases; one witness came from the guided-search route.

## Measurement and records

[run_browser.py](../run_browser.py) creates a fresh dedicated browser context and directly starts a new Worker for every board. It uses neither UI result history nor Service Workers. Playwright routing enforces same-origin GET requests and disables the HTTP cache. Timing starts just before Worker construction and ends at result receipt, including startup, static-resource fetching, WASM and model preparation. Independent replay after receipt is outside this clock. Do not pool these observations with resident/warmed native measurements. The recorded controller nice value is 19. No Worker CPU throttle or conversion to smartphone speed was applied.

The 60-second watchdog is observational. Expiration terminates the Worker and records `unknown`, never unreachability or a finite failure cost. Old-program found-time summaries are conditional on obtaining a witness; means from different solved sets are not directly comparable. Raw `wall_seconds` records actual observed time including unknown observations; `worker_wall_seconds` is the separate clock returned by the Worker.

Each program directory preserves original `runs.jsonl`, `metadata.json` and `progress.json` bytes. They include witnesses, progress events, per-attempt SAT/inference statistics, environment metadata and before/after asset SHA-256 values. If the watchdog fires before a result arrives, only progress available by then is retained; unfinished internal attempts have no final statistics. Large GET logs are omitted. Their original hashes and aggregates, including zero API requests, are in `network-summary.json`.

[Old auto v1](../prototype-auto-v1.js), [old SAT v2](../prototype-sat-v2.js) and the [final v3 source snapshots](source-snapshots/) are distinct versions identified by the raw metadata hashes. [export-manifest.json](export-manifest.json) identifies distributed files and original records; [summary.json](summary.json) contains all aggregate values. Original raw observations and earlier formal results are unchanged.

This is a **pilot**. It does not include results of the larger formal 400-midgame/20-terminal study with three repetitions per program, which remains pending.
