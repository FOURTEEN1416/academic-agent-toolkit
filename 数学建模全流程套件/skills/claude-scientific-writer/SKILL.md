---
name: scientific-writer
description: "Comprehensive scientific writing toolkit with 15 modules for academic and clinical authorship. Use whenever the user drafts, revises, peer-reviews, or submits a manuscript, grant, poster, slide deck, clinical report, treatment plan, literature review, hypothesis paper, or market research report. Triggers include any mention of peer review, manuscript, response to reviewers, IMRaD, abstract, citations, BibTeX, Vancouver/APA/AMA, CONSORT, STROBE, PRISMA, TRIPOD, CARE, ICH-E3, SOAP, case report, clinical trial report, ScholarEval, NSF/NIH/DOE/DARPA grants, Nature/Science/Cell/NEJM/Lancet/NeurIPS/ICML formatting, beamerposter, tikzposter, conference poster, research slides, hypothesis generation, treatment plan, or clinical decision support."
license: "MIT"
---

# Scientific Writer

A consolidated scientific writing toolkit covering 15 modules: from manuscript drafting through peer review, citation management, clinical documentation, grant proposals, posters, slides, and beyond. Each module is self-contained as a reference file under `references/`. Read only the module(s) you need for the current task.

## How to use this skill

This SKILL.md is a **router**. It does three things:

1. Tells you **which reference file to load** for the user's task (see "Module map" below).
2. Defines **global rules** that apply across all modules (writing style, API substitutions, integration with Claude.ai's native tools).
3. Points you to **assets and scripts** for templates, checklists, and helper code.

**Workflow:** Identify the task → match it to a module in the table below → `view` the corresponding `references/<module>.md` → follow that module's instructions → use any listed assets/scripts as needed.

For complex tasks spanning multiple modules (e.g., write a Nature paper + peer-review it + format citations), load each module's reference file in turn.

---

## Module map

| User intent / trigger | Load reference file | Key assets |
|---|---|---|
| Drafting or revising a manuscript section (abstract, introduction, methods, results, discussion); IMRaD structure; reporting guideline checklists (CONSORT, STROBE, PRISMA, TRIPOD, ARRIVE, SPIRIT) | `references/scientific-writing.md` | `assets/scientific-writing/scientific_report.sty`, `scientific_report_template.tex` |
| Peer-reviewing a manuscript; structured reviewer comments; methodology critique; reporting-standard verification | `references/peer-review.md` | — |
| Formatting citations and BibTeX; verifying DOI/PMID metadata; switching between APA/AMA/Vancouver/Chicago/IEEE styles | `references/citation-management.md` | `assets/citation-management/bibtex_template.bib`, `citation_checklist.md`; `scripts/citation-management/*.py` |
| Conducting a systematic or narrative literature review; PRISMA flow; database search strategies | `references/literature-review.md` | `assets/literature-review/review_template.md`; `scripts/literature-review/*.py` |
| Critically appraising study rigor; evaluating bias, confounding, statistical validity; GRADE/Cochrane ROB | `references/scientific-critical-thinking.md` | — |
| Generating testable hypotheses; competing-explanations analysis; experimental predictions | `references/hypothesis-generation.md` | `assets/hypothesis-generation/` (templates) |
| Targeting a specific journal or conference (Nature, Science, Cell, NEJM, Lancet, NeurIPS, ICML, IEEE, ACM, etc.) — venue-specific style, abstract format, reviewer expectations, LaTeX templates | `references/venue-templates.md` | `assets/venue-templates/` (LaTeX templates per venue) |
| Applying ScholarEval framework (8-dimension manuscript scoring) | `references/scholar-evaluation.md` | `scripts/scholar-evaluation/calculate_scores.py` |
| Writing NSF, NIH, DOE, or DARPA grant proposals; broader impacts; budget justification | `references/research-grants.md` | `assets/research-grants/` (templates) |
| Clinical case reports (CARE), diagnostic reports (radiology/pathology/lab), clinical trial reports (ICH-E3, CSR, SAE), patient documentation (SOAP, H&P, discharge summary, consult note) | `references/clinical-reports.md` | `assets/clinical-reports/*.md` (11 templates), HIPAA + quality checklists; `scripts/clinical-reports/*.py` |
| Clinical decision support documents; biomarker-stratified cohort analyses; treatment recommendation logic | `references/clinical-decision-support.md` | `assets/clinical-decision-support/` (templates); `scripts/clinical-decision-support/*.py` |
| Patient-specific treatment plans (medical, rehab, mental health, chronic disease); LaTeX/PDF output | `references/treatment-plans.md` | `assets/treatment-plans/` (templates); `scripts/treatment-plans/*.py` |
| LaTeX research posters (beamerposter, tikzposter, baposter); A0/A1 conference posters | `references/latex-posters.md` | `assets/latex-posters/` (templates); `scripts/latex-posters/review_poster.sh` |
| Research presentation decks (Beamer, conference talks, thesis defense, seminar) | `references/scientific-slides.md` | `assets/scientific-slides/` (templates); `scripts/scientific-slides/*.py` |
| Long-form market research reports in McKinsey/BCG/Gartner style | `references/market-research-reports.md` | `assets/market-research-reports/` (templates) |

---

## Global rules

### 1. API-dependent functionality has been removed

Some modules originally depended on several external APIs (Perplexity Sonar Pro, Parallel CLI, Google Nano Banana Pro, FLUX, OpenRouter, Gemini direct calls). **Those modules and bash invocations have been stripped.** Whenever a reference file contains a command like:

- `python scripts/generate_schematic.py "..."` → instead call Claude.ai's `image_search` tool, or generate an SVG diagram inline using the visualizer tool, or describe the figure for the user to produce externally.
- `python scripts/generate_image.py "..."` → same as above; use `image_search` or external generation.
- `python scripts/research_lookup.py "..."` or any "research-lookup skill" reference → use Claude.ai's `web_search` and `web_fetch` tools.
- `parallel-cli` invocations → use `web_search` / `web_fetch`.
- `markitdown` references → Claude.ai already handles common file formats (PDF, DOCX, PPTX, XLSX) natively via the file-reading skill; route those tasks there.

**Treat every figure-generation or research-lookup bash command in the reference files as a placeholder for the equivalent Claude.ai-native action.** Do not error out, do not tell the user to install the original CLI — silently substitute.

### 2. Writing style invariants (apply to all manuscript modules)

These come from the user's standing preferences and are non-negotiable for academic deliverables:

- **Neutral, formal academic tone.** Passive voice is acceptable and often preferred in methods/results.
- **No em dashes (—).** Use commas, semicolons, parentheses, or sentence breaks instead.
- **No hedging filler.** Avoid phrases like "in some cases," "it is widely believed," "many studies suggest" without citation.
- **No invented data.** Every statistic, sample size, p-value, or numeric claim must come from a verifiable source. If unknown, write `[VALUE TO BE INSERTED]`.
- **Medications written explicitly** (drug name + dose + route + frequency) — never abbreviate or omit.
- **Retrospective designs labeled as retrospective cohort** (or retrospective case series, etc.) — never call retrospective work "cohort study" without the qualifier.
- **Full paragraphs, never bullet points** in submitted manuscripts. Bullets are for outlining only.

### 3. Bilingual deliverable convention

The user works bilingually:
- **Turkish** for meta-discussion, internal drafts, reviewer-comment scratchpads.
- **English** for final manuscripts, cover letters, and professional correspondence to journals.
- For peer-review reports and reviewer-response letters, **produce both TR and EN versions** by default unless told otherwise.

### 4. File creation defaults

- Final deliverables (manuscript, cover letter, response-to-reviewers, treatment plan, poster) → produce a `.docx` or `.pdf` file via the appropriate Claude.ai skill (docx, pdf, pptx, xlsx as relevant).
- Drafts in chat are markdown.
- LaTeX output (posters, venue templates, scientific reports) → write `.tex` files and either provide them directly or build a PDF if the LaTeX toolchain is available.

### 5. Reading reference files efficiently

Reference files are large (50K–200K each). **Do not read them in full unless needed.** Use targeted `view` ranges:

- For a specific reporting guideline (e.g., CONSORT) → `view` the file and then `grep`-style scan, or jump to a known line range.
- For a specific journal template (e.g., Nature) → search for the journal name within `references/venue-templates.md`.
- For a specific clinical report type (e.g., CARE case report) → search within `references/clinical-reports.md`.

If unsure where to look, first `view` the table of contents (top 100 lines) of the reference file to orient.

---

## Common multi-module workflows

**Manuscript submission workflow** (typical):
1. `references/scientific-writing.md` for IMRaD structure and section drafting.
2. `references/venue-templates.md` for the target journal's style and LaTeX template.
3. `references/citation-management.md` to validate references and produce BibTeX.
4. `references/scientific-critical-thinking.md` as a self-review pass before submission.

**Peer-review report workflow**:
1. `references/peer-review.md` for the structured review template.
2. `references/scholar-evaluation.md` if quantitative scoring is required.
3. `references/scientific-critical-thinking.md` for methodology/statistical critique depth.
4. Produce TR + EN versions (see Global Rule 3).

**Response-to-reviewers workflow**:
1. `references/scientific-writing.md` (revision section) for response-letter structure.
2. `references/citation-management.md` if new references are added.
3. Apply tracked changes directly in DOCX (use the docx skill).

**Clinical case report workflow**:
1. `references/clinical-reports.md` (CARE-guideline section) for structure.
2. `assets/clinical-reports/case_report_template.md` as the starting template.
3. `assets/clinical-reports/hipaa_compliance_checklist.md` and `quality_checklist.md` before finalizing.
4. `scripts/clinical-reports/check_deidentification.py` to verify PHI removal.

**Conference poster workflow**:
1. `references/latex-posters.md` for layout principles.
2. `assets/latex-posters/` for the template (beamerposter / tikzposter / baposter).
3. `scripts/latex-posters/review_poster.sh` for compilation and review.

**Grant proposal workflow**:
1. `references/research-grants.md` for the target agency (NSF/NIH/DOE/DARPA).
2. `references/scientific-writing.md` for narrative sections.
3. `references/hypothesis-generation.md` for specific aims.
4. `assets/research-grants/` for agency-specific templates.

---

## Directory layout

```
scientific-writer/
├── SKILL.md                              ← this file (router)
├── references/                           ← module content (load on demand)
│   ├── scientific-writing.md
│   ├── peer-review.md
│   ├── citation-management.md
│   ├── literature-review.md
│   ├── scientific-critical-thinking.md
│   ├── hypothesis-generation.md
│   ├── venue-templates.md
│   ├── scholar-evaluation.md
│   ├── research-grants.md
│   ├── clinical-reports.md
│   ├── clinical-decision-support.md
│   ├── treatment-plans.md
│   ├── latex-posters.md
│   ├── scientific-slides.md
│   └── market-research-reports.md
├── assets/                               ← templates, checklists, .sty files, .tex templates
│   └── <module>/...
└── scripts/                              ← Python/bash helpers (no API keys required)
    └── <module>/...
```

---

## Notes

This Claude.ai package consolidates 15 modules for scientific authorship and removes API-dependent functionality (research-lookup via Perplexity/Parallel, image generation via Nano Banana / FLUX / Gemini, paper-2-web, parallel-web, infographics) along with `markitdown` and `document-skills` which Claude.ai provides natively.
