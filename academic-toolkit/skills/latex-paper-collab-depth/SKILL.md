---
name: latex-paper-collab-depth
description: "Use an external CLI agent as a depth-analysis co-pilot for paper-from-zero. Primary role: claim tree compression and deep evidence analysis (depth over breadth). 只用于逐点深挖/论证收敛；方向发散与选题扩展场景改用 latex-paper-collab-breadth. Optional collaborator, skips when CLI absent."
metadata:
  short-description: Depth co-pilot (external CLI) for paper-from-zero
---


<!--ACAT-ADAPTED: 资产补齐自 yunshenwuchuxun/latex-paper-skills@d0f106108cb0（collaborating-with-claude + _shared），正文未改。溯源见 references/UPSTREAM.md。2026-09-09 专项治理。2026-10-27 宿主叙事中性化（B′ 批遗留）：宿主/产品叙事改写为「外部协作者 CLI（当前示例实现为 claude，可替换）」口径；功能逻辑与参数未动。-->
# Collaborating with an External CLI (Depth Mode)

Use an external CLI collaborator as a **depth-analysis** collaborator for
paper-from-zero, or as a generic code collaborator in fallback mode.
（当前示例实现以 Anthropic `claude` CLI 为例；可按需替换为任意同类协作者 CLI。）

> **协作者定位**：本技能把 claude CLI 当作**外部评审桥协作者**调用（可选增强），不预设执行环境；`claude` 不在 PATH 时跳过该协作者、由当前 Agent 自审降级，不阻断流程。


This skill provides a lightweight bridge script (`scripts/claude_bridge.py`)
that returns structured JSON and supports multi-turn sessions via `SESSION_ID`.

> **Shared rules**: This skill inherits all shared rules from
> `../../_shared/collaboration-base.md` (core rules, candidates-only
> constraint, fallback code-collaboration mode, safety guardrails, and
> collaboration state capsule format).  Only collaborator-CLI-specific
> additions (for the current `claude` example) are listed below.

## When to Use
- contribution-map initial draft needs claim-level stress testing.
- evidence-matrix needs sufficiency audit (does evidence match claim strength?).
- Routing decision (review vs empirical) needs adversarial challenge.
- A specific claim needs deep falsification analysis.
- Fallback: generic code collaboration (analysis, patch, review).

## When NOT to Use
- Broad literature expansion or adjacent-area scanning (use Gemini).
- Generating candidate framing directions (use Gemini).
- Generating `ref.bib` entries or verified citations.
- Tasks requiring breadth exploration rather than depth analysis.

## Collaborator CLI Rules (Current Example: `claude`)
- Always run the bridge script with `--help` first if you are unsure of parameters.
- Prefer file/line references; run the bridge with `--cd` set to the repo root.
  Use `--add-dir` when the collaborator needs access to additional directories.
- For automation, prefer `--SESSION_ID` (resume). Session selectors are mutually
  exclusive: choose one of `--SESSION_ID`, `--continue`, or `--session-id`.
- Ensure the collaborator CLI is logged in before running headless commands
  (for the `claude` example: run `claude` and `/login` once if needed).
- Streamed JSON requires `--verbose`; the bridge enables this automatically.

## Model Selection

The `claude` CLI (current example) supports model aliases, so you can use `--model sonnet` / `--model opus` instead of hard-coding versioned model IDs.

- If you omit `--model`, the driving agent uses its configured default model (see the engine model configuration `engine/modex-core/contest_models.json`; otherwise the current agent's default model applies).
- If you need strict reproducibility, pass a full model name via `--model <full-name>`.
- For `claim-stress-test` and `route-review-vs-empirical` templates, prefer `opus`.
- For `evidence-sufficiency-audit`, `sonnet` is sufficient.

## Quick Start (shell-safe)

If your prompt contains Markdown backticks, use a heredoc; see `references/shell-quoting.md`.

```bash
PROMPT="$(cat <<'EOF'
Review src/auth.py around login() and propose fixes.
OUTPUT: Unified Diff Patch ONLY.
EOF
)"
python3 scripts/claude_bridge.py --cd "." --model sonnet --PROMPT "$PROMPT" --output-format stream-json
```

**Output:** JSON with `success`, `SESSION_ID`, `agent_messages`, and optional `error` / `all_messages`.

## Multi-turn Sessions

```bash
# Start a session
PROMPT="$(cat <<'EOF'
Analyze the bug in foo(). Keep it short.
EOF
)"
python3 scripts/claude_bridge.py --cd "." --PROMPT "$PROMPT" --output-format stream-json

# Continue the same session
PROMPT="$(cat <<'EOF'
Now propose a minimal fix as Unified Diff Patch ONLY.
EOF
)"
python3 scripts/claude_bridge.py --cd "." --SESSION_ID "<SESSION_ID>" --PROMPT "$PROMPT" --output-format stream-json
```

## Prompting Patterns (Paper Mode)

Use `assets/prompt-template.md` as a starter when crafting `--PROMPT`.
Paper-mode templates (top of the file):
- **`claim-stress-test`** — adversarial review of contribution-map (use `--model opus`)
- **`route-review-vs-empirical`** — routing recommendation with adversarial self-challenge (use `--model opus`)
- **`evidence-sufficiency-audit`** — per-claim evidence sufficiency assessment (use `--model sonnet`)

Each template specifies its input sources, output artifact mappings, and constraints.

- **De-AI polish（反AI味，强制）**：正文/成稿定稿前必读 `cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md` 的 `<de_ai_polish>` 段（工程/质检语汇泄漏、模板开头、AI 过渡词；中英文正文同样适用），并按其执行改写。

## Verification
- Cross-check both collaborators: use the `check-collaborators` skill
- Smoke-test the bridge: `python3 scripts/claude_bridge.py --help`
- For session testing: run one prompt with `--output-format stream-json` and confirm JSON contains `success: true` and a `SESSION_ID`.

## References
- `../../_shared/collaboration-base.md` (shared rules)
- `assets/prompt-template.md` (prompt patterns)
- `references/shell-quoting.md` (shell quoting/backticks)
