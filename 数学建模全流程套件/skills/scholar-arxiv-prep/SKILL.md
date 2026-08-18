---
name: arxiv-prep
user_invocable: true
description: Prepare an arXiv submission package from a LaTeX paper. Cleans the source, builds a tarball, and extracts metadata for the submission form. Use before uploading to arXiv.
---

# arxiv-prep — arXiv Submission Preparation

Automate the tedious steps of preparing a LaTeX paper for arXiv upload. Creates a clean copy, removes cruft, verifies compilation, and produces a ready-to-upload tarball.

## When to Use

- "prep for arxiv", "make an arxiv package", "I need to upload this to arxiv"
- After the paper is finalized and ready for submission
- Complements `presubmit-checks` (content quality) — this skill handles packaging

## Workflow

### Phase 1: Pre-clean (judgment calls)

#### 1. Find the paper

Same search logic as presubmit-checks:
1. User-provided path
2. `paper/current/main.tex`
3. `paper/main.tex`
4. `main.tex`
5. Glob for `**/*.tex` with `\begin{document}`

Identify the **paper directory** (parent of the main `.tex` file). All subsequent operations are relative to this directory.

#### 2. Optionally run presubmit-checks

Ask the user: "Want me to run the presubmit-checks first?" Skip if they say they already did.

#### 3. Check for supplements

Scan for separate supplement/appendix `.tex` files (e.g., `supp.tex`, `appendix.tex`, `si.tex`). If found, ask the user whether to:
- **Merge** into the main file via `\appendix` (arXiv prefers single-PDF submissions)
- **Keep separate** (will be included as ancillary files)

#### 4. Review style files

Grep for journal-specific language that should be removed for arXiv:
- "Submitted to", "Under review at", "Accepted by"
- Journal-specific class options (e.g., `review`, `preprint` mode toggles)
- Copyright/license statements that conflict with arXiv's license

Flag these and ask before changing.

### Phase 2: Automated cleaning

#### 5. Optimize bibliography

Run `bib_optimizer` to remove unused citations and reorder entries to match their order of appearance in the text:

```bash
uvx bib_optimizer bibopt <main.tex> <references.bib> <references_cleaned.bib>
```

- If the paper has a **supplement with its own `.bib`** (e.g., `si.tex`/`supp.tex` using `si_references.bib`), run `bibopt` separately for each:
  ```bash
  uvx bib_optimizer bibopt <si.tex> <si_references.bib> <si_references_cleaned.bib>
  ```
- If the supplement **shares the main `.bib`**, run `bibopt` on each `.tex` file separately against the same `.bib`, then merge the two outputs (concatenate and deduplicate entries by cite key):
  ```bash
  uvx bib_optimizer bibopt <main.tex> <references.bib> <references_main.bib>
  uvx bib_optimizer bibopt <si.tex> <references.bib> <references_si.bib>
  ```
  Then merge with `bibtool` (deduplicates by cite key):
  ```bash
  bibtool -d references_main.bib references_si.bib -o references_cleaned.bib
  ```
  If `bibtool` is not available, concatenate both files and manually remove any duplicate `@type{key,` entries (keep the first occurrence).
- Update the `\bibliography{...}` command in each `.tex` file to point to the cleaned file.
- The original `.bib` is never modified.

If `bib_optimizer` is not available, skip this step — the `.bib` will still be handled in step 7.

#### 6. Run arxiv-latex-cleaner

```bash
uvx arxiv-latex-cleaner <paper-dir> --resize_images --im_size 500 --compress_pdf
```

This creates a `<paper-dir>_arXiv/` directory with a cleaned copy. The original is untouched. The `--compress_pdf` flag reduces embedded PDF figure sizes, helping stay under arXiv's 50 MB limit.

If `arxiv-latex-cleaner` is not available, fall back to manual cleaning:
- Copy the paper directory
- Remove `.git/`, `__pycache__/`, `.DS_Store`
- Remove commented-out text blocks (lines starting with `%` that aren't TeX directives)
- Remove unused `.tex` files not referenced by `\input` or `\include`

#### 7. Post-cleaner fixes in `_arXiv/`

Apply these fixes to the cleaned copy:

- **4-pass trick**: Add `\typeout{get arXiv to do 4 passes}` on the line after `\end{document}` — this ensures arXiv runs enough LaTeX passes to resolve all references
- **Ensure `.bbl` exists**: Check if a `.bbl` file exists. If not, compile with `pdflatex` + `bibtex`/`biber` to generate it. arXiv needs the `.bbl`, not the `.bib`
- **Ask before deleting `.bib`**: If `.bbl` exists, ask the user whether to remove `.bib` files (reduces package size; arXiv uses `.bbl` directly)
- **Clean aux files**: Remove `.aux`, `.log`, `.out`, `.blg`, `.fls`, `.fdb_latexmk`, `.synctex.gz`, `.toc`, `.lof`, `.lot`, `.nav`, `.snm`, `.vrb`. Do **not** use `latexmk -CA` here — it also removes `.bbl`, which arXiv needs
- **Remove `.git/`** if it exists in the copy

### Phase 3: Verify & package

#### 8. Test compilation

Run in the `_arXiv/` directory:

```bash
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

(Three passes to resolve references.) Report:
- **Errors**: any lines with `!` — these are blockers
- **Warnings**: undefined references, missing citations, overfull hboxes
- If compilation fails, report the error but continue to the next steps

#### 9. Extract clean metadata

Parse the `.tex` file to extract metadata for copy-paste into the arXiv submission form:
- **Title**: from `\title{...}` — strip LaTeX commands, math mode, line breaks
- **Abstract**: from `\begin{abstract}...\end{abstract}` — strip LaTeX commands
- **Authors**: from `\author{...}` — extract names, strip affiliations/footnotes
- **Comments**: suggest standard format. If the paper has supplementary material, use: "Main text: X pages, X figures. Supplementary Information: X pages, X figures". Otherwise: "X pages, X figures"

Present this in a clean, copy-pasteable format.

#### 10. Create tarball

```bash
cd <paper-dir>_arXiv && tar -cvf ../arxiv-submission.tar *
```

- Warn if the tarball exceeds 50 MB (arXiv's limit is ~50 MB for source)
- Report the file count and size
- Note: arXiv also accepts `.tar.gz` — use gzip if close to the limit

#### 11. Final summary

Present:
- Package location and size
- Clean metadata (title, abstract, authors, comments)
- Compilation status (clean / warnings / errors)
- Remaining manual steps:
  - Upload `arxiv-submission.tar` at https://arxiv.org/submit
  - Select primary subject area and cross-list categories
  - Paste metadata into the form
  - Set license (usually CC BY 4.0 or arXiv perpetual non-exclusive)
  - Share the submission password with co-authors

## Rules

- **Never modify the original paper directory** — all changes happen in the `_arXiv/` copy
- Ask before destructive operations (deleting `.bib`, merging supplements)
- If any step fails, continue with the remaining steps and report all issues at the end
- Keep the final summary concise and actionable

