# PaperSpine Project Memory (V4)

## Project Purpose

PaperSpine is a contribution-first paper and report writing skill for Claude
Code, Codex, OpenClaw, and Hermes CLI. It researches the target scene, confirms
the controlling contribution and motivation with the user, then writes/rewrites/
builds end to end with LaTeX/PDF/Word output. The methodology is enforced by
gates: **Contribution-First** (`confirmed_contribution.md`), **Results-as-
Validation** (`results_validation.md`), **Reviewer-Aware** (`reviewer_audit.md`).
Motivation is still required, but it supports the confirmed contribution.

Version: **4.0.0** (canonical: `dist/paperspine_version.json`, auto-propagated to
`.claude-plugin/plugin.json` and `marketplace.json` by the sync script).

## Architecture: ONE skill

V4 collapsed the old 12-skill flat suite into a **single `paper-spine` skill** —
an orchestrator with 12-stage routing inside `SKILL.md`, `references/` playbooks
for each stage, and `agents/` role cards for parallel sub-agents. There are no
longer separate worker skills.

### Single source of truth: `src/`

- `src/skill/SKILL.md` — orchestrator + command/stage routing tables
- `src/skill/references/*.md` — per-stage playbooks (intake, research, citation,
  rewrite, build, humanize, latex, audit, translate, submission, respond,
  resume, contribution, results-validation, reviewer-audit, scenarios, …)
- `src/skill/agents/*` — role cards for fan-out agents (research scene/sota/
  exemplar, reviewer method/evidence/writing) + `openai.yaml`
- `src/scripts/*.py` — deterministic gate/check scripts (standard library only):
  `sync_local_installs.py`, `contribution_check.py`,
  `results_validation_check.py`, `reviewer_audit_check.py`, `progress_check.py`,
  `submission_check.py`, `respond_check.py`, `citation_verification_en.py`,
  `latex_guard.py`, `humanize_check.py`, `style_metrics.py`, etc.
- `src/adapters/{claude,codex,hermes}` — per-host frontmatter/manifest overlays

### Generated: `dist/` (never hand-edit)

`dist/` is fanned out from `src/` by `sync_local_installs.py` for **4 hosts**:

- `dist/claude/skills/paper-spine` (+ `/paperspine` command)
- `dist/codex/skills/paper-spine` (+ `/paperspine` prompt)
- `dist/openclaw/skills/paper-spine`
- `dist/hermes/skills/academic-writing/paper-spine`

Install entry points: `python install.ps1` (Windows) / `bash install.sh`
(macOS/Linux) — thin wrappers delegating to `src/scripts/sync_local_installs.py`;
PS5.1-safe; they never touch `settings.json`.

Acceptance harness: `examples/v4_acceptance.py`.

## DISCIPLINE — rules guarded by tests

1. **Single source of truth.** Edit `src/` only; never hand-edit `dist/` copies.
   Regenerate with `python src/scripts/sync_local_installs.py --dist-only`
   (project-internal) or `--clean-legacy` (full sync to install dirs). A
   dist-sync guard test fails if `dist/` drifts from `src/`.
2. **Never author backslash/LaTeX markdown via Python string concatenation.**
   Write LaTeX/Markdown templates as literal file content, not built up from
   pieces in Python. A control-char corruption test guards this.
3. **Home isolation.** Any code touching `~/.claude` / `~/.codex` / `hermes`
   must take directory arguments (install-dir overrides) and must **never**
   touch `settings.json`. Guarded by validate_repo / install tests.
4. **Standard library only** for `src/scripts/` Python.

## Before claiming ready

```powershell
python -m pytest tests          # expect 197 passed
ruff check src/scripts tests
```

Do not push to GitHub unless explicitly asked. Keep `README.md` (Chinese) and
`README.en.md` (English) content-equivalent.
