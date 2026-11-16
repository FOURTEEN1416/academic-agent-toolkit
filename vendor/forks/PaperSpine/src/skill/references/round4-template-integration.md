# Round 4: Template Integration, Compilation and Page Verification

## Contents
- Step 1: Prepare the Applicable Template
- Step 2: Template Integration Check
- Step 3: Compile and Fix
- Step 4: Verify Content and Actual Page Design
- Step 5: Generate Plain Text Version

---

Use this method when integrating a manuscript into its final layout. Historical
“Round 3/4” names describe the work, not mandatory Runner transitions or approval
states. Start from the current semantic manuscript or existing TeX; do not assume
an earlier stage already chose the right preamble or compiled successfully.
Apply [manuscript-format.md](manuscript-format.md) for official-template discovery,
asset classification, local-PDF learning and final figure-size checks. Preserve
the scientific content while correcting the producing template and build.

## Step 1: Prepare the Applicable Template

Read the current venue/year/article-type instructions and downloaded package.
Keep the original sample and compile it with its documented engine and
bibliography tool as the comparison demo. Then prepare a working integration
under the existing manuscript directory, retaining required class/style files,
fonts/dependencies, the real figures, bibliography and editable source.

A native official `.tex` sample is a complete document, not a Pandoc template.
Fill its working copy, or make a thin Pandoc adapter that retains the official
class/options, fonts, geometry and front matter while translating content and
metadata insertion. Pass only that compatible adapter to `--template`. Word
styles use a separate prepared reference DOCX through `--reference-doc`.
Use manuscript-format.md's bounded, documented fallback if no applicable template
is obtainable; do not invent an official class or a requirement for user approval.

---

## Step 2: Template Integration Check

Check the actual generated/current source before compiling:

1. **Preamble consistency**: Does it use the verified template for this output?
   - `\documentclass` options
   - Package imports (no missing or conflicting packages)
   - Custom macro definitions needed by the source/writer
   - Official font/geometry settings retained; necessary adapter changes explained
   - Correct review/anonymity mode and title/abstract macros; no leftover demo text

2. **Figure path alignment**: Verify `\graphicspath{}` matches the actual figure directory. Verify every `\includegraphics{}` filename exists.

3. **Bibliography setup**: For BibTeX, check `.bst`, `.bib` and citation keys;
   for biblatex/Biber, check its actual resources and backend. For citeproc,
   check the selected CSL and resolved entries/links rather than requiring
   `\bibliographystyle{}` or rerunning BibTeX over preprocessed references.

4. **Section structure**: Verify the current article-type requirements and all
   intended manuscript sections. Populate author/declaration fields only with
   known facts; keep missing facts explicit without borrowing the demo's identity.

---

## Step 3: Compile and Fix

Use the template's documented build system/engine. The following is only an
example for a pdfLaTeX + BibTeX project, not a universal sequence:

```bash
cd <output_directory>/
pdflatex -interaction=nonstopmode <main_tex_filename>.tex
bibtex <main_tex_filename>
pdflatex -interaction=nonstopmode <main_tex_filename>.tex
pdflatex -interaction=nonstopmode <main_tex_filename>.tex
```

If compilation fails:
- Read the `.log` file to identify the error
- Fix its source, dependency or adapter cause while preserving official settings
- Rerun the affected build after a concrete correction and verify reference
  resolution. Do not repeat an identical failure without new evidence or a changed
  method. An unavailable dependency warrants an exact limitation, not a claim that
  no official template exists; preserve usable sources and independent work.

Common issues:
- **Undefined citation warnings**: Check keys, resources and bibliography build;
  add a missing entry only from a real verified source.
- **Undefined control sequence**: LaTeX macro misspelled or missing. Compare with original template.
- **Figure not found**: Path mismatch. Check `\graphicspath{}` and actual file locations.
- **Missing `$` / unbalanced braces**: Math mode or bracket mismatch. Trace from reported line number.
- **Missing glyphs or substituted fonts**: Inspect the final log and output;
  repair notation/font coverage without silently replacing a valid venue design.

---

## Step 4: Verify Content and Actual Page Design

After successful compilation, compare the actual PDF with the complete current
semantic source. Compilation alone proves neither completeness nor readable layout.

1. **Read the compiled PDF** page by page
2. **Compare against the source** section by section:
   - Are all intended sections, tables, notes and required declarations present?
   - Are all subsections present with correct numbering?
   - Are all figures visible and correctly referenced in the text?
   - Are all equations rendered correctly?
   - Are all citations resolved (no `[?]` markers)?
   - Are all numerical values intact?
3. **If any content is missing or corrupted**, fix the producing source/adapter,
   regenerate affected formats, and re-verify.

Compare representative pages against both the official demo and the actual local
target-venue PDFs (three by default or the saved count). Use manuscript-format.md's
page observations → producing layout change → rendered page method for title/body,
figures/tables, captions, references and page rhythm. Current submission rules
govern the submission artifact; learned publication design informs the reading
PDF without imitating publisher branding, DOI, volume/issue or acceptance dates.

Inspect every final PDF page and the requested Word's faithful rendering. Measure
placed figure dimensions and effective smallest labels in each format. If a
figure/caption pair does not fit legibly, change allowed placement, panel layout
or lettering rather than shrinking until it fits. Check links, reading order and
all pages affected by reflow; reuse unchanged scientific checks.

---

## Step 5: Generate Plain Text Version

When a plain-text reading copy is useful/requested, extract it from the current
verified output/source (historically `plain_text_paper.md`). It supplements the
actual PDF/Word checks and cannot establish layout or image readability.

---

## Output Structure

Keep reproducible assets together in the existing task. The names below illustrate
the historical layout, not a required new folder or fixed artifact inventory:

```
<paper_output_directory>/
├── <main_tex_filename>.tex    # Main LaTeX document (the filled template)
├── Fig/ or figures/            # Figure files
├── reference.bib               # Bibliography
├── [template files]            # cls, sty, bst files
├── supplementary.tex           # If applicable
└── paper_rewriting_output/     # All intermediate outputs
```
