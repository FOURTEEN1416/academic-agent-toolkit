---
name: paper-compile-zh
description: "用 XeLaTeX 把中文 LaTeX 论文编译为 PDF。触发词：编译中文论文、compile Chinese paper、中文PDF。只负责编译既有 .tex，不做内容创作；要从零写正文改用 paper-write-zh。"
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
if grep -qi 'wuyi\|五一杯' AGENTS.md 2>/dev/null; then
    grep -q '承诺书' paper/main.tex || { echo "❌ 五一杯缺少承诺书页"; FAIL=$((FAIL+1)); }
    grep -q 'image2' paper/main.tex || { echo "❌ 五一杯缺少封面logo"; FAIL=$((FAIL+1)); }
fi
[ "$FAIL" -eq 0 ] && echo "✅ 模板完整性检查通过" || echo "⛔ $FAIL 项失败 — main.tex 可能被重写了，必须从模板恢复"
```

**⛔ 如果模板检查失败，必须从模板目录重新复制 main.tex 并只替换占位符，不要继续编译。**

### Step 3.6: 中文引号规范化（编译前，防直引号）

AI 写正文时常把中文引号打成 ASCII 直引号 `"词"`，在竞赛模板（`\setmainfont{Times New Roman}`）下会渲染成西文直立引号（两个一样的竖引号），而非中文全角弯引号“词”。编译前统一规范化（只转紧贴中文的直引号，自动跳过代码/数学/`\url`，幂等）：

```bash
NORMQ=""
for f in _utils/normalize_cjk_quotes.py skills/shared-scripts/normalize_cjk_quotes.py; do
  [ -f "$f" ] && { NORMQ="$f"; break; }
done
if [ -n "$NORMQ" ]; then
  python "$NORMQ" paper/sections/*.tex paper/main.tex 2>/dev/null || echo "引号规范化跳过（脚本不可用，不阻塞）"
else
  echo "未找到 normalize_cjk_quotes.py，跳过引号规范化（不阻塞编译）"
fi
```

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
bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/
```

`compile_check.sh` checks: PDF existence/size, undefined references, overfull hbox, TOC, bibliography command and entries, citation count in body, unused figures, figure stacking, TikZ diagram presence against plan, contest-specific front matter, over-long tables (abstract presence is intentionally not checked there — requirements vary by competition). `writing_check.sh` covers source/narrative/layout/style/AI-tell checks. Exit code 3 from either means the checker itself is unavailable — record TOOL_GAP, never read it as a content failure.

Run compile_utils.sh post-compile checks too (items 10-13: TOC, abstracts, bibliography config, unused figures).

### Step 7: Page count verification

Body pages = chapter 1 through conclusion, excluding cover/abstract/TOC/references/acknowledgments/appendix.

Body pages must be ≥ MAX_PAGES. If insufficient, return to paper-write-zh to expand content. Exceeding MAX_PAGES is allowed.

### Step 8: ⛔ Final gate — 引擎 `paper_final_gate` 承接

旧内联 FINAL QUALITY GATE（16 项 bash/Python 脚本）已由引擎检查器接管，正文不再内联脚本。运行方式：

- **finish 自动挂载**：`session finish` 按检查器注册表 `engine/modex-core/checkers/registry.json` 的 `applies_to` 自动运行本步检查器。英文模板（paper_writing 等）的 paper-compile 步骤已挂 `paper_final_gate`（delivery 档 blocking）。
- **中文模板现状**：`paper_final_gate` 的 `applies_to` 尚未列入 `paper_writing_zh` / `paper-compile-zh`，中文工作流在本步 finish 前必须手动单跑一次；退出码 0=pass、1=fail、3=unknown（unknown 是"未核验"，不是通过）：

```bash
cd academic-toolkit && python engine/quality_gates.py gate <工作区> --check paper_final_gate
```

逐项覆盖映射（原 16 项内联项 → 现承接方）：

| 原内联项 | 现承接方 | 口径说明 |
|---|---|---|
| 1. PDF 存在且体量达标 | `paper_final_gate` | PDF 缺失或 ≤50000B 判 ❌；另受本步 min_size 产物合同约束 |
| 2. 无 LaTeX 错误 | `paper_final_gate` + Step 5 人工 | 引擎查 math 错误（Bad math delimiter / Missing $ inserted）；**LR mode 错误引擎不查，仍在 Step 5 修复循环人工清零** |
| 3. Bibliography / Citations | `paper_final_gate` | main.bbl 无 `\bibitem` 或正文无 `\cite` 判 ❌ |
| 4. figures/*.pdf 全嵌入 | `paper_final_gate` + `figure_plan_reconciliation` | 引擎查 figures/*.pdf 是否被正文引用；「规划清单 ∪ figures/*.pdf 并集嵌入对账」在 figure 步骤由 `figure_plan_reconciliation` 承接 |
| 5/11. overfull vbox / hbox≥5 | `paper_final_gate` | 读 main.log 计数，超限判 ❌；引擎另查未定义引用（旧内联未查，更严） |
| 6. AI 列表（itemize） | `paper_final_gate` | sections 内 `\begin{itemize}` 计数，>0 判 ❌ |
| 7. 模板完整性 | `paper_final_gate` + `compile_check.sh` + 人工 | 引擎比对前言 4 类（usepackage/documentclass/pagestyle/bibliography）；赛事封面/承诺书/cline 由 Step 6 `compile_check.sh` 查；「前言差异是等价改写还是篡改」为人工判断 |
| 7b/10. 占位符 | `paper_final_gate` + 人工 | 引擎查 sections 的 `PLACEHOLDER`/`TODO` 字面；`[论文标题]`、`[中文摘要内容]` 等中文方括号占位符引擎不查，finish 前人工确认清零 |
| 8. TikZ | `paper_final_gate` + `figure_plan_reconciliation` | TikZ 由 `paper-figure-drawio` 编译为 figures/tikz_diagrams.pdf 后 `\includegraphics` 嵌入，引擎查 tikz_*.pdf 是否嵌入；计划 TikZ 改用 DrawIO 属合法替代 |
| 12. 中英文摘要 | 人工判断 | 各赛事要求不一（仅中文/仅英文/双语），引擎与 `compile_check.sh` 均不做统一摘要检查（后者显式 skip）；编译后人工核对 PDF 首页 |
| 13. 数值一致性 | `paper_final_gate` | all_results.json 关键指标与正文 1% 容差对账，>3 项缺失判 ❌ |
| 13.5. 太完美检测 | `paper_final_gate` advisories + `result_sanity_check` | >0.999/零误差等只提示不阻断；硬错误（NaN/负误差/R²<0.5/p>1）与 AUDIT_OK 凭证由 `result_sanity_check` 在 paper-analysis 步骤承接 |
| 13.6. 合理性审查章节 | `paper_final_gate` | RESULTS.md 缺合理性审查章节判 ❌ |
| 13.7. 数据源时间戳 | `paper_final_gate` advisories + 人工 | mtime 判据降为 advisory（复制/恢复工作区必误报），是否真陈旧人工确认 |
| 13.8. 正文长表格 | `compile_check.sh`（Step 6） | 引擎无对应项，由 Step 6 脚本承接 |
| 14. 元叙述泄露 | `paper_final_gate` | 内部文件名（RESULTS.md/AGENTS.md 等）出现在 sections 判 ❌ |
| 15. 过度声称 | `paper_final_gate` advisories | 只提示不阻断，建议温和化 |
| 16. Claims 覆盖 | `paper_final_gate` | PAPER_PLAN claims 关键词未在正文命中判 ❌ |

> 六类检查（数值一致性/太完美/数据源时间戳/长表格/元叙述/过度声称）另有竞赛侧共享脚本实现：`academic-toolkit/skills/_utils/contest_consistency_check.py`（与 `shared-scripts/` 同源双副本，参数化 latex/docx 与中英文）——本技能以引擎 `paper_final_gate` 为准；竞赛场景（comp-compile-zh）以该共享脚本落闸。

人工判断项（`registry.json` → `paper_final_gate.manual_items`）：图表版式与视觉美观（图堆叠判据之外的观感）、claims 关键词命中之外的论证充分性、模板前言差异属等价改写还是篡改、可疑完美值结合研究背景确认是否真合理、图表 mtime 陈旧的人工确认。

**⛔ 引擎判 fail/unknown 时按 `violations` 逐项修复后重跑。省重编修复顺序：多数 ❌ 是源码类（.tex），先批量改完所有源码类问题再一次重编，不要修一项编一项；只有 PDF 体量等编译产物类问题需要重编。violations 全部清零前不得 finish。**

### Step 9: Output report

Status, PDF path, page count, compliance results, fixed errors, remaining warnings.

## 执行与产出

使用当前执行会话完成本步工作；产物路径按当前步骤合同。程序采集真实操作、输入输出、版本与运行清单，模型只负责实质成果和领域质量。

建议额外记录：LaTeX 引擎版本、包版本、编译警告数。编译日志门禁 compilation_log 要求保留编译日志。

## Key Rules

- No latexmk — manual step-by-step compilation
- Use `-interaction=nonstopmode`, not `-halt-on-error`
- Do not delete .bbl file (bibliography data) — also do not write cleanup scripts that delete .bbl
- Figure embedding is the compile step's responsibility — fix missing labels from figures/*.tex
- Bibliography is a core validation item — final PDF must not have `[?]`
- Primary output: `paper/main.pdf`, compile log: `paper/compile.log`
- Temp files: `_tmp/` directory
