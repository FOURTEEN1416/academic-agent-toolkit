---
allowed-tools: Bash(powershell:*), Bash(powershell.exe:*), Bash(pwsh:*), Bash(cmd:*), Bash(bash:*), Bash(sh:*), Bash(chmod:*)
description: Open or resume the current PaperSpine Skill workflow, or handle an explicit update request
argument-hint: "[update check | optional paper target]"
---

Invocation arguments: `$ARGUMENTS`

Read the installed `paper-spine` Skill and follow its current host workflow.
The host Agent performs research, writing, figures and revision; Web stores the
same task's configuration, choices and feedback and presents actual files.

For an explicit update or update-check request, read `references/update.md` and
handle that request without starting paper work. On a normal paper invocation,
follow the installed Skill's `scripts/paperspine_update.py --preflight --yes`
once, then continue the same task. This original wrapper now selects the full
suite channel for the actual operating system; explicit opt-out is respected.
After upgrading, reread the installed Skill and current public tool schemas.

For writing, formatting, review or revision, open or resume the user's existing
public task as directed by `SKILL.md` and `references/product-v1-workflow.md`.
Use the installed `scripts/paperspine5_web.py launch` and its `host`
commands when public MCP tools are not exposed. Reuse the remembered or explicitly
supplied profile; read the actual saved configuration before continuing.

A missing historical `paper_rewriting_output/paper_spine_config.json` is not a
reason to create another task, restart intake or use a legacy Runner flow.
Treat invocation arguments as the user's instructions or target hint, preserving
valid existing materials, configuration, selections and versions. Continue the
same task through actual writing, target-venue formatting, independent review,
preview/download and requested revision.
