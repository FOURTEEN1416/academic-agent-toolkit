---
name: comp-compile-zh
description: "数学建模竞赛中文论文编译与合规检查。编译 PDF 并检查页数、匿名、格式等竞赛要求。Use when user says \"编译竞赛论文\", \"compile competition paper\"."
argument-hint: [paper-directory]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# Competition Paper Compile & Compliance (Chinese)

Compile and validate: **$ARGUMENTS**

## Constants

- **ENGINE = `xelatex`**
- **MAX_COMPILE_ATTEMPTS = 3**
- **PAPER_DIR = `paper/`**
- **MAX_PAGES** / **COMPETITION** — From Additional Parameters.

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

The script auto-handles: special chars cleanup, table format fixes, includegraphics path correction (`figures/` → `../figures/`), hidelinks, figures/figures/ nesting, math_commands conflicts, wide table resizebox wrapping, narrow table resizebox removal, light-color text fixes, TikZ library injection.

If script not found, perform these steps manually.

**⛔ 表格行结束符修复（Misplaced \noalign 的根因）：**
```bash
# 检测并修复 tabular/longtable 中的单 \ 行结束符（应该是 \\）
# 这是 heredoc 不加引号导致 \\ 被转义为 \ 的常见问题
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    # 检测：tabular 环境内，行末只有单个 \ 后跟换行（应该是 \\）
    if grep -P '(?<!\\)\\(?!\\)(?=\s*$)' "$f" | grep -v '\\begin\|\\end\|\\hline\|\\toprule\|\\midrule\|\\bottomrule\|\\caption\|\\label\|\\centering\|\\input\|\\include\|\\usepackage\|\\section\|\\subsection' > /dev/null 2>&1; then
        echo "⚠ $(basename $f): 可能有表格行结束符问题（单 \\ 应为 \\\\）"
        # 在 tabular/longtable 环境内，把行末的单 \ 替换为 \\
        python3 -c "
import re
with open('$f', 'r', encoding='utf-8') as fh:
    content = fh.read()
# 只在 tabular/longtable 环境内修复
def fix_table_endings(match):
    table = match.group(0)
    # 把数据行末尾的单 \ (后跟换行) 替换为 \\\\
    fixed = re.sub(r'(?<=&[^&\n]*)\\\s*\n', r'\\\\\\\\\n', table)
    return fixed
for env in ['tabular', 'longtable']:
    pattern = r'(\\\\begin\{' + env + r'[*]?\}.*?\\\\end\{' + env + r'[*]?\})'
    content = re.sub(pattern, fix_table_endings, content, flags=re.DOTALL)
with open('$f', 'w', encoding='utf-8') as fh:
    fh.write(content)
" 2>/dev/null
    fi
done
```

Also check ref/label matching and embed missing figures:
```bash
mkdir -p _tmp
grep -oh '\\ref{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null | sort -u > _tmp/_refs.txt
grep -oh '\\label{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null | sort -u > _tmp/_labels.txt
comm -23 <(sed 's/\\ref/\\label/g' _tmp/_refs.txt) _tmp/_labels.txt > _tmp/_missing_labels.txt
cat _tmp/_missing_labels.txt
```

**⛔ 中文引号统一为全角引号（避免 PDF 出现 ''乱码或两个堆叠反引号）：**

中文论文用 xeCJK，全角引号 `"..."` 会自动渲染为漂亮的对称弯引号。
LaTeX 风格 `` ``...'' `` 在中文字体下会显示成两个堆叠的反引号，很丑。
ASCII 直引号 `"..."` 在 LaTeX 中渲染为右右引号 `''...''`。
统一替换为全角引号。

```bash
# 把所有错误引号统一为全角引号
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    python3 -c "
import re
content = open('$f', 'r', encoding='utf-8').read()
# 保护数学环境
placeholders = []
def stash(m):
    placeholders.append(m.group(0)); return f'\\x00M{len(placeholders)-1}\\x00'
content = re.sub(r'\\\$[^\\\$]*\\\$', stash, content)
content = re.sub(r'\\\\\\[.*?\\\\\\]', stash, content, flags=re.DOTALL)
# 保护 \begin{verbatim}/lstlisting 等代码环境
content = re.sub(r'\\\\begin\{(verbatim|lstlisting|minted)\}.*?\\\\end\{\\1\}', stash, content, flags=re.DOTALL)

# 1. LaTeX 风格 ``...'' → 全角双引号
content = re.sub(r\"\`\`([^\`'\\\\n]+?)''\", '\u201c\\\\g<1>\u201d', content)
# 2. ASCII 直引号 \"...\" → 全角双引号（成对处理）
parts = content.split('\"')
if len(parts) > 2:
    result = parts[0]
    for i, p in enumerate(parts[1:], 1):
        result += ('\u201c' if i % 2 == 1 else '\u201d') + p
    content = result

# 还原
for i, ph in enumerate(placeholders):
    content = content.replace(f'\\x00M{i}\\x00', ph)
open('$f', 'w', encoding='utf-8').write(content)
" 2>/dev/null
done
```

If labels are missing, find corresponding figure/table code in `figures/*.tex` and embed into the correct section file.

Also check compile_utils.sh output for "UNEMBEDDED" warnings — each one means a figure or table from `figures/` is not in any section.

**MANDATORY FIX LOOP — do NOT proceed to compilation until all figures AND tables are embedded:**

```bash
UNEMBED=0
# Check PDF figures
for pdf in figures/*.pdf; do
    [ -f "$pdf" ] || continue
    bn=$(basename "$pdf")
    grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null || { echo "UNEMBEDDED PDF: $bn"; UNEMBED=$((UNEMBED+1)); }
done
# Check TABLE_*.tex files
for tbl in figures/TABLE_*.tex; do
    [ -f "$tbl" ] || continue
    bn=$(basename "$tbl")
    # Check if any label from this table file appears in sections
    for lbl in $(grep -oh '\\label{[^}]*}' "$tbl" 2>/dev/null); do
        grep -rq "$lbl" paper/sections/*.tex paper/main.tex 2>/dev/null || { echo "UNEMBEDDED TABLE: $lbl (from $bn)"; UNEMBED=$((UNEMBED+1)); }
    done
done
# Check latex_includes.tex labels
if [ -f figures/latex_includes.tex ]; then
    for lbl in $(grep -oh '\\label{[^}]*}' figures/latex_includes.tex 2>/dev/null); do
        grep -rq "$lbl" paper/sections/*.tex paper/main.tex 2>/dev/null || { echo "UNEMBEDDED: $lbl (from latex_includes.tex)"; UNEMBED=$((UNEMBED+1)); }
    done
fi
echo "Total unembedded: $UNEMBED"
```

If UNEMBED > 0, you MUST fix ALL of them before compiling. For each unembedded item:
- **PDF figure**: copy the `\begin{figure}...\end{figure}` block from `figures/latex_includes.tex` into the target section
- **TABLE_*.tex**: copy the `\begin{table}...\end{table}` block from `figures/TABLE_*.tex` into the target section (use `\input{../figures/TABLE_xxx.tex}` or paste the tabular code directly)
- Add 1-2 sentences of lead-in text before and 3-5 sentences of analysis after each embedded item
- Re-run the count check above — repeat until UNEMBED = 0

**Do NOT compile with unembedded figures or tables — the PDF will have missing content.**

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
xelatex -interaction=nonstopmode main.tex
bibtex main
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
```

### Step 4: Error fix loop (MANDATORY — do NOT skip)

After each compilation, check `main.log` for CRITICAL errors. **You MUST fix ALL errors before declaring compilation complete.**

```bash
# Count critical errors
MATH_ERR=$(grep -c 'Bad math environment delimiter\|Missing \$ inserted\|begin{document} ended by' paper/main.log 2>/dev/null || echo 0)
LR_ERR=$(grep -c 'Not allowed in LR mode' paper/main.log 2>/dev/null || echo 0)
UNDEF_CS=$(grep -c 'Undefined control sequence' paper/main.log 2>/dev/null || echo 0)
TOTAL_ERR=$((MATH_ERR + LR_ERR))
echo "Math errors: $MATH_ERR, LR mode errors: $LR_ERR, Undefined CS: $UNDEF_CS"
if [ "$TOTAL_ERR" -gt 0 ]; then
    echo "CRITICAL: $TOTAL_ERR errors — MUST FIX before proceeding"
    # Show error locations
    grep -B2 'Bad math\|Missing \$ inserted\|begin{document} ended\|Not allowed in LR mode' paper/main.log | grep -E '^\./|^l\.' | head -20
fi
```

**Error fix rules (iterate up to 5 times, not 3):**

1. **Math environment errors** (`Bad math environment delimiter`, `Missing $ inserted`, `\begin{document} ended by \end{equation}`):
   - Read the error location from main.log (e.g., `./sections/3_model_theory.tex:42`)
   - Open the file and find the broken math: usually `\X(t)$` should be `$X(t)$`, or `\mu$` should be `$\mu$`
   - Common cause: a sed/cleanup script stripped the opening `$` but left the closing `$`
   - Fix: ensure every math expression has matching `$...$` or `\[...\]` delimiters
   - **Do NOT use broad sed patterns to fix math** — read each error location and fix individually

2. **LR mode errors** (`Not allowed in LR mode`):
   - Usually caused by `\begin{figure}` or `\begin{table}` inside a paragraph without proper separation
   - Fix: add `\par` or blank line before the float environment

3. **Undefined control sequence**:
   - Missing package → add `\usepackage{xxx}` to main.tex preamble
   - Typo in command → fix the command name

4. **BibTeX failures**:
   - If BibTeX fails because of earlier LaTeX errors, fix the LaTeX errors first, then recompile
   - Check that `\bibliography{references}` and `\bibliographystyle{plainnat}` exist in main.tex
   - Check that references.bib has no syntax errors (unmatched braces, missing commas)

**After each fix, recompile and recheck:**
```bash
cd paper/
xelatex -interaction=nonstopmode main.tex
bibtex main 2>&1 | tail -5
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
cd ..
# Recheck
MATH_ERR=$(grep -c 'Bad math environment delimiter\|Missing \$ inserted' paper/main.log 2>/dev/null || echo 0)
echo "Remaining math errors: $MATH_ERR"
```

**⛔ Do NOT proceed to Step 5 until MATH_ERR = 0 and LR_ERR = 0.** BibTeX will also fail if there are LaTeX errors upstream — fix LaTeX first.

When fixing errors in main.tex, only fix the specific error (e.g., add a missing package, fix a typo). Do not rewrite or restructure main.tex — the template's preamble, cover page, page margins, section numbering format, and header/footer settings must remain unchanged.

### Step 5: Post-compile checks

```bash
bash _utils/compile_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_check.sh paper/
```

The script checks: PDF existence/size, undefined references, overfull hbox, TOC, abstracts, bibliography entries, citation count, citation format (上标/顺序/合并), unused figures, figure stacking, TikZ diagram presence.

**⛔ MANDATORY: 引用格式问题必须修复（不可忽略）：**

compile_check.sh 会检查 3 类引用格式问题，任何一类 FAIL/WARN 都必须修复：

1. **上标格式 FAIL** → 如果 bibliographystyle 是 `plain/plainnat/unsrt` 但 `\cite{}` 没有上标
   - 修复方法A：改 bibliographystyle 为 `gbt7714-numerical` 或 `plainnat` + `\usepackage[numbers,square,super]{natbib}`
   - 修复方法B：把正文里所有 `\cite{x}` 改为 `\upcite{x}` 或 `\textsuperscript{\cite{x}}`

2. **多引用顺序 WARN** → `\cite{c,a,b}` 但全文 a 先出现
   - 修复方法：改成 `\cite{a,b,c}`（按全文首次出现顺序）
   - 用以下 bash 找出所有需修复的位置：
     ```bash
     grep -rnP '\\(up)?cite\{[^}]+\}' paper/sections/*.tex paper/main.tex
     ```

3. **连续引用未合并 WARN** → `\cite{a}\cite{b}` 或 `\cite{a} \cite{b}`
   - 修复方法：合并为 `\cite{a,b}`
   - 批量修复：
     ```bash
     # 找出所有需合并的位置
     grep -rnoP '\\(up)?cite\{[^}]+\}\s*\\(up)?cite\{[^}]+\}' paper/sections/*.tex paper/main.tex
     ```

**⛔ 修复后必须重新编译验证：** `xelatex → bibtex → xelatex → xelatex`，然后重新运行 compile_check.sh 确认无 FAIL。

Additionally check:
```bash
# List of figures / list of tables (stats competition requirement)
[ -s paper/main.lof ] && echo "✅ 插图清单已生成" || echo "⚠ 插图清单为空"
[ -s paper/main.lot ] && echo "✅ 表格清单已生成" || echo "⚠ 表格清单为空"
```

**Template format verification (stats competition)**:
```bash
echo "=== 模板格式验证 ==="
if grep -q 'stats\|统计建模' paper/main.tex 2>/dev/null || [ "$COMPETITION" = "stats" ]; then
    # Check page margins (should be 2.54cm top/bottom, 3.17cm left/right)
    grep -q '2.54cm' paper/main.tex && echo "✅ 页边距正确" || echo "⚠ 页边距可能不对（应为上下2.54cm，左右3.17cm）"
    # Check Chinese section numbering
    grep -q 'chinese{section}' paper/main.tex && echo "✅ 中文章节编号" || echo "⚠ 缺少中文章节编号（一、二、三...）"
    # Check cover page
    grep -q '参赛学校\|参赛作品\|作品编号' paper/main.tex && echo "✅ 封面存在" || echo "⚠ 缺少封面"
    # Check abstract format (should be \section*{摘要}, not \begin{abstract})
    grep -q 'section\*.*摘要' paper/main.tex && echo "✅ 摘要格式正确" || echo "⚠ 摘要格式可能不对"
    # Check natbib (stats uses natbib, not gbt7714)
    grep -q 'natbib' paper/main.tex && echo "✅ natbib 引用格式" || echo "⚠ 缺少 natbib（统计建模应用 natbib）"
    # Check no header line
    grep -q 'headrulewidth.*0pt' paper/main.tex && echo "✅ 无页眉线" || echo "⚠ 可能有页眉线"
    # Check listoffigures / listoftables
    grep -q 'listoffigures' paper/main.tex && echo "✅ 插图清单命令" || echo "⚠ 缺少 \\listoffigures"
    grep -q 'listoftables' paper/main.tex && echo "✅ 表格清单命令" || echo "⚠ 缺少 \\listoftables"
fi
```
If any format checks fail, Claude should fix main.tex to match the template format before recompiling.

### Step 6: Competition compliance

Check items:
1. **Page count**: body = chapter 1 through conclusion, excluding 摘要/目录/参考文献/附录. Must be ≥ MAX_PAGES (**MAX_PAGES 是页数下限/目标，不是天花板**；页数可以超，不能少。竞赛若有硬性页数上限会另行注明，没注明就不要主动压页)
2. **Anonymous**: no team info (队号, 队员, 指导老师)
3. **Abstract exists** (数模竞赛: at least Chinese; 统计建模: both Chinese and English)
4. **TOC exists** (required by MathorCup etc.)
5. **Code appendix exists**
6. **No undefined references/citations**

<page_diagnosis>
#### Page count diagnosis (when insufficient)

If body pages < 80% of MAX_PAGES:
```bash
echo "=== 页数不足诊断 ==="
echo "目标: ≥ MAX_PAGES 页"
echo ""
echo "=== 各章节字符数（找出最薄的章节）==="
for f in paper/sections/*.tex; do
    chars=$(wc -c < "$f")
    echo "  $(basename $f): $chars 字符 (~$(echo "scale=1; $chars/900" | bc) 页)"
done
echo ""
echo "=== 建议扩充的章节（字符数最少的 3 个）==="
for f in $(ls -S paper/sections/*.tex | tail -3); do
    chars=$(wc -c < "$f")
    echo "  ⚠ $(basename $f): 仅 $chars 字符"
done
```

Mark as CRITICAL with specific recommendations:
- Which chapters are thinnest
- What content to add (more derivation? more result analysis? more literature discussion?)
- Estimated chars needed to reach target

If pages < 80% of MAX_PAGES, attempt to expand the thinnest 1-2 chapters:
- Read MODELING_REPORT.md and RESULTS.md for detailed content
- Add unexpanded derivations, result analysis, parameter discussions
- Recompile after expansion
</page_diagnosis>

<page_overflow>
#### ⛔⛔ 页数超限时的铁律（本次要根治的"图小"根因）

**背景**：曾出现编译期把 `MAX_PAGES` 误当天花板，为凑页数用「压缩图宽 + 注入全局 `\small`」把图压到 `0.46~0.48\textwidth`、正文字号整体缩小 —— 结果图小到看不清、版面敷衍。这是**严重错误**，本段是硬约束。

**⚠ 再次强调：`MAX_PAGES` 是页数下限/目标，不是天花板。** 除非竞赛简章白纸黑字写了硬性页数上限（会在 Additional Parameters 里另行注明），否则**页数超了完全没问题，绝不能主动压页**。**严禁自己臆想一个「≤30 页」之类的上限再去压图**——国赛（CUMCM）等多数竞赛并无硬性页数上限。

**图的尺寸由写作规则 + `compile_utils.sh` 兜底唯一决定：单图恒 `width=0.85\textwidth`（并排双栏才 `0.48`），高度兜底为 `height=0.9\textheight`（防单图独占整页）。编译期绝不许因为页数去改图宽或压小图高。**

**⛔ 特别警告——压小 `height` 是最隐蔽的凑页手段：** 给图加 `height=0.20\textheight` 这类小限高，在 `keepaspectratio` 下会先于 width 生效，把近方图/竖图卡成一小块（图又小又挤成一堆）。这和压图宽同样恶劣，同样禁止。`compile_utils.sh` 会自动剥离 `<0.5\textheight` 的限高并补回 `0.9\textheight`，编译期不得反向再压。

超页（且竞赛确有硬性上限）时，**只能**按下列优先级瘦身，**从上往下试，图和正文字号永远不动**：

1. 精简附录代码（节选核心片段、删冗余注释），附录不计正文页数但占篇幅；
2. 合并/删除稀薄的重复过渡段、把 enumerate 冗述改紧凑叙述；
3. 收紧浮动间距参数（`\setlength{\intextsep}` 等），不动图本身尺寸；
4. 删除非必要的重复图/表（一张图重复出现多次时）。

**⛔ 绝对禁止的凑页手段（出现即判不合格，必须回退）：**
- ❌ 把 `\includegraphics` 的 width 从 `0.85` 改小（如 `0.6/0.5/0.48/0.46\textwidth`）来省空间；
- ❌ 给 `\includegraphics` 加 `height=0.NN\textheight` 小限高（如 `0.20/0.22/0.3\textheight`）压小图来省空间；
- ❌ 在 `\begin{document}` 后注入全局 `\small` / `\footnotesize` 等正文降字号；
- ❌ 给正文（非表格）套任何全局缩字号命令。

**自检（Step 7 质量门禁前必跑）：**
```bash
echo "=== 图宽合规自检（禁凑页压图）==="
# 只看 includegraphics 的 width 系数；<0.80 视为被凑页压小（真正并排双栏请写 0.48 并用 subfigure/minipage，本检测会提示、人工确认即可）
BAD_W=$(grep -rhoE 'includegraphics\[[^]]*width=0\.[0-9]+' paper/sections/*.tex paper/main.tex 2>/dev/null | grep -oE 'width=0\.[0-9]+' | grep -vE 'width=0\.(8[0-9]|9[0-9])' | wc -l)
[ "$BAD_W" -eq 0 ] && echo "OK 无过小图宽" || echo "FAIL 有 $BAD_W 处图宽<0.80（疑似凑页压图，除真正并排双栏外必须改回 0.85）"
echo "=== 图高合规自检（禁压小图高凑页）==="
# <0.5\textheight 的限高视为凑页压图；compile_utils.sh 本应剥离，若仍残留说明预处理没跑或被反向压回
BAD_H=$(grep -rhoE 'includegraphics\[[^]]*height=0?\.[0-9]+' paper/sections/*.tex paper/main.tex 2>/dev/null | grep -oE 'height=0?\.[0-9]+' | grep -vE 'height=0?\.([5-9][0-9]*)' | wc -l)
[ "$BAD_H" -eq 0 ] && echo "OK 无过小限高" || echo "FAIL 有 $BAD_H 处 height<0.5\\textheight（凑页压图，须删该限高让 compile_utils.sh 补回 0.9）"
echo "=== 全局 small 自检（禁正文降字号）==="
# \begin{document} 到 \maketitle 之间若单独出现 \small/\footnotesize/\scriptsize，即全局降字号
AFTER_DOC=$(awk '/begin\{document\}/,/maketitle/' paper/main.tex 2>/dev/null | grep -cE '^[[:space:]]*[\](small|footnotesize|scriptsize)([[:space:]]|$)')
[ "$AFTER_DOC" -eq 0 ] && echo "OK document 后无全局降字号" || echo "FAIL document 后有全局 small/footnotesize（凑页降字号，必须删）"
```
三项都必须 OK；任一 FAIL 都要先修回（图宽改回 0.85、删过小限高、删全局 small），再重编译。
</page_overflow>

### Step 7: ⛔ FINAL QUALITY GATE (must ALL pass before finishing)

Run all checks and verify every item passes. **Do NOT output the report until all CRITICAL items are resolved.**

```bash
echo "=========================================="
echo "  FINAL QUALITY GATE"
echo "=========================================="
GATE_FAIL=0

# ⛔⛔ 两阶段执行总则（省重编，必读）：本门 22 项分两类，改完的重编需求完全不同——
#   【源码类】(19项)：只扫 .tex/.json/.md 文本(grep/awk/python)，与已编译 PDF 无关。
#      改完直接 grep 就能重判，【绝不需要重编】。含：#4图嵌入 #8模板完整 #9图对账 #10TikZ
#      #12占位符 #17摘要 #19符号longtable #21babel #22数值一致 #22.4声称↔代码 #22.5方法凭证
#      #22.5太完美 #22.6合理性 #22.8长表格 #23AI列表 #24meta #25过度声称 + #18的writing_check
#      (图注超长/引用格式/figure stacking)。
#   【产物类】(少数)：读 main.log/main.toc/PDF，改完【必须重编】才能重判。含：#16TOC、
#      #5页数、#18的compile_check内部(overfull hbox/vbox、未定义引用)。
#   ⛔ 正确修复顺序见本门末尾指令：先把所有【源码类】❌ 批量改完(期间禁止重编)→ 统一重编
#      一次 → 再判【产物类】。禁止每修一个源码类问题就重编 57 页(那是"卡很久"的根因)。

# ⛔ 已删除原 #1(PDF存在/大小)、#2(LaTeX错误)、#3(参考文献非空)手工检查：
#    这三项 compile_check.sh 已分别在其 #1/#2.5/#6 覆盖，且第18项退出码现已计入
#    GATE_FAIL（见上）。此处不再手工重查，避免同一检查跑两遍、AI 逐条空转。

# 4. No unembedded figures
UNEMBED=0
for pdf in figures/*.pdf; do
    [ -f "$pdf" ] || continue
    bn=$(basename "$pdf")
    grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null || UNEMBED=$((UNEMBED+1))
done
[ "$UNEMBED" -eq 0 ] && echo "✅ All figures embedded" || { echo "❌ $UNEMBED figures not embedded in paper"; GATE_FAIL=$((GATE_FAIL+1)); }

# 5. Page count
PAGE_EST=0
for f in paper/sections/*.tex; do [ -f "$f" ] || continue; c=$(wc -c < "$f"); PAGE_EST=$((PAGE_EST + c)); done
PAGE_EST=$((PAGE_EST / 900))
echo "  Page estimate: ~$PAGE_EST pages (target: ≥ MAX_PAGES)"

# ⛔ 已删除原 #6(overfull vbox)：compile_check.sh #3.5 已覆盖，第18项退出码现已计分。

# ⛔ 已删除原 #7(itemize 检查)：与下方 #23 完全重复，且 #23 更全（itemize+enumerate、
#    阈值 ≤3）。保留 #23，此处删除，避免同一检查在一个门里跑两遍。

# 8. Template integrity — compare preamble against original template
echo "--- Template integrity ---"
TMPL=""
for t in _templates/apmcm_zh/main.tex _templates/stats_main.tex _templates/cumcm_main.tex _templates/mcm_main.tex _templates/bachelor_main.tex _templates/master_main.tex _templates/journal_main.tex; do
    [ -f "$t" ] && TMPL="$t" && break
done
if [ -n "$TMPL" ] && [ -f paper/main.tex ]; then
    # Extract preamble (before \begin{document}) from both files
    TMPL_PRE=$(sed -n '1,/\\begin{document}/p' "$TMPL" | grep '\\usepackage\|\\documentclass\|\\ctexset\|\\pagestyle\|\\renewcommand.*headrulewidth\|\\listoftables\|\\listoffigures\|\\cline\|\\bibliography' | sort)
    MAIN_PRE=$(sed -n '1,/\\begin{document}/p' paper/main.tex | grep '\\usepackage\|\\documentclass\|\\ctexset\|\\pagestyle\|\\renewcommand.*headrulewidth\|\\listoftables\|\\listoffigures\|\\cline\|\\bibliography' | sort)
    MISSING=$(comm -23 <(echo "$TMPL_PRE") <(echo "$MAIN_PRE") 2>/dev/null | head -5)
    if [ -z "$MISSING" ]; then
        echo "✅ Template preamble intact"
    else
        echo "❌ Template preamble was modified — these lines from template are missing in main.tex:"
        echo "$MISSING" | sed 's/^/    /'
        GATE_FAIL=$((GATE_FAIL+1))
    fi
    # Check cover page structure (if template has one)
    if grep -q '参赛学校\|参赛作品' "$TMPL" 2>/dev/null; then
        grep -q '参赛学校\|参赛作品' paper/main.tex 2>/dev/null && echo "✅ Cover page present" || { echo "❌ Cover page missing/rewritten"; GATE_FAIL=$((GATE_FAIL+1)); }
        grep -q 'cline{2-2}' paper/main.tex 2>/dev/null && echo "✅ Cover underlines (cline)" || { echo "❌ Cover cline missing"; GATE_FAIL=$((GATE_FAIL+1)); }
    fi
    # Check bracket placeholders not remaining
    if grep -q '\[论文标题\]\|\[学校名称\]\|\[队员1\]\|\[指导老师\]\|\[竞赛年份\]\|\[届数\]\|\[中文摘要内容\]' paper/main.tex 2>/dev/null; then
        echo "❌ Unreplaced bracket placeholders in main.tex"; GATE_FAIL=$((GATE_FAIL+1))
    else
        echo "✅ All placeholders replaced"
    fi
    # Check hand-written figure/table list (anti-pattern)
    if grep -P '^(表|图)\d+\.' paper/main.tex 2>/dev/null | head -1 | grep -q '.'; then
        echo "❌ Hand-written figure/table list (use \\listoftables/\\listoffigures)"; GATE_FAIL=$((GATE_FAIL+1))
    fi
else
    echo "  (no template found for comparison, skipping)"
fi

# 9. Figure plan reconciliation (check planning docs)
echo "--- Figure plan check ---"
PLAN_FIGS=0; ACTUAL_FIGS=$(ls figures/*.pdf 2>/dev/null | wc -l)
for plan in TOPIC_PLAN.md PAPER_PLAN.md PROBLEM_ANALYSIS.md; do
    [ -f "$plan" ] || continue
    pf=$(grep -ci 'fig_\|图.*：\|figure.*:' "$plan" 2>/dev/null || echo 0)
    [ "$pf" -gt "$PLAN_FIGS" ] && PLAN_FIGS=$pf
done
if [ "$PLAN_FIGS" -gt 0 ]; then
    echo "  Planned: ~$PLAN_FIGS figures, Actual: $ACTUAL_FIGS PDFs"
    [ "$ACTUAL_FIGS" -ge "$PLAN_FIGS" ] && echo "✅ Figure count meets plan" || { echo "❌ Fewer figures than planned ($ACTUAL_FIGS < $PLAN_FIGS)"; GATE_FAIL=$((GATE_FAIL+1)); }
else
    echo "  No figure plan found, actual: $ACTUAL_FIGS PDFs"
fi

# 10. TikZ 几何/算法/架构图
# TikZ 由 paper-figure-drawio 编译成 figures/tikz_diagrams.pdf, 通过 \includegraphics 嵌入
# (不是 sections 里的裸 tikzpicture 代码)。两种形态都算已嵌入。
TIKZ_IN_PAPER=$(grep -rl 'tikzpicture\|tikz_diagrams\|tikz_' paper/sections/*.tex paper/main.tex 2>/dev/null | wc -l)
# ⛔ 只在"实际生成了 tikz_*.pdf 产物"时才硬核对(避免规划提了但用 DrawIO 替代时误报失败)
TIKZ_PDF_TOTAL=0; TIKZ_PDF_MISSING=0
for tpdf in figures/tikz_diagrams.pdf figures/tikz_diagrams_*.pdf figures/tikz_*.pdf; do
    [ -f "$tpdf" ] || continue
    TIKZ_PDF_TOTAL=$((TIKZ_PDF_TOTAL+1))
    grep -rq "$(basename "$tpdf")" paper/sections/*.tex paper/main.tex 2>/dev/null || TIKZ_PDF_MISSING=$((TIKZ_PDF_MISSING+1))
done
if [ "$TIKZ_PDF_TOTAL" -gt 0 ]; then
    # 有真实 TikZ 产物 → 必须全部嵌入
    if [ "$TIKZ_PDF_MISSING" -gt 0 ]; then
        echo "❌ $TIKZ_PDF_MISSING 张 TikZ PDF 未嵌入任何章节"; GATE_FAIL=$((GATE_FAIL+1))
    else
        echo "✅ TikZ diagrams embedded ($TIKZ_PDF_TOTAL)"
    fi
elif grep -qi 'tikz\|架构\|路线图\|几何示意\|算法流程' PAPER_PLAN.md PROBLEM_ANALYSIS.md 2>/dev/null; then
    # 规划提到 TikZ 但没生成 tikz_*.pdf(可能已用 DrawIO 替代) → 仅提醒, 不判失败
    [ "$TIKZ_IN_PAPER" -gt 0 ] && echo "✅ TikZ embedded" || echo "  ⚠ 规划提到 TikZ 但未发现 tikz_*.pdf(可能已用 DrawIO 替代, 不阻塞)"
else
    [ "$TIKZ_IN_PAPER" -gt 0 ] && echo "✅ TikZ diagrams embedded ($TIKZ_IN_PAPER)" || echo "  (no TikZ planned)"
fi

# ⛔ 已删除原 #11(正文引用数)：compile_check.sh #7 已查引用数，第18项退出码现已计分。

# 12. No placeholders remaining
PLACEHOLDERS=$(grep -rl 'PLACEHOLDER\|待补充\|TODO\|\[论文标题\]\|\[中文摘要内容\]' paper/sections/*.tex paper/main.tex 2>/dev/null | wc -l)
[ "$PLACEHOLDERS" -eq 0 ] && echo "✅ No placeholders" || { echo "❌ $PLACEHOLDERS files have placeholders"; GATE_FAIL=$((GATE_FAIL+1)); }

# ⛔ 已删除原 #13(未定义引用)、#14(overfull hbox)、#15(图堆叠)：
#    compile_check.sh 分别在其 #2/#3/#9 覆盖（#9 注释明写与 writing_check 同一检查，
#    原本查了三遍），第18项退出码现已计分。此处不再手工重查。

# 16. TOC 【产物类】——⛔ 唯一在本门主体内会重编的项，但仅当 main.toc 真空时才触发兜底重编。
#     正常情况 Step 3/4 已编够 3-4 遍、TOC 早已生成，此分支不进、不重编。不要误以为每轮都要走这里。
if grep -q 'tableofcontents' paper/main.tex 2>/dev/null; then
    [ -s paper/main.toc ] && echo "✅ TOC generated" || {
        echo "❌ TOC empty — running extra compile pass..."
        cd paper/
        xelatex -interaction=nonstopmode main.tex > /dev/null 2>&1
        xelatex -interaction=nonstopmode main.tex > /dev/null 2>&1
        cd ..
        [ -s paper/main.toc ] && echo "✅ TOC generated after extra compile" || { echo "❌ TOC still empty"; GATE_FAIL=$((GATE_FAIL+1)); }
    }
fi

# 17. Abstracts (Chinese papers)
if grep -q 'ctex' paper/main.tex 2>/dev/null; then
    grep -rq '摘.*要' paper/sections/*.tex paper/main.tex 2>/dev/null && echo "✅ Chinese abstract" || { echo "❌ No Chinese abstract"; GATE_FAIL=$((GATE_FAIL+1)); }
    grep -rq 'Abstract' paper/sections/*.tex paper/main.tex 2>/dev/null && echo "✅ English abstract" || { echo "❌ No English abstract"; GATE_FAIL=$((GATE_FAIL+1)); }
fi

# 18. Run compile_check.sh + writing_check.sh for full details
echo ""
echo "--- Full check scripts ---"
# ⛔ 必须分别捕获两个脚本的退出码：过去 `WC_EXIT=$?` 只接到 writing_check 的，
#    compile_check 的退出码被覆盖丢弃 → 它 506 行的检查白跑、FAIL 不计分。
#    现在两者都计入 GATE_FAIL，本项就成了「引用格式/未定义引用/hbox/vbox/未用图/
#    图堆叠/模板包冲突…」等一大批检查的权威裁判，下面手工项里与之重叠的已删除。
bash _utils/compile_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_check.sh paper/ 2>/dev/null
CC_EXIT=$?
bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/ 2>/dev/null
WC_EXIT=$?
[ "$CC_EXIT" -eq 0 ] && echo "✅ compile_check passed" || { echo "❌ compile_check failed (exit=$CC_EXIT) — 看上方明细逐条修"; GATE_FAIL=$((GATE_FAIL+1)); }
[ "$WC_EXIT" -eq 0 ] && echo "✅ writing_check passed" || { echo "❌ writing_check failed (exit=$WC_EXIT) — 看上方明细逐条修"; GATE_FAIL=$((GATE_FAIL+1)); }

# 19. 符号说明 longtable 检查
echo "--- Symbol table format ---"
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    if grep -q '\\section{符号说明}\|\\section.*符号' "$f" 2>/dev/null; then
        if grep -q '\\begin{longtable}' "$f" 2>/dev/null; then
            echo "✅ 符号说明使用 longtable"
        elif grep -q '\\begin{table}' "$f" 2>/dev/null; then
            echo "❌ 符号说明仍用 table（应转 longtable 防分页）"; GATE_FAIL=$((GATE_FAIL+1))
        fi
    fi
done

# ⛔ 已删除原 #20(长表格 >15 行)：与下方 #22.8(>12 行)阈值矛盾、检查重复。
#    保留 #22.8（阈值更严 >12、Python 精确数行、排除附录），此处删除，避免一个门里
#    两套打架的长表格标准。

# 21. babel[english] 冲突
echo "--- babel check ---"
if grep -q 'ctex\|cumcmthesis\|gmcmthesis' paper/main.tex 2>/dev/null; then
    grep -q 'babel.*english' paper/main.tex 2>/dev/null && { echo "❌ 中文论文有 babel[english]"; GATE_FAIL=$((GATE_FAIL+1)); } || echo "✅ 无 babel 冲突"
fi

# 22. 数值一致性（JSON vs 论文）
echo "--- Numerical consistency ---"
if [ -f figures/all_results.json ]; then
    python3 -c "
import json, re, os
with open('figures/all_results.json','r',encoding='utf-8') as f: results=json.load(f)
def extract(obj,p=''):
    n={}
    if isinstance(obj,dict):
        for k,v in obj.items(): n.update(extract(v,f'{p}.{k}'))
    elif isinstance(obj,(int,float)) and not isinstance(obj,bool):
        if 0.001<abs(obj)<1e10: n[p]=obj
    return n
jn=extract(results); pn=set()
for tf in sorted(os.listdir('paper/sections')):
    if not tf.endswith('.tex'): continue
    with open(f'paper/sections/{tf}','r',encoding='utf-8',errors='ignore') as f: t=f.read()
    for m in re.finditer(r'(?<![a-zA-Z])(\d+\.?\d+)(?![a-zA-Z_{}])',t):
        try: pn.add(float(m.group(1)))
        except: pass
miss=sum(1 for k,v in jn.items() if not any(abs(p-v)<abs(v)*0.01+0.001 for p in pn) and any(w in k.lower() for w in ['rmse','r2','accuracy','f1','objective','optimal','best']))
print(f'❌ {miss} key values missing in paper' if miss else '✅ Key values consistent')
import sys; sys.exit(1 if miss>3 else 0)
" 2>/dev/null
    [ $? -ne 0 ] && GATE_FAIL=$((GATE_FAIL+1))
fi

# 22.4 声称↔代码 确定性静态扫描（⛔ 两个模式都跑，零额度；数值一致 ≠ 结论成立）
# 编译阶段 paper/sections 已存在，这里再跑一次能把"正文声称"也纳入扫描，比 comp-code 阶段更全。
echo "--- 声称↔代码 静态扫描（第 3 道闸）---"
CC_SCRIPT=""
for f in _utils/claim_code_check.py skills/shared-scripts/claim_code_check.py; do
    [ -f "$f" ] && { CC_SCRIPT="$f"; break; }
done
if [ -n "$CC_SCRIPT" ] && [ -d code ]; then
    python "$CC_SCRIPT" --modeling MODELING_REPORT.md --codedir code
    CC=$?
    if [ "$CC" -eq 1 ]; then
        echo "❌ 静态扫描发现'声称的方法代码没实现'（整数规划实为连续 / 仿真实为加噪声等）— 回 comp-code 修"
        GATE_FAIL=$((GATE_FAIL+1))
    fi
    # CC=2（缺文件）不阻断
else
    echo "ℹ 无 claim_code_check.py 或无 code/，跳过静态扫描"
fi

# 22.5 方法实现对账凭证核对（严格模式 comp-code 会写 METHOD_CHECK 凭证）
echo "--- Method-implementation credential（凭证核对）---"
if [ -f RESULTS.md ]; then
    MC=$(grep -oE 'METHOD_CHECK[^>]*' RESULTS.md | tail -1)
    if [ -z "$MC" ]; then
        echo "⚠ RESULTS.md 无 METHOD_CHECK 凭证（应回 comp-code 补方法实现对账）"
    elif echo "$MC" | grep -q 'skipped_anchor=1'; then
        echo "ℹ 锚定式对账快速模式跳过；静态扫描已在上面独立跑过"
    else
        NC=$(echo "$MC" | grep -oE 'n_claims=[0-9]+' | grep -oE '[0-9]+'); NI=$(echo "$MC" | grep -oE 'n_implemented=[0-9]+' | grep -oE '[0-9]+')
        if [ -n "$NC" ] && [ "$NC" = "$NI" ]; then echo "✅ 方法声称全部有代码实现（$NI/$NC）"
        elif [ -n "$NC" ]; then echo "❌ 方法声称未全实现（$NI/$NC）— 回 comp-code 补实现或改正文声称"; GATE_FAIL=$((GATE_FAIL+1)); fi
    fi
fi

# 22.5 "太完美"结果检测（AI 编造或过拟合特征）
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
        suspicious.append(f'{name}={val:.4f} 过于完美（>0.999）')
    if any(w in key for w in ['rmse','mae','mse','loss']) and val == 0:
        suspicious.append(f'{name}=0 完美误差')
    if ('p_value' in key or 'pvalue' in key) and val == 0:
        suspicious.append(f'{name}=0 完美显著')
    if any(w in key for w in ['improvement','speedup','gain','提升']) and val > 10:
        suspicious.append(f'{name}={val} 提升过大（{val*100:.0f}%）')
def walk(obj, path=''):
    if isinstance(obj,dict):
        for k,v in obj.items(): walk(v, f'{path}.{k}')
    elif isinstance(obj,list):
        for i,v in enumerate(obj): walk(v, f'{path}[{i}]')
    else: check(path, obj)
walk(data)
if suspicious:
    print(f'🚩 {len(suspicious)} 处可疑的完美结果（可能过拟合或数值编造）:')
    for s in suspicious[:5]: print(f'    {s}')
    print('  需在论文中说明合理性，或回到 comp-code 检查数据泄漏')
else:
    print('✅ 数值合理性通过')
" 2>/dev/null
fi

# 22.6 合理性审查章节是否存在（必须）
echo "--- 合理性审查章节检查 ---"
if [ -f RESULTS.md ]; then
    if grep -q '合理性审查\|数值合理\|背景对照\|sanity.*check' RESULTS.md 2>/dev/null; then
        echo "✅ RESULTS.md 包含合理性审查章节"
    else
        echo "❌ RESULTS.md 缺少合理性审查章节 — 回到 comp-code Step 1.7 补充"
        GATE_FAIL=$((GATE_FAIL+1))
    fi
fi

# 22.7 数据源时间戳一致性（代码 vs 图表 vs 论文）
echo "--- 数据源时间戳一致性 ---"
if [ -f figures/all_results.json ]; then
    JSON_TIME=$(stat -c %Y figures/all_results.json 2>/dev/null || stat -f %m figures/all_results.json 2>/dev/null || echo 0)
    # 检查是否有 PDF 图表比 JSON 旧（说明代码重跑了但图没更新）
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
        echo "  → 建议重跑 paper-figure 步骤更新图表"
        GATE_FAIL=$((GATE_FAIL+1))
    else
        echo "✅ 数据源时间戳一致"
    fi
fi

# 22.8 正文长表格检测（>12 行的表格不应在正文中完整展开）
echo "--- 正文长表格检测 ---"
LONG_TABLES=0
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    # 跳过附录文件
    echo "$(basename $f)" | grep -qi 'appendix\|附录\|A_code' && continue
    # 统计每个 tabular/longtable 环境内的数据行数（\\ 的数量）
    python3 -c "
import re
with open('$f', 'r', encoding='utf-8', errors='ignore') as fh:
    content = fh.read()
# 找所有 tabular/longtable 环境
for env in ['tabular', 'longtable', 'tabular*']:
    pattern = r'\\\\begin\{' + env + r'[*]?\}.*?\\\\end\{' + env + r'[*]?\}'
    for match in re.finditer(pattern, content, re.DOTALL):
        table_text = match.group()
        row_count = table_text.count('\\\\\\\\') - table_text.count('\\\\hline') // 2
        if row_count > 12:
            print(f'$(basename $f): {env} 有 {row_count} 行（>12）')
" 2>/dev/null | while read line; do
        echo "  ❌ $line — 正文表格超过 12 行，应截断（前3+后3+省略），完整版放附录"
        LONG_TABLES=$((LONG_TABLES+1))
    done
done
[ "$LONG_TABLES" -eq 0 ] && echo "✅ 正文无超长表格" || GATE_FAIL=$((GATE_FAIL+1))

# 22.9 图注超长检测已集中到 writing_check.sh（见第 18 项，其 EXIT_CODE→WC_EXIT→GATE_FAIL），此处不再重复。

# 23. AI 写作痕迹（列表环境）
echo "--- AI writing patterns ---"
AI_LISTS=0
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    echo "$(basename $f)" | grep -qi 'appendix\|A_code' && continue
    c=$(grep -c '\\begin{itemize}\|\\begin{enumerate}' "$f" 2>/dev/null || echo 0)
    AI_LISTS=$((AI_LISTS+c))
done
[ "$AI_LISTS" -le 3 ] && echo "✅ AI patterns: $AI_LISTS lists" || { echo "❌ $AI_LISTS lists in body — convert to prose"; GATE_FAIL=$((GATE_FAIL+1)); }

# 24. 元叙述泄露
echo "--- Meta content leak ---"
META=0
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    l=$(grep -ci 'RESULTS\.md\|CLAUDE\.md\|MODELING_REPORT\|PROBLEM_ANALYSIS\|latex_includes' "$f" 2>/dev/null || echo 0)
    META=$((META+l))
done
[ "$META" -eq 0 ] && echo "✅ No meta leaks" || { echo "❌ $META meta content leaks"; GATE_FAIL=$((GATE_FAIL+1)); }

# 25. 过度声称
echo "--- Overclaiming ---"
OC=0
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    for w in "首次提出" "首次发现" "完美" "最优的" "无可比拟" "前所未有" "开创性" "革命性"; do
        c=$(grep -c "$w" "$f" 2>/dev/null || echo 0); OC=$((OC+c))
    done
done
[ "$OC" -eq 0 ] && echo "✅ No overclaiming" || echo "⚠ $OC overclaiming instances"

echo ""
echo "=========================================="
if [ "$GATE_FAIL" -eq 0 ]; then
    echo "  ✅ ALL CRITICAL CHECKS PASSED — ready to submit"
else
    echo "  ❌ $GATE_FAIL CRITICAL FAILURES — MUST FIX before finishing"
    echo "  按下方「省重编修复顺序」修：先批量改完源码类，再统一重编一次。"
fi
echo "=========================================="
```

**⛔ If GATE_FAIL > 0, you MUST fix every ❌ before finishing. Repeat until GATE_FAIL = 0. 但修复顺序按下面来，别每修一项就重编：**

**⛔⛔ 省重编修复顺序（治"编译卡很久"的关键——大多数 ❌ 是源码类，改完不必重编）：**

1. **先批量修完所有【源码类】❌**（见本门开头总则的清单：图注超长 / 引用格式 / 占位符 / meta / AI列表 / 长表格 / 数值一致 / 模板完整 …）。这些只改 `paper/sections/*.tex` 或 `main.tex` 文本，**期间一次都不要重编**——它们和已编译 PDF 的 hbox/页数/TOC 无关，改完直接 grep 就能重判。
2. **所有源码类改完后 → 统一重编一次**：`cd paper/ && xelatex→bibtex→xelatex→xelatex`。
3. **重编后只重跑【产物类】检查**（#16 TOC / #5 页数 / #18 compile_check 的 hbox·vbox·未定义引用）。
4. **仅当【产物类】还有 ❌ 时**（通常是页数不足或 hbox），才针对性修 + 再重编一次。
5. **重复直到 GATE_FAIL=0**，但每一轮都遵循"源码类批量改→只重编一次"，**严禁每修一个源码类问题就重编 57 页**。

> 为什么这样能省时间：一篇 57 页论文 xelatex 单遍就要几十秒，×4 遍一轮就 1-2 分钟。过去把"图注改短""表格内联"这类纯文本修改也各自触发一轮重编，多轮累积就是十几分钟。按上面顺序，源码类问题无论多少个都只在末尾重编一次，重编轮数从"问题分几批就编几轮"压到 1-2 轮。

### Step 8: Output report

Competition name, status, PDF path, total pages, body pages, compliance pass/fail.

## Key Rules

- No latexmk — manual step-by-step compilation
- Do not delete .bbl file after compilation (bibliography data)
- Figure paths auto-corrected by compile_utils.sh: `figures/` → `../figures/`
- Body pages ≥ MAX_PAGES (can exceed, must not fall short)
- Anonymous: no team info in body
- Primary output: `paper/main.pdf`, temp files: `_tmp/`

⛔ **结束前必跑 PASS 阻断验证**：
```bash
PASS=true
[ -f paper/main.pdf ] && SZ=$(wc -c < paper/main.pdf) || SZ=0
if [ "$SZ" -ge 100000 ]; then
    echo "✅ paper/main.pdf ($SZ bytes)"
else
    echo "❌ paper/main.pdf 缺失或过小 ($SZ bytes) — 必须编译成功后再结束"
    PASS=false
fi
[ "$PASS" != true ] && echo "⛔ 验证未通过 — 必须修复后再结束本步骤"
```

