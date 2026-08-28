---
name: paper-write-nature-docx
description: "Draft a Nature-style paper as Markdown for Word (docx) export. Use when params.output_format == 'docx' for nature_writing template. Mirrors paper-write-nature writing rules but produces paper/main.md only."
argument-hint: [venue-or-section]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch, mcp__codex__codex, mcp__codex__codex-reply
---

# Nature-Style Paper Writing — Markdown for Word (docx mode)

Draft a Nature-quality paper as Markdown: **$ARGUMENTS**

> docx-mode counterpart of `paper-write-nature`. Keeps hourglass structure, claim-evidence-boundary paragraph architecture, reader-first ordering. Produces **`paper/main.md`** only.
>
> ⛔ **NEVER produce `.tex`, run XeLaTeX, or use LaTeX commands.**

## Constants

- **TARGET_VENUE = `Nature`** — Override via Additional Parameters.
- **MAX_PAGES** — Nature Article: ~5 pages main + Methods (override via Additional Parameters).
- **ANONYMOUS = false**
- **CUSTOM_REQUIREMENTS** — highest priority.
- **REVIEWER_SCRIPT** — external reviewer.

## Inputs

1. PAPER_PLAN.md — outline with claims-evidence matrix
2. RESULTS.md / experiment_results.md / figures/all_results.json
3. figures/ — `.png` / `.pdf` (Nature figure aesthetics from `nature-figure` step)

## Core Architecture

### 1. Identify paper type first
Before writing, determine:
- **Research paper**: why phenomenon matters → what was done → what was found → what it means
- **Methods paper**: does method work → reproducible → better under fair comparison
- **Hypothesis-based**: establish or rule out a causal explanation
- **Algorithmic/device**: propose tool/system → show reliable, advantageous performance

Don't use one narrative for all paper types.

### 2. Reader-first writing order
Write for the reader's cognitive sequence:
1. Is this relevant? (Introduction hook)
2. What's new? (Contribution)
3. Do I trust it? (Results + Methods)
4. Can I reuse it? (Methods detail + Data Availability)
5. What does it mean? (Discussion)

### 3. Productive writing order
1. **Results** — anchor in evidence
2. **Introduction** — frame the gap
3. **Title** — crystallize contribution
4. **Discussion** — interpret + bound
5. **Methods** — reproducibility
6. **Abstract** — last

### 4. Hourglass structure
- **Introduction**: open broad → narrow to gap → state question
- **Discussion**: widen again → connect → explain how gap was filled

### 5. Paragraph architecture: Claim-Evidence-Boundary
Every paragraph:
- **Claim** (topic sentence)
- **Evidence** (data/comparison/literature)
- **Boundary** (limitation, scope, transition)

### 6. Boundary language
Express limitations honestly:
- "These findings hold under [conditions]"
- "We do not claim [X] generalizes to [Y]"
- "The generalizability is limited by..."

## Section Responsibilities

### Title
- ≤ 75 characters including spaces (Nature guideline)
- Searchable, specific, restrained, defensible
- Pattern: `[Core entity] in/through/by [mechanism or context]`
- No vague hooks, no unverified "first"

### Abstract (150–200 words)
Mini-paper structure: context/problem → gap → approach → key result with numbers → implication

### Introduction (~600–800 words for Nature)
- Hook: why the topic matters broadly
- Known: what is established
- Gap: what remains unresolved
- Aim: what this study asks/does
- Value: brief indication of approach and significance
- Do NOT summarize Results or Conclusion here
- Short paragraphs OK (Nature style allows 3–4 sentence paragraphs)

### Results
- Past tense: report what was observed
- Orient reader to figure/table → state main observation → quantitative detail → patterns
- **Figure numbers MUST be cited explicitly (every paragraph names its "Fig. N"), but VARY the citation pattern — don't open every figure with the same "Fig. N shows/presents…" skeleton.** Rotate: parenthetical ("…dropped 4.2% (Fig. 3)"), sentence-start, verb-led ("Comparing the curves in Fig. 4…"), figure-as-subject (when it carries a real quantitative finding). The number always appears; only the sentence structure rotates. Adjacent figures must not use the same pattern.
- Results = what happened, NOT what it means
- Each result paragraph tied to a specific figure or table
- Active voice preferred: "We observed..." not "It was observed that..."

### Discussion
- Restate main finding → plausible explanations → compare with earlier work → limitations → implications → future work
- Short rule: Results = what we observed; Discussion = how we understand it and when it may fail
- Three-part close: contribution → key evidence → implication with boundary

### Materials and Methods
- Specific, complete, transparent, reproducible
- Another group must determine: ethical conformity, materials/conditions, key parameters, data processing, statistical tests, software versions
- Never: "under standard conditions", "using routine methods", "data were analyzed statistically"

### Data Availability Statement
Generate using Nature data policy principles:
- Map each dataset to access route: public repository, controlled access, within supplement, reused source, third-party restricted
- Prefer DOI/accession numbers over personal websites
- Pattern: "The [data type] generated in this study have been deposited in [repository] under accession code [XXX]. Source data are provided with this paper."
- Flag "available upon request" as weak unless legally/ethically required

## Failure Mode Diagnosis

Before editing any section, diagnose the main problem in priority order:

1. **Paper type** — wrong narrative logic for this paper type?
2. **Section job** — section not fulfilling its rhetorical responsibility?
3. **Paragraph logic** — claim without evidence? evidence without claim? missing boundary?
4. **Sentence polish** — clutter, passive voice, overclaim?

Fix from top down. Do not polish sentences while reasoning is broken.

## Nature-Specific Style Rules

### Sentence control
- Each sentence ≤ 30 words
- One core subject-verb proposition per sentence
- Split overloaded sentences rather than polishing cosmetically
- Active voice preferred: "We show..." not "It is shown that..."

### Paragraph control
- Short paragraphs OK (3–5 sentences typical for Nature)
- Each paragraph: one controlling idea + support
- Thematic linking, not repetitive "This suggests..." openings

### De-AI Polish Rules

Remove or replace these AI-typical words:
- "delve" → "examine", "investigate"
- "pivotal" → "important", "central"
- "landscape" → "field", "area"
- "multifaceted" → "complex"
- "underscores" → "shows", "highlights"
- "leveraging" → "using"
- "novel" (overused) → "new", or remove if claim is clear from context
- "groundbreaking" → remove or use specific evidence
- "paradigm shift" → describe the actual change
- "in conclusion" → just state the conclusion directly

### Hedging (Academic Phrasebank patterns)
- "These results suggest that..."
- "A possible explanation is that..."
- "This discrepancy may reflect..."
- "To our knowledge, this is the first..."
- "Further work is needed to determine whether..."

### Transitions
- Contrast: "However,", "By contrast,", "Nevertheless,"
- Addition: "Moreover,", "Furthermore,", "In addition,"
- Cause: "Consequently,", "As a result,", "Therefore,"
- Concession: "Although...,", "Despite...,", "Notwithstanding,"

### Limitations acknowledgment
- "These results should be interpreted with caution because..."
- "A limitation of this study is that..."
- "The generalizability of these findings is limited by..."

## ⛔⛔⛔ Output Contract (highest priority)

**Single artifact**: `paper/main.md` (UTF-8, ≥ 5KB)

**Never produce**: `.tex` / `.bib` / `.cls` / `.aux` / any LaTeX command.

**Mandatory verification**:
```bash
PASS=true
[ -f paper/main.md ] && SZ=$(wc -c < paper/main.md) || SZ=0
[ "$SZ" -ge 5120 ] && echo "✅ paper/main.md ($SZ)" || { echo "❌ paper/main.md missing"; PASS=false; }

if grep -qE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter)\{' paper/main.md; then
    echo "❌ LaTeX residue:"
    grep -nE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter)\{' paper/main.md | head -5
    PASS=false
fi

ls paper/*.tex paper/sections/*.tex 2>/dev/null | head -1 | grep -q . && { echo "❌ .tex files detected"; PASS=false; } || true

[ "$PASS" != true ] && echo "⛔ verification FAILED"
```

## docx-cn-engine markdown conventions

(Same as paper-write-docx — see that SKILL or the brief recap below.)

- `# Title` (unique), `## Section`, `### Subsection`
- `## Abstract` triggers centered abstract style
- `## References` triggers hanging-indent for `[N] ...` lines
- Math: `$inline$`, `$$display$$`, append ` (1)` for numbering
- Figures: `![Figure 1: caption](figures/fig.png)`
- Tables: markdown pipe tables (rendered as 3-line academic style)
- Citations: `[1]`, `[1, 2]`, `[1-3]` — never `\cite{}`

## Workflow

### Step 0: Upstream check + resume

```bash
for f in PAPER_PLAN.md RESULTS.md; do
    [ -f "$f" ] && echo "✅ $f" || echo "  $f not found"
done
[ -f figures/all_results.json ] && echo "✅ figures/all_results.json" || true
ls figures/*.png figures/*.pdf 2>/dev/null | head -10

[ -f paper/main.md ] && cp paper/main.md "paper/main-backup-$(date +%s).md.bak"
```

### Step 1: Identify paper type and target venue

Read PAPER_PLAN.md and TARGET_VENUE. Choose:
- **Nature / Science**: 3000-3500 words main, ~4 figures, single-column logic
- **Nature Methods / Communications**: 4000-5000 words, ~5-6 figures
- **Cell**: 7000-8000 words, more figures, longer methods

### Step 1.5: Figure inventory

Before drafting, build inventory of available figures:

```bash
echo "=== Available figures ==="
ls -la figures/*.png figures/*.pdf 2>/dev/null
echo ""
echo "=== Available tables ==="
ls -la figures/TABLE_*.md 2>/dev/null
echo ""
echo "=== latex_includes.tex (caption reference only) ==="
cat figures/latex_includes.tex 2>/dev/null
```

Build mapping: figure ID → file → target section. Only embed figures whose files exist. Each figure needs ≥ 5 lines analysis after it before next visual.

⛔ Nature standard: Fig. 1 (overview/hero), Figs. 2-4 (main findings).

### Step 2: Pre-fetch verified reference pool

⛔ Build verified pool BEFORE writing any citations.

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
mkdir -p _tmp

# Use descriptive citation keys: LastName_Year_topic_keywords
# Examples:
#   - vaswani_2017_attention_transformer
#   - lecun_2015_deep_learning_review
#   - TODO__crispr_cas9_off_target  (author/year unclear)

# Search by topic:
#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "transformer attention mechanism" --max 5
```

Save verified entries to `_tmp/_verified_refs.txt`. Use ONLY verified entries while drafting.

### Step 2.5: BibTeX verification (after body draft is done)

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
# List descriptive citation keys to _tmp/_topics.txt
while IFS= read -r key; do
    query=$(echo "$key" | sed 's/^TODO__//; s/_/ /g')
    echo "--- Fetching: $key (query: $query) ---"
    $PYTHON "$SCHOLAR_SCRIPT" bibtex "$query" --max 3
    sleep 0.5
done < _tmp/_topics.txt
```

For each result:
1. **`match_label`**: `"good"` → use; `"partial"` → verify; `"low"` → retry or use WebSearch.
2. **`match_score`**: < 0.3 → don't blindly trust.
3. Format as `[N] Author A, Author B. Title. Journal Year, vol(issue): pages.` under `## References`.
4. References ordered by first-appearance in body.

**Fallback**: WebSearch on Google Scholar / PubMed / Semantic Scholar to verify title + authors + year manually.

⛔ References: Nature ≥ 30; Nature Methods/Communications ≥ 50; Cell ≥ 70. **⛔ Authenticity over count**: these are targets for *真实检索到的* references — NEVER fabricate entries to hit the number. If real retrieval falls short, keep the real ones and note the gap; do not invent citations.

### Step 3: Draft Results first

Anchor in evidence. Each subsection:
- One claim
- 2-3 numerical pieces of evidence
- One figure or one table reference
- Boundary statement

**⛔ Cross-section context + figure-data binding (prevents the "two-layers" disconnect):**
- **After finishing each section**, append a 3-5 line card to `_writing_context.md` in the workspace root (core claim / key numbers / newly defined symbols & terms / figures discussed); re-read it before the next section so later sections carry forward prior conclusions, reuse defined terms (don't redefine), and keep every metric's number consistent — see `<chapter_context_card>` in `shared-scripts/writing_rules.md`.
- **Before writing the analysis for any figure**, follow `<figure_data_binding>`: identify *what quantity the figure plots* from `latex_includes.tex`/figure inventory → locate its real values in `RESULTS.md`/`figures/all_results.json` → use only those real numbers. **Never guess numbers from the plot's shape/position, never fabricate coordinates.**

Required figures (Nature standard): Fig. 1 (overview), Fig. 2-4 (main findings). Each figure embedded with full caption.

### Step 4: Draft Introduction

After Results, write Intro with hourglass:
- Para 1: broad relevance (why phenomenon matters)
- Para 2: narrow to specific gap (what's missing in literature)
- Para 3: state hypothesis/question
- Para 4: preview contribution

### Step 5: Title + Discussion

- Title: ≤ 15 words, contribution-driven (not "A Study of...")
- Discussion: widen back. Connect findings to broader literature. State boundaries.

### Step 6: Methods (reproducibility)

- Materials, conditions, equipment
- Detailed protocol
- Statistical analysis
- Code/data availability statement

### Step 7: Abstract last

150-200 words. Single paragraph. Cover: context → gap → method → finding → implication.

### Step 8: Final structure

```markdown
# [Title]

[Authors and affiliations]

## Abstract

[150-200 words single paragraph]

## Introduction

[Hourglass]

## Results

### [Result 1 subheading]

![Figure 1: ...](figures/fig1.png)

[Claim-Evidence-Boundary paragraph + ≥5 lines analysis]

### [Result 2 subheading]

...

## Discussion

[Widen + connect + bound]

## Methods

### Data and materials

### Analysis

### Statistics

### Data availability

### Code availability

## References

[1] ...
[2] ...
```

### Step 9: Cross-review

```bash
mkdir -p _tmp
cat << 'EOF' > _tmp/_review_prompt.txt
Nature-style paper review. Focus on:
1. Hourglass structure
2. Claim-evidence-boundary in each paragraph
3. Title/abstract clarity
4. Reader-first ordering
5. Score (1-10) + top-3 improvements
## Paper:
EOF
cat paper/main.md >> _tmp/_review_prompt.txt
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _tmp/_review_prompt.txt --thread-file _tmp/_reviewer_thread.json 2>&1 | tee _tmp/_cross_review.txt
```

### Step 9.5: Self-review checklist

Run failure mode diagnosis on each section. Check (every box must be ✅):

- [ ] **Hourglass structure intact** (Intro broad → narrow → gap; Discussion narrow → broad → implication)
- [ ] **Each paragraph has claim-evidence-boundary** (no claim-only or evidence-only paragraphs)
- [ ] **No AI-typical language remaining** (delve / pivotal / landscape / multifaceted / underscores / leveraging / novel / groundbreaking / paradigm shift / "in conclusion")
- [ ] **Active voice dominant** ("We show..." not "It is shown that...")
- [ ] **Sentences ≤ 30 words** (split overloaded sentences)
- [ ] **Title ≤ 75 characters** (Nature guideline)
- [ ] **Abstract 150–200 words**
- [ ] **No fabricated references** (every citation came from scholar_fetch.py / WebSearch verification)
- [ ] **Hedging appropriate** (no overclaim — use "These results suggest...", "A possible explanation is...", "To our knowledge, this is the first...")
- [ ] **Data Availability statement complete** (DOI/accession for each dataset; "available upon request" only when legally/ethically required)
- [ ] **Author Contributions template present** ("X.Y. designed the study, performed analysis. Z.W. collected data. All authors discussed results and edited the manuscript.")
- [ ] **Boundary language present in Discussion** ("These findings hold under...", "We do not claim X generalizes to Y", "The generalizability is limited by...")

If any box is ❌, fix before proceeding.

### Step 10: Final verification

Re-run the Output Contract block. All ✅ before ending.

## Writing Discipline (apply throughout drafting)

**⛔ Style rules:**
- No bullet/enumerated lists for narrative prose. Use "(1) ... (2) ..." inline numbering or transitional phrases ("First, ...; second, ..."). Bullets OK for input checklists, evaluation metrics, software dependencies.
- Each paragraph 3-5 sentences (for Nature, sometimes 3-4 OK; never 1-2 sentence paragraphs).
- Consecutive paragraphs cannot start with the same syntactic pattern.
- Figure numbers MUST be cited explicitly (every paragraph names its "Fig. N"), but VARY the pattern. What's forbidden is the monotonous empty "Fig. X shows… as can be seen…" skeleton repeated for every figure — NOT figure-as-subject per se. Rotate: parenthetical (preferred, "(Fig. X)"), sentence-start, verb-led, figure-as-subject (allowed when it carries a real finding), post-hoc confirmation. Adjacent figures must not use the same pattern.
- Each figure/table needs ≥ 5 lines of analysis (numerical interpretation + comparison + reasoning) before the next visual.

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
Every scalar you need is in `RESULTS.md` or the range/sample above. If one scalar isn't fully shown, fetch just that value with `python3 -c "import json;d=json.load(open('figures/all_results.json'));print(d['key'])"` — still never read the whole file. Copy exact numbers. No memory-based estimation.

## Expansion strategies (substantive, not padding)

- Formula without derivation → add step-by-step derivation with physical/biological meaning
- Result with only "Figure X shows" → add 2-3 paragraphs (numerical interpretation + comparison + reasoning + boundary)
- Methods only listed → add why this method, what alternatives were considered, why rejected
- Algorithm as pseudocode only → add explanation, complexity, convergence, sensitivity to hyperparameters

## Key Rules (docx mode)

- Single artifact: `paper/main.md`
- No LaTeX (no `\begin`, `\input`, `\cite`, `\section`, `\includegraphics`)
- Math: `$...$` / `$$...$$`
- Figures: `![alt](path)`
- Tables: markdown pipe tables
- Citations: `[N]`
- Hourglass + claim-evidence-boundary architecture
- Backup before overwrite


---

## ⛔ Figure embedding verification (MUST pass before finishing — file existence + actual reference in paper/main.md both required)

```bash
echo "=== Figure embedding check (docx mode: file + ![]() / image reference in paper/main.md) ==="
missing=0

# Markdown docx mode: figure files referenced via ![](figures/xxx.png) or relative path
for img in figures/*.png figures/*.pdf figures/*.jpg figures/*.svg; do
    [ -f "$img" ] || continue
    bn=$(basename "$img")
    # Skip placeholder files
    [ "$bn" = "latex_includes.tex" ] && continue
    if [ -f paper/main.md ]; then
        if ! grep -q "$bn" paper/main.md; then
            echo "MISSING: $bn — produced but not embedded in paper/main.md"
            missing=$((missing + 1))
        fi
    fi
done

# Also check TABLE_*.md files are embedded
for tbl in figures/TABLE_*.md; do
    [ -f "$tbl" ] || continue
    bn=$(basename "$tbl")
    if [ -f paper/main.md ]; then
        if ! grep -q "$bn" paper/main.md; then
            echo "MISSING: $bn — table file produced but not referenced in paper/main.md"
            missing=$((missing + 1))
        fi
    fi
done

echo "Total missing embeddings: $missing"
[ "$missing" -gt 0 ] && echo "⛔ DO NOT finish until missing = 0. Embed each missing figure/table into paper/main.md via ![caption](figures/xxx.png) or cat figures/TABLE_xxx.md."
```

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
        if ! ls figures/${name}.png figures/${name}.pdf figures/${name}.drawio 2>/dev/null | head -1 | grep -q .; then
            echo "❌ MANIFEST: $name file missing"
            manifest_missing=$((manifest_missing + 1))
        elif ! grep -qE "${name}\.(png|pdf)" paper/main.md 2>/dev/null; then
            echo "❌ MANIFEST: $name exists but not embedded"
            manifest_missing=$((manifest_missing + 1))
        fi
    done
    if [ "$manifest_missing" -gt 0 ]; then
        echo "⛔ FIGURE_MANIFEST audit failed ($manifest_missing missing)"
    else
        echo "✅ FIGURE_MANIFEST fully embedded"
    fi
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

