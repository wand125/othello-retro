# Othello Retro engine

[日本語](README.md) | English

The original Rust SAT CLI and Python CNN-guided search/training code are MIT
licensed (Copyright 2026 wand125 and contributors). Cargo remains unchanged; current source adds the terminal-undo correction and opt-in lightweight auto. It differs from the original formal-measurement source. See the [later diagnosis](../AUTO_DIAGNOSIS.en.md) and [historical records](history/v0.1.0/README.md).
Dependencies keep their own terms: see THIRD_PARTY_NOTICES.md and
PYTHON_DEPENDENCIES.md. No third-party implementation or binary is vendored.

## Layout and build

Run from `solver/`, with Cargo.toml, src/ and ml/ as siblings. Linux/macOS,
Rust 1.98.0, a C++17 compiler and a separate Kissat 4.0.3 executable are needed.
Use the upstream Kissat rel-4.0.3 source (`./configure CC=clang -O3`, `make -j2`)
and put its build/ directory on PATH. Cargo downloads locked cadical 0.1.16,
whose crate builds CaDiCaL 1.9.5. These are two distinct solver integrations.

```sh
rustup toolchain install 1.98.0 --profile minimal
nice -n 19 cargo +1.98.0 build --release --locked -j2
kissat --version
nice -n 19 cargo +1.98.0 test --release --locked -j2 -- --test-threads=1
```

Skip toolchain installation if 1.98.0 already exists; it does not change the
default toolchain. Current 11 unit tests passed with real Kissat 4.0.3; the nine-test v0.1.0 record remains historical. Without Kissat,
the integration test prints a skip message, which is not SAT execution proof.
`--jobs 1` does not mean one CPU: the solver portfolio can start multiple jobs.
Use the separate benchmark two-slot gate when reproducing that configuration.

## SAT

Input is 64 row-major X/O/- cells, starting at a1. Whitespace is ignored.

```sh
./target/release/othello-retro solve examples/one-move.board --json --method sat --time 10 --prepass-ms 0 --jobs 1
./target/release/othello-retro solve examples/one-move.board --json --method sat --no-time-limit --prepass-ms 0 --jobs 1
```

The example proof is `["d3"]`. `found` returns a record; `unknown` is unresolved,
not an unreachability proof. `--no-time-limit` is supported by solve/method sat
and removes the final SAT deadline. Otherwise the default limit is 10 seconds.
It is not a fast-completion or CPU-allocation guarantee.

## Python and separate weights

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-inference.txt
```

Place the separately published Release weights at ml/model.pt and
ml/model_passes.pt and check MODEL_FILES.json hashes/sizes. Weights, raw training
data, bytecode and environments are excluded from this source archive.
Inference consumes learned weights, not the original training JSONL. The
Torch 2.2.2 / NumPy 1.26.4 pins match formal CPU inference, not a recovered historical
training environment. Optional comparison dependencies have explicitly stated
local version evidence rather than a claim of exact retraining reproducibility.

## Two opt-in auto configurations

These flags select Python search/inference policy. Even `baseline` keeps the current Rust undo correction. Build v0.1.0/commit `32e472e` in a separate checkout for the old native source.

```sh
# Old policy/inference, using the currently corrected native
OTHELLO_DEVICE=cpu RETRO_HALF=0 RETRO_AUTO_POLICY=baseline RETRO_INFERENCE_OPT=baseline OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python ml/worker.py ml/model.pt
# Lightweight policy and fused CPU inference
OTHELLO_DEVICE=cpu RETRO_HALF=0 RETRO_AUTO_POLICY=lightweight RETRO_INFERENCE_OPT=fused_channels_last OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python ml/worker.py ml/model.pt
```

An incomplete terminal returns `miss` reason `incomplete_terminal_exact_route`: planned general-SAT routing. The worker alone does not run final exact SAT; the caller must do so. `ui/server.py` checks this route before cold-starting the model. Checkpoints are unchanged; there is no retraining. CPU inference optimization is not an unconditional GPU setting.

Run the 17 related Python tests with `python -m unittest benchmarks/test_lightweight.py benchmarks/test_analyze_auto_diagnostic.py`. [NATIVE_LIGHTWEIGHT_VALIDATION.json (JSON)](NATIVE_LIGHTWEIGHT_VALIDATION.json) records evidence/hashes; see [benchmarks/README.md](benchmarks/README.md) for the separate three-variant experiment and resume semantics.

## Auto / guided search

```sh
OTHELLO_DEVICE=cpu RETRO_HALF=0 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python ml/worker.py ml/model.pt
```

Wait for `{"status":"ready"}`, then write one request per stdin line:
`{"board":"64 actual X/O/- characters","time":60}`. Replace the placeholder with
a real target. A sibling model_passes.pt is loaded for the pass-aware route.
This worker is time-bounded candidate search; `miss` is not an impossibility
proof. It does not itself run the final general-SAT fallback. For an unresolved
result, use the Rust SAT command above.

The existing timed auto→SAT evaluation pipeline reports stages/timing rather
than returning the reconstructed record itself:

```sh
OTHELLO_DEVICE=cpu RETRO_HALF=0 python ml/eval_pipeline.py examples/one-move.hex --model ml/model.pt --model-passes ml/model_passes.pt --time 60
```

This legacy time-allocation pipeline is separate from the formally frozen
unbounded harness. Match bank, schedule, harness, resource gate and environment
before claiming to reproduce those results. search.py also exposes a research
beam+SAT CLI; beam exhaustion is not unreachability. Accept returned records
with the public runner's strict independent replay, including passes. The
historical search.verify helper is not a general strict legality checker.

## Training and teacher restrictions

```sh
./target/release/othello-retro spine 10 mix --seed 1 > spine.jsonl
python ml/label_spine.py spine.jsonl labels.jsonl --per 8 --limit 2 --workers 2
python ml/train_final.py labels.jsonl --out my-model.pt --epochs 25
```

These demonstrate the interfaces, not a bit-identical recipe for the released
weights. The pass-aware spine generator conditions on full 64-disc games with
passes, excluding early terminal games. Original training-set selection and
provenance are separate release documentation. label.py's walk rows are a
different schema from the spine-feature rows used above.

- No-pass UNSAT labels apply only to the no-pass encoding. `reach` restricts
  side-to-move and passes to the last 12 placements; its UNSAT is not general
  board-only unreachability.
- train_final.py changes unknown y=-1 labels to positive. This is a learning
  heuristic, not a reachability proof. Record unknown rates and teacher scope.
- train.py is a feature-comparison experiment. Its --save writes a model with
  scalar inputs, incompatible with worker.py's Net(False). Use train_final.py
  for the worker architecture. Install requirements-training.txt only for the
  optional comparison tools.
- Research helpers can have substantial time/parallelism defaults. Choose
  resource limits explicitly. The release removes bench_fix.py's broad pkill;
  its own bounded tasks now finish/join without stopping unrelated solvers.
  RELEASE_PATCHES.json records that one release-only change.

The original 400/20 measurement data and checkpoints remain unchanged. The later source update and WSL production adoption are documented separately.
ENGINE_SOURCE_MANIFEST.json records the original/released source hashes and
scope; model/data/UI/infra distribution are separate from this source pack.
