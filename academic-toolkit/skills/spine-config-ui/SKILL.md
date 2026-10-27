---
name: spine-config-ui
description: Launches the PaperSpine external terminal configuration UI. (internal /paperspine step)
---


<!--ACAT-ADAPTED: 资产回填自 WUBING2023/PaperSpine@1fe46f0e76aa（单技能拆分重组编排）。溯源见 references/UPSTREAM.md。2026-09-09 专项治理。-->
# PaperSpine UI

Use this branch whenever `paper_spine_config.json` is missing, incomplete, or
the user asks to configure PaperSpine interactively.

## Required Behavior

The supported interaction is a real terminal window launched by
the bundled `launch_paperspine_ui.ps1` (resolve its absolute path inside the repo
checkout). When configuration is missing, launch the UI as the first action; do
not infer config from materials instead. Do not run `input()`-based Python in an
execution environment where stdin is not exposed (hidden terminal or sandbox).

```powershell
# Resolve the launcher from the repository checkout. Run commands from the
# user's project folder, where `scripts/` does not exist, so a relative path is
# the most common reason the UI window never opens.
$repo = git rev-parse --show-toplevel
$launcher = Join-Path $repo "academic-toolkit/skills/spine-intake/scripts/launch_paperspine_ui.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $launcher -OutputDir paper_rewriting_output
```

If no separate window appears (no interactive desktop, or a sandboxed
environment), add `-InPlace` to run the wizard in the current terminal instead;
if stdin is still not interactive, fall back to numbered menus or native
structured questions. Never silently skip configuration.

The UI writes:

```text
paper_rewriting_output/paper_spine_config.json
paper_rewriting_output/paper_spine_config.md
```

## UI Contract

- Open a separate interactive terminal window when possible.
- Provide a full-screen terminal UI when a real Windows terminal is available:
  centered welcome screen, white ridge wordmark, readable field/option panels,
  and a stable 30% field list plus 70% detail panel.
- Use Up/Down for field navigation, Left/Right for choice fields, Enter for
  text/list editing, `S` to save, and `Q` to quit.
- Show only one active field's reasoning and value details on the right panel;
  do not dump a long JSON-like checklist into the chat.
- Fall back to numbered terminal menus only when arrow-key UI is unavailable.
- Use chat questions only when terminal execution is impossible.
- Never require the user to manually write JSON.

Read `references/interactive-intake.md` for the question order and fallback
template.
