# Rewrite Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Substantively rewrite an existing manuscript from confirmed motivation, research
outputs, and a paragraph-level writing rationale matrix.

## Prerequisites

- `paper_spine_config.json`
- User draft from `draft_path`
- Research outputs: `research_dossier.md`, `exemplar_learning_dossier.md`,
  `style_profile.md`, `sota_gap_map.md`
- `citation_support_bank.md`
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
- `writing_rationale_matrix.md` - the rewrite plan
- `rewrite_matrix.md`
- `logic_transfer_audit.md`
- Revised manuscript

## Writing Rationale Matrix

| Row ID | Manuscript Unit | Original Problem or Planned Function | Motivation Link | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Change | Final Text Check |
|---|---|---|---|---|---|---|---|---|

First row: deeply justify the whole-work framework. Each subsequent row must
teach why this writing move is better.

Before drafting, read `references/writing-rationale-matrix.md` and apply its
full depth rules. Every non-trivial row must include concrete anchors from
confirmed motivation, SOTA/example pattern, target scene, evidence/citation,
and the planned text move. After drafting, every `Final Text Check` value must
start with `PASS` or `FAIL`; do not write vague notes such as "done" or only a
section location.

## Rewrite Rules

- Rewrite from the matrix, not by appending to old paragraphs.
- Preserve LaTeX commands, labels, citations, equations, figures, tables.
- Use `output_language` from config.
- Select citations sentence by sentence from `citation_support_bank.md`.
- `rewrite_matrix.md` maps original to final units, classifying each change.

For a deeper, literature-informed pass — motivation-thread extraction,
move-guided section rewrite, structural-coherence pass, and a numerical /
cross-section motivation audit — apply the staged method in
`references/round1-literature-revision.md`.

## Pre-LaTeX Gate

```bash
python scripts/integrity_audit.py paper_rewriting_output --markdown --write
python scripts/structured_review.py paper_rewriting_output --dispatch
```

After dispatch, launch three parallel review sub-agents per `review_prompts/dispatch.md`.
Validate independence with `structured_review.py --validate review_prompts`.
