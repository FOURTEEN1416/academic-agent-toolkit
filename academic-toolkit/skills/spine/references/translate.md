# Translate Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Produce the complete `translation_zh/` package when `output_language=en` and
`translation_package=zh`. Every required file must be translated; partial
translation is a failed output.

Important: `translation_zh/` is the Chinese translation audit/intermediate
package. It is not the final user-facing Chinese document. When Word output is
enabled, the final Chinese deliverable must also be generated as one Word file:

- `paper_rewriting_output/final_paper/paper.zh.docx`
- `paper_rewriting_output/word_report.zh.md`

Do not report "Chinese translation: translation_zh/ - 10 files" as the final
Chinese doc deliverable. The user-facing result is `paper.zh.docx`.

## Three-Phase Flow

### Phase 1 - Inventory

List every file to translate. Write `translation_zh/manifest.md`. `translate_guard.py`
demands the exact set below (every file lives under `translation_zh/`); a missing
file is a BLOCKER.

Common files (required for both workflows):

- `manifest.md`
- `translation_coverage.md`
- `paper_spine_config.zh.md`
- `source_map.zh.md`
- `reference_materials/source_index.zh.md`
- `research_dossier.zh.md`
- `exemplar_learning_dossier.zh.md`
- `style_profile.zh.md`
- `sota_gap_map.zh.md`
- `motivation_options_after_research.zh.md`
- `confirmed_motivation.zh.md`
- `section_blueprints.zh.md`
- `writing_rationale_matrix.zh.md`
- `citation_support_bank.zh.md`
- `final_structure.zh.md`
- `final_paper.zh.md`
- `full_paper_translation.zh.md`
- `latex_report.zh.md`
- `final_artifact_manifest.zh.md`
- `artifact_check.zh.md`

Additional files for the `rewrite_existing` workflow:

- `original_logic_map.zh.md`
- `rewrite_matrix.zh.md`
- `logic_transfer_audit.zh.md`

Additional files for the `build_from_materials` workflow:

- `source_inventory.zh.md`
- `evidence_bank.zh.md`
- `figure_asset_map.zh.md`
- `claim_register.zh.md`

### Phase 2 - Translate

- Plain prose: translate full text; preserve LaTeX keys, labels, equations, URLs.
- Large tabular files: translate every row and cell; no summary.
- `full_paper_translation.zh.md`: title, abstract, every section, captions,
  tables, conclusion, appendix.

### Phase 3 - Final Chinese Word Document

After `translation_zh/full_paper_translation.zh.md` is complete, convert it into
the final user-facing Chinese Word document:

```bash
pandoc paper_rewriting_output/translation_zh/full_paper_translation.zh.md \
  -o paper_rewriting_output/final_paper/paper.zh.docx
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx \
  --markdown --output paper_rewriting_output/word_report.zh.md
```

If pandoc is unavailable while Word output is required, write BLOCKED/FAIL in
the relevant report and do not claim the Chinese deliverable is complete.

### Phase 4 - Verify

```bash
python scripts/translate_guard.py paper_rewriting_output --markdown --write
python scripts/progress_check.py paper_rewriting_output --gate word --require
```

Require PASS. Write `translation_coverage.md`.

## Integration

Called after LaTeX and before audit. The orchestrator requires translate guard
to PASS before audit begins. When Word output is enabled, the workflow is not
complete until `final_paper/paper.zh.docx` and `word_report.zh.md` exist.
