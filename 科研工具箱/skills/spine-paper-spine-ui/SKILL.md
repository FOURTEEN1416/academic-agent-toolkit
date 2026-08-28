---
name: paper-spine-ui
description: Launches the PaperSpine external terminal configuration UI for Codex and Claude Code. (internal /paperspine step)
---

# PaperSpine UI

Use this branch whenever `paper_spine_config.json` is missing, incomplete, or
the user asks to configure PaperSpine interactively.

## Required Behavior

The supported interaction is a real terminal window launched by
the installed `launch_paperspine_ui.ps1` (resolve its absolute path under
`~/.codex/skills/...` or `~/.claude/skills/...`). Do not run `input()`-based Python inside a
hidden tool surface when the host cannot expose stdin.

In Claude Code, `/paperspine` must call this branch automatically when config is
missing.

In Codex, launching this window opens a visible GUI/terminal, which Codex treats
as an escalated action — request it with `sandbox_permissions: require_escalated`,
or the window will not reliably appear. Launch the UI as the first action when
config is missing; do not infer config from materials instead.

```powershell
# Pass the ABSOLUTE path to the installed launcher. Codex/Claude run from the
# user's project folder, where `scripts/` does not exist, so a relative path is
# the most common reason the UI window never opens. Resolve the install dir:
$launcher = @(
  "$env:USERPROFILE\.codex\skills\paper-spine-ui\scripts\launch_paperspine_ui.ps1",
  "$env:USERPROFILE\.claude\skills\paper-spine-ui\scripts\launch_paperspine_ui.ps1",
  "$env:USERPROFILE\.codex\skills\paper-spine-intake\scripts\launch_paperspine_ui.ps1",
  "$env:USERPROFILE\.claude\skills\paper-spine-intake\scripts\launch_paperspine_ui.ps1"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $launcher -OutputDir paper_rewriting_output
```

If no separate window appears (headless or sandboxed Codex with no
interactive desktop), add `-InPlace` to run the wizard in the current
terminal instead; if stdin is still not interactive, fall back to numbered
menus or native questions. Never silently skip configuration.

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
