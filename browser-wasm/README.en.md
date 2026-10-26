# Othello Retro — browser SAT and lightweight Auto

[日本語](README.md) | [English](README.en.md) · [Open the preview](https://wand125.github.io/othello-retro/)

Search runs locally using SAT or optional lightweight Auto. The Rust encoder, Kissat 4.0.3 and Auto's ONNX Runtime Web 1.30.0 are same-origin static assets, without a computation backend or CDN. Auto uses CPU FP32/one inference thread to rank candidates from existing checkpoints; misses return to complete general SAT. The native 400/20-case benchmark and later 32-case diagnosis are separate implementations and conditions.

The UI retains board entry and color/rotation/reflection transforms, playback/seeking, sound voices and standard/screen-recording audio output, local record storage, JSON import/export and compressed record-sharing URLs. New records stay in the browser; the existing public snapshot has a library and individual URLs.

## Search and testing your device

Every `found` witness is independently replayed under standard rules, including Black first, flips, forced passes and all 64 target cells. Restricted-probe failure and Auto misses never establish unreachability. Only necessary-condition rejection or UNSAT of the complete pass-aware formula returns `unreachable`. Normal final SAT has no time limit; cancellation terminates the Worker. Independent DRAT checking is not provided.

Current Auto considers boards with at least 36 discs using width 8, cap 2 per parent, shortlist 128, a 30-placement stopping point and an approximately 12-second guidance budget. Bounded candidate SAT retains complete fallback. For boards with at least 44 discs, SAT also tries a stronger no-pass probe before the complete general formula without redundant occupancy constraints. Probe work limits are not wall-time promises.

No smartphone 60-second guarantee has been established. [Benchmark this device](https://wand125.github.io/othello-retro/benchmark.html): start with quick5 across occupancy strata, then optionally 20 midgames, 20 terminals or all 40 cases, using SAT/Auto. Each case gets a fresh Worker, bypasses cached witnesses and independently checks the result. The observational limit is 60 seconds per case; interruption means unresolved. Results stay local and can be downloaded as JSON, without POST. Real Chrome runs controlled by Python are distinct from physical-phone measurements.

## Download models and build

Prepare Rust 1.98.0 with the wasm32 target, Emscripten, Python 3 and Node.js. From the repository root, first download [browser-models-v1](https://github.com/wand125/othello-retro/releases/tag/browser-models-v1), verify the archive SHA-256 and copy **only the two ONNX files** to `ui/models/`. They are eval Conv–BN-folded conversions of unchanged trained checkpoints.

```sh
BROWSER_MODEL_STAGE="$(mktemp -d)"
curl -fL 'https://github.com/wand125/othello-retro/releases/download/browser-models-v1/browser-models-v1.tar.gz' -o "$BROWSER_MODEL_STAGE/browser-models-v1.tar.gz"
printf '%s  %s\n' 'da61f0c2da3d518ebe6c6a5f5c02e9b6f20fe1f68a67a1258200617f17a0c248' "$BROWSER_MODEL_STAGE/browser-models-v1.tar.gz" | shasum -a 256 -c -
tar -xzf "$BROWSER_MODEL_STAGE/browser-models-v1.tar.gz" -C "$BROWSER_MODEL_STAGE"
mkdir -p browser-wasm/ui/models
cp "$BROWSER_MODEL_STAGE/model.fused.onnx" "$BROWSER_MODEL_STAGE/model_passes.fused.onnx" browser-wasm/ui/models/
```

```sh
cargo +1.98.0 build --manifest-path browser-wasm/engine/Cargo.toml --target wasm32-unknown-unknown --release --locked -j2
cp browser-wasm/engine/target/wasm32-unknown-unknown/release/othello_retro_browser_encoder.wasm browser-wasm/ui/encoder.wasm
EMCC="$(command -v emcc)" EM_CACHE=/tmp/othello-emcache python3 browser-wasm/solver/build.py
```

Use a prepared SDK cache for `EM_CACHE`, or select an existing compatible cache. See [Kissat build notes](solver/README.md) for sources/wasm32 changes/flags/notices, and [model conversion and numerical fixtures](model-tools/README.en.md). The historical `model_passes` filename does not imply pass-only training.

## Verify, assemble and use offline

```sh
node --test browser-wasm/tests/test-verify.cjs browser-wasm/tests/test-policy.cjs browser-wasm/tests/test-auto.cjs
node browser-wasm/model-tools/verify-planes.cjs
node browser-wasm/tests/test-solver.cjs --smoke
node browser-wasm/solver/smoke.cjs
python3 browser-wasm/build_static.py --public-repo . --output /tmp/othello-static-new
python3 -m http.server 8000 --directory /tmp/othello-static-new
```

The first command runs 27 rule/probe-control/Auto unit tests. Run `node browser-wasm/tests/test-solver.cjs --stress` separately for expensive full acceptance. Listing that command does not claim completion on every device.

Download models before `build_static.py`. Its output directory must be new; `--public-repo` selects the public repository containing the article. Optional `--records` supplies an `{"examples":[...]}` snapshot, otherwise bundled records are used. The builder does not deploy. Article prose, CSS, mathematics and languages stay unchanged; asset/link references become relative.

The roughly 14.24MB inference runtime and one needed 1.232MB model load only when Auto first needs them, outside the initial bulk precache. After successful fetching under Service Worker control, model/runtime assets work offline while the browser retains their cache. First-use offline downloads are unavailable; loading/inference errors fall back to SAT.

## Licensing

Original Rust/JS/build/verification code is [MIT](LICENSE). Kissat, Rust standard-library, Emscripten, ONNX Runtime and bundled runtimes retain their notices: see `ui/kissat.LICENSES.txt`, `ui/RUST-LICENSES.txt` and references, plus `ui/inference/LICENSE`. ONNX derivatives retain [CC BY 4.0](tests/licenses/CC-BY-4.0.txt), attribution **wand125**, the source Release and conversion changes.

[Acceptance-fixture terms](tests/LICENSE.md) distinguish 12 MIT examples from two existing CC BY 4.0 article-derived examples. [Model tooling](model-tools/README.en.md) distinguishes MIT bank inputs from model attribution. Original article prose/figures, benchmark data and hashes are unchanged. See the repository-wide [LICENSE_SCOPE](../LICENSE_SCOPE.md).

For boards with at least 44 discs, the final browser policy tries a bounded no-pass formula, then a bounded late-pass (last 12 placements) formula before general SAT or model guidance. Neither restricted UNSAT is a general refutation. The final general formula remains unlimited. Work limits are conflicts/decisions, not wall-clock promises.
