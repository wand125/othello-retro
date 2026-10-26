# Layout and provenance

[日本語](repository.md) | [English](repository.en.md)

`browser-wasm/`, `solver/`, and `short/` contain the static browser implementation, native reconstruction engine, and server-oriented vertical UI. Their guides stay with the implementations. Shared measurement and verification tools live in `runner/`; explanations and result interpretation live in `docs/`.

## Frozen data and source

Preserve paths and bytes of existing banks, schedules, raw results, and manifested experiment snapshots. Add new measurements in separately named result directories and use the [common runner's verification and export](../runner/VALIDATION.en.md). Keep measured source hashes so historical results are not attributed to current code.

`browser-wasm/engine/native/` is a pinned source snapshot used for WASM builds. `solver/history/` contains historical distribution checks. Neither is interchangeable with current source or current test evidence. Updates require explicit provenance and validation. Browser model-conversion tools live in `browser-wasm/model-tools/`.

Release tags and attached artifacts describe historical distributions. Root `RELEASE_FILES.json` inventories current tracked files. Moving documentation does not justify rewriting experiment manifests to describe a new layout.

## Private output and distribution

Keep runtime output in locations such as `.runs/` and user configuration in `*.local.json`. Credentials, usage logs, browser identifiers, and private infrastructure settings are excluded from public artifacts. `.pt` and converted `.onnx` weights are Release assets; Git stores their identifiers and terms.

Retain third-party runtimes and notices with the implementation. See [LICENSE_SCOPE.md](../LICENSE_SCOPE.md).
