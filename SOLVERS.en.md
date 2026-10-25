# Solvers and dependencies

[日本語](SOLVERS.md) | [English](SOLVERS.en.md)

## Public measurement tools and the original engine

The published `runner/` contains general-purpose measurement tools using only the Python 3.10+ standard library. It includes no SAT solver or trained model. You can connect your own external reconstruction program. See the adapter guide in [日本語](runner/README.md) or [English](runner/README.en.md).

The following describes the reconstruction engine and dependencies used by the public service and original program's experiments. That engine and its trained models are not distributed. The public runner's standard-library dependencies are separate from the original engine's Rust, ML, and video-related dependencies.

## Original reconstruction workflow

1. Check necessary conditions such as stone count and occupancy of the four opening center squares.
2. Try a short direct search for boards with fewer stones.
3. Encode legal placements, flips, forced passes, and the target board as SAT constraints. Search three parallel formulations: no passes, passes only in the late game, and the general formulation.
4. For dense boards, automatic mode also uses a trained model to guide reverse beam search. If no candidate is found, return to SAT from the original target board.
5. Replay the resulting record forward from the standard opening with an independent rules implementation, checking legality and all 64 target cells.

UNSAT for a restricted pass formulation or failure of model-guided search does not by itself establish unreachability. Under time-limited operation, exhausting the limit produces `unknown`. A SAT `found` result is also replay-verified after decoding the assignment into moves. Only unsatisfiability of the general formulation or an invariant violation establishes unreachability in this design. This does not mean that third-party verification of proof traces has been published.

The formal unbounded benchmark removes the overall trial deadline and final general SAT limit; the final Kissat invocation receives no `--time` argument. Short internal probes and candidate-SAT budgets remain algorithmic policies. A common benchmark gate limits the three-formulation portfolio to at most two real Kissat processes at once, with queue and startup time included. This differs from the public service's default configuration. See the [measurement design](MEASUREMENT_DESIGN.en.md).

## Original program's solvers

| Software | Version used | Role | License check status |
|---|---|---|---|
| [Kissat](https://github.com/arminbiere/kissat/tree/rel-4.0.3) | 4.0.3 | External SAT solver and parallel portfolio | [MIT LICENSE](https://github.com/arminbiere/kissat/blob/rel-4.0.3/LICENSE) checked at the specified tag |
| [CaDiCaL Rust binding](https://github.com/mmaroti/cadical-rs) | cadical crate 0.1.16 | SAT calls from Rust | Crate's MIT declaration checked |
| [CaDiCaL](https://github.com/arminbiere/cadical) | 1.9.5 bundled with that crate | Embedded SAT solver | Bundled VERSION and MIT license checked |
| [PyTorch](https://github.com/pytorch/pytorch) | 2.2.2 for the four-environment comparison / 2.6.0 CPU for production-reference measurements | Inference with the custom trained model | BSD-style license and bundled third-party notices remain under review |

Reconstruction search and constraint generation are custom Rust/Python implementations. The trained model ranks reverse candidates; it does not replace a reachability proof or uniquely identify the original game's history.

The training/copy records associate the main `model.pt` with 38,504 mixed-data rows and `model_passes.pt` with the retained old model from 25,796 no-pass rows. The latter filename does not imply pass-only training. Original training files are absent; artifact-specific predictive accuracy and exact retraining reproduction remain unconfirmed. An explicit license and publication decision for the weights are also pending. The teachers restrict passes to none or a final 12-move window, and training treats unresolved labels as positives; these conditions must be distinguished from general reachability accuracy.

## Distribution terms and remaining checks

The public runner and the two synthetic midgame/endgame test banks are [MIT-licensed](BENCHMARK_LICENSE.md). They may be used, modified, and redistributed with other programs. This permission does not mean that licensing and dependency review for the original engine or models is complete.

A 31-file Rust-only source candidate has notices packaged for nine locked dependencies. The same source passed a WSL/Rust 1.98.0 locked release build, all nine unit tests with Kissat 4.0.3, finite/unbounded SAT smoke tests, and independent replay of the records. MIT terms for the custom Rust code remain a proposal awaiting the owner's decision, so **the original engine has not been distributed**. Python/ML/video implementations, weights, original training data, and binaries are excluded from this candidate.

Remaining checks are separated by distribution scope:

- The owner's decision on Rust candidate provenance, attribution, proposed custom-code MIT terms, and publication.
- Python and native-library dependencies and notices.
- Distribution terms for training code and weights, with revalidation limits caused by missing original training data.
- Additional dependencies of the local video version. Video features are not included in the simple public service.
- Separate distribution terms for original custom code, text, and data outside the stated MIT scope.

Listing a license such as MIT does not license the whole project on those terms. A [declared-license and notice-file inventory](licenses/rust-dependency-inventory.json) is published for nine locked Rust dependencies. Exact archive checksums and required notices have been checked. r-efi 6.0.0's MIT permission text and copyright attributions were found in `AUTHORS` and included in the source-only candidate, resolving the earlier missing-notice issue. This does not complete a project-wide audit covering Python/ML/video components or distributed binaries.

See [code publication scope](CODE_PUBLICATION.en.md) for the stages and outstanding work.
