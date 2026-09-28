---
description: Start PaperSpine — research, then rewrite or build a paper or report end to end
argument-hint: "[optional: target/scene, e.g. 'IEEE conference paper from ./materials']"
---

Start the PaperSpine workflow for the current project using the **`$paper-spine`
orchestrator** skill. Route through `$paper-spine`; do not call the worker
sub-skills directly unless the orchestrator tells you to.

If `paper_rewriting_output/paper_spine_config.json` is missing or incomplete,
your FIRST tool action MUST be to run the launcher below with
`sandbox_permissions: require_escalated` (opening a visible window is an
escalated action in Codex; without it the window will not reliably appear). Do
NOT inspect materials, infer defaults, create config files, or continue the
workflow before the UI has launched or explicitly failed. Resolve the launcher
by its absolute installed path — Codex runs from the project folder, where
`scripts/` does not exist. Only fall back to numbered/chat intake on launch error.

### Windows

```powershell
$config = Join-Path (Get-Location) "paper_rewriting_output\paper_spine_config.json"
$launcher = @(
  "$env:USERPROFILE\.codex\skills\paper-spine\scripts\launch_paperspine_ui.ps1",
  "$env:USERPROFILE\.claude\skills\paper-spine\scripts\launch_paperspine_ui.ps1",
  "$env:USERPROFILE\AppData\Local\hermes\skills\academic-writing\paper-spine\scripts\launch_paperspine_ui.ps1"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $launcher) { throw "PaperSpine UI launcher not found. Reinstall or resync PaperSpine." }
if (-not (Test-Path -LiteralPath $config)) {
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File $launcher -OutputDir "paper_rewriting_output"
}
for ($i = 0; $i -lt 120 -and -not (Test-Path -LiteralPath $config); $i++) { Start-Sleep -Seconds 5 }
if (-not (Test-Path -LiteralPath $config)) {
  throw "PaperSpine intake config not created yet. Finish the opened UI window, then rerun /paperspine."
}
Get-Content -LiteralPath $config -Raw
```

### macOS / Linux

```bash
CONFIG="paper_rewriting_output/paper_spine_config.json"
LAUNCHER="$HOME/.codex/skills/paper-spine/scripts/launch_paperspine_ui.sh"
[ -f "$LAUNCHER" ] || LAUNCHER="$HOME/.claude/skills/paper-spine/scripts/launch_paperspine_ui.sh"
if [ ! -f "$LAUNCHER" ]; then
  echo "PaperSpine UI launcher not found. Reinstall or resync PaperSpine." >&2; exit 1
fi
if [ ! -f "$CONFIG" ]; then
  chmod +x "$LAUNCHER"; bash "$LAUNCHER" "paper_rewriting_output"
fi
for i in $(seq 1 120); do [ -f "$CONFIG" ] && break; sleep 5; done
if [ ! -f "$CONFIG" ]; then
  echo "PaperSpine intake config not created yet. Finish the opened terminal, then rerun /paperspine." >&2; exit 1
fi
cat "$CONFIG"
```

### After config is ready

When the config already exists, read it and continue through the `$paper-spine`
orchestrator workflow (research → confirm motivation → rationale matrix →
rewrite/build → LaTeX/PDF/Word → audit) without relaunching intake unless
required fields are missing. If `$1` was provided, treat it as the target/scene hint.
