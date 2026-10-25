# Acceptance fixtures and test code / 受入れデータと検証コード

The JavaScript tests are original code under [MIT](../LICENSE), Copyright (c) 2026 wand125 and contributors.

`cases.json` preserves the existing source publication terms per entry:

| Fixtures | Terms | Attribution/source |
|---|---|---|
| 11 reachable initial/opening/bank/example positions, plus `missing-center` | MIT; existing bank/original-example policy | wand125 and contributors; each case's source file, JSON location and source SHA-256 |
| `paper-two-placement-unreachable`, `paper-deep-root-61` | [CC BY 4.0](licenses/CC-BY-4.0.txt); existing article-content policy | **wand125**, [Othello Retro article](https://othello-retro.logicpuzzle.app/paper), and each case's `attribution.source_data` |

Article-derived material was extracted into the acceptance-fixture schema, with proof-scope and source metadata added. The board positions and any reference move sequences were not altered. Preserve attribution, license/source links and an indication of later changes when redistributing the CC BY material. This file does not relicense the original banks, article, external works or third-party runtime components.

`source` and `sources` in the JSON identify the original file/JSON location and file hash. `license` and `attribution` state the per-case policy; this mixed fixture file is not assigned one blanket MIT grant. Recorded general UNSAT is distinct from independent DRAT verification: no DRAT trace was generated or checked for the deep fixture.

検証コードはMITです。14データのうち既存bank・自作例由来12件はMIT、上記の論文由来2件はCC BY 4.0を維持します。著作者wand125、論文とcase別の元データURL、抽出・メタデータ追加の変更を表示します。元の盤面・参照棋譜は不変です。データ全体や第三者runtimeを一括してMITへ変更するものではありません。
