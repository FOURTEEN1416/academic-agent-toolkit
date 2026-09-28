---
allowed-tools: Bash(powershell:*), Bash(powershell.exe:*), Bash(pwsh:*), Bash(cmd:*), Bash(bash:*), Bash(sh:*), Bash(chmod:*)
description: Start PaperSpine with automatic intake UI when configuration is missing
argument-hint: "[update check | auto-update on|off|status | optional paper target]"
---

Start the PaperSpine workflow for the current project.

Invocation arguments: `$ARGUMENTS`

If the arguments request `update`, `update check`, or `auto-update
on|off|status`, route immediately through the `paper-spine` skill's
`references/update.md`. Do not launch intake or start a paper workflow for an
update command.

For every other invocation, run the update playbook's `--auto` preflight before
intake. If it installs a new version, stop and ask the user to reload Claude
Code and invoke `/paperspine` again. If it is disabled, not due, already current,
or fails without changing the install, continue with the current version.

After update routing and preflight, if
`paper_rewriting_output/paper_spine_config.json` is missing or incomplete,
route through the `paper-spine` skill and launch the PaperSpine intake UI
automatically.
Do not hand-write the configuration.

## Platform-specific launcher

### Windows

```powershell
$config = Join-Path (Get-Location) "paper_rewriting_output\paper_spine_config.json"
$launcher = Join-Path $env:USERPROFILE ".claude\skills\paper-spine\scripts\launch_paperspine_ui.ps1"
if (-not (Test-Path -LiteralPath $launcher)) {
  throw "PaperSpine UI launcher not found at $launcher. Reinstall or resync PaperSpine."
}
if (-not (Test-Path -LiteralPath $config)) {
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File $launcher -OutputDir "paper_rewriting_output"
}
for ($i = 0; $i -lt 120 -and -not (Test-Path -LiteralPath $config); $i++) {
  Start-Sleep -Seconds 5
}
if (-not (Test-Path -LiteralPath $config)) {
  throw "PaperSpine intake config was not created yet. Finish the opened PowerShell UI window, then rerun /paperspine."
}
Get-Content -LiteralPath $config -Raw
```

### macOS / Linux

```bash
CONFIG="paper_rewriting_output/paper_spine_config.json"
LAUNCHER="$HOME/.claude/skills/paper-spine/scripts/launch_paperspine_ui.sh"

if [ ! -f "$LAUNCHER" ]; then
  echo "PaperSpine UI launcher not found at $LAUNCHER. Reinstall or resync PaperSpine." >&2
  exit 1
fi

if [ ! -f "$CONFIG" ]; then
  chmod +x "$LAUNCHER"
  bash "$LAUNCHER" "paper_rewriting_output"
fi

for i in $(seq 1 120); do
  if [ -f "$CONFIG" ]; then break; fi
  sleep 5
done

if [ ! -f "$CONFIG" ]; then
  echo "PaperSpine intake config was not created yet. Finish the opened terminal window, then rerun /paperspine." >&2
  exit 1
fi

cat "$CONFIG"
```

## After config is ready

When the config already exists, read it directly and continue through the
`paper-spine` orchestrator workflow without relaunching intake unless required
fields are missing.
