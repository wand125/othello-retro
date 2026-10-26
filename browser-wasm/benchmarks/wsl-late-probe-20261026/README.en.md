# WSL: SAT restricted to passes in the last12 placements

[日本語](README.md)

This is a post-screening diagnosis of three known terminal boards that were unresolved within60 seconds on M4. Each setting ran once. These deliberately selected hard cases are not a representative success-rate benchmark or a smartphone timing test. No models, CNN or LTO were used.

| Case ID suffix | late12, default options | SAT-directed options |
|---|---:|---:|
| 200028 | Found 9.868s | Unknown 19.115s |
| 200107 | Found 7.821s | Found 7.492s |
| 300185 | Found 14.418s | Unknown 15.905s |

Trials used WSL2, Ryzen 9 9950X, Node24.19, nice19 and guest logical CPUs16–19, with one solver Worker at a time. Default means Kissat4.0.3 defaults; SAT-directed means `target=2,restartint=50`. Both used100,000 conflicts / 1,000,000 decisions. These are work limits, not seconds. Both unknown outcomes returned Kissat0 at a work limit; neither reached the separate60-second observation watchdog.

All four found witnesses were independently replayed and matched all64 target squares. Restricted-formula UNSAT or unknown never establishes general unreachability. A deployed caller must continue with unrestricted SAT when this branch does not find a valid witness. WSL times must not be presented as M4 or smartphone times.

`results.jsonl` retains the six measured rows byte for byte, including every witness, cost and unknown outcome. `conditions.json` is a public allowlist of host conditions, with no SSH endpoints, private IPs, user paths or service configuration. The original input-bank hash is preserved; exact case agreement with the available public bank is documented in `data-provenance.json`. `check_results.py` independently verifies the raw hash, schedule and witnesses.

```sh
python3 browser-wasm/benchmarks/wsl-late-probe-20261026/check_results.py
```

Reproduction requires Rust1.98.0 with the wasm32 target, Python3, Node24, and the existing Kissat/verify artifacts in `browser-wasm/ui`. No ONNX files or model downloads are required, and no binaries are duplicated here. `encoder-source/` preserves the measured experimental wrapper and its five native modules; build this snapshot rather than substituting the current main encoder.

```sh
rustup target add --toolchain 1.98.0 wasm32-unknown-unknown
python3 browser-wasm/benchmarks/wsl-late-probe-20261026/build_encoder.py --require-measured-hash
nice -n 19 taskset -c 16-19 node browser-wasm/benchmarks/wsl-late-probe-20261026/run.cjs --output /tmp/retro-late-new-run
```

`taskset` is a Linux example. Omit it on other systems and record actual conditions. The output directory must be new. If another compiler produces different artifacts, do not silently label them identical: explicitly pass `--allow-artifact-change` for a separate measurement. `RETRO_ENCODER_WASM` can select another compatible encoder. `source-provenance.json` records source hashes and path/output-guard changes from the measured harness; `protocol.json` records limits and order.

Only the `boardWords` bitboard conversion is called from `measured-engine.js`; its old UI search policy is not run. `plan.json` and `run.cjs` select the actual formula and limits. Publication staging did not rerun heavy trials or rebuild the compiler output; explicitly check rebuild identity using the hash comparison above.

Code is [MIT](../../../LICENSE). Synthetic cases follow [BENCHMARK_LICENSE.md](../../../BENCHMARK_LICENSE.md). Reused third-party WASM retains the existing [Kissat/runtime notices](../../ui/kissat.LICENSES.txt) and [Rust runtime notices](../../ui/RUST-LICENSES.txt). This directory does not distribute private server infrastructure or a backend configuration.
