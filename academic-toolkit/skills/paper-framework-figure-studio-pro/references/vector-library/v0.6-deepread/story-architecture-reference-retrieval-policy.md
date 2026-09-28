# Story / Architecture Reference Retrieval Policy 鈥?v0.6 Deep-Read-backed Addendum

High-confidence retrieval must prefer reference cases whose source paper has a `complete` or `usable_with_gaps` deep-read record. A visual-only or non-deep-read reference can be used for Round 1 style mood only, not as a Round 2 architecture/story precedent.

# Story / Architecture Reference Retrieval Policy

## Purpose

Before generating candidates, retrieve reference figures that match the target paper by narrative and architecture. Good retrieval helps avoid generic diagrams and gives the composer concrete patterns for story flow, module grouping, evidence placement, and reviewer-first simplification.

## Query Construction

Build `retrieval_query_profile.json` from:

- target `paper_story_signature.json`;
- target `model_architecture_signature.json`;
- desired figure subtype;
- paper slot;
- main stage outputs to show;
- user preference profile;
- evidence usage plan;
- vector/PPT constraints.

## Retrieval Priority

Use this priority order:

1. Same reader question and similar architecture topology.
2. Same module-role sequence even if domain/style differs.
3. Same story arc and figure role.
4. Same evidence treatment or result integration need.
5. Same visual style or user preference.

Style-only matches are useful for Round 1 mood, but they must not drive Round 2 model-essence candidates.

## Output Groups

Return reference cases in groups:

- `direct_story_architecture_match`
- `architecture_match_style_different`
- `story_match_architecture_different`
- `visual_style_match_only`
- `evidence_treatment_reference`
- `do_not_use_due_to_mismatch`

## Adaptation Notes

For each reference, write:

- why it matches;
- what can be borrowed;
- what must not be borrowed;
- how to adapt it to the target paper;
- whether it is useful for Round 1, Round 2, final vector construction, or caption strategy;
- risks.
