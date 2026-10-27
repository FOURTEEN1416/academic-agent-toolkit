---
name: latex-paper-collab-check
description: "Verify that the external CLI collaborators are installed, authenticated, and API-reachable before starting a collaboration workflow; missing CLIs only skip that phase."
metadata:
  short-description: Collaborator CLI health check
---


<!--ACAT-ADAPTED: 资产补齐自 yunshenwuchuxun/latex-paper-skills@d0f106108cb0（check-collaborators + _shared），正文未改。溯源见 references/UPSTREAM.md。2026-09-09 专项治理。2026-10-27 宿主叙事中性化（B′ 批遗留）：Claude Code 探测节改写为通用外部协作者 CLI 可用性探测，其余 Claude 专名同步中性化；Gemini 探测链作为既定外部协作者保留。-->
# Collaborator CLI Health Check

> **协作者定位**：被检查的 CLI 是外部协作者，不是执行前提；任一缺位仅降级对应协作阶段，当前 Agent 可继续自审运行。

## When to use
- Before starting any collaboration workflow that depends on external collaborator CLIs（可选增强检查：CLI 缺位时对应协作阶段直接跳过，不构成阻断）。
- When diagnosing CLI connectivity or authentication issues.
- After installing or reconfiguring any collaborator CLI.

## When not to use
- All collaborator CLIs are already confirmed working in the current session.
- The task does not involve cross-agent collaboration.

## Inputs
- Current OS environment (auto-detected).

## Outputs
- Summary table: Collaborator x CLI / Version / Auth / API / Status.
- Actionable remediation advice for any failed step.

- **De-AI polish（反AI味，强制）**：正文/成稿定稿前必读 `cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md` 的 `<de_ai_polish>` 段（工程/质检语汇泄漏、模板开头、AI 过渡词；中英文正文同样适用），并按其执行改写。

## Workflow

Run each configured collaborator's detection chain **in parallel** where possible.
For each collaborator, execute steps sequentially and **short-circuit on the first failure** — skip subsequent steps and mark the failure reason.

### Step 0: Detect OS

Determine the platform to choose the correct binary-lookup command:
- **Windows** (`win32`): use `where`
- **Unix/macOS**: use `which`

Detect via `uname -s 2>/dev/null` (returns nothing or errors on Windows) or check `$OSTYPE`.

---

### Gemini Detection Chain

#### 1. CLI Exists

```bash
# Unix
which gemini
# Windows
where gemini
```

**Pass**: command exits 0 and outputs a path.
**Fail**: command not found — suggest: `npm install -g @anthropic-ai/gemini-cli` or see https://github.com/google-gemini/gemini-cli

#### 2. Version

```bash
timeout 15 bash -c 'GEMINI_CLI_NO_RELAUNCH=true gemini --version'
```

On Windows (no `timeout` command), run directly:
```bash
GEMINI_CLI_NO_RELAUNCH=true gemini --version
```

`GEMINI_CLI_NO_RELAUNCH=true` is **required** to prevent the CLI from hanging.

**Pass**: output contains a version string (e.g., `0.32.1`).
**Fail**: timeout or no version output.

#### 3. Auth

Check for any of the following (any one is sufficient):
1. Environment variable `GEMINI_API_KEY` is set and non-empty.
2. Environment variable `GOOGLE_API_KEY` is set and non-empty.
3. File `~/.gemini/oauth_creds.json` exists.

```bash
[[ -n "$GEMINI_API_KEY" ]] || [[ -n "$GOOGLE_API_KEY" ]]
test -f "$HOME/.gemini/oauth_creds.json"
```

**Pass**: any one condition is true.
**Fail**: none found — suggest: `export GEMINI_API_KEY=<key>` or run `gemini` interactively to complete OAuth.

#### 4. API Connectivity

```bash
timeout 30 gemini --prompt "Reply with exactly: HEALTH_OK"
```

**Pass**: stdout contains `HEALTH_OK`.
**Fail**: timeout or no `HEALTH_OK` in output — suggest checking network, API key validity, or quota.

**Note**: Gemini CLI may emit warnings (e.g., skill conflict notices) in its output. These are benign and do not affect the health check. The pass/fail criterion is solely whether `HEALTH_OK` appears in stdout.

---

### External Collaborator CLI Detection (Generic Pattern, Optional Enhancement)

The four-step pattern below applies to **any** collaborator CLI: detect command
existence and authentication state the same way regardless of which product
provides the CLI. Instantiate `<collaborator-cli>` with the actual command name,
and take install/auth specifics from that CLI's own documentation. The Gemini
chain above is one concrete instantiation of this pattern.

#### 1. CLI Exists

```bash
# Unix
which <collaborator-cli>
# Windows
where <collaborator-cli>
```

**Pass**: command exits 0 and outputs a path.
**Fail**: command not found — suggest installing per the collaborator's official documentation (`<install-command>`).

#### 2. Version

```bash
timeout 15 <collaborator-cli> --version
```

**Pass**: output contains a version string (e.g., `1.2.3`).
**Fail**: timeout or no version output.

#### 3. Auth

Check for any of the following (any one is sufficient):
1. A credentials/profile file under the CLI's home directory.
2. The API-key environment variable documented by that CLI.
3. An auth/status subcommand reporting a logged-in state (e.g., `<collaborator-cli> auth status`, if the CLI provides one).

**Pass**: any one condition is true.
**Fail**: none found — suggest running `<collaborator-cli>` interactively to complete its login/OAuth flow.

#### 4. API Connectivity

```bash
timeout 30 <collaborator-cli> <minimal-prompt-flag> "Reply with exactly: HEALTH_OK"
```

**Pass**: stdout contains `HEALTH_OK`.
**Fail**: timeout or no `HEALTH_OK` — suggest checking network, API key validity, or quota.

**Note**: if the collaborator CLI supports a spend/limit flag, leave headroom
above the per-call minimum cost floor. Limit values below that floor
(e.g., `0.01`, `0.05`) can trigger immediate budget-exceeded errors before
inference starts.

---

## Output Format

Present a summary table after all checks:

```
| Collaborator | CLI | Version | Auth | API | Status    |
|--------------|-----|---------|------|-----|-----------|
| Gemini       | ✓/✗ | x.y.z   | ✓/✗  | ✓/✗ | Available / Failed |
| <collaborator-cli> | ✓/✗ | x.y.z | ✓/✗ | ✓/✗ | Available / Failed |
```

- Use `✓` for passed steps, `✗` for failed steps, `—` for skipped steps (due to short-circuit).
- **Status** is `Available` only if all 4 steps pass; otherwise `Failed`.
- Version column shows the detected version string, or `—` if not reached.

For any failed step, append actionable remediation advice below the table:

```
### Issues Found

**Gemini — Auth failed**
No API key or OAuth credentials detected.
→ Set `GEMINI_API_KEY` environment variable, or run `gemini` to complete OAuth login.

**<collaborator-cli> — CLI not found**
The collaborator CLI is not installed.
→ Install: `<install-command>` (per the collaborator's official docs)
→ Docs: the collaborator CLI's official documentation site
```

If all configured collaborators pass all checks:

```
All collaborator CLIs are available and ready for collaboration workflows.
```

## Verification
- Run this skill and confirm the summary table appears with correct status for each collaborator.

## Safety and guardrails
- Read-only checks only; no configuration files are modified.
- API connectivity tests consume minimal tokens (~$0.01 per check).
- Steps 2-4 spawn external CLI processes; run them outside sandbox (escalated permissions) to avoid hangs or `EPERM` errors.
- On Windows, `timeout` may not be available; run commands directly and watch for hangs.
- Gemini `--version` **must** use `GEMINI_CLI_NO_RELAUNCH=true` to prevent the CLI from relaunching itself.
