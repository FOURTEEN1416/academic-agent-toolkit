---
name: comp-paper-en-docx
description: "Mathematical modeling competition paper in English (MCM/ICM/APMCM) — Word docx mode. docx-mode counterpart of comp-paper-en — keeps COMAP structure but produces paper/main.md only."
argument-hint: [competition-type]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# Competition Paper Writing (English) — docx mode

Write an MCM/ICM/APMCM paper as Markdown for Word export: **$ARGUMENTS**

## ⚡ Fast-mode detection (run first)

```bash
FAST_MODE=0
grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null && FAST_MODE=1
echo "FAST_MODE=$FAST_MODE"
```

**If `FAST_MODE=1` (speed priority):** still MUST produce a complete paper (all sections present, every sub-problem covered, figures embedded per manifest, body pages meet MAX_PAGES, cite real data — no fabrication, pass output verification), but **SKIP** line-by-line number consistency re-checks and repeated polish for minor issues. **If `FAST_MODE=0` (default):** run all consistency checks as usual.

> docx-mode counterpart of `comp-paper-en`. Keeps COMAP/APMCM structure (Summary Sheet, Assumptions, Notations, sub-problem chapters, Sensitivity Analysis, Strengths & Weaknesses) but produces **`paper/main.md`** only.
>
> ⛔ **NEVER produce `.tex` / `.cls` / `.sty` / `.bib`. NEVER use LaTeX commands.**

## Constants

- **COMPETITION** — Default `mcm`
- **MAX_PAGES** — Default 25. Body ≥ MAX_PAGES (~600 words/page in English)
- **CUSTOM_REQUIREMENTS**

## Inputs

1. PROBLEM_ANALYSIS.md, MODELING_REPORT.md, RESULTS.md
2. figures/ — `.png` / `.pdf`
3. code/, figures/all_results.json, figures/problem_*_results.json

## Load shared rules

```bash
cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md
```

## MCM/ICM Paper Structure

```
Summary Sheet (1 page — most important page)
1. Introduction
2. Assumptions and Justifications
3. Notations
4. Model Design and Solution (per sub-problem)
5. Sensitivity Analysis
6. Model Evaluation (Strengths + Weaknesses)
7. Conclusions
References
Appendix A: Code
```

## ⛔⛔⛔ Output Contract (highest priority)

**Single artifact**: `paper/main.md` (UTF-8, ≥ 5KB)

**Never produce**: `.tex` / `.bib` / `.cls` / `.sty` / `.aux` / any LaTeX command.

**Mandatory verification**:
```bash
PASS=true
[ -f paper/main.md ] && SZ=$(wc -c < paper/main.md) || SZ=0
[ "$SZ" -ge 5120 ] && echo "✅ paper/main.md ($SZ)" || { echo "❌ paper/main.md missing"; PASS=false; }

words=$(wc -w < paper/main.md 2>/dev/null || echo 0)
est_pages=$((words / 600))
target_pages="${MAX_PAGES:-25}"
echo "words: $words, est pages: ~$est_pages, target: ≥ $target_pages"
[ "$est_pages" -lt "$((target_pages * 80 / 100))" ] && echo "⚠ below 80% target"

if grep -qE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter|subsection|bibitem|usepackage|documentclass)\{' paper/main.md; then
    echo "❌ LaTeX residue:"
    grep -nE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter|subsection|bibitem|usepackage|documentclass)\{' paper/main.md | head -5
    PASS=false
fi

ls paper/*.tex paper/sections/*.tex 2>/dev/null | head -1 | grep -q . && { echo "❌ .tex files detected"; PASS=false; } || true

[ "$PASS" != true ] && echo "⛔ verification FAILED"
```

## docx-cn-engine markdown conventions

(See paper-write-docx for the full reference.)

- `# Title` (unique, centered cover); `## Section`; `### Subsection`
- `## Summary Sheet` / `## Abstract` triggers centered abstract style
- `## References` triggers hanging-indent for `[N] ...` lines
- Math: `$inline$`, `$$display$$`, append ` (1)` for numbering
- Figures: `![Figure 1: caption](figures/fig.png)`
- Tables: markdown pipe tables (rendered as 3-line academic style)
- Citations: `[1]`, `[1, 2]`, `[1-3]` — never `\cite{}`

## Workflow

### Step 0: Upstream check + resume

```bash
echo "=== Upstream check ==="
for f in PROBLEM_ANALYSIS.md MODELING_REPORT.md RESULTS.md; do
    [ -f "$f" ] && echo "✅ $f ($(wc -c < $f) chars)" || echo "❌ $f missing"
done
[ -f figures/all_results.json ] && echo "✅ figures/all_results.json" || true
PNG_COUNT=$(ls figures/*.png 2>/dev/null | wc -l)
PDF_COUNT=$(ls figures/*.pdf 2>/dev/null | wc -l)
echo "figures: PNG=$PNG_COUNT, PDF=$PDF_COUNT"

if [ -f paper/main.md ]; then
    cp paper/main.md "paper/main-backup-$(date +%s).md.bak"
    echo "Resume mode — backup created"
fi
```

### Step 1: Figure inventory + embedding plan

```bash
ls -la figures/*.png figures/*.pdf 2>/dev/null
ls -la figures/TABLE_*.md 2>/dev/null
cat figures/latex_includes.tex 2>/dev/null  # caption reference only
```

⛔ Build figure embedding plan before writing:
| ID | File | Section | Caption |
|----|------|---------|---------|
| Fig 1 | figures/fig_roadmap.png | 1. Introduction | Figure 1: Solution roadmap |
| Fig 2 | figures/fig_flow_q1.png | 4.1 Sub-problem 1 | Figure 2: Sub-problem 1 algorithm flow |
| ... | ... | ... | ... |

⛔ Only embed figures whose files exist. ⛔ DrawIO figures (roadmap/flow) MUST be embedded into proper sections.

**⛔⛔ Figures must be drawn out by the argument, not stamped with a template sentence (hard rule):**
- Embed every figure in the prose so the argument itself leads into it. The one test that matters: **it reads as a smooth narrative, not as one label slapped on each figure in turn.**
- **✅ Three goals to reach (goals, NOT a sentence template, and NOT a fixed structure to copy for every figure)**: make the reader understand (1) what this figure shows, (2) what earlier point it follows from, (3) what conclusion it supports. How you weave these in — in what order, in what sentence structure — is up to you as the prose dictates: conclusion-then-figure, or phenomenon-then-figure. **What varies is HOW you write (structure, entry angle, order); what does NOT vary is HOW DEEP you go.**
- **⛔⛔ Depth floor — a figure is never an island; the prose around it must flow logically (lead-in from the argument above → coherent explanation → hand-off to what follows), never a bare figure + one flat sentence.** Each figure's prose (lead-in + follow-up combined) must land all three: (1) **reading** — what key phenomenon/structure/trend it reveals (anchor with concrete numbers *when the plot has quantifiable values* — max radius 4.229 m, 7.59% shorter; for purely qualitative figures just state the qualitative feature clearly, **do NOT invent numbers**); (2) **attribution or comparison** — why it looks this way / vs a baseline, other scheme, or prior sub-problem; (3) **inference and linkage** — what it proves, what it leads into next, so the paragraph is a link in the argument chain, not a standalone caption card. A single flat sentence (e.g. "Fig. 24: the spirals join smoothly.") is a failure; so is a figure whose prose has no connection to the surrounding text (delete it and nothing changes = it was an island).
  - **❌ Perfunctory anti-example (forbidden)**: "The arc-length optimization is shown in Fig. 25: multiple starts converge to the same neighborhood, and the optimum stays below the baseline." — one sentence, no numbers, no quantified comparison.
  - **✅ Benchmark example (the fullness to emulate)**: "Fig. 15 shows the collision radius decreasing strictly monotonically as the pitch grows: from 0.4 m to 0.55 m pitch, the radius falls from 7.04 m to 2.289 m; its intersection with the R_t = 4.5 m threshold lands exactly at the critical pitch p_min = 0.448 m. The moderate slope near the intersection indicates a stable inversion and well-conditioned bisection." — numbers, trend, threshold crossing, and inference all present.
- **⛔⛔ No formulaic sentence patterns (the core problem being fixed here)**: never write every figure with the same skeleton, especially the "[figure type] (Fig. N) + verb + one-line conclusion" opener (e.g. "The waterfall chart (Fig. 33) decomposes…", "The radar chart (Fig. 34) compares…", "The heatmap (Fig. 35) shows…" — several in a row like this is a failure). **For adjacent figures and figures in the same section, vary the entry angle and sentence structure**: lead from the prior conclusion, from the question being answered, from an anomaly in the figure, or fold the figure into an argument already in flow. Write like a good paper, not identically-formatted caption cards.
- **✅ Figure numbers MUST be cited explicitly (academic norm, compatible with "no formulaic patterns")**: every figure must be named ("Fig. N") so the reader maps the paragraph to the exact figure — a hard requirement; don't drop numbers to avoid templating. **What varies is the citation's structure and position, not whether you cite.** Rotate entry styles, never the same one for two adjacent figures: sentence-start ("In the pipeline of Fig. 3…"), mid-sentence parenthetical ("…holds (see Fig. 2):"), verb-led ("Observing the curves in Fig. 4…"), figure-as-subject ("Fig. 5 compares…"), or post-hoc confirmation ("…confirmed in Fig. 6."). The number must always appear — just don't open every figure with the one "Fig. N + verb + one-line conclusion" pattern.
- **⛔ No boilerplate placeholders**: "as shown below", "the figure shows the results", "this is the flowchart" carry no real information and hold true for any figure — they count as nothing. If you cannot say what is unique about it and why it matters to the argument, do not include it ("if it's not useful, better not to include it").
- **⛔ Keep captions SHORT — a label (body ≤14 words, excluding the "Figure N:" prefix)**: the alt text in `![caption](path)` holds only a short noun phrase naming what the figure is; criteria, parameters, axis meanings, and conclusions go into the prose, not the caption (Word centers/bolds captions, so long ones wrap to ugly multi-line blocks). Anti-example `![Figure 3: Coverage-radius geometry: station as center, R=3km coverage circle, dispatch distance and response-time criterion](...)` → short form `![Figure 3: Station coverage-radius geometry](...)`. See the caption-length rule in `_utils/writing_rules.md`; final verification scans caption length and flags overruns.
- **⛔ No two images directly adjacent** (one `![...](...)` right after another with no prose paragraph between). If two figures must appear back-to-back, write a transition paragraph explaining their logical relationship.

### Step 1.5: Pre-fetch verified reference pool

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
mkdir -p _tmp
# Search by topic, save verified entries to _tmp/_verified_refs.txt
```

### Step 2: Write the paper

Order: Body chapters first → References → Summary Sheet last.

**⛔ Cross-chapter context + figure-data binding (prevents the "two-layers" disconnect):**
- Even in one `main.md`, keep the whole draft coherent: **as you finish each chapter, append a 3-5 line card** to `_writing_context.md` in the workspace root (core claim / key numbers / newly defined symbols & terms / figures discussed), and re-read it so later chapters carry forward prior conclusions, reuse defined terms (don't redefine), and keep every metric's number consistent — see `<chapter_context_card>` in `_utils/writing_rules.md`.
- **Before writing the analysis for any figure/table**, follow `<figure_data_binding>`: identify *what quantity the figure plots* from FIGURE_MANIFEST/latex_includes → locate its real values in `RESULTS.md`/`figures/all_results.json` → use only those real numbers. **Never guess numbers from the plot's shape/position, never fabricate coordinates.**

Skeleton (one `paper/main.md`):

```markdown
# [Paper Title]

## Summary Sheet

[Placeholder — write LAST in Step 5.6, after all chapters complete and numerical results known]

**Keywords**: ...

## 1. Introduction

### 1.1 Problem Background

[2-3 paragraphs of real-world context, references to prior work]

### 1.2 Restatement of the Problem

[Restate in own words, NOT copy the problem statement]

### 1.3 Our Approach

[Use a paragraph or two to explain how the three sub-problems build on one another, letting the prose settle into "the overall pipeline can be summarized as follows" before the figure — do NOT open with "As shown in Figure 1"]

![Figure 1: Solution roadmap.](figures/fig_roadmap.png)

[After the figure: highlight the pivotal stage of the pipeline and lead into the first sub-problem. Vary the entry for every figure — never a uniform "As shown in Figure X / Figure X shows"]

## 2. Assumptions and Justifications

We make the following assumptions:

(1) [Assumption]. This assumption is justified because... [1-2 sentences]
(2) ...
(3) ...
(4) ...
(5) ...

⛔ 4-6 assumptions. Each 1-2 sentences (assumption + justification).

## 3. Notations

**Table 1: Key Notations**

| Symbol | Meaning | Unit |
|--------|---------|------|
| $N$ | Total quantity | items |
| $x_i$ | Decision variable for item $i$ | --- |
| ... | ... | ... |

⛔ 15-20 symbols max — only those actually used in body.

## 4. Sub-Problem 1

### 4.1 Problem Analysis

[1-2 paragraphs]

### 4.2 Model Formulation

[Transition from the problem analysis: since the crux is X, the solution proceeds in several stages — describe them, then bring in the figure. Use a different opener, not "Figure 2 illustrates"]

![Figure 2: Sub-problem 1 algorithm flow.](figures/fig_flow_q1.png)

We formulate the model as:

$$\min \sum_{i=1}^n c_i x_i \quad (1)$$

$$\text{s.t.} \quad \sum_i a_{ij} x_i \leq b_j, \quad j=1,\dots,m \quad (2)$$

[≥ 5 lines explaining each symbol's meaning]

### 4.3 Solution Algorithm

[Algorithm steps + complexity analysis]

### 4.4 Results

**Table 2: Comparison of algorithms for Sub-problem 1**

| Algorithm | Fitness | Time(s) |
|-----------|---------|---------|
| GA | 0.823 | 12.3 |
| PSO | 0.811 | 10.8 |
| Ours | **0.917** | **9.4** |

Table 2 shows that our method... [≥ 2 paragraphs of analysis]

![Figure 3: Convergence curves.](figures/fig_results_q1.png)

[Change the entry again: e.g. pose the question "where does the gap in Table 2 come from?" and let the convergence curves answer it, folding the figure into the ongoing argument rather than a "Figure 3 shows…" label. Follow with enough numerical interpretation and reasoning to make the point fully.]

## 5. Sub-Problem 2

[Same structure]

## 6. Sub-Problem 3

[Same structure]

## 7. Sensitivity Analysis

[≥ 2 key parameters, each with variation curve + analysis]

## 8. Model Evaluation

### 8.1 Strengths

[3-4 strengths, each one paragraph]

### 8.2 Weaknesses

[2-3 weaknesses]

### 8.3 Future Work

[1-2 paragraphs]

## 9. Conclusions

[Summary + main contributions + practical implications]

## References

[1] LeSage J P, Pace R K. Introduction to Spatial Econometrics. CRC Press, 2009.
[2] Vaswani A, et al. Attention is all you need. NeurIPS 2017.

## Appendix A: Code

```python
# Code listings or file inventory
```
```

### Step 3: Writing discipline

**⛔ Style rules:**
- No bullet/enumerated lists for narrative prose. Use "(1) ... (2) ..." inline numbering or transitional phrases ("First, ...; second, ..."). Bullets/enumerations OK for input checklists, evaluation metrics definitions, software dependencies, model assumptions.
- Each paragraph 3-5 sentences minimum.
- Consecutive paragraphs cannot start with the same syntactic pattern.
- Figure numbers MUST be cited explicitly (every paragraph names its "Fig. N"), but VARY the pattern. What's forbidden is the monotonous empty "Fig. X shows… as can be seen…" skeleton repeated for every figure — NOT figure-as-subject per se. Rotate: parenthetical (preferred, "(Fig. X)"), sentence-start, verb-led, figure-as-subject (allowed when it carries a real finding, at most once per section), post-hoc confirmation. Adjacent figures must not use the same pattern, and two adjacent paragraphs both opening with "Fig. N…" is an outright violation. Define any jargon or internal code (e.g. C4, blend, ridge distribution) in plain words at first use — never drop raw pipeline codes into the prose.

**⛔ Numbers from data only.**

**⛔ NEVER `cat figures/*_results.json`.** These result files often contain full-precision time-series arrays (tens of MB / hundreds of thousands of lines); reading them whole blows up the context — local models fail outright, and GPT-via-transit chokes on protocol translation of the oversized payload and stalls on repeated `api_retry`. **The paper text only uses scalar values; the giant arrays are for figures, not prose.** Before writing any results section, run the `summarize` script below for a KB-level overview (scalars shown verbatim — zero precision loss — only big arrays compressed to "length + range + first 3 samples"):
```bash
[ -f RESULTS.md ] && cat RESULTS.md
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
Every scalar you need is in `RESULTS.md` or the range/sample above. If one scalar isn't fully shown, fetch just that value with `python3 -c "import json;d=json.load(open('figures/all_results.json'));print(d['key'])"` — still never read the whole file. Copy exact numbers from data. No memory-based estimation.

**⛔ Figure-text discipline:**
- Each figure/table needs ≥ 5 lines of analysis (numerical interpretation + comparison + reasoning) before the next visual
- Never two consecutive visuals without analysis paragraph between

**⛔ Long tables (>15 rows):**
- ≤15 rows: in body
- >15 rows: body shows summary (first 5 + last 3 + "⋮"), full table in `## Appendix A`
- Caption notes "(partial; see Appendix for full table)"

After each section:
```bash
words=$(wc -w < paper/main.md)
echo "running word count: $words"
```

<exemplar_depth>
#### Writing depth reference

**MCM/ICM Outstanding Paper (~25 pages, ~15000 words total)**:
- Summary Sheet (1p, 300-400 words): self-contained with specific numerical results. Structure: problem statement (1-2 sentences) → method (2-3 sentences) → key results (3-4 sentences with numbers) → conclusion (1-2 sentences)
- Introduction (2p, ~1200 words): problem context + literature + approach overview
- Assumptions (0.5p): each assumption with justification (not just a bullet list)
- Notations (0.5p): 15-20 symbols max, three-line markdown table
- Each sub-problem (4-5p, ~2400-3000 words): model formulation (1.5p with derivation) + solution method (1p with algorithm) + results table+figure+numbers (1p) + analysis (0.5-1p interpretation + comparison)
- Sensitivity Analysis (2-3p, ~1200-1800 words): ≥ 2 key parameters, each with variation plot + analysis paragraph
- Model Evaluation (1.5p): 3-5 strengths + 2-3 weaknesses (**honest**, not token weaknesses like "limited by time") + generalization discussion
- References + Appendix (3-4p)

**APMCM First Prize (25-30 pages)**: similar but can be longer, 5-6 pages per sub-problem with more detailed analysis.
</exemplar_depth>

**Expansion strategies** (not padding — substantive content):
- Formula without derivation → add step-by-step derivation with physical meaning
- Result with only "Table X shows" → add 2-3 paragraphs (what numbers mean, comparison with expectations, why this result makes sense)
- Algorithm as pseudocode only → add explanation of key steps, complexity analysis, convergence discussion

**Summary Sheet** is the most important page — invest the most effort here. Must be self-contained, one page, ≥ 300 words, with quantitative results.

**Each sub-problem chapter**: model formulation → solution method → results (table + figure + numbers) → result analysis (2-3 paragraphs of interpretation)

**Sensitivity Analysis**: parameter sensitivity + robustness + error analysis

**Model Evaluation**: Strengths 3-5 points + Weaknesses 2-3 points (honest) — do not write token weaknesses like "limited by time"

### Step 4: Reference numbering

```bash
grep -oE '\[[0-9]+(-[0-9]+)?(, *[0-9]+)*\]' paper/main.md | sort -u > _tmp/_cited.txt
ref_count=$(awk '/^## References/,0' paper/main.md | grep -cE '^\[[0-9]+\]')
echo "Cited tokens vs reference entries: $(wc -l < _tmp/_cited.txt) vs $ref_count"
```

⛔ Numbering must be strictly increasing by first appearance ([1] before [2] before [3]). No gaps.
⛔ MCM/ICM ≥ 10 references; APMCM ≥ 10.

### Step 4.5: Verify references with scholar_fetch (mandatory)

⛔ **All references MUST be fetched via scholar_fetch.py. NEVER fabricate BibTeX from memory.**

Use **descriptive citation keys** while drafting: `LastName_Year_topic_keywords`.
- ✅ `cordeau_2007_vrp_branch_cut`
- ❌ `cordeau2007vrp` (impossible to re-search)
- Author/year unknown → `TODO__` prefix: `TODO__integer_programming_scheduling`

After drafting, verify each citation:

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
mkdir -p _tmp
# Place descriptive keys in _tmp/_topics.txt (one per line)
while IFS= read -r key; do
    query=$(echo "$key" | sed 's/^TODO__//; s/_/ /g')
    echo "--- Fetching: $key (query: $query) ---"
    $PYTHON "$SCHOLAR_SCRIPT" bibtex "$query" --max 3
    sleep 0.5
done < _tmp/_topics.txt
```

For each result:
1. **Check `match_label`**: `"good"` → use; `"partial"` → verify title; `"low"` → retry or use WebSearch.
2. **Check `match_score`**: < 0.3 → don't blindly trust.
3. Format result as `[N] Author A, Author B. Title. Venue, Year, vol(issue): pages.` under `## References`.
4. References order in `## References` MUST match first-appearance order in body.

**Fallback**: If `scholar_fetch.py` fails or `match_label="low"`, use WebSearch on Google Scholar / Semantic Scholar to verify title + authors + year manually.

### Step 4.6: Claims-Evidence Matrix Verification

Before each chapter, re-read the claims-evidence matrix in `PROBLEM_ANALYSIS.md` / `MODELING_REPORT.md` / `PAPER_PLAN.md`:

```bash
grep -A 100 'Claims-Evidence\|claim.*evidence\|claim-evidence' PROBLEM_ANALYSIS.md MODELING_REPORT.md PAPER_PLAN.md 2>/dev/null | head -50
```

Discipline:
- Every claim in the paper must map to a row in the planning doc
- Don't add claims outside the plan (if a new finding appears, update MODELING_REPORT.md first)
- Don't skip planned claims (even negative results must be reported honestly)
- Every numerical claim must match `figures/all_results.json` exactly

If a planned claim has no data evidence, write "preliminary results suggest X, formal validation left to future work" instead of fabricating evidence.

### Step 5: De-AI polish

See `<de_ai_polish>` in writing_rules.md. Key:
- Drop "this paper proposes / we propose" boilerplate
- Replace "explore / investigate" with concrete verbs
- Cap "we" frequency

### Step 5.5: Cross-review (optional)

```bash
mkdir -p _tmp
cat << 'EOF' > _tmp/_review_prompt.txt
Review this MCM/ICM/APMCM paper draft. Focus on:
1. Sub-problem coverage (does each sub-problem have explicit numerical results?)
2. Claim-evidence alignment (every conclusion supported by data?)
3. Chapter structure vs MCM/ICM standard
4. Writing clarity (any meta-narrative leaks / boilerplate openings?)
5. Score (1-10) + top-3 improvements

## Paper:
EOF
cat paper/main.md >> _tmp/_review_prompt.txt
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _tmp/_review_prompt.txt --thread-file _tmp/_reviewer_thread.json 2>&1 | tee _tmp/_cross_review.txt
```

Skip if reviewer script unavailable.

### Step 5.6: Write Summary Sheet LAST

⛔ NOW write the Summary Sheet (replace the placeholder from Step 2).

The Summary Sheet is the most important page. Read RESULTS.md and all body chapters to extract specific numerical results for each sub-problem.

```markdown
## Summary Sheet

[1-page summary covering:
- Background and problem context (1 short paragraph)
- Approach/methodology summary (1 paragraph)
- Sub-problem 1: method + key result with specific number (1 paragraph)
- Sub-problem 2: method + key result with specific number (1 paragraph)
- Sub-problem 3: method + key result with specific number (1 paragraph)
- Model evaluation: strengths + weaknesses (1 short paragraph)]

**Keywords**: keyword1; keyword2; keyword3; keyword4; keyword5
```

⛔⛔ **Bold the key content in the Summary Sheet (use `**bold**` markdown, Summary Sheet body only)**: judges skim the summary; bolding the core method and result is a plus. **Bold ONLY these three "conclusion anchors":**
1. **Key result numbers** (final answers): e.g. `**2376.8**`, `**98.7%**`, `**<3%**`, `**12.4 km**`
2. **Core method/model names**: e.g. `**NSGA-II**`, `**XGBoost**`, `**genetic algorithm**` — bold each name only at its first/conclusion appearance, not every mention
3. **The single most critical noun** in a conclusion sentence

⛔ **Bold discipline (avoid over-bolding — less is more):**
- **1~3 bolds per paragraph, ≤ 12 total**. More than that is wrong.
- **Never** bold: whole sentences, background, connectives, or the same method name repeatedly.
- ⛔ Use `**xxx**` only (markdown), **NOT `\textbf{}`** (that is LaTeX; it would show as literal garbage in docx).
- ⛔ Do **not** touch the `**Keywords**:` line — that bold is the label itself.
- ⛔ Bold only wraps the text in `**`; numbers must still be pulled truthfully from the body, never changed or fabricated for emphasis.

Example: `We build an **NSGA-II** multi-objective model, achieving optimal cost **$2376.8k**, a **12.3%** reduction over baseline.`

⛔ Each sub-problem must have its specific result in the Summary Sheet (e.g., "For Sub-problem 1, we apply genetic algorithm achieving fitness 0.917 with 9.4s solve time"). Numbers must match body text exactly.

⛔⛔ **Each "For Sub-problem X" must be its own paragraph, separated by a blank line — never cram two or more into one paragraph.** Examples:

```markdown
(correct ✅ — blank line between each sub-problem)
This paper addresses ... by building ... models.

For Sub-problem 1, we apply ...; the optimal solution is ..., fitness 0.917.

For Sub-problem 2, we construct ...; MAPE drops from 29.48% to 14.93%.

For Sub-problem 3, ...; predicted values are 952.8, 1570.5, 11030.9.

Model evaluation: strengths ...; weaknesses ....
```

```markdown
(wrong ❌ — Word export turns this into a wall of text)
For Sub-problem 2, MAPE 14.93%. For Sub-problem 3, predicted values are 952.8, 1570.5.
```

⛔ **Run the paragraph self-check (detect → fix → recheck loop; use `python`, not `python3`):**
```bash
python - <<'PY'
import re, sys
text = open('paper/main.md', encoding='utf-8').read()
m = re.search(r'^##\s*(Summary Sheet|Abstract)[\s\S]*?(?=^##\s|\Z)', text, re.MULTILINE)
if not m:
    print('⚠ Summary Sheet section not found'); sys.exit(0)
section = m.group(0)
bad = []
for i, para in enumerate(re.split(r'\n\s*\n', section), 1):
    if len(re.findall(r'[Ff]or [Ss]ub-?problem', para)) > 1:
        bad.append((i, para.strip()[:80]))
if bad:
    print(f"❌ {len(bad)} paragraph(s) cram multiple 'For Sub-problem' openers — split each into its own paragraph:")
    for i, snip in bad:
        print(f"  para {i}: {snip}...")
    sys.exit(1)
print('✓ Summary Sheet is split per sub-problem')
PY
```
⛔ **Loop rule: if the check exits 1, go back to the `## Summary Sheet` section in `paper/main.md`, insert a blank line before each "For Sub-problem X" so it becomes its own paragraph, then rerun the check until it prints "✓ Summary Sheet is split per sub-problem" before moving on.**

### Step 6: Final verification

**⛔ Capability-claim gate (full-chain contract; zero-cost, both modes):** The Word paper must not claim capabilities that failed acceptance in coding.
```bash
FAST_MODE=0; grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null && FAST_MODE=1
python _utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper --fast $FAST_MODE
PCC=$?   # 0=all passed 1=some capability FAIL/PENDING (do not finalize) 2=no audit, skip
```
> `PCC=1`: make the failed capability truly PASS in comp-code before finalizing. WARN: a not-passed capability name appears in the body (main.md) — ensure it isn't written as done unless honestly under Limitations. Chain: analysis→modeling→code-audit→paper reports only passed.

```bash
echo "=== Final verification ==="

[ -f paper/main.md ] && SZ=$(wc -c < paper/main.md) || SZ=0
echo "paper/main.md: $SZ bytes"

words=$(wc -w < paper/main.md)
est_pages=$((words / 600))
target=${MAX_PAGES:-25}
echo "words: $words, est pages: ~$est_pages, target: ≥ $target"
[ "$est_pages" -lt "$((target * 80 / 100))" ] && echo "⛔ MUST expand thinnest sections"

# Sub-problem coverage
for n in 1 2 3; do
    if grep -qE "^## [0-9]+\. Sub-Problem ${n}|^## [0-9]+\. Problem ${n}" paper/main.md; then
        echo "✅ Sub-Problem ${n} present"
    else
        echo "⚠ Sub-Problem ${n} missing"
    fi
done

# Figure embedding
missing_img=0
for img in figures/*.png figures/*.pdf; do
    [ -f "$img" ] || continue
    bn=$(basename "$img")
    [ "$bn" = "latex_includes.tex" ] && continue
    if ! grep -q "$bn" paper/main.md; then
        echo "⚠ unembedded: $bn"
        missing_img=$((missing_img + 1))
    fi
done
[ "$missing_img" -gt 0 ] && echo "⛔ embed missing figures"

# ⛔ Adjacent-image check (prevents "two figures stuck together with no text between")
echo "=== Adjacent-image check ==="
python - paper/main.md << 'PYEOF'
import re, sys
try:
    t = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
except FileNotFoundError:
    sys.exit(0)
imgs = list(re.finditer(r'!\[[^\]]*\]\([^)]*\)', t))
bad = 0
for i in range(len(imgs) - 1):
    gap = t[imgs[i].end():imgs[i+1].start()]
    body = re.sub(r'\s+', '', gap)
    if len(body) < 150:
        bad += 1
if bad:
    print("  X paper/main.md: %d figure gaps with too little prose (<150 chars, likely perfunctory/one-liner) — each figure needs full analysis: concrete numbers + comparison/trend + inference/linkage, never a lone sentence" % bad)
PYEOF
echo "(no output = no adjacency found)"

# ⛔ FIGURE_MANIFEST audit: planned figures must all be produced AND embedded
PLAN_FILE=""
for f in PROBLEM_ANALYSIS.md PAPER_PLAN.md MODELING_REPORT.md; do
  [ -f "$f" ] && grep -q '<!-- BEGIN FIGURE_MANIFEST -->' "$f" && { PLAN_FILE="$f"; break; }
done
if [ -n "$PLAN_FILE" ]; then
    START=$(grep -n '<!-- BEGIN FIGURE_MANIFEST -->' "$PLAN_FILE" | head -1 | cut -d: -f1)
    END=$(grep -n '<!-- END FIGURE_MANIFEST -->' "$PLAN_FILE" | head -1 | cut -d: -f1)
    EXPECTED_FIGS=$(sed -n "${START},${END}p" "$PLAN_FILE" | grep -oE '^[[:space:]]*-[[:space:]]+(fig_[a-zA-Z0-9_]+|tikz_[a-zA-Z0-9_]+)' | sed 's/^[[:space:]]*-[[:space:]]*//')
    manifest_missing=0
    for name in $EXPECTED_FIGS; do
        if ! ls figures/${name}.png figures/${name}.pdf figures/${name}.drawio 2>/dev/null | head -1 | grep -q .; then
            echo "❌ MANIFEST: $name file missing"
            manifest_missing=$((manifest_missing + 1))
        elif ! grep -qE "${name}\.(png|pdf)" paper/main.md; then
            echo "❌ MANIFEST: $name exists but not embedded in paper/main.md"
            manifest_missing=$((manifest_missing + 1))
        fi
    done
    [ "$manifest_missing" -gt 0 ] && echo "⛔ FIGURE_MANIFEST audit failed ($manifest_missing missing): must produce + embed all planned figures"
fi

# Citation continuity
max_cited=$(grep -oE '\[[0-9]+\]' paper/main.md | grep -v '^## ' | tr -d '[]' | sort -n | tail -1)
ref_lines=$(awk '/^## References/,0' paper/main.md | grep -cE '^\[[0-9]+\]')
echo "max cited: ${max_cited:-0}, refs: $ref_lines"
[ -n "$max_cited" ] && [ "$ref_lines" -lt "$max_cited" ] && echo "⛔ refs less than cited"

# LaTeX residue
if grep -qE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter)\{' paper/main.md; then
    echo "⛔ LaTeX residue:"
    grep -nE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter)\{' paper/main.md | head -5
fi

# .tex residue
ls paper/*.tex paper/sections/*.tex 2>/dev/null | head -1 | grep -q . && echo "⛔ .tex files detected" || echo "✅ no .tex"

# Summary Sheet not placeholder
if grep -A 3 '^## Summary Sheet' paper/main.md | grep -qiE 'placeholder|TODO'; then
    echo "⛔ Summary Sheet still placeholder — must fill in"
fi

# ⛔ Figure-opener de-templating check (docx-only: the LaTeX contest flow is covered by
#    writing_check.sh, but the docx flow was not — so prose ended up opening every figure with
#    "Figure N shows…/Fig. N depicts…". This adds the same guard, matching the LaTeX version.)
echo "=== Figure-opener de-templating check ==="
PYTHONIOENCODING=utf-8 python - paper/main.md << 'PYEOF'
import re, sys
try:
    text = open(sys.argv[1], encoding='utf-8', errors='ignore').read().replace('\r\n', '\n')
except FileNotFoundError:
    sys.exit(0)
# Body only: cut at "## Appendix"/"## References" (figure numbers in code/refs don't count)
m = re.search(r'\n##\s*(Appendix|References)', text)
body = text[:m.start()] if m else text
# Opening with "Figure N…/Fig. N…/Table N…" = the most monotonous AI tell.
# Lead-ins that bury the number mid-sentence ("as shown in Fig. 2", "observing Fig. 4",
# "in the pipeline of Fig. 3") are fine and must NOT be flagged.
open_re = re.compile(r'^(Figure|Fig\.?|Table|Tab\.?)\s*\d', re.I)
leadin_re = re.compile(r'^(as\s|in\s|observing\b|from\b|see\b|per\b|following\b)', re.I)
def is_prose(p):
    s = p.strip()
    if len(s) < 15:
        return False
    if s[0] in '#>|`!*-\\%{}$&':          # heading/quote/table/code/image(![)/list/bold/LaTeX
        return False
    if re.match(r'^\d+\.', s):             # ordered list "1."
        return False
    return True
sections = re.split(r'(?m)^##\s', body)
adj_pairs = 0
heavy_secs = []
for sec in sections:
    flags = []
    for p in re.split(r'\n\s*\n', sec):
        if not is_prose(p):
            continue
        s = p.strip()
        flags.append(bool(open_re.match(s)) and not bool(leadin_re.match(s)))
    adj_pairs += sum(1 for i in range(len(flags) - 1) if flags[i] and flags[i + 1])
    n_open = sum(flags)
    if n_open >= 3:
        heavy_secs.append(n_open)
if adj_pairs or heavy_secs:
    if adj_pairs:
        print(f"  X {adj_pairs} adjacent paragraph pair(s) both open with 'Figure N…/Table N…' — the worst tell; sink the number mid-sentence or into a trailing parenthetical")
    if heavy_secs:
        print(f"  X {len(heavy_secs)} section(s) with >=3 figure-number openers ({heavy_secs}) — opening every figure with 'Fig. N' is monotonous; vary the entry")
    print("  Fix: parenthetical (preferred, '…(Fig. 3)'), verb-led ('Observing Fig. 4…'), or post-hoc ('…confirmed in Fig. 5'); figure-as-subject at most once per section")
    sys.exit(3)
print("  OK: figure citations are not templated")
PYEOF
fig_rc=$?
[ "$fig_rc" -eq 3 ] && echo "⛔ Templated figure openers: rewrite per the hints above, then re-run this check until it prints OK"

# Caption-too-long check (alt text is a short label; criteria/params/conclusions go in the body)
echo "=== Caption-too-long check ==="
python - paper/main.md << 'PYEOF'
import re, sys
LIMIT = 14  # word cap after stripping the "Figure N:" prefix (matches spec; over 14 = violation)
try:
    text = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
except FileNotFoundError:
    sys.exit(0)
# Body only (cut at Appendix/References), matching writing_check.sh 7b3
m = re.search(r'(?m)^##\s*(Appendix|References)', text)
body_text = text[:m.start()] if m else text
bad = []
for alt in re.findall(r'!\[([^\]]*)\]\([^)]*\)', body_text):
    body = re.sub(r'^\s*(Figure|Fig\.?|Table|Tab\.?)\s*\d+\s*[:.．、]?\s*', '', alt, flags=re.I)
    words = re.findall(r'[A-Za-z][A-Za-z-]*', body)
    if len(words) > LIMIT:
        bad.append((len(words), ' '.join(words[:12])))
if bad:
    for n, preview in bad:
        print(f"  X caption {n} words (>{LIMIT}): {preview}...")
    print(f"  {len(bad)} caption(s) too long — keep alt text to a short label (<=14 words); move criteria/params/conclusions into the body")
    sys.exit(3)
print("  OK captions are concise")
PYEOF
cap_rc=$?
[ "$cap_rc" -eq 3 ] && echo "⛔ Captions too long: shorten the alt text and move detail into the body, then re-run until it prints OK"
```

If any ⛔ appears, fix and re-run verification.

⛔ **The figure-opener check is a detect → fix → recheck loop**: whenever it reports X (`exit 3`), go back to `paper/main.md`, rewrite the flagged "Figure N…/Table N…" openers into parenthetical / verb-led / post-hoc forms (figure-as-subject at most once per section), then **re-run this check until it prints "OK: figure citations are not templated"** before finishing. This mirrors `writing_check.sh` in the LaTeX contest flow so the docx export matches the PDF export in quality.

### Step 7: Compliance check (MCM/ICM specific)

Before submitting, verify against contest rules:

- [ ] **Summary Sheet present** with quantitative results for every sub-problem
- [ ] **Team Control Number** placeholder visible (where required)
- [ ] **No author names / affiliations** anywhere in body (anonymous submission)
- [ ] **Page count** within limit (MCM/ICM ≤ 25; APMCM may extend; check current year's rules)
- [ ] **APMCM submission**: commitment letter is submitted separately, NOT bundled into the PDF/docx
- [ ] **Code appendix included** (complete runnable code, not snippets)
- [ ] **Figure paths reference** `figures/*.png` (not absolute paths)
- [ ] **Numbers in Summary Sheet** match numbers in body text exactly
- [ ] **Constraint consistency**: every numerical result satisfies problem constraints (load capacity, time window, count limits etc.)

If any box is ❌, fix before submission.

## Key Rules (docx mode)

- **Single artifact**: `paper/main.md`
- **Never**: `.tex` / `.bib` / `.cls` / `.sty` / `.aux`
- **Math**: `$...$` / `$$...$$`
- **Figures**: `![alt](path)`
- **Tables**: markdown pipe tables
- **Citations**: `[N]`
- Summary Sheet structure: each sub-problem with specific number
- Body length ≥ MAX_PAGES × 600 words
- Numbers from `figures/*.json` / `RESULTS.md`
- Long tables (>15 rows): summary in body + full in Appendix
- Citations strictly increasing by first appearance
- Backup before overwrite

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

