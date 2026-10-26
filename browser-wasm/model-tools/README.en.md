# Browser-model conversion and numerical fixtures

The tools strict-load the two published checkpoints in CPU eval mode, clone them, fold nine Conv–BatchNorm pairs and export ONNX. There is no training or checkpoint overwrite. These are conversion checks, not classifier-accuracy or smartphone-performance tests.

Prepare Python 3.12, PyTorch 2.2.2, NumPy 1.26.4, ONNX 1.17.0, protobuf 5.29.5 and Node.js in a separate environment. Download and hash-check the existing [Release weights](https://github.com/wand125/othello-retro/releases/tag/v0.1.0). From the repository root, with new output paths:

```sh
node browser-wasm/model-tools/generate-edge-items.cjs --solver-repo . --output /tmp/legal-edges-new.json
python browser-wasm/model-tools/export_models.py --solver-repo . --weights-dir /path/to/weights --legal-edges /tmp/legal-edges-new.json --output /tmp/onnx-export-new
node browser-wasm/model-tools/verify-planes.cjs
```

`--solver-repo` accepts an engine root containing `ml/` or a public repository root containing `solver/ml/`. The generator finds the corresponding browser rules and fixtures. Three independently replayed public-bank references provide 179 genuine placement edges, including forced-pass examples. In the checked CPU/PyTorch 2.2.2 environment, the portable re-export matched both ONNX files, numeric fixtures and legal-edge JSON byte-for-byte.

Models are `model.fused.onnx`/`model_passes.fused.onnx`: input `planes`, FP32 `[N,5,8,8]`, output `logits`, FP32 `[N]`, dynamic batch only, opset 17/IR8. Logical layout remains NCHW; runtime physical layout is separate. Outputs are raw logits, without sigmoid.

Planes are predecessor mover-own, mover-opponent, empty, removed placement and flipped discs. Use explicit mover for pass-aware candidates, not placement parity. Map fixture `mover` to the JS item's `next`. The JSON specifies equations and row-major indexing.

Seven batches cover legal inputs of 1/16/128, one edge after a forced pass, and synthetic random 0/1 conversion inputs of 1/16/128. Expected original and folded PyTorch logits are both retained. `verify-planes.cjs` checks four legal batches/146 candidates/46,720 Float32 values byte-for-byte against JS. Compare ONNX Runtime to the folded reference using `abs(error) <= 1e-4 + 1e-4*abs(expected)`. Original-to-folded maximum absolute error is 0.0001564/0.0001259 for the two models, within the combined absolute/relative tolerance. Near-tied rankings are not guaranteed bit-identical.

Inference ranks heuristic candidates. Independently replay every accepted witness; a candidate miss or numeric difference must not become an unreachability verdict, and complete SAT fallback must remain available.

`model-export-manifest.json` preserves the **historical first export**, whose file map describes its output set rather than every file in this folder. `portable-export-manifest.json` records the CLI re-export and distinguishes historical source hashes. `portable-tools-manifest.json` covers the actual distributed tooling/fixtures and reproduction results. Model `.pt`, `.onnx` and `.npy` payloads are excluded from this Git directory.

Original tooling is [MIT](../LICENSE). Legal-edge inputs retain the synthetic banks' existing [MIT policy](../../BENCHMARK_LICENSE.md); the two article-derived impossible fixtures are not used. ONNX derivatives retain the weights' [CC BY 4.0](../tests/licenses/CC-BY-4.0.txt) terms: attribute **wand125**, Release v0.1.0 and the eval-fold/ONNX conversion. Numeric outputs also carry model attribution. The historical `model_passes.pt` filename does not imply pass-only training; see the [model card](../../models/MODEL_CARD.en.md). Random inputs are conversion fixtures, not training data or reachability labels. Runtime implementations retain their own notices.
