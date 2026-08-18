---
name: paper-compile-zh
description: "Compile Chinese LaTeX paper to PDF using XeLaTeX. Use when user says \"编译中文论文\", \"compile Chinese paper\", \"中文PDF\", or wants to compile a Chinese academic paper."
argument-hint: [paper-directory]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# Chinese Paper Compile: XeLaTeX → PDF

Compile a Chinese LaTeX paper: **$ARGUMENTS**

## Constants

- **ENGINE = `xelatex`** — Required for Chinese text
- **MAX_COMPILE_ATTEMPTS = 3**
- **PAPER_DIR = `paper/`**
- **MAX_PAGES** — From Additional Parameters.
- **PAPER_TYPE** — bachelor/master/journal

## Workflow

### Step 1: Verify environment

```bash
if ! which xelatex 2>/dev/null; then
    echo "xelatex not found, attempting install..."
    if which miktex 2>/dev/null; then
        miktex packages install xetex ctex xecjk gbt7714 fontspec
        miktex fndb refresh
    elif which initexmf 2>/dev/null; then
        initexmf --set-config-value=[MPM]AutoInstall=1
    fi
fi
which xelatex && which bibtex && echo "ready" || echo "xelatex/bibtex not found"
fc-list :lang=zh | head -5
kpsewhich gbt7714.sty 2>/dev/null || echo "gbt7714.sty not found (will auto-install on first compile)"
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

The script auto-handles: special chars cleanup (emoji, zero-width chars, Unicode math → LaTeX), table format fixes (single → double backslash), includegraphics path correction, hidelinks, figures/figures/ nesting, PDF existence check, math_commands conflicts, wide table resizebox wrapping, narrow table resizebox removal, light-color text fixes, `on background layer` removal, TikZ library injection (backgrounds + fit).

If script not found, perform these steps manually.

### Step 3: Figure completeness check

```bash
mkdir -p _tmp
grep -oh '\\ref{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null | sort -u > _tmp/_refs.txt
grep -oh '\\label{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null | sort -u > _tmp/_labels.txt
comm -23 <(sed 's/\\ref/\\label/g' _tmp/_refs.txt) _tmp/_labels.txt > _tmp/_missing_labels.txt
cat _tmp/_missing_labels.txt
```

If labels are missing, find corresponding figure/table code in `figures/*.tex` and embed into the correct section file. Figure embedding is the compile step's responsibility — do not just warn, actually fix it by copying the figure/table block from `figures/*.tex` into the appropriate section.

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
    bn=$(basename "$tbl")
    for lbl in $(grep -oh '\\label{[^}]*}' "$tbl" 2>/dev/null); do
        grep -rq "$lbl" paper/sections/*.tex paper/main.tex 2>/dev/null || { echo "UNEMBEDDED TABLE: $lbl (from $bn)"; UNEMBED=$((UNEMBED+1)); }
    done
done
if [ -f figures/latex_includes.tex ]; then
    for lbl in $(grep -oh '\\label{[^}]*}' figures/latex_includes.tex 2>/dev/null); do
        grep -rq "$lbl" paper/sections/*.tex paper/main.tex 2>/dev/null || { echo "UNEMBEDDED: $lbl"; UNEMBED=$((UNEMBED+1)); }
    done
fi
echo "Total unembedded: $UNEMBED"
```

If UNEMBED > 0, fix ALL before compiling. For each:
- **PDF**: copy `\begin{figure}...\end{figure}` from `figures/latex_includes.tex` into target section
- **TABLE_*.tex**: paste the `\begin{table}...\end{table}` block into target section
- Add lead-in text + analysis after each embedded item
- Re-run count check — repeat until UNEMBED = 0

### Step 3.5: 模板完整性检查（编译前必须通过）

```bash
echo "=== main.tex 模板完整性检查（编译前）==="
FAIL=0
grep -q 'documentclass' paper/main.tex || { echo "❌ 缺少 documentclass"; FAIL=$((FAIL+1)); }
grep -q '\\input{sections/' paper/main.tex || { echo "❌ 缺少 sections input"; FAIL=$((FAIL+1)); }
grep -q 'thebibliography\|bibliography{' paper/main.tex || { echo "❌ 缺少参考文献"; FAIL=$((FAIL+1)); }
grep -q 'superscript\|\\@cite\|setcitestyle.*super' paper/main.tex || { echo "❌ 缺少上标引用"; FAIL=$((FAIL+1)); }
# 五一杯
if grep -qi 'wuyi\|五一杯' CLAUDE.md 2>/dev/null; then
    grep -q '承诺书' paper/main.tex || { echo "❌ 五一杯缺少承诺书页"; FAIL=$((FAIL+1)); }
    grep -q 'image2' paper/main.tex || { echo "❌ 五一杯缺少封面logo"; FAIL=$((FAIL+1)); }
fi
[ "$FAIL" -eq 0 ] && echo "✅ 模板完整性检查通过" || echo "⛔ $FAIL 项失败 — main.tex 可能被重写了，必须从模板恢复"
```

**⛔ 如果模板检查失败，必须从模板目录重新复制 main.tex 并只替换占位符，不要继续编译。**

### Step 4: Compile (manual steps, no latexmk)

```bash
cd paper/
# Keep main.pdf (old version) and main.bbl (bibliography data), only delete intermediate files
rm -f main.aux main.blg main.log main.out main.toc main.xdv 2>/dev/null
xelatex -interaction=nonstopmode main.tex 2>&1 | tee compile_pass1.log
bibtex main 2>&1 | tee bibtex.log
xelatex -interaction=nonstopmode main.tex 2>&1 | tee compile_pass2.log
xelatex -interaction=nonstopmode main.tex 2>&1 | tee compile.log
[ -f main.pdf ] && echo "main.pdf $(wc -c < main.pdf) bytes" || echo "PDF not generated"
```

### Step 5: Error diagnosis and fix loop (MANDATORY)

After each compilation, check `main.log` for CRITICAL errors. **You MUST fix ALL errors before declaring compilation complete.**

```bash
MATH_ERR=$(grep -c 'Bad math environment delimiter\|Missing \$ inserted\|begin{document} ended by' paper/main.log 2>/dev/null || echo 0)
LR_ERR=$(grep -c 'Not allowed in LR mode' paper/main.log 2>/dev/null || echo 0)
echo "Math errors: $MATH_ERR, LR mode errors: $LR_ERR"
[ $((MATH_ERR + LR_ERR)) -gt 0 ] && grep -B2 'Bad math\|Missing \$ inserted\|Not allowed in LR mode' paper/main.log | grep -E '^\./|^l\.' | head -20
```

Iterate up to MAX_COMPILE_ATTEMPTS times, each with full 4-step compilation (xelatex → bibtex → xelatex → xelatex). For each error:
- **Math errors**: read the error location from main.log, open the file, fix broken `$...$` delimiters individually. Do NOT use broad sed patterns.
- **LR mode errors**: add `\par` or blank line before float environments.
- **Missing packages**: `tlmgr install` or miktex auto-install.
- **Font not found**: check `fc-list`.
- **BibTeX failures**: fix LaTeX errors first (BibTeX fails when LaTeX errors exist upstream), then recompile.

After each fix, recompile and recheck. **⛔ Do NOT proceed until MATH_ERR = 0 and LR_ERR = 0.**

When fixing errors in main.tex, only fix the specific error. Do not rewrite or restructure main.tex — the template's preamble, cover page, page margins, section numbering format, and header/footer settings must remain unchanged.

### Step 6: Post-compile checks

```bash
bash _utils/compile_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_check.sh paper/
```

The script checks: PDF existence/size, undefined references, overfull hbox, TOC, Chinese/English abstracts, bibliography command and entries, citation count in body, unused figures, figure stacking, TikZ diagram presence against plan.

Run compile_utils.sh post-compile checks too (items 10-13: TOC, abstracts, bibliography config, unused figures).

### Step 7: Page count verification

Body pages = chapter 1 through conclusion, excluding cover/abstract/TOC/references/acknowledgments/appendix.

Body pages must be ≥ MAX_PAGES. If insufficient, return to paper-write-zh to expand content. Exceeding MAX_PAGES is allowed.

### Step 8: ⛔ FINAL QUALITY GATE

```bash
echo "=========================================="
echo "  FINAL QUALITY GATE"
echo "=========================================="
GATE_FAIL=0

# 1. PDF
[ -f paper/main.pdf ] && [ $(wc -c < paper/main.pdf) -gt 100000 ] && echo "✅ PDF exists" || { echo "❌ PDF missing"; GATE_FAIL=$((GATE_FAIL+1)); }

# 2. No LaTeX errors
MATH_ERR=$(grep -c 'Bad math.*delimiter\|Missing \$ inserted' paper/main.log 2>/dev/null || echo 0)
LR_ERR=$(grep -c 'Not allowed in LR mode' paper/main.log 2>/dev/null || echo 0)
[ "$((MATH_ERR+LR_ERR))" -eq 0 ] && echo "✅ No LaTeX errors" || { echo "❌ $MATH_ERR math + $LR_ERR LR errors"; GATE_FAIL=$((GATE_FAIL+1)); }

# 3. Bibliography
BBL=$(grep -c '\\bibitem' paper/main.bbl 2>/dev/null || echo 0)
[ "$BBL" -gt 0 ] && echo "✅ Bib: $BBL entries" || { echo "❌ Bib empty"; GATE_FAIL=$((GATE_FAIL+1)); }

# 4. Unembedded figures
UNEMBED=0
for pdf in figures/*.pdf; do [ -f "$pdf" ] || continue; bn=$(basename "$pdf"); grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null || UNEMBED=$((UNEMBED+1)); done
[ "$UNEMBED" -eq 0 ] && echo "✅ All figures embedded" || { echo "❌ $UNEMBED unembedded"; GATE_FAIL=$((GATE_FAIL+1)); }

# 5. Overfull vbox
VBOX=$(grep -c 'Overfull.*vbox' paper/main.log 2>/dev/null || echo 0)
[ "$VBOX" -eq 0 ] && echo "✅ No overflow" || { echo "❌ $VBOX overfull vbox"; GATE_FAIL=$((GATE_FAIL+1)); }

# 6. AI lists
AI_LISTS=0
for f in paper/sections/*.tex; do [ -f "$f" ] || continue; echo "$(basename $f)" | grep -qi 'appendix\|附录' && continue; c=$(grep -c '\\begin{itemize}' "$f" 2>/dev/null || echo 0); AI_LISTS=$((AI_LISTS+c)); done
[ "$AI_LISTS" -eq 0 ] && echo "✅ No bullet lists" || { echo "❌ $AI_LISTS itemize — convert to prose"; GATE_FAIL=$((GATE_FAIL+1)); }

# 7. Template integrity — compare against original template
TMPL=""
for t in _templates/stats_main.tex _templates/cumcm_main.tex _templates/bachelor_main.tex _templates/master_main.tex _templates/journal_main.tex; do [ -f "$t" ] && TMPL="$t" && break; done
if [ -n "$TMPL" ] && [ -f paper/main.tex ]; then
    TMPL_PRE=$(sed -n '1,/\\begin{document}/p' "$TMPL" | grep '\\usepackage\|\\documentclass\|\\ctexset\|\\pagestyle\|\\listoftables\|\\listoffigures\|\\cline\|\\bibliography' | sort)
    MAIN_PRE=$(sed -n '1,/\\begin{document}/p' paper/main.tex | grep '\\usepackage\|\\documentclass\|\\ctexset\|\\pagestyle\|\\listoftables\|\\listoffigures\|\\cline\|\\bibliography' | sort)
    MISSING=$(comm -23 <(echo "$TMPL_PRE") <(echo "$MAIN_PRE") 2>/dev/null | head -5)
    [ -z "$MISSING" ] && echo "✅ Template preamble intact" || { echo "❌ Template preamble modified"; echo "$MISSING" | sed 's/^/    /'; GATE_FAIL=$((GATE_FAIL+1)); }
    if grep -q '参赛学校\|参赛作品' "$TMPL" 2>/dev/null; then
        grep -q '参赛学校\|参赛作品' paper/main.tex 2>/dev/null && echo "✅ Cover page" || { echo "❌ Cover missing"; GATE_FAIL=$((GATE_FAIL+1)); }
        grep -q 'cline{2-2}' paper/main.tex 2>/dev/null && echo "✅ Cover cline" || { echo "❌ Cover cline missing"; GATE_FAIL=$((GATE_FAIL+1)); }
    fi
    if grep -q '\[论文标题\]\|\[学校名称\]\|\[队员1\]\|\[中文摘要内容\]' paper/main.tex 2>/dev/null; then
        echo "❌ Unreplaced placeholders"; GATE_FAIL=$((GATE_FAIL+1))
    else
        echo "✅ Placeholders replaced"
    fi
    if grep -P '^(表|图)\d+\.' paper/main.tex 2>/dev/null | head -1 | grep -q '.'; then
        echo "❌ Hand-written list"; GATE_FAIL=$((GATE_FAIL+1))
    fi
else
    echo "  (no template for comparison)"
fi

# 8. TikZ check
TIKZ=$(grep -rl 'tikzpicture' paper/sections/*.tex 2>/dev/null | wc -l)
[ "$TIKZ" -gt 0 ] && echo "✅ TikZ: $TIKZ sections" || { echo "❌ No TikZ diagrams"; GATE_FAIL=$((GATE_FAIL+1)); }

# 9. Citations
CITE=$(grep -roh '\\cite{' paper/sections/*.tex paper/main.tex 2>/dev/null | wc -l)
[ "$CITE" -gt 0 ] && echo "✅ Citations: $CITE" || { echo "❌ No citations"; GATE_FAIL=$((GATE_FAIL+1)); }

# 10. Placeholders
PLACEHOLDERS=$(grep -rl 'PLACEHOLDER\|待补充\|TODO\|\[论文标题\]\|\[中文摘要内容\]' paper/sections/*.tex paper/main.tex 2>/dev/null | wc -l)
[ "$PLACEHOLDERS" -eq 0 ] && echo "✅ No placeholders" || { echo "❌ $PLACEHOLDERS files have placeholders"; GATE_FAIL=$((GATE_FAIL+1)); }

# 11. Overfull hbox
HBOX=$(grep -c 'Overfull.*hbox' paper/main.log 2>/dev/null || echo 0); [ "$HBOX" -lt 5 ] && echo "✅ Hbox: $HBOX" || { echo "❌ $HBOX overfull hbox"; GATE_FAIL=$((GATE_FAIL+1)); }

# 12. Abstracts
grep -rq '摘.*要' paper/sections/*.tex paper/main.tex 2>/dev/null && echo "✅ Chinese abstract" || { echo "❌ No Chinese abstract"; GATE_FAIL=$((GATE_FAIL+1)); }
grep -rq 'Abstract' paper/sections/*.tex paper/main.tex 2>/dev/null && echo "✅ English abstract" || { echo "❌ No English abstract"; GATE_FAIL=$((GATE_FAIL+1)); }

# 13. 数值一致性（JSON vs 论文）— 防止 LLM 编造实验数值
echo "--- 数值一致性 ---"
if [ -f figures/all_results.json ]; then
    python3 -c "
import json, re, os
try:
    with open('figures/all_results.json','r',encoding='utf-8') as f: results=json.load(f)
except Exception:
    print('⚠ all_results.json 无法读取'); exit(0)
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
key_patterns = ['accuracy','acc','rmse','mae','r2','f1','auc','loss','precision','recall','objective','optimal','best','准确率','精度','误差']
key_values = {k: v for k, v in jn.items() if any(w in k.lower() for w in key_patterns)}
miss = sum(1 for k, v in key_values.items() if not any(abs(p - v) < abs(v) * 0.01 + 0.001 for p in pn))
total = len(key_values)
if total == 0:
    print('  (JSON 中无关键指标可对比)')
elif miss > 3:
    print(f'❌ {miss}/{total} 关键数值在论文中找不到 — 检查是否有数值编造'); exit(1)
else:
    print(f'✅ 数值一致性: {total-miss}/{total} 关键数值已在论文中出现')
" 2>/dev/null
    [ $? -ne 0 ] && GATE_FAIL=$((GATE_FAIL+1))
else
    echo "  (无 all_results.json 可对比)"
fi

# 13.5 "太完美"结果检测（防 AI 编造或过拟合）
echo "--- 数值合理性检查（太完美特征）---"
if [ -f figures/all_results.json ]; then
    python3 -c "
import json
with open('figures/all_results.json','r',encoding='utf-8') as f: data=json.load(f)
suspicious = []
def check(name, val):
    if not isinstance(val,(int,float)) or isinstance(val,bool): return
    key = name.lower()
    if any(w in key for w in ['r2','r_squared','accuracy','acc','precision','recall','f1','auc']) and val > 0.999:
        suspicious.append(f'{name}={val:.4f} 过于完美（>0.999），疑似过拟合或数据泄漏')
    if any(w in key for w in ['rmse','mae','mse','loss']) and val == 0:
        suspicious.append(f'{name}=0 完美误差，现实中几乎不可能')
    if ('p_value' in key or 'pvalue' in key or 'p值' in key) and val == 0:
        suspicious.append(f'{name}=0 完美显著')
    if any(w in key for w in ['improvement','speedup','gain','提升','改进']) and val > 10:
        suspicious.append(f'{name}={val}（提升 {val*100:.0f}%）数值过大')
def walk(obj, path=''):
    if isinstance(obj,dict):
        for k,v in obj.items(): walk(v, f'{path}.{k}')
    elif isinstance(obj,list):
        for i,v in enumerate(obj): walk(v, f'{path}[{i}]')
    else: check(path, obj)
walk(data)
if suspicious:
    print(f'🚩 {len(suspicious)} 处数值过于完美（可能编造或过拟合）:')
    for s in suspicious[:5]: print(f'    {s}')
    print('  若数据确实支持这些结果，在论文讨论中说明原因')
else:
    print('✅ 无异常完美数值')
" 2>/dev/null
fi

# 13.6 合理性审查章节是否存在
echo "--- 合理性审查章节检查 ---"
if [ -f RESULTS.md ]; then
    if grep -q '合理性审查\|数值合理\|背景对照\|sanity.*check' RESULTS.md 2>/dev/null; then
        echo "✅ RESULTS.md 包含合理性审查章节"
    else
        echo "❌ RESULTS.md 缺少合理性审查章节 — 回到 paper-analysis Step 1.5 补充"
        GATE_FAIL=$((GATE_FAIL+1))
    fi
fi

# 13.7 数据源时间戳一致性（代码 vs 图表）
echo "--- 数据源时间戳一致性 ---"
if [ -f figures/all_results.json ]; then
    JSON_TIME=$(stat -c %Y figures/all_results.json 2>/dev/null || stat -f %m figures/all_results.json 2>/dev/null || echo 0)
    STALE_FIGS=0
    for pdf in figures/*.pdf; do
        [ -f "$pdf" ] || continue
        PDF_TIME=$(stat -c %Y "$pdf" 2>/dev/null || stat -f %m "$pdf" 2>/dev/null || echo 0)
        if [ "$JSON_TIME" -gt "$PDF_TIME" ] && [ "$((JSON_TIME - PDF_TIME))" -gt 60 ]; then
            echo "  ⚠ $(basename $pdf) 比 all_results.json 旧 — 图表数据可能过期"
            STALE_FIGS=$((STALE_FIGS+1))
        fi
    done
    if [ "$STALE_FIGS" -gt 0 ]; then
        echo "  ❌ $STALE_FIGS 张图表可能使用了旧数据（JSON 更新后图表未重新生成）"
        GATE_FAIL=$((GATE_FAIL+1))
    else
        echo "✅ 数据源时间戳一致"
    fi
fi

# 13.8 正文长表格检测（>12 行不应在正文完整展开）
echo "--- 正文长表格检测 ---"
LONG_TABLES=0
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    echo "$(basename $f)" | grep -qi 'appendix\|附录\|A_code' && continue
    COUNT=$(grep -c '\\\\' "$f" 2>/dev/null || echo 0)
    # 粗略检测：如果单个文件里 \\ 超过 50 个且包含 longtable/tabular，大概率有超长表格
    if [ "$COUNT" -gt 40 ]; then
        HAS_TABLE=$(grep -c 'begin{longtable}\|begin{tabular}' "$f" 2>/dev/null || echo 0)
        if [ "$HAS_TABLE" -gt 0 ]; then
            echo "  ❌ $(basename $f): 疑似超长表格（$COUNT 行 + $HAS_TABLE 个表格环境）— 应截断正文（>12行），完整版放附录"
            LONG_TABLES=$((LONG_TABLES+1))
        fi
    fi
done
[ "$LONG_TABLES" -eq 0 ] && echo "✅ 正文无超长表格" || GATE_FAIL=$((GATE_FAIL+1))

# 14. 元叙述泄露（内部文件名不该出现在论文里）
echo "--- 元叙述泄露 ---"
META=0
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    l=$(grep -ci 'RESULTS\.md\|CLAUDE\.md\|MODELING_REPORT\|PROBLEM_ANALYSIS\|PAPER_PLAN\|latex_includes\|all_results\.json' "$f" 2>/dev/null || echo 0)
    META=$((META+l))
done
[ "$META" -eq 0 ] && echo "✅ 无元叙述泄露" || { echo "❌ $META 处泄露了内部文件名"; GATE_FAIL=$((GATE_FAIL+1)); }

# 15. 过度声称
echo "--- 过度声称 ---"
OC=0
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    for w in "首次提出" "首次发现" "完美" "无可比拟" "前所未有" "开创性" "革命性"; do
        c=$(grep -c "$w" "$f" 2>/dev/null || echo 0); OC=$((OC+c))
    done
done
[ "$OC" -eq 0 ] && echo "✅ 无过度声称" || echo "⚠ $OC 处过度声称（建议温和化）"

# 16. Claims-Evidence 回填验证（论文是否覆盖了规划中的所有论断）
echo "--- Claims 覆盖检查 ---"
if [ -f PAPER_PLAN.md ]; then
    python3 -c "
import re, os
try: plan = open('PAPER_PLAN.md','r',encoding='utf-8').read()
except: exit(0)
rows = re.findall(r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|', plan)
claims = [c.strip() for c, e in rows if c.strip() not in ('Claim','观点','---') and '---' not in c and len(c.strip()) > 8]
if not claims:
    print('  （PAPER_PLAN.md 中无 claims-evidence 矩阵）'); exit(0)
section_dir = 'paper/sections' if os.path.isdir('paper/sections') else 'paper'
paper_text = ''
for tf in sorted(os.listdir(section_dir)):
    if tf.endswith('.tex'):
        try: paper_text += open(f'{section_dir}/{tf}','r',encoding='utf-8',errors='ignore').read()
        except: pass
missing = []
for c in claims[:15]:
    keywords = [w for w in re.findall(r'[a-zA-Z_]{4,}|[\u4e00-\u9fff]{2,}', c) if len(w) > 3][:3]
    if keywords and not any(kw.lower() in paper_text.lower() for kw in keywords):
        missing.append(c[:50])
if missing:
    print(f'❌ {len(missing)}/{len(claims)} 规划中的论断在论文中未覆盖:')
    for m in missing[:5]: print(f'    - {m}')
    exit(1)
else:
    print(f'✅ 规划中的 {len(claims)} 个论断均已在论文中覆盖')
" 2>/dev/null
    [ $? -ne 0 ] && GATE_FAIL=$((GATE_FAIL+1))
fi

# 16. Run check scripts for full details
echo ""
echo "--- Full check scripts ---"
bash _utils/compile_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_check.sh paper/ 2>/dev/null
bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/ 2>/dev/null

echo ""
[ "$GATE_FAIL" -eq 0 ] && echo "✅ ALL CRITICAL PASSED" || echo "❌ $GATE_FAIL FAILURES — fix and recompile"
```

**⛔ If GATE_FAIL > 0, fix every ❌, recompile, re-run gate. Do NOT finish with any ❌.**

### Step 9: Output report

Status, PDF path, page count, compliance results, fixed errors, remaining warnings.

## Key Rules

- No latexmk — manual step-by-step compilation
- Use `-interaction=nonstopmode`, not `-halt-on-error`
- Do not delete .bbl file (bibliography data) — also do not write cleanup scripts that delete .bbl
- Figure embedding is the compile step's responsibility — fix missing labels from figures/*.tex
- Bibliography is a core validation item — final PDF must not have `[?]`
- Primary output: `paper/main.pdf`, compile log: `paper/compile.log`
- Temp files: `_tmp/` directory
