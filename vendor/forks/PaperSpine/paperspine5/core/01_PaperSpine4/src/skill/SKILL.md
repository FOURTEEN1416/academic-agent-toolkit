---
name: paper-spine
description: Build, rewrite, audit, submit, revise, or transfer scholarly papers end to end, producing verified LaTeX/PDF/Word and target-specific publication packages.
---

# PaperSpine Orchestrator

Use this skill as the suite entrypoint. PaperSpine exposes one main skill:
`paper-spine`. Each stage is executed by reading the corresponding playbook
under `references/`.

**Update detection**: If the user asks to update, upgrade, check for updates,
or configure automatic updates, read `references/update.md` and execute without
starting intake or the writing workflow. Automatic updates are opt-in only.

## Command Routing

| Trigger | Read |
|---|---|
| Default / full workflow | This file (Non-Negotiable Route below) |
| `resume` / `continue` / "continue from" | `references/resume.md` |
| `update` / "check for updates" / 手动更新 | `references/update.md` |
| `auto-update on|off|status` / 自动更新 | `references/update.md` |
| `submission` / "submission materials" / delivery package | `references/publication-cycle.md`, then `references/submission.md` |
| `audit` | `references/audit.md` |
| `translate` | `references/translate.md` |
| `humanize` | `references/humanize.md` |
| `respond` / `rebuttal` / minor or major revision | `references/publication-cycle.md`, then `references/respond.md` |
| rejection / resubmit / journal transfer / 转投 | `references/publication-cycle.md`, then `references/journal-transfer.md` |

## Automatic Update Preflight

Before every normal workflow launch or resume, follow `references/update.md`
and run the installed updater with `--auto`. The preflight is a local no-op
unless the user has explicitly enabled automatic updates and the configured
interval is due. Never enable it on the user's behalf.

If the preflight installs a new version, stop before intake/research/writing and
ask the user to reload or restart the host, then invoke PaperSpine again. If the
preflight fails, warn once and continue with the current installation; do not
turn an update-network failure into a paper-workflow blocker.

For fine-grained stage execution, the orchestrator reads the playbook for each
stage from `references/` rather than requiring a separate skill invocation:

| Stage | Playbook |
|---|---|
| Intake / config | `references/intake.md` |
| Resume / checkpoint | `references/resume.md` |
| Research | `references/research.md` |
| Citation | `references/citation.md` |
| Review policy / autonomy | `references/review-policy.md` |
| Editorial completeness / manuscript scale | `references/editorial-completeness.md` |
| Semantic confirmation | `references/semantic-confirmation.md` |
| Contribution contract | `references/contribution.md` |
| Rewrite | `references/rewrite.md` |
| Build | `references/build.md` |
| Results validation | `references/results-validation.md` |
| Scientific evidence ledger | `references/scientific-evidence-ledger.md` |
| Reviewer audit | `references/reviewer-audit.md` |
| Humanize | `references/humanize.md` |
| Reader-facing claim voice | `references/assertive-scientific-writing.md` |
| LaTeX | `references/latex.md` |
| Visual readiness | `references/visual-readiness-gate.md` |
| Submission metadata | `references/submission-metadata.md` |
| Publication surface | `references/publication-surface.md` |
| Publication target profile | `references/publication-target-profile.md` |
| Submission / revision / transfer cycle | `references/publication-cycle.md` |
| Publication-cycle main-flow interface | `references/publication-cycle-interface.md` |
| Journal transfer | `references/journal-transfer.md` |
| Usage telemetry / phase receipts | `references/usage-telemetry.md`, `references/phase-contracts.md` |
| Translate | `references/translate.md` |
| Respond | `references/respond.md` |
| Audit | `references/audit.md` |

Historical worker skill names (`paper-spine-research`, etc.) are legacy only
and are not user entry points.

## Operating Principle

PaperSpine is a research-writing workflow, not a prose patcher. Its job is to
learn the target scene and available evidence, confirm the controlling
contribution and motivation, then give the writing Agent room to design the
strongest argument and manuscript structure for the actual material.

Never fabricate data, metrics, p-values, datasets, citations, figures, or
experimental claims. User materials are authoritative for this paper's results.
External examples teach structure and rhetoric only.

Keep scientific boundaries explicit without repeating the full provenance
disclaimer in every paragraph. Define stable evidence scope at the paper or
section boundary, inherit it until the evidence changes, and restate only the
exception. This preserves caution without defensive repetition.

Default to `review_policy=balanced`. Gates are decision aids, not a substitute
for writing judgment. Hard-block fabricated facts/citations, unsupported primary
claims, unresolved figure/text conflicts, broken citations, missing required
metadata, and unusable deliverables. Treat stylistic preferences, literature
breadth inside a declared closed corpus, optional planning forms, and minor
review suggestions as advisory. Use `strict` only when the user requests it or
the task is explicitly a submission/final-compliance audit. Read
`references/review-policy.md` when selecting or changing this policy.

The internal evidence model may be precise; the manuscript should still sound
like a confident scholarly article. Read
`references/assertive-scientific-writing.md`: state supported results directly,
reserve hedging for genuine uncertainty or causal/generalization boundaries,
and do not repeat audit language in reader-facing prose.

## Editorial North Star

The manuscript is the product; plans, ledgers, reviews, and receipts exist only
to help the Agent write it. A workflow is not complete merely because its
internal artifacts pass. The final paper must let its intended reader follow one
visible arc: why the work was needed, what was done, what the evidence shows,
what those findings mean, and what conclusion the evidence earns.

Give the writing Agent freedom to choose section architecture, paragraph moves,
emphasis, and revision order from the confirmed contribution, target venue, and
available evidence. Guide with reader questions and editorial judgment rather
than paragraph quotas or extra forms. Hard stops are reserved for truth,
authorization, unresolved evidence/figure identity conflicts, and unusable
deliverables.

`tier` changes research and process depth, never the promised manuscript scale.
A `flash` journal paper is still a complete journal paper; it is not permission
to omit the ending, compress Results into captions, or replace Discussion with
an audit summary. Read `references/editorial-completeness.md` before drafting
and again for the integrated editorial pass.

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

The contribution check runs at semantic confirmation and again at planning;
Results validation runs at planning before prose; reviewer audit runs before
LaTeX assembly. Stage 12 re-runs all three as defense in depth. Final audit must
never be the first place one of these failures is discovered.

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
| `tier` | `flash`, `pro` (research/process depth only; never manuscript completeness) |
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

Optional policy fields (default without adding intake questions):

| Field | Allowed Values |
|---|---|
| `review_policy` | `balanced` (default), `strict` |
| `literature_scope` | `auto` (default), `closed_corpus`, `open_literature` |

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
`contribution_options_after_research.md`, `motivation_options_after_research.md`.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate research
```
If FAILED: return to research. All six artifacts must exist before citation work begins.

### Stage 3 — Citation Support Bank

Read `references/citation.md` and build `citation_support_bank.md`. Resolve the
literature contract first. `open_literature` builds a broad candidate pool
(normally `citation_target_count * 3` unique sources, with recency as a coverage
goal). `closed_corpus` exhausts and deduplicates the supplied bibliography,
requires enough real sources for the planned final citations, and treats
recency/breadth as disclosed limitations rather than reasons to stop writing.
Repeating one paper never increases source coverage in either mode.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate citation
```
If FAILED: return to citation. The bank must exist with sufficient candidates.

### Stage 4 — Semantic Confirmation

Read `references/semantic-confirmation.md`. Stop for user confirmation of the
contribution contract first and its supporting motivation second. Write
`confirmed_contribution.md` and `confirmed_motivation.md` only after the user
chooses, revises, combines, or replaces the research-generated options.

This stage is BLOCKED (not just pending) until the user confirms both artifacts.
Present `contribution_options_after_research.md` and
`motivation_options_after_research.md`; do not auto-select either one.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate semantic_confirmation
```
If FAILED/BLOCKED: stop and wait for user. Do not proceed with an unconfirmed
or invalid contribution contract, even when motivation is already confirmed.

### Stage 5 — Humanize (if applicable)

If `humanize_tier` is `light`, `medium`, or `heavy`, read
`references/humanize.md` and apply tier-specific constraints.

### Stage 6 — Writing / Drafting

If `workflow` is `rewrite_existing`, read `references/rewrite.md`.
If `workflow` is `build_from_materials`, read `references/build.md`.

Both workflows create `section_blueprints.md` before drafting. In balanced mode,
the blueprint plus evidence ledger/results map are enough: the Agent may plan in
the format that best supports the paper and should not expand a table merely to
satisfy a row quota. `writing_rationale_matrix.md` is required only in strict
mode or when the user explicitly asks for a paragraph-level rationale trace.

For evidence-bearing scenes, read `references/scientific-evidence-ledger.md`
and create `scientific_evidence_ledger.json` during planning. Separate and link
sources, claims, numeric facts, methods, outcomes, and results; preserve
verification state rather than collapsing all evidence into one prose bank.

For `journal`, `conference`, and `competition`, read
`references/results-validation.md` and create `results_validation.md` during
planning, before Results prose. Every planned major Results unit must test at
least one contribution promise.

When existing scientific figures are present or new/redesigned figures are
needed, set `figure_policy` to `existing_only` or `generate_or_redesign`, read
`references/figure-story.md`, and inspect every existing image and panel with a
multimodal tool before drafting. Create one `figure_requests.json` contract that
records each figure's question, dominant claim, intended conclusion, claim
boundary, hero panel, panel jobs/evidence anchors, Results units, caption, and
`keep`/`redesign`/`create` decision. This is both the manuscript storyboard and
the PaperFigure/FigMirror handoff; do not add a second figure-planning form.

Read `references/editorial-completeness.md`. Use the blueprint and figure story
as private scaffolding, then expand them into full reader-facing argument. The
Agent may merge, split, or rename sections to fit the venue; every full-paper
scene must nevertheless complete the research arc and give Results and
Discussion enough space to do their distinct intellectual jobs.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate planning
```
If FAILED: return to the writing stage. Blueprints and, for evidence-bearing
scenes, the Results validation/evidence map remain mandatory. Strict mode also
requires the rationale matrix. Planning artifacts should capture real decisions,
not restate the same justification in many cells.

Write Results by figure question and claim: visible evidence first, then the
bounded answer. Do not reduce Results to chronological panel narration. For
`redesign`/`create`, use the existing PaperFigure integration; its candidates
must preserve the same scientific-story contract while exploring visual form.

After drafting, run:

```bash
python scripts/progress_check.py paper_rewriting_output --gate drafting
```

### Stage 7 — Integrity Audit

Run `structured_review.py`. In balanced mode it prepares a compact editorial
brief, then one capable Agent reads the actual manuscript and writes a free-form
editor synthesis. Judge the paper as a reader: complete argument, Results depth,
Discussion synthesis, figure/text reading order, and an earned ending. Do not
manufacture reviewer personas, scores, rationale rows, or extra forms. Revise
the manuscript, then mark the integrated review `PASS` only when the editor
synthesis genuinely supports that judgment. Strict mode keeps three independent
reviewer passes, phase receipts, `reviewer_audit.md`, and
`reviewer_audit_check.py`.

Run before LaTeX assembly:
```bash
python scripts/structured_review.py paper_rewriting_output --markdown --write
python scripts/integrity_audit.py paper_rewriting_output --markdown --write
```
For strict mode, add `structured_review.py --dispatch` and
`reviewer_audit_check.py` per `references/review-policy.md`.
Review BLOCKER findings. Return to the relevant stage for any BLOCKED dimension.
Do not proceed to LaTeX with unresolved BLOCKERs.

**Gate:**
```bash
python scripts/progress_check.py paper_rewriting_output --gate integrity_audit
```
If FAILED: return to drafting or the owning upstream stage, fix BLOCKERs, and
re-run structured review, reviewer audit, and integrity audit until the gate
passes.

### Stage 8 — LaTeX / PDF / Word

Read `references/latex.md` for LaTeX assembly, PDF compilation, and Word output.
Word (.docx) is a standard required artifact. Produce and check it unless
`word_output` is explicitly `none`.

After the current PDF and figure assets are final, read
`references/publication-surface.md` and `references/visual-readiness-gate.md`.
Scrub internal audit scaffolding, render every PDF page and figure, inspect the
actual renders with a multimodal tool, complete `visual_audit_manifest.json`,
and require `visual_readiness_check.py` PASS. TeX-source PASS does not imply
`visual_ready`. For every scientific figure, compare the actual pixels against
its story contract and record claim alignment, panel-role alignment, claim
boundary, and panel-level receipts. If the final image disagrees with the
planned story, revise the image or prose and invalidate the old receipt.
Also inspect the paper in reading order. Figures should appear close enough to
the Results units that interpret them for a reader to follow the argument; a
hash-valid figure floated beyond its discussion is visually valid but
editorially unresolved.

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

If submission materials are requested, read `references/publication-cycle.md`,
`references/publication-target-profile.md`, and `references/submission.md`.
Research the current official author guide, create
`publication_target_profile.json`, and verify it before producing files:

```bash
python scripts/publication_cycle.py profile-check \
  paper_rewriting_output/publication_cycle/targets/<target>/publication_target_profile.json \
  --markdown --write
```

Create `submission_package_plan.json`, transform and validate every required or
applicable conditional item, obtain author-only confirmations, then assemble a
new immutable bundle directory:

```bash
python scripts/publication_cycle.py assemble \
  paper_rewriting_output/publication_cycle/targets/<target>/publication_target_profile.json \
  paper_rewriting_output/publication_cycle/targets/<target>/submission_package_plan.json \
  paper_rewriting_output/publication_cycle/targets/<target>/bundles/<bundle-id> \
  --markdown
```

The package is upload-ready only when `bundle_manifest.json status=READY`, the
ZIP exists, and its SHA-256 receipt matches. `submission_check.py` is a
compatibility validator for legacy cover-letter/highlights packages, not the
completeness authority for a real target.

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
`references/publication-cycle.md` and `references/respond.md`. Preserve and
hash the decision sources, create an atomic `review_round.json`, confirm the
author's position for each issue, and run:

```bash
python scripts/publication_cycle.py rebuttal-check \
  paper_rewriting_output/publication_cycle/revisions/<round-id>/review_round.json \
  --markdown --write
python scripts/publication_cycle.py rebuttal-render \
  paper_rewriting_output/publication_cycle/revisions/<round-id>/review_round.json \
  paper_rewriting_output/publication_cycle/revisions/<round-id>/rendered \
  --markdown
```

Minor revisions revalidate every readiness dimension and may mark a genuinely
unaffected dimension `not_affected`. Major revisions and reject-and-resubmit
rounds require all five dimensions to be re-run and passed. Package the revised
manuscript, response letter, and target-required marked files through a new
READY bundle. `respond_check.py` remains a legacy Markdown compatibility check.

**Post-decision transfer branch:** After rejection or when the user asks to
change venue, read `references/journal-transfer.md`. Compare destinations
against the user's must-haves and deal-breakers, obtain destination
confirmation, create fresh origin/destination profiles and
`transfer_request.json`, then run `publication_cycle.py transfer-plan`. Rebuild
the destination format, all five narrative parts, and the entire delivery
package from the canonical paper; never patch the old upload copy or silently
accept a publisher transfer.

### Stage 12 — Final Audit & Completion Hard Gate

Read `references/audit.md`. Before declaring the workflow complete, all checks
below must pass. If any command fails or reports missing/content issues, the
workflow is not complete; return to the failing upstream stage.

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

Before these commands, create `submission_metadata.json` per
`references/submission-metadata.md` and maintain `usage_ledger.jsonl` per
`references/usage-telemetry.md`. Completion may be declared only when
`artifact_check.py` exits 0, final progress reports `is_complete=true`, no
`misplaced_artifacts` are reported, integrity audit has no unresolved BLOCKER,
and all five readiness dimensions are true: `scientific_content_ready`,
`visual_ready`, `citation_verified`, `metadata_ready`, and
`artifact_portable`. No green dimension offsets a red one. Word output remains
required unless explicitly disabled. If pandoc is unavailable, write
BLOCKED/FAIL in `latex_report.md`; never silently skip Word.

If a publication-cycle mode ran, its current authority must also be green:
submission requires a READY bundle manifest and matching archive checksum;
revision requires a PASS rebuttal check plus a new READY target bundle; transfer
requires `transfer_delta.json status=READY_TO_REBUILD`, a completed destination
rebuild, and a new READY destination bundle. Preparing local files never grants
authority to press an external submit/transfer button.

**Hard gate rules:**
- `artifact_check.md` Status: FAIL or BLOCKED → workflow NOT complete; return to upstream stage.
- `citation_bank_check.md` Status: FAIL → citation bank unqualified; return to citation stage.
- Nested `paper_rewriting_output/` inside `paper_rewriting_output/` → misplaced; move contents up.
- Sibling `final_paper/` outside `paper_rewriting_output/` → misplaced; remove sibling copy.
- In strict mode, a generic or shallow `writing_rationale_matrix.md` remains a
  failure. Balanced mode does not require this matrix.

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
- `optional-transfer` — produced when a rejected or redirected paper is rebuilt for another target

**Common required artifacts:**
`paper_spine_config.json`, `paper_spine_config.md`, `source_map.md`,
`reference_materials/source_index.md`, `research_dossier.md`,
`exemplar_learning_dossier.md`, `style_profile.md`, `sota_gap_map.md`,
`contribution_options_after_research.md`, `motivation_options_after_research.md`,
`citation_support_bank.md`, `confirmed_contribution.md`,
`confirmed_motivation.md`, `section_blueprints.md`,
`structured_review.md`; strict mode also requires
`writing_rationale_matrix.md` and `reviewer_audit.md`;
plus `results_validation.md` and `scientific_evidence_ledger.json` for journal,
conference, and competition scenes; plus `submission_metadata.json`,
`usage_ledger.jsonl`, and the visual/publication-surface audit receipts before
final completion. Figure-active work also requires `figure_requests.json` and
`figure_story_check.md`.

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
`publication_cycle/targets/<target>/publication_target_profile.json`,
`submission_package_plan.json`, and an immutable `bundles/<bundle-id>/` with
`bundle_manifest.json`, `submission_bundle.zip`, and
`submission_bundle.sha256` (when submission materials are requested and READY).

**Review-cycle artifacts:** `publication_cycle/revisions/<round-id>/review_round.json`,
`rebuttal_check.md`, `response_matrix.md`, `response_letter.md`, and
`revision_change_log.md`; the revised files then enter a new target bundle.

**Transfer artifacts:** `publication_cycle/transfers/<id>/transfer_request.json`
and `transfer_delta.json`, followed by a newly rendered destination manuscript
and target-specific READY bundle.

## Writing Rationale Matrix (Strict / Optional Trace)

Use `writing_rationale_matrix.md` before final writing in strict mode or when
the user requests a paragraph-level rationale trace. It is not required by the
balanced default:

| Row ID | Manuscript Unit | Current/Planned Function | Contribution Promise / Claim ID | Motivation Alignment | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Change | Final Text Check |
|---|---|---|---|---|---|---|---|---|---|

When used, the first data row should justify the whole-work framework. Subsequent
rows split the document into the smallest useful writing units. Contribution is
the governing column; motivation explains significance but cannot substitute
for a claim ID or enlarge its boundary. Do not create rows that merely paraphrase
the template; prefer a shorter plan containing genuine decisions.

## Command-Line UI

Claude Code and Codex do not guarantee a native graphical picker for skills.
The supported UI is the bundled terminal wizard. When configuration is missing,
read `references/intake.md` to launch the intake UI. In Claude Code,
`/paperspine` must launch the intake UI automatically.
