# Browser ONNX models

Copyright (c) 2026 wand125. CC BY 4.0.

Derived from the published model.pt / model_passes.pt checkpoints:
https://github.com/wand125/othello-retro/releases/tag/v0.1.0

Changes: strict-loaded eval checkpoints were cloned, nine Conv/BatchNorm pairs were folded and exported as FP32 ONNX opset17, dynamic NCHW batch. No retraining or quantization. The source checkpoint files are unchanged. Converted graph hashes, checkpoint hashes, numerical validation conditions and modification details are in model-export-manifest.json. No original training data is included.

Attribution: wand125, Othello Retro. License: https://creativecommons.org/licenses/by/4.0/

These converted weights remain CC BY 4.0. Application code and ONNX Runtime retain their separate licenses.
