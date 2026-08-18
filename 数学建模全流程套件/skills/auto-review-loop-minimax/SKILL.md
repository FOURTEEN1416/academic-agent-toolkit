---
name: auto-review-loop-minimax
description: Autonomous multi-round research review loop using MiniMax API. Use when you want to use MiniMax directly for external review. Trigger with "auto review loop minimax" or "minimax review".
argument-hint: [topic-or-scope]
allowed-tools: Bash(*), Read, Grep, Glob, Write, Edit, Agent, Skill
---

# Auto Review Loop (MiniMax Version): Autonomous Research Improvement

Autonomously iterate: review → implement fixes → re-review, until the external reviewer gives a positive assessment or MAX_ROUNDS is reached.

## Context: $ARGUMENTS

## Constants

- MAX_ROUNDS = 4
- POSITIVE_THRESHOLD: score >= 6/10, or verdict contains "accept", "sufficient", "ready for submission"
- REVIEW_DOC: `AUTO_REVIEW.md` in project root (cumulative log)
- REVIEWER_MODEL: the configured reviewer model, invoked via `reviewer_client.py` script

## API Configuration

This skill uses MiniMax (or any backend-configured reviewer model) for external review via `reviewer_client.py`.

The reviewer model is configured by the user in the MH Agent settings page (reviewer API Key / Base URL / Model ID). These are injected as environment variables (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `REVIEWER_MODEL_ID`) automatically.

**Why MiniMax as an alternative?** MiniMax provides a separate review perspective. To use MiniMax specifically, configure the reviewer settings with Base URL `https://api.minimax.chat/v1` and Model ID `MiniMax-M2.5`.

## State Persistence (Compact Recovery)

Long-running loops may hit the context window limit, triggering automatic compaction. To survive this, persist state to `REVIEW_STATE.json` after each round:

```json
{
  "round": 2,
  "status": "in_progress",
  "last_score": 5.0,
  "last_verdict": "not ready",
  "pending_experiments": ["screen_name_1"],
  "timestamp": "2026-03-13T21:00:00"
}
```

**Write this file at the end of every Phase E** (after documenting the round). Overwrite each time — only the latest state matters.

**On completion** (positive assessment or max rounds), set `"status": "completed"` so future invocations don't accidentally resume a finished loop.

## Workflow

### Initialization

1. **Check for `REVIEW_STATE.json`** in project root:
   - If it does not exist: **fresh start** (normal case)
   - If it exists AND `status` is `"completed"`: **fresh start** (previous loop finished normally)
   - If it exists AND `status` is `"in_progress"` AND `timestamp` is older than 24 hours: **fresh start** (stale state from a killed/abandoned run — delete the file and start over)
   - If it exists AND `status` is `"in_progress"` AND `timestamp` is within 24 hours: **resume**
     - Read the state file to recover `round`, `last_score`, `pending_experiments`
     - Read `AUTO_REVIEW.md` to restore full context of prior rounds
     - If `pending_experiments` is non-empty, check if they have completed (e.g., check screen sessions)
     - Resume from the next round (round = saved round + 1)
     - Log: "Recovered from context compaction. Resuming at Round N."
2. Read project narrative documents, memory files, and any prior review documents
3. Read recent experiment results (check output directories, logs)
4. Identify current weaknesses and open TODOs from prior reviews
5. Initialize round counter = 1 (unless recovered from state file)
6. Create/update `AUTO_REVIEW.md` with header and timestamp

### Loop (repeat up to MAX_ROUNDS)

#### Phase A: Review

Send comprehensive context to the external reviewer via `reviewer_client.py`.

**If the reviewer script fails (API key not configured)**: perform the review yourself using your own critical analysis capabilities. Act as a senior ML reviewer (NeurIPS/ICML level) and score the work honestly. The loop can still function without external review, though cross-model review is preferred for objectivity.

When the reviewer script is available, use:

```bash
cat << 'REVIEW_EOF' > _review_prompt.txt
[Round N/MAX_ROUNDS of autonomous review loop]

[Full research context: claims, methods, results, known weaknesses]
[Changes since last round, if any]

Please act as a senior machine learning researcher serving as a reviewer for top-tier conferences like NeurIPS, ICML, and ICLR. Provide rigorous, constructive feedback.

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

**CRITICAL: Save the FULL raw response** from the external reviewer verbatim (store in a variable for Phase E). Do NOT discard or summarize — the raw text is the primary record.

Then extract structured fields:
- **Score** (numeric 1-10)
- **Verdict** ("ready" / "almost" / "not ready")
- **Action items** (ranked list of fixes)

**STOP CONDITION**: If score >= 6 AND verdict contains "ready" or "almost" → stop loop, document final state.

#### Phase C: Implement Fixes (if not stopping)

For each action item (highest priority first):

1. **Code changes**: Write/modify experiment scripts, model code, analysis scripts
2. **Run experiments**: Deploy to GPU server via SSH + screen/tmux
3. **Analysis**: Run evaluation, collect results, update figures/tables
4. **Documentation**: Update project notes and review document

Prioritization rules:
- Skip fixes requiring excessive compute (flag for manual follow-up)
- Skip fixes requiring external data/models not available
- Prefer reframing/analysis over new experiments when both address the concern
- Always implement metric additions (cheap, high impact)

#### Phase D: Wait for Results

If experiments were launched:
- Monitor remote sessions for completion
- Collect results from output files and logs

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

[Paste the COMPLETE raw response from the external reviewer here — verbatim, unedited.
This is the authoritative record. Do NOT truncate or paraphrase.]

</details>

### Actions Taken
- [what was implemented/changed]

### Results
- [experiment outcomes, if any]

### Status
- [continuing to round N+1 / stopping]
```

**Write `REVIEW_STATE.json`** with current round, score, verdict, and any pending experiments.

Increment round counter → back to Phase A.

### Termination

When loop ends (positive assessment or max rounds):

1. Update `REVIEW_STATE.json` with `"status": "completed"`
2. Write final summary to `AUTO_REVIEW.md`
3. Update project notes with conclusions
4. If stopped at max rounds without positive assessment:
   - List remaining blockers
   - Estimate effort needed for each
   - Suggest whether to continue manually or pivot

## Key Rules

⛔ **File writing strategy (prevent both failure modes):**
- For short content (<150 lines): use the **Write tool** directly (atomic, reliable)
- For long content (>150 lines): use **Write** for the first section (ensures file exists on disk), then append remaining sections with `cat << 'EOF' >> AUTO_REVIEW.md`
- **NEVER `end_turn` without producing `AUTO_REVIEW.md`** — even if upstream steps had issues, write what you have

⛔ **MUST run output verification before ending**:
```bash
PASS=true
[ -f AUTO_REVIEW.md ] && SZ=$(wc -c < AUTO_REVIEW.md) || SZ=0
if [ "$SZ" -ge 500 ]; then
    echo "✅ AUTO_REVIEW.md ($SZ bytes)"
else
    echo "❌ AUTO_REVIEW.md missing or too small ($SZ bytes) — write it NOW before ending"
    PASS=false
fi
[ "$PASS" != true ] && echo "⛔ Verification failed — must produce output before ending step"
```

- ALWAYS use the same `_reviewer_thread.json` across rounds to maintain conversation context
- Be honest — include negative results and failed experiments
- Do NOT hide weaknesses to game a positive score
- Implement fixes BEFORE re-reviewing (don't just promise to fix)
- If an experiment takes > 30 minutes, launch it and continue with other fixes while waiting
- Document EVERYTHING — the review log should be self-contained
- Update project notes after each round, not just at the end

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
3. [Action 3]: [result]

## Updated Results
[paste updated metrics/tables]

## Current Research Context
[brief summary of claims, methods, current state]

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
