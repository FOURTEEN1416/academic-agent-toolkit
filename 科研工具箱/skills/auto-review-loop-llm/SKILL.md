---
name: auto-review-loop-llm
description: Autonomous research review loop using any OpenAI-compatible LLM API. Configure reviewer via MH Agent settings page or environment variables. Trigger with "auto review loop llm" or "llm review".
argument-hint: [topic-or-scope]
allowed-tools: Bash(*), Read, Grep, Glob, Write, Edit, Agent, Skill
---

# Auto Review Loop (Generic LLM): Autonomous Research Improvement

Autonomously iterate: review → implement fixes → re-review, until the external reviewer gives a positive assessment or MAX_ROUNDS is reached.

## Context: $ARGUMENTS

## Constants

- MAX_ROUNDS = 4
- POSITIVE_THRESHOLD: score >= 6/10, or verdict contains "accept", "sufficient", "ready for submission"
- REVIEW_DOC: `AUTO_REVIEW.md` in project root (cumulative log)
- REVIEWER_MODEL: the configured reviewer model, invoked via `reviewer_client.py` script

## LLM Configuration

This skill uses **any OpenAI-compatible API** for external review via `reviewer_client.py`.

The reviewer model is configured by the user in the MH Agent settings page (reviewer API Key / Base URL / Model ID). These are injected as environment variables (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `REVIEWER_MODEL_ID`) automatically.

### Supported Providers

| Provider | Base URL | Model |
|----------|----------|-------|
| **OpenAI** | `https://api.openai.com/v1` | `gpt-4o`, `o3` |
| **DeepSeek** | `https://api.deepseek.com/v1` | `deepseek-chat`, `deepseek-reasoner` |
| **MiniMax** | `https://api.minimax.chat/v1` | `MiniMax-M2.5` |
| **Kimi (Moonshot)** | `https://api.moonshot.cn/v1` | `moonshot-v1-8k`, `moonshot-v1-32k` |
| **ZhiPu (GLM)** | `https://open.bigmodel.cn/api/paas/v4` | `glm-4`, `glm-4-plus` |
| **SiliconFlow** | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-72B-Instruct` |
| **阿里云百炼** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-max` |
| **零一万物** | `https://api.lingyiwanwu.com/v1` | `yi-large` |

## State Persistence (Compact Recovery)

Persist state to `REVIEW_STATE.json` after each round:

```json
{
  "round": 2,
  "status": "in_progress",
  "last_score": 5.0,
  "last_verdict": "not ready",
  "pending_experiments": [],
  "timestamp": "2026-03-15T10:00:00"
}
```

**Write this file at the end of every Phase E** (after documenting the round).

**On completion**, set `"status": "completed"`.

## Workflow

### Initialization

1. **Check `REVIEW_STATE.json`** for recovery
2. Read project context and prior reviews
3. Initialize round counter

### Loop (up to MAX_ROUNDS)

#### Phase A: Review

Send comprehensive context to the external reviewer via `reviewer_client.py`.

**If the reviewer script fails (API key not configured)**: perform the review yourself using your own critical analysis capabilities. Act as a senior ML reviewer (NeurIPS/ICML level) and score the work honestly. The loop can still function without external review, though cross-model review is preferred for objectivity.

When the reviewer script is available, use:

```bash
cat << 'REVIEW_EOF' > _review_prompt.txt
[Round N/MAX_ROUNDS of autonomous review loop]

[Full research context: claims, methods, results, known weaknesses]
[Changes since last round, if any]

Please act as a senior ML reviewer (NeurIPS/ICML level).

1. Score this work 1-10 for a top venue
2. List remaining critical weaknesses (ranked by severity)
3. For each weakness, specify the MINIMUM fix (experiment, analysis, or reframing)
4. State clearly: is this READY for submission? Yes/No/Almost

Be brutally honest. If the work is ready, say so clearly.
REVIEW_EOF
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _review_prompt.txt --thread-file _reviewer_thread.json
```

If this is round 2+, use the same `_reviewer_thread.json` to maintain conversation context.

#### Phase B: Parse Assessment

**CRITICAL: Save the FULL raw response** verbatim. Then extract:
- **Score** (numeric 1-10)
- **Verdict** ("ready" / "almost" / "not ready")
- **Action items** (ranked list of fixes)

**STOP**: If score >= 6 AND verdict contains "ready/almost"

#### Phase C: Implement Fixes

Priority: metric additions > reframing > new experiments

#### Phase D: Wait for Results

Monitor remote experiments

#### Phase E: Document Round

Append to `AUTO_REVIEW.md`:

```markdown
## Round N (timestamp)

### Assessment (Summary)
- Score: X/10
- Verdict: [ready/almost/not ready]
- Key criticisms: [bullet list]

### Reviewer Raw Response

<details>
<summary>Click to expand full reviewer response</summary>

[Paste the COMPLETE raw response here — verbatim, unedited.]

</details>

### Actions Taken
- [what was implemented/changed]

### Results
- [experiment outcomes, if any]

### Status
- [continuing to round N+1 / stopping]
```

**Write `REVIEW_STATE.json`** with current state.

### Termination

1. Set `REVIEW_STATE.json` status to "completed"
2. Write final summary

## Key Rules

⛔ **File writing strategy (prevent both failure modes):**
- For short content (<150 lines): use the **Write tool** directly (atomic, reliable)
- For long content (>150 lines): use **Write** for the first section (ensures file exists on disk), then append remaining sections with `cat << 'EOF' >> NARRATIVE_REPORT.md`
- **NEVER `end_turn` without producing `NARRATIVE_REPORT.md`** — even if upstream steps had issues, write what you have

⛔ **MUST run output verification before ending**:
```bash
PASS=true
[ -f NARRATIVE_REPORT.md ] && SZ=$(wc -c < NARRATIVE_REPORT.md) || SZ=0
if [ "$SZ" -ge 500 ]; then
    echo "✅ NARRATIVE_REPORT.md ($SZ bytes)"
else
    echo "❌ NARRATIVE_REPORT.md missing or too small ($SZ bytes) — write it NOW before ending"
    PASS=false
fi
[ "$PASS" != true ] && echo "⛔ Verification failed — must produce output before ending step"
```

- ALWAYS use the same `_reviewer_thread.json` across rounds to maintain conversation context
- Be honest about weaknesses
- Implement fixes BEFORE re-reviewing
- Document everything
- Include previous context in round 2+ prompts

## Prompt Template for Round 2+

```bash
cat << 'REVIEW_EOF' > _review_prompt.txt
[Round N/MAX_ROUNDS of autonomous review loop]

## Previous Review Summary (Round N-1)
- Previous Score: X/10
- Previous Verdict: [ready/almost/not ready]
- Previous Key Weaknesses: [list]

## Changes Since Last Review
1. [Action 1]: [result]
2. [Action 2]: [result]

## Updated Results
[paste updated metrics/tables]

Please re-score and re-assess:
1. Score this work 1-10 for a top venue
2. List remaining critical weaknesses (ranked by severity)
3. For each weakness, specify the MINIMUM fix
4. State clearly: is this READY for submission? Yes/No/Almost

Be brutally honest. If the work is ready, say so clearly.
REVIEW_EOF
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _review_prompt.txt --thread-file _reviewer_thread.json
```
