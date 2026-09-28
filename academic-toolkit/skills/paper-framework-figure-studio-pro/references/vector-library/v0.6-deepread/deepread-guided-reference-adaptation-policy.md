# Deep-Read Guided Reference Adaptation Policy

## Purpose

Skill B should not adapt a reference figure merely because it looks good. It should adapt reference cases whose source papers have been deep-read and whose story/architecture/claim-evidence logic matches the target paper.

## Retrieval Inputs

Use:

- target deep-read report and structured records;
- target paper story signature;
- target model architecture signature;
- reference case cards;
- reference paper deep-read status;
- figure/table deep-read index;
- visual communication audit;
- user preference profile;
- result evidence records.

## Adaptation Plan Fields

For each retrieved reference case, write:

- `source_paper_summary`: one-sentence source paper story;
- `source_figure_role`: what the reference figure did in its paper;
- `match_reason`: story / architecture / evidence / style / layout;
- `borrowable_patterns`;
- `non_borrowable_facts`;
- `target_paper_evidence_supporting_adaptation`;
- `adaptation_for_round1`;
- `adaptation_for_round2`;
- `vectorization_risk`;
- `caption_or_writing_feedback`.

## Hard Gates

- Reference case without deep-read record cannot drive Round 2 structure.
- Style-only reference can affect mood, palette, icon style, or density, but not module flow.
- Reference facts cannot enter the target figure unless independently grounded in the target paper.
- If a reference case suggests a clearer module grouping than the target manuscript, mark it as writing feedback, not as a fact change.
