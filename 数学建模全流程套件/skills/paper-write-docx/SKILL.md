---
name: paper-write-docx
description: "Draft an English academic paper as Markdown for Word (docx) export. Use when params.output_format == 'docx'. Mirrors paper-write writing rules (ICLR/NeurIPS/ICML) but produces paper/main.md only."
argument-hint: [venue-or-section]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch, mcp__codex__codex, mcp__codex__codex-reply
---

# Paper Write — Markdown for Word (docx mode)

Draft an English academic paper as Markdown: **$ARGUMENTS**

> docx-mode counterpart of `paper-write`. Keeps all writing principles (claims-evidence, story arc, citation discipline, venue checklists) but produces **`paper/main.md`** only. The downstream `docx-export` step runs `tools/docx-cn-engine/md_to_docx.js` to convert it.
>
> ⛔ **NEVER produce `paper/main.tex` / `paper/sections/*.tex` / `.cls` / `.sty` / `.bib`. NEVER run XeLaTeX.**

## Constants

- **TARGET_VENUE = `ICLR`** — Supported: ICLR, NeurIPS, ICML. Override via Additional Parameters.
- **MAX_PAGES = 9** — Body length target ≥ MAX_PAGES (~800 words/page).
- **ANONYMOUS = true**
- **CUSTOM_REQUIREMENTS** — highest priority.
- **REVIEWER_SCRIPT** — external reviewer script.

## Inputs

1. PAPER_PLAN.md — outline with claims-evidence matrix, figure plan
2. NARRATIVE_REPORT.md — research narrative
3. experiment_results.md / RESULTS.md / figures/all_results.json
4. figures/ — `.png` / `.pdf` files
5. Verified reference pool

## Load shared rules

```bash
cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md
```

> The LaTeX-specific bits in shared rules don't apply here; the writing principles do.

## Orchestra References

- `../shared-references/writing-principles.md` — story framing, clarity
- `../shared-references/venue-checklists.md` — submission requirements
- `../shared-references/citation-discipline.md` — citation fallback

## ⛔⛔⛔ Output Contract (highest priority)

**Single artifact**: `paper/main.md` (UTF-8, complete paper, ≥ 5KB)

**Never produce**: `paper/main.tex`, `paper/sections/*.tex`, `paper/references.bib`, `.cls`, `.sty`, `.aux`, any LaTeX command (`\begin`, `\input`, `\cite`, `\section`, `\includegraphics`, ...).

**Mandatory verification before ending**:
```bash
echo "=== Output verification (must be all ✅) ==="
PASS=true

[ -f paper/main.md ] && SZ=$(wc -c < paper/main.md) || SZ=0
[ "$SZ" -ge 5120 ] && echo "✅ paper/main.md ($SZ bytes)" || { echo "❌ paper/main.md missing or too small ($SZ bytes)"; PASS=false; }

words=$(wc -w < paper/main.md 2>/dev/null || echo 0)
est_pages=$((words / 600))   # ~600 words/page for English
target_pages="${MAX_PAGES:-9}"
echo "words: $words, est pages: ~$est_pages, target: ≥ $target_pages"
[ "$est_pages" -lt "$((target_pages * 80 / 100))" ] && echo "⚠ below 80% target — expand thinnest sections"

# No LaTeX residue
if grep -qE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter|subsection)\{' paper/main.md; then
    echo "❌ LaTeX command residue in paper/main.md:"
    grep -nE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter|subsection)\{' paper/main.md | head -5
    PASS=false
fi

# No .tex
ls paper/*.tex paper/sections/*.tex 2>/dev/null | head -1 | grep -q . && { echo "❌ .tex files detected"; ls paper/*.tex paper/sections/*.tex 2>/dev/null; PASS=false; } || true

[ "$PASS" != true ] && echo "⛔ verification FAILED — fix and re-run before ending"
```

## docx-cn-engine markdown conventions

The downstream `docx-export` step uses `tools/docx-cn-engine/md_to_docx.js`. Follow these conventions:

### 1. Headings
- `# Paper Title` — paper title (unique, centered, largest)
- `## 1. Introduction` — top-level section
- `### 1.1 Subsection`
- `#### Sub-subsection`

### 2. Abstract (engine auto-centers)
```markdown
## Abstract

[150-250 word abstract]

**Keywords**: kw1; kw2; kw3
```

### 3. Math
- Inline: `$x^2 + y^2 = r^2$`
- Display: `$$ \nabla_\theta L(\theta) = \mathbb{E}[\dots] \quad (1) $$`
- Number on right by appending `(1)`, `(2)` after `$$ ... $$`

⛔ **Never use** `\begin{equation}`, `\[...\]`, `\begin{align}` — engine doesn't render those.

### 4. Figures
```markdown
![Figure 1: Architecture overview.](figures/fig_arch.png)
```
- Alt text becomes the caption (centered, bold)
- Path relative to workspace root
- Prefer `.png`; `.pdf` works but Word renders PNG better
- **⛔ Keep captions SHORT — a label (body ≤14 words, excluding the "Figure N:" prefix)**: the alt text holds only a short noun phrase naming what the figure is; criteria, parameters, axis meanings, and conclusions go into the prose, not the caption (Word centers/bolds captions, so long ones wrap to ugly multi-line blocks). Anti-example `![Figure 3: Coverage-radius geometry: station as center, R=3km coverage circle, dispatch distance and response-time criterion](...)` → short form `![Figure 3: Station coverage-radius geometry](...)`. See the caption-length rule in `_utils/writing_rules.md`; final verification scans caption length and flags overruns.

### 5. Tables (3-line academic style)
```markdown
**Table 1: Main results.**

| Method | Accuracy | F1 | Time(s) |
|--------|----------|----|---------|
| Baseline | 0.823 | 0.811 | 124 |
| Ours | **0.917** | **0.905** | 132 |
```

⛔ **Never use** `\begin{table}` or `\input{figures/TABLE_x.tex}`. If `figures/TABLE_*.md` exists, paste its content.

### 6. References
```markdown
## References

[1] LeSage J P, Pace R K. Introduction to Spatial Econometrics. CRC Press, 2009.
[2] Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need. NeurIPS, 2017.
```

In-text citations use `[1]`, `[1, 2]`, `[1-3]` — **not** `\cite{key}`.

The engine detects `## References` and renders the following `[N] ...` lines with hanging indent.

## Workflow

### Step 0: Upstream check + resume

```bash
echo "=== Upstream check ==="
for f in PAPER_PLAN.md RESULTS.md NARRATIVE_REPORT.md experiment_results.md; do
    [ -f "$f" ] && echo "✅ $f ($(wc -c < $f) chars)" || echo "  $f not found"
done
[ -f figures/all_results.json ] && echo "✅ figures/all_results.json" || echo "⚠ no all_results.json"
PNG_COUNT=$(ls figures/*.png 2>/dev/null | wc -l)
PDF_COUNT=$(ls figures/*.pdf 2>/dev/null | wc -l)
echo "figures: PNG=$PNG_COUNT, PDF=$PDF_COUNT"

if [ -f paper/main.md ]; then
    cp paper/main.md "paper/main-backup-$(date +%s).md.bak"
    echo "Resume mode — backed up existing main.md"
fi
```

**⛔ Numbers come from data, not memory.**

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
Every scalar you need is in `RESULTS.md` or the range/sample above. If one scalar isn't fully shown, fetch just that value with `python3 -c "import json;d=json.load(open('figures/all_results.json'));print(d['key'])"` — still never read the whole file.

**⛔ Claims-Evidence discipline**: re-read PAPER_PLAN.md claims-evidence matrix before each section. Every claim must be supported by data. If evidence is missing for a planned claim, write an honest "preliminary results suggest X, formal validation left to future work" instead of fabricating.

### Step 1: Figure inventory

```bash
ls -la figures/*.png figures/*.pdf 2>/dev/null
ls -la figures/TABLE_*.md 2>/dev/null
cat figures/latex_includes.tex 2>/dev/null  # reference only — DO NOT use the LaTeX commands
```

Build a mapping: figure ID → file → target section. Only embed figures whose files exist.

### Step 1.5: Pre-fetch verified reference pool

⛔ Build a verified pool **before** writing any `[N]` citations.

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
mkdir -p _tmp
# Search by topic:
#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "transformer attention" --max 5
```

Save the verified list to `_tmp/_verified_refs.txt` with one entry per line.

### Step 2: Write the paper

Order: **Method/core → Experiments → Introduction → Related Work → Conclusion → Abstract** (last).

**⛔ Cross-section context + figure-data binding (prevents the "two-layers" disconnect):**
- Since everything goes in one `main.md`, keep the whole draft coherent: **as you finish each section, jot a 3-5 line card** (core claim / key numbers / newly defined symbols & terms / figures discussed) — into `_writing_context.md` in the workspace root, and re-read it so later sections carry forward prior conclusions, reuse defined terms (don't redefine), and keep every metric's number consistent. See `<chapter_context_card>` in `_utils/writing_rules.md`.
- **Before writing the analysis for any figure/table**, follow `<figure_data_binding>`: identify *what quantity the figure plots* from FIGURE_MANIFEST/latex_includes → locate its real values in `RESULTS.md`/`figures/all_results.json` → use only those real numbers. **Never guess numbers from the plot's shape/position, never fabricate coordinates.**

Save everything in **`paper/main.md`** (single file). Suggested skeleton:

```markdown
# [Paper Title]

[Author placeholders]

## Abstract

[150-250 words]

**Keywords**: kw1; kw2; kw3

## 1. Introduction

[Hook → gap → contribution → results preview, ~1.5 pages]

## 2. Related Work

[Synthesize by category, not by paper, ~1-1.5 pages]

## 3. Method

### 3.1 Notation

### 3.2 Formulation

$$ \mathcal{L}(\theta) = \mathbb{E}_{x \sim \mathcal{D}} [\ell(f_\theta(x), y)] \quad (1) $$

### 3.3 Algorithm

![Figure 1: Method overview.](figures/fig_arch.png)

As shown in Figure 1, ... [≥ 5 lines analysis]

## 4. Experiments

### 4.1 Setup

### 4.2 Main results

**Table 1: Comparison with baselines.**

| Method | Acc | F1 |
|--------|-----|-----|
| ... | ... | ... |

Table 1 shows ... [numerical interpretation + comparison + reasoning, ≥ 2 paragraphs]

![Figure 2: Ablation.](figures/fig_ablation.png)

Figure 2 reveals ... [≥ 5 lines]

### 4.3 Ablation

### 4.4 Discussion

## 5. Conclusion

[Rephrase contributions + limitations + future work, ~0.5 page]

## References

[1] LeSage J P, Pace R K. Introduction to Spatial Econometrics. CRC Press, 2009.
[2] Vaswani A, et al. Attention is all you need. NeurIPS 2017.
```

**⛔ Style discipline:**
- No bullet/enumerated lists for narrative prose. Use "(1) ... (2) ..." inline numbering or transitional phrases ("First, ...; second, ...").
- Each paragraph 3-5 sentences minimum.
- Consecutive paragraphs cannot start with the same syntactic pattern.
- Every figure/table needs ≥ 5 lines of analysis after it before the next visual.

After each section:
```bash
words=$(wc -w < paper/main.md)
echo "running word count: $words"
```

<exemplar_depth>
#### Writing depth by venue

**ICLR/NeurIPS/ICML (9 pages main body, ~5400-6300 words for body)**:
- Abstract (0.3p, 150-250 words): what → why hard → how → evidence → strongest result. Self-contained
- Introduction (1.5p): hook → gap → contributions → results preview → hero figure. Front-load the contribution
- Related Work (1-1.5p): organize by category, synthesize not list. Each category: 3-5 papers with method summary + positioning vs this work
- Method (2-2.5p): notation → formulation → algorithm. Every formula has intuition explanation. Key derivation steps not skipped
- Experiments (3-4p): setup → main results table → comparison plots → ablation table → analysis. Every result has 1-2 paragraphs of interpretation (not just "our method outperforms")
- Conclusion (0.5p): rephrase contributions + limitations + future work

**JMLR/TPAMI journal (15-20 pages, ~9000-12000 words)**:
- Introduction (2-3p): more thorough literature positioning
- Related Work (2-3p): comprehensive survey by sub-topic
- Method (4-6p): full derivations, proofs, complexity analysis
- Experiments (6-8p): multiple datasets, extensive ablations, qualitative analysis, failure cases
- Conclusion (1p): detailed limitations and future directions
</exemplar_depth>

**Expansion strategies** (not padding — substantive content):
- Formula listed without derivation → add step-by-step derivation with intuition
- Result only says "Table X shows" → add 1-2 paragraphs (what numbers mean, comparison, reasoning)
- Related work only lists papers → add method summaries and positioning vs this work
- Algorithm only has pseudocode → add explanation of key steps and complexity analysis

#### Section guidelines (per-section minimums)
- Abstract: what → why hard → how → evidence → strongest result. Self-contained. 150-250 words.
- Introduction: hook → gap → contributions → results preview. 1.5 pages. Front-load contribution.
- Related Work: ≥ 1 full page. Organize by category, synthesize not list.
- Method: notation → formulation → algorithm. 1.5-2 pages.
- Experiments: setup → main results → ablations. 2.5-3 pages. Every claim needs evidence.
- Conclusion: rephrase contributions + limitations + future work. 0.5 pages.

#### Per-section minimum figures/citations
- Introduction: ≥ 1 figure (hero figure recommended) + ≥ 3 citations
- Related Work: ≥ 3 citations per category
- Method: ≥ 1 figure (architecture/algorithm) + ≥ 2 citations
- Experiments: ≥ 3 figures/tables + ≥ 3 citations
- Conclusion: ≥ 1 citation

### Step 3: Reference numbering

After writing prose:
```bash
grep -oE '\[[0-9]+(-[0-9]+)?(, *[0-9]+)*\]' paper/main.md | sort -u > _tmp/_cited.txt
ref_count=$(awk '/^## References/,0' paper/main.md | grep -cE '^\[[0-9]+\]')
echo "Cited tokens vs reference entries: $(wc -l < _tmp/_cited.txt) vs $ref_count"
```

Make every `[N]` in body match an entry in `## References`. No gaps.

⛔ Numbering must be strictly increasing by first appearance: [1] before [2] before [3]. No regression.
⛔ Multi-cite merging: `[1, 2, 3]` requires ascending order; non-adjacent IDs can be split `[1] [5]`.

### Step 3.5: Build verified BibTeX entries (citation discipline)

⛔ **Use scholar_fetch.py for ALL reference retrieval. NEVER fabricate BibTeX from memory.**

While drafting, use **descriptive citation keys** so you can search them later: `LastName_Year_topic_keywords`.
- ✅ `wang_2023_supply_chain_resilience` 
- ❌ `wang2023supply` (impossible to re-search)
- If author/year unknown, use `TODO__` prefix: `TODO__digital_economy_spatial_spillover`

When all draft text is done, search and verify each citation:

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
mkdir -p _tmp

# Collect citation keys / topic descriptors (you maintained while writing)
# For each, search scholar_fetch:
while IFS= read -r key; do
    query=$(echo "$key" | sed 's/^TODO__//; s/_/ /g')
    echo "--- Fetching: $key (query: $query) ---"
    $PYTHON "$SCHOLAR_SCRIPT" bibtex "$query" --max 3
    sleep 0.5
done < _tmp/_topics.txt
```

For each search result:
1. **Check `match_label`**: `"good"` → use; `"partial"` → verify title matches; `"low"` → likely wrong paper, retry with better keywords or use WebSearch.
2. **Check `match_score`**: < 0.3 → don't blindly trust.
3. Format the BibTeX result as a `[N] LastName F M, ... Title. Venue, Year.` line under `## References`.
4. If `bibtex_source=auto`, add `<!-- VERIFY -->` comment in the source markdown next to the citation.

⛔ References must include ≥ 30 entries for journal venues, ≥ 20 for conferences (rules of thumb).

### Step 4: De-AI polish

See `<de_ai_polish>` in writing_rules.md. Key:
- Drop "this paper proposes / we propose" boilerplate openings
- Replace "explore / investigate" with concrete verbs
- Cap "we" frequency

### Step 5: Cross-review

```bash
mkdir -p _tmp
cat << 'EOF' > _tmp/_review_prompt.txt
Review this academic paper draft. Focus on:
1. Logic flow and argument structure
2. Claim-evidence alignment
3. Clarity and concision
4. Missing/weak sections
5. Score (1-10) + top-3 improvements

## Paper:
EOF
cat paper/main.md >> _tmp/_review_prompt.txt
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _tmp/_review_prompt.txt --thread-file _tmp/_reviewer_thread.json 2>&1 | tee _tmp/_cross_review.txt
```

Skip if reviewer script unavailable.

### Step 5.5: Reverse outline test

Extract topic sentences from each paragraph → read them in sequence → check claim coverage → fix gaps.

```bash
# Extract first sentence of every paragraph (paragraphs separated by blank line)
awk 'BEGIN{RS=""} {print substr($0, 1, index($0,"\n")?index($0,"\n")-1:length($0)) }' paper/main.md \
  | grep -v '^#' | grep -v '^!' | grep -v '^|' | head -50
```

Reading just topic sentences should still tell the paper's story. If gaps exist (claim made but evidence missing, or evidence presented but claim not stated), fix them.

### Step 6: Final verification

Run the full output-contract verification block (top of this SKILL). Any ⛔ → go back, fix, re-verify.

## Key Rules (docx mode)

- **Single artifact**: `paper/main.md`
- **Never produce**: `.tex` / `.bib` / `.cls` / `.sty` / `.aux`
- **No LaTeX commands** in body
- **Math**: `$...$` / `$$...$$`
- **Figures**: `![alt](path)`
- **Tables**: markdown pipe tables
- **Citations**: `[N]`, references inline in `## References` section
- Body length ≥ MAX_PAGES × 600 words
- Numbers from data files, not memory
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
    [ "$bn" = "latex_includes.tex" ] && continue
    if [ -f paper/main.md ]; then
        if ! grep -q "$bn" paper/main.md; then
            echo "MISSING: $bn — produced but not embedded in paper/main.md"
            missing=$((missing + 1))
        fi
    fi
done

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
[ "$missing" -gt 0 ] && echo "⛔ DO NOT finish until missing = 0. Embed each missing figure/table into paper/main.md."

# Caption-too-long check (alt text is a short label; criteria/params/conclusions go in the body)
echo "=== Caption-too-long check ==="
python - paper/main.md << 'PYEOF'
import re, sys
LIMIT = 14  # word cap after stripping the "Figure N:" prefix (over 14 = violation)
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
[ "$cap_rc" -eq 3 ] && echo "⛔ Captions too long: shorten the alt text and move detail into the body, then re-run until it prints OK — detect → fix → recheck loop, do not finish while it fails"
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

