# Rewrite Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Substantively rewrite an existing manuscript from the confirmed motivation and
contribution choice, research outputs, and an evidence-aware writing plan.

## Prerequisites

- `paper_spine_config.json`
- User draft from `draft_path`
- Research outputs: `research_dossier.md`, `exemplar_learning_dossier.md`,
  `style_profile.md`, `sota_gap_map.md`
- `citation_support_bank.md`
- `confirmed_motivation.md`

Reuse this task's valid configuration, choices, source evidence and learning
notes. If a substantive prerequisite is missing, resolve that specific gap and
return to the owning stage; the absence of a historical filename alone does not
send the workflow back to an old stage.

## Humanize Tier

If `paper_spine_config.json` has `humanize_tier` set to `light`, `medium`, or
`heavy`, follow the `spine-humanize` skill and apply its tier-specific
constraints during all prose generation. Preserve the prior draft and retain
already-clear text; compare revised meaning, terminology, evidence and claim
strength rather than chasing detector or rhythm targets.

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

- Rewrite from the applicable evidence-aware plan, not by appending to old
  paragraphs. Preserve valid passages and make the changes the actual problem
  needs rather than appending generic prose.
- Preserve LaTeX commands, labels, citations, equations, figures, tables.
- Use `output_language` from config.
- Select citations sentence by sentence from `citation_support_bank.md`.
- `rewrite_matrix.md` maps original to final units, classifying each change.
- State supported findings directly; add qualifications only where causal
  scope, generalization, or provenance genuinely changes. A hedged claim
  repeated in every sentence is not rigor.
- Use figure/evidence planning notes as private scaffolding: expand them into
  Results and Discussion prose that explains progression and meaning, rather
  than emitting a sequence of audited captions.

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

Review must assess the actual revised prose, evidence and rendered outputs —
pagination and Word fidelity can only be judged after rendering, never from a
pre-LaTeX approval chain alone. Revise affected passages and outputs in the
same task, reusing valid unaffected work, and report scientific, editorial,
format and submission limitations separately.
