---
name: paper-writing
description: Writes and revises scientific manuscripts, journal articles, preprints, theses, reports, in full paragraphs with the argument built from the project's actual results and sources, as a real .tex or .md file in the working folder. Use for drafting or revising a paper, a section, an abstract, a response to reviewers, or a technical report in any field. For ML conference papers use ml-paper-writing; for adding or checking references use citations; for figures use figures or schematics.
summary: "Draft or revise a manuscript, report or thesis section as a real file, from the evidence."
category: core
role: workflow
allowed-tools: [Read, Write, Edit, Bash, glob, grep, webfetch]
license: MIT
version: 1.0.0
author: Synthetic Sciences
metadata:
  upstream: K-Dense-AI/claude-scientific-writer
  upstream-url: https://github.com/K-Dense-AI/claude-scientific-writer
  upstream-license: MIT
  upstream-relationship: references and scripts derived
  adapted-by: Synthetic Sciences
  skill-author: Synthetic Sciences
  adapted-from: K-Dense scientific-writing and venue-templates (MIT); alphaXiv OpenResearch orx-paper (MIT)
---

# Paper writing

A paper is an argument with evidence attached, written for a reader who is busy and
skeptical. The draft succeeds when a reviewer can state the claim, the evidence, and the
limits after one read, and cannot find a sentence the results do not support.

## Non-negotiables

1. **Write the file, not an outline in chat.** Create or edit the manuscript in the working
   folder (`paper.tex`, `paper.md`, or the user's file) and link it. An outline in chat
   gives the user nothing to render or send.
2. **Every claim traces to a result or a source.** Numbers come from the project's outputs
   (tables, logs, tracked runs), quoted with their units, precision and conditions. Prior
   work is cited only after reading it; the citations skill resolves and verifies the
   references, never memory.
3. **Prose, not lists.** Sections are paragraphs, each with one point stated in its first
   sentence. Bullets belong in supplementary checklists, not in the body.
4. **Preserve what exists.** When revising a manuscript, keep its claims, structure,
   figures and voice unless the user asked for those to change. Improve the sentence, not
   the science, unless the science is wrong, and then say so.
5. **State the limits where the claim is.** Scope, sample, assumptions and failure cases go
   in the results and discussion, not only in a limitations paragraph at the end.
6. **Match the venue.** Length, section order, abstract form, reference style and figure
   rules come from the target; `references/journals-formatting.md` and the style files
   below carry the common ones.

## Workflow

- [ ] Fix the target: venue or document type, length, audience, deadline, template.
- [ ] Inventory the evidence: results, figures, data, methods, prior drafts, notes.
- [ ] Write the argument in one paragraph before the sections.
- [ ] Draft sections in evidence order: methods, results, discussion, introduction, abstract.
- [ ] Verify every number and citation against its source; compile; read the PDF yourself.
- [ ] Hand over with the open questions listed.

**Target.** Ask once if the venue or document type is unknown and it changes the shape;
otherwise infer from the request. Check the working folder for a template or class file
the user supplied and use it unchanged (`\documentclass`, packages, section skeleton);
without one, `assets/report-template.tex` and `assets/scientific_report.sty` compile
cleanly for a report or preprint.

**Evidence.** Read the results files, notebooks, tracked runs and figures before writing a
sentence about them. A report on work done in this session is built from that evidence and
cites outside work only where the text needs it; a literature review belongs to a
manuscript for submission, not to every write-up. Build a short table of the claims the evidence supports, each with
its source path. Anything the user asserts that the evidence does not show is flagged, not
written as fact.

**Argument.** One paragraph: the question, why it is open, what was done, what was found,
what it means. If this paragraph cannot be written, the paper is not ready and the user
should hear that first.

**Sections.** Follow `references/imrad-structure.md` for empirical work and adapt for
theory, methods and review papers. Write the methods and results first (they are facts),
the discussion next (interpretation), then the introduction (the argument in reverse), and
the abstract last (the paper in miniature: question, approach, main result with a number,
implication). Titles state the finding when the venue allows it.

**Figures and tables.** Each makes one claim, named in its caption's first clause; the
figures skill builds plots, the schematics skill renders diagrams and the generate-image
skill renders illustrations and graphical abstracts, all with `generate_image`, never
hand-drawn as TikZ or SVG. A report with a method section gets an overview schematic; a
report that argues a mechanism gets a conceptual figure. When image generation is
unavailable, leave a placeholder box with the planned caption and say what is needed to
render it, rather than drawing it by hand. Tables carry the numbers the prose cites, with
uncertainty and n. Reference every figure and table in the text before it appears.

**Page balance.** Floats are placed by LaTeX, not by where they sit in the source, so
check pages, not code. Place figures with `[t]` or `[tbp]` (never bare `[h]`), size them to
the column or text width they need rather than the full page, and keep two floats from
landing back to back on one page with a sliver of text between them: move one to the next
section, combine them into one figure with panels, or let the smaller one sit in the text
with `\FloatBarrier` only where a section must end cleanly. A page that is two thirds
figure and one third blank, a heading orphaned at the foot of a page, or a caption
separated from its figure is a defect to fix before the report ships.

**Verification.** This is part of writing, done here, not handed to a worker. Compile
(`latexmk -pdf` or `pdflatex` twice with `bibtex`), fix every error, then look at every
page: `pdftoppm -r 50 -png paper.pdf "$TMPDIR/pages/p"` renders thumbnails cheap enough to
`read` several at once (into scratch, not the project: page images are not deliverables);
check them for figure sizes, page balance, blank regions, overfull lines, orphaned
headings and broken refs (`??`). `scripts/validate_format.py --file paper.pdf --venue "<venue>" --check-all` checks
page count, margins and font size against the venue's rules where it knows them. Run the
citations skill's `validate_bib.py` on the `.bib`. Re-read the abstract against the
results table.

## Style

- Precise verbs, concrete subjects: "the model reduced error by 12%" not "a reduction in
  error was observed". Active voice for what you did; passive where the agent is irrelevant.
- One idea per sentence; one point per paragraph, stated first.
- Define every symbol and acronym at first use; keep one term per concept throughout.
- Hedge to the evidence: "suggests" for a single study, "shows" for a replicated result,
  never "proves" for empirical work.
- No filler ("it is important to note"), no self-praise ("novel", "significant" without a
  test), no rhetorical questions.
- Numbers: consistent precision, units on every quantity, uncertainty on every estimate.

`references/writing-principles.md` expands each of these with examples;
`references/reporting-guidelines.md` lists the CONSORT, STROBE, PRISMA, ARRIVE and similar
checklists a venue may require; `references/figures-tables.md` covers table design.

## Venue styles

| Target | Read |
| --- | --- |
| Nature, Science and their families | `references/nature-science-style.md` |
| Cell Press | `references/cell-press-style.md` |
| Medical journals (NEJM, Lancet, JAMA, BMJ) | `references/medical-journal-styles.md` |
| Any journal's mechanics: lengths, abstract forms, reference styles | `references/journals-formatting.md` |
| NeurIPS, ICML, ICLR, ACL, COLM, AAAI | load `ml-paper-writing` instead |

## Responding to reviewers

Quote each comment, answer it directly, state the change and where it is (page, line,
section), and disagree with evidence when the reviewer is wrong. Never change a result to
please a review; change the text to make the result clearer.

## Before you hand it over

- The file compiles or renders and is linked in the answer.
- Every number in the text appears in a table, figure or output file with the same value.
- Every citation is resolved (citations skill) and every `\ref` resolves.
- The abstract's main result matches the results section.
- Open questions for the user are listed: missing evidence, choices made, venue rules not
  met.
