---
name: auto-review-loop
description: Autonomous multi-round research review loop. Repeatedly reviews via external reviewer script, implements fixes, and re-reviews until positive assessment or max rounds reached. Use when user says "auto review loop", "review until it passes", or wants autonomous iterative improvement.
argument-hint: [topic-or-scope]
allowed-tools: Bash(*), Read, Grep, Glob, Write, Edit, Agent, Skill
---

# Auto Review Loop: Autonomous Research Improvement

Autonomously iterate: review → implement fixes → re-review, until the external reviewer gives a positive assessment or MAX_ROUNDS is reached.

## Context: $ARGUMENTS

## ⛔ Output Mode (read first, before anything else)

The orchestrator may inject one of two notice blocks into `CLAUDE.md`:

| Block name | Output mode | LaTeX compile? | Final artefact |
|---|---|---|---|
| `AUTO_REVIEW_DOCX_MODE` | docx | **No** | `NARRATIVE_REPORT.md` (will be auto-converted to `.docx` by a downstream step) |
| `AUTO_REVIEW_PDF_MODE` | pdf | Yes, but **only if `paper/main.tex` exists** | `paper/main.pdf` if .tex provided, else `NARRATIVE_REPORT.md` |
| (neither block present) | markdown (default) | No | `NARRATIVE_REPORT.md` |

**Behavior rules:**

1. If `AUTO_REVIEW_DOCX_MODE` is in CLAUDE.md:
   - Skip every `xelatex` / `pdflatex` / `bibtex` invocation in this skill (Phase D2, Termination step 3).
   - Phase C must produce/edit `paper/draft_v<round>.md` (markdown only) — never write `.tex` files.
   - Termination step 3 reduces to: `cp paper/draft_vN.md NARRATIVE_REPORT.md`.

2. If `AUTO_REVIEW_PDF_MODE` is in CLAUDE.md:
   - Run LaTeX compile **only** if `paper/main.tex` already exists.
   - Otherwise behave like markdown mode and warn the user in `NARRATIVE_REPORT.md` that LaTeX source was missing.

3. Default (markdown mode): the existing flow applies, but treat `paper/main.pdf` compile blocks as **best-effort, fail-soft** — do not abort the whole loop just because there is no `.tex` source.

## Constants

- MAX_ROUNDS = 4
- POSITIVE_THRESHOLD: score >= 6/10, or verdict contains "accept", "sufficient", "ready for submission"
- REVIEW_DOC: `AUTO_REVIEW.md` in project root (cumulative log)
- REVIEWER_MODEL: the configured reviewer model, invoked via `reviewer_client.py` script
- **HUMAN_CHECKPOINT = false** — When `true`, pause after each round's review (Phase B) and present the score + weaknesses to the user. Wait for user input before proceeding to Phase C. The user can: approve the suggested fixes, provide custom modification instructions, skip specific fixes, or stop the loop early. When `false` (default), the loop runs fully autonomously.

> 💡 Override: `/auto-review-loop "topic" — human checkpoint: true`

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
   - If it does not exist: **fresh start** (normal case, identical to behavior before this feature existed)
   - If it exists AND `status` is `"completed"`: **fresh start** (previous loop finished normally)
   - If it exists AND `status` is `"in_progress"` AND `timestamp` is older than 24 hours: **fresh start** (stale state from a killed/abandoned run — delete the file and start over)
   - If it exists AND `status` is `"in_progress"` AND `timestamp` is within 24 hours: **resume**
     - Read the state file to recover `round`, `last_score`, `pending_experiments`
     - Read `AUTO_REVIEW.md` to restore full context of prior rounds
     - If `pending_experiments` is non-empty, check if they have completed (e.g., check screen sessions)
     - Resume from the next round (round = saved round + 1)
     - Log: "Recovered from context compaction. Resuming at Round N."
2. Read project narrative documents, memory files, and any prior review documents
3. Read recent experiment results — **explicitly check these files in order**:
   - `experiment_results.md` (from experiment-bridge, contains structured results summary)
   - `figures/experiment_data.json` (consolidated raw experiment data)
   - `RESULTS.md` (from comp-code, if competition workflow)
   - Output directories: `results/`, `outputs/`, `logs/`
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

If this is round 2+, use the same `_reviewer_thread.json` to maintain conversation context (对话历史通过 `_reviewer_thread.json` 自动保存).

#### Phase B: Parse Assessment

**CRITICAL: Save the FULL raw response** from the external reviewer verbatim (store in a variable for Phase E). Do NOT discard or summarize — the raw text is the primary record.

Then extract structured fields:
- **Score** (numeric 1-10)
- **Verdict** ("ready" / "almost" / "not ready")
- **Action items** (ranked list of fixes)

**STOP CONDITION**: If score >= 6 AND verdict contains "ready" or "almost" → stop loop, document final state.

#### Human Checkpoint (if enabled)

**Skip this step entirely if `HUMAN_CHECKPOINT = false`.**

When `HUMAN_CHECKPOINT = true`, present the review results. In interactive mode, wait for user input. **In non-interactive mode (claude -p), treat as "go" and proceed with all suggested fixes automatically. Log: "HUMAN_CHECKPOINT: non-interactive mode, auto-proceeding with all fixes."**

```
📋 Round N/MAX_ROUNDS review complete.

Score: X/10 — [verdict]
Top weaknesses:
1. [weakness 1]
2. [weakness 2]
3. [weakness 3]

Suggested fixes:
1. [fix 1]
2. [fix 2]
3. [fix 3]

Options:
- Reply "go" or "continue" → implement all suggested fixes
- Reply with custom instructions → implement your modifications instead
- Reply "skip 2" → skip fix #2, implement the rest
- Reply "stop" → end the loop, document current state
```

Wait for the user's response. Parse their input:
- **Approval** ("go", "continue", "ok", "proceed"): proceed to Phase C with all suggested fixes
- **Custom instructions** (any other text): treat as additional/replacement guidance for Phase C. Merge with reviewer suggestions where appropriate
- **Skip specific fixes** ("skip 1,3"): remove those fixes from the action list
- **Stop** ("stop", "enough", "done"): terminate the loop, jump to Termination

#### Feishu Notification (if configured)

After parsing the score, check if `~/.claude/feishu.json` exists and mode is not `"off"`:
- Send a `review_scored` notification: "Round N: X/10 — [verdict]" with top 3 weaknesses
- If **HUMAN_CHECKPOINT=true** and verdict is "almost": send as checkpoint, wait for user reply on whether to continue or stop. In non-interactive mode (claude -p), auto-continue.
- If config absent or mode off: skip entirely (no-op)

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

##### ⛔ 新增 / 修改图表时的图表规范铁律

如果 Phase C 的某个 action item **要新增、修改、补全图表**（如 reviewer 反馈"缺消融实验图"/"散点图配色不可读"），**先读图表规范再写代码**，否则新图风格会跟前面步骤已生成的图不一致：

```
Read _utils/figure_style_guide.md            # 配色方案 + 选图决策表 + 反模式
Read _utils/figure_recipes_<type>.md         # 按论文类型选: academic / competition / empirical / advanced / basic
                                             # _utils/get_recipe.py <type> <id> 提取完整配方代码
```

写图代码必须做到的：

- 顶部统一初始化：`from _utils.plot_utils import setup_style, save_fig, PALETTE; setup_style()`
- **不要硬编码颜色**, 用 `PALETTE[0]` / `PALETTE[1]` 等; 不要 `plt.title()`
- 文件名沿用前面 paper-figure 步骤的命名规范 (`figures/fig_*.png` + `figures/fig_*.pdf`)
- 跟既有图保持同一套配色方案（看 `figures/fig_*.png` 已有的颜色, 或读 `figure_style_guide.md` 选定方案后保持一致）
- 写完跑一遍 `bash _utils/figure_check.sh` 自检 (anti-pattern 扫描)

如果 reviewer 只让"加一张图", 优先看现有 `figures/fig_*.png` 的配色取色, 别自己随便挑——风格漂移会让审稿人感觉"补丁感强"。

#### Phase D: Wait for Results

If experiments were launched:
- Monitor remote sessions for completion
- Collect results from output files and logs

#### Phase D2: Recompile + Quality Check

**⛔ MANDATORY after every round of fixes** — but the action depends on the output mode set in the preamble at the top of this skill:

| Mode (from CLAUDE.md) | Action |
|---|---|
| `AUTO_REVIEW_DOCX_MODE` block present | **Skip** the LaTeX compile entirely. Just sanity-check `paper/draft_v<round>.md` (line count, fenced-code balance, broken refs). |
| `AUTO_REVIEW_PDF_MODE` block present + `paper/main.tex` exists | Run the full LaTeX compile chain below. |
| `AUTO_REVIEW_PDF_MODE` block present + no `paper/main.tex` | Skip compile, fall back to markdown sanity check. |
| Neither block (default markdown) | Try compile only if `paper/main.tex` exists; otherwise skip silently. |

If skipping, log: `[Phase D2] Skipping LaTeX compile (mode=<mode>)`.

If compiling, follow the standard 4-step LaTeX chain below:

1. **Pre-compile cleanup**: Run `compile_utils.sh` to auto-fix common issues:
```bash
if [ -f "_utils/compile_utils.sh" ]; then
    bash _utils/compile_utils.sh paper/
elif [ -f "skills/shared-scripts/compile_utils.sh" ]; then
    bash skills/shared-scripts/compile_utils.sh paper/
fi
```

2. **Compile** (auto-detect engine):
```bash
cd paper/
# Detect engine
if grep -q 'ctex\|xelatex\|xeCJK\|fontspec' main.tex 2>/dev/null; then
    ENGINE=xelatex
else
    ENGINE=pdflatex
fi
$ENGINE -interaction=nonstopmode main.tex
bibtex main 2>/dev/null
$ENGINE -interaction=nonstopmode main.tex
$ENGINE -interaction=nonstopmode main.tex
cd ..
```

3. **Post-compile check**: Run `compile_check.sh` and `writing_check.sh`:
```bash
bash _utils/compile_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_check.sh paper/ 2>/dev/null
bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/ 2>/dev/null
```

4. **Verify PDF**: Confirm `paper/main.pdf` exists and is non-trivial (>100KB):
```bash
if [ -f paper/main.pdf ] && [ $(wc -c < paper/main.pdf) -gt 100000 ]; then
    echo "✅ PDF compiled successfully ($(wc -c < paper/main.pdf) bytes)"
    cp paper/main.pdf "paper/main_round${ROUND}.pdf"
else
    echo "⛔ PDF compilation failed — fix errors before proceeding"
fi
```

If compilation fails, fix the LaTeX errors (check `paper/main.log`) and recompile before moving to Phase E. Do NOT proceed with a broken PDF.

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
3. **Final compile + quality gate** (gated by output mode, see preamble):

   - **Mode = `AUTO_REVIEW_DOCX_MODE`**: skip the LaTeX block entirely. Run only:
     ```bash
     # Promote the latest markdown draft to the canonical name
     LAST=$(ls paper/draft_v*.md 2>/dev/null | sort -V | tail -1)
     [ -n "$LAST" ] && cp "$LAST" NARRATIVE_REPORT.md
     [ -f NARRATIVE_REPORT.md ] && echo "✅ Final markdown: $(wc -c < NARRATIVE_REPORT.md) bytes" || echo "⛔ NARRATIVE_REPORT.md missing"
     ```
     Do **not** call xelatex/pdflatex. The downstream `docx-export` step converts `NARRATIVE_REPORT.md` to `NARRATIVE_REPORT.docx`.

   - **Mode = `AUTO_REVIEW_PDF_MODE`** with `paper/main.tex` present: run the LaTeX block below.

   - **Mode = `AUTO_REVIEW_PDF_MODE`** without `paper/main.tex`: skip the LaTeX block, fall back to the markdown promote logic above, and append a note in `AUTO_REVIEW.md`: "⚠ PDF requested but no LaTeX source found, output is markdown only."

   - **Default markdown / no mode block**: try LaTeX only if `paper/main.tex` exists; otherwise use markdown promote logic.

   LaTeX compile block (used when applicable):
   ```bash
   # Pre-compile cleanup
   bash _utils/compile_utils.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_utils.sh paper/ 2>/dev/null
   # Compile
   cd paper/
   ENGINE=pdflatex
   grep -q 'ctex\|xelatex\|xeCJK\|fontspec' main.tex 2>/dev/null && ENGINE=xelatex
   $ENGINE -interaction=nonstopmode main.tex
   bibtex main 2>/dev/null
   $ENGINE -interaction=nonstopmode main.tex
   $ENGINE -interaction=nonstopmode main.tex
   cd ..
   # Post-compile check
   bash _utils/compile_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_check.sh paper/ 2>/dev/null
   bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/ 2>/dev/null
   # Verify
   [ -f paper/main.pdf ] && echo "✅ Final PDF: $(wc -c < paper/main.pdf) bytes" || echo "⛔ Final PDF missing"
   ```
   **⛔ Only enforce the "PDF >100KB or fix compile errors" gate when actually compiling LaTeX. In docx/markdown mode, this gate does not apply.**
4. **Write `NARRATIVE_REPORT.md`** in the project root — a comprehensive research narrative document containing:
   - Problem description and motivation
   - Methodology overview
   - Experimental setup and results (with key metrics from collected data)
   - Claims-evidence mapping (which experiments support which claims)
   - Known limitations and remaining weaknesses
   - This document serves as the primary input for `/paper-plan` and `/paper-write` in Workflow 3.
4. Update project notes with conclusions
5. **Write method/pipeline description** to `AUTO_REVIEW.md` under a `## Method Description` section — a concise 1-2 paragraph description of the final method, its architecture, and data flow. This serves as input for `/paper-illustration` in Workflow 3 (so it can generate architecture diagrams automatically).
6. If stopped at max rounds without positive assessment:
   - List remaining blockers
   - Estimate effort needed for each
   - Suggest whether to continue manually or pivot
7. **Feishu notification** (if configured): Send `pipeline_done` with final score progression table

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
- 对话历史通过 `_reviewer_thread.json` 自动保存
- Be honest — include negative results and failed experiments
- Do NOT hide weaknesses to game a positive score
- Implement fixes BEFORE re-reviewing (don't just promise to fix)
- If an experiment takes > 30 minutes, launch it and continue with other fixes while waiting
- Document EVERYTHING — the review log should be self-contained
- Update project notes after each round, not just at the end

## Prompt Template for Round 2+

```bash
cat << 'REVIEW_EOF' > _review_prompt.txt
[Round N update]

Since your last review, we have:
1. [Action 1]: [result]
2. [Action 2]: [result]
3. [Action 3]: [result]

Updated results table:
[paste metrics]

Please re-score and re-assess. Are the remaining concerns addressed?
Same format: Score, Verdict, Remaining Weaknesses, Minimum Fixes.
REVIEW_EOF
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _review_prompt.txt --thread-file _reviewer_thread.json
```
