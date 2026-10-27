---
name: latex-paper-collab-breadth
description: "Use an external CLI agent as a breadth-exploration co-pilot for paper-from-zero. Primary role: candidate direction expansion and idea divergence (breadth over depth). 只用于选题/方向发散；逐点深挖与论证收敛场景改用 latex-paper-collab-depth. Optional collaborator, skips when CLI absent."
metadata:
  short-description: Breadth co-pilot (external CLI) for paper-from-zero
---


<!--ACAT-ADAPTED: 资产补齐自 yunshenwuchuxun/latex-paper-skills@d0f106108cb0（collaborating-with-gemini + _shared），正文未改。溯源见 references/UPSTREAM.md。2026-09-09 专项治理。-->
# Collaborating with Gemini

Use Gemini CLI as a **breadth-exploration** collaborator for paper-from-zero,
or as a generic code collaborator in fallback mode.

> **协作者定位**：本技能把 gemini CLI 当作**外部评审桥协作者**调用（可选增强），不预设执行环境；`gemini` 不在 PATH 时跳过该协作者、由当前 Agent 自审降级，不阻断流程。


This skill provides a lightweight bridge script that returns structured JSON
and supports multi-turn sessions via `SESSION_ID`.

> **Shared rules**: This skill inherits all shared rules from
> `../../_shared/collaboration-base.md` (core rules, candidates-only
> constraint, fallback code-collaboration mode, safety guardrails, and
> collaboration state capsule format).  Only Gemini-specific additions
> are listed below.

## When to Use
- paper-from-zero needs to expand the candidate literature pool.
- topic-brief initial draft exists but adjacent research areas are uncovered.
- contribution-map needs 3-5 alternative framing candidates.
- evidence-matrix has coverage gaps that need broader search directions.
- Fallback: generic code collaboration tasks (analysis, patch, review).

## When NOT to Use
- Claim-level logical analysis or reviewer objection stress tests (use latex-paper-collab-depth).
- Final routing judgment between review/empirical (use latex-paper-collab-depth).
- Generating `ref.bib` entries or verified citations.
- Tasks requiring depth reasoning rather than breadth scanning.

## Gemini-Specific Rules
- Optional: pass `--sandbox` to run Gemini in sandbox mode.
- Auth/home notes:
  - The bridge defaults `GEMINI_CLI_HOME` to a writable repo-local directory
    (`<repo>/.gemini_cli_home/`) to avoid Gemini CLI hanging in some runners.
  - If your local `gemini` is already logged in, reuse that login with
    `--use-user-home`.
  - If you have `GEMINI_API_KEY` set but want to use OAuth creds, add
    `--prefer-oauth` to unset API-key env vars for this run.

## Quick Start (shell-safe)

If your prompt contains Markdown backticks, use a heredoc; see `references/shell-quoting.md`.

> 本技能未随包提供 gemini bridge 脚本；`gemini` 在 PATH 时由调用方按上游参数（`--cd`/`--PROMPT`/`--SESSION_ID`/`--output-format`）直接调用，或使用自备的等价桥脚本；CLI 缺位时按协作者定位声明降级。

```bash
PROMPT="$(cat <<'EOF'
Review src/auth.py around login() and propose fixes.
OUTPUT: Unified Diff Patch ONLY.
EOF
)"
python3 <gemini-bridge-script> --cd "." --PROMPT "$PROMPT"
```

**Output:** JSON with `success`, `SESSION_ID`, `agent_messages`, and optional `error` / `all_messages`.

## Multi-turn Sessions

```bash
# Start a session
PROMPT="$(cat <<'EOF'
Analyze the bug in foo(). Keep it short.
EOF
)"
python3 <gemini-bridge-script> --cd "." --PROMPT "$PROMPT"

# Continue the same session
PROMPT="$(cat <<'EOF'
Now propose a minimal fix as Unified Diff Patch ONLY.
EOF
)"
python3 <gemini-bridge-script> --cd "." --SESSION_ID "<SESSION_ID>" --PROMPT "$PROMPT"
```

## Prompting Patterns (Paper Mode)

Use `assets/prompt-template.md` as a starter when crafting `--PROMPT`.
Paper-mode templates (top of the file):
- **`literature-map`** — expand candidate papers and adjacent research areas
- **`innovation-candidates`** — generate 3-5 candidate contribution framings
- **`evidence-matrix-gap-check`** — audit evidence coverage gaps

Each template specifies its input sources, output artifact mappings, and constraints.

## Advanced Flags
- `--sandbox`: Run Gemini in sandbox mode.
- `--model <name>`: Override the default Gemini model.
- `--return-all-messages`: Include all raw messages (tool calls, traces) in output JSON.
- `--use-user-home`: Reuse your normal home (and existing `~/.gemini` login) for this run.
- `--prefer-oauth`: Unset `GEMINI_API_KEY`/`GOOGLE_API_KEY` so OAuth creds can be used (if present in the selected home).
- `--seed-user-auth`: Copy OAuth/settings files from your `~/.gemini` into `<repo>/.gemini_cli_home/.gemini/` (avoids `--use-user-home` hangs).
- `--fake-responses <path.jsonl>`: Offline deterministic run using Gemini CLI fake responses (for smoke tests).

- **De-AI polish（反AI味，强制）**：正文/成稿定稿前必读 `cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md` 的 `<de_ai_polish>` 段（工程/质检语汇泄漏、模板开头、AI 过渡词；中英文正文同样适用），并按其执行改写。

## Verification
- Cross-check both collaborators: use the `check-collaborators` skill
- Smoke-test the bridge: `python3 <gemini-bridge-script> --help`

## References
- `../../_shared/collaboration-base.md` (shared rules)
- `assets/prompt-template.md` (prompt patterns)
- `references/shell-quoting.md` (shell quoting/backticks)
