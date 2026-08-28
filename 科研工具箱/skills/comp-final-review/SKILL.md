---
name: comp-final-review
description: Use when a mathematical modeling competition submission requires a final evidence-based re-review after edits and before delivery.
---

# Competition Final Review

## Inputs

Read the final paper source and PDF, executable code, `RESULTS.md`, `figures/all_results.json`, `CONSISTENCY_REPORT.json`, `LITERATURE.md`, literature search evidence, `COMP_REVIEW_VERDICT.json`, `VISUAL_REVIEW_VERDICT.json`, and `EDITOR_CHANGELOG.md`. If any required input is absent, record it as a fatal verification gap.

## Execution

1. Confirm every earlier fatal finding is fixed with traceable evidence, or remains explicitly unresolved.
2. Recheck the paper's central claims against the canonical result ledger and consistency report.
3. Recheck citation closure, compilation state, figure review status, and delivery-file completeness.
4. Do not repeat a prior verdict blindly: inspect the edited source and the final PDF independently.
5. Classify every issue as `fatal`, `major`, or `minor`; a fatal is any missing required evidence, unresolved leakage, unsupported central claim, invalid result trace, or competition-format blocker.

## Outputs

Write `FINAL_REVIEW.md` with the reviewed inputs, evidence locations, findings, and required remediation. Write `FINAL_REVIEW_VERDICT.json` as an object containing `findings` and integer `fatal_count`; each finding must include an ID, severity, location, evidence, and fix. Write `REVIEW_EXECUTION_EVIDENCE.json` with the independently completed `reviewer`, `visual_reviewer`, `editor`, and `final_reviewer` role records. Each role record must contain `session_id`, `model`, `output_file`, `output_sha256`, and `completed_at`; calculate the hash from the final workspace output file. The primary agent writes this evidence after receiving read-only child-agent conclusions. A nonzero fatal count blocks `comp-final-audit`. If a visual API was unavailable, retain its `unavailable` status rather than converting it to a pass.
