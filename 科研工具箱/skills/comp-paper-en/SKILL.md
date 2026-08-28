---

name: comp-paper-en

description: "Mathematical modeling competition paper writing in English (MCM/ICM/APMCM). Generate complete LaTeX paper following COMAP format. Use when user says \"write MCM paper\", \"美赛论文\", \"English competition paper\"."

argument-hint: [competition-type]

allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch

---

# Competition Paper Writing (English)

Write a competition paper: **$ARGUMENTS**

## ⚡ Fast-mode detection (run first)

```bash

FAST_MODE=0

grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null && FAST_MODE=1

echo "FAST_MODE=$FAST_MODE"

```

**If `FAST_MODE=1` (speed priority):** still MUST produce a complete paper (all chapters present, every sub-problem covered, figures embedded per manifest, body pages meet MAX_PAGES, cite real data — no fabrication, pass output verification), but **SKIP**: line-by-line figure-text number consistency re-checks, source-traceback audits, and repeated polish/rewrite for minor issues. Write it once, complete in structure and content. **If `FAST_MODE=0` (default):** run all consistency checks as usual.

## Constants

- **COMPETITION** — Default `mcm`. From Additional Parameters.

- **MAX_PAGES** — Default 25. Body pages must be ≥ MAX_PAGES.

- **CUSTOM_REQUIREMENTS**

## Inputs

1. PROBLEM_ANALYSIS.md, MODELING_REPORT.md, RESULTS.md

2. figures/, code/

## Load shared rules

```bash

cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md

```

## MCM/ICM Paper Structure

```

Summary Sheet (1 page — most important page in the entire paper)

Table of Contents

1. Introduction (1-2 pages)

2. Assumptions and Justifications (0.5 page)

3. Notations (0.5 page)

4. Model Design and Solution (per sub-problem, 4-5 pages each)

5. Sensitivity Analysis (1-2 pages)

6. Model Evaluation (Strengths + Weaknesses)

7. Conclusions (0.5 page)

References

Appendix A: Code

```

## ⛔⛔⛔ Output Contract (highest priority)

**Mandatory output depends on `params.output_format`**:

- **PDF mode**: `paper/main.tex` (≥ 5KB) + `paper/sections/*.tex` + `paper/references.bib`

- **docx mode**: `paper/main.md` (single file, ≥ 5KB). Do NOT create `paper/main.tex`

⛔ **MUST run output verification before ending the step**:

```bash

MODE=$(grep -q "Word（.docx）\|docx mode" CLAUDE.md 2>/dev/null && echo docx || echo pdf)

PASS=true

if [ "$MODE" = "docx" ]; then

    [ -f paper/main.md ] && SZ=$(wc -c < paper/main.md) || SZ=0

    [ "$SZ" -ge 5120 ] && echo "✅ paper/main.md ($SZ)" || { echo "❌ paper/main.md missing"; PASS=false; }

else

    [ -f paper/main.tex ] && SZ=$(wc -c < paper/main.tex) || SZ=0

    [ "$SZ" -ge 5120 ] && echo "✅ paper/main.tex ($SZ)" || { echo "❌ paper/main.tex missing"; PASS=false; }

    SECT_COUNT=$(ls paper/sections/*.tex 2>/dev/null | wc -l)

    [ "$SECT_COUNT" -ge 3 ] && echo "✅ sections ($SECT_COUNT)" || { echo "❌ too few sections"; PASS=false; }

fi

[ "$PASS" != true ] && echo "⛔ Output verification FAILED — must complete before ending"

```

## Workflow

### Step 0: Backup + resume check

Back up existing `paper/`. Check for incomplete sections:

```bash

echo "=== Resume check ==="

if [ -d "paper/sections" ]; then

    for f in paper/sections/*.tex; do

        [ -f "$f" ] || continue

        chars=$(wc -c < "$f")

        [ "$chars" -lt 500 ] && echo "⚠ Placeholder: $(basename $f) ($chars chars)" || echo "✅ Complete: $(basename $f) ($chars chars)"

    done

fi

```

Resume: only write placeholder sections, skip completed ones (>2000 chars). Save each section immediately. If approaching output limit, create `% [PLACEHOLDER]` files.

### Step 1: Select template

```bash

mkdir -p paper/sections

TMPL_BASE="_templates"

[ -d "$TMPL_BASE" ] || TMPL_BASE="templates"

if echo "$ARGUMENTS" | grep -qi "mcm\|MCM\|ICM" || grep -qi "mcm\|MCM" CLAUDE.md 2>/dev/null; then

    echo "Using MCM template"

    cp "$TMPL_BASE/mcm/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "apmcm\|APMCM\|亚太" || grep -qi "apmcm" CLAUDE.md 2>/dev/null; then

    echo "Using APMCM template"

    cp "$TMPL_BASE/apmcm/"* paper/ 2>/dev/null

else

    echo "Using default English template"

    cp "$TMPL_BASE/default/"* paper/ 2>/dev/null

fi

[ -f paper/main.tex ] && echo "Template copied: $(wc -l < paper/main.tex) lines" || echo "ERROR: template not found!"

```

MCM/ICM uses `mcmthesis.cls` (included in template folder). APMCM uses article class.

**⛔ Do not write main.tex from scratch** — copy the template and only replace placeholders. The template handles fonts, margins, headers, and formatting.

### Step 2: Figure inventory

Before writing any section, build a complete inventory of available figures:

```bash

echo "=== Available PDF figures ==="

ls -la figures/*.pdf 2>/dev/null || echo "No PDF figures found"

echo ""

echo "=== Available table files (PDF mode: .tex / Word mode: .md) ==="

ls -la figures/TABLE_*.tex figures/TABLE_*.md 2>/dev/null || echo "No TABLE files found"

echo ""

echo "=== latex_includes.tex content (figure→PDF mapping) ==="

cat figures/latex_includes.tex 2>/dev/null || echo "No latex_includes.tex"

echo ""

echo "=== TikZ geometry/algorithm/architecture diagrams ==="

# TikZ generated by paper-figure-drawio as figures/tikz_diagrams.tex → compiled to figures/tikz_diagrams.pdf

# (legacy name tikz_architecture_examples.tex also accepted). Their \includegraphics blocks are in latex_includes.tex.

ls figures/tikz_*.pdf 2>/dev/null && echo "→ TikZ present, must embed" || echo "No TikZ diagrams"

```

**⛔ MANDATORY: Build a FIGURE EMBEDDING PLAN before writing any section:**

```

FIGURE EMBEDDING PLAN:

1. fig_p1_result.pdf → Problem 1 section → caption: "Figure X: ..."

2. fig_p2_result.pdf → Problem 2 section → caption: "Figure X: ..."

3. TABLE_comparison.tex → Results section → caption: "Table X: ..."

4. tikz_diagrams.pdf (geometry/algorithm/architecture TikZ, from latex_includes.tex) → Introduction/Model section

```

**Rules:**

- **⛔ Must use figure blocks from `latex_includes.tex`**, not write `\includegraphics` from scratch

- **⛔ TikZ diagrams must be embedded**: every `\begin{figure}` block in `latex_includes.tex` that references `tikz_diagrams.pdf` / `tikz_*.pdf` must be copied into a section — do not miss any

- **⛔ Image paths must be `../figures/xxx.pdf`**

- Only embed figures whose PDF files actually exist

**⛔⛔⛔ DrawIO figure embedding (most commonly missed — check each one):**

DrawIO figures (roadmap, flow charts, pipeline diagrams) are appended at the **end** of `latex_includes.tex` by the paper-figure-drawio step. You MUST embed them:

| DrawIO figure type | Embed location | Section file |

|-------------------|---------------|-------------|

| Technical roadmap (fig_roadmap) | End of Introduction/Problem Restatement | `1_introduction.tex` |

| Sub-problem flow chart (fig_flow_q1/q2/q3) | Inside each sub-problem's "Model Construction" subsection, preceded by 2-3 sentences introducing the solving approach and main steps | `4_problem1.tex`, `5_problem2.tex` etc. |

| Data pipeline (fig_pipeline) | Data preprocessing section | Data/method section |

| TikZ geometry/algorithm (tikz_diagrams.pdf) | Geometry → relevant sub-problem section; algorithm flow → Model Construction subsection | Sub-problem/Model section |

**⛔⛔ HARD RULE: sub-problem flow charts MUST be spread across their own problem sections — NEVER pile all of them into the "Problem Analysis" (2_analysis) chapter.**

Cramming fig_flow_q1~q5 into the analysis chapter is the most common and ugliest failure: a single section with 5 large figures makes LaTeX's float mechanism push them all to the top of the section in a stack, shoving body text to the back and severely unbalancing the layout. Correct: `fig_flow_q1` → `4_problem1.tex`, `fig_flow_q2` → `5_problem2.tex`, … one per section, right after that problem's introductory sentences. The analysis chapter (2_analysis) keeps **at most the overall roadmap fig_roadmap**; no other flow chart may appear there.

**After writing all sections, verify DrawIO/TikZ figures are embedded:**

```bash

echo "=== DrawIO/TikZ embedding check ==="

for pdf in figures/fig_roadmap.pdf figures/fig_flow_*.pdf figures/fig_pipeline*.pdf figures/fig_framework*.pdf; do

    [ -f "$pdf" ] || continue

    bn=$(basename "$pdf")

    grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null && echo "✅ $bn embedded" || echo "❌ $bn NOT embedded — fix now!"

done

# ⛔ TikZ check by PDF filename (most reliable)

for tpdf in figures/tikz_diagrams.pdf figures/tikz_diagrams_*.pdf figures/tikz_*.pdf; do

    [ -f "$tpdf" ] || continue

    tbn=$(basename "$tpdf")

    grep -rq "$tbn" paper/sections/*.tex paper/main.tex 2>/dev/null && echo "✅ TikZ $tbn embedded" || echo "❌ TikZ $tbn NOT embedded — fix now!"

done

# ⛔ Flow-chart stacking check: the analysis chapter (2_analysis) must hold ≤1 sub-problem

#    flow chart, otherwise fig_flow_q1~q5 were wrongly piled into the analysis chapter.

_analysis_tex=$(ls paper/sections/2_*.tex 2>/dev/null | head -1)

if [ -n "$_analysis_tex" ]; then

    _flow_in_analysis=$(grep -oE 'fig_flow_q[0-9]+' "$_analysis_tex" 2>/dev/null | sort -u | wc -l)

    if [ "$_flow_in_analysis" -ge 2 ]; then

        echo "❌ Analysis chapter contains $_flow_in_analysis sub-problem flow charts — violates HARD RULE! Move fig_flow_q1~q5 to their own problem sections (4_problem1.tex etc.); the analysis chapter keeps at most fig_roadmap."

    else

        echo "✅ Flow charts not piled into the analysis chapter"

    fi

fi

```

Also scan `figures/*.tex` for all `\begin{figure}` / `\begin{table}` blocks with their `\label{}`. After writing, verify all embedded:

```bash

grep -oh '\\label{[^}]*}' figures/*.tex 2>/dev/null | sort -u > _tmp/all_fig_labels.txt

grep -oh '\\label{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null | sort -u > _tmp/embedded_labels.txt

comm -23 _tmp/all_fig_labels.txt _tmp/embedded_labels.txt  # should be empty

```

Follow interleaving and embedding rules from `_utils/writing_rules.md`.

**⛔ Figure-text interleaving hard rules (every section must follow):**

- **Float specifiers (pin figures in place)**: figures use `\begin{figure}[H]`; tables use `\begin{table}[H]` (both in place). `[H]` pins each figure directly under the paragraph that introduces it, so figures never float away and — crucially — **multiple figures can never stack together on one page** (the stacking problem `[htbp]` used to cause). The template still loads `\usepackage[section]{placeins}` (`\FloatBarrier` at each section end) as a safety net for any residual floating body. Trade-off: on the rare occasion a figure is nearly full-page-tall and lands near the page bottom, `[H]` leaves whitespace above it — but figures are already height-capped at `0.9\textheight` and the writing rules force text before and after every figure, so this is rare and far less harmful than illegible stacked figures. ⛔ Do NOT give tables `[htbp]`: floating pushes them to the section end, leaving half a blank page above the table (symbol/notation tables are the usual victims); short tables use `[H]`, long tables use `\begin{longtable}`. Pseudocode keeps `\begin{algorithm}[H]`.

- **⛔⛔ Figures must be drawn out by the argument, not stamped with a template sentence (hard rule)**: embed every figure in the prose so the argument itself leads into it — the reader reaches this point and naturally needs to see this figure. The one test that matters: **it reads as a smooth narrative, not as one label slapped on each figure in turn.**

  - **✅ Three goals to reach (goals, NOT a sentence template, and NOT a fixed structure to copy for every figure)**: make the reader understand (1) what this figure shows, (2) what earlier point it follows from, (3) what conclusion it supports. How you weave these into the paragraph — in what order, in what sentence structure — is up to you as the prose dictates: state the conclusion then show the figure as evidence, or describe the phenomenon then bring in the figure to explain it. **What varies is HOW you write (structure, entry angle, order); what does NOT vary is HOW DEEP you go.**

  - **⛔⛔ Depth floor for post-figure analysis (hard rule, the second core problem being fixed here)**: the discussion around each figure must **never be dispatched in a single sentence** (e.g. "See Fig. 24: the inbound spiral, two arcs, and outbound spiral join smoothly at the tangent points" — a lone sentence like this is a failure). Each figure's prose (lead-in + follow-up combined) **must land all three of the following, none omissible**: (1) **concrete numbers** — the key figures read off the plot (max radius 4.229 m, 7.59% shorter, peak 1.72 m/s), not a vague "clear trend"; (2) **comparison or trend** — against a baseline / other scheme / the previous sub-problem, or how a quantity varies along some axis; (3) **inference or linkage** — what this figure proves, what bottleneck it exposes, which next step it leads into. If you cannot do all three, the figure adds nothing to the argument and should not be included.

    - **❌ Perfunctory anti-example (the current failure mode, forbidden)**: "The arc-length optimization and comparison are shown in Fig. 25: multiple starts converge to the same optimal neighborhood, and the optimum stays below the baseline." — one sentence, no numbers, no quantified comparison, cut off abruptly.

    - **✅ Benchmark example (the fullness to emulate)**: "Fig. 15 shows the collision radius decreasing strictly monotonically as the pitch grows: as the pitch rises from 0.4 m to 0.55 m, the collision radius falls from 7.04 m to 2.289 m; the intersection of the data points with the R_t = 4.5 m threshold line lands exactly at the critical pitch p_min = 0.448 m, with the left side unable to spiral in and the right side able to. The moderate slope near the intersection indicates that the critical-pitch inversion is stable and the bisection is well-conditioned." — numbers, monotonic trend, threshold crossing, and a stability inference all present, in natural non-formulaic prose.

  - **⛔⛔ No formulaic sentence patterns (the core problem being fixed here)**: never write every figure with the same skeleton, especially the "[figure type] (Fig. N) + verb + one-line conclusion" opener (e.g. "The waterfall chart (Fig. 33) decomposes…", "The radar chart (Fig. 34) compares…", "The heatmap (Fig. 35) shows…" — several figures in a row opening this way is a failure). **For adjacent figures and figures in the same section, vary the entry angle and sentence structure**: lead from the prior conclusion, from the question being answered, from an anomaly visible in the figure, or fold the figure into an argument already in flow without a dedicated opening sentence. Write like a good paper, not like issuing an identically-formatted caption card for each figure.

  - **✅ Figure numbers MUST be cited explicitly (academic norm, fully compatible with "no formulaic patterns")**: every figure must be named in the prose ("Fig. N") so the reader can map the paragraph to the exact figure — this is a hard requirement; do not drop figure numbers just to avoid templating. **What varies is the citation's sentence structure and position, not whether you cite.** Rotate among these entry styles, and don't use the same one for two adjacent figures: sentence-start ("In the pipeline of Fig. 3, the third stage…"), mid-sentence parenthetical ("…this premise holds (see Fig. 2): propagation and text intensity…"), verb-led ("Observing the three curves in Fig. 4, the difference concentrates in…"), figure-as-subject ("Fig. 5 compares the proposed method against the baseline…", **used at most once per section, never as the default opener; two adjacent figures both opening with "Fig. N…" is an outright violation**), or post-hoc confirmation ("…this conclusion is confirmed in Fig. 6."). The number must always appear — just don't open every figure with the one "Fig. N + verb + one-line conclusion" pattern.

  - **⛔ No boilerplate placeholders**: sentences like "as shown in Fig. X", "the figure below shows the results", "Fig. X is the flowchart" carry no real information and would hold true for any figure — they count as nothing. If you cannot say what is unique about this figure and why it matters to the argument, the figure adds nothing and should not be included ("if it's not useful, better not to include it").

  - **⛔ Define jargon and internal codes in plain words at first use**: any specialized term, pipeline code, or variable shorthand (e.g. C4, blend, ridge distribution, weakly-supervised self-consistency upper bound) must first be explained in one plain sentence — what it is / what it measures — before being used. Never drop raw internal pipeline codes or working names into the prose; the paper is written for reviewers, not for the pipeline.

  - **⛔ Keep captions SHORT — a label (body ≤14 words, excluding the "Figure N" number)**: `\caption{}` holds only a short noun phrase naming what the figure is; criteria, parameters, axis meanings, and conclusions go into the prose, not the caption (long ones wrap to ugly multi-line blocks). Anti-example `\caption{Coverage-radius geometry: station as center, R=3km coverage circle, dispatch distance and response-time criterion}` → short form `\caption{Station coverage-radius geometry}`. See the caption-length rule in `_utils/writing_rules.md`; the compile step scans caption length and flags overruns.

- Every figure/table must also be followed by ≥5 lines of analysis text (data interpretation + comparison + conclusion) before the next figure

- Absolutely no consecutive `\begin{figure}...\end{figure}` environments with no prose paragraph between them; if two figures must appear back-to-back, write a transition paragraph explaining their logical relationship

- **⛔ Logic diagrams (flowchart / architecture / roadmap / pipeline / framework / TikZ geometry·algorithm·architecture sketches) must occupy their own `figure` — never place two side-by-side.** They rely on legible node text and connectors; shrinking to half text-width makes them illegible, and they are not same-axes trend comparisons so side-by-side yields no information gain. Even two related flowcharts go in separate figures with a transition paragraph between. (Data-result figures may still be combined via a single matplotlib-composed PDF, per the width rule below.)

- **🟡 Not every data figure should be paired — single-column by default, whitespace is the trigger**: data-result figures default to one-per-row; only pair two into a 2-panel when they are **same-kind/comparable** (e.g. two variables' distributions, same-kind curves for two scenarios) **and** each alone would fill only half a page, leaving over half a page of whitespace after its text. Unrelated figures stay single-column even if sparse — never pair just to fill the page (see `_utils/writing_rules.md` rule 4, decision step 3.5).

- Use `\includegraphics[width=0.85\textwidth,keepaspectratio]` (width-driven, let height auto-scale). ⛔ Do NOT add a small `height=0.38\textheight` cap — with `keepaspectratio`, a height cap can only **shrink** the figure: near-square or tall figures (heatmaps, radar charts, forest plots, confusion matrices, stacked subplots, flowcharts) get clamped to ~half text-width and look tiny. Only add `height=0.9\textheight` as an overflow guard when a single figure is genuinely near a full page tall

### Step 2.5: Pre-fetch verified reference pool

**⛔ MUST complete before writing any \citep{} in Step 3.**

```bash

PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python

mkdir -p _tmp

# Search for real papers in your topic areas (adapt queries to your paper)

# Example:

#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "your core method keywords" --max 5

#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "your research domain keywords" --max 5

```

Create `_tmp/_verified_refs.txt` with verified papers. Only cite papers from this pool when writing. Search and verify before adding new citations.

**Fallback**: If `scholar_fetch.py` returns no results or `match_label="low"` for a topic, use WebSearch to find the paper on Google Scholar / Semantic Scholar website, then manually verify title + authors + year before adding to the pool.

### Step 3: Write each section

**⛔ CRITICAL: Do NOT write the Summary Sheet now.** Skip Section 0 entirely. Write a placeholder `[Summary Sheet — fill in Step 4.6 after all chapters are complete]` in the Summary Sheet position. The Summary Sheet MUST be written LAST (after Step 4.5) because it needs specific numerical results from all chapters. Writing it first = making up numbers.

Come back to fill the Summary Sheet in Step 4.6, after all body chapters are complete. At that point, read `RESULTS.md` and all section .tex files to extract the actual numbers.

**⛔ MCM/ICM chapter order (must follow template):**

```

1_introduction.tex  — Problem background + restatement + approach overview

2_assumptions.tex   — Assumptions and justifications

3_symbols.tex       — Notation table (use non-floating table: \begin{center}\begin{tabular}, NOT \begin{table})

4_model.tex         — Model development (or split per sub-problem)

5_results.tex       — Results and analysis

6_sensitivity.tex   — Sensitivity analysis

7_strengths.tex     — Strengths and weaknesses

A_code.tex          — Appendix: code

```

File names must match template `\input{sections/...}` lines.

**⛔ Before writing each section, read MODELING_REPORT.md and RESULTS.md** for exact numbers and formulas.

**⛔ Cross-chapter context + figure-data binding (prevents the "two-layers" disconnect):**

- **After finishing each section**, append a 3-5 line card to `_writing_context.md` in the workspace root (core claim / key numbers / newly defined symbols & terms / figures discussed); **`cat _writing_context.md` before writing the next section** to carry forward prior conclusions, reuse defined terms (don't redefine), and keep every metric's number consistent — see `<chapter_context_card>` in `_utils/writing_rules.md`.

- **Before writing the analysis for any figure/table**, follow `<figure_data_binding>`: identify *what quantity the figure plots* from FIGURE_MANIFEST/latex_includes → locate its real values in `RESULTS.md`/`figures/all_results.json` → use only those real numbers. **Never guess numbers from the plot's shape/position, never fabricate coordinates.**

**⛔ No `\begin{itemize}` or `\begin{enumerate}` in body text** — use flowing prose. Inline numbering "(1)...(2)..." is acceptable.

<exemplar_depth>

#### Writing depth reference

**MCM/ICM Outstanding Paper (25 pages total, including everything)**:

- Summary Sheet (1p): 300-400 words, self-contained with specific numerical results. Structure: problem statement (1-2 sentences) → method (2-3 sentences) → key results (3-4 sentences with numbers) → conclusion (1-2 sentences)

- Introduction (2p): problem context + literature + approach overview

- Assumptions (0.5p): each assumption with justification (not just a bullet list)

- Notations (0.5p): **use non-floating table** (`\begin{center}\begin{tabular}` + `\captionof{table}{}`, NOT `\begin{table}`). This prevents the section title and table from being split across pages. Keep to 15-20 symbols max.

- Each sub-problem (4-5p): model formulation (1.5p, with derivation) + solution method (1p, with algorithm) + results with table+figure+numbers (1p) + analysis (0.5-1p, interpretation + comparison)

- Sensitivity Analysis (2-3p): ≥2 key parameters, each with variation plot + analysis paragraph

- Model Evaluation (1.5p): 3-5 strengths + 2-3 weaknesses (honest, not token weaknesses) + generalization discussion

- References + Appendix (3-4p)

**APMCM First Prize (25-30 pages)**: similar but can be longer, 5-6 pages per sub-problem with more detailed analysis.

</exemplar_depth>

After each chapter, check chars:

```bash

chars=$(wc -c < "paper/sections/current_chapter.tex")

echo "Current chapter: $chars chars"

# English LaTeX ≈ 2000-2500 chars/page

# If sub-problem chapter expected 4 pages but only 4000 chars (~2 pages), expand immediately

```

**Expansion strategies** (not padding — substantive content):

- Formula without derivation → add step-by-step derivation with physical meaning

- Result with only "as shown in Table X" → add 2-3 paragraphs (what numbers mean, comparison with expectations, why this result makes sense)

- Algorithm as pseudocode only → add explanation of key steps, complexity analysis, convergence discussion

**Summary Sheet** is the most important page — invest the most effort here. Must be self-contained, one page, ≥300 words, with quantitative results.

**Each sub-problem chapter**: model formulation → solution method → results (table + figure + numbers) → result analysis (2-3 paragraphs of interpretation)

**Sensitivity Analysis**: parameter sensitivity + robustness + error analysis

**Model Evaluation**: Strengths 3-5 points + Weaknesses 2-3 points (honest) — do not write token weaknesses like "limited by time"

### Step 4: Build bibliography

Follow the `<references_workflow>` in `_utils/writing_rules.md`.

Search DBLP/CrossRef for real BibTeX. `\usepackage[hidelinks]{hyperref}`.

**⛔ Use scholar_fetch.py for ALL reference retrieval. NEVER fabricate BibTeX from memory.**

**⛔ Citation key rule: when writing body text, citation keys MUST contain descriptive keywords, format: `author_year_topic_keywords`.**

Example: `\citep{wang_2023_supply_chain_resilience}` not `\citep{wang2023supply}`.

If unsure about author/year, use `TODO__` prefix: `\citep{TODO__digital_economy_spatial_spillover}`.

```bash

# Step 4a: Collect all cited keys

grep -roh '\\cite[tp]*{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null \

  | grep -oP '\{[^}]+\}' | tr -d '{}' | tr ',' '\n' | sed 's/^ *//;s/ *$//' | sort -u > _tmp/_cited_keys.txt

echo "Cited keys: $(wc -l < _tmp/_cited_keys.txt)"

# Step 4b: Fetch BibTeX using descriptive keywords from citation keys

PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python

while IFS= read -r key; do

    query=$(echo "$key" | sed 's/^TODO__//; s/_/ /g')

    echo "--- Fetching: $key (query: $query) ---"

    $PYTHON "$SCHOLAR_SCRIPT" bibtex "$query" --max 3

    sleep 0.5

done < _tmp/_cited_keys.txt

```

For each result:

1. Check `match_label`: `"good"` → use directly. `"partial"` → verify title. `"low"` → likely wrong paper, re-search or use WebSearch.

2. `match_score` < 0.3 means the result probably doesn't match your citation intent. Do NOT blindly use it.

3. Replace citation keys in .tex files with actual keys from BibTeX entries.

4. Mark `bibtex_source=auto` with `% [VERIFY]`. Mark `match_label="low"` with `% [LOW_MATCH]`.

### Step 4.5: De-AI polish

See `<de_ai_polish>` in `_utils/writing_rules.md`.

### Step 4.6: Write Summary Sheet LAST

⛔ **MANDATORY: NOW write the Summary Sheet** (replace the placeholder from Step 3).

Read `RESULTS.md` and all section .tex files first to extract actual numerical results. Then write the Summary Sheet using only those verified numbers — do not invent any value.

Structure: problem statement (1-2 sentences) → method (2-3 sentences) → key results with specific numbers (3-4 sentences) → conclusion (1-2 sentences). 300-400 words, one page. Self-contained — readers should grasp the entire paper from this page alone.

⛔⛔ **Bold the key content in the Summary Sheet (Summary Sheet only, LaTeX `\textbf{}`)**: judges skim the summary; bolding the core method and result is a plus. **Bold ONLY these three "conclusion anchors":**

1. **Key result numbers** (final answers): e.g. `\textbf{2376.8}`, `\textbf{98.7\%}`, `\textbf{12.4 km}` (note `%` must be `\%` in LaTeX)

2. **Core method/model names**: e.g. `\textbf{NSGA-II}`, `\textbf{XGBoost}` — bold each name only at its first/conclusion appearance, not every mention

3. **The single most critical noun** in a conclusion sentence

⛔ **Bold discipline (avoid over-bolding — less is more):** 1~3 bolds per paragraph, ≤ 12 total; never bold whole sentences / background / connectives / a repeated method name; use `\textbf{}` only (NOT markdown `**`); do not touch the `\textbf{Keywords:}` label; `\textbf{}` only wraps text — numbers must still be pulled truthfully from the body, never invented for emphasis. Example: `We build an \textbf{NSGA-II} model, achieving optimal cost \textbf{2376.8}, a \textbf{12.3\%} reduction.`

⛔⛔ **Break the Summary Sheet into per-problem paragraphs — never cram every problem into one block.** Paragraph skeleton:

- Paragraph 1: background + overall modeling approach

- Then one paragraph per problem, **each starting with "For Problem 1 / For Problem 2 / ..." and standing alone** (method + specific numbers)

- Final paragraph: model evaluation / strengths / outlook

- **Separate paragraphs with a blank line.** A judge must be able to locate each problem's answer at a glance.

⛔ **Hard rule: a single paragraph must NOT contain two or more "For Problem" openers.** Examples:

```text

(correct ✅ — each "For Problem X" is its own paragraph, blank line between)

This paper addresses ... by building ... models.

For Problem 1, we first ... and adopt ...; the optimal solution is ..., with fitness 0.917.

For Problem 2, we construct ...; MAPE drops from 29.48% to 14.93%.

For Problem 3, ...; predicted values are 952.8, 1570.5, 11030.9.

Sensitivity analysis shows ...; the model evaluation indicates ....

```

```text

(wrong ❌ — Problems 2 and 3 crammed into one paragraph)

For Problem 2, MAPE 14.93%. For Problem 3, predicted values are 952.8, 1570.5.

```

After writing, grep the body chapters for every number you used to verify it actually appears:

```bash

for n in $(grep -oE '[0-9]+\.[0-9]+' paper/sections/0_summary.tex | sort -u); do

  grep -q "$n" paper/sections/*.tex RESULTS.md || echo "⛔ Summary number $n not in body: invented?"

done

```

⛔ **Then run the paragraph self-check (detect → fix → recheck loop; use `python`, not `python3`):**

```bash

python - paper/sections/0_summary.tex <<'PY'

import re, sys

path = sys.argv[1]

try:

    text = open(path, encoding="utf-8", errors="ignore").read()

except FileNotFoundError:

    print(f"⚠ {path} not found — locate the Summary Sheet file and rerun with its actual path"); sys.exit(0)

bad = []

for i, para in enumerate(re.split(r"\n\s*\n", text), 1):

    if len(re.findall(r"[Ff]or [Pp]roblem", para)) > 1:

        bad.append((i, para.strip()[:80]))

if bad:

    print(f"❌ {len(bad)} paragraph(s) cram multiple 'For Problem' openers — split each into its own paragraph:")

    for i, snip in bad:

        print(f"  para {i}: {snip}...")

    sys.exit(1)

print("✓ Summary Sheet is split per problem")

PY

```

⛔ **Loop rule: if the check exits 1, go back to `paper/sections/0_summary.tex`, insert a blank line before each "For Problem X" so it becomes its own paragraph, then rerun the check until it prints "✓ Summary Sheet is split per problem" before moving on.**

### Step 5: Final verification

```bash

bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/

```

**⛔ Capability-claim gate (full-chain contract, run before AND after writing; zero-cost, both modes):** The paper must not claim capabilities that failed acceptance in the coding stage.

```bash

FAST_MODE=0; grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null && FAST_MODE=1

python _utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE

PCC=$?   # 0=all passed 1=some capability FAIL/PENDING (must not finalize) 2=no audit, skip

```

> `PCC=1`: a capability failed acceptance in comp-code — go back and make it truly PASS before finalizing. WARN (a not-passed capability's name appears in the body): confirm you are not writing an undone capability as done (OK only if honestly stated under Limitations/Future work). Contract chain: problem-analysis defines it → modeling claims each → code implements & audits → paper reports only what passed.

Also check:

```bash

echo "=== Section character counts ==="

total=0

for f in paper/sections/*.tex; do

    chars=$(wc -c < "$f")

    total=$((total + chars))

    echo "  $(basename $f): $chars chars (~$(echo "scale=1; $chars/2200" | bc) pages)"

done

echo "  Total: $total chars (~$(echo "scale=1; $total/2200" | bc) pages)"

```

- Total chars ≥ MAX_PAGES × 1800 (expand thinnest chapters if not)

- Any sub-problem chapter <8000 chars (~4 pages) needs expansion

- Summary Sheet exists (MCM/ICM critical)

- All figures/*.pdf and TABLE files (PDF mode .tex / Word mode .md) referenced in sections/body

- No `\input{figures}` patterns

- Team Control Number placeholder present

**⛔ Page count pre-check (MUST pass before finishing):**

> ⛔ **MAX_PAGES counts BODY pages only** (chapters 1 → conclusion, including figures/tables).

> Does **NOT** include abstract / TOC / references / **appendix code**.

> Check scans `paper/sections/*.tex` only; appendix code goes in `paper/appendix/` (separate, no page cap).

```bash

source .env_skill 2>/dev/null || true

echo "=== Body page pre-check (paper/sections/ only, NOT appendix) ==="

# 1. sections/ must NOT contain code blocks (lstlisting / verbatim / minted)

code_in_body=0

for f in paper/sections/*.tex; do

    [ -f "$f" ] || continue

    if grep -qE '\\begin\{(lstlisting|verbatim|minted|python|matlab)\}' "$f" 2>/dev/null; then

        code_in_body=$((code_in_body + 1))

        echo "  ⚠️ $f contains code blocks — code must go in paper/appendix/"

    fi

done

if [ "$code_in_body" -gt 0 ]; then

    echo "⛔ CRITICAL: $code_in_body body section(s) contain code blocks. Move to paper/appendix/"

    echo "  Reason: page estimate uses chars/2200, code is line-heavy but low density → est_pages inflated, actual body thin"

fi

# 2. Body char count + page estimate

total_chars=0

for f in paper/sections/*.tex; do

    [ -f "$f" ] || continue

    chars=$(wc -c < "$f")

    total_chars=$((total_chars + chars))

done

est_pages=$((total_chars / 2200))

echo "Body chars: $total_chars, Est pages: ~$est_pages, Target: ≥ ${MAX_PAGES:-25} pages"

# 3. Appendix separately (info only)

if [ -d paper/appendix ]; then

    app_chars=0

    for f in paper/appendix/*.tex; do

        [ -f "$f" ] || continue

        app_chars=$((app_chars + $(wc -c < "$f")))

    done

    app_pages=$((app_chars / 2200))

    echo "(Appendix chars: $app_chars, ~$app_pages pages — NOT counted in MAX_PAGES)"

fi

```

If estimated pages < 80% of MAX_PAGES, expand the thinnest chapters before finishing.

⛔ **Body vs Appendix file convention**:

- `paper/sections/` — body chapters only (intro / methods / results / discussion / conclusion)

- `paper/appendix/` — code listings / long data tables / solver logs / supplementary derivations / pseudocode

- Putting code in `sections/` inflates est_pages but body is actually thin

**⛔ Figure embedding verification (must pass before finishing):**

```bash

echo "=== Figure embedding check ==="

missing=0

for pdf in figures/*.pdf; do

    [ -f "$pdf" ] || continue

    bn=$(basename "$pdf")

    if ! grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null; then

        echo "MISSING: $bn not embedded in any section"

        missing=$((missing + 1))

    fi

done

echo "Missing: $missing"

# ⛔ Adjacent-figure check (prevents "two figures stuck together with no text between")

echo "=== Adjacent-figure check ==="

for f in paper/sections/*.tex; do

    [ -f "$f" ] || continue

    # ⛔ Build the backslash via chr(92)+re.escape: this box's bash heredoc eats bare

    #    backslashes, so a literal \\end would corrupt into \end and raise re.error

    python - "$f" << 'PYEOF'

import re, sys

t = open(sys.argv[1], encoding='utf-8', errors='ignore').read()

BS = chr(92)

END = re.escape(BS + 'end') + r'\{(?:figure|table)\}'

BEG = re.escape(BS + 'begin') + r'\{(?:figure|table)\}'

bad = 0

for g in re.finditer(END + r'(.*?)' + BEG, t, re.DOTALL):

    body = re.sub(r'%[^\n]*', '', g.group(1))   # strip comments

    body = re.sub(r'\s+', '', body)             # strip whitespace

    if len(body) < 150:                         # real prose between < 150 chars => perfunctory (adjacent or one-liner)

        bad += 1

if bad:

    print("  X %s: %d figure gaps with too little prose (<150 chars, likely perfunctory/one-liner) — each figure needs full analysis: concrete numbers + comparison/trend + inference/linkage, never a lone sentence" % (sys.argv[1], bad))

PYEOF

done

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

        if ! ls figures/${name}.pdf figures/${name}.png 2>/dev/null | head -1 | grep -q .; then

            echo "❌ MANIFEST: $name file missing"

            manifest_missing=$((manifest_missing + 1))

        elif ! grep -rqE "${name}\.(pdf|png)" paper/sections/ paper/main.tex 2>/dev/null; then

            echo "❌ MANIFEST: $name exists but not referenced in paper"

            manifest_missing=$((manifest_missing + 1))

        fi

    done

    if [ "$manifest_missing" -gt 0 ]; then

        echo "⛔ FIGURE_MANIFEST audit failed ($manifest_missing missing)"

        missing=$((missing + manifest_missing))

    fi

fi

echo "Total missing: $missing"

```

**⛔ Do NOT proceed to Step 6 until missing = 0.**

### Step 6: Compliance check

Page count, Summary Sheet, Team Control Number, anonymous, APMCM commitment letter not in PDF, code appendix.


## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：论文模板版本、TeX Live 版本、引用条目数。

## Key Rules

- Summary Sheet is everything — invest the most effort here

- Specific numbers — never say "good results", give exact values

- Figure paths: `../figures/xxx.pdf`

- ⛔⛔ **Tables**: `[H]` float specifier **ONLY** (not `[!ht]` / `[ht]` / `[htbp]` / `[tb]` / `[b]` / `[p]`). (Figures use `[H]` too — pinned in place right under their lead-in text to prevent multi-figure stacking; see the interleaving rules above.)

  All competition templates load `\usepackage[section]{placeins}` which forces `\FloatBarrier` at end of each `\section`, blocking float migration across sections. With `[!ht]` and a tall table + lead-in text, LaTeX is forced to leave the section heading + lead-in text at top of page and dump the table at section bottom → **half a blank page above the table**. Symbol tables / notation tables are the most common victims. Solution: use `\begin{longtable}` (non-floating) for symbol tables; use `\begin{table}[H]` (forces in-place) for short result tables.

- After writing, run this grep audit:

  ```bash

  BAD=$(grep -rEn '\\begin\{table\}\[(!?ht?|htbp|tb|b|p)\]' paper/sections/ 2>/dev/null)

  if [ -n "$BAD" ]; then

      echo "❌ Found floating table specifiers (may cause blank-page-above-table):"

      echo "$BAD" | head -5

      echo "   Fix: change to \\begin{table}[H] or \\begin{longtable}"

  fi

  ```

- Wide tables (≥6 cols): wrap with `\resizebox{\textwidth}{!}{...}`

- Narrow tables (≤4 cols): do not use `\resizebox`

- Code appendix: complete runnable code

- No team info — use placeholders

- `\usepackage[hidelinks]{hyperref}`

- Primary output: `paper/` directory, temp files: `_tmp/`

- ⛔ **This step only writes paper .tex files. Do NOT regenerate figure PDFs, modify code/*.py, or re-run analysis scripts.** Figures and data are already produced by prior steps (paper-figure / comp-code) — just reference them

- Large files: Bash heredoc

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

