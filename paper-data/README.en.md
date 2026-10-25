# Supplementary article data

[日本語](README.md) | English

This directory contains boards, game records, figure inputs and verification conditions supporting the [Japanese article](https://othello-retro.logicpuzzle.app/paper?lang=ja) and its [English version](https://othello-retro.logicpuzzle.app/paper?lang=en). Explanations belong to the article itself.

| File | Contents |
|---|---|
| [article-data.json](article-data.json) | The exact JSON loaded by the article's figures: reconstructed games, shallow predecessors and pass examples |
| [deep-reverse-chain.json](deep-reverse-chain.json) | Additional verified data, not displayed in the current article: the eleven-step reverse chain, moving colors, replay checks, general-SAT configuration/result and CNF hash |
| [manifest.json](manifest.json) | SHA-256 hashes for the data and corresponding manuscript assets, plus the verified scope |

Data records distinguish verified and unverified claims. This supplement does not distribute the original solver, models, CNF file or private usage logs.

Performance datasets, schedules and completed timing results are managed separately under `benchmarks/`; see the [benchmark design](../MEASUREMENT_DESIGN.en.md).
