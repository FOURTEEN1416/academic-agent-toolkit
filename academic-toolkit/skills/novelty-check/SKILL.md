---
name: novelty-check
description: "Verify research idea novelty against recent literature. Use when user says ”查新”, ”novelty check”, ”有没有人做过”, or ”check if done”."
argument-hint: [method-or-idea-description]
allowed-tools: Bash(*), Read, Write, Glob, Grep, WebSearch, WebFetch
---

# Novelty Check Skill

使用当前执行会话完成本步；路径按步骤合同，运行清单和证据由程序生成，模型负责实质成果。

Check whether a proposed method/idea has already been done in the literature: **$ARGUMENTS**

## 检索范围与证据

按任务预算进行新颖性检索，保留真实查询、来源及最接近工作。进度直接汇报，不调用shell打印心跳；工具超时或不可用时说明证据缺口，不能推断“无人做过”。时间预算来自用户任务，不假定宿主五分钟无stdout就强杀。

## Instructions

Given a method description, systematically verify its novelty:

### Phase A: Extract Key Claims
1. Read the user's method description
2. Identify **3 core technical claims** (NOT more) that would need to be novel:
   - What is the method?
   - What problem does it solve?
   - What makes it different from obvious baselines?

Print the claims to stdout before proceeding:
```bash
echo "=== Novelty Check: Extracted 3 core claims ==="
echo "1. [claim 1]"
echo "2. [claim 2]"
echo "3. [claim 3]"
echo "=== Starting literature search ==="
```

### Phase B: Efficient Literature Search

**Search budget: MAX 6 WebSearch calls total + MAX 5 WebFetch calls total.**

Do NOT search every claim with 3 different queries. Instead:

1. **Round 1 — Broad search (2 WebSearch calls):**
   - Combine all claims into 1-2 comprehensive search queries
   - Use specific technical terms: `"[method] [problem] [key technique] site:arxiv.org 2024 2025 2026"`
   - Print progress before each search

2. **Round 2 — Targeted search (2-4 WebSearch calls):**
   - Based on Round 1 results, search for the **closest-looking papers only**
   - Focus on the most novel claim that wasn't already covered
   - Skip this round if Round 1 already found clear overlaps

3. **Read top papers (MAX 5 WebFetch calls):**
   - Only fetch the **top 3-5 most relevant** paper abstracts
   - If WebFetch fails on a URL, **skip immediately** — do NOT retry
   - Prefer arXiv abstract pages (fast) over full PDFs (slow)
   - Print progress: `echo ">>> Reading paper: [title]"`

**If ANY WebSearch or WebFetch call hangs or takes too long:**
- Move on immediately
- Use the results you already have
- A partial search is better than a killed process

### Phase C: Cross-Model Verification (optional, quick)

**Only if `$REVIEWER_SCRIPT` is available AND Phase B completed quickly (< 8 minutes elapsed).**

```bash
echo ">>> Starting cross-model verification..."
# 写入评审 prompt
cat << 'REVIEW_EOF' > _review_prompt.txt
[The proposed method description]
[Top 3-5 papers found in Phase B]
Ask: "Is this method novel? What is the closest prior work? What is the delta?"
REVIEW_EOF

# 调用外部评审模型（设置 30 秒超时）
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
timeout 60 $PYTHON "$REVIEWER_SCRIPT" --prompt-file _review_prompt.txt --thread-file _reviewer_thread.json 2>/dev/null || echo ">>> Reviewer script unavailable or timed out, skipping."
```

**If the reviewer script fails, times out, or is unavailable**, skip immediately. Use your own analysis from Phase B.

### Phase D: Novelty Report

Print progress: `echo ">>> Writing novelty report..."`

Write the report to **`novelty_check_report.md`** in the project root:

```markdown
## Novelty Check Report

### Proposed Method
[1-2 sentence description]

### Core Claims
1. [Claim 1] — Novelty: HIGH/MEDIUM/LOW — Closest: [paper]
2. [Claim 2] — Novelty: HIGH/MEDIUM/LOW — Closest: [paper]
3. [Claim 3] — Novelty: HIGH/MEDIUM/LOW — Closest: [paper]

### Closest Prior Work
| Paper | Year | Venue | Overlap | Key Difference |
|-------|------|-------|---------|----------------|

### Overall Novelty Assessment
- Score: X/10
- Recommendation: PROCEED / PROCEED WITH CAUTION / ABANDON
- Key differentiator: [what makes this unique, if anything]
- Risk: [what a reviewer would cite as prior work]

### Suggested Positioning
[How to frame the contribution to maximize novelty perception]

### Search Summary
- WebSearch calls used: [N]/6
- Papers fetched: [N]/5
- Search completed: YES/PARTIAL
```

## Key Rules

- **⛔ File writing strategy (prevent both failure modes):**
  - novelty_check_report.md is typically only 30-50 lines → **use the Write tool directly (atomic, reliable)**
  - If content is unexpectedly long (>150 lines), Write the first half, then `cat << 'EOF' >> novelty_check_report.md` to append the rest
  - **NEVER end_turn without writing the report** — even if search was incomplete, write what you have (mark as "PARTIAL")
- **NEVER block on network calls** — if a search/fetch fails or is slow, skip it and move on
- **Print progress frequently** — at least every 2 minutes, to prevent inactivity timeout
- Be BRUTALLY honest — false novelty claims waste months of research time
- "Applying X to Y" is NOT novel unless the application reveals surprising insights
- Check both the method AND the experimental setting for novelty
- If the method is not novel but the FINDING would be, say so explicitly
- If search results are limited (network issues), note this in the report and give a conservative assessment

产出结构、存在性和最低完整性由 `finish` 按模板中的 `output_contract` 自动核验；修复返回的具体问题，不复制执行验证脚本。
