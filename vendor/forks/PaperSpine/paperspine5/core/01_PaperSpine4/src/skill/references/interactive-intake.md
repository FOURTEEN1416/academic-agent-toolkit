# Interactive Intake

Use this reference when PaperSpine needs workflow configuration.

## Question Order

Read the same task's saved configuration first. Open its current configuration page only when input or a change is needed; use the actual public schema and ask only for missing decisions. The historical field list below is a checklist to interpret, not a mandatory questionnaire:

1. Workflow: use the actual saved public value: build_from_materials, rewrite_existing, audit, review, revise or transfer. Preserve its requested work type.
2. Scene: use the current public scene schema and the user's actual journal, conference, report, review, competition or other target; do not submit the historical report_review alias.
3. Legacy tier: `flash` or `pro` only explains old records; current tasks use the saved literature settings and requested scientific scope.
4. Output language: read configuration.output_language and the actual requested language(s), including multilingual requests; do not restrict the current workflow to en/zh.
5. Target name: journal, conference, course, report type, or competition name.
6. Draft path for `rewrite_existing`, or materials directory for
   `build_from_materials`.
7. User motivation, if known.
8. Official URLs, if known.
9. Special requirements.
10. Requested output formats: use current `formats`, including DOCX when requested/defaulted; do not submit old `word_output` fields.
11. Requested language/translation package: use current `output_language` and formats; do not restrict multilingual output to the old `none`/`zh` option.

## Web-First Intake

Keep first use inside the current host:

1. Use the public host tools to open a genuinely new task or resume the task
   identified by the user and its material roots, then open its workspace in
   the user's connected browser. Do not stop after creating the task or printing
   its URL.
   Persist task facts through the public command API; never manufacture an
   `integration_job.json` or edit the task database directly.
2. Otherwise invoke the installed `launch_paperspine_ui` wrapper. It starts the
   same public Web service in the background and opens the browser with the
   existing profile. Scientific work remains in this host conversation.
3. Use host typed questions or chat only for exact author/target/figure/contribution
   confirmations surfaced by the persisted task issue. Submit those answers through
   the same authenticated Web API; never create a parallel config truth.

Do not launch an external terminal as the first tool action, request escalation
just to show intake, or poll for a separate window.

The current host Agent performs the scientific work. The local Web service needs only the permissions required for its actual task/configuration/file functions. Do not treat a hidden J4–J11 child Agent or a separate Codex application login as a launch prerequisite. Reuse the same task/profile, report an actual service failure accurately, and resolve only the concrete failing capability.

## Browser and progress handoff

The first visible handoff is the actual task page, not the Web root or a
terminal receipt. After task creation/resume, use the returned origin plus
`skill_bridge.web_path` (or `/?task_id=<same-task-id>`) in the same browser and
verify the title, materials/configuration cards and current stage. If browser
control is available, open that exact URL and inspect the rendered page; if it
is unavailable, provide the exact task URL and disclose that it was not opened.
Start service-only; open one chosen browser, not both a default-browser homepage
and an in-app task tab. A background server alone is not a handoff.

When scientific progress or the next user action changes, commit a short factual
milestone with actual useful artifact IDs through the public task API. The command
result already contains the updated projection; use it instead of immediately
fetching the full task again. Check the actual page when handing off user input or
diagnosing a display problem. Unchanged progress needs no duplicate milestone.
Make useful research notes or draft outputs visible by publishing those files;
a stage label alone does not expose their contents. While waiting for
the user, leave the task in that stage and use `paperspine_wait_for_task_change`;
do not continue from a stale shell snapshot or silently advance several stages.

## Standalone Web Launcher

When the host has no Product Kernel tools, use the installed launcher as a thin
adapter to the same Web workspace. It does not start the historical terminal
wizard and it must fail clearly rather than pretend a TUI is Web.

```powershell
$launcher = @(
  "$env:USERPROFILE\.codex\skills\paper-spine\scripts\launch_paperspine_ui.ps1",
  "$env:USERPROFILE\.claude\skills\paper-spine\scripts\launch_paperspine_ui.ps1",
  "$env:USERPROFILE\AppData\Local\hermes\skills\academic-writing\paper-spine\scripts\launch_paperspine_ui.ps1"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $launcher
```

macOS/Linux:

```bash
LAUNCHER="$HOME/.codex/skills/paper-spine/scripts/launch_paperspine_ui.sh"
[ -f "$LAUNCHER" ] || LAUNCHER="$HOME/.claude/skills/paper-spine/scripts/launch_paperspine_ui.sh"
chmod +x "$LAUNCHER" && "$LAUNCHER"
```

The public launcher returns the actual `address`, `process_id`, `binding`,
`profile_root`, `reused` and `scientific_agent_started=false`. `READY` means the
same service responded, not that research ran. `runtime_code_status=changed`
reports code replaced since that owned service loaded; resume with that same
profile after the specific service is restarted. An older receipt without a
code fingerprint is `unverified`, not proof of current loaded bytes.

Only the explicit legacy launcher returns a `paperspine5.web-workspace-receipt` containing the local
URL, PID, user-data root, build identity, `frontend=web`, and
`terminal_frontend=false`. A refresh reuses the tab-scoped session; a repeated
launch reuses the healthy workspace instead of creating parallel state.
`reused` and `server_reused` describe a live server process, while
`output_root_preexisting` and `output_root_had_entries` separately report
whether the chosen data root already existed or contained user files. Never
infer an empty/new root from `reused=false`. PowerShell `-?`, `-h`, `-help`, `--help` and
Shell `-h`/`--help` are zero-start help paths: they must not create the output
root, open a browser, or start/reuse a server.

## User Confirmation Boundary

Ask only the precise question represented by the current persisted issue and
wait when user authority is required. Do not ask the user to paste or hand-author
a configuration skeleton or academic JSON contract.

The persisted JSON or Product Kernel task record is the source of truth for
later stages.
