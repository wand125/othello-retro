# Validating datasets, game records and measurements

[日本語](VALIDATION.md) | English

Validation is separate from running a reconstruction program. Most checks require only the Python 3.10+ standard library. Reproducing the original WSL NumPy bootstrap endpoints requires an optional package.

## Frozen inputs and schedules

```sh
python3 runner/check.py bank \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --bank benchmarks/study-endgame-cpu222-unbounded-v1.json \
  --require-disjoint seed
```

This checks protocol, case, schedule and reference hashes, and independently replays references. It checks all 64 squares, disc count, terminal status, IDs/seeds, complete case/slot/repetition coverage and declared first-slot balance. Coincident boards can arise from independent seeds, so board duplication is reported rather than rejected by default. Use `--require-disjoint` only for a required non-overlap condition.

A hash alone does not detect a changed dataset whose hash was also updated. Reproduce the generation rules as well:

```sh
python3 runner/check_generation.py \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --bank benchmarks/study-endgame-cpu222-unbounded-v1.json \
  --output .runs/generation-check.json
```

The checker replays seeded legal-move selection and compares 430 boards and reference records: 400 main midgames, ten pilot cases and 20 terminal cases. This is a validation count, not a pooled independent sample size for performance. It also regenerates midgame acceptance/rejection and both schedules. Sampling from the unpublished source candidate pool for the 20 terminal cases is not verified; the report states this limitation.

## A single reconstructed record

Save either a move array or a JSON object containing `moves` to `record.json`. Use a case ID present in the bank.

```sh
python3 runner/check.py record \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --case main-n12-s202610250000000 \
  --moves record.json
```

Every placement is replayed from the standard initial position. Flips, moving color, forced passes and the target are checked. Legitimately omitted forced passes are normalized; skipping a player who has a legal move is rejected. The normalized game and verification result are returned as JSON.

## Run logs and publication bundles

```sh
python3 runner/check.py run \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --input .runs/my-midgame

python3 runner/check.py published \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --input public-results/my-midgame
```

`run` independently replays every returned record and checks case/slot/repeat order, input hashes, timing values and retained interruption cost. `published` also checks manifest file hashes, unsafe file references and private material. Means and ratios are recomputed. Generic-runner summaries are checked against the same standard-library bootstrap settings.

The original WSL summaries used NumPy. Standard-library validation does not pretend to verify those confidence intervals: it explicitly reports their unchecked status. Recompute them with the optional dedicated checker:

```sh
# Use a Python 3.12 environment with NumPy 1.26.4, matching the original analysis.
python3 runner/check_numpy_ci.py \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --input benchmarks/wsl-cpu222-unbounded-midgame-main-20261025 \
  --output .runs/wsl-midgame-ci-check.json
```

For the terminal suite, replace both bank and input with the corresponding endgame versions. The original replicate count, seed and stratum order are used to compare the actual endpoints. Missing NumPy is not treated as a passed CI check.

You can validate multiple inputs together:

```sh
python3 runner/check.py all \
  --bank benchmarks/study-midgame-cpu222-unbounded-v1.json \
  --bank benchmarks/study-endgame-cpu222-unbounded-v1.json \
  --run local=.runs/my-midgame \
  --published wsl=benchmarks/wsl-cpu222-unbounded-midgame-main-20261025
```

## Reading results and running self-tests

Successful checks exit with code zero; failed checks exit nonzero. Validation success is distinct from measurement completion. A valid saved prefix can pass validation while still being explicitly marked unfinished. A passing fixture only tests the harness, not reconstruction performance.

These checks establish game-rule validity and data consistency. They do not prove that a program avoided reading reference records, complied with self-declared resources, or represents a population of user inputs. Common-case coverage and CI precision must be assessed separately.

```sh
python3 -m unittest discover -s runner/tests -v
```

Self-tests cover illegal passes/records, altered data with recomputed hashes, ordering, invalid clocks, fixture contamination, interruption/resume, owned-child cleanup, private-data leakage and altered summaries. NumPy-specific self-tests are shown as skipped when the optional package is absent.
