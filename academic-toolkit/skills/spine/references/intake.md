# Intake Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Collect workflow options and write validated configuration before any substantive work.

## Required Output

- `paper_rewriting_output/paper_spine_config.json`
- `paper_rewriting_output/paper_spine_config.md`

## Config Fields

| Field | Allowed Values | Default |
|---|---|---|
| `workflow` | `rewrite_existing`, `build_from_materials` | — |
| `scene` | `journal`, `conference`, `report_review`, `competition` | — |
| `tier` | `flash`, `pro` | `flash` |
| `output_language` | `en`, `zh` | `en` for journal/conference; `zh` for Chinese requests |
| `target_name` | free text | — |
| `materials_dir` | path or empty | — |
| `draft_path` | path or empty | — |
| `user_motivation` | free text or empty | — |
| `official_urls` | list | `[]` |
| `special_requirements` | list | `[]` |
| `word_output` | `none`, `docx` | `docx` |
| `translation_package` | `none`, `zh` | `none` |
| `reference_mode` | `local_first`, `specified_paths`, `web` | `local_first` |
| `reference_paths` | list of local paths | `["."]` |
| `citation_target_count` | integer | `20` |
| `humanize_tier` | `none`, `light`, `medium`, `heavy` | `medium` |

## UI

- The supported interactive path is the bundled terminal wizard (`intake_wizard.py`).
- When config is missing, launch this wizard automatically; resolve its launcher by absolute path from the repository checkout root.
- Fallback: numbered menus; native structured questions when the execution environment supports them; chat-based questions only when terminal execution is impossible.
- Never require the user to hand-write JSON.

## Scripts

```bash
python scripts/intake_wizard.py --output-dir paper_rewriting_output
```
