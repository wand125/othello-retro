# Python dependency scope and version evidence

This archive contains original Python source, requirements, and notices only;
it does not vendor Python package source, wheels, native libraries or an
environment. Our code is MIT. The dependencies retain their upstream licenses.

| Use | Dependency | Version evidence | Upstream terms |
|---|---|---|---|
| inference and final CNN training | PyTorch2.2.2 | all four formal CPU222 runs and their preparation records | BSD-3-Clause, with additional upstream bundled-component notices |
| inference and training | NumPy1.26.4 | same four runs | BSD-3-Clause and upstream bundled-component notices |
| `train.py` comparison only | scikit-learn1.7.2 | installed distribution metadata in the review environment | BSD-3-Clause |
| optional comparison dependencies | SciPy1.15.3, joblib1.5.3, threadpoolctl3.6.0 | installed distribution metadata; satisfy scikit-learn's declared requirements | upstream BSD-family terms and distribution notices |

The inference requirements are direct pins, not a complete platform-specific
wheel lock. `licenses/python-inference-inventory.json` inventories the actual
CPU222 inference dependencies. The optional training comparison pins were
observed during this release review. They are not evidence of the exact
historical environment that produced either weight file; do not infer
bit-for-bit retraining reproducibility. `train_final.py` does not import
scikit-learn and can use the inference requirements alone.

PyTorch2.2.2 has CPU-capable wheels for the documented Python3.12 macOS ARM,
macOS Intel and Linux configurations. Architecture, BLAS/MKL/oneDNN/Accelerate,
OS, compiler, memory and scheduling can still change performance. Use a new
venv, not an existing user's global environment. For CUDA or another Python
version, follow the upstream installation instructions and record changes.
No GPU training recipe is asserted by these CPU pins.

Exact upstream distribution notices for torch2.2.2 and numpy1.26.4 are included
under `licenses/python-*`; optional comparison-package notices are included
where supplied by their installed distribution. They describe upstream
components, some not present in this source-only archive, and are not a claim
that every wheel/binary distribution is covered by the project's MIT license.
If distributing an environment/container/binary, review the actual bundled
native files and their complete notices separately.

Primary references:
- https://pytorch.org/get-started/previous-versions/#v222
- https://github.com/pytorch/pytorch/blob/v2.2.2/LICENSE
- https://github.com/numpy/numpy/blob/v1.26.4/LICENSE.txt
- https://github.com/scikit-learn/scikit-learn/blob/1.7.2/COPYING
