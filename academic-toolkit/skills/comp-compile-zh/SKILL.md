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

- **PAGE_CAP / PAGE_SCOPE / PAGE_CAP_STATUS** — 与写作步、打包步消费**同一份 bound 赛事快照**：`gate_page_cap`（本任务 operative 口径）+ `gate_page_scope`（`body`/`total` 两种计数口径，绝不折叠成一个数）+ `page_cap_status`（来源性质）。逐字转录自下发的 `contest_profile`；无默认、无下限；**不直读档案原始页数字段**、不自行猜生效值与计数范围。

- **CONTEST_ID** — 逐字转录自 `contest_profile.contest_id`（规范 `comp_*` 键；不从自由文本或文件名猜）。

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

MATH_ERR=$(grep -c 'Bad math environment delimiter\|Missing \$ inserted\|begin{document} ended by' paper/main.log 2>/dev/null)

LR_ERR=$(grep -c 'Not allowed in LR mode' paper/main.log 2>/dev/null)

UNDEF_CS=$(grep -c 'Undefined control sequence' paper/main.log 2>/dev/null)

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

MATH_ERR=$(grep -c 'Bad math environment delimiter\|Missing \$ inserted' paper/main.log 2>/dev/null)

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

if [ "$CONTEST_ID" = "comp_stats" ]; then

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

If any format checks fail, 执行 Agent should fix main.tex to match the template format before recompiling.

### Step 6: Competition compliance

Check items:

1. **Page count**: 上限与**计数口径**来自与写作步消费的同一份 bound 赛事快照——`gate_page_cap` + `gate_page_scope`（`body` = 章节 1 至结论、不含摘要/目录/参考文献/附录；`total` = 整本 PDF 计）。两种口径绝不折叠成一个数，本步不直读档案原始字段、不猜生效值。状态为 `official_verified` 或显式任务授权时**不得超过该上限**；`unverified` 口径不产生默认硬页限——如实上报数值、口径与性质；没有下发时如实报告缺口，不自行设限。**没有页数下限，不为凑页数扩写。**

2. **Anonymous**: no team info (队号, 队员, 指导老师)

3. **Abstract exists** (数模竞赛: at least Chinese; 统计建模: both Chinese and English)

4. **TOC exists** — 仅当消费的赛事快照 verified 要求目录时检查；MathorCup 的目录要求未核验（档案 historical_notes 存档未确认），核验前不作为硬检查项

5. **Code appendix exists**

6. **No undefined cross-references or citations**

<page_diagnosis>

#### Page count principles

**没有页数下限：页数少不是合规失败，不为凑页扩写。** 章节内容完整性由写作步骤自身的合同保证；编译步只对「超出赛事档案上限」负责瘦身（见 page_overflow），不对「未达某个目标页数」做任何扩写或充数。

</page_diagnosis>

<page_overflow>

#### ⛔⛔ 页数超限时的铁律（图小问题的根治约束）

**页数上限来自赛事档案**（`comp_rules.json` compliance 页数字段，由引擎下发），不是本步自造的目标。历史教训的实质是「为页数目标而压图变形」：无论是把上限当凑页目标反向压图，还是为塞进超限内容压图，都是同一类错误。本段是硬约束。

**图的尺寸由写作规则 + `compile_utils.sh` 兜底唯一决定：单图恒 `width=0.85\textwidth`（并排双栏才 `0.48`），高度兜底为 `height=0.9\textheight`（防单图独占整页）。编译期绝不许因为页数去改图宽或压小图高。**

**⛔ 特别警告——压小 `height` 是最隐蔽的压页手段：** 给图加 `height=0.20\textheight` 这类小限高，在 `keepaspectratio` 下会先于 width 生效，把近方图/竖图卡成一小块（图又小又挤成一堆）。这和压图宽同样恶劣，同样禁止。`compile_utils.sh` 会自动剥离 `<0.5\textheight` 的限高并补回 `0.9\textheight`，编译期不得反向再压。

页数超出赛事档案上限时，**只能**按下列优先级瘦身，**从上往下试，图和正文字号永远不动**：

1. 精简附录代码（节选核心片段、删冗余注释），附录不计正文页数但占篇幅；

2. 合并/删除稀薄的重复过渡段、把 enumerate 冗述改紧凑叙述；

3. 收紧浮动间距参数（`\setlength{\intextsep}` 等），不动图本身尺寸；

4. 删除非必要的重复图/表（一张图重复出现多次时）。

**⛔ 绝对禁止的凑页手段（出现即判不合格，必须回退）：**

- ❌ 把 `\includegraphics` 的 width 从 `0.85` 改小（如 `0.6/0.5/0.48/0.46\textwidth`）来省空间；

- ❌ 给 `\includegraphics` 加 `height=0.NN\textheight` 小限高（如 `0.20/0.22/0.3\textheight`）压小图来省空间；

- ❌ 在 `\begin{document}` 后注入全局 `\small` / `\footnotesize` 等正文降字号；

- ❌ 给正文（非表格）套任何全局缩字号命令。

**上游细化（modex-3 同源吸收，2026-09-22）——自适应图尺寸，反凑页双向成立**：上述 `0.85\textwidth` 是本仓统一口径的**默认档**，不是"合格证明"。真正的判据是**最终印刷可读性**：诊断实际裁切、缩后文字是否 <8pt、重叠与异常空白，必要时重排信息密度。同理**禁止反向操作**——不得为了"满足图宽规范"把所有图无脑放大到 `0.85\textwidth`；一张可读的紧凑小图与一张设计良好的多面板大图都合法，`0.48\textwidth`、绝对尺寸、有意控制的高度都**不构成缺陷证据**。字号与尺寸永远不由页数目标驱动（无论压缩还是撑大）。

**自检（Step 7 质量门禁前必跑）：**

```bash

echo "=== 图宽合规自检（禁凑页压图）==="

# 只看 includegraphics 的 width 系数；<0.80 视为被凑页压小（2026-11-16 与英文侧 comp-compile-en 统一为 0.80 口径，原 0.70 口径废弃，取严）。
# 合规域 0.80~0.98 内一律不误报：正则兼容一位/两位小数（fig_include_size.py 以 %g 写出 0.8/0.9 一位小数形态，其密度感知
# 推荐域 0.80~0.98；drawio 窄图 0.7 现落入待确认域，会提示人工确认）——0.8/0.9/0.85/0.98 等全部放行，仅抓 <0.80 的压图值
# （真正并排双栏请写 0.48 并用 subfigure/minipage，本检测会提示、人工确认即可）

BAD_W=$(grep -rhoE 'includegraphics\[[^]]*width=0\.[0-9]+' paper/sections/*.tex paper/main.tex 2>/dev/null | grep -oE 'width=0\.[0-9]+' | grep -vE 'width=0\.(8|9)[0-9]*' | wc -l)

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

旧内联 22 项 bash/Python 门禁已拆分承接（对齐英文侧 paper-compile 口径）：机器可判项由引擎 `paper_final_gate` 与共享检查脚本接管，正文不再内联大段脚本；本步保留「何时跑 + 判据 + 修复动作」。运行方式：

- **finish 自动挂载**：`session finish` 按检查器注册表 `engine/modex-core/checkers/registry.json` 的 `applies_to` 自动运行本步检查器。
- **竞赛中文模板现状**：若 `paper_final_gate` 的 `applies_to` 尚未覆盖当前竞赛模板（如 `comp_writing_zh`），finish 前必须手动单跑一次；退出码 0=pass、1=fail、3=unknown（unknown 是「未核验」，不是通过）：

```bash
cd academic-toolkit && python engine/quality_gates.py gate <工作区> --check paper_final_gate
```

- **六类一致性检查（数值一致性/太完美/时间戳/长表格/元叙述/过度声称）由共享脚本承接**（comp-compile-zh / paper-compile-zh 单一实现，双副本同 `shared-scripts/`）：

```bash
CHK=_utils/contest_consistency_check.py
[ -f "$CHK" ] || CHK=../_utils/contest_consistency_check.py
[ -f "$CHK" ] || CHK=skills/_utils/contest_consistency_check.py
[ -f "$CHK" ] || CHK=academic-toolkit/skills/_utils/contest_consistency_check.py
python "$CHK" --paper paper --figures figures     # 退出码 0=无硬失败 1=有硬失败 3=输入缺失(unavailable)
```

- **编译侧脚本闸仍由 Step 6 的 `compile_check.sh` / `writing_check.sh` 承接**（overfull hbox/vbox、未定义引用、TOC、图注超长、AI 列表、封面要素等）。

逐项覆盖映射（原 22 项内联项 → 现承接方）：

| 原内联项 | 现承接方 | 口径说明 |
|---|---|---|
| #4 图嵌入 | `paper_final_gate` + `figure_plan_reconciliation` | figures/*.pdf 未被正文引用判 ❌；「规划清单 ∪ figures/ 并集」对账由 figure 步骤检查器承接 |
| #5 页数 | `paper_final_gate` + 人工 | 页数上限按引擎竞赛配置判；正文页数不足回写稿步扩写，超限允许 |
| #8 模板完整 | `paper_final_gate` + `compile_check.sh` + 人工 | 引擎比对前言 4 类（usepackage/documentclass/pagestyle/bibliography）；赛事封面/cline/承诺书由 `compile_check.sh` 与人工确认 |
| #9 图规划对账 | `figure_plan_reconciliation` | FIGURE_MANIFEST 与 figures/ 实际产出对账 |
| #10 TikZ | `paper_final_gate` + `figure_plan_reconciliation` | tikz_*.pdf 须嵌入正文；计划 TikZ 改用 DrawIO 属合法替代 |
| #12 占位符 | `paper_final_gate` + 人工 | 引擎查 sections 的 `PLACEHOLDER`/`TODO` 字面；`[论文标题]` 等中文方括号占位符引擎不查，finish 前人工确认清零 |
| #16 TOC【产物类】 | `compile_check.sh`（Step 6） | main.toc 真空时按原兜底逻辑重编一次 |
| #17 摘要 | 人工判断 | 各赛事要求不一（仅中文/仅英文/双语），引擎与 `compile_check.sh` 均不做统一摘要检查；编译后人工核对 PDF 首页 |
| #18 compile_check/writing_check | `compile_check.sh` + `writing_check.sh`（Step 6） | 保留原双脚本闸，退出码非 0 计入失败；退出码 3=检查器不可用记 TOOL_GAP，不判通过也不判论文错 |
| #19 符号说明 longtable | `paper_final_gate` + 人工 | 符号表格式（longtable/三线）人工核对 |
| #21 babel[english] 冲突 | `paper_final_gate` + 人工 | 与中文文档的冲突处置人工确认 |
| #22 数值一致性 | `contest_consistency_check.py`（共享脚本） | all_results.json 关键指标 vs 正文 1% 容差对账，>3 项缺失判 ❌ |
| #22.4 声称↔代码 | `claim_code_check.py`（既有共享脚本） | 静态扫描第 3 道闸；编译阶段再跑一次把正文声称纳入扫描（CC=1 判 ❌，CC=2 缺文件不阻断） |
| #22.5 方法凭证 | 人工核对 RESULTS.md 的 METHOD_CHECK | 凭证缺失提示（⚠）；n_claims≠n_implemented 判 ❌，回 comp-code 补实现或改正文声称 |
| #22.5 太完美 | `contest_consistency_check.py`（advisory） | >0.999/零误差/完美显著/提升>10 倍只提示不阻断；需在论文说明合理性或回 comp-code 查数据泄漏 |
| #22.6 合理性章节 | `paper_final_gate` + `result_sanity_check` | RESULTS.md 缺合理性审查章节判 ❌ |
| #22.7 时间戳 | `contest_consistency_check.py` | PDF 图比 results JSON 旧 >60s 判 ❌（重跑 paper-figure 更新图表） |
| #22.8 长表格 | `contest_consistency_check.py` | 正文表格 >12 行判 ❌（截断前3+后3+省略，完整版放附录） |
| #22.9 图注超长 | `writing_check.sh`（Step 6） | 已集中到 writing_check，正文不重复 |
| #23 AI 列表 | `paper_final_gate` | sections 内 `\begin{itemize}`/`enumerate` 计数 >3 判 ❌（转成散文段落） |
| #24 元叙述泄露 | `contest_consistency_check.py` | 内部文件名（RESULTS.md/AGENTS.md/MODELING_REPORT/PROBLEM_ANALYSIS/latex_includes）出现在正文判 ❌ |
| #25 过度声称 | `contest_consistency_check.py`（advisory） | 绝对化措辞（首次提出/完美/最优的/前所未有/开创性/革命性等）只提示不阻断，建议温和化 |

人工判断项（引擎与脚本都不做统一判定）：图表版式与视觉美观、摘要语言合规（#17）、模板前言差异属等价改写还是篡改、符号表格式（#19）、babel 冲突处置（#21）、方法凭证缺省时的补账（#22.5）、可疑完美值结合研究背景确认是否真合理。

**⛔ 引擎/脚本判 fail/unknown 时按输出逐项修复后重跑，violations 全部清零前不得 finish。省重编修复顺序见下。

**⛔⛔ 省重编修复顺序（治"编译卡很久"的关键——大多数 ❌ 是源码类，改完不必重编）：**

1. **先批量修完所有【源码类】❌**（见上方覆盖映射表中的源码类各项：图注超长 / 引用格式 / 占位符 / meta / AI列表 / 长表格 / 数值一致 / 模板完整 …）。这些只改 `paper/sections/*.tex` 或 `main.tex` 文本，**期间一次都不要重编**——它们和已编译 PDF 的 hbox/页数/TOC 无关，改完直接 grep 就能重判。

2. **所有源码类改完后 → 统一重编一次**：`cd paper/ && xelatex→bibtex→xelatex→xelatex`。

3. **重编后只重跑【产物类】检查**（#16 TOC / #5 页数 / #18 compile_check 的 hbox·vbox·未定义引用）。

4. **仅当【产物类】还有 ❌ 时**（通常是页数不足或 hbox），才针对性修 + 再重编一次。

5. **重复直到全部检查通过（无 ❌）**，但每一轮都遵循"源码类批量改→只重编一次"，**严禁每修一个源码类问题就重编 57 页**。

> 为什么这样能省时间：一篇 57 页论文 xelatex 单遍就要几十秒，×4 遍一轮就 1-2 分钟。过去把"图注改短""表格内联"这类纯文本修改也各自触发一轮重编，多轮累积就是十几分钟。按上面顺序，源码类问题无论多少个都只在末尾重编一次，重编轮数从"问题分几批就编几轮"压到 1-2 轮。

**上游证据优先规约（modex-3 同源吸收，2026-09-22，与 `_utils/quality_gate_contract.md` 同一口径）**：

- 只修**具体失败项**，批量修完后编译一次、只对改动的最终快照复查。绝不为让步骤通过而压制真实失败。
- **工具失败/超时/缺依赖不是论文内容缺陷**。停下给出可恢复诊断；不得为此消耗模型调用去重写无关文本。检查器故障先修检查器。
- **提示性警告（advisory）也不是已证实的证据**。其来源与适用性在既有的语义复核中一并解决；无法解决的如实保留为局限，不升级成硬失败。
- 不要用对 `sections/` 全目录的大范围 `grep` 自行重实现检查器——只有 `main.tex` 实际包含的源与最终稿实际引用的图参与判定。
- 不得把 PDF 字节数、固定公式显示数、表格行数、列表数、计划图名的提及、缺失的字面算法关键词、或单条 caption 长度本身当作硬失败判据。`fig_size_consistency_check.py` 只比对草稿规划，陈旧规划不判成品错。
- 检查脚本区分两类退出：`GATE_FAIL`（内容失败，必修）与 `GATE_UNAVAILABLE`（检查不可用，如实报告、不判通过也不判论文错）。

### Step 8: Output report

Competition name, status, PDF path, total pages, body pages, compliance pass/fail.


## 执行与产出

使用当前执行会话完成本步工作；产物路径按当前步骤合同。程序采集真实操作、输入输出、版本与运行清单，模型只负责实质成果和领域质量。

建议额外记录：LaTeX 引擎版本、页数、编译警告数。

## Key Rules

- ⛔ **写稿/图表质量闸全家桶（按需选跑，双副本同 shared-scripts/）**：编译侧 `latex_typography_check.py`（排版精细检查）/`normalize_cjk_quotes.py`（中文引号规范）；图表侧 `tikz_structure_check.py <file>` + `tikz_palette_check.py`（TikZ 结构/配色）/`fig_include_size.py` + `fig_size_consistency_check.py`（插图尺寸与一致性）/`figure_pdf_quality_check.py` + `pdf_page_density_check.py` + `pdf_snapshot_report.py`（PDF 成品质量/页密度/快照）/`figure_text_budget.py` + `figure_narrative_check.py`（图内文字预算与叙事）/`fig_bucket_doc_sync_check.py`（图桶-文档同步）；写作侧 `abstract_emphasis_check.py`（摘要重点）/`symbol_layout_check.py` + `assumption_layout_check.py`（符号表/假设排版）/`writing_source_check.py` + `compile_source_check.py`（写稿/编译源一致性）/`paper_source_scope.py`（正文范围）。计算侧 `compute_checkpoint.py`/`run_compute.py`/`modeling_tex_policy.py`/`recipe_audit.py` 归 comp-code 侧按需。合同规范：`modeling_paper_contract.md`（建模-论文合同）/`abstract_writing_contract.md`（摘要合同）/`quality_gate_contract.md`（验证证据复用）/`cumcm_2026_format.md`（2026 国赛格式）/`tikz_style_families.md`（TikZ 风格族）。

- No latexmk — manual step-by-step compilation

- Do not delete .bbl file after compilation (bibliography data)

- Figure paths auto-corrected by compile_utils.sh: `figures/` → `../figures/`

- 正文页数不超过引擎下发的赛事档案页数上限（无下限，不为凑页扩写）

- Anonymous: no team info in body

- Primary output: `paper/main.pdf`, temp files: `_tmp/`

**⛔ 国赛提交包打包规则（强制）**：

1. **所有提交文件必须以中文命名**：
   - `论文.pdf`（正文 PDF）
   - `代码说明.txt`（程序说明，**仅使用 TXT 格式**）
   - `支撑材料.pdf`（含 AI工具使用详情.pdf 等）
   - `代码/`（代码文件夹，中文命名）

2. **程序说明仅使用 TXT 文件**（`代码说明.txt`），不使用 Markdown、Word 或其他格式。内容包括：
   - 代码功能说明
   - 运行环境要求
   - 核心算法简述
   - 输入输出说明

3. **压缩包命名**：`参赛编号+队号.zip`（如 `20260001_A01.zip`）

4. **禁止在提交包中包含**：
   - `.env` 文件
   - `.sqlite` 数据库文件
   - `__pycache__` 目录
   - 任何包含真实竞赛题面的文件（题面由组委会单独分发）


产出结构、存在性和最低完整性由 `finish` 按模板中的 `output_contract` 自动核验；修复返回的具体问题，不复制执行验证脚本。

## 退出判据（Verification）

本步完成前逐项自检（不达标即视为未完成）：

- [ ] 0 编译错误、0 未定义引用
- [ ] 图表公式编号连续且与正文引用一致
- [ ] 页数与页边距符合规则
- [ ] 编译日志已留档（可复现）

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "能出 PDF 就算编译通过" | 带警告的编译可能藏着断引用与错编号，需按日志逐项清。 |
| "引用警告无视即可" | 未定义引用即正文存在断链，评审一眼可见。 |
| "重新编译一下就好" | 无留档的编译不可复现；日志是产物的一部分。 |

> 本段与 `skills/_utils/anti_rationalization.md`（全局版）配套：本表是本步专属，
> 全局版覆盖跨步骤通用借口。新增借口时优先落到本表（更贴岗位），能泛化再上升。
