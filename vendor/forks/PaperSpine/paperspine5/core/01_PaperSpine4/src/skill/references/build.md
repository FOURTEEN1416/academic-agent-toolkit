# Build Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Build a manuscript from materials when no real draft exists yet. Shares the
same research, motivation, and rationale logic as the rewrite stage.

## Prerequisites

- `paper_spine_config.json`
- `materials_dir`
- Research outputs
- `citation_support_bank.md`
- `confirmed_contribution.md` (user-confirmed and passing `contribution_check.py`)
- `confirmed_motivation.md`

## First Pass

```bash
python scripts/material_inventory.py <materials_dir> --output-dir paper_rewriting_output
```

Create `source_inventory.md` before making claims.

## Humanize Tier

If `humanize_tier` is set to `light`, `medium`, or `heavy`, read
`references/humanize.md` and apply tier-specific constraints.

## Required Outputs

- `source_inventory.md`, `evidence_bank.md`, `figure_asset_map.md`, `claim_register.md`
- `section_blueprints.md`; `writing_rationale_matrix.md` in strict mode or when requested
- `results_validation.md` for journal, conference, and competition scenes
- `scientific_evidence_ledger.json` for journal, conference, and competition scenes
- Manuscript draft
- `final_paper/main.tex`, `latex_report.md`, `final_artifact_manifest.md`

## Planning Depth

Balanced mode lets the Agent design the manuscript from `section_blueprints.md`,
primary evidence links, and the results map. Use the matrix only for strict mode
or a user-requested paragraph-level rationale trace.

Read `editorial-completeness.md`. The blueprint is scaffolding, not the paper:
develop each evidence or figure unit into a complete reader-facing argument and
preserve a full ending appropriate to the venue. Research `tier` never changes
this manuscript-scale commitment.

## Writing Rationale Matrix (Strict / Optional)

| Row ID | Manuscript Unit | Planned Function | Contribution Promise / Claim ID | Motivation Alignment | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Text Move | Final Text Check |
|---|---|---|---|---|---|---|---|---|---|

When strict mode applies, read `references/writing-rationale-matrix.md` and apply its
full depth rules. Every non-trivial row must identify a contribution promise
and include concrete anchors from the aligned motivation, SOTA/example pattern,
target scene, evidence/citation, and the planned text move. For evidence-bearing
scenes, create and pass `results_validation.md` before drafting Results prose.
The first row must justify the whole-work framework.
After drafting, every `Final Text Check` value must start with `PASS` or
`FAIL`; do not write vague notes such as "done" or only a section location.

## Build Rules

- Treat images as potential figure assets.
- Do not fabricate missing experiments or results.
- Quote paths with spaces or non-ASCII chars.
- Use `output_language` from config.
- Select citations sentence by sentence.
- Build and validate the S/C/N/M/O/R ledger before drafting Results; update it
  after analysis changes rather than editing result prose alone.
- Let the Agent choose section names, paragraph structure, and revision order.
  Use the contribution and reader questions as guidance; do not turn planning
  rows, section counts, or word ranges into prose templates.
- Draft from `section_blueprints.md` / `writing_rationale_matrix.md`, but keep
  their scaffolding internal: the manuscript body must never name supervisors,
  reviewers, review comments, an earlier draft, or narrate that the paper was
  reorganized to address feedback, and must never transcribe an `A -> B -> C`
  planning throughline as prose. `integrity_audit.py` hard-fails this.
- Cite with `\cite{key}` linked to a bibliography; never type literal `[1]` text.
- Read `references/assertive-scientific-writing.md`; evidence precision should
  support a clear voice, not produce repetitive defensive hedging.
- Run integrity audit + structured review before LaTeX. In balanced mode,
  `structured_review.py --write` creates the brief; the Agent must replace its
  guidance with a real editor synthesis and revise the paper before setting
  `Review status: PASS`. Strict mode additionally requires three independent
  reviews and `reviewer_audit.md`.
- Apply the last language pass, then run the publication-surface scrub; internal
  evidence IDs stay in the ledger and must not leak into the manuscript.
- Build final LaTeX under `final_paper/`.
