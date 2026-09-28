# Audit Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Audit all PaperSpine outputs before declaring the workflow complete.

## Required Checks

1. Artifact completeness.
2. Reference material workspace has `source_index.md`.
3. Contribution and aligned motivation were user-confirmed after research;
   `contribution_check.py` passed before planning.
4. Balanced mode has a substantive `section_blueprints.md`; strict mode also
   requires an ordered `writing_rationale_matrix.md`.
5. `results_validation.md` passed during planning for journal, conference, and
   competition scenes.
6. `structured_review.md` contains a completed editor synthesis before LaTeX
   assembly; balanced mode accepts free-form editorial judgment, while strict
   mode also requires `reviewer_audit.md` and its checker.
7. No append-only or shallow revision for substantive rewrite tasks.
8. Logic transfer from original draft or materials.
9. Claim support from user evidence.
10. LaTeX citation, label, figure safety.
11. `citation_support_bank.md` follows its literature contract: open-literature
    breadth/recency, or closed-corpus exhaustive deduplication and honest scope.
12. `scientific_evidence_ledger.json` resolves S/C/N/M/O/R links and final
    verification states for evidence-bearing scenes.
13. Final LaTeX source plus hash-bound rendered page/figure inspection.
14. Word output structurally valid by default; skip only when
   `word_output=none` is explicit in config.
15. Submission metadata passes its check. When publication-cycle work is in
    scope, the current target profile passes; a submission/revision has a READY
    immutable bundle and matching archive checksum; a rebuttal passes atomic
    coverage and lineage checks; and a transfer has completed the destination
    rebuild after a READY_TO_REBUILD delta.
16. Publication surface contains no internal evidence IDs or gate narration.
17. Usage telemetry contains measured usage or explicit
    `telemetry_unavailable` receipts; file bytes never stand in for billed tokens.
18. Translation coverage complete when `translation_package=zh`.
19. When `translation_package=zh` and Word output is enabled,
    `final_paper/paper.zh.docx` and `word_report.zh.md` exist and pass. The
    `translation_zh/` folder is an audit/intermediate package, not the final
    Chinese Word deliverable.

## Scripts

```bash
python scripts/integrity_audit.py paper_rewriting_output --markdown --write
python scripts/artifact_check.py paper_rewriting_output --markdown --write
python scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --markdown --write
python scripts/scientific_evidence_check.py paper_rewriting_output --phase final --markdown --write
python scripts/publication_surface_check.py paper_rewriting_output --markdown --write
python scripts/visual_readiness_check.py paper_rewriting_output --markdown --write
python scripts/metadata_readiness_check.py paper_rewriting_output --markdown --write
python scripts/usage_ledger.py paper_rewriting_output --markdown --write
python scripts/progress_check.py paper_rewriting_output --markdown --write
python scripts/revision_audit.py <original> <revised> --markdown
python scripts/structured_review.py paper_rewriting_output --markdown --write
# strict mode only:
python scripts/structured_review.py paper_rewriting_output --dispatch
python scripts/citation_quality_audit.py paper_rewriting_output --write
python scripts/latex_guard.py <main.tex> --bib <references.bib> --markdown
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx --tex paper_rewriting_output/final_paper/main.tex --markdown --output paper_rewriting_output/word_report.md
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx --tex paper_rewriting_output/final_paper/main.tex --markdown --output paper_rewriting_output/word_report.zh.md
# when a target-specific publication cycle is in scope:
python scripts/publication_cycle.py profile-check <profile.json> --markdown --write
python scripts/publication_cycle.py assemble <profile.json> <plan.json> <bundle-dir> --markdown
python scripts/publication_cycle.py rebuttal-check <review_round.json> --markdown --write
python scripts/publication_cycle.py transfer-plan <origin-profile.json> <destination-profile.json> <transfer-request.json> <delta-dir> --markdown
```

## Required Outputs

- `integrity_audit.md`, `artifact_check.md`, `revision_audit.md`
- `structured_review.md` and `citation_quality_audit.md`; strict mode also
  requires `reviewer_audit.md`; `logic_transfer_audit.md`
- `scientific_evidence_check.md`, `visual_audit_manifest.json`,
  `visual_readiness_check.md`, `publication_surface_check.md`
- `submission_metadata.json`, `metadata_readiness_check.md`,
  `usage_ledger.jsonl`, `token_budget_by_stage.md`
- A passed `target_profile_check.md`; a READY `bundle_manifest.json`,
  `submission_bundle.zip`, and matching `submission_bundle.sha256` (when applicable)
- A passed `rebuttal_check.md` and rendered response/change artifacts (when applicable)
- `transfer_delta.json` plus the newly rendered destination paper and READY
  destination bundle (when applicable)
- `final_paper/paper.zh.docx` and `word_report.zh.md` when
  `translation_package=zh`

Do not declare the task complete if required artifacts are missing, claims are
unsupported, the integrated editor synthesis is still pending, translation is
partial, a strict-mode rationale matrix is generic, or the final Chinese Word
document is missing. A green canonical manuscript audit does not override a
blocked target package, rebuttal, or transfer rebuild.

## Output Directory Rules

The workflow root is `paper_rewriting_output/`. All artifacts must live inside
it. The following are hard errors that prevent completion:

- **No nested directories:** Do not create `paper_rewriting_output/` inside
  `paper_rewriting_output/`. If a nested inner directory is detected, move all
  contents up one level and remove the inner directory.
- **No sibling final_paper:** `final_paper/` must exist only inside
  `paper_rewriting_output/`, never as a sibling next to it. If both exist,
  remove the sibling copy outside `paper_rewriting_output/`.
- **No misplaced artifacts:** `writing_rationale_matrix.md`,
  `citation_support_bank.md`, `research_dossier.md`, and other workflow
  artifacts belong inside `paper_rewriting_output/`, not outside it.

## Completion Hard Gate

Before declaring the workflow complete, run the checks below in order.
`progress_check.py --gate final_audit` is the authoritative hard gate: it
re-runs `artifact_check.py`, `citation_bank_check.py`, `integrity_audit.py`,
`citation_quality_audit.py`, evidence, visual, metadata, publication-surface,
and usage-ledger checks, the required `word_guard.py` check, and — once
`final_paper/main.tex` exists — `latex_guard.py` and `section_economy_check.py`,
then fails on any non-zero exit code. In balanced mode,
`section_economy_check.py` is advisory; strict mode may explicitly enforce the
configured section budget.
Do not treat existing report files as enough evidence of completion.

These last two read the manuscript body, not just report shapes:
`latex_guard.py` fails literal-bracket citations that are not real `\cite`
links and out-of-sync numbering; `integrity_audit.py` fails writing-process /
meta-narrative language (supervisor or reviewer mentions, "reorganized the
paper", transcribed `A -> B -> C` plan chains) leaking into the prose; and
`section_economy_check.py` surfaces unusually fragmented sectioning for
editorial review. Section count alone does not fail a balanced paper. A clean
report file is not enough — the body and completed editor synthesis must agree
that the paper is ready.

```bash
python scripts/artifact_check.py paper_rewriting_output --markdown --write
python scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --markdown --write
python scripts/scientific_evidence_check.py paper_rewriting_output --phase final --markdown --write
python scripts/publication_surface_check.py paper_rewriting_output --markdown --write
python scripts/visual_readiness_check.py paper_rewriting_output --markdown --write
python scripts/metadata_readiness_check.py paper_rewriting_output --markdown --write
python scripts/usage_ledger.py paper_rewriting_output --markdown --write
python scripts/progress_check.py paper_rewriting_output --gate final_audit
python scripts/integrity_audit.py paper_rewriting_output --markdown --write
python scripts/progress_check.py paper_rewriting_output --markdown --write
```

When `word_output` is not explicitly `none` and `output_language` is not `zh`,
also run:

```bash
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx --markdown --output paper_rewriting_output/word_report.md
```

When `translation_package=zh` or `output_language=zh`, also run:

```bash
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx --markdown --output paper_rewriting_output/word_report.zh.md
```

When `translation_package=zh`, also run and require PASS:

```bash
python scripts/translate_guard.py paper_rewriting_output --markdown --write
```

The final Chinese Word file must be predominantly Chinese and free of visible
Markdown emphasis markers such as `**bold**` or `*italic*`. A `.zh.docx` file
that contains English body prose under a Chinese title is a failed translation
package.

You may declare completion only when `progress_check.py --gate final_audit`
exits 0, `artifact_check.py` exits 0, final progress reports
`is_complete=true`, no `misplaced_artifacts` are reported, integrity audit has
no unresolved BLOCKER, and all five independent readiness dimensions are true:
`scientific_content_ready`, `visual_ready`, `citation_verified`,
`metadata_ready`, and `artifact_portable`. A PASS in one dimension cannot
offset a failure in another. Word output must be present and valid unless the
user explicitly opted out. If pandoc is unavailable, write BLOCKED/FAIL in
`latex_report.md`; do not silently skip Word or claim the workflow is complete.

## Anti-Pass-Through Rule

**If `artifact_check.md` reports Status: FAIL or Status: BLOCKED, the workflow
is not complete.** Do not declare completion. Do not write `progress.md` with
`is_complete=true`. Return to the failing upstream stage:

- Missing artifacts → run that stage.
- Content issues (weak rationale matrix, thin citation bank) → fix the
  artifact, then re-run `artifact_check.py`.
- Misplaced artifacts → move them into `paper_rewriting_output/`.

**If `citation_bank_check.md` reports Status: FAIL, the citation support bank
is not qualified.** The final audit must not pass until the bank is re-run and
all weak rows are strengthened with reference format + claim-support sentences.

In strict mode, a present but generic rationale matrix fails. Balanced mode does
not require the matrix and must not block a scientifically supportable paper for
missing row-level paperwork.
