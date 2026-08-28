---
name: presubmit-checks
user_invocable: true
description: Pre-submission checklist for LaTeX papers. Runs several checks in parallel — references, LaTeX cleanup, build, and front matter — then presents a unified report. Use before submitting or sharing a paper draft.
---

# presubmit-checks — Paper Pre-Submission Checklist

Run a comprehensive set of checks on a LaTeX paper before submission.

## When to Use

- "presubmit check", "check before I submit", "is my paper ready?"
- Before submitting to a journal or conference
- Before sharing a draft with co-authors

## Checks

The skill runs these checks, ideally in parallel via subagents:

### 1. References (subagent: check-refs skill)
Verify all cited papers exist in academic databases. Flag unverified entries, suggest missing DOIs.

### 2. LaTeX cleanup (subagent: latex-cleanup skill)
Run the full latex-cleanup checklist: common issues, style consistency, draft artifacts, cross-references, typography, and missing figures.

### 3. Build check
If a Makefile exists, run `make` and check for:
- Compilation errors
- Undefined references (`LaTeX Warning: Reference ... undefined`)
- Missing citations (`LaTeX Warning: Citation ... undefined`)
- Overfull hboxes (badly broken lines)
Report warnings count and list the critical ones.

### 4. Figure format check

Scan for all figures included in the paper (`\includegraphics`, `\input` for pgf/tikz). For each figure file:
- Check the file extension — PDF, EPS, and PGF/TikZ are vector formats (good). PNG, JPG/JPEG, TIFF, and BMP are bitmap formats (flag).
- For any bitmap figure found, report the filename, resolution if detectable, and file size.
- Flag bitmap figures as **blockers** — they often indicate low-resolution images that will look poor in print.
- Exception: photographs and screenshots are legitimately bitmap — note this but still flag for the user to confirm intentionality.

### 5. Front matter review
Read the paper and check:
- **Affiliations**: List all authors and their affiliations. Flag if any author is missing an affiliation or if affiliations look incomplete (e.g., missing department, institution, or country).
- **Acknowledgements**: Extract the acknowledgements section and list:
  - All grant numbers / funding sources mentioned
  - All individuals thanked (for discussions, feedback, etc.)
  - Flag if the acknowledgements section is missing entirely
- **Code/data availability**: Check for a data availability statement or code availability statement. Flag if missing — most journals now require one. Look for `\dataavailability`, `\codeavailability`, or sections titled "Data Availability", "Code Availability", "Data and Code Availability", etc.

## Workflow

### 1. Find the paper

Same search logic as check-refs:
1. User-provided path
2. `paper/current/main.tex`
3. `paper/main.tex`
4. `main.tex`
5. Glob for `**/*.tex` with `\begin{document}`

### 2. Run checks in parallel

Launch subagents for independent checks:
- **Agent 1**: Run check-refs (bibsleuth existence check)
- **Agent 2**: Run latex-cleanup skill on the `.tex` file
- **Agent 3**: Run `make` in the paper directory if Makefile exists
- **Agent 4**: Figure format check — scan all `\includegraphics` paths and flag bitmap formats (PNG, JPG, TIFF, BMP)
- **Agent 5**: Front matter review — read the paper and extract affiliations, acknowledgements (grants + people thanked), and code/data availability statements for the user to verify

### 3. Present unified report

Organize findings by severity:

**Blockers** (must fix):
- Missing figures
- Undefined references/citations
- Compilation errors
- Retracted citations
- Bitmap figures (PNG, JPG, TIFF, BMP) — should be vector (PDF, EPS) unless intentionally raster (photos, screenshots)
- Missing code/data availability statement (if journal requires it)

**Warnings** (should fix):
- Unverified references
- Draft artifacts (TODOs, commented-out text)
- `draft` mode still enabled
- Overfull hboxes
- Missing or incomplete affiliations

**For user to verify** (cannot be auto-checked):
- Affiliations — list all authors + affiliations for the user to eyeball
- Acknowledgements — list all grants and people thanked so the user can confirm completeness
- Code/data availability — show the statement for the user to review

**Suggestions** (nice to fix):
- Missing DOIs/URLs in `.bib`
- LaTeX style issues
- Spacing/typography

### 5. Offer to fix

For each category, offer to fix what can be automated:
- Apply `.bib` patches (DOIs, URLs)
- Remove draft artifacts
- Fix spacing issues
- Ask before each category of changes

### 6. Offer content review

After presenting the report and addressing formatting/technical issues, offer:
"Want me to run `/critique-manuscript` to check for content-level weaknesses reviewers might flag?"

This is a deeper, separate pass that evaluates the paper's substance (literature, methodology, claims, etc.) rather than its formatting and technical correctness.

## Rules

- Run all checks even if one fails — present a complete picture
- Clearly separate blockers from suggestions — don't alarm about minor issues
- Don't modify files without asking
- If the paper doesn't compile, still run the other checks
- Keep the final report concise — group similar issues rather than listing every overfull hbox
