# Round 1 / Round 2 Focus Policy

This policy aligns with the original project source idea that global exploration is divergent and local refinement is precise, but upgrades the process for preference references, result evidence, and reviewer-first comprehension.

## Round 1: Diverse Global Exploration

Round 1 is about breadth. It should produce visually and structurally different directions, not polished final designs.

### Primary Goals

- Explore 8 different visual sentences by default in the v3.1.6 first round.
- Explore different layout silhouettes: pipeline, central core, swimlane, loop, evidence board, zoom callout, storyboard, matrix/taxonomy, hybrid.
- Explore different reader paths: left-to-right, top-to-bottom, cyclic, inside-out, example-first, mechanism-first, evidence-first.
- Explore different module grouping hypotheses.
- Explore how optional result evidence could be placed without crowding.
- Explore user preference styles without collapsing diversity.

### What Round 1 Should NOT Focus On

- exact final labels;
- exact formula syntax;
- all method substeps;
- final vector coordinates;
- final icon identities;
- full result table replication;
- photo-realistic/painterly polish;
- dense poster-like explanations.

### Preference Handling in Round 1

If `user_preference_profile.json` exists, use it as an exploration dimension:

- default: 4-5 candidates stay broad and unbiased; 1-2 candidates are preference-informed;
- if the user explicitly locks a style, keep all candidates within that style envelope but vary structure and reader path;
- never let style preference override paper facts.

### Experimental Evidence in Round 1

If `result_evidence_record.json` exists, Round 1 may test evidence placement alternatives:

- evidence as a small side card;
- evidence as output-stage metric badge;
- evidence as before/after qualitative tile;
- evidence as caption-only reference;
- evidence omitted from image body.

Round 1 should not require exact chart reconstruction.

## Round 2: Reviewer-First Local Refinement

Round 2 is about explaining the paper essence accurately and cleanly.

### Primary Goals

- Make the model/method essence understandable without reading the full paper.
- Show input, core mechanism, major stage outputs, and final output.
- Keep paper facts correct while allowing clearer visual grouping.
- Use short labels and visible artifacts to distinguish what each step produces.
- Use necessary formulas or symbols only if they reduce ambiguity.
- Make result evidence support a claim without becoming a mini-poster.
- Be vector-first and scene-spec-ready.

### Allowed Reorganization

Round 2 may merge, split, rename, or reorder visual modules if:

- it does not change paper semantics;
- it preserves dependencies and input/output meaning;
- it makes the method clearer to reviewers;
- it records terminology mapping and evidence anchors;
- it generates writing feedback for the manuscript.

### Forbidden in Round 2

- invented modules or claims;
- fake experimental values;
- too many equations or symbols;
- raw poster-like result panels;
- dense text blocks;
- tiny icons used as decorative noise;
- flows that contradict algorithm/model dependencies;
- visual detail that cannot be rebuilt as SVG/PPT.
