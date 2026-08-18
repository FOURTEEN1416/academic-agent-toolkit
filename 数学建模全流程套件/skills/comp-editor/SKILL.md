---
name: comp-editor
description: Use when a mathematical modeling competition draft needs controlled edits in response to documented reviewer findings.
---

# Competition Editor

## Inputs

Read `COMP_REVIEW_VERDICT.json`, `VISUAL_REVIEW_VERDICT.json`, the associated markdown reports, the current paper sources, captions, and the canonical result ledger. Treat a missing report or invalid verdict as a blocking issue, not an invitation to infer reviewer intent.

## Execution

1. Build a list of unresolved finding IDs and their requested fixes.
2. Modify prose, captions, layout, references, or declared delivery materials only for those IDs.
3. Do not alter data, model outputs, equations, or headline metrics without a new computation, updated result ledger, and fresh execution evidence from the responsible step.
4. Preserve unresolved fatal findings in the changelog and route them back to modeling, code, or paper writing instead of hiding them through wording changes.
5. Re-run the narrow validation relevant to every changed file, then return the workspace to the final reviewer.

## Outputs

Write `EDITOR_CHANGELOG.md`. For every reviewed finding ID, record the disposition (`fixed`, `unresolved`, or `not_applicable`), changed files, a concise description of the edit, the validation command or manual check, and the reason for any unresolved item. Do not claim the paper is delivery-ready; only `comp-final-review` and `comp-final-audit` may make that decision.
