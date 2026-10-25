# Othello Retro — browser SAT edition

A Rust CNF encoder and Kissat 4.0.3 WebAssembly search for a legal history from the standard initial position, entirely in the browser. Distribution consists of static files. Computation uses SAT, without a computation server or trained model. The native implementation and its auto benchmarks are separate implementations and measurements.

The UI supports board entry and transformations, playback, seeking, sound, browser-local record storage, and JSON import/export. Newly created records stay in that browser; sharing requires exporting the JSON or another explicit publication step. Previously published records bundled with the static site have a library and individual URLs.

Every `found` witness is replayed by independent JavaScript rules: Black starts, placements must flip discs legally, only forced passes are permitted, and all 64 target cells must agree. `unreachable` comes only from a necessary-condition rejection or UNSAT of the general encoding that allows passes. Restricted no-pass UNSAT never establishes general unreachability. Cancellation, resource exhaustion and errors are distinct outcomes. Independent DRAT certificate checking is not provided.

Search runs in a Worker; cancellation terminates that Worker. Some positions require substantial time or memory. Mobile search performance and memory use have not been measured. Native benchmark timings do not guarantee browser performance.

## Build

Prepare Rust 1.98.0 with the `wasm32-unknown-unknown` target, Emscripten, Python 3 and Node.js. From the repository root:

```sh
cargo +1.98.0 build --manifest-path browser-wasm/engine/Cargo.toml --target wasm32-unknown-unknown --release --locked -j2
cp browser-wasm/engine/target/wasm32-unknown-unknown/release/othello_retro_browser_encoder.wasm browser-wasm/ui/encoder.wasm
EMCC="$(command -v emcc)" EM_CACHE=/tmp/othello-emcache python3 browser-wasm/solver/build.py
```

Provide a usable Emscripten SDK cache. [solver/README.md](solver/README.md) and its manifests describe the upstream source, small wasm32 portability change, build flags, hashes and notices.

## Verification and static assembly

```sh
node --test browser-wasm/tests/test-verify.cjs browser-wasm/tests/test-policy.cjs
node browser-wasm/tests/test-solver.cjs --smoke
node browser-wasm/solver/smoke.cjs
python3 browser-wasm/build_static.py --public-repo /path/to/othello-retro --records /path/to/public-records-snapshot.json --output /tmp/othello-static-new
python3 -m http.server 8000 --directory /tmp/othello-static-new
```

`--public-repo` selects the public repository containing the four existing paper assets. `--output` must be a new directory. The builder does not deploy. `--records` selects a public snapshot shaped as `{ "examples": [...] }`. Every record is independently replayed; only safe IDs and allowlisted public metadata are distributed. Without it, the UI's bundled records are used. The bundled 72 records are a verified snapshot; supplying another snapshot replaces that input.

The generated `/paper/` preserves the manuscript, CSS, mathematics and language switching; only links and asset references change. Static redirects support `paper.html`, `examples/` and each record URL, carrying the query and fragment. Relative URLs work on both a custom domain and a GitHub Pages project subpath. `asset-manifest.json` records the version and file hashes. A Service Worker stores successfully fetched assets for offline use; first-use offline operation and continued browser storage retention are not guaranteed.

The browser smoke additionally requires Playwright and Chromium. After starting the static preview, run `OTHELLO_PREVIEW_URL=http://127.0.0.1:8000/ node browser-wasm/tests/browser-smoke.cjs`. Its observational deadline is never interpreted as an unreachability verdict. The 61-disc deep-unreachable fixture in `tests/cases.json` is an optional stress case, excluded from ordinary smoke.

## Licensing

Original Rust, JavaScript, build scripts and verification scripts are MIT. Kissat retains its authors' MIT notices. Rust standard-library components require their applicable MIT OR Apache-2.0 and third-party notices; Emscripten, musl, compiler-rt and other runtime components retain their own notices. The compiled WebAssembly must not be treated as containing only original code. Kissat-side notices are in `ui/kissat.LICENSES.txt` and `solver/licenses/`. The original article prose and figures retain the existing CC BY 4.0 policy. See `LICENSE_SCOPE.md` in the public repository for the full scope.


### Acceptance-fixture terms

Each of the 14 entries in `tests/cases.json` has `license`, `attribution`, original JSON location and source hashes. The 12 bank-derived/original-example fixtures retain MIT terms. The two article-derived fixtures, `paper-two-placement-unreachable` and `paper-deep-root-61`, retain the existing CC BY 4.0 policy. Attribute **wand125**, the [article](https://othello-retro.logicpuzzle.app/paper), and each case's `source_data`. Extraction into fixture format and added verification metadata are recorded changes; boards and reference moves are unchanged. [Fixture terms](tests/LICENSE.md) and the [CC BY 4.0 text](tests/licenses/CC-BY-4.0.txt) are supplied. Verification code remains MIT, and third-party runtime notices remain separate.
