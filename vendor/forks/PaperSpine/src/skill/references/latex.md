# LaTeX Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Assemble the LaTeX project, compile PDF when possible, and produce Word output.
Word (.docx) is a standard required artifact, not optional. Do not change
manuscript logic during assembly.

For a section-by-section, template-first conversion (copy the base `.tex`,
`Edit` only prose paragraphs, preserve preamble / floats / equations /
`\maketitle` / bibliography commands) and the compile-and-fix + content-integrity
steps, follow `references/round3-latex-polish.md` then
`references/round4-template-integration.md`. They also walk the proper citation
mechanism — `\cite` + `\bibliographystyle`/`\bibliography` resolved by bibtex —
which is exactly the linkage `latex_guard.py` now enforces (see the citation
hard rule below).

## Required Outputs

- `final_paper/main.tex`
- `final_paper/main.pdf` (compiled source PDF when TeX engine is available)
- `final_paper/paper.pdf` (must be a current copy of `main.pdf`)
- `final_paper/paper.docx` + `word_report.md`
- `final_paper/paper.zh.docx` + `word_report.zh.md` when `translation_package=zh`
- `latex_report.md`
- `final_artifact_manifest.md`

## Scripts

```bash
python scripts/latex_guard.py paper_rewriting_output/final_paper/main.tex --markdown
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx --tex paper_rewriting_output/final_paper/main.tex --language en --fix-fonts
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx --tex paper_rewriting_output/final_paper/main.tex --language en --markdown --output paper_rewriting_output/word_report.md
```

## Key Rules

**PDF alias (hard rule):** after compiling `final_paper/main.pdf`, copy it to
`final_paper/paper.pdf` in the same run. `paper.pdf` must match `main.pdf`;
never leave an older `paper.pdf` beside a newer `main.pdf`.
`artifact_check.py` fails stale or mismatched `paper.pdf`.

**Citation mechanism (hard rule):** Every in-text citation must be a real
`\cite{key}` linked to a bibliography entry — either `\bibliographystyle{unsrt}`
(or `plain`/`ieeetr`) + `\bibliography{references.bib}`, or a `thebibliography`
block whose `\bibitem{key}` entries are reached by `\cite{key}`. Never type the
bracket number as literal text: a hand-typed `[1]` is inert and links to nothing
in either the PDF or the .docx, and the numbering silently desyncs if the
reference list reorders. A numeric `bibliographystyle`/CSL still renders as `[1]`
or `[3,12,13]`, so the visible plain-numeric style is preserved. Author-year
citations and extra-parenthesized numeric citations such as `([15])` are
forbidden. Do not use superscript for these citations unless the target journal
explicitly requires it. `latex_guard.py` fails literal-bracket citations that
have no `\cite` and flags numbering that exceeds the reference-entry count.

**Title (hard rule):** `main.tex` must contain `\title{...}` (with the paper's
title) and `\maketitle` after `\begin{document}`. Word output must begin with
the paper title on the first page, not Abstract, Keywords, Introduction, or
body paragraphs. `latex_guard.py` checks the TeX source; `word_guard.py`
checks the .docx.

- Preserve citation keys and labels.
- Copy approved images into `figures/` with stable labels.
- For Chinese: prefer XeLaTeX + CJK-capable template.
- If no TeX engine: keep `.tex`, record skipped compilation.
- If compilation fails: keep `.tex`, write first fatal error, do not claim pass.
- Word output is mandatory by default. If `word_output` is missing, treat it as
  `docx`. Only explicit `word_output=none` opts out.
- If pandoc is unavailable while Word is required, write BLOCKED/FAIL in
  `latex_report.md`, keep the workflow incomplete, and do not silently skip
  Word.

## English Word Output

From `final_paper/`:

```bash
pandoc main.tex -o paper.docx --from latex --to docx \
  --resource-path=. --extract-media=./media \
  --number-sections --citeproc --bibliography=references.bib
```

Flatten `\input`/`\include` with `latexpand` first. Expand or remove
`\newcommand` macros. Verify tables, citations, figures after conversion.

After conversion, run `word_guard.py --fix-fonts` first, then run
`word_guard.py --markdown --output ...` and require PASS before proceeding.
English Word must use Times New Roman in the default/body/title styles and
theme fonts; do not rely on pandoc's default Office theme.

```bash
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx \
  --tex paper_rewriting_output/final_paper/main.tex \
  --language en --fix-fonts
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx \
  --tex paper_rewriting_output/final_paper/main.tex \
  --language en --markdown --output paper_rewriting_output/word_report.md
```

If numbered headings render as `1Introduction` or `2Methods`, regenerate or
repair the Word file so headings read `1 Introduction`, `2 Methods`, etc.
`word_guard.py` fails glued English heading numbers.

## Final Chinese Word Output

When `translation_package=zh` and `word_output` is not explicitly `none`, the
final Chinese deliverable is a single Word document, not a folder of Markdown
files:

- Required final file: `paper_rewriting_output/final_paper/paper.zh.docx`
- Required check report: `paper_rewriting_output/word_report.zh.md`

Generate it from `translation_zh/full_paper_translation.zh.md` after the
translation stage:

```bash
pandoc paper_rewriting_output/translation_zh/full_paper_translation.zh.md \
  -o paper_rewriting_output/final_paper/paper.zh.docx
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx \
  --tex paper_rewriting_output/final_paper/main.tex \
  --language zh --fix-fonts
python scripts/word_guard.py paper_rewriting_output/final_paper/paper.zh.docx \
  --tex paper_rewriting_output/final_paper/main.tex \
  --language zh --markdown --output paper_rewriting_output/word_report.zh.md
```

`translation_zh/` remains the translation audit/intermediate package. Do not
list it as the only Chinese deliverable.
Chinese Word must use SimSun/宋体 for East Asian text and Times New Roman for
Latin text. If the font gate fails, repair the docx and re-run the report.

**Chinese abstract heading:** In a Chinese `main.tex`, author the abstract as
`\section*{摘要}` followed by the abstract paragraph rather than the LaTeX
`abstract` environment. pandoc renders `\begin{abstract}` as an English
"Abstract" heading in the .docx even for a Chinese paper (the `lang` variable
does not localize it); `\section*{摘要}` produces 摘要 in both the ctex PDF and
the Word file.
