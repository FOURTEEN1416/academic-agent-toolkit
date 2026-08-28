---
name: bib-doi-toggle
user_invocable: true
description: Toggle DOI/URL display in the compiled bibliography of a biblatex-based LaTeX paper. Default-on for review/writing builds (clickable refs in the PDF). Invoking with no arg asks user what to do. Use when the user says "show DOIs in refs", "make refs clickable", "turn off DOI display", etc. 
---

# bib-doi-toggle — Toggle clickable DOI/URL refs

Toggle whether DOI and URL fields print in the compiled bibliography of a biblatex paper.

## When to use

- **Turn on** during writing and review so co-authors and reviewers can click through to verify each citation. This is the common case.
- **Turn off** only if a specific venue requires DOI/URL fields stripped from the bibliography (rare — most just ignore them at typesetting). Don't pre-emptively turn off.
- If the user passes `on` / `off`, do that. If no argument, **ask** which they want.

## Scope: biblatex only

This skill assumes biblatex (with biber).
If the paper uses natbib + a `.bst` file, bail out with a friendly message — the toggle approach there is style-specific and out of scope.

Detect by grepping the main `.tex` for `\usepackage[...]{biblatex}`.
If absent (and `\bibliographystyle{...}` / `\bibliography{...}` present instead → natbib), report and stop.

## Workflow

### 1. Find the paper

Same search order as other claude-scholar skills:
1. User-provided path
2. `paper/current/main.tex`
3. `paper/main.tex`
4. `main.tex`

### 2. Detect biblatex

- Read the main `.tex` and locate `\usepackage[...options...]{biblatex}`. Bail out if not found (see "Scope" above).
- If invoked with no argument, ask the user whether to turn `on` or `off` before editing.

### 3. Apply

**To turn on** (review/writing build):
- Set `doi=true, url=true, eprint=true` in the biblatex options.
- Set `isbn=false` (almost never useful for clickability and adds noise).
- If `\usepackage{hyperref}` is present, optionally suggest enabling colored links so reviewers can spot them: `\hypersetup{colorlinks=true, citecolor=blue, urlcolor=blue}`.

**To turn off** (submission build):
- Set `doi=false, url=false, eprint=false, isbn=false`.
- Leave hyperref settings alone unless the user asks.

Edit the options *in place* in the existing `\usepackage[...]{biblatex}` line — don't add a duplicate package call.

### 4. Report

Tell the user what changed and that they need to recompile (`make` / `latexmk`) to see the new bibliography.

### 5. Contextual nudge (only when toggling ON)

After turning the display **on**, scan the `.bib` file for entries missing a `doi` field (and missing `url`/`eprint` for entries that don't have a DOI, like preprints).
If any are missing:

- List the citekeys (cap at ~10 for readability; say "and N more" if truncated).
- Offer to backfill them: "Want me to look these up via `claude-scholar:doi-bibtex` (if you have DOIs) or `claude-scholar:openalex` (search by title)?"

Don't nudge on the off-toggle — there's nothing actionable to surface.
Don't nudge generically (e.g., "also run check-refs") — keep this skill atomic.

## Notes

- This skill mutates `main.tex`. Always work on a clean tree or warn the user if there are uncommitted changes that could obscure the diff.
- Some journals strip URLs even when they're in the source — but explicit `url=false, doi=false` is the safest default for submission, and lets the user toggle back on after acceptance for the camera-ready / arXiv mirror as desired.
- If the user uses a separate review build (e.g., `main-review.tex` that `\input`s `main.tex`), the toggle should still operate on the main `\usepackage{biblatex}` call. Mention this in the report so the user knows what was edited.

## Related

- `claude-scholar:check-refs` — verify references exist; complementary to this skill but separate concerns. Run check-refs once early; toggle this skill on/off across the writing/submission lifecycle.
- `claude-scholar:doi-bibtex` — fetch BibTeX for a known DOI; pair with this skill's contextual nudge to backfill missing DOI fields.
- `claude-scholar:openalex` — search by title to find the DOI when only a title is known.
- `claude-scholar:presubmit-checks` — pre-submission sweep; can flag if a venue specifically needs DOIs stripped.
