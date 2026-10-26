# WSL Node pilot: native candidate-search settings in a browser prototype

[日本語](README.md)

**This is neither a formal benchmark nor an equivalent native port.** Three known boards ran once each under canonical browser Auto A and a native-geometry prototype B. The host was WSL2/Ryzen9950X/Node24.19, with ONNX Runtime WASM FP32, one thread, nice19 and guest CPUs16–19. These are not Chrome, M4 or smartphone measurements.

| Board | A, canonicalV3 | B, native-geometry prototype |
|---|---:|---:|
| 44 discs400000 | Found4.217s, CNN0 | Found6.896s, CNN28calls/5,509items |
| 64 discs200001 | Found3.964s, CNN0 | Unresolved at60.018s, CNN166calls/38,828items |
| 36 discs300002 | Found0.557s, CNN2calls/90items | Found2.947s, CNN0 |

A retains width8/cap2, a cheap128-candidate shortlist, and extended no-pass/late12 SAT probes before ML for44+ discs. B uses width16/cap4, no pre-CNN shortlist or heuristic sort, stop30, one symmetry, no refinement, batch256, ML only at44+ discs, and up to18 candidates. B enters CNN after a short2,000-conflict/20,000-decision probe without late12. Its ML deadline is disabled; only the outer60-second observation watchdog stops the trial. Settings/order are in `protocol.json`/`plan.json`; `native-geometry.patch` is the complete A-to-B diff.

Native's2-second probe is not equivalent to2,000work units. Native's SAT portfolio/concurrency and20-second candidate budgets differ from the browser's single solver and work limits. Torch CPU2threads and ONNX WASM1thread are different inference backends; B's36-disc SAT route is also not the native portfolio. This is therefore not an exact native implementation running in a browser.

For the64-disc B trial, CNN exploration reached30 placements at34.879s; after16 candidate checks, general SAT began at37.002s, and observation ended unresolved at60s. The33.950s score-call total includes runtime/session setup. No CNN execution failures occurred, but partial logs do not retain each candidate's UNSAT/unknown classification. B did not improve speed on these three pilots. Routing/probe policy changed along with geometry, so this does not isolate the causal effect of beam width.

`results.jsonl` preserves all six raw observations byte for byte. All five successful witnesses also passed independent Python replay and target comparison. The unresolved cost and partial CNN counts are retained; unknown is never relabeled as unreachable or failure. JSON contains no nonfinite numbers: B's `guided_budget_seconds:null` means JavaScript Infinity, a disabled deadline. `conditions.json` is a public allowlist with no private paths, addresses, SSH endpoints or credentials.

`verification.json` records raw/source/patch/verifier hashes and checks; `summary.json` records stage timing. To reproduce the code change, verify the A source hash, apply the patch to a copy, and verify B's hash. Full source trees, models and binaries are not duplicated here, and this package does not enable B in a product. No retraining, production changes or interference with the M4 formal benchmark occurred.

The code diff is MIT; synthetic cases follow the [public benchmark terms](https://github.com/wand125/othello-retro/blob/main/BENCHMARK_LICENSE.md). Attribution: wand125. Model/runtime terms remain those of their original distributions.

## Verification and reproduction

Clone the public repository containing the independent verifier. Set `RETRO_REPO` to that checkout and `DIAG` to this directory. The first command checks the recorded hash, order, CNN count consistency and witnesses without running a solver.

```sh
RETRO_REPO=/path/to/othello-retro
DIAG=/path/to/this-directory
python3 "$DIAG/check_results.py" --repo "$RETRO_REPO"
```

Reproduction requires Node24, Python3, `patch`, and the WASM/runtime inputs under the checkout's `browser-wasm/ui`. Obtain only the two ONNX models from the [official browser-models-v1 Release](https://github.com/wand125/othello-retro/releases/tag/browser-models-v1), checking archive SHA-256 `da61f0c2da3d518ebe6c6a5f5c02e9b6f20fe1f68a67a1258200617f17a0c248`. No training or reconversion is required. See the [browser build instructions](https://github.com/wand125/othello-retro/blob/main/browser-wasm/README.en.md) for runtime/WASM setup and third-party terms.

```sh
BROWSER_MODEL_STAGE="$(mktemp -d)"
curl -fL 'https://github.com/wand125/othello-retro/releases/download/browser-models-v1/browser-models-v1.tar.gz' -o "$BROWSER_MODEL_STAGE/models.tar.gz"
printf '%s  %s\n' 'da61f0c2da3d518ebe6c6a5f5c02e9b6f20fe1f68a67a1258200617f17a0c248' "$BROWSER_MODEL_STAGE/models.tar.gz" | shasum -a 256 -c -
tar -xzf "$BROWSER_MODEL_STAGE/models.tar.gz" -C "$BROWSER_MODEL_STAGE"
mkdir -p "$RETRO_REPO/browser-wasm/ui/models"
cp "$BROWSER_MODEL_STAGE/model.fused.onnx" "$BROWSER_MODEL_STAGE/model_passes.fused.onnx" "$RETRO_REPO/browser-wasm/ui/models/"
RETRO_BROWSER_UI="$RETRO_REPO/browser-wasm/ui" nice -n 19 taskset -c 16-19 node "$DIAG/run.cjs" --output /tmp/retro-geometry-new-run
python3 "$DIAG/check_results.py" --repo "$RETRO_REPO" --results /tmp/retro-geometry-new-run/results.jsonl
```

`taskset` is Linux-specific; omit it elsewhere and record actual conditions. The output directory must not exist. B is generated by patching a copy inside that output, leaving the checkout and models unchanged. Artifact mismatch is rejected by default. Explicitly add `--allow-artifact-change` only for an intentional separate measurement. `runner-port.json` and `runner-port.patch` disclose path/output-guard changes from the measured runner. Reproduction need not yield identical found/unknown counts. Publication preparation did not repeat the heavy experiment.
