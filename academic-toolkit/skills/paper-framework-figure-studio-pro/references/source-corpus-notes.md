# Source Corpus Notes

This skill uses the project-local full-feasible diagram corpus.

The underlying extraction artifacts are summarized in this package rather than bundled as thousands of PDFs. The build used the project-local corpus summarized here.

## Coverage Summary

- Corpus processing scope: `all_accessible_relevant_pdfs`.
- Candidate PDF count: 7,631.
- Accessible PDF count: 7,631.
- Processed PDF count: 7,631.
- Skipped PDF count: 0.
- Skipped reasons: none recorded.
- Verified official oral PDFs: 3,356.
- Supplemental local PDFs: 4,275.
- Figure captions extracted: 146,071.
- Diagram-relevant captions: 119,534.
- Multi-label figure records: 93,088.
- Representative rendered pages: 96, audit aids only.

## Framework-Relevant Evidence

| Label | Caption Count | Paper Count |
|---|---:|---:|
| method_framework | 16,565 | 5,267 |
| architecture | 14,651 | 4,256 |
| pipeline_process | 28,981 | 5,878 |
| agent_workflow | 16,271 | 2,228 |
| mechanism_intuition | 42,578 | 5,947 |
| case_walkthrough | 35,822 | 6,465 |

## Classification Policy

Classification is multi-label. A single paper or diagram may simultaneously be a method framework, pipeline, architecture, agent workflow, mechanism diagram, evidence board, or case walkthrough. Do not force exclusive labels during routing. First collect all applicable labels, then choose the primary production subtype for the user's target figure.

## Sufficiency

- Evidence sufficiency level: `full_taxonomy`.
- Lock grade: `production_grade`.
- Lock basis: `full_taxonomy`.

Known limitations:

- Evidence extraction used automated PDF text/caption extraction, title/caption multi-label classification, and representative rendered-page inspection; it is not exhaustive manual annotation of every figure.
- Supplemental local PDFs support taxonomy breadth but are not counted as verified official oral PDFs.
- For very narrow venue/domain styling, ask for sample images or refresh with closer domain papers.
