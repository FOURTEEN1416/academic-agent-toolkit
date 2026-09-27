---

name: comp-paper-en

description: "Mathematical modeling competition paper writing in English. Supported contests (canonical comp_rules IDs): comp_mcm (MCM/ICM), comp_apmcm, comp_certcup_en; comp_shuwei_en is a declared template capability gap. Generate complete LaTeX paper following COMAP-style format. 区别于 comp-compile-en：本技能只写正文并产出 LaTeX 源，不负责编译。"
argument-hint: [competition-type]

allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch

---

# Competition Paper Writing (English)

Write a competition paper: **$ARGUMENTS**

## ⚡ Fast-mode detection (run first)

```bash

FAST_MODE=0

grep -q 'MH_FAST_MODE=1' AGENTS.md 2>/dev/null && FAST_MODE=1

echo "FAST_MODE=$FAST_MODE"

```

**If `FAST_MODE=1` (speed priority):** still MUST produce a complete paper (all chapters present, every sub-problem covered, figures embedded per manifest, body pages within the dispatched page cap, cite real data — no fabrication, pass output verification), but **SKIP**: line-by-line figure-text number consistency re-checks, source-traceback audits, and repeated polish/rewrite for minor issues. Write it once, complete in structure and content. **If `FAST_MODE=0` (default):** run all consistency checks as usual.

## Constants (transcribed verbatim from the dispatched `contest_profile`)

The execution session context carries a `contest_profile` JSON (issued by the engine from `comp_rules.json`; `contest_profile: null` means this workflow has no contest identity). Transcribe the fields below **verbatim** into shell variables once, then only consume them — never derive, prefix, rename, or guess them from AGENTS.md, filenames, free text, or shell defaults:

> Transition channel: program-side injection (interface request filed with B — contest id / page cap / scope / status read from the bound snapshot and fed into the actual command environment) has **not landed yet**; until it does, this verbatim transcription is performed by the model. It is a pending interface, not a completed program path — never describe it as automated.

- **CONTEST_ID** ← `contest_profile.contest_id` — canonical `comp_*` key of the contest archive (e.g. `comp_mcm`, `comp_apmcm`). There is no `comp_icm`: ICM runs under `comp_mcm`. Transcribe it only when `contest_profile.status == "bound"`; `pending_binding` or absent ⇒ no valid contest identity — stop and report (待核实), never guess, no default.

- **PAGE_CAP** ← `contest_profile.gate_page_cap` — this task's operative page-gate cap. A ceiling must not be exceeded; **there is no page floor and no default value**. Numeric rules live in the archive, not in this skill. Absent ⇒ this contest has no operative page contract (or a historical ruling was deliberately not inherited): page cap unknown → report 待核实.

- **PAGE_SCOPE** ← `contest_profile.gate_page_scope` — `body` (cap counts body chapters; appendix/references separate) or `total` (cap counts the whole PDF). Never merge the two counts.

- **PAGE_CAP_STATUS** ← `contest_profile.page_cap_status` — `official_verified` / `task_override` / `unverified`. An `unverified` (unknown-provenance) cap does **not** create a default hard page limit and is never presented as a proven official rule: unknown only blocks the corresponding compliance verdict (it neither passes it nor invents a limit). A cap is enforced as hard only when `official_verified`, or when separately identified as an explicit task authorization (`task_override` / explicit task cap) — never rebrand an unknown official rule as a task override.

- **EDITION** ← `contest_profile.edition` — may be absent; absence is reported via `missing_fields`, never inferred.

- **CUSTOM_REQUIREMENTS**

## Inputs

1. PROBLEM_ANALYSIS.md, MODELING_REPORT.md, RESULTS.md

2. figures/, code/

## Content map (four categories — load only what applies)

- **通用方法 Generic method** (contest-independent): paper structure semantic slots, figure interleaving/embedding rules, `<exemplar_depth>` writing depth, bibliography workflow, de-AI polish, Summary Sheet method, capability-claim gate, universal paper-stage audit.
- **赛事专属 Contest-specific**: comes from the dispatched `contest_profile` (identity, page cap/scope, `rules_highlights`, `compliance`) plus `references/contest_profiles.md` — **read only the entry matching `CONTEST_ID`**, never another contest's entry and never the whole file set.
- **任务裁决 Task adjudication**: Step 1 template selection (canonical-ID case branches + capability-gap errors), Step 4.7 AI-use statement resolution (evidenced → produce; absent → 待核实), page pre-check scope resolution.
- **经验建议 Empirical advice, non-binding**: the per-chapter depth breakdown and chars/page estimation are marked empirical; they never create a quota and never override the dispatched cap.

## Load shared rules

```bash

cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md

```

## MCM/ICM Paper Structure

Competition papers do **not** generate a Table of Contents in this product. Build an adaptive
section sequence from the problem dependency chain: summary → concise problem framing → necessary
assumptions/notation → content-named model chapters → model-specific or cross-model validation →
conclusions/evaluation → references → appendix. These are semantic slots, not mandatory chapter names.

**⛔ The template section files are a safe starter skeleton, not a mandatory chapter order.**
Rename/add `paper/sections/*.tex` around the actual models and update `paper/main.tex` `\input{}` lines
accordingly. Keep the document class, contest cover/summary, anonymity and page settings unchanged;
do not leave an empty section referenced by `main.tex`.

**⛔⛔ HARD RULE: each sub-problem flow chart must stay beside the model it explains — never pile all of them into one overview section.**
Filenames do not matter. Each flow chart needs nearby model-specific lead-in and interpretation, and one file must not stack several large flow charts without substantive text between them.

```

Summary Sheet (1 page — most important page in the entire paper)

1. Introduction

2. Assumptions and Justifications

3. Notations

4. Model Design and Solution (one chapter per sub-problem; no per-chapter page quota)

5. Sensitivity Analysis

6. Model Evaluation (Strengths + Weaknesses)

7. Conclusions

References

Appendix A: Code

```

Page counts are intentionally absent from this skeleton (a Table of Contents is not generated either): no per-chapter page rule is evidenced in the archive, and writing one here would create a fake quota. Depth guidance lives in `<exemplar_depth>` as marked-empirical advice.

## ⛔⛔⛔ Output Contract (highest priority)

- **This skill always produces the LaTeX deliverable set**: `paper/main.tex` (≥ 5KB) + `paper/sections/*.tex` + `paper/references.bib` — exactly what the workflow template's `output_contract` verifies at `finish`.

- **`params.output_format=docx` does NOT change this step's product**: the engine appends a downstream `docx-export` step that converts the compiled paper. The LaTeX sources are contract-required legitimate intermediates — **never delete or skip them "for DOCX export"**. (The main.md-only product belongs to the standalone `comp-paper-en-docx` skill, not to this one.)

产出结构、存在性和最低完整性由 `finish` 按模板中的 `output_contract` 自动核验；修复返回的具体问题，不复制执行验证脚本。

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

# Template selection: the canonical CONTEST_ID transcribed verbatim from
# contest_profile.contest_id (a comp_rules.json top-level key). Never guessed from
# free text, AGENTS.md, or filenames — substring matching once sent APMCM into the
# MCM template because "apmcm" contains "mcm". Bare names like "mcm"/"icm"/"apmcm"
# are NOT archive IDs (there is no comp_icm; ICM runs under comp_mcm) and are rejected.
if [ -z "$CONTEST_ID" ]; then
    echo "⛔ CONTEST_ID is empty: contest_profile was not dispatched (contest_profile=null)." >&2
    echo "   This skill only runs inside a comp_* workflow; refusing to guess." >&2
    exit 1
fi
case "$CONTEST_ID" in

    comp_mcm)

        echo "Using MCM/ICM template (mcmthesis)"

        cp "$TMPL_BASE/mcm/"* paper/ 2>/dev/null

        ;;

    comp_certcup_en)

        # certcup_en has its own standalone skeleton (archive comp_certcup_en:
        # template_cls=article; "article 或 mcmthesis" both sanctioned). It does NOT
        # copy the mcm/ skeleton — that skeleton carries its home contest's own
        # identity settings (control number / problem / summary sheet), which must
        # never reach another contest's deliverable.
        echo "Using certcup_en standalone article skeleton (archive: template_cls=article, Summary standalone page)"

        cp "$TMPL_BASE/certcup_en/"* paper/ 2>/dev/null

        ;;

    comp_apmcm)

        echo "Using APMCM template (apmcmthesis)"

        cp "$TMPL_BASE/apmcm/"* paper/ 2>/dev/null

        ;;

    comp_shuwei_en)

        echo "⛔ Capability gap: comp_shuwei_en (archive class: article) has no starter skeleton" >&2

        echo "   in _templates (mcm/ = mcmthesis, apmcm/ = apmcmthesis). Reporting the gap and" >&2

        echo "   stopping — silently substituting another contest's template is forbidden." >&2

        exit 1

        ;;

    *)

        echo "⛔ Unknown CONTEST_ID: '$CONTEST_ID' is not an archive key this skill supports" >&2

        echo "   (comp_mcm | comp_apmcm | comp_certcup_en; comp_shuwei_en = declared capability gap)." >&2

        echo "   Refusing to guess the competition; report the capability gap, never fall back to MCM." >&2

        exit 1

        ;;

esac

[ -f paper/main.tex ] && echo "Template copied: $(wc -l < paper/main.tex) lines" || echo "ERROR: template not found!"

```

`comp_mcm` uses `mcmthesis.cls` (in its own template folder). `comp_certcup_en` has its own standalone `certcup_en/` skeleton (archive `template_cls: article`; Summary on a standalone page; carries no other contest's cover or control-number elements). `comp_apmcm` uses `apmcmthesis.cls`. `comp_shuwei_en` (archive class: article) is a declared capability gap — no skeleton, report and stop; no silent substitution.

**⛔ Reused-skeleton content check (mandatory after `cp`)**: a shared document class does **not** carry another contest's identity. Whenever this skill copies a skeleton into `paper/`, verify and replace/remove every other contest's cover element, control-number/problem setting (`tcn = …`, `problem = …`, submission sheet), and contest declaration in `paper/main.tex` before writing — per the current contest's own rules. This check stays mandatory even though every current route copies a home or standalone skeleton: it is defense in depth (the `certcup_en` skeleton only became standalone on 2026-09-27; before that its copies silently carried the source contest's identity settings). Leaving another contest's cover, control number, or declaration in the deliverable is a compliance failure.

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

**MCM/ICM paper skeleton (page ceiling: PAGE_CAP binds as hard only when its status is `official_verified` or an explicit task authorization; an `unverified` cap is not executed as a hard limit. The per-section depth breakdown below is 经验建议 — empirical guidance from Outstanding papers, not an official rule and not a quota)**:

- Summary Sheet (1p): 300-400 words, self-contained with specific numerical results. Structure: problem statement (1-2 sentences) → method (2-3 sentences) → key results (3-4 sentences with numbers) → conclusion (1-2 sentences)

- Introduction (2p): problem context + literature + approach overview

- Assumptions (0.5p): each assumption with justification (not just a bullet list)

- Notations (0.5p): **use non-floating table** (`\begin{center}\begin{tabular}` + `\captionof{table}{}`, NOT `\begin{table}`). This prevents the section title and table from being split across pages. Keep to 15-20 symbols max.

- Each sub-problem: model formulation (with derivation) + solution method (with algorithm) + results with table+figure+numbers + analysis (interpretation + comparison). No per-sub-problem page quota — depth follows the modeling; only the dispatched PAGE_CAP binds.

- Sensitivity Analysis (2-3p): ≥2 key parameters, each with variation plot + analysis paragraph

- Model Evaluation (1.5p): 3-5 strengths + 2-3 weaknesses (honest, not token weaknesses) + generalization discussion

- References + Appendix

For `comp_apmcm` and `comp_certcup_en`: same structure, same dispatched PAGE_CAP. The archive evidences no "25-30 pages / First Prize" target, so no such target exists here.

</exemplar_depth>

After each chapter, check chars:

```bash

chars=$(wc -c < "paper/sections/current_chapter.tex")

echo "Current chapter: $chars chars"

# English LaTeX ≈ 2000-2500 chars/page — estimation only. Use it to notice a section

# that is clearly underdeveloped relative to its modeling content. It is NOT a

# per-chapter quota: length follows modeling and evidence, never a page target.

```

**Expansion strategies** (not padding — substantive content):

- Formula without derivation → add step-by-step derivation with physical meaning

- Result with only "as shown in Table X" → add 2-3 paragraphs (what numbers mean, comparison with expectations, why this result makes sense)

- Algorithm as pseudocode only → add explanation of key steps, complexity analysis, convergence discussion

**Summary Sheet** is the most important page — invest the most effort here. Must be self-contained, one page, ≥300 words, with quantitative results.

**Each sub-problem chapter**: model formulation → solution method → results (table + figure + numbers) → result analysis (2-3 paragraphs of interpretation)

**Sensitivity Analysis**: parameter sensitivity + robustness + error analysis

**Model Evaluation**: Strengths 3-5 points + Weaknesses 2-3 points (honest) — do not write token weaknesses like "limited by time"

#### ⛔⛔ Optimization / programming models: state decision variables, objective, and constraints in separate blocks

**When this applies**: the model contains `\min` / `\max`, or the problem asks for something optimal
(minimum cost, maximum coverage, siting, assignment, scheduling, routing, blending). **Does not apply**
to statistical modeling (index systems / DEA / PCA / regression / forecasting) — those follow the
"theoretical basis → formulas → parameters" order above.

> The three elements of an optimization problem are **decision variables, objective function, and
> constraints**. Strong papers usually expose them in that recognition order; the hard requirement is
> that each element is clearly distinguishable. Melting them into one blob of formulas is the fastest
> way for a judge to conclude you never worked out what you were deciding.

**Decision variables → objective → constraints → domains is the preferred reading order, not a mandatory set of subsections.** Complex models need separate blocks; a small model may use one paragraph and one aligned display.

**⛔ Subsection titles inside a sub-problem chapter must name the model.** Optimization chapters
slide into placeholder titles that tell a judge nothing while skimming:

| ❌ Placeholder | ✅ Informative |
|---|---|
| Model Formulation | A 0-1 Integer Programming Model for Service-Station Siting |
| Model Solution | Branch-and-Cut Solution and the Optimal Siting Plan |
| Sensitivity Analysis (as a subsection inside a sub-problem) | Effect of the Budget Cap on the Number of Stations Opened |

⛔ The table only says that titles must carry information; it does not prescribe chapter numbers.
Restatement, sensitivity, and evaluation are available semantic roles, not mandatory verbatim chapter
names. Keep them separate only when the content and dependency chain justify a separate chapter.

**① Decision variables** — state five things: **symbol, meaning, type, index range, and why that type**.
Binary variables must be written as a piecewise definition spelling out what each value means in the
real problem; never just `$y_j \in \{0,1\}$`:

```latex
Let $x_{ij}$ indicate whether demand point $i$ is assigned to station $j$. Assignment either holds
or it does not — there is no partial assignment — so $x_{ij}$ is binary:
\begin{equation}
x_{ij}=\begin{cases}
1, & \text{demand point } i \text{ is served by station } j,\\
0, & \text{otherwise},
\end{cases}\qquad i=1,\dots,m;\ j=1,\dots,n
\end{equation}
```

⛔ **Never skip the type justification**: why integer (people/vehicles are indivisible), why binary
(open or not, no middle state), why continuous (an arbitrarily divisible flow or ratio). Writing
"$x_j$ is an integer" with no reason reads as not having thought it through.

**② Objective function** — its own display equation, immediately followed by one sentence on where
the objective comes from (quote the problem statement; keep it consistent with the objective-traceability
table in `MODELING_REPORT.md`):

```latex
The problem requires "minimizing total construction and operating cost while covering every demand
point", so total cost is minimized:
\begin{equation}
\min\ Z=\sum_{j=1}^{n} f_j y_j+\sum_{i=1}^{m}\sum_{j=1}^{n} c_{ij} d_i x_{ij}
\end{equation}
where the first term is the fixed construction cost of the stations and the second is transport cost.
```

For multi-objective models, state how the objectives are combined (weighting / lexicographic / Pareto),
how the weights were set, and how units were normalized.

**③ Constraints** — introduce with `s.t.`, list them vertically, **number each one, and give every
constraint its real-world meaning**:

```latex
\begin{equation}
\begin{aligned}
\text{s.t.}\quad
& \sum_{j=1}^{n} x_{ij}=1, && i=1,\dots,m\\
& \sum_{i=1}^{m} d_i x_{ij}\le Q_j y_j, && j=1,\dots,n\\
& x_{ij}\le y_j, && \forall i,j
\end{aligned}
\end{equation}
```

Then explain: the first line forces every demand point to be served by exactly one station
(the problem forbids split deliveries); the second caps the demand assigned to station $j$ at its
capacity $Q_j$; the third prevents assigning demand to a station that was never opened.

⛔ Formulas with no accompanying meaning leave the judge unable to tell whether you missed a
constraint — this is the single most common deduction.

**Constraint-type checklist (for finding gaps, not a requirement to have all of them)**: demand
coverage / budget or resource cap / per-site capacity / fixed total / at-most-or-at-least-k /
mutual exclusion / logical linking (big-M) / time windows / flow balance / degree constraints and
subtour elimination.

⛔ **Linearization tricks must be explained.** For big-M, piecewise linearization, absolute-value
conversion, or turning a `max` into constraints, say what the nonlinear form was and why the
rewrite is equivalent. Example: $x_j\le My_j$ forces $y_j=1$ whenever $x_j>0$, which turns the
fixed cost $f_jy_j$ — incurred only when the station opens — into a linear term. Justify the
magnitude of $M$ (derive it from a data upper bound; do not write 99999).

**④ Variable domains + model classification** — list non-negativity / integrality / bounds on their
own line, then add a paragraph stating the problem class (LP / ILP / MILP / NLP / multi-objective /
dynamic programming), **the size** (number of variables and constraints, computed from the index
ranges), and **why this solution method** (exact solver vs. heuristic; if heuristic, why an exact
solve is not viable — NP-hardness, size blow-up).

**⛔ Anti-pattern** (the judge cannot tell what you are deciding):

```latex
We build the optimization model $\min\sum c_{ij}x_{ij}+\sum f_jy_j$ subject to
$\sum_j x_{ij}=1$, $\sum_i d_ix_{ij}\le Q_j$, $x_{ij},y_j\in\{0,1\}$, and solve it with Gurobi.
```

Problems: none of $x_{ij}$, $y_j$, $c_{ij}$, $f_j$, $Q_j$ is defined; no reason given for binary;
neither constraint is tied to a sentence in the problem statement; no model class or size;
"solve it with Gurobi" never says why an exact solve is possible.

**⛔ Consistency with upstream**: the three elements must match `MODELING_REPORT.md` — the objective
must appear in its objective/constraint traceability table, and the number of constraints must not
fall below the key constraints registered during modeling. Do not invent a constraint that modeling
never had, and do not quietly drop one that it did.

#### ⛔⛔ Solution section: argue why the solution is credible, do not recount how the algorithm works

A modeling-contest paper is judged on the **model** and the **solution**, not on algorithm exposition.
Judges care whether the model is right and whether the solution can be trusted — not whether you can
explain how a genetic algorithm works. **Keep algorithm description short: name, one clause on its
role, citation.**

| Write this (the bulk of the section) | Not this (textbook material, one clause at most) |
|---|---|
| Why this solution method (size / NP-hardness / whether an exact solve is viable) | How GA selection, crossover, and mutation operate |
| Evidence the solution is credible: cross-validation across methods, comparison against a bound, constraint checks | Derivation of the Metropolis criterion in SA |
| Key implementation choices and their rationale (decomposition, linearization, seeding) | Line-by-line pseudocode, $O(n^2)$ derivations |
| How tight the constraints are at the solution (which is near-active, how much slack) | History and literature of the algorithm family |

**What must come across — how you arrange it, and whether it needs a section of its own, is
determined by the problem:**

- why this solution method (size, NP-hardness, whether an exact solve is viable)
- key implementation choices and their basis (decomposition, linearization, multi-start seeding)
- **evidence the solution is credible**: whether independently-motivated methods agree (and the
  relative spread), comparison against a bound or a no-action baseline, constraint-by-constraint
  verification, which constraint is nearest to active and how much slack remains

⛔ **Do not impose a fixed section name or a fixed number of points.** Some problems need a single
paragraph (small model, stock solver returns the answer); others warrant a section of their own.
The only test is whether a reader ends up convinced the solution is right. An empty section
heading is worse than no heading.

⛔ The one hard ratio: **words spent on "why the solution is credible" must not fall below words
spent on "how the algorithm works".** The former is what judges read; the latter is textbook material.

⛔ **Do not add pseudocode or complexity analysis to pad length** — that is a CS-paper convention.
In a modeling paper they belong in the appendix: put algorithm parameters (initial temperature,
cooling rate, iteration count, solver time limit, random seed) in an appendix table, and keep one
sentence in the body: "the full pipeline runs under a fixed random seed and is reproducible;
parameters are listed in Appendix X."

⛔ **Honesty boundary**: an analytic or relaxation bound **is not a feasible solution**. The gap
between it and the optimum only confirms the optimum is not anomalously low — it **must not** be
presented as remaining room for improvement.

⛔ **Expand toward modeling depth and result credibility, never toward algorithm exposition.**
When a section is thin, add: justification of each assumption, refinement of definitions, comparison
against baselines and expectations, sensitivity and robustness, constraint-tightness analysis, and
the operational meaning of the conclusions. Test: if the body spends more words on "how the algorithm
works" than on "why the solution is credible", the emphasis is inverted.

**⛔⛔ The Innovations subsection is required, not optional.** Real runs routinely ship only strengths
and weaknesses, leaving judges to hunt for what was actually new. Write 2-4 items, each as
"conventional approach → what this paper does → what difference it makes", kept at the **modeling**
level (not the tooling level).

- ✅ Real: redefining the satisfaction rate against a stock-out floor, avoiding the degenerate case
  where the naive definition makes every station fully satisfied; injecting the Sub-problem 1 score
  into the Sub-problem 2 objective so the two sub-problems are genuinely coupled rather than adjacent
- ❌ Filler: implemented in Python; compared three algorithms; clean figures; "the model accounts for
  many factors"
- ⛔ Test: if the claim would hold for any other problem ("we used machine learning", "we ran a
  sensitivity analysis"), it is not an innovation for this problem — cut it. Two substantive items
  beat five hollow ones.

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

**What goes in each paragraph — hard criteria below. This is what separates an award-level summary
from a generic one.**

| Sentence | Content | Optional? |
|---|---|---|
| 1st | The problem's background, in one sentence — do not elaborate | Required |
| **2nd** | **What this paper did** — what process was analyzed, which factors were jointly considered, what model was built | **Most important; never omit** |
| 3rd | Real-world significance / where the model is applied | Optional |

⛔ The 2nd sentence is the face of the whole summary — a judge reads it to decide whether the team
actually thought the problem through. It must convey the **analysis and the scope considered**, not
just a model name. Pattern: `This paper studies …, analyzes the … process, jointly considers …,
builds a … model, and applies it to …`

**[Middle paragraphs] one per sub-problem, each carrying all three elements:**

1. **Which problem** — open by naming the sub-problem this paragraph handles
2. **What method** — the governing law/principle relied on, how the data was processed, how it was
   discretized, how it was solved. Chain it with *first … then … finally …* so the judge sees the path
3. **What result** — specific numbers, plus what analysis was run on them (error, verification, comparison)

⛔ **Name the methods down to the level of theorems and conditions** — not "a model was built".
What should appear: the governing laws (Fourier's law, conservation of energy, Newton's law of
cooling), the boundary-condition types (Dirichlet / Robin, coupling conditions), the discretization
and solver (implicit backward difference, Thomas algorithm, enumeration to fix a coefficient), and
parameter values (initial temperature 37 °C). These specifics are the evidence that the work was
actually done; "built a model and solved it" is something any team can write.
⛔ **Point at the output file when there is one** (`see problem1.xlsx`) — that is how a judge
confirms you actually computed it.

⛔ **Be economical** — carrying all three elements is not licence to ramble. A model paragraph covers
the problem, the full method chain, and the result with its error analysis in roughly 150 words;
deleting any clause loses information. That is the standard.

**[Final paragraph] optional, but write it whenever there is sensitivity analysis, verification,
or a generalization worth stating** — say what the model is sensitive to, what it is not, and why
that matters. ❌ Filler: "The model has good practical value and generalizability."

### Step 4.7: AI tool usage statement (resolved from the contest profile; never silently skipped)

**Resolve the obligation first (任务裁决 — this resolution runs even when the user disabled disclosure):**

1. **Evidenced provision** — the archive for `CONTEST_ID` (via `contest_profile.compliance` / constraint items with confirmed `status` + `source_ids`) requires an AI-use statement: produce it **in the official format for that contest** — placement, content limits, and naming exactly as the constraint specifies. Content comes only from the user-confirmed record (`.mh/ai_disclosure.json` when present): never randomize or infer tools, dates, purposes, or interaction records; do not list AI tools as academic references. If the record shows AI was not used, record exactly that fact.
2. **No evidenced provision** — the archive carries no current-year AI-use rule for `CONTEST_ID`/`EDITION`: **do not** substitute a generic short note and do not present it as compliance. Surface an explicit pending-verification item instead: `AI_USE_REPORT: 待核实 (no evidenced provision in the archive for CONTEST_ID/EDITION — verify against the current-year official instructions before submission)` in the step's handoff notes.
3. **User disabled disclosure (`AI_DISCLOSURE` off)** — the switch only suppresses generating disclosure *content*; it cannot waive a competition requirement: an evidenced requirement still gets its statement from the user-confirmed record, and a contest without an evidenced provision still gets the 待核实 item. Nothing is bypassed by default.

```bash
AI_DISC=off
grep -q 'AI_DISCLOSURE=used' AGENTS.md 2>/dev/null && AI_DISC=used
grep -q 'AI_DISCLOSURE=none' AGENTS.md 2>/dev/null && AI_DISC=none
echo "AI_DISC=$AI_DISC CONTEST_ID=$CONTEST_ID"
```

The CUMCM statement format (Chinese "AI工具使用声明" + `_utils/build_ai_disclosure.py` + "AI工具使用详情.pdf") belongs to the CUMCM chain (`comp-cumcm-disclosure`), **not** to this skill — it is never reused as a stand-in for another contest's requirement.

### Step 5: Final verification

**Upstream closeout & handoff (incremental; local checks below remain the item source):** while writing, read numerical claims from the real JSON/TABLE sources and never change result data to make prose agree; the `% DATA_CHECK_PASSED` marker and the authoritative data audit are generated once by the following `comp-compile-en` step on the final source snapshot (it also owns rendered layout, fonts, physical pages, figure-size consistency and stale-result checks — see its Phase ownership section). This step may run its source-level gates, but do not launch a second compiler audit loop for temporary drafts: batch source fixes, then let one compile+recheck close them out. Never expand merely to approach `PAGE_CAP`, and never compress merely to fall below it; add or remove material only for a real modeling, evidence, clarity, or final-submission need explicitly requested by the user. Figure inventory, inter-figure prose, template structure and rendered visual results must not drive repeated compiles here; while writing, each selected figure must still appear inside its actual formulation, solution, or results narrative rather than in a gallery.

```bash

bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/

```

**⛔ Capability-claim gate (full-chain contract, run before AND after writing; zero-cost, both modes):** The paper must not claim capabilities that failed acceptance in the coding stage.

```bash

FAST_MODE=0; grep -q 'MH_FAST_MODE=1' AGENTS.md 2>/dev/null && FAST_MODE=1

python _utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE

PCC=$?   # 0=all passed 1=some capability FAIL/PENDING (must not finalize) 2=no audit, skip

```

> `PCC=1`: a capability failed acceptance in comp-code — go back and make it truly PASS before finalizing. WARN (a not-passed capability's name appears in the body): confirm you are not writing an undone capability as done (OK only if honestly stated under Limitations/Future work). Contract chain: comp-problem-analysis defines it → modeling claims each → code implements & audits → paper reports only what passed.

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

- Chapter completeness is owned by the writing contract (every sub-problem covered, claims evidence-backed); there is no character-count or page-count target, and no chapter is padded for length

- Summary Sheet exists (MCM/ICM critical)

- All figures/*.pdf and TABLE files (PDF mode .tex / Word mode .md) referenced in sections/body

- No `\input{figures}` patterns

- Team Control Number placeholder present

**⛔ Page count pre-check (MUST pass before finishing):**

> ⛔ The binding cap is **PAGE_CAP** (`contest_profile.gate_page_cap`, this task's operative gate cap); which pages it counts is **PAGE_SCOPE** (`gate_page_scope`: `body` / `total`) — body and total are tracked separately, never merged into one number.

> `PAGE_SCOPE=body` (e.g. `comp_cumcm`/`comp_huawei`): the cap counts body chapters only (including figures/tables) — **not** abstract / TOC / references / **appendix code**. Scan covers `paper/sections/*.tex` only; appendix code goes in `paper/appendix/` (separate, no page cap).

> `PAGE_SCOPE=total` (e.g. `comp_mcm`, whose 25-page cap counts the whole PDF): check against the **whole-paper estimate**, not the body-only estimate — a body-only count would silently under-count.

> **PAGE_CAP_STATUS** (`page_cap_status`) is reported together with the numbers: `unverified` = unknown provenance — it does **not** create a default hard page cap and is not presented as a proven official rule; unknown only leaves the compliance verdict blocked. A cap binds as hard only with `official_verified` or a separately identified explicit task authorization (`task_override`) — never packaged as one.

```bash

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

if [ -n "$PAGE_CAP" ]; then
    echo "Body chars: $total_chars (est ~$est_pages pages); Cap: <= $PAGE_CAP pages, scope: $PAGE_SCOPE, status: ${PAGE_CAP_STATUS:-unreported}"
else
    echo "⛔ PAGE_CAP missing: contest_profile.gate_page_cap not dispatched (no operative page contract for this contest, or a non-inherited ruling) — page cap unknown (待核实); do not invent a default."
fi

# 3. Appendix separately (info only)

if [ -d paper/appendix ]; then

    app_chars=0

    for f in paper/appendix/*.tex; do

        [ -f "$f" ] || continue

        app_chars=$((app_chars + $(wc -c < "$f")))

    done

    app_pages=$((app_chars / 2200))

    echo "(Appendix chars: $app_chars, ~$app_pages pages — tracked separately from the body count)"

fi

# Total-paper estimate (body + front/back matter) — reported separately from the body

# estimate; which of the two PAGE_CAP binds is decided by PAGE_SCOPE, not by this script.

total_all_chars=$total_chars

[ -n "$app_chars" ] && total_all_chars=$((total_chars + app_chars))

echo "(Whole-paper estimate: ~$((total_all_chars / 2200)) pages incl. appendix)"

```

Do not pad or expand chapters to approach any page target; length follows the modeling and evidence, not a quota.

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


## 执行与产出

使用当前执行会话完成本步工作；产物路径按当前步骤合同。程序采集真实操作、输入输出、版本与运行清单，模型只负责实质成果和领域质量。

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

