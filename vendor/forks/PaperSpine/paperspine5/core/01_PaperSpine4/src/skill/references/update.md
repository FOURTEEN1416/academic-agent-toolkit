# Update Stage

This file is the canonical update playbook for the `paper-spine` orchestrator.
Update commands never start intake or the writing workflow.

## User Commands

| User intent | Action |
|---|---|
| `/paperspine update check` | Run a read-only, immediate version check. |
| `/paperspine update` | Run a manual update. The explicit command authorizes installation; use `--yes`. |
| `/paperspine auto-update on` | Opt in to launch-time automatic updates, checked at most once every 24 hours. |
| `/paperspine auto-update on 72h` | Opt in with a custom 1-168 hour interval. |
| `/paperspine auto-update off` | Disable automatic updates. |
| `/paperspine auto-update status` | Show the local policy and last result without using the network. |

Do not infer consent to enable automatic updates. They are disabled until the
user runs the `on` command.

## Resolve the Installed Updater

Use the first existing installed path. A repository checkout may use
`src/scripts/paperspine_update.py` directly.

Windows candidates:

```powershell
$candidates = @(
  (Join-Path $env:USERPROFILE ".codex\skills\paper-spine\scripts\paperspine_update.py"),
  (Join-Path $env:USERPROFILE ".claude\skills\paper-spine\scripts\paperspine_update.py"),
  (Join-Path $env:USERPROFILE ".openclaw\skills\paper-spine\scripts\paperspine_update.py"),
  (Join-Path $env:USERPROFILE "AppData\Local\hermes\skills\academic-writing\paper-spine\scripts\paperspine_update.py")
)
$script = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $script) { throw "PaperSpine updater not found. Reinstall PaperSpine." }
```

macOS / Linux candidates:

```bash
for script in \
  "$HOME/.codex/skills/paper-spine/scripts/paperspine_update.py" \
  "$HOME/.claude/skills/paper-spine/scripts/paperspine_update.py" \
  "$HOME/.openclaw/skills/paper-spine/scripts/paperspine_update.py"
do
  [ -f "$script" ] && break
done
[ -f "$script" ] || { echo "PaperSpine updater not found. Reinstall PaperSpine." >&2; exit 1; }
```

## Script Mapping

After resolving the script:

```text
update check        -> python <script> --check-only
manual update       -> python <script> --yes
auto-update on      -> python <script> --enable-auto-update --interval-hours 24
auto-update off     -> python <script> --disable-auto-update
auto-update status  -> python <script> --auto-status
launch preflight    -> python <script> --auto
```

Use `python3` where `python` is unavailable. `--target
codex|claude|openclaw|hermes` limits a manual update or records the target when
automatic updates are enabled; the default is all four hosts.

## Launch-Time Automatic Update Contract

On a normal PaperSpine launch, run `python <script> --auto` before intake or
resuming a paper. This is a local no-op when automatic updates are disabled or
the configured interval has not elapsed. When due, it checks the manifest and,
if a newer version exists, installs it without another prompt because the user
previously opted in.

- If an update was installed, stop the current PaperSpine workflow and tell the
  user to reload/restart the host, then invoke `/paperspine` again. Do not mix
  instructions loaded before and after an update in one paper run.
- If the check fails, report the warning and continue with the existing local
  version. The updater records the error and throttles repeated launch checks.
- Automatic update is not a background service. It runs only on PaperSpine
  launches, so it adds no daemon, scheduler, or startup item.

## Safety and State

- Read the local version from `~/.paperspine/install_state.json` and the
  automatic policy from `~/.paperspine/update_policy.json`.
- Compare with the GitHub release manifest and validate the complete core
  package before touching an installed host.
- Update the `paper-spine` skill plus the Claude command and Codex prompt for
  Codex, Claude Code, OpenClaw, and Hermes.
- Replace selected host entries as one transaction; if a filesystem operation
  fails, restore the entries changed earlier in that transaction.
- Preserve `~/.paperspine/config.json` and every project artifact.
- On network or package validation failure, do not delete or partially replace
  the current installation.
- A successful update requires a host reload before the new instructions are
  considered active.

## Offline and Advanced Use

- `--repo-archive <path>` accepts a local repository directory or zip for
  offline/manual verification and tests.
- `--auto --force` bypasses the interval once but still refuses to run when
  automatic updates are disabled.
- Exit code `2` from `--check-only` means an update is available; it is not an
  installation failure.
