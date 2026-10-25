---
name: paper-compile
description: "Compile English LaTeX paper to PDF using pdflatex. Use when user says ”compile paper” or ”build PDF”."
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

Requires `pdflatex` and `bibtex` on PATH. If either is missing, report TOOL_GAP and stop — never fake a compile.

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

Embedding rules (production knowledge):

- Every `\ref{}` in the body needs a matching `\label{}`. When a label is missing, find the corresponding block in `figures/*.tex` and embed it into the right section file with lead-in text + analysis.
- Every `figures/*.pdf` must be referenced from the body. The engine check `paper_final_gate` verifies this at finish.
- Every `\label` in `figures/TABLE_*.tex` must be referenced from the body. `paper_final_gate` does not cover tables, so check them explicitly:

```bash
for tbl in figures/TABLE_*.tex; do
    [ -f "$tbl" ] || continue
    for lbl in $(grep -oh '\\label{[^}]*}' "$tbl" 2>/dev/null); do
        grep -rq "$lbl" paper/sections/*.tex paper/main.tex 2>/dev/null || echo "UNEMBEDDED TABLE: $lbl"
    done
done
```

An embedded figure or table is not done until its surrounding prose has lead-in text and analysis.

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

### Step 4: Error diagnosis and fix

After each compile, read `paper/main.log` for `!` error lines. Iterate up to MAX_COMPILE_ATTEMPTS times, each with the full 4-step compilation. For each class of error:

- **Math errors**: read the error location from `main.log`, open the file, fix broken `$...$` delimiters individually. Do NOT use broad sed patterns.
- **LR mode errors**: add `\par` or a blank line before float environments.
- **Missing packages**: install them.
- **BibTeX failures**: fix LaTeX errors first (BibTeX fails when LaTeX errors exist upstream), then recompile.

If the same error survives three fix attempts, stop and report it as an escalation instead of looping. When fixing errors in main.tex, only fix the specific error. Do not rewrite or restructure main.tex — the template's preamble, page margins, and formatting settings must remain unchanged.

### Step 5: Post-compile checks

```bash
bash _utils/compile_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/compile_check.sh paper/
bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/
```

`compile_check.sh` covers what `paper_final_gate` does not: template integrity, package conflicts (cite + natbib), contest-specific front matter, over-long tables, abstract/bibliography structure. `writing_check.sh` covers source/narrative/layout/style/AI-tell checks. Exit code 3 from either means the checker itself is unavailable — record TOOL_GAP, never read it as a content failure.

### Step 6: Page count verification

Body pages = Introduction through Conclusion, excluding references and appendix.
Body pages must be ≥ MAX_PAGES. If insufficient, return to `skills/paper-write/SKILL.md` to expand content.

### Step 7: Final gate — engine `paper_final_gate`

`session finish` runs the engine check `paper_final_gate` for this step in **delivery: blocking** — the step cannot finish until `violations` and `unverified` are cleared (unknown means the checker could not verify, not a pass). Exploration-tier runs record it as advisory only. Standalone: `cd academic-toolkit && python engine/quality_gates.py gate <workspace> --check paper_final_gate` (0=pass, 1=fail, 3=unknown — not a pass). Fix hints: `fix_hint` in `engine/modex-core/checkers/registry.json`.

It takes over the old FINAL QUALITY GATE's machine-decidable items; the full checklist and per-item `fix_hint` are in `engine/modex-core/checkers/registry.json`. Advisory-only items: suspicious perfect values, overclaiming, stale figure data.

Human judgement still needed: visual layout beyond stacking, argument sufficiency beyond claim keywords, whether a preamble change is an equivalent rewrite, and whether a perfect-looking value is genuine. TikZ is compiled by `skills/paper-figure-drawio/SKILL.md` into `figures/tikz_diagrams.pdf` and embedded with `\includegraphics`; a planned TikZ replaced by DrawIO is a legitimate substitution.

### Step 8: Output report

Status, PDF path, page count, compliance results, fixed errors, remaining warnings.

## 执行与产出

使用当前执行会话完成本步工作；产物路径按当前步骤合同。程序采集真实操作、输入输出、版本与运行清单，模型只负责实质成果和领域质量。

建议额外记录：LaTeX 引擎版本、包版本、编译警告数。编译日志门禁 compilation_log 要求保留编译日志。

## Key Rules

- No latexmk — manual step-by-step compilation
- Use `-interaction=nonstopmode`, not `-halt-on-error`
- Do not delete .bbl file (bibliography data)
- Figure embedding is the compile step's responsibility — fix missing labels from figures/*.tex
- Bibliography is a core validation item — final PDF must not have `[?]`
- Primary output: `paper/main.pdf`, compile log: `paper/compile.log`
- Temp files: `_tmp/` directory
