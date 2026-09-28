# Audit Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Audit all PaperSpine outputs before declaring the workflow complete.

## Required Checks

1. Artifact completeness.
2. Reference material workspace has `source_index.md`.
3. Motivation was user-confirmed after research.
4. `writing_rationale_matrix.md` exists, is ordered, and covers whole-work
   framework + task-specific writing units.
5. No append-only or shallow revision for substantive rewrite tasks.
6. Logic transfer from original draft or materials.
7. Claim support from user evidence.
8. LaTeX citation, label, figure safety.
9. `citation_support_bank.md` count, recency, quality, and Source Channel audit.
10. Final LaTeX source; PDF when TeX available.
11. Word output structurally valid by default; skip only when
    `word_output=none` is explicit in config.
12. Submission materials pass `submission_check.py`.
13. Translation coverage complete when `translation_package=zh`.
14. When `translation_package=zh` and Word output is enabled,
    `final_paper/paper.zh.docx` and `word_report.zh.md` exist and pass. The
    `translation_zh/` folder is an audit/intermediate package, not the final
    Chinese Word deliverable.

## Scripts

```bash
python scripts/integrity_audit.py paper_rewriting_output --markdown --write
python scripts/artifact_check.py paper_rewriting_output --markdown --write
python scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --markdown --write
python scripts/progress_check.py paper_rewriting_output --markdown --write
python scripts/revision_audit.py <original> <revised> --markdown
python scripts/structured_review.py paper_rewriting_output --dispatch
python scripts/citation_quality_audit.py paper_rewriting_output --write
python scripts/latex_guard.py <main.tex> --bib <references.bib> --markdown
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx --tex paper_rewriting_output/final_paper/main.tex --markdown --output paper_rewriting_output/word_report.md
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx --tex paper_rewriting_output/final_paper/main.tex --markdown --output paper_rewriting_output/word_report.zh.md
python scripts/submission_check.py paper_rewriting_output/submission_package --fix-fonts --markdown --write
```

## Required Outputs

- `integrity_audit.md`, `artifact_check.md`, `revision_audit.md`
- `structured_review.md` (uses scene-aware reviewer personas from config; does
  not fabricate venue rules, only what the research stage or user provides),
  `citation_quality_audit.md`, `logic_transfer_audit.md`
- `submission_package/submission_check.md` (when applicable)
- `final_paper/paper.zh.docx` and `word_report.zh.md` when
  `translation_package=zh`

Do not declare the task complete if required artifacts are missing, claims are
unsupported, translation is partial, the rationale matrix is generic, or the
final Chinese Word document is missing.

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
`citation_quality_audit.py`, the required `word_guard.py` check, and — once
`final_paper/main.tex` exists — `latex_guard.py` and `section_economy_check.py`,
then fails on any non-zero exit code.
Do not treat existing report files as enough evidence of completion.

These last two read the manuscript body, not just report shapes:
`latex_guard.py` fails literal-bracket citations that are not real `\cite`
links and out-of-sync numbering; `integrity_audit.py` fails writing-process /
meta-narrative language (supervisor or reviewer mentions, "reorganized the
paper", transcribed `A -> B -> C` plan chains) leaking into the prose; and
`section_economy_check.py` fails a top-level section count above the
applied-paper budget (4-6). A clean report file is not enough — the body must
pass.

```bash
python scripts/artifact_check.py paper_rewriting_output --markdown --write
python scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --markdown --write
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
no unresolved BLOCKER, and Word output is present and valid unless the user
explicitly opted out. If pandoc is unavailable, write BLOCKED/FAIL in
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

**If `writing_rationale_matrix.md` rows are too thin (generic cells, fewer than
8 rows, first-row framework missing), `artifact_check.py` will report FAIL.**
The progress gate will not clear until the matrix is rewritten with concrete
motivation, reference/SOTA, target-scene, evidence, and text-move anchors per
row.
