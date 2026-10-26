# Run the public banks with another program or environment

[日本語](README.md) | [English](README.en.md)

See the [validation guide](VALIDATION.en.md) for individual and batch checks of generation, records, run logs, summaries, and publication bundles.

This folder contains measurement tools for Python 3.10 or later, using only the standard library. The supported runtime is POSIX: Linux, macOS, or WSL. Connect an external program through JSON input and output to measure the same boards in the same fixed order. Reversal solvers, trained models, and the existing service implementation are not included. The new tools in `runner/` use the [MIT license](LICENSE). See [BENCHMARK_LICENSE.md](../BENCHMARK_LICENSE.md) for reuse of the published synthetic test banks.

## Connect your program

Run from the repository root:

```sh
python3 runner/benchmark.py run \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --config my-programs.local.json \
  --split pilot \
  --output .runs/my-environment-pilot
```

Use `examples/external-program.json` as a configuration template. `sat` and `auto` under `programs` are the comparison slots named by the fixed schedule. These names do not certify that the connected programs use SAT or CNNs. You can connect other algorithms to either slot.

- `command` is a JSON array containing the executable and its arguments, rather than a shell command string.
- Relative `cwd` paths are resolved from the configuration file's parent directory. If omitted, the runner's working directory is used. In the supplied examples, `../..` points from `runner/examples/` to the repository root.
- You can set shared `env` and per-program `env`. Whether a program actually uses the example OMP/BLAS settings depends on its implementation. Record CPU allocation, threads, device, model, library versions, OS, compiler, and internal search limits. Labels and declarations are not independent confirmation of those conditions.
- Keep secrets out of configuration files. Actual commands, working paths, and configured environment variables are stored in `private-runtime.json`; stderr and related logs go into `.private-logs/`. Do not include these private files in published results.

Each program can also define `declared_environment` and `artifacts`. For example, add these fields under `programs.sat` or `programs.auto`, replacing the declarations and filename with the actual conditions:

```json
{
  "declared_environment": {"device":"cpu", "dtype":"float32", "inference_threads":2, "solver_parallelism":2},
  "artifacts": [{"name":"model", "path":"my-model.bin"}]
}
```

Relative artifact paths are resolved from that program's `cwd`. The runner records SHA-256 hashes of the executable, command arguments that identify files, and additional artifacts. It cannot discover every dependency automatically; add relevant source, model, and configuration files. Public metadata retains permitted environment fields and hashes while private paths are separated. Resume checks the configuration, runner, connected program, and artifact identities.

Source, model, and library hashes in the original bank's `protocol` record the original program's experimental conditions. An external program does not have to use those same sources or models. Keep the input `cases`, `schedule`, and bank hash fixed, and separately record the connected program's identity, hashes, environment, and timing mode in runner metadata.

An example close to the original computation settings is CPU, FP32, two inference threads, and `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2`. The configuration examples do not enforce FP32, CPU affinity, or the number of SAT child processes. Set these in your program and check the actual conditions.

The pilot contains ten boards distinct from the main midgame set, for checking the adapter and estimating runtime. The endgame bank has no pilot. For the main experiment, change to `--split main`. Measure the 400 midgame boards and 20 terminal boards using separate banks and output directories. With both methods and three repetitions, these contain 2,400 and 120 trials respectively.

```sh
python3 runner/benchmark.py run --bank benchmarks/study-midgame-cpu222-unbounded-v1.json --config my-programs.local.json --split main --output .runs/my-midgame
python3 runner/benchmark.py run --bank benchmarks/study-endgame-cpu222-unbounded-v1.json --config my-programs.local.json --split main --output .runs/my-endgame
```

Use `--method sat` or `--method auto` to measure only one slot. To resume, use `--resume` with the same configuration, bank, and output directory. Preserve the original schedule and trial identities; do not replace slow cases with easier ones. `--pause-file FILE` supports pauses between trials. Its default is `PAUSE` in the output directory. While that file exists, the runner waits before starting the next trial; removing it resumes the run. This does not impose a time limit on a trial already in progress.

```sh
touch .runs/my-midgame/PAUSE
# To resume
rm .runs/my-midgame/PAUSE
```

For a manual interruption such as Ctrl-C, the unfinished trial is not added as a successful row. Resume runs that same trial again. Work already spent is recorded separately and added to its effective time. If an interruption such as SIGKILL prevents accurate preservation of the unfinished attempt, resume is refused to avoid understating its cost. Record manual interruptions and pauses, and distinguish trial computation time from total elapsed program time.

## JSON adapter protocol

Input is one JSON object per line. Reference records are not passed to your program.

```json
{"id":"trial-identifier","board":"---------------------------OX------XO---------------------------"}
```

`board` is exactly 64 characters, with no embedded newline: the first character is a1, the eighth is h1, and the last is h8. Black is `X`, white is `O`, and empty is `-`. Return a sequence from the standard opening position, with black moving first, that reaches this board.

A successful response has this form:

```json
{"status":"found","moves":[]}
```

The empty sequence matches the opening board above. For other inputs, the sequence must match all 64 requested cells. Coordinates are lowercase `a1` through `h8`, and a pass is the string `pass`. Do not append two passes just to indicate game termination. A player with a legal move cannot skip their turn. A forced pass may be omitted: the verifier inserts it only when the current player has no legal move and the opponent does.

`unknown` and `error` are not equivalent to `found`. An illegal record, malformed JSON, premature program exit, or a response other than `found` causes the runner to record an error and stop, rather than silently move to the next case. Every bank input has a legal reference sequence. Reporting `unreachable` for a reachable input is incorrect. Document any internal time limits or candidate cutoffs in your program. The absence of a runner-wide trial cutoff does not establish that the external program is itself unrestricted.

### oneshot

For each request, the runner starts `command` and passes a JSON request to stdin. Write one result JSON line to stdout and exit. **Process startup, model loading, and similar preparation are included in that trial's time.**

### resident

Start `command`, finish model loading and your fixed warmup, then write:

```json
{"event":"ready"}
```

For each subsequent stdin request, return:

```json
{"event":"result","payload":{"status":"found","moves":["d3","c3"]}}
```

Direct result objects are also accepted, but the event wrapper above is recommended. Progress can be emitted as `{"event":"progress","payload":{...}}`. Preparation before `ready` is recorded separately from trial time. Oneshot startup-inclusive times and resident post-preparation times represent different measurement conditions. Report the mode, warmup policy, and environment rather than mixing them into a speed ranking.

Keep stdout limited to the JSON protocol. Send explanations and debugging messages to stderr.

## Fixture for checking the connection

```sh
python3 runner/benchmark.py run --bank benchmarks/study-midgame-cpu222-unbounded-v1.json --config runner/examples/fixture-oneshot.json --split pilot --output .runs/fixture-oneshot
python3 runner/benchmark.py run --bank benchmarks/study-midgame-cpu222-unbounded-v1.json --config runner/examples/fixture-resident.json --split pilot --output .runs/fixture-resident
```

`fixture_adapter.py` **only looks up and returns public reference records; it performs no reversal search**. It checks JSON integration, the fixed order, replay verification, and output handling. The configuration and response set `fixture:true`, and the response includes `measurement_kind:harness-smoke-only`. Never present fixture timing as solver performance or mix fixture runs with formal performance results.

## Analyze and export results

Only combine runs using the same bank in one analysis. Repeat `--run LABEL=DIR` for multiple runs. This example analyzes sat/auto within one environment:

```sh
python3 runner/analyze.py \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --run local=.runs/my-midgame \
  --split main --output .runs/my-midgame-analysis.json
```

For multiple environments, use `--run hostA=.runs/hostA --run hostB=.runs/hostB`. Add `--require-label hostA --require-label hostB` to name every environment required for the comparison. Analysis rechecks records, boards, fixed order, and hashes, then produces 95% paired bootstrap intervals with independent cases resampled within strata. The defaults are 3,000 replicates and seed 730253; set them with `--bootstrap-replicates` and `--bootstrap-seed`. Repetitions of each case remain grouped. Having 90% common completed cases is neither a precision guarantee nor permission to stop early. Report the timing ratio's interval width and whether it includes one. Treat the 20 terminal cases as an auxiliary measurement.

Before publishing, export to a directory separate from the private run:

```sh
python3 runner/export.py \
  --input .runs/my-midgame \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --split main --output public-results/my-midgame
```

Export revalidates records and writes timings and permitted metadata. It excludes actual commands, private logs, configured environment variables, fields with secret-like names, and absolute paths. Outputs include `metadata.json`, `runs.jsonl`, `verification.json`, `manifest.json`, and, for completed runs, `summary.json`. Review the files before publication. Partial results are marked `incomplete`, and fixtures remain identified as fixtures. Completing one environment does not establish readiness for a cross-environment comparison. For pilot analysis and export, supply `--split pilot` to both tools.

## Independent replay verification

`verify.py` provides `verify(moves, target)`. It replays every move under the standard rules and checks all 64 target cells. The returned dictionary contains normalized `moves`, game termination flag `terminal`, placement count `placements`, and pass count `passes`. Invalid records or boards raise `InvalidRecord`, a subclass of `ValueError`.

```sh
python3 -m unittest discover -s runner/tests -p 'test_verify.py'
```

Three repetitions of one case are not three independent boards. Keep the 400 midgame and 20 terminal samples separate, distinguish incomplete progress from completed results, and separate fixtures from performance measurements.

A [browser WebAssembly adapter guide](../browser-wasm/benchmarks/README.en.md) is also available.
