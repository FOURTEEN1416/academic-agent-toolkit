---

name: comp-compile-en

description: "Compile English competition paper (MCM/ICM/APMCM) and run compliance checks. Use when user says \"compile MCM paper\", \"编译美赛论文\"."

argument-hint: [paper-directory]

allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob

---

# Competition Paper Compile & Compliance (English)

Compile and validate: **$ARGUMENTS**

## Constants

- **ENGINE = `pdflatex`**

- **MAX_COMPILE_ATTEMPTS = 3**

- **PAPER_DIR = `paper/`**

- **MAX_PAGES** — Default 25.

- **COMPETITION** — From Additional Parameters.

## Workflow

### Step 1: Verify environment

Check pdflatex and bibtex are installed.

### Step 2: Pre-compile cleanup

```bash

if [ -f "_utils/compile_utils.sh" ]; then

    bash _utils/compile_utils.sh paper/

elif [ -f "skills/shared-scripts/compile_utils.sh" ]; then

    bash skills/shared-scripts/compile_utils.sh paper/

else

    echo "compile_utils.sh not found, manual cleanup needed"

fi

```

The script auto-handles: special chars, table fixes, path correction, hidelinks, wide table resizebox, light-color text fixes, TikZ library injection.

Also check ref/label matching and embed missing figures:

```bash

mkdir -p _tmp

grep -oh '\\ref{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null | sort -u > _tmp/_refs.txt

grep -oh '\\label{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null | sort -u > _tmp/_labels.txt

comm -23 <(sed 's/\\ref/\\label/g' _tmp/_refs.txt) _tmp/_labels.txt > _tmp/_missing_labels.txt

cat _tmp/_missing_labels.txt

```

If labels are missing, find corresponding figure/table code in `figures/*.tex` and embed into the correct section file.

Also check compile_utils.sh output for "UNEMBEDDED" warnings — each one means a figure or table from `figures/` is not in any section.

**⛔ Auto-fix Unicode quotes (避免 PDF 出现 ''乱码):**

LaTeX doesn't render Unicode quotes (U+201C `"`, U+201D `"`, U+2018 `'`, U+2019 `'`) correctly — they output as `''`.

ASCII straight quotes `"..."` also render as `''...''` instead of paired curly quotes.

```bash

for f in paper/sections/*.tex; do

    [ -f "$f" ] || continue

    python3 -c "

import re

content = open('$f', 'r', encoding='utf-8').read()

placeholders = []

def stash(m):

    placeholders.append(m.group(0)); return f'\\x00M{len(placeholders)-1}\\x00'

content = re.sub(r'\\\$[^\\\$]*\\\$', stash, content)

content = re.sub(r'\\\\\\[.*?\\\\\\]', stash, content, flags=re.DOTALL)

content = content.replace('\u201c', '\`\`').replace('\u201d', \"''\")

content = content.replace('\u2018', '\`').replace('\u2019', \"'\")

parts = content.split('\"')

if len(parts) > 2:

    result = parts[0]

    for i, p in enumerate(parts[1:], 1):

        result += ('\`\`' if i % 2 == 1 else \"''\") + p

    content = result

for i, ph in enumerate(placeholders):

    content = content.replace(f'\\x00M{i}\\x00', ph)

open('$f', 'w', encoding='utf-8').write(content)

" 2>/dev/null

done

```

**MANDATORY FIX LOOP — do NOT proceed to compilation until all figures AND tables are embedded:**

```bash

UNEMBED=0

for pdf in figures/*.pdf; do

    [ -f "$pdf" ] || continue

    bn=$(basename "$pdf")

    grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null || { echo "UNEMBEDDED PDF: $bn"; UNEMBED=$((UNEMBED+1)); }

done

for tbl in figures/TABLE_*.tex; do

    [ -f "$tbl" ] || continue

    for lbl in $(grep -oh '\\label{[^}]*}' "$tbl" 2>/dev/null); do

        grep -rq "$lbl" paper/sections/*.tex paper/main.tex 2>/dev/null || { echo "UNEMBEDDED TABLE: $lbl"; UNEMBED=$((UNEMBED+1)); }

    done

done

echo "Total unembedded: $UNEMBED"

```

If UNEMBED > 0, fix ALL before compiling. For each unembedded item, copy the figure/table block into the appropriate section with lead-in text + analysis. Re-run until UNEMBED = 0.

```bash

# Check all figures/*.pdf are referenced in body

for pdf in figures/*.pdf; do

    [ -f "$pdf" ] || continue

    bn=$(basename "$pdf")

    grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null || echo "⚠ $bn not referenced"

done

```

### Step 3: Compile (manual steps, no latexmk)

```bash

cd paper/

pdflatex -interaction=nonstopmode main.tex

bibtex main

pdflatex -interaction=nonstopmode main.tex

pdflatex -interaction=nonstopmode main.tex

```

### Step 4: Error fix loop (MANDATORY)

After each compilation, check `main.log` for CRITICAL errors. **You MUST fix ALL errors before declaring compilation complete.**

```bash

MATH_ERR=$(grep -c 'Bad math environment delimiter\|Missing \$ inserted\|begin{document} ended by' paper/main.log 2>/dev/null || echo 0)

LR_ERR=$(grep -c 'Not allowed in LR mode' paper/main.log 2>/dev/null || echo 0)

echo "Math errors: $MATH_ERR, LR mode errors: $LR_ERR"

[ $((MATH_ERR + LR_ERR)) -gt 0 ] && grep -B2 'Bad math\|Missing \$ inserted\|Not allowed in LR mode' paper/main.log | grep -E '^\./|^l\.' | head -20

```

Iterate up to 5 times. For each error:

- **Math errors**: read the error location from main.log, open the file, fix broken `$...$` delimiters individually. Do NOT use broad sed patterns.

- **LR mode errors**: add `\par` or blank line before float environments.

- **Undefined control sequence**: add missing `\usepackage` or fix typo.

- **BibTeX failures**: fix LaTeX errors first (BibTeX fails when LaTeX errors exist upstream), then recompile.

After each fix, recompile (xelatex → bibtex → xelatex → xelatex) and recheck. **⛔ Do NOT proceed until MATH_ERR = 0 and LR_ERR = 0.**

When fixing errors in main.tex, only fix the specific error. Do not rewrite or restructure main.tex — the template's preamble, page margins, and formatting settings must remain unchanged.

### Step 5: Post-compile checks

```bash

bash _utils/compile_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_check.sh paper/

```

The script checks: PDF existence/size, undefined references, overfull hbox, TOC, bibliography entries, citation count, unused figures, figure stacking, TikZ diagram presence.

### Step 6: Competition compliance

Check items:

1. **Page count**: body = Summary Sheet through Conclusions, excluding References/Appendix. Must be ≥ MAX_PAGES (**MAX_PAGES is a floor/target, NOT a ceiling**; pages may exceed it, must not fall short. Only compress pages if the competition states a hard page limit)

2. **Summary Sheet exists** (MCM/ICM critical)

3. **Team Control Number** placeholder present

4. **Anonymous** (no school names)

5. **APMCM**: commitment letter not in PDF

6. **Code appendix exists**

7. **No undefined references/citations**

<page_diagnosis>

#### Page count diagnosis (when insufficient)

If body pages < 80% of MAX_PAGES:

```bash

source .env_skill 2>/dev/null || true  # Load MAX_PAGES from engine

echo "=== Page count diagnosis ==="

echo "Target: ≥ ${MAX_PAGES:-25} pages"

echo ""

echo "=== Section character counts ==="

for f in paper/sections/*.tex; do

    chars=$(wc -c < "$f")

    echo "  $(basename $f): $chars chars (~$(echo "scale=1; $chars/2200" | bc) pages)"

done

echo ""

echo "=== Sections needing expansion (3 smallest) ==="

for f in $(ls -S paper/sections/*.tex | tail -3); do

    chars=$(wc -c < "$f")

    echo "  ⚠ $(basename $f): only $chars chars"

done

```

Mark as CRITICAL with specific recommendations:

- Which sections are thinnest

- What content to add (more derivation? more result analysis? more literature?)

- Estimated chars needed

If pages < 80% of MAX_PAGES, attempt to expand thinnest 1-2 sections from MODELING_REPORT.md and RESULTS.md, then recompile.

</page_diagnosis>

<page_overflow>

#### ⛔⛔ Hard rule when pages OVERFLOW (root cause of "figures too small")

**Background**: the compiler once misread `MAX_PAGES` as a hard ceiling and, to fit under it, shrank figure widths to `0.46~0.48\textwidth` and injected a global `\small` on the body — producing tiny, unreadable figures. This is a serious error. This block is a hard constraint.

**⚠ Reminder: `MAX_PAGES` is a floor/target, NOT a ceiling.** Unless the competition brief explicitly states a hard page limit (noted in Additional Parameters), overflowing is fine and you must NOT proactively cut pages. **Never invent a ceiling like "≤30 pages" and then shrink figures to meet it** — most competitions (e.g. CUMCM) have no hard page cap.

**Figure size is decided solely by the writing rules + `compile_utils.sh` fallback: a single figure is always `width=0.85\textwidth` (side-by-side uses `0.48`), height fallback is `height=0.9\textheight` (to stop a single figure owning a whole page). The compiler must NEVER change figure width OR shrink figure height to save space.**

**⛔ Special warning — shrinking `height` is the most insidious page-fitting hack:** adding `height=0.20\textheight` under `keepaspectratio` binds before width, crushing near-square/tall figures into a tiny block (small AND stacked). This is as bad as width-shrinking and equally forbidden. `compile_utils.sh` auto-strips any `<0.5\textheight` cap and restores `0.9\textheight`; the compiler must not re-impose it.

When pages overflow (and the competition truly has a hard limit), trim only in this priority order — **figures and body font size are never touched**:

1. Trim appendix code (keep core snippets, drop redundant comments);

2. Merge/remove thin repetitive transition paragraphs; tighten verbose enumerate into compact prose;

3. Tighten float spacing (`\setlength{\intextsep}` etc.), without changing figure size;

4. Remove non-essential duplicate figures/tables.

**⛔ Absolutely forbidden page-fitting hacks (any occurrence = fail, must revert):**

- ❌ Reducing `\includegraphics` width from `0.85` to something smaller (`0.6/0.5/0.48/0.46\textwidth`) to save space;

- ❌ Adding a small `height=0.NN\textheight` cap (`0.20/0.22/0.3\textheight`) to shrink figures for space;

- ❌ Injecting a global `\small` / `\footnotesize` on the body after `\begin{document}`;

- ❌ Any global font-shrinking command on body (non-table) text.

**Self-check (run before Step 7 quality gate):**

```bash

echo "=== Figure-width compliance (no page-fitting shrink) ==="

# Only inspect includegraphics width coefficients; <0.80 = shrunk to fit pages (genuine side-by-side panels use 0.48 with subfigure/minipage; this check flags them for manual confirm)

BAD_W=$(grep -rhoE 'includegraphics\[[^]]*width=0\.[0-9]+' paper/sections/*.tex paper/main.tex 2>/dev/null | grep -oE 'width=0\.[0-9]+' | grep -vE 'width=0\.(8[0-9]|9[0-9])' | wc -l)

[ "$BAD_W" -eq 0 ] && echo "OK no undersized figures" || echo "FAIL $BAD_W figures width<0.80 (page-fitting shrink; restore 0.85 unless genuine side-by-side)"

echo "=== Figure-height compliance (no page-fitting shrink) ==="

# <0.5\textheight cap = page-fitting shrink; compile_utils.sh should have stripped it. Residual = preprocessing skipped or re-imposed.

BAD_H=$(grep -rhoE 'includegraphics\[[^]]*height=0?\.[0-9]+' paper/sections/*.tex paper/main.tex 2>/dev/null | grep -oE 'height=0?\.[0-9]+' | grep -vE 'height=0?\.([5-9][0-9]*)' | wc -l)

[ "$BAD_H" -eq 0 ] && echo "OK no undersized heights" || echo "FAIL $BAD_H figures height<0.5\\textheight (page-fitting shrink; drop the cap so compile_utils.sh restores 0.9)"

echo "=== Global small check (no body font shrink) ==="

AFTER_DOC=$(awk '/begin\{document\}/,/maketitle/' paper/main.tex 2>/dev/null | grep -cE '^[[:space:]]*[\](small|footnotesize|scriptsize)([[:space:]]|$)')

[ "$AFTER_DOC" -eq 0 ] && echo "OK no global body font shrink" || echo "FAIL global small/footnotesize after document (page-fitting, must remove)"

```

All three must be OK; any FAIL must be fixed (restore width to 0.85, drop small height caps, remove global small) and recompiled.

</page_overflow>

### Step 7: ⛔ FINAL QUALITY GATE (must ALL pass before finishing)

```bash

echo "=== Running check scripts ==="

bash _utils/compile_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_check.sh paper/ 2>/dev/null

bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/ 2>/dev/null

WC_EXIT=$?

echo ""

echo "=========================================="

echo "  FINAL QUALITY GATE"

echo "=========================================="

GATE_FAIL=0

# writing_check.sh result must be counted AFTER GATE_FAIL is reset, or it would be wiped

[ "$WC_EXIT" -eq 0 ] && echo "✅ Writing checks passed" || { echo "❌ Writing checks failed (exit=$WC_EXIT) — includes figure stacking / adjacent figure-number openers / caption-too-long"; GATE_FAIL=$((GATE_FAIL+1)); }

# --- CRITICAL ---

[ -f paper/main.pdf ] && [ $(wc -c < paper/main.pdf) -gt 100000 ] && echo "✅ PDF exists" || { echo "❌ PDF missing/small"; GATE_FAIL=$((GATE_FAIL+1)); }

MATH_ERR=$(grep -c 'Bad math.*delimiter\|Missing \$ inserted' paper/main.log 2>/dev/null || echo 0)

LR_ERR=$(grep -c 'Not allowed in LR mode' paper/main.log 2>/dev/null || echo 0)

[ "$((MATH_ERR+LR_ERR))" -eq 0 ] && echo "✅ No LaTeX errors" || { echo "❌ $MATH_ERR math + $LR_ERR LR errors"; GATE_FAIL=$((GATE_FAIL+1)); }

BBL=$(grep -c '\\bibitem' paper/main.bbl 2>/dev/null || echo 0)

[ "$BBL" -gt 0 ] && echo "✅ Bib: $BBL entries" || { echo "❌ Bib empty"; GATE_FAIL=$((GATE_FAIL+1)); }

CITE=$(grep -roh '\\cite{' paper/sections/*.tex paper/main.tex 2>/dev/null | wc -l)

[ "$CITE" -gt 0 ] && echo "✅ Citations: $CITE" || { echo "❌ No citations"; GATE_FAIL=$((GATE_FAIL+1)); }

UNEMBED=0; for pdf in figures/*.pdf; do [ -f "$pdf" ] || continue; bn=$(basename "$pdf"); grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null || UNEMBED=$((UNEMBED+1)); done

[ "$UNEMBED" -eq 0 ] && echo "✅ All figures embedded" || { echo "❌ $UNEMBED unembedded"; GATE_FAIL=$((GATE_FAIL+1)); }

PLACEHOLDERS=$(grep -rl 'PLACEHOLDER\|待补充\|TODO\|\[论文标题\]' paper/sections/*.tex paper/main.tex 2>/dev/null | wc -l)

[ "$PLACEHOLDERS" -eq 0 ] && echo "✅ No placeholders" || { echo "❌ $PLACEHOLDERS files have placeholders"; GATE_FAIL=$((GATE_FAIL+1)); }

# --- WARNING ---

VBOX=$(grep -c 'Overfull.*vbox' paper/main.log 2>/dev/null || echo 0); [ "$VBOX" -eq 0 ] && echo "✅ No overflow" || { echo "❌ $VBOX overfull vbox"; GATE_FAIL=$((GATE_FAIL+1)); }

HBOX=$(grep -c 'Overfull.*hbox' paper/main.log 2>/dev/null || echo 0); [ "$HBOX" -lt 5 ] && echo "✅ Hbox: $HBOX" || { echo "❌ $HBOX overfull hbox"; GATE_FAIL=$((GATE_FAIL+1)); }

AI=0; for f in paper/sections/*.tex; do [ -f "$f" ] || continue; echo "$(basename $f)" | grep -qi 'appendix' && continue; c=$(grep -c '\\begin{itemize}' "$f" 2>/dev/null || echo 0); AI=$((AI+c)); done

[ "$AI" -eq 0 ] && echo "✅ No bullet lists" || { echo "❌ $AI itemize — convert to prose"; GATE_FAIL=$((GATE_FAIL+1)); }

UNDEF_REFS=$(grep -c 'LaTeX Warning.*Reference.*undefined' paper/main.log 2>/dev/null || echo 0)

[ "$UNDEF_REFS" -eq 0 ] && echo "✅ No undefined refs" || { echo "❌ $UNDEF_REFS undefined refs"; GATE_FAIL=$((GATE_FAIL+1)); }

STACKING=0; for f in paper/sections/*.tex; do [ -f "$f" ] || continue; s=$(awk '/\\end\{(figure|table)\}/{a=1;t=0;next} a&&/\\begin\{(figure|table)\}/{if(t<3)c++;a=0;next} a&&/[a-zA-Z\x80-\xff]{3,}/{t++} a&&t>=3{a=0} END{print c+0}' "$f" 2>/dev/null); STACKING=$((STACKING+s)); done

[ "$STACKING" -eq 0 ] && echo "✅ No figure stacking" || { echo "❌ $STACKING figure stacking"; GATE_FAIL=$((GATE_FAIL+1)); }

if grep -q 'tableofcontents' paper/main.tex 2>/dev/null; then

    [ -s paper/main.toc ] && echo "✅ TOC generated" || { echo "❌ TOC empty"; GATE_FAIL=$((GATE_FAIL+1)); }

fi

TIKZ=$(grep -rl 'tikzpicture\|tikz_diagrams\|tikz_' paper/sections/*.tex paper/main.tex 2>/dev/null | wc -l)

# Template integrity

TMPL=""

for t in _templates/mcm_main.tex _templates/stats_main.tex _templates/cumcm_main.tex; do [ -f "$t" ] && TMPL="$t" && break; done

if [ -n "$TMPL" ] && [ -f paper/main.tex ]; then

    TMPL_PRE=$(sed -n '1,/\\begin{document}/p' "$TMPL" | grep '\\usepackage\|\\documentclass\|\\pagestyle\|\\bibliography' | sort)

    MAIN_PRE=$(sed -n '1,/\\begin{document}/p' paper/main.tex | grep '\\usepackage\|\\documentclass\|\\pagestyle\|\\bibliography' | sort)

    MISSING=$(comm -23 <(echo "$TMPL_PRE") <(echo "$MAIN_PRE") 2>/dev/null | head -5)

    [ -z "$MISSING" ] && echo "✅ Template intact" || { echo "❌ Template preamble modified"; GATE_FAIL=$((GATE_FAIL+1)); }

    if grep -q 'PLACEHOLDER\|TODO\|\[Team Control Number\]' paper/main.tex 2>/dev/null; then

        echo "❌ Unreplaced placeholders"; GATE_FAIL=$((GATE_FAIL+1))

    else

        echo "✅ Placeholders replaced"

    fi

fi

if ls figures/tikz_*.pdf >/dev/null 2>&1; then

    TIKZ_PDF_MISSING=0

    for tpdf in figures/tikz_diagrams.pdf figures/tikz_diagrams_*.pdf figures/tikz_*.pdf; do

        [ -f "$tpdf" ] || continue

        grep -rq "$(basename "$tpdf")" paper/sections/*.tex paper/main.tex 2>/dev/null || TIKZ_PDF_MISSING=$((TIKZ_PDF_MISSING+1))

    done

    if [ "$TIKZ_PDF_MISSING" -gt 0 ]; then

        echo "❌ $TIKZ_PDF_MISSING TikZ PDF(s) not embedded in any section"; GATE_FAIL=$((GATE_FAIL+1))

    else

        echo "✅ TikZ embedded"

    fi

elif grep -qi 'tikz\|architecture\|roadmap' PAPER_PLAN.md PROBLEM_ANALYSIS.md 2>/dev/null; then

    [ "$TIKZ" -gt 0 ] && echo "✅ TikZ embedded" || echo "  ⚠ Plan mentions TikZ but no tikz_*.pdf found (may be replaced by DrawIO, non-blocking)"

else

    [ "$TIKZ" -gt 0 ] && echo "✅ TikZ: $TIKZ" || echo "  (no TikZ planned)"

fi

PLAN_FIGS=0; ACTUAL=$(ls figures/*.pdf 2>/dev/null | wc -l)

for plan in PAPER_PLAN.md PROBLEM_ANALYSIS.md TOPIC_PLAN.md; do [ -f "$plan" ] || continue; pf=$(grep -ci 'fig_\|figure.*:' "$plan" 2>/dev/null || echo 0); [ "$pf" -gt "$PLAN_FIGS" ] && PLAN_FIGS=$pf; done

if [ "$PLAN_FIGS" -gt 0 ]; then

    [ "$ACTUAL" -ge "$PLAN_FIGS" ] && echo "✅ Figures: $ACTUAL (plan: ~$PLAN_FIGS)" || { echo "❌ Only $ACTUAL figures (plan: ~$PLAN_FIGS)"; GATE_FAIL=$((GATE_FAIL+1)); }

else

    echo "  Figures: $ACTUAL PDFs"

fi

# Caption-too-long check has moved into writing_check.sh (its EXIT_CODE feeds WC_EXIT -> GATE_FAIL below); not duplicated here.

echo ""

[ "$GATE_FAIL" -eq 0 ] && echo "✅ ALL CRITICAL PASSED" || echo "❌ $GATE_FAIL FAILURES — fix and recompile"

```

**⛔ If GATE_FAIL > 0, fix every ❌, recompile, re-run gate. Do NOT finish with any ❌.**

### Step 8: Output report

Status, PDF path, page count, compliance pass/fail.


## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：LaTeX 引擎版本、页数、编译警告数。

## Key Rules

- No latexmk — manual step-by-step compilation

- Do not delete .bbl file after compilation

- Summary Sheet is critical for MCM/ICM

- APMCM: commitment letter must not be in PDF

- Body pages ≥ MAX_PAGES

- Primary output: `paper/main.pdf`, temp files: `_tmp/`

