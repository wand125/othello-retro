# Othello Retro model weights

[日本語](README.md) | [English](README.en.md)

These two weights are distributed as GitHub Release assets; they need not be committed to Git history. Read the [model card](MODEL_CARD.en.md) for provenance, teacher-label, and evaluation limitations. Original training JSONL files are not needed for inference.

## Download and verify

1. Obtain the matching source release, `model.pt`, `model_passes.pt`, and `SHA256SUMS` from the [project Releases](https://github.com/wand125/othello-retro/releases). Extract the model archive if one is provided.
2. Place both weights and `SHA256SUMS` together, and verify from that directory. The checksum file covers only the two weights.

```sh
# Linux
sha256sum -c SHA256SUMS
# macOS
shasum -a 256 -c SHA256SUMS
```

3. In the source checkout, place the files at `solver/ml/model.pt` and `solver/ml/model_passes.pt`. Keep them in the same directory. The main model uses mixed data; `model_passes.pt` is the old no-pass model. Do not swap them based on their names.
4. Run the examples below from the source checkout's implementation root, `solver/`. The extracted model archive directory is not that implementation root; move to the matching source's `solver/` first.

```sh
# From the source repository root
cd solver
```

## CPU loading example

Loading was checked with Python 3.12, Torch 2.2.2, and NumPy 1.26.4. Install PyTorch and NumPy separately for your platform. Run the following from the matching source checkout's implementation root, `solver/`. Importing/loading `Net` does not require the training-only scikit-learn dependency.

```python
from pathlib import Path
import sys
import torch

sys.path.insert(0, "ml")
from train import Net

torch.set_num_threads(2)
model_dir = Path("ml")
for filename in ("model.pt", "model_passes.pt"):
    state = torch.load(
        str(model_dir / filename),
        map_location="cpu",
        weights_only=True,
    )
    net = Net(False).to(device="cpu", dtype=torch.float32)
    net.load_state_dict(state, strict=True)
    net.eval()
    print(filename, sum(p.numel() for p in net.parameters()))
```

Each model should report 307841 parameters. CPU mapping loads the weights despite their saved MPS device tags. This checks loading, not reversal search or predictive accuracy. See the model card and `planes` in `ml/train.py` for the five input-plane definitions.

Full reconstruction additionally requires the Rust executable and external tools such as Kissat. After placing the models in the repository's `solver/ml/` directory (`ml/` relative to the implementation root), follow the matching source version's `solver/README.md` for build and search instructions.

## License and contents

The two weights and the accompanying original READMEs and model cards use **CC BY 4.0, with attribution to wand125**. See [LICENSE-WEIGHTS.md](LICENSE-WEIGHTS.md), the [included legal code](CC-BY-4.0.txt), and the [official license](https://creativecommons.org/licenses/by/4.0/). This is separate from the custom project's code under MIT.

This model asset contains the two weights, checksums/manifest, Japanese and English guides/model cards, and license information. It does not contain original training data, private execution logs, credentials, PyTorch/NumPy, or SAT solver implementations. Original training files are unavailable; exact retraining reproduction and final-artifact-specific holdout accuracy remain unestablished.
