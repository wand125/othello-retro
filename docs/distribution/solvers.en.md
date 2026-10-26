# Solvers and dependencies

[日本語](solvers.md) | [English](solvers.en.md)

## Public measurement tools and the original engine

The published `runner/` contains general-purpose measurement tools using only the Python 3.10+ standard library. It includes no SAT solver or trained model. You can connect your own external reconstruction program. See the adapter guide in [日本語](../../runner/README.md) or [English](../../runner/README.en.md).

The Rust/Python engine, UI/server and frozen measurement harness are published in [`solver/`](../../solver/README.en.md), with the vertical UI in `short/`. Weights are assets of the [experimental Release v0.1.0](https://github.com/wand125/othello-retro/releases/tag/v0.1.0). Standard-library runner dependencies are separate from the engine's Rust, ML and video dependencies.

## Separate browser SAT edition

[`browser-wasm/`](../../browser-wasm/README.en.md) contains compiled WASM for the Rust CNF encoder and Kissat 4.0.3, rebuild sources and notices. SAT runs in one Worker without trained models, Python or a computation server. A bounded no-pass SAT probe is followed by the general encoding allowing passes when it does not find a witness. Restricted-probe UNSAT alone never establishes general unreachability; only a necessary-condition rejection or general-encoding UNSAT does. An independent JavaScript replay validates every `found` witness.

Original-code MIT and the Kissat, Rust standard-library and Emscripten/runtime binary notices remain separate. [Fixture terms](../../browser-wasm/tests/LICENSE.md) distinguish MIT bank-derived cases from two CC BY 4.0 article-derived cases. The original four-environment native measurements are not browser performance measurements; mobile performance is unmeasured.

## Current native lightweight auto

Current `solver/` offers an opt-in single-stage width 16 / nsym 1 / refine 0 policy and CPU Conv–BN fusion/channels-last. Incomplete terminals route directly to general SAT; witnesses are strictly replayed. WSL has adopted it. The [32-case diagnosis](../algorithms/auto-diagnosis.en.md) is separate from the original 400/20 suites and uses unchanged checkpoints without retraining. `RETRO_AUTO_POLICY=baseline RETRO_INFERENCE_OPT=baseline` selects the old Python policy but does not revert the native undo fix. Reproduce the old frozen source from v0.1.0/commit `32e472e`, without changing banks. Current validation has 11 native plus 17 Python tests; the old nine-native-test record is historical.

## Original reconstruction workflow

1. Check necessary conditions such as stone count and occupancy of the four opening center squares.
2. Try a short direct search for boards with fewer stones.
3. Encode legal placements, flips, forced passes, and the target board as SAT constraints. Search three parallel formulations: no passes, passes only in the late game, and the general formulation.
4. For dense boards, automatic mode also uses a trained model to guide reverse beam search. If no candidate is found, return to SAT from the original target board.
5. Replay the resulting record forward from the standard opening with an independent rules implementation, checking legality and all 64 target cells.

UNSAT for a restricted pass formulation or failure of model-guided search does not by itself establish unreachability. Under time-limited operation, exhausting the limit produces `unknown`. A SAT `found` result is also replay-verified after decoding the assignment into moves. Only unsatisfiability of the general formulation or an invariant violation establishes unreachability in this design. This does not mean that third-party verification of proof traces has been published.

The formal unbounded benchmark removes the overall trial deadline and final general SAT limit; the final Kissat invocation receives no `--time` argument. Short internal probes and candidate-SAT budgets remain algorithmic policies. A common benchmark gate limits the three-formulation portfolio to at most two real Kissat processes at once, with queue and startup time included. This differs from the public service's default configuration. See the [measurement design](../benchmarks/design.en.md).

## Original program's solvers

| Software | Version used | Role | License check status |
|---|---|---|---|
| [Kissat](https://github.com/arminbiere/kissat/tree/rel-4.0.3) | 4.0.3 | External SAT solver and parallel portfolio | [MIT LICENSE](https://github.com/arminbiere/kissat/blob/rel-4.0.3/LICENSE) checked at the specified tag |
| [CaDiCaL Rust binding](https://github.com/mmaroti/cadical-rs) | cadical crate 0.1.16 | SAT calls from Rust | Crate's MIT declaration checked |
| [CaDiCaL](https://github.com/arminbiere/cadical) | 1.9.5 bundled with that crate | Embedded SAT solver | Bundled VERSION and MIT license checked |
| [PyTorch](https://github.com/pytorch/pytorch) | 2.2.2 for the four-environment comparison / 2.6.0 CPU for production-reference measurements | Inference with the custom trained model | BSD-3-Clause and upstream third-party notices; notices are supplied, wheel binaries are not bundled |

Reconstruction search and constraint generation are custom Rust/Python implementations. The trained model ranks reverse candidates; it does not replace a reachability proof or uniquely identify the original game's history.

The training/copy records associate the main `model.pt` with 38,504 mixed-data rows and `model_passes.pt` with the retained old model from 25,796 no-pass rows. The latter filename does not imply pass-only training. Original training files are absent; artifact-specific predictive accuracy and exact retraining reproduction remain unconfirmed. Weights are Release assets under CC BY 4.0, attribution wand125; see the [model card](../../models/MODEL_CARD.en.md). The teachers restrict passes to none or a final 12-move window, and training treats unresolved labels as positives; these conditions must be distinguished from general reachability accuracy.

## Distribution terms and external dependencies

Original source is [MIT](../../LICENSE), and the two synthetic banks retain their existing [MIT scope](../../BENCHMARK_LICENSE.md). Weights/model cards and original article prose/figures are [CC BY 4.0](../../licenses/CC-BY-4.0.txt). Third-party software and cited material retain their respective terms. [LICENSE_SCOPE.md](../../LICENSE_SCOPE.md) distinguishes these grants.

[`solver/THIRD_PARTY_NOTICES.md`](../../solver/THIRD_PARTY_NOTICES.md) supplies notices for nine Rust dependencies and the SAT solvers. [`solver/PYTHON_DEPENDENCIES.md`](../../solver/PYTHON_DEPENDENCIES.md) records Python versions, notices and requirements evidence. r-efi 6.0.0's MIT permission/copyright is retained from AUTHORS. Cargo.toml/lock remain unchanged. Historical records preserve the original Rust/inference measurement hashes; current lightweight source has separate hashes. The release-only removal of bench_fix.py's broad pkill is documented.

Build with Rust 1.98.0 and C++17; install Kissat 4.0.3 separately. The historical v0.1.0 source passed a locked release build, nine unit tests and finite/unbounded SAT smoke checks. Current changes have separate 11-native/17-Python validation. See the [engine guide](../../solver/README.en.md) and [model card](../../models/MODEL_CARD.en.md).

The native v0.1.0 source distribution excludes compiled dependencies, Python wheels, WASM and container images. The separate browser edition includes the compiled WASM and applicable notices described above. Original training JSONL files are absent and are not distributed. Restricted teacher labels, unknown-as-positive training, unconfirmed artifact-specific holdout accuracy and incomplete retraining reproducibility remain scientific limits after source publication. Any later binary/video-library distribution needs a review of its actual bundled components. See [publication scope](publication.en.md).
