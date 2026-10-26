# Browser measurements through the common runner

`adapter.py` is a resident JSONL adapter running the static application in real Chrome/Chromium. It supports SAT and lightweight Auto. It requires Python 3.10+, Python Playwright, Chrome/Chromium, and a complete static snapshot including both models. It installs nothing and contacts no external service.

Freeze a separate snapshot before measuring. The example `browser-programs.json` uses the repository root as `cwd` and reads `browser-wasm/ui`. For a formal run, replace **both** programs' `--ui-dir` and all thirteen `artifacts[].path` entries with the same immutable snapshot. Adjust `cwd` if moving the configuration. Replace `python3` with a Playwright-enabled interpreter if necessary, and optionally append `--chrome PATH` to each command. See the [browser README](../README.en.md) for models and static builds.

```sh
python3 runner/benchmark.py run \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --config browser-wasm/benchmarks/browser-programs.json \
  --split pilot --output .runs/browser-pilot

# After checking the pilot: main has 400 fixed cases, three repeats per method.
# Measure the 20 terminal cases separately with the endgame bank's main split.
python3 runner/benchmark.py run \
  --bank benchmarks/study-endgame-cpu222-unbounded-v1.json \
  --config browser-wasm/benchmarks/browser-programs.json \
  --split main --output .runs/browser-endgame
```

The common [runner](../../runner/README.en.md) owns order, repeats, resume, logs, and independent Python replay. Resume with the same command/output plus `--resume`. Never count unfinished trials as successful finite costs or unreachable verdicts. This is separate from the observational deadline used by the frozen 40-case `run_browser.py`; that code and its results remain unchanged.

## Timing and isolation

`ready` follows Chrome, loopback server, and empty verifier-page preparation. Every request creates a fresh Worker, including WASM and any needed model fetch/initialization in the trial. HTTP caching, Service Workers, history, and saved witnesses are disabled. This differs from native resident runs retaining a warm model; do not pool them merely because both use the resident protocol. `stats.timing_profile` is `fresh-worker-cold-wasm-models-browser-ready-v1`. The common runner's clock also includes JSONL transport and the page's extra JS replay. `stats.proof_receipt_seconds` is an auxiliary clock ending at Worker response receipt.

There is **no wall deadline**. Restricted candidate-search limits do not terminate the complete general-SAT fallback. Only confirmed general-formula UNSAT yields `unreachable`. Errors return `error` and stop the runner; cancellation never becomes UNSAT. Ctrl-C/SIGTERM closes the adapter's browser and server; the common runner additionally cleans its own process group.

Workers use CPU/WASM and FP32, one-thread inference, without GPU. A fresh browser context permits only same-loopback-origin GET requests for thirteen allowlisted assets. WebSocket, CDN, and API access are rejected. All thirteen asset SHA-256 hashes and the actual Chrome version appear in ready and every result's stats. Distribution conditions remain those in the browser README and bundled notices.

The adapter accepts one `{"id":"trial-1","board":"64 X/O/- cells"}` object per stdin line. Stdout contains JSONL only: first `{"event":"ready","stats":{...}}`, then `{"event":"result","id":"trial-1","payload":{"status":"found","moves":["d3"],"stats":{...}}}`. Found witnesses are independently replayed by the Worker, the harness page, and the common runner. Unreachable verdicts have no witness.

## Small acceptance tests

```sh
python3 -m unittest discover -s browser-wasm/benchmarks -p test_adapter.py -v
RETRO_BROWSER_TEST_UI=/path/to/immutable-snapshot \
  python3 -m unittest discover -s browser-wasm/benchmarks -p test_adapter.py -v
```

The opt-in browser test runs real 5/12-stone solves, immediate impossibility, invalid input, and shutdown for SAT and Auto. Its 45-second test-supervision wait is not an adapter solver deadline. These tests do not run the formal 400/20 banks or establish smartphone speed.

Code/tests: MIT. Reference-case provenance and licenses are in `../tests/cases.json`.
