# Rewrite Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Substantively rewrite an existing manuscript from confirmed motivation,
research outputs, and a compact evidence-aware writing plan.

## Prerequisites

- `paper_spine_config.json`
- User draft from `draft_path`
- Research outputs: `research_dossier.md`, `exemplar_learning_dossier.md`,
  `style_profile.md`, `sota_gap_map.md`
- `citation_support_bank.md`
- `confirmed_contribution.md` (user-confirmed and passing `contribution_check.py`)
- `confirmed_motivation.md`

If any prerequisite is missing, return to the owning stage.

## Humanize Tier

If `paper_spine_config.json` has `humanize_tier` set to `light`, `medium`, or
`heavy`, read `references/humanize.md` and apply tier-specific constraints
during all prose generation.

## Required Outputs

- `original_logic_map.md` - map the existing manuscript in order
- `evidence_bank.md`
- `section_blueprints.md`
- `writing_rationale_matrix.md` - strict-mode or user-requested rationale trace
- `results_validation.md` for journal, conference, and competition scenes
- `scientific_evidence_ledger.json` for journal, conference, and competition scenes
- `rewrite_matrix.md`
- `logic_transfer_audit.md`
- Revised manuscript

## Planning Depth

Balanced mode uses `section_blueprints.md`, the evidence ledger/results map, and
the Agent's own manuscript judgment. Do not create paragraph rows merely to fill
a matrix. Strict mode or an explicit trace request uses the matrix below.

Read `editorial-completeness.md`. Preserve or rebuild the full reader-facing
research arc rather than compressing the manuscript into a safer summary. The
Agent may depart from the old section structure when the contribution, venue,
and evidence support a better one; `tier` does not reduce manuscript scale.

## Writing Rationale Matrix (Strict / Optional)

| Row ID | Manuscript Unit | Original Problem or Planned Function | Contribution Promise / Claim ID | Motivation Alignment | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Change | Final Text Check |
|---|---|---|---|---|---|---|---|---|---|

First row: deeply justify the whole-work framework. Each subsequent row must
teach why this writing move is better.

When strict mode applies, read `references/writing-rationale-matrix.md` and apply its
full depth rules. Every non-trivial row must identify a contribution promise
and include concrete anchors from the aligned motivation, SOTA/example pattern,
target scene, evidence/citation, and the planned text move. For evidence-bearing
scenes, create and pass `results_validation.md` before drafting Results prose.
After drafting, every `Final Text Check` value must
start with `PASS` or `FAIL`; do not write vague notes such as "done" or only a
section location.

## Rewrite Rules

- Rewrite from the matrix, not by appending to old paragraphs.
- Preserve LaTeX commands, labels, citations, equations, figures, tables.
- Use `output_language` from config.
- Select citations sentence by sentence from `citation_support_bank.md`.
- `rewrite_matrix.md` maps original to final units, classifying each change.
- Read `references/assertive-scientific-writing.md`. State supported findings
  directly; put qualifications only where causal scope, generalization, or
  provenance genuinely changes.
- Use figure contracts and evidence maps as private scaffolding. Expand them
  into Results and Discussion that explain progression and meaning, rather than
  emitting a sequence of audited captions.

For a deeper, literature-informed pass — motivation-thread extraction,
move-guided section rewrite, structural-coherence pass, and a numerical /
cross-section motivation audit — apply the staged method in
`references/round1-literature-revision.md`.

## Pre-LaTeX Gate

```bash
python scripts/structured_review.py paper_rewriting_output --markdown --write
python scripts/integrity_audit.py paper_rewriting_output --markdown --write
```

Balanced mode performs one integrated, free-form editor synthesis and proceeds
after truth/claim-relevant defects are fixed and the manuscript has been revised
to complete its reader-facing arc. Strict mode launches three
independent reviewers, validates their outputs, synthesizes
`reviewer_audit.md`, and passes `reviewer_audit_check.py` before LaTeX.
