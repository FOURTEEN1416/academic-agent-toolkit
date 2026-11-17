# Intake Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Collect workflow options and write validated configuration before any substantive work.
When resuming, reuse a confirmed configuration; switching to a new `workflow`
label does not erase valid earlier choices — carry them forward unless the user
revises them.

## Research Scope Discipline

Research scope is a promise about what analysis the paper may rely on:

- `required`: the requested research/analysis is performed with real tools and
  evidence; a literature dossier or analysis plan alone does not complete it.
- `agent_decide`: assess what evidence the scientific question needs and what
  the inputs support, state the rationale briefly, then perform the justified
  work. This mode never silently means `materials_only`.
- `materials_only`: use the supplied analyses, tables, images and reported
  results without new EDA, tests, modelling or reruns; literature study,
  faithful extraction, plotting supplied results and consistency checks remain
  available. Supplying materials or asking for a draft first does not
  automatically select this mode.

## Deliverable Invariance

`tier` selects research/example breadth and optional process depth only. It
never changes the requested deliverable type, the necessary scientific
argument, venue structure, or manuscript length: a `flash` journal run still
produces a full journal manuscript; it simply researches fewer examples than
`pro`.

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
