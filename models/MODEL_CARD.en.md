# Othello Retro — Legacy model card

[日本語](MODEL_CARD.ja.md) | [English](MODEL_CARD.en.md) · [Loading guide](README.en.md) · [Weight license](LICENSE-WEIGHTS.md)

## Distribution and identity

The owner has authorized distribution of these two existing weights as GitHub Release assets under CC BY 4.0, with attribution to **wand125**. The accompanying original READMEs and model cards also use CC BY 4.0. This is separate from the custom code's MIT license. The intended use and scientific limitations below impose no additional legal restrictions on uses permitted by CC BY 4.0.

| File | SHA-256 | Bytes | Record-supported lineage |
|---|---|---:|---|
| `model.pt` | `dfb1f2e6a7ad4536415d3df9758c0a2e72af95abb40dfaae3c55f1921aee9820` | 1,257,333 | 38,504 mixed no-pass/pass-aware rows, 12 epochs |
| `model_passes.pt` | `8c3bc353fc136feb0561263bf75bac0dc7e491d261c124ca408fc100e6ce3c2d` | 1,256,602 | Retained old model: 25,796 no-pass rows, 12 epochs |

**The name `model_passes.pt` does not mean it was trained exclusively on pass-aware examples.** It names the old model retained for the pass-aware beam stage. The main `model.pt` corresponds to mixed training that includes pass-containing games.

The weights were not retrained for this release. Original training JSONL files are unavailable and are not included. The public benchmark banks are different datasets from these training files.

## Purpose and architecture

This evaluator ranks one-move predecessor candidates during reverse board search. It neither uniquely identifies the original game's history nor proves general reachability. Its output is a single logit, not a calibrated reachability probability.

- `Net(False)` in `solver/ml/train.py` (`ml/train.py` relative to the `solver/` implementation root): 307,841 parameters and 67 state-dictionary tensors.
- Input: `5×8×8` planes for the predecessor's own stones, opponent stones, empty squares, removed stone, and color-changed stones.
- Moving color comes from label field `c` when present; otherwise it is inferred from move-count parity under a no-pass assumption.
- A 5→64-channel 3×3 convolution/BatchNorm/ReLU stem, four two-layer 64-channel residual blocks, concatenated spatial mean and maximum, and a 128→64→1 head. The seven scalar features are omitted.
- Inference may average logits across four opening-preserving symmetries.

Torch 2.2.2 CPU loading with `weights_only=True` and strict state-dictionary matching has been checked. Every saved floating tensor is finite FP32. The saved device tag is MPS, but the weights load through CPU mapping.

## Data and teacher provenance

Recovered generation/training records show custom synthetic legal games alternating random and greedy play, followed by generation of true predecessors and sibling undo candidates. The no-pass generator accepts full 64-disc games with zero passes; the pass-aware generator accepts full 64-disc games with at least one pass. This is not a uniform sample of all possible boards.

| Recorded stage | Size and operation |
|---|---|
| 16 and 48 no-pass games | 6,469 and 19,327 labeled rows; merge to 25,796 with offset game IDs |
| 40 games containing passes | 12,708 labeled rows |
| Combined data | 25,796 + 12,708 = 38,504 rows, with offset game IDs |

These counts come from execution records, not a fresh count of the original files. Multiple correlated examples come from each game, so row count is not independent-game count. Labeled parents contain 17–64 discs, and predecessor candidates 16–63 discs.

The teacher labels have important restrictions:

1. Candidates matching the known trajectory are positives.
2. Other no-pass candidates use `nopass,occ` SAT. UNSAT means unreachable without passes, not generally unreachable.
3. Other pass-aware candidates use `reach` with a specified next mover, but permit passes only in a final 12-move window. Its UNSAT also does not establish general unreachability.
4. `train_final.py` uses **`unknown_as_pos=True`**, rewriting every unresolved `y=-1` to positive label 1. The teacher budget is two seconds. Treating timeouts or other unresolved outcomes as positives is a learning policy, not a reachability proof.

Thus, negatives may include generally reachable positions and positives may be unproven. General unreachability does not follow from a low model score or failed guided search. Evaluation requires SAT and strict forward replay checks alongside the model.

## Training recipe and confidence in the lineage

The recorded final runs initialize a fresh `Net(False)` without loading external pretrained weights. They use four symmetries—identity, main diagonal, anti-diagonal, and 180-degree rotation—batch size 256, `torch.manual_seed(0)`, AdamW with learning rate 0.002 and weight decay 0.0001, CosineAnnealingLR, BCEWithLogitsLoss, and 12 epochs. Final training uses all loaded rows without a holdout split.

Training-completion/copy records, architecture, and saved archive identifiers support the filename mapping above. All nine BatchNorm update counters equal 7,224 in the main model and 4,848 in the old model, matching `12×ceil(38504×4/256)` and `12×ceil(25796×4/256)`. This strongly corroborates the lineage. It is not a cryptographic binding of all current weight bytes to original training inputs, because historical dataset and intermediate-checkpoint hashes are absent.

A contemporaneous preflight reported Torch 2.12.1 with MPS available. Individual training runs lack full environment locks. The Torch 2.2.2 CPU loading check does not reproduce the original training environment.

## Evaluation and reproducibility limits

**Artifact-specific holdout AUC and calibration of these two final weights have not been established.** AUC from separately initialized exploratory training is not assigned to these weights. Reconstruction benchmarks combining models with SAT also differ from stand-alone classification accuracy.

The original training-file bytes, row order, per-label evidence, and complete environment manifests have not been recovered. Time-limited teachers, parallel output ordering, and MPS/library differences also prevent a claim that published code and seeds regenerate the original datasets or weights byte-for-byte.

## Owner statement and evidential scope

The owner regards the weights as self-created and explicitly authorized their distribution and license selection. Recovered generation/training records support a custom synthetic-game, undo-candidate, and SAT-teacher pipeline. No external human-game corpus or pretrained weight input was found in the recorded final training pipeline.

This does not establish absence of external-data mixing through a complete audit of the unavailable original data. Owner authorization, record-supported provenance, and limits of the data audit are separate facts.

PyTorch, NumPy, and SAT solvers are external dependencies, not bundled in this model asset. Their licenses are separate from the weights' CC BY 4.0 license.
