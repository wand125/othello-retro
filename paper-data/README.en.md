# Supplementary article data

[日本語](README.md) | English

Figure inputs, boards, records and verification files for the [Japanese article](https://othello-retro.logicpuzzle.app/paper?lang=ja) and [English article](https://othello-retro.logicpuzzle.app/paper?lang=en). The eleven-step reverse chain is displayed in the manuscript. Explanations belong to the article.

| File | Contents |
|---|---|
| [article-data.json](article-data.json) | Exact figure JSON: seven records, shallow predecessors, pass examples and the eleven-step chain |
| [deep-reverse-chain.json](deep-reverse-chain.json) | Twelve positions/eleven edges from 61 to 50 discs, next players, recorded general-SAT result and scope |
| [deep-root-general.cnf.gz](deep-root-general.cnf.gz) | Gzip-compressed general CNF for the 61-disc root |
| [deep-root-general-solver.log](deep-root-general-solver.log) | Existing Kissat UNSAT output, not private user-access logs |
| [check_deep_reverse_chain.py](check_deep_reverse_chain.py) | Independent array-rule verifier using the standard library; optional CNF/log hash checks |
| [test_deep_reverse_chain.py](test_deep_reverse_chain.py) | Rejection tests for illegal moves, false passes, turn mismatches and overstated claims |
| [forced-pass-reference.json](forced-pass-reference.json) | Separate reference testing explicit and omitted forced passes |
| [deep-reverse-chain-report.json](deep-reverse-chain-report.json) | Replay, necessary-condition and existing-artifact checks |
| [adversarial-check-report.json](adversarial-check-report.json) | Mutation, forced-pass and initial-position tests |
| [manifest.json](manifest.json) | Hashes for every supplement file and the four corresponding article assets, with verification scope |

## Re-run verification

Run at the repository root with Python's standard library and gzip. These commands launch no solver or model. Output goes to a temporary directory without replacing stored evidence.

```sh
check_dir="$(mktemp -d)"
gzip -dc paper-data/deep-root-general.cnf.gz > "$check_dir/deep-root-general.cnf"
python3 -B paper-data/check_deep_reverse_chain.py \
  --input paper-data/deep-reverse-chain.json \
  --cnf "$check_dir/deep-root-general.cnf" \
  --solver-output paper-data/deep-root-general-solver.log
python3 -B paper-data/test_deep_reverse_chain.py \
  --input paper-data/deep-reverse-chain.json \
  --pass-example paper-data/forced-pass-reference.json \
  --output "$check_dir/adversarial-check-report.json"
```

The checker validates the eleven edges, forced passes/next turns, listed necessary conditions on twelve positions, reference records and existing file hashes. **It does not recompute UNSAT, establish the encoding's semantic correctness or check a DRAT proof.** The 61-disc root has a recorded general-pass, unrestricted-next-player UNSAT decision; no DRAT certificate was generated or independently checked. Descendant unreachability is conditional on that decision and applies only to the specified next-player states. Other next players, whole-frontier survival and minimum required search depth are not established.

The verification scripts are [MIT](../LICENSE). See [LICENSE_SCOPE.md](../LICENSE_SCOPE.md) for data/original supplementary-analysis terms. Performance banks, schedules and measurements remain separate under [`benchmarks/`](../MEASUREMENT_DESIGN.en.md); engine source and weights are in [Release v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0).
