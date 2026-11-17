---
name: spine-translate-zh
description: "Produces the complete translation_zh/ package with row-by-row translation of all required artifacts and full-paper consistency checks."
---


<!--ACAT-ADAPTED: 资产回填自 WUBING2023/PaperSpine@1fe46f0e76aa（单技能拆分重组编排）。溯源见 references/UPSTREAM.md。2026-09-09 专项治理。-->
# PaperSpine Translate

Use this branch when `output_language` is `en` and `translation_package` is
`zh`.  Its job is to produce every required Chinese translation file under
`paper_rewriting_output/translation_zh/` — not a summary, not a partial set.

## Operating Principle

A translation package that covers only a few files is a failed output.
The orchestrator requires a complete `translation_zh/` before declaring the
workflow complete.  This branch owns the translation responsibility end-to-end.

Translation scope is tiered:

- **Core (always required):** the final paper text
  (`full_paper_translation.zh.md`), `confirmed_motivation.zh.md`, and
  `writing_rationale_matrix.zh.md`. Missing or partial core files are always
  a failure.
- **Optional (internal process files):** research/learning/audit working
  documents. Translate them by default; skip them only when `tier` is `flash`
  or the user explicitly agrees, and record every skipped file as
  `optional-skipped` in `manifest.md`.

`scripts/translate_guard.py` currently checks the full artifact list. If
optional files were skipped with user consent, treat the guard's `missing`
findings for exactly those recorded files as confirmed-and-accepted and note
the decision — never silently claim PASS while core files are missing.

## Three-Phase Flow

### Phase 1 — Inventory

Read `paper_spine_config.json` to determine `workflow`.  List every file that
must be translated.  The tables below are the baseline guard set: if the run
produced additional stage artifacts, add them to the inventory and translate
them too.  Write the inventory to `translation_zh/manifest.md` with
status `pending` for each entry.

**Common files (both workflows):** (`core` = always required; `optional` =
internal process file, skippable only under the tiered scope above)

| English Source | Chinese Target | Tier |
|---|---|---|
| `paper_spine_config.json` | `paper_spine_config.zh.md` | optional |
| `source_map.md` | `source_map.zh.md` | optional |
| `reference_materials/source_index.md` | `reference_materials/source_index.zh.md` | optional |
| `research_dossier.md` | `research_dossier.zh.md` | optional |
| `exemplar_learning_dossier.md` | `exemplar_learning_dossier.zh.md` | optional |
| `style_profile.md` | `style_profile.zh.md` | optional |
| `sota_gap_map.md` | `sota_gap_map.zh.md` | optional |
| `motivation_options_after_research.md` | `motivation_options_after_research.zh.md` | optional |
| `confirmed_motivation.md` | `confirmed_motivation.zh.md` | core |
| `section_blueprints.md` | `section_blueprints.zh.md` | optional |
| `writing_rationale_matrix.md` | `writing_rationale_matrix.zh.md` | core |
| `citation_support_bank.md` | `citation_support_bank.zh.md` | optional |
| `latex_report.md` | `latex_report.zh.md` | optional |
| `final_artifact_manifest.md` | `final_artifact_manifest.zh.md` | optional |
| `artifact_check.md` | `artifact_check.zh.md` | optional |
| the final paper (`.tex` or `.md`) | `full_paper_translation.zh.md` | core |
| — | `translation_coverage.md` | optional |

**Rewrite-only additions:**

| English Source | Chinese Target | Tier |
|---|---|---|
| `original_logic_map.md` | `original_logic_map.zh.md` | optional |
| `rewrite_matrix.md` | `rewrite_matrix.zh.md` | optional |
| `logic_transfer_audit.md` | `logic_transfer_audit.zh.md` | optional |

**Build-only additions:**

| English Source | Chinese Target | Tier |
|---|---|---|
| `source_inventory.md` | `source_inventory.zh.md` | optional |
| `evidence_bank.md` | `evidence_bank.zh.md` | optional |
| `figure_asset_map.md` | `figure_asset_map.zh.md` | optional |
| `claim_register.md` | `claim_register.zh.md` | optional |

### Phase 2 — Translate

Translate every file listed in the inventory.  Follow these rules:

- **Plain prose files:** Translate the full text.  Preserve LaTeX citation keys
  (`\cite{...}`), labels (`\label{...}`), equations, file paths, raw numeric
  values, URLs, and code identifiers as-is.  Translate the surrounding prose.
- **Large tabular files** (`writing_rationale_matrix.md`,
  `citation_support_bank.md`, `section_blueprints.md`,
  `research_dossier.md`, `exemplar_learning_dossier.md`,
  `sota_gap_map.md`, and any workflow-specific tabular files):
  Translate **every row and every cell**.  The translated table must have
  at least as many rows as the original.  A shortened summary table is a
  failed output.
- **`full_paper_translation.zh.md`** must include: title, abstract, every
  section and subsection body paragraph, figure captions, table captions
  and table notes, limitations, conclusion, acknowledgements, and appendix
  narrative text.
- Update `manifest.md` status from `pending` → `translated` after each file.

Do not skip core files because they are "large."  Do not summarize instead of
translating.  Optional files may be skipped only under the tiered scope above
(`flash` tier or explicit user consent), with each skip recorded in
`manifest.md`.  The audit rejects partial core translations.

### Phase 3 — Verify

Run the guard script and require PASS:

```bash
# Resolve the script from this repository checkout, not the user's project cwd
# (a bare `python scripts/...` path is the most common reason the command fails).
REPO="$(git rev-parse --show-toplevel)"
python "$REPO/academic-toolkit/skills/spine-translate-zh/scripts/translate_guard.py" paper_rewriting_output --markdown --write
```

Same-name guard scripts exist in several spine skill directories (registered
in `academic-toolkit/data/duplicate_assets_registry.json`); use this skill's
own copy shown above.

This produces `translation_zh/translate_guard_report.md`.  If any check fails,
return to Phase 2 and fix the specific files flagged by the report.

Write `translation_coverage.md` listing every source file, its Chinese
counterpart, and its final status (`translated`).  Every entry must be
`translated` before the audit passes.

## Integration

This branch is called by the orchestrator after `spine-latex` and before
`spine-audit`.  The orchestrator's Non-Negotiable Route step 14 requires
the translate guard to PASS before audit begins.
