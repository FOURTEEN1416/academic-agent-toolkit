---
name: paper-compile
description: "Compile English LaTeX paper to PDF using pdflatex. Use when user says \"compile paper\", \"build PDF\", or wants to compile an English academic paper."
argument-hint: [paper-directory]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# English Paper Compile: pdflatex → PDF

Compile an English LaTeX paper: **$ARGUMENTS**

## Constants

- **ENGINE = `pdflatex`**
- **MAX_COMPILE_ATTEMPTS = 3**
- **PAPER_DIR = `paper/`**
- **MAX_PAGES** — From Additional Parameters.

## Workflow

### Step 1: Verify environment

```bash
which pdflatex && which bibtex && echo "ready" || echo "pdflatex/bibtex not found"
```

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

The script auto-handles: special chars cleanup, table format fixes, includegraphics path correction, hidelinks, wide table resizebox wrapping, narrow table resizebox removal, light-color text fixes, TikZ library injection, unembedded figure detection.

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

### Step 3: Compile (manual steps, no latexmk)

```bash
cd paper/
rm -f main.aux main.blg main.log main.out main.toc 2>/dev/null
pdflatex -interaction=nonstopmode main.tex 2>&1 | tee compile_pass1.log
bibtex main 2>&1 | tee bibtex.log
pdflatex -interaction=nonstopmode main.tex 2>&1 | tee compile_pass2.log
pdflatex -interaction=nonstopmode main.tex 2>&1 | tee compile.log
[ -f main.pdf ] && echo "main.pdf $(wc -c < main.pdf) bytes" || echo "PDF not generated"
```

### Step 4: Error diagnosis and fix loop (MANDATORY)

After each compilation, check `main.log` for CRITICAL errors. **You MUST fix ALL errors before declaring compilation complete.**

```bash
MATH_ERR=$(grep -c 'Bad math environment delimiter\|Missing \$ inserted\|begin{document} ended by' paper/main.log 2>/dev/null || echo 0)
LR_ERR=$(grep -c 'Not allowed in LR mode' paper/main.log 2>/dev/null || echo 0)
echo "Math errors: $MATH_ERR, LR mode errors: $LR_ERR"
[ $((MATH_ERR + LR_ERR)) -gt 0 ] && grep -B2 'Bad math\|Missing \$ inserted\|Not allowed in LR mode' paper/main.log | grep -E '^\./|^l\.' | head -20
```

Iterate up to MAX_COMPILE_ATTEMPTS times, each with full 4-step compilation. For each error:
- **Math errors**: read the error location from main.log, open the file, fix broken `$...$` delimiters individually. Do NOT use broad sed patterns.
- **LR mode errors**: add `\par` or blank line before float environments.
- **Missing packages**: install them.
- **BibTeX failures**: fix LaTeX errors first (BibTeX fails when LaTeX errors exist upstream), then recompile.

After each fix, recompile and recheck. **⛔ Do NOT proceed until MATH_ERR = 0 and LR_ERR = 0.**

When fixing errors in main.tex, only fix the specific error. Do not rewrite or restructure main.tex — the template's preamble, page margins, and formatting settings must remain unchanged.

### Step 5: Post-compile checks

```bash
bash _utils/compile_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_check.sh paper/
```

### Step 6: Page count verification

Body pages = Introduction through Conclusion, excluding references and appendix.
Body pages must be ≥ MAX_PAGES. If insufficient, return to paper-write to expand content.

### Step 7: ⛔ FINAL QUALITY GATE

```bash
echo "=== Running check scripts ==="
bash _utils/compile_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_check.sh paper/ 2>/dev/null
bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/ 2>/dev/null

echo ""
echo "=========================================="
echo "  FINAL QUALITY GATE"
echo "=========================================="
GATE_FAIL=0
[ -f paper/main.pdf ] && [ $(wc -c < paper/main.pdf) -gt 50000 ] && echo "✅ PDF" || { echo "❌ PDF missing"; GATE_FAIL=$((GATE_FAIL+1)); }
MATH_ERR=$(grep -c 'Bad math.*delimiter\|Missing \$ inserted' paper/main.log 2>/dev/null || echo 0)
[ "$MATH_ERR" -eq 0 ] && echo "✅ No math errors" || { echo "❌ $MATH_ERR math errors"; GATE_FAIL=$((GATE_FAIL+1)); }
BBL=$(grep -c '\\bibitem' paper/main.bbl 2>/dev/null || echo 0)
[ "$BBL" -gt 0 ] && echo "✅ Bib: $BBL" || { echo "❌ Bib empty"; GATE_FAIL=$((GATE_FAIL+1)); }
CITE=$(grep -roh '\\cite{' paper/sections/*.tex paper/main.tex 2>/dev/null | wc -l)
[ "$CITE" -gt 0 ] && echo "✅ Citations: $CITE" || { echo "❌ No citations"; GATE_FAIL=$((GATE_FAIL+1)); }
UNEMBED=0; for pdf in figures/*.pdf; do [ -f "$pdf" ] || continue; bn=$(basename "$pdf"); grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null || UNEMBED=$((UNEMBED+1)); done
[ "$UNEMBED" -eq 0 ] && echo "✅ All figures embedded" || { echo "❌ $UNEMBED unembedded"; GATE_FAIL=$((GATE_FAIL+1)); }
PLACEHOLDERS=$(grep -rl 'PLACEHOLDER\|TODO' paper/sections/*.tex 2>/dev/null | wc -l)
[ "$PLACEHOLDERS" -eq 0 ] && echo "✅ No placeholders" || { echo "❌ $PLACEHOLDERS placeholders"; GATE_FAIL=$((GATE_FAIL+1)); }
VBOX=$(grep -c 'Overfull.*vbox' paper/main.log 2>/dev/null || echo 0); [ "$VBOX" -eq 0 ] && echo "✅ No overflow" || { echo "❌ $VBOX overfull vbox"; GATE_FAIL=$((GATE_FAIL+1)); }
HBOX=$(grep -c 'Overfull.*hbox' paper/main.log 2>/dev/null || echo 0); [ "$HBOX" -lt 5 ] && echo "✅ Hbox: $HBOX" || { echo "❌ $HBOX overfull hbox"; GATE_FAIL=$((GATE_FAIL+1)); }
AI=0; for f in paper/sections/*.tex; do [ -f "$f" ] || continue; c=$(grep -c '\\begin{itemize}' "$f" 2>/dev/null || echo 0); AI=$((AI+c)); done
[ "$AI" -eq 0 ] && echo "✅ No bullet lists" || { echo "❌ $AI itemize — convert to prose"; GATE_FAIL=$((GATE_FAIL+1)); }
UNDEF_REFS=$(grep -c 'LaTeX Warning.*Reference.*undefined' paper/main.log 2>/dev/null || echo 0)
[ "$UNDEF_REFS" -eq 0 ] && echo "✅ No undefined refs" || { echo "❌ $UNDEF_REFS undefined refs"; GATE_FAIL=$((GATE_FAIL+1)); }
STACKING=0; for f in paper/sections/*.tex; do [ -f "$f" ] || continue; s=$(awk '/\\end\{(figure|table)\}/{a=1;t=0;next} a&&/\\begin\{(figure|table)\}/{if(t<3)c++;a=0;next} a&&/[a-zA-Z\x80-\xff]{3,}/{t++} a&&t>=3{a=0} END{print c+0}' "$f" 2>/dev/null); STACKING=$((STACKING+s)); done
[ "$STACKING" -eq 0 ] && echo "✅ No figure stacking" || { echo "❌ $STACKING figure stacking"; GATE_FAIL=$((GATE_FAIL+1)); }
if grep -q 'tableofcontents' paper/main.tex 2>/dev/null; then
    [ -s paper/main.toc ] && echo "✅ TOC" || { echo "❌ TOC empty"; GATE_FAIL=$((GATE_FAIL+1)); }
fi
# TikZ 嵌入检测: TikZ 由 paper-figure-drawio 编译成 figures/tikz_diagrams.pdf,
# 通过 \includegraphics 嵌入(不是 sections 里的裸 tikzpicture 代码)。两种形态都算已嵌入。
TIKZ=$(grep -rl 'tikzpicture\|tikz_diagrams\|tikz_' paper/sections/*.tex paper/main.tex 2>/dev/null | wc -l)
# Template integrity
TMPL=""
for t in _templates/bachelor_main.tex _templates/master_main.tex _templates/journal_main.tex _templates/stats_main.tex _templates/cumcm_main.tex _templates/mcm_main.tex; do [ -f "$t" ] && TMPL="$t" && break; done
if [ -n "$TMPL" ] && [ -f paper/main.tex ]; then
    TMPL_PRE=$(sed -n '1,/\\begin{document}/p' "$TMPL" | grep '\\usepackage\|\\documentclass\|\\pagestyle\|\\bibliography' | sort)
    MAIN_PRE=$(sed -n '1,/\\begin{document}/p' paper/main.tex | grep '\\usepackage\|\\documentclass\|\\pagestyle\|\\bibliography' | sort)
    MISSING=$(comm -23 <(echo "$TMPL_PRE") <(echo "$MAIN_PRE") 2>/dev/null | head -5)
    [ -z "$MISSING" ] && echo "✅ Template intact" || { echo "❌ Template preamble modified"; GATE_FAIL=$((GATE_FAIL+1)); }
fi
# TikZ 计划检测: 只在"实际生成了 tikz_*.pdf 产物"时才硬核对(规划提了但用 DrawIO 替代时不误报)
TIKZ_PDF_TOTAL=0; TIKZ_PDF_MISSING=0
for tpdf in figures/tikz_diagrams.pdf figures/tikz_diagrams_*.pdf figures/tikz_*.pdf; do
    [ -f "$tpdf" ] || continue
    TIKZ_PDF_TOTAL=$((TIKZ_PDF_TOTAL+1))
    grep -rq "$(basename "$tpdf")" paper/sections/*.tex paper/main.tex 2>/dev/null || TIKZ_PDF_MISSING=$((TIKZ_PDF_MISSING+1))
done
if [ "$TIKZ_PDF_TOTAL" -gt 0 ]; then
    if [ "$TIKZ_PDF_MISSING" -gt 0 ]; then
        echo "❌ $TIKZ_PDF_MISSING TikZ PDF(s) not embedded in any section"; GATE_FAIL=$((GATE_FAIL+1))
    else
        echo "✅ TikZ embedded ($TIKZ_PDF_TOTAL)"
    fi
elif grep -qi 'tikz\|architecture\|roadmap' PAPER_PLAN.md 2>/dev/null; then
    [ "$TIKZ" -gt 0 ] && echo "✅ TikZ embedded" || echo "  ⚠ Plan mentions TikZ but no tikz_*.pdf found (may be replaced by DrawIO, non-blocking)"
else
    [ "$TIKZ" -gt 0 ] && echo "✅ TikZ: $TIKZ" || echo "  (no TikZ planned)"
fi
PLAN_FIGS=0; ACTUAL=$(ls figures/*.pdf 2>/dev/null | wc -l)
for plan in PAPER_PLAN.md; do [ -f "$plan" ] || continue; pf=$(grep -ci 'fig_\|figure.*:' "$plan" 2>/dev/null || echo 0); [ "$pf" -gt "$PLAN_FIGS" ] && PLAN_FIGS=$pf; done
if [ "$PLAN_FIGS" -gt 0 ]; then
    [ "$ACTUAL" -ge "$PLAN_FIGS" ] && echo "✅ Figures: $ACTUAL (plan: ~$PLAN_FIGS)" || { echo "❌ Only $ACTUAL figures (plan: ~$PLAN_FIGS)"; GATE_FAIL=$((GATE_FAIL+1)); }
else
    echo "  Figures: $ACTUAL PDFs"
fi

# Numerical consistency (JSON vs paper)
echo "--- Numerical consistency ---"
if [ -f figures/all_results.json ]; then
    python3 -c "
import json, re, os
try:
    with open('figures/all_results.json','r',encoding='utf-8') as f: results=json.load(f)
except Exception:
    print('⚠ all_results.json unreadable'); exit(0)
def extract(obj, p=''):
    n = {}
    if isinstance(obj, dict):
        for k, v in obj.items(): n.update(extract(v, f'{p}.{k}'))
    elif isinstance(obj, list):
        for i, v in enumerate(obj): n.update(extract(v, f'{p}[{i}]'))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if 0.001 < abs(obj) < 1e10: n[p] = obj
    return n
jn = extract(results)
pn = set()
section_dir = 'paper/sections' if os.path.isdir('paper/sections') else 'paper'
for tf in sorted(os.listdir(section_dir)):
    if not tf.endswith('.tex'): continue
    try:
        with open(f'{section_dir}/{tf}','r',encoding='utf-8',errors='ignore') as f: t=f.read()
    except: continue
    for m in re.finditer(r'(?<![a-zA-Z])(\d+\.?\d+)(?![a-zA-Z_{}])', t):
        try: pn.add(float(m.group(1)))
        except: pass
key_patterns = ['accuracy','acc','rmse','mae','r2','f1','auc','loss','precision','recall','bleu','rouge','perplexity','ppl','speed','latency','throughput','map','ndcg']
key_values = {k: v for k, v in jn.items() if any(w in k.lower() for w in key_patterns)}
miss = sum(1 for k, v in key_values.items() if not any(abs(p - v) < abs(v) * 0.01 + 0.001 for p in pn))
total = len(key_values)
if total == 0:
    print('  (no key metrics in JSON to check)')
elif miss > 3:
    print(f'❌ {miss}/{total} key values not found in paper — check numerical consistency'); exit(1)
else:
    print(f'✅ Numerical consistency: {total-miss}/{total} key values present in paper')
" 2>/dev/null
    [ $? -ne 0 ] && GATE_FAIL=$((GATE_FAIL+1))
else
    echo "  (no all_results.json to check against)"
fi

# Unrealistic values check (detect fabricated or overfitted values)
echo "--- Unrealistic values check ---"
if [ -f figures/all_results.json ]; then
    python3 -c "
import json
with open('figures/all_results.json','r',encoding='utf-8') as f: data=json.load(f)
suspicious = []
def check(name, val):
    if not isinstance(val,(int,float)) or isinstance(val,bool): return
    key = name.lower()
    if any(w in key for w in ['r2','r_squared','accuracy','acc','precision','recall','f1','auc']) and val > 0.999:
        suspicious.append(f'{name}={val:.4f} too perfect (>0.999), likely overfitted or leaked')
    if any(w in key for w in ['rmse','mae','mse','loss']) and val == 0:
        suspicious.append(f'{name}=0 perfect error, nearly impossible')
    if ('p_value' in key or 'pvalue' in key) and val == 0:
        suspicious.append(f'{name}=0 perfect significance')
    if any(w in key for w in ['improvement','speedup','gain']) and val > 10:
        suspicious.append(f'{name}={val} (+{val*100:.0f}%) unrealistically large')
def walk(obj, path=''):
    if isinstance(obj,dict):
        for k,v in obj.items(): walk(v, f'{path}.{k}')
    elif isinstance(obj,list):
        for i,v in enumerate(obj): walk(v, f'{path}[{i}]')
    else: check(path, obj)
walk(data)
if suspicious:
    print(f'🚩 {len(suspicious)} suspiciously perfect values (check for data leakage or fabrication):')
    for s in suspicious[:5]: print(f'    {s}')
    print('  If values are genuinely valid, discuss why in the paper')
else:
    print('✅ No suspicious values')
" 2>/dev/null
fi

# Reasonableness review section check
echo "--- Reasonableness review check ---"
if [ -f RESULTS.md ]; then
    if grep -iq 'reasonableness.*review\|sanity.*check\|合理性审查\|plausibility' RESULTS.md 2>/dev/null; then
        echo "✅ RESULTS.md has reasonableness review section"
    else
        echo "❌ RESULTS.md missing reasonableness review — go back to paper-analysis Step 1.5"
        GATE_FAIL=$((GATE_FAIL+1))
    fi
fi

# Data source timestamp consistency (code vs figures)
echo "--- Data source timestamp consistency ---"
if [ -f figures/all_results.json ]; then
    JSON_TIME=$(stat -c %Y figures/all_results.json 2>/dev/null || stat -f %m figures/all_results.json 2>/dev/null || echo 0)
    STALE_FIGS=0
    for pdf in figures/*.pdf; do
        [ -f "$pdf" ] || continue
        PDF_TIME=$(stat -c %Y "$pdf" 2>/dev/null || stat -f %m "$pdf" 2>/dev/null || echo 0)
        if [ "$JSON_TIME" -gt "$PDF_TIME" ] && [ "$((JSON_TIME - PDF_TIME))" -gt 60 ]; then
            echo "  ⚠ $(basename $pdf) older than all_results.json — figure data may be stale"
            STALE_FIGS=$((STALE_FIGS+1))
        fi
    done
    if [ "$STALE_FIGS" -gt 0 ]; then
        echo "  ❌ $STALE_FIGS figures may use outdated data (JSON updated after figures were generated)"
        GATE_FAIL=$((GATE_FAIL+1))
    else
        echo "✅ Data source timestamps consistent"
    fi
fi

# Meta content leak (internal filenames showing in paper)
echo "--- Meta content leak ---"
META=0
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    l=$(grep -ci 'RESULTS\.md\|CLAUDE\.md\|MODELING_REPORT\|PROBLEM_ANALYSIS\|PAPER_PLAN\|latex_includes\|all_results\.json' "$f" 2>/dev/null || echo 0)
    META=$((META+l))
done
[ "$META" -eq 0 ] && echo "✅ No meta leaks" || { echo "❌ $META meta content leaks — remove references to internal files"; GATE_FAIL=$((GATE_FAIL+1)); }

# Overclaiming
echo "--- Overclaiming ---"
OC=0
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    for w in "首次提出" "首次发现" "完美" "无可比拟" "前所未有" "开创性" "revolutionary" "unprecedented" "groundbreaking"; do
        c=$(grep -ci "$w" "$f" 2>/dev/null || echo 0); OC=$((OC+c))
    done
done
[ "$OC" -eq 0 ] && echo "✅ No overclaiming" || echo "⚠ $OC overclaiming instances"

# Claims-Evidence backfill (does paper cover all planned claims?)
echo "--- Claims coverage ---"
if [ -f PAPER_PLAN.md ]; then
    python3 -c "
import re, os
try: plan = open('PAPER_PLAN.md','r',encoding='utf-8').read()
except: exit(0)
rows = re.findall(r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|', plan)
claims = [c.strip() for c, e in rows if c.strip() not in ('Claim','---') and '---' not in c and len(c.strip()) > 8]
if not claims:
    print('  (no claims-evidence matrix in PAPER_PLAN.md)'); exit(0)
# 读取所有论文章节
section_dir = 'paper/sections' if os.path.isdir('paper/sections') else 'paper'
paper_text = ''
for tf in sorted(os.listdir(section_dir)):
    if tf.endswith('.tex'):
        try: paper_text += open(f'{section_dir}/{tf}','r',encoding='utf-8',errors='ignore').read()
        except: pass
# 对每个 claim，提取关键词，在论文里找
missing = []
for c in claims[:15]:
    keywords = [w for w in re.findall(r'[a-zA-Z_]{4,}|[\u4e00-\u9fff]{2,}', c) if len(w) > 3][:3]
    if keywords and not any(kw.lower() in paper_text.lower() for kw in keywords):
        missing.append(c[:50])
if missing:
    print(f'❌ {len(missing)}/{len(claims)} planned claims not covered in paper:')
    for m in missing[:5]: print(f'    - {m}')
    exit(1)
else:
    print(f'✅ All {len(claims)} planned claims covered in paper')
" 2>/dev/null
    [ $? -ne 0 ] && GATE_FAIL=$((GATE_FAIL+1))
fi
echo ""
[ "$GATE_FAIL" -eq 0 ] && echo "✅ ALL PASSED" || echo "❌ $GATE_FAIL FAILURES — fix and recompile"
```

**⛔ If GATE_FAIL > 0, fix and recompile. Do NOT finish with ❌.**

### Step 8: Output report

Status, PDF path, page count, compliance results, fixed errors, remaining warnings.

## Key Rules

- No latexmk — manual step-by-step compilation
- Use `-interaction=nonstopmode`, not `-halt-on-error`
- Do not delete .bbl file (bibliography data)
- Figure embedding is the compile step's responsibility — fix missing labels from figures/*.tex
- Bibliography is a core validation item — final PDF must not have `[?]`
- Primary output: `paper/main.pdf`, compile log: `paper/compile.log`
- Temp files: `_tmp/` directory
