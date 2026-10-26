# Native lightweight diagnosis: 32 cases × 3 variants × 3 repeats

See [日本語](../../AUTO_DIAGNOSIS.md) / [English](../../AUTO_DIAGNOSIS.en.md) for definitions, results and limits. This separate WSL experiment has 12 selected 44-disc midgames and all 20 terminal cases; it does not replace the original 400/20 four-environment benchmark or measure browser performance.

- `data/run/`: byte-identical completed 288-row log, metadata, summary and the saved 42-row pre-resume metadata.
- `data/analysis/`: independent legality/statistics audit, separate production functional-smoke summary, and existing-log guided-hit context.
- `data/audits/`: launch, interruption/resume, cleanup, source hashes and native build/test evidence. Exact removal/substitution and original/exported hashes are in [EXPORT_MANIFEST.json (JSON)](EXPORT_MANIFEST.json).
- `sources/`: allowlisted, measured **partial source snapshots**, both driver versions and analysis/tests. These are provenance artifacts, not a standalone engine checkout. The complete current engine is in [`solver/`](../../solver/README.en.md); its Cargo/native/ML tree and separately downloaded weights are needed for execution. Original baseline reproduction uses the frozen source/archive or commit`32e472e`.

Model and native binary payloads are excluded; their measured hashes remain in metadata. Published source updates are listed with repository-relative paths in the export manifest. Ordinary original measurement data and original code retain the repository's [MIT scope](../../BENCHMARK_LICENSE.md); separately distributed weights and third-party components retain their own terms.

The six lightweight candidate misses are distinct from 18 planned incomplete-terminal exact routes. All 288 final witnesses passed independent replay. Program wall preserves interrupted work and setup; its unallocated residual is not assigned to an individual case or counted as a failure. Production Torch 2.6 functional smokes are distinct from the Torch 2.2.2 comparison.
