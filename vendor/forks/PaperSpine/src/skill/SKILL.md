---
name: paper-spine
description: Write, rewrite, or build a paper or report (journal, conference, report, review, competition) end to end, then output LaTeX/PDF/Word. The main PaperSpine entry point that orchestrates every step.
---

# PaperSpine Orchestrator

Use this skill as the suite entrypoint. PaperSpine exposes one main skill:
`paper-spine`. Each stage is executed by reading the corresponding playbook
under `references/`.

**Update detection**: If the user asks to update, upgrade, or check for updates,
read `references/update.md` and execute without starting the full writing
workflow.

## Command Routing

| Trigger | Read |
|---|---|
| Default / full workflow | This file (Non-Negotiable Route below) |
| `resume` / `continue` / "continue from" | `references/resume.md` |
| `update` / "check for updates" | `references/update.md` |
| `submission` / "submission materials" | `references/submission.md` |
| `audit` | `references/audit.md` |
| `translate` | `references/translate.md` |
| `humanize` | `references/humanize.md` |
| `respond` / `response letter` / `reviewer comments` | `references/respond.md` |

For fine-grained stage execution, the orchestrator reads the playbook for each
stage from `references/` rather than requiring a separate skill invocation:

| Stage | Playbook |
|---|---|
| Intake / config | `references/intake.md` |
| Resume / checkpoint | `references/resume.md` |
| Research | `references/research.md` |
| Citation | `references/citation.md` |
| Rewrite | `references/rewrite.md` |
| Build | `references/build.md` |
| Humanize | `references/humanize.md` |
| LaTeX | `references/latex.md` |
| Translate | `references/translate.md` |
| Respond | `references/respond.md` |
| Audit | `references/audit.md` |

Historical worker skill names (`paper-spine-research`, etc.) are legacy only
and are not user entry points.

## Operating Principle

PaperSpine is a research-writing workflow, not a prose patcher. Its job is to
learn the target scene and strong examples first, force a user-confirmed
motivation, design the paper row by row, and only then write or rebuild the
manuscript.

Never fabricate data, metrics, p-values, datasets, citations, figures, or
experimental claims. User materials are authoritative for this paper's results.
External examples teach structure and rhetoric only.

## Contribution-First, Reviewer-Aware Rules (V4)

These three rules sit above the motivation thread. Motivation remains required,
but it supports the contribution rather than replacing it.

1. **Contribution-First.** The manuscript's highest-priority organizing unit is
   the confirmed contribution. Do not begin substantive writing until
   `confirmed_contribution.md` exists (what the paper adds, what problem/gap/
   challenge makes it necessary, what evidence validates it, what claim boundary
   to respect, why a reviewer should find it publishable). Template + per-section
   checklists: `references/contribution.md`. Gate: `contribution_check.py`.
2. **Results-as-Validation.** Each major Results subsection must validate at least
   one contribution promise; metric-only units with no contribution mapping are a
   failure. Record this in `results_validation.md`. Template:
   `references/results-validation.md`. Gate: `results_validation_check.py`
   (journal / conference / competition scenes).
3. **Reviewer-Aware.** Before claiming submission-ready, create `reviewer_audit.md`
   (reviewer value map + objection register + editorial fit), populating the
   objection register from the three `structured_review` reviewer agents. Template:
   `references/reviewer-audit.md`. Gate: `reviewer_audit_check.py`.

The Stage 12 Final Audit hard gate runs all three checks; do not declare the work
complete while any of them fails.

## User-Facing Language

When the user writes in Chinese, `ui_language=zh`, `output_language=zh`, or
`translation_package=zh`, all user-facing communication must be in Chinese
throughout the whole run, not only in the final completion report. This includes
intermediate progress updates, status bullets, tool-result summaries, blocked
messages, gate re-run notes, final delivery tables, and error explanations.

Do not write English progress sentences such as "Chinese .docx generated",
"Now writing the word report", "All stages passed", "Deliverables", or
"PaperSpine Workflow Complete" in those Chinese-facing runs. Use Chinese status
phrases instead, for example:

- `中文 Word 文档已生成：final_paper/paper.zh.docx。正在写入 Word 检查报告并重新运行关卡检查。`
- `PaperSpine 工作流已完成`
- `全部阶段已通过`
- `交付文件清单`

Tool names, file paths, command names, and required English manuscript text may
remain literal, but explanatory prose around them must be Chinese.

## Required Configuration

Prefer reading `paper_rewriting_output/paper_spine_config.json`. If it is
missing, read `references/intake.md` and collect configuration.

Required fields:

| Field | Allowed Values |
|---|---|
| `workflow` | `rewrite_existing`, `build_from_materials` |
| `scene` | `journal`, `conference`, `report_review`, `competition` |
| `tier` | `flash`, `pro` |
| `output_language` | `en`, `zh` |
| `target_name` | free text |
| `materials_dir` | path or empty |
| `draft_path` | path or empty |
| `user_motivation` | free text or empty |
| `official_urls` | list |
| `special_requirements` | list |
| `word_output` | `none`, `docx` |
| `translation_package` | `none`, `zh` |
| `reference_mode` | `local_first`, `specified_paths`, `web` |
| `reference_paths` | list of local reference folders/files; default `["."]` |
| `citation_target_count` | integer; default `20` |
| `humanize_tier` | `none`, `light`, `medium`, `heavy` |

## Non-Negotiable Route

**Resume-first rule:** Before starting any workflow, read
`references/resume.md` and run `progress_check.py` against
`paper_rewriting_output/`.  If earlier stages have produced valid artifacts,
start from the first incomplete stage. After executing that stage, run its gate,
run the full progress check again, and continue until final audit is complete.
Do **not** restart from intake unless the user explicitly requests a clean run
or the output directory is empty.

**Anti-skip rule:** Each stage is a gate. After completing a stage, run its
gate check before moving to the next. If the gate fails, route back to that
stage — do not skip, do not hand-write the missing artifact, do not patch
downstream. The gate script is `progress_check.py --gate <stage_name>`.
Never use bulk placeholder generators such as `generate_artifacts.py`,
`quick_generate.py`, or `mock_artifacts.py` to replace real stage work.

**Default Word output:** Word (.docx) is a standard required artifact. Produce
it in the LaTeX stage unless `word_output` is explicitly set to `none` in config.
If pandoc is unavailable, write a BLOCKED/FAIL note in `latex_report.md` and do
not declare completion.

---

### Stage 1 — Intake / Configuration

If configuration is missing or incomplete, run the terminal wizard from
the intake UI via the absolute installed launcher
`$env:USERPROFILE\.claude\skills\paper-spine\scripts\launch_paperspine_ui.ps1`
(or the `.codex` equivalent, or
`$HOME/.codex/skills/paper-spine/scripts/launch_paperspine_ui.sh` on bash); do
not ask the user to hand-write JSON or answer a long plain chat checklist when a
terminal is available. In Claude Code, `/paperspine` is the preferred entry: it launches
the external intake window automatically when configuration is missing.

**Codex hard constraint (do not skip):** when
`paper_rewriting_output/paper_spine_config.json` is missing, the FIRST tool
action after reading this skill MUST be to run the absolute
`launch_paperspine_ui.ps1` (resolve under `~/.codex/skills/...` or
`~/.claude/skills/...`) with `sandbox_permissions: require_escalated` so the
window can open.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate intake
```
If FAILED: return to intake. Config must exist and be valid before any research.

### Stage 2 — Research

Read `references/research.md` and execute the research stage. Research must
index local references per `reference_mode` and `reference_paths` before
any web collection.

Required outputs: `reference_materials/source_index.md`, `research_dossier.md`,
`exemplar_learning_dossier.md`, `style_profile.md`, `sota_gap_map.md`,
`motivation_options_after_research.md`.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate research
```
If FAILED: return to research. All six artifacts must exist before citation work begins.

### Stage 3 — Citation Support Bank

Read `references/citation.md` and build `citation_support_bank.md`. Generate
at least `citation_target_count * 3` candidates (default: 60). ~80% recent.
Include Source Channel for every row.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate citation
```
If FAILED: return to citation. The bank must exist with sufficient candidates.

### Stage 4 — Motivation Confirmation

Stop for user confirmation of the controlling motivation. Write
`confirmed_motivation.md` only after the user chooses.

This stage is BLOCKED (not just pending) until the user confirms. Present
`motivation_options_after_research.md` and wait. Do not auto-select.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate motivation_confirmation
```
If FAILED/BLOCKED: stop and wait for user. Do not proceed with an unconfirmed motivation.

### Stage 5 — Humanize (if applicable)

If `humanize_tier` is `light`, `medium`, or `heavy`, read
`references/humanize.md` and apply tier-specific constraints.

### Stage 6 — Writing / Drafting

If `workflow` is `rewrite_existing`, read `references/rewrite.md`.
If `workflow` is `build_from_materials`, read `references/build.md`.

Both workflows must create `section_blueprints.md` and
`writing_rationale_matrix.md` before drafting.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate planning
```
If FAILED: return to the writing stage. Blueprints and rationale matrix are
mandatory — a paper without a documented design is not a PaperSpine paper.

### Stage 7 — Integrity Audit

Run integrity audit before LaTeX assembly:
```bash
python scripts/integrity_audit.py paper_rewriting_output --markdown --write
```
Review BLOCKER findings. Return to the relevant stage for any BLOCKED dimension.
Do not proceed to LaTeX with unresolved BLOCKERs.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate integrity_audit
```
If FAILED: run the audit, fix BLOCKERs, re-run until gate passes.

### Stage 8 — LaTeX / PDF / Word

Read `references/latex.md` for LaTeX assembly, PDF compilation, and Word output.
Word (.docx) is a standard required artifact. Produce and check it unless
`word_output` is explicitly `none`.

**Citation mechanism (hard rule):** Every in-text citation must be a real
`\cite{key}` linked to a bibliography entry — either `\bibliographystyle{unsrt}`
(or `plain`/`ieeetr`) + `\bibliography{references.bib}`, or a `thebibliography`
block whose `\bibitem{key}` entries are reached by `\cite{key}`. Never type the
bracket number as literal text: a hand-typed `[1]` is inert and does not link to
the reference list (in the PDF or the .docx). A numeric `bibliographystyle`/CSL
still renders as `[1]` or `[3,12,13]`, so the visible plain-numeric style is
preserved. Do not use author-year citations and do not wrap numeric citations in
extra parentheses such as `([15])`. `latex_guard.py` fails literal-bracket
citations with no `\cite` and out-of-sync numbering; it also checks the format.

**Title (hard rule):** `main.tex` must contain `\title{...}` and `\maketitle`.
Word output must begin with the paper title — not Abstract, Keywords, or body
text. `latex_guard.py` checks the TeX source; `word_guard.py` checks the .docx.

When `output_language` is `zh`, the paper is Chinese. Produce
`final_paper/paper.zh.docx` as the primary Word output instead of
`paper.docx` — the `.zh.docx` suffix marks the language, not a translation:

```bash
pandoc paper_rewriting_output/final_paper/main.tex -o paper_rewriting_output/final_paper/paper.zh.docx --from latex --to docx --resource-path=paper_rewriting_output/final_paper --number-sections --citeproc --bibliography=paper_rewriting_output/final_paper/references.bib
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx --language zh --fix-fonts
```

`--citeproc --bibliography=...` resolves `\cite` to linked `[1]` numbers in the
.docx (matching the English command). Use it when citations come from a
`references.bib`. If the paper instead carries a `thebibliography` block with
`\bibitem`, drop `--citeproc --bibliography=...` — pandoc resolves `\cite`
against `\bibitem` natively; either way the source must use `\cite`, never
literal bracket text.

```bash
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx --language zh --markdown --output paper_rewriting_output/word_report.zh.md
```

If `output_language` is `en`, produce `final_paper/paper.docx` as the primary
Word output. Do not produce or require `final_paper/paper.zh.docx` unless
`translation_package=zh` is explicitly requested.

**Gate (LaTeX):**
```bash
python scripts/progress_check.py paper_rewriting_output --gate latex
```

**Word guard (run only for the Word files requested by the config):**
```bash
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx --language en --fix-fonts
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx --language en --markdown --output paper_rewriting_output/word_report.md
```

When `output_language=zh`, run:

```bash
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx --language zh --fix-fonts
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx --language zh --markdown --output paper_rewriting_output/word_report.zh.md
```

**Gate (Word):**
```bash
python scripts/progress_check.py paper_rewriting_output --gate word --require
```
Use `--require` so the gate checks Word even when config says `none` — the file
should exist and be valid. If `word_output` is explicitly `none`, skip this gate.

### Stage 9 — Submission Package (if requested)

If submission materials are requested, read `references/submission.md`,
create `submission_package/`, and run:
```bash
python scripts/submission_check.py paper_rewriting_output/submission_package --fix-fonts --markdown --write
```

### Stage 10 — Translation Package (if applicable)

If `output_language` is `en` and `translation_package` is `zh`, read
`references/translate.md` and produce the complete `translation_zh/` package.

`translation_zh/` is the **translation audit/intermediate package**, NOT the final
user-facing Chinese document. The final Chinese deliverable is a single Word file
under `final_paper/`. After `translation_zh/full_paper_translation.zh.md` is
complete, generate the final Chinese Word document:

```bash
pandoc paper_rewriting_output/translation_zh/full_paper_translation.zh.md -o paper_rewriting_output/final_paper/paper.zh.docx
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx --language zh --fix-fonts
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx --language zh --markdown --output paper_rewriting_output/word_report.zh.md
```

Run `python scripts/translate_guard.py paper_rewriting_output --markdown --write`
and require PASS. If pandoc is unavailable, write BLOCKED/FAIL in the
translation report — do not silently skip the final Chinese Word document.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate translation --require
```

### Stage 11 — Review Response (if requested)

If the user requests review response / revision response, read
`references/respond.md`, create `review_response/`, and run
`python scripts/respond_check.py paper_rewriting_output/review_response --markdown --write`.

### Stage 12 — Final Audit & Completion Hard Gate

Read `references/audit.md`. Before declaring the workflow complete, all checks
below must pass. If any command fails or reports missing/content issues, the
workflow is not complete; return to the failing upstream stage.

```bash
python scripts/artifact_check.py paper_rewriting_output --markdown --write
python scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --markdown --write
python scripts/progress_check.py paper_rewriting_output --gate final_audit
python scripts/integrity_audit.py paper_rewriting_output --markdown --write
python scripts/progress_check.py paper_rewriting_output --markdown --write
```

When `word_output` is not explicitly `none`, also run:

```bash
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx --language en --fix-fonts
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx --language en --markdown --output paper_rewriting_output/word_report.md
```

When `translation_package` is `zh` or `output_language` is `zh`, also run:

```bash
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx --language zh --fix-fonts
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx --language zh --markdown --output paper_rewriting_output/word_report.zh.md
```

Completion may be declared only when `artifact_check.py` exits 0, final progress
reports `is_complete=true`, no `misplaced_artifacts` are reported, integrity
audit has no unresolved BLOCKER, and Word output is present and valid unless the
user explicitly opted out with `word_output=none`. If pandoc is unavailable,
write BLOCKED/FAIL in `latex_report.md`; never silently skip Word.

**Hard gate rules:**
- `artifact_check.md` Status: FAIL or BLOCKED → workflow NOT complete; return to upstream stage.
- `citation_bank_check.md` Status: FAIL → citation bank unqualified; return to citation stage.
- Nested `paper_rewriting_output/` inside `paper_rewriting_output/` → misplaced; move contents up.
- Sibling `final_paper/` outside `paper_rewriting_output/` → misplaced; remove sibling copy.
- `writing_rationale_matrix.md` too thin (<8 rows, generic cells) → artifact_check FAIL → NOT complete.

**Chinese completion report rule:** When the output language is Chinese
(`output_language=zh`) or a Chinese translation package is requested
(`translation_package=zh`), the final user-visible completion report must be
written in Chinese. Use Chinese section titles and status labels. Prohibited:
"PaperSpine Workflow Complete", "All stages passed", "Deliverables". Required
minimum content: 工作流已完成、全部阶段已通过、交付文件清单. The final Chinese
Word document is `final_paper/paper.zh.docx`; the `translation_zh/` folder is
an audit/intermediate package, not the final deliverable.

---

**Loop Rule:** If a gate fails, route back to that stage. Do not patch the
final paper directly when the missing artifact should have been created earlier.

If a worker skill is unavailable, follow the reference playbook locally and
produce the same artifacts.

## Migration Note

See `references/orchestrator-branch-map.md` for stage ownership details.

## Standard Artifacts

Write workflow artifacts under `paper_rewriting_output/`.

`final_artifact_manifest.md` must label each artifact with its source category:
- `required` — always produced
- `pro-extra` — produced only in `pro` tier (additional analysis depth)
- `optional-translation` — produced when translation package is requested
- `optional-submission` — produced when submission materials are requested
- `optional-review-response` — produced when review response workflow runs

**Common required artifacts:**
`paper_spine_config.json`, `paper_spine_config.md`, `source_map.md`,
`reference_materials/source_index.md`, `research_dossier.md`,
`exemplar_learning_dossier.md`, `style_profile.md`, `sota_gap_map.md`,
`motivation_options_after_research.md`, `citation_support_bank.md`,
`confirmed_motivation.md`, `section_blueprints.md`,
`writing_rationale_matrix.md`

**Rewrite existing:** `original_logic_map.md`, `evidence_bank.md`,
`rewrite_matrix.md`, `logic_transfer_audit.md`, revised manuscript.

**Build from materials:** `source_inventory.md`, `evidence_bank.md`,
`figure_asset_map.md`, `claim_register.md`, manuscript draft.

**Final artifacts:** `latex_report.md`, `final_artifact_manifest.md`,
`final_paper/main.tex`, `final_paper/paper.pdf` (when TeX available),
`final_paper/paper.docx` + `word_report.md` (standard; skip only if
`word_output` is explicitly `none`),
`final_paper/paper.zh.docx` + `word_report.zh.md` (when `output_language=zh`
or `translation_package=zh`; `translation_zh/` is the audit/intermediate
package, NOT the final Chinese deliverable),
`submission_package/` (when requested).

## Writing Rationale Matrix

`writing_rationale_matrix.md` must be created before final writing in both
workflows. It is the execution plan, not a post-hoc summary:

| Row ID | Manuscript Unit | Current/Planned Function | Motivation Link | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Change | Final Text Check |
|---|---|---|---|---|---|---|---|---|

The first data row must justify the whole-work framework in depth. Subsequent
rows split the document into the smallest useful writing units. Each row must
explain concrete anchors across multiple dimensions. A shallow matrix is a
failure.

## Command-Line UI

Claude Code and Codex do not guarantee a native graphical picker for skills.
The supported UI is the bundled terminal wizard. When configuration is missing,
read `references/intake.md` to launch the intake UI. In Claude Code,
`/paperspine` must launch the intake UI automatically.
