---
name: paper-spine-latex
description: Handles LaTeX project assembly, figure placement, citations, labels, and compile-safe cleanup. (internal /paperspine step)
---

# PaperSpine LaTeX

Use this skill for LaTeX assembly, template integration, figure placement,
citations, labels, and compile-safety checks. Do not change manuscript logic
unless rewrite/build outputs require it.

## Required Inputs

- revised manuscript or built manuscript
- target template if any
- figures, tables, bibliography, and source files
- `paper_rewriting_output/figure_asset_map.md` when building from materials

## Required Outputs

- updated LaTeX project; for from-materials builds, use
  `paper_rewriting_output/final_paper/main.tex`
- compiled PDF when a TeX engine is available; for from-materials builds, use
  `paper_rewriting_output/final_paper/paper.pdf`
- `paper_rewriting_output/latex_report.md`
- `paper_rewriting_output/final_artifact_manifest.md` when producing final
  deliverables
- optional `paper_rewriting_output/final_paper/paper.docx` plus
  `paper_rewriting_output/word_report.md`

## Rules

- The project path may contain spaces or non-ASCII characters (e.g.
  `exp_lab_en - 副本`). Quote every path passed to pandoc/copy commands and avoid
  unquoted shell globs; they break silently on such directories. On Windows
  prefer PowerShell for file operations.
- Keep content work separate from LaTeX scaffolding.
- Preserve citation keys and labels unless there is a verified reason to rename.
- Copy approved images into `figures/` and use stable labels.
- Run `scripts/latex_guard.py` when available.
- Record unresolved compile or asset issues in `latex_report.md`.
- Do not treat Markdown as the final manuscript when the workflow is
  `build_from_materials`.
- For Chinese output, prefer XeLaTeX and a CJK-capable template. For English
  output, follow the target template or use a conservative article template.
- If no TeX engine is available, keep the `.tex` and record that compilation was
  skipped in `latex_report.md`.
- If compilation fails despite an available engine, keep the `.tex`, write the
  first fatal error to `latex_report.md`, and do not claim the artifact check
  passes.
- If generating Word output, use pandoc from the `final_paper/` directory. When
  the manuscript uses BibTeX citations, resolve them with citeproc so `\cite`
  commands render as formatted references instead of leaking raw LaTeX:
  ```bash
  cd final_paper
  pandoc main.tex -o paper.docx --from latex --to docx \
    --resource-path=. --extract-media=./media \
    --number-sections --citeproc --bibliography=references.bib
  ```
  - `--citeproc --bibliography=references.bib` renders `\cite{...}` and the
    reference list; omit only when the manuscript has no citations
  - `--number-sections` keeps headings numbered like the LaTeX source
  - `--resource-path=.` resolves `\includegraphics{figures/...}` paths
  - `--extract-media=./media` embeds images into the docx
  - For house styles (fonts, heading styles, margins), add
    `--reference-doc=reference.docx` built from the target template
  - `\ref`/`\autoref` cross-references need the `pandoc-crossref` filter
    (`--filter pandoc-crossref`); without it they may render as `[?]`
  - Without these flags, pandoc silently drops images or citations, or produces a blank docx
  - Run from `final_paper/` so relative paths in `.tex` resolve correctly
  - Do NOT use intermediate plain-text steps that strip encoding
- Run `scripts/word_guard.py final_paper/paper.docx --markdown --output
  paper_rewriting_output/word_report.md` and fix failures before presenting
  the Word file as usable. If word_guard reports 0 paragraphs, check that
  images are in supported formats (PNG/JPG) and the `figures/` directory exists.
- To keep Word output faithful, prevent these common pandoc errors:
  - Flatten `\input`/`\include` first (e.g. `latexpand main.tex > flat.tex`),
    then convert the flattened file; pandoc does not pull sub-files in reliably.
  - Expand or remove custom `\newcommand`/`\def` macros; pandoc drops macros it
    cannot resolve, silently losing their content.
  - Keep tables simple (`tabular`/`booktabs`); `tabularx`, `multirow`, and nested
    tables often misalign in docx, so open and verify each table.
  - Citeproc renders author-date by default, so a numeric LaTeX style (`plain`,
    `unsrt`, `ieeetr`) renders differently in Word. To keep numbered `[1]`
    citations, pass a numeric CSL, e.g. `--csl=ieee.csl` or `--csl=vancouver.csl`.
  - For Chinese, build `--reference-doc=reference.docx` with a CJK font (e.g.
    SimSun or Noto Serif CJK) or characters render as boxes.
  - After conversion, open the docx and confirm headings, equations, figures,
    tables, and references all rendered.

Read `references/latex-source-control.md` before structural LaTeX edits.
