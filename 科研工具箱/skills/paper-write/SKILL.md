---
name: paper-write
description: "Draft LaTeX paper section by section from an outline. Use when user says \"write paper\", \"draft LaTeX\", or wants to generate LaTeX content from a paper plan."
argument-hint: [venue-or-section]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch, mcp__codex__codex, mcp__codex__codex-reply
---

# Paper Write: Section-by-Section LaTeX Generation

Draft a LaTeX paper based on: **$ARGUMENTS**

## Constants

- **TARGET_VENUE = `ICLR`** — Supported: ICLR, NeurIPS, ICML. Override via Additional Parameters.
- **MAX_PAGES = 9** — Main body to Conclusion end. Refs/appendix excluded. Body pages must be ≥ MAX_PAGES.
- **ANONYMOUS = true**
- **DBLP_BIBTEX = true** — Fetch real BibTeX from DBLP/CrossRef. Never fabricate.
- **CUSTOM_REQUIREMENTS** — Highest priority.
- **REVIEWER_SCRIPT** — External reviewer script

## Inputs

1. PAPER_PLAN.md — outline with claims-evidence matrix, figure plan
2. NARRATIVE_REPORT.md — research narrative
3. experiment_results.md — structured experiment results (from experiment-bridge)
4. figures/ — PDFs + latex_includes*.tex + experiment_data.json
5. Existing .bib file (or will create)

If no PAPER_PLAN.md, generate minimal outline from available docs.

## Orchestra References (use when needed)

- `../shared-references/writing-principles.md` — story framing, clarity
- `../shared-references/venue-checklists.md` — submission requirements
- `../shared-references/citation-discipline.md` — citation fallback

## Load shared rules

```bash
cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md
```

## ⛔⛔⛔ Output Contract (highest priority, violating fails the step)

**Mandatory output depends on `params.output_format`**:

- **PDF mode (default)**: `paper/main.tex` (template-based, ≥ 5KB) + `paper/sections/*.tex` (each ≥ 500 chars) + `paper/references.bib`
- **docx mode (user chose Word)**: `paper/main.md` (**single file** with complete paper, ≥ 5KB). **Do NOT create paper/main.tex**

⛔ **Detect current mode**:
```bash
grep -q "Word（.docx）\|docx mode\|output_format.*docx" CLAUDE.md && echo "MODE=docx" || echo "MODE=pdf"
```

⛔ **MUST run output verification before ending the step**:
```bash
echo "=== Output verification (must be all ✅) ==="
MODE=$(grep -q "Word（.docx）\|docx mode" CLAUDE.md 2>/dev/null && echo docx || echo pdf)
echo "MODE: $MODE"
PASS=true
if [ "$MODE" = "docx" ]; then
    [ -f paper/main.md ] && SZ=$(wc -c < paper/main.md) || SZ=0
    [ "$SZ" -ge 5120 ] && echo "✅ paper/main.md ($SZ bytes)" || { echo "❌ paper/main.md missing or too small"; PASS=false; }
else
    [ -f paper/main.tex ] && SZ=$(wc -c < paper/main.tex) || SZ=0
    [ "$SZ" -ge 5120 ] && echo "✅ paper/main.tex ($SZ bytes)" || { echo "❌ paper/main.tex missing or too small"; PASS=false; }
    SECT_COUNT=$(ls paper/sections/*.tex 2>/dev/null | wc -l)
    [ "$SECT_COUNT" -ge 3 ] && echo "✅ sections ($SECT_COUNT)" || { echo "❌ too few sections"; PASS=false; }
fi
[ "$PASS" != true ] && echo "⛔ Output verification FAILED — must complete missing artifacts before ending"
```
**If verification fails, complete the missing files instead of exiting**.



## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：模板来源哈希、BibTeX 条目数、引用格式。

## Workflow
### Step 0: Backup + resume check + upstream validation

**⛔ 上游输出完整性检查（写论文前必做）：**
```bash
echo "=== Upstream outputs validation ==="
UPSTREAM_OK=true

# 1. 核心文件是否存在
for f in PAPER_PLAN.md RESULTS.md; do
    if [ -f "$f" ]; then
        sz=$(wc -c < "$f")
        echo "✅ $f ($sz chars)"
        [ "$sz" -lt 500 ] && { echo "  ⚠ File too small, content may be incomplete"; UPSTREAM_OK=false; }
    else
        echo "⚠ $f not found (paper-write will use minimal outline)"
    fi
done

# 2. 实验数据文件
[ -f figures/all_results.json ] && echo "✅ figures/all_results.json" || echo "⚠ No all_results.json — numerical values may be inaccurate"
[ -f experiment_results.md ] && echo "✅ experiment_results.md" || echo "  (no experiment_results.md, will rely on RESULTS.md)"

# 3. 图表文件
PDF_COUNT=$(ls figures/*.pdf 2>/dev/null | wc -l)
echo "Figures: $PDF_COUNT PDFs"
[ "$PDF_COUNT" -eq 0 ] && echo "⚠ No PDF figures — paper will lack visual content"

# 4. latex_includes.tex 是否存在
[ -f figures/latex_includes.tex ] && echo "✅ figures/latex_includes.tex" || echo "⚠ No latex_includes.tex — figure embedding code missing"

# 5. Claims-Evidence 匹配检查（如果 PAPER_PLAN.md 有 matrix）
if [ -f PAPER_PLAN.md ]; then
    CLAIM_ROWS=$(grep -c '|.*|.*|' PAPER_PLAN.md 2>/dev/null || echo 0)
    [ "$CLAIM_ROWS" -gt 2 ] && echo "✅ Claims-Evidence matrix in PAPER_PLAN.md ($CLAIM_ROWS rows)" || echo "  (no claims-evidence matrix detected)"
fi

echo "=== Validation complete ==="
$UPSTREAM_OK || echo "⚠ Some upstream files incomplete — proceeding anyway but results may be less reliable"
```

Back up existing `paper/` to `paper-backup-{timestamp}/`. Clean stale section files. Check for incomplete sections:
```bash
echo "=== Resume check ==="
if [ -d "paper/sections" ]; then
    for f in paper/sections/*.tex; do
        [ -f "$f" ] || continue
        chars=$(wc -c < "$f")
        if [ "$chars" -lt 500 ]; then
            echo "⚠ Placeholder: $(basename $f) ($chars chars) — needs writing"
        else
            echo "✅ Complete: $(basename $f) ($chars chars)"
        fi
    done
fi
```
Resume: only write placeholder sections (<500 chars or contains "placeholder"/"TODO"), skip completed ones (>2000 chars). See `<resume_strategy>` in writing_rules.md.

### Step 1: Initialize

Create paper/, copy venue template, generate math_commands.tex (paper-specific commands only), create section files.

### Step 1.5: Figure inventory

Before writing any section, build a complete inventory of available figures:

```bash
echo "=== Available PDF figures ==="
ls -la figures/*.pdf 2>/dev/null || echo "No PDF figures found"
echo ""
echo "=== latex_includes.tex content (figure→PDF mapping) ==="
cat figures/latex_includes.tex 2>/dev/null || echo "No latex_includes.tex"
echo ""
echo "=== TikZ diagrams ==="
# TikZ 图由 paper-figure-drawio 生成为 figures/tikz_diagrams.tex → 编译成 figures/tikz_diagrams.pdf
# （历史命名可能是 tikz_architecture_examples.tex，一并兼容）。
# TikZ 的 PDF 已经由 paper-figure-drawio 写进 latex_includes.tex，按 latex_includes.tex 嵌入即可。
ls -la figures/tikz_*.pdf figures/tikz_*.tex 2>/dev/null || echo "No TikZ diagrams"
grep -l 'tikz_' figures/latex_includes.tex >/dev/null 2>&1 && echo "→ TikZ 已在 latex_includes.tex 中，按其图块嵌入" || true
```

**⛔ Build a FIGURE EMBEDDING PLAN before writing any section:**
```
FIGURE EMBEDDING PLAN:
1. fig_main_results.pdf → Experiments section
2. fig_ablation.pdf → Experiments section
3. fig_training_curves.pdf → Experiments section
4. TABLE_main.tex (PDF mode) / TABLE_main.md (Word/docx mode) → Experiments section
5. tikz_diagrams.pdf (geometry/algorithm/architecture TikZ, from latex_includes.tex) → Method section
```
> Tables: PDF mode embeds `\input{figures/TABLE_*.tex}`; Word/docx mode embeds Markdown tables via `cat figures/TABLE_*.md`. Embed every TABLE file that exists — match the format to the output mode.
- **Must use figure blocks from `latex_includes.tex`**, not write `\includegraphics` from scratch
- **TikZ diagrams must be embedded** into corresponding sections — every `tikz_*.pdf` referenced in `latex_includes.tex` must appear in some section (paper-figure-drawio already added include blocks for them)
- **Read experiment_results.md / RESULTS.md for exact numbers** — do not invent results

**⛔ CRITICAL: ALL numerical results in the paper MUST come from `figures/all_results.json` or `RESULTS.md`.**

**⛔ NEVER `cat figures/*_results.json`.** These result files often contain full-precision time-series arrays (tens of MB / hundreds of thousands of lines); reading them whole blows up the context — local models fail outright, and GPT-via-transit chokes on protocol translation of the oversized payload and stalls on repeated `api_retry`. **The paper text only uses scalar values; the giant arrays are for figures, not prose.** Before writing any results/experiments section, run the `summarize` script below for a KB-level overview (scalars shown verbatim — zero precision loss — only big arrays compressed to "length + range + first 3 samples"):
```bash
[ -f RESULTS.md ] && cat RESULTS.md
[ -f experiment_results.md ] && cat experiment_results.md
python3 - <<'PY'
import json, os, glob
def summarize(v, depth=0):
    if isinstance(v, list):
        n=len(v); nums=[x for x in v if isinstance(x,(int,float))]
        if nums: return f'list[{n}] range=[{min(nums):.4g},{max(nums):.4g}] sample={v[:3]}'
        if v and isinstance(v[0], (list,dict)): return f'list[{n}] of {type(v[0]).__name__}, first_shape={len(v[0]) if hasattr(v[0],"__len__") else "?"}'
        return f'list[{n}] sample={str(v[:3])[:80]}'
    if isinstance(v, dict) and depth<2:
        return 'dict{'+', '.join(f'{k}: {summarize(x,depth+1)}' for k,x in list(v.items())[:6])+'}'
    return f'{type(v).__name__}={str(v)[:60]}'
for f in sorted(glob.glob('figures/*_results.json')):
    sz=os.path.getsize(f); d=json.load(open(f,encoding='utf-8'))
    print(f'\n=== {os.path.basename(f)} ({sz//1024}KB) ===')
    if isinstance(d, dict):
        for k,v in d.items(): print(f'  {k}: {summarize(v)}')
    else: print(f'  {summarize(d)}')
PY
```
Every scalar you need is in `RESULTS.md` / `experiment_results.md` or the range/sample above. If one scalar isn't fully shown, fetch just that value with `python3 -c "import json;d=json.load(open('figures/all_results.json'));print(d['key'])"` — still never read the whole file. When quoting specific numbers (accuracy, RMSE, F1, p-values, speedup ratios, parameter counts, etc.), you MUST copy them verbatim. Do NOT estimate, round, or make up values from LLM memory. A paper with fabricated numbers will fail the final quality gate's numerical consistency check.

**⛔ Claims-Evidence 对照（必须严格遵循规划）：**

Before writing each section, re-read PAPER_PLAN.md's claims-evidence matrix:
```bash
# 提取 PAPER_PLAN.md 中的 claims-evidence 表
grep -A 100 'Claims-Evidence\|claim.*evidence\|claim-evidence' PAPER_PLAN.md 2>/dev/null | head -30
```

Writing discipline:
- Every claim in the paper MUST trace back to a row in the matrix
- Do not add new claims not in the plan (if you discover something, update PAPER_PLAN.md first)
- Do not skip claims that were planned (even negative results should be reported)
- Each claim's numerical evidence must match the value in `figures/all_results.json`

If a planned claim has no evidence in the data, write an honest statement like "preliminary results suggest X, though we leave formal validation to future work" instead of fabricating evidence.

### Step 1.5: Pre-fetch verified reference pool (BEFORE writing any text)

**⛔ This step MUST happen before Step 2. Do NOT write any \citep{} until this pool exists.**

The goal is to build a pool of real, verified papers so that when writing body text, you only cite papers that actually exist.

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
mkdir -p _tmp

# Search for papers in each key topic area of this paper
# (adapt these queries to your specific paper topic)
echo "=== Searching key topic areas ==="

# Extract topic keywords from PAPER_PLAN.md
grep -i 'related\|background\|literature\|baseline\|prior work' PAPER_PLAN.md 2>/dev/null | head -20

# For each major topic/method mentioned in the plan, search for real papers:
# Example queries (REPLACE with your actual topics):
#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "spatial Durbin model digital economy" --max 5
#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "computing infrastructure regional development" --max 5
#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "spatial spillover effect panel data" --max 5
```

After searching, create `_tmp/_verified_refs.txt` with one line per verified paper:
```
key: lesage_2009_spatial_econometrics | title: Introduction to Spatial Econometrics | authors: LeSage, Pace | year: 2009 | match: good
key: elhorst_2014_spatial_panel | title: Spatial Econometrics: From Cross-Sectional Data to Spatial Panels | authors: Elhorst | year: 2014 | match: good
```

**When writing body text in Step 2, ONLY use citation keys from this verified pool.** If you need to cite a paper not in the pool, search for it first and add it to the pool before citing.

**Fallback**: If `scholar_fetch.py` returns no results or `match_label="low"` for a topic, use WebSearch to find the paper on Google Scholar / Semantic Scholar website, then manually verify title + authors + year before adding to the pool.

### Step 2: Write each section

**⛔ CRITICAL: Do NOT write the abstract now.** Skip the abstract section entirely. Write a placeholder `% [Abstract — fill in Step 4.5 after all sections complete]` where the abstract should go. The abstract MUST be written LAST because it needs specific numerical results from all sections. Writing it first = making up numbers.

Come back to fill the abstract in Step 4.5, after all body sections are complete. At that point, read `RESULTS.md` / `experiment_results.md` / `figures/all_results.json` and all `sections/*.tex` to extract the actual numbers.

Writing order: Method → Experiments → Introduction → Related Work → Conclusion (core content first).
Save each section immediately. If approaching output limit, create `% [PLACEHOLDER]` files.

**⛔ Writing style rules:**
- **No `\begin{itemize}` or `\begin{enumerate}` in body text** — bullet lists are the #1 AI writing tell. Use flowing prose with inline numbering "(1)...(2)...(3)..." or transition words "First,...Second,...Finally,...".
- **Each paragraph must have ≥3 sentences.** No 1-2 sentence micro-paragraphs.
- **Consecutive paragraphs must not start with the same phrase.**

Follow all rules from `_utils/writing_rules.md` (interleaving, embedding, LaTeX constraints).

**⛔ Cross-chapter context + figure-data binding (prevents the "two-layers" disconnect):**
- **After finishing each section**, immediately append a 3-5 line card to `_writing_context.md` in the workspace root (core claim / key numbers / newly defined symbols & terms / figures already discussed); **`cat _writing_context.md` before writing the next section** to carry forward prior conclusions, reuse already-defined terms (don't redefine), and keep every metric's number consistent across the paper — see `<chapter_context_card>` in `_utils/writing_rules.md`.
- **Before writing the analysis for any figure/table**, follow `<figure_data_binding>`: read FIGURE_MANIFEST/latex_includes to identify *what quantity the figure plots* → locate its real values in `RESULTS.md`/`figures/all_results.json` → use only those real numbers. **Never guess numbers from the plot's shape/position, never fabricate coordinates.**

For each section, copy the matching figure/table blocks from `figures/latex_includes.tex` (or `figures/*.tex`) into the section file. Path: always `../figures/xxx.pdf` (relative to paper/). Figures use `[H]` float specifier (pinned in place to prevent multi-figure stacking), tables use `[H]`. Post-write check: every `\ref` must have matching `\label`.

Wide tables (≥6 columns or multiple `p{}` columns): wrap with `\resizebox{\textwidth}{!}{...}`.

After each section, check chars:
```bash
chars=$(wc -c < "paper/sections/current_section.tex")
echo "Current section: $chars chars"
# English LaTeX ≈ 2000-2500 chars/page
# If section page budget is 2 pages but only 2000 chars (~1 page), expand immediately
```

<exemplar_depth>
#### Writing depth by venue

**ICLR/NeurIPS/ICML (9 pages main body)**:
- Abstract (0.3p): what → why hard → how → evidence → strongest result. 150-250 words. Self-contained
- Introduction (1.5p): hook → gap → contributions → results preview → hero figure. Front-load the contribution
- Related Work (1-1.5p): organize by category, synthesize not list. Each category: 3-5 papers with method summary + positioning vs this work
- Method (2-2.5p): notation → formulation → algorithm. Every formula has intuition explanation. Key derivation steps not skipped
- Experiments (3-4p): setup → main results table → comparison plots → ablation table → analysis. Every result has 1-2 paragraphs of interpretation (not just "our method outperforms")
- Conclusion (0.5p): rephrase contributions + limitations + future work

**JMLR/TPAMI journal (15-20 pages)**:
- Introduction (2-3p): more thorough literature positioning
- Related Work (2-3p): comprehensive survey by sub-topic
- Method (4-6p): full derivations, proofs, complexity analysis
- Experiments (6-8p): multiple datasets, extensive ablations, qualitative analysis, failure cases
- Conclusion (1p): detailed limitations and future directions
</exemplar_depth>

**Expansion strategies** (not padding — substantive content):
- Formula listed without derivation → add step-by-step derivation with intuition
- Result only says "as shown in Table X" → add 1-2 paragraphs of interpretation (what numbers mean, comparison, reasoning)
- Related work only lists papers → add method summaries and positioning vs this work
- Algorithm only has pseudocode → add explanation of key steps and complexity analysis

#### Section guidelines
- Abstract: what → why hard → how → evidence → strongest result. Self-contained. 150-250 words.
- Introduction: hook → gap → contributions → results preview → hero figure. 1.5 pages. Front-load contribution.
- Related Work: ≥1 full page. Organize by category, synthesize not list.
- Method: notation → formulation → algorithm. 1.5-2 pages.
- Experiments: setup → main results → ablations. 2.5-3 pages. Every claim needs evidence.
- Conclusion: rephrase contributions + limitations + future work. 0.5 pages.

### Step 3: Build bibliography

Follow the `<references_workflow>` in `_utils/writing_rules.md`.
Venue style: natbib (citep/citet). Verify references.bib is non-empty before proceeding.

**⛔ Use the scholar_fetch.py tool for ALL reference retrieval. NEVER fabricate BibTeX from memory.**

**⛔ 引用写法规则：写正文时，citation key 必须包含描述性关键词，格式为 `作者姓_年份_主题关键词`。**
例如：`\citep{wang_2023_supply_chain_resilience}` 而不是 `\citep{wang2023supply}`。
这样 Step 3b 搜索时能用关键词找到正确的论文。如果不确定作者/年份，用 `TODO__` 前缀：`\citep{TODO__digital_economy_spatial_spillover}`。

```bash
# Step 3a: Collect all cited keys and extract search queries
grep -roh '\\cite[tp]*{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null \
  | grep -oP '\{[^}]+\}' | tr -d '{}' | tr ',' '\n' | sed 's/^ *//;s/ *$//' | sort -u > _tmp/_cited_keys.txt
echo "Cited keys: $(wc -l < _tmp/_cited_keys.txt)"
cat _tmp/_cited_keys.txt

# Step 3b: For each cited key, extract descriptive keywords and search
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
while IFS= read -r key; do
    # Convert citation key to search query: replace _ with spaces, remove TODO prefix
    query=$(echo "$key" | sed 's/^TODO__//; s/_/ /g')
    echo "--- Fetching: $key (query: $query) ---"
    $PYTHON "$SCHOLAR_SCRIPT" bibtex "$query" --max 3
    sleep 0.5
done < _tmp/_cited_keys.txt
```

For each result:
1. **Check `match_label`**: if `"good"` → use directly. If `"partial"` → verify title matches your intent. If `"low"` → this is likely the wrong paper, search again with better keywords or use WebSearch.
2. **Check `match_score`**: score < 0.3 means the search result probably doesn't match what you cited. Do NOT blindly use it.
3. Pick the correct paper and copy its `bibtex` field into `paper/references.bib`.
4. Replace the citation key in .tex files with the actual key from the BibTeX entry.
5. If `bibtex_source=auto`, add `% [VERIFY]` above the entry.
6. If `match_label="low"` and no better result found, add `% [LOW_MATCH - verify this is the intended paper]` and use WebSearch as fallback.

### Step 4: De-AI polish

See `<de_ai_polish>` in `_utils/writing_rules.md`.

### Step 4.5: Write Abstract LAST

⛔ **MANDATORY: NOW write the abstract** (replace the placeholder from Step 2).

Read `RESULTS.md` / `experiment_results.md` / `figures/all_results.json` and all `sections/*.tex` first. Extract the actual numerical results (accuracy, F1, p-values, coefficients). Then write the abstract using only those verified numbers — do not invent any value.

Structure: problem → why hard → approach → key result with numbers → implication. 150-250 words, self-contained.

After writing, verify every number in the abstract appears in the body:

```bash
for n in $(grep -oE '[0-9]+\.[0-9]+' paper/sections/0_abstract.tex | sort -u); do
  grep -q "$n" paper/sections/*.tex RESULTS.md 2>/dev/null \
    || echo "⛔ Abstract number $n not found in body — invented?"
done
```

### Step 5: Cross-review

Send draft to external reviewer for feedback before finalizing:

```bash
mkdir -p _tmp
cat << 'REVIEW_EOF' > _tmp/_review_prompt.txt
Please review this academic paper draft. Focus on:
1. Logical flow and argument structure
2. Claim-evidence alignment (every claim has supporting data?)
3. Writing clarity and conciseness
4. Missing content or weak sections
5. Score (1-10) and top 3 actionable improvements

## Paper sections:
REVIEW_EOF
for f in paper/sections/*.tex; do
    [ -f "$f" ] && echo "### $(basename $f)" >> _tmp/_review_prompt.txt && cat "$f" >> _tmp/_review_prompt.txt
done
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _tmp/_review_prompt.txt --thread-file _tmp/_reviewer_thread.json 2>&1 | tee _tmp/_cross_review.txt
```

If reviewer script unavailable, skip this step.

### Step 6: Reverse outline test

Extract topic sentences → read in sequence → check claim coverage → fix gaps.

### Step 7: Final checks

```bash
bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/
```

**Figure embedding verification (must pass before finishing)**:
```bash
echo "=== Figure embedding check ==="
missing=0
# Check every PDF in figures/ is referenced in sections
for pdf in figures/*.pdf; do
    [ -f "$pdf" ] || continue
    bn=$(basename "$pdf")
    if ! grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null; then
        echo "MISSING: $bn not embedded in any section"
        missing=$((missing + 1))
    fi
done
# Check every label in figures/*.tex is in sections
for fig_tex in figures/*.tex; do
    [ -f "$fig_tex" ] || continue
    for lbl in $(grep -oh '\\label{[^}]*}' "$fig_tex" 2>/dev/null); do
        if ! grep -rq "$lbl" paper/sections/*.tex paper/main.tex 2>/dev/null; then
            echo "MISSING: $lbl (from $(basename $fig_tex)) not in any section"
            missing=$((missing + 1))
        fi
    done
done
echo "Total missing: $missing"
```
If any figures are missing, go back and embed them into the appropriate sections before finishing. **⛔ Do NOT finish until missing = 0.**

**Page estimate check**:
```bash
echo "=== Section sizes ==="
total=0
for f in paper/sections/*.tex; do
    chars=$(wc -c < "$f")
    total=$((total + chars))
    echo "  $(basename $f): $chars chars"
done
echo "  Total: $total chars (~$((total / 2200)) pages), Target: ≥ MAX_PAGES pages"
```
If total chars < MAX_PAGES × 2000, expand the thinnest sections before finishing.

## Key Rules

- Large files: Bash heredoc
- No author info — anonymous block
- Complete sections, not outlines
- One file per section
- Every claim cites evidence
- Venue style: natbib (citep/citet)
- Clean bib — only cited entries
- Section count flexible (5-8)
- Backup before overwrite
- Front-load the contribution
- Primary output: `paper/` directory, temp files: `_tmp/`


---

## ⛔ FIGURE_MANIFEST audit (run before finishing — must produce + embed every planned figure)

```bash
echo "=== FIGURE_MANIFEST audit ==="
PLAN_FILE=""
for f in PROBLEM_ANALYSIS.md PAPER_PLAN.md MODELING_REPORT.md TOPIC_PLAN.md; do
  [ -f "$f" ] && grep -q "<!-- BEGIN FIGURE_MANIFEST -->" "$f" && { PLAN_FILE="$f"; break; }
done
if [ -n "$PLAN_FILE" ]; then
    START=$(grep -n "<!-- BEGIN FIGURE_MANIFEST -->" "$PLAN_FILE" | head -1 | cut -d: -f1)
    END=$(grep -n "<!-- END FIGURE_MANIFEST -->" "$PLAN_FILE" | head -1 | cut -d: -f1)
    EXPECTED_FIGS=$(sed -n "${START},${END}p" "$PLAN_FILE" | grep -oE "^[[:space:]]*-[[:space:]]+(fig_[a-zA-Z0-9_]+|tikz_[a-zA-Z0-9_]+)" | sed "s/^[[:space:]]*-[[:space:]]*//")
    manifest_missing=0
    for name in $EXPECTED_FIGS; do
        if ! ls figures/${name}.pdf figures/${name}.png 2>/dev/null | head -1 | grep -q .; then
            echo "❌ MANIFEST: $name file missing"
            manifest_missing=$((manifest_missing + 1))
        elif ! grep -rqE "${name}\.(pdf|png)" paper/sections/ paper/main.tex 2>/dev/null; then
            echo "❌ MANIFEST: $name exists but not referenced in paper"
            manifest_missing=$((manifest_missing + 1))
        fi
    done
    if [ "$manifest_missing" -gt 0 ]; then
        echo "⛔ FIGURE_MANIFEST audit failed ($manifest_missing missing): produce + embed every planned figure before ending"
    else
        echo "✅ FIGURE_MANIFEST fully embedded"
    fi
else
    echo "(no FIGURE_MANIFEST in plan docs, skip audit)"
fi
```

## ⛔ Universal paper-stage audit (shared across all writing steps)

Before finishing writing / compiling, run the universal audit. Works without `PROBLEM_FACTS.json`:

```bash
# Universal paper audit:
#   [13] Conclusion consistency: paper text ↔ results.json (prevent "optimal=X but paper says Y")
#   [14] Event source attribution (prevent "guessing source from variable name")
# Falls back to simplified mode if no PROBLEM_FACTS.json (general academic / course / humanities).
if [ -f _utils/facts_audit.py ]; then
    python3 _utils/facts_audit.py --stage paper 2>&1 | tee -a AUDIT_REPORT.md
    PRC=$?
    if [ "$PRC" = "1" ]; then
        echo "❌ Universal paper-stage audit failed — fix paper text / results.json before finishing"
    fi
fi
```

