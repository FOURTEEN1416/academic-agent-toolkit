---
name: spine
description: "Write, rewrite, or build a paper or report (journal, conference, report, review, competition) end to end. PaperSpine suite entrypoint routing to intake, research, rewrite, build, and audit branches."
---


<!--ACAT-ADAPTED: 资产回填自 WUBING2023/PaperSpine@1fe46f0e76aa（单技能拆分重组编排）。溯源见 references/UPSTREAM.md。2026-09-09 专项治理。-->
# PaperSpine Orchestrator

Use this skill as the suite entrypoint. It is the main orchestrator: it routes
the user to UI, intake, research, citation, rewrite, build, LaTeX,
translate, humanize, audit, and update branch skills.

**Update detection**: If the user asks to update, upgrade, check for updates,
or manage the PaperSpine installation, route immediately to
`spine-update` without starting the writing workflow.

## Operating Principle

PaperSpine is a research-writing workflow, not a prose patcher. Its job is to
learn the target scene and strong examples first, force a user-confirmed
motivation, design the paper row by row, and only then write or rebuild the
manuscript.

Never fabricate data, metrics, p-values, datasets, citations, figures, or
experimental claims. User materials are authoritative for this paper's results.
External examples teach structure and rhetoric only.

Tool success, hashes, and task status do not establish scientific, editorial,
visual, or submission readiness; assess the actual paper. Tool names, file
paths, and required manuscript text may stay literal, but progress and delivery
reports use the user's language.

## Required Configuration

Prefer reading `paper_rewriting_output/paper_spine_config.json`. If it is
missing, route to `spine-intake` or ask the same fields directly.

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
| `humanize_tier` | `none`, `light`, `medium`, `heavy`; default `medium` |

## Non-Negotiable Route

1. If configuration is missing or incomplete, run the terminal wizard from
   `spine-config-ui`, then `spine-intake`; do not ask the user to hand-write
   JSON or answer a long plain chat checklist when a terminal is available.
   The wizard is the supported command-line UI.

   **Do not skip (hard constraint):** when
   `paper_rewriting_output/paper_spine_config.json` is missing, the FIRST tool
   action after reading this skill MUST be to run `launch_paperspine_ui.ps1`
   by its absolute path inside the repository checkout so the window can open.
   Do NOT inspect materials, infer defaults, create config files, or continue
   the workflow before the UI has launched or explicitly failed. Only fall back
   to numbered/chat intake if the launch returns an error.
2. Always create or verify `source_map.md`.
3. Always use `spine-research` before choosing the final motivation.
   Research must first index local/default references according to
   `reference_mode` and `reference_paths`; web collection supplements this
   index but does not replace it.
4. Research must create `reference_materials/`, `research_dossier.md`,
   `exemplar_learning_dossier.md`, `style_profile.md`, `sota_gap_map.md`, and
   `motivation_options_after_research.md`.
5. Use `spine-citation` to create `citation_support_bank.md`. This bank
   is separate from exemplar learning: it supports Introduction, Related Work,
   Discussion, background, limitation, and application claims. Generate at
   least `citation_target_count * 3` candidates; default target is 20, so the
   default candidate pool is 60. About 80% should be recent, using
   `current_year - 3` as the simple threshold.
6. Stop for user confirmation of the controlling motivation, together with the
   contribution promise it supports and the claim boundary it respects. Do not
   write or rewrite until `confirmed_motivation.md` records the user's chosen
   motivation. The final motivation should be concise and specific. Do not
   inflate one narrow contribution into a multi-claim motivation.
7. If `workflow` is `rewrite_existing`, use `spine-rewrite`.
8. If `workflow` is `build_from_materials`, use `spine-build`.
9. Before drafting, both workflows must create `section_blueprints.md` and
   `writing_rationale_matrix.md`. The matrix is the execution plan, not a
   post-hoc summary.
10. Run the integrity audit with the script resolved inside this repository
    checkout: set `REPO="$(git rev-parse --show-toplevel)"`, then run
    `python "$REPO/academic-toolkit/skills/spine/scripts/integrity_audit.py" paper_rewriting_output --markdown --write`.
    This produces `integrity_audit.md` — a teaching report where every finding
    includes root cause, fix action, downstream impact, and a teaching note.
    The report must show no BLOCKED findings before LaTeX compilation can proceed.
11. Use `spine-latex` for final LaTeX structure, figure placement,
   citation safety, and compile-oriented cleanup.
12. Always produce final LaTeX source. Compile PDF when a TeX engine is
    available. Markdown alone is not a final PaperSpine output.
13. If `word_output` is `docx`, produce and check a Word version.
14. If `output_language` is `en` and `translation_package` is `zh`, use
    `spine-translate-zh` to produce the complete `translation_zh/` package.
    Run `python "$REPO/academic-toolkit/skills/spine/scripts/translate_guard.py" paper_rewriting_output --markdown --write`
    (with `REPO="$(git rev-parse --show-toplevel)"` resolved first)
    and require PASS. The translation package must cover every required
    intermediate and final artifact with row-by-row translation of large
    tabular files. Summaries are not acceptable.
15. Use `spine-audit` before declaring the work complete.
   If the user requests a submission package, also produce
   `submission_package/` per `references/orchestrator-branch-map.md` stage 10
   (gate: `submission`) before the final audit.

If another skill is unavailable, follow the referenced workflow locally and
produce the same artifacts.

**Guard script paths:** run guard commands from the user's project directory
with the script resolved inside this repository checkout — never as a bare
`python scripts/...` relative path. Set `REPO="$(git rev-parse --show-toplevel)"`
first and prefix the script path with `$REPO/academic-toolkit/skills/...`.
Same-name script copies exist across several spine skill directories
(registered in `academic-toolkit/data/duplicate_assets_registry.json`); each
skill's commands use the copy in that same skill's own directory.

## Standard Artifacts

Write workflow artifacts under `paper_rewriting_output/` unless the user asks
otherwise.

Common required artifacts:

- `paper_spine_config.json`
- `paper_spine_config.md`
- `source_map.md`
- `reference_materials/source_index.md`
- `research_dossier.md`
- `exemplar_learning_dossier.md`
- `style_profile.md`
- `sota_gap_map.md`
- `motivation_options_after_research.md`
- `citation_support_bank.md`
- `confirmed_motivation.md`
- `section_blueprints.md`
- `writing_rationale_matrix.md`

Rewrite existing:

- `original_logic_map.md`
- `evidence_bank.md`
- `rewrite_matrix.md`
- `logic_transfer_audit.md`
- revised manuscript

Build from materials:

- `source_inventory.md`
- `evidence_bank.md`
- `figure_asset_map.md`
- `claim_register.md`
- manuscript draft as an intermediate artifact

Final artifacts:

- `latex_report.md`
- `final_artifact_manifest.md`
- `final_paper/main.tex`
- `final_paper/paper.pdf` when a TeX compiler is available
- `final_paper/paper.docx` and `word_report.md` when Word output is requested
- `translation_zh/` when English output requests a Chinese translation package

## Writing Rationale Matrix Requirement

`writing_rationale_matrix.md` must be created before final writing in both
`rewrite_existing` and `build_from_materials`. It must be a Markdown table used
as the execution plan. Column headers are owned by the single source of truth
`spine-rewrite/references/writing-rationale-matrix.md` (an identical copy lives
in `spine-build/references/`); the table below repeats them for convenience.

| Row ID | Manuscript Unit | Current Problem or Planned Function | Motivation Link | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Change/Text Move | Final Text Check |
|---|---|---|---|---|---|---|---|---|

The first data row must justify the whole-work framework, structure, or main
throughline in depth: why this controlling structure is chosen, how SOTA/target
examples informed it, how it follows the confirmed motivation, which user
evidence anchors it, and how the final manuscript will be checked against it.
Subsequent rows must follow the target document in order and split it into the
smallest useful writing units: paragraph-level moves, paragraph
groups, model steps, assumptions, result/claim units, review synthesis units,
competition solution blocks, headings, captions, and other argument-bearing
fragments.

This is flexible by scene. A journal paper may naturally use abstract,
introduction, methods, results, and discussion units. A competition paper may
use problem restatement, assumptions, model construction, solving process,
validation, sensitivity, strengths/weaknesses, and recommendations. A report or
review may use executive summary, background, taxonomy, comparison, synthesis,
and recommendation units. Do not force all tasks into a fixed IMRaD template.

Each row must explain concrete anchors across multiple dimensions: it advances
or narrows the confirmed motivation, transfers a structural pattern learned from
SOTA/example work, matches a target-scene norm, uses a user-provided evidence
item, creates a front/back echo, fixes an original logic failure, and/or
constrains a claim to available evidence. For important rows, write enough
reasoning that the user can learn why this writing move is better.

A shallow matrix is a failure. If most rows say only "improve clarity" or
"polish wording", stop and redo the research/blueprint stage.

## Figure And Evidence Discipline

Map actual results to the questions a reader will ask, and assign each useful
job — primary finding, comparison, uncertainty/validation, robustness or
subgroup, and mechanism explanation — to a figure, table, prose passage,
supplement, or a justified omission. There is no figure quota: merge duplicated
messages, but do not let a single omnibus plot define the story. If an
explanatory mechanism figure is central and sourced, make an explicit decision
to create one; a flowchart, ROC panel, or statistical summary is not a
mechanism figure.

Every substantive claim needs source or result support and a bounded
uncertainty. Citation identity and citation context are both checked; no
fabricated or inert references. Humanize and detector scores are diagnostics,
not paper-quality verdicts. Keep internal workflow chatter out of the paper,
but preserve real study methods, software/model names, citations, ethics
statements, and factual venue-required disclosures.

## Completion Contract

Deliver the requested scope, not a publication guarantee. A local draft
delivery is not submission readiness: report scientific limitations,
submission readiness, and required external authorizations separately, and
disclose missing author/ethics/venue facts instead of inventing them.
Arranging independent review stays part of the route; without it, deliver a
usable draft with review explicitly pending, not a reviewed final.

## Branch Map

Read `references/orchestrator-branch-map.md` when the workflow needs to be
debugged or when a branch output fails audit. The rule is simple: route back to
the branch that owns the weak artifact instead of patching the final paper
directly.

## Command-Line UI

The terminal wizard is the supported interactive interface. When configuration
is missing, run `spine-intake`. If the execution environment cannot expose an
interactive terminal, add `-InPlace`; if stdin is still unavailable, fall back
to numbered menus, then native structured questions, then chat as a last resort.

