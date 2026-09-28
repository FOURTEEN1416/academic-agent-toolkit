# Update Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Check for and install PaperSpine updates from GitHub while preserving global
config.

## Script

Windows:
```powershell
$script = Join-Path $env:USERPROFILE ".claude\skills\paper-spine\scripts\paperspine_update.py"
python $script --yes
```

macOS / Linux:
```bash
python3 ~/.claude/skills/paper-spine/scripts/paperspine_update.py --yes
```

For version check only: `--check-only` instead of `--yes`.

## Behavior

- Read local install state from `~/.paperspine/install_state.json`.
- Compare against GitHub `main` manifest.
- Update Codex, Claude Code, and OpenClaw by default.
- Preserve `~/.paperspine/config.json`.
- Never touch project artifacts.
- If network fails, report the error; do not delete local skills.

## Advanced

- `--target codex|claude|openclaw` for single-host update.
- `--repo-archive <path>` for local/offline update.
