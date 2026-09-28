# Reference Adaptation and Non-Borrow Policy

## Core Rule

A reference figure provides design evidence, not target-paper facts.

Borrowable:

- layout skeleton;
- reader path;
- panel rhythm;
- module grouping style;
- abstraction level;
- stage-output visualization technique;
- callout strategy;
- evidence-card placement;
- icon style;
- arrow grammar;
- density/symbol discipline;
- style family.

Non-borrowable:

- model modules absent from the target paper;
- datasets;
- metrics;
- numeric results;
- method names;
- claims;
- equations/objectives;
- implementation details;
- paper-specific symbols or legends;
- author-specific visual logos.

## Candidate Requirements

Every Round-2 candidate that uses references must include `reference_adaptation_trace`:

- reference case ids;
- borrowed patterns;
- rejected facts;
- target-paper evidence anchors;
- adaptation risks;
- effect on paper-writing feedback.

## Validation Gate

The final fidelity report must include a reference-adaptation gate:

- no non-borrowable facts imported;
- target paper modules still come from target semantic graph;
- reference layout adaptation preserves target paper data/control dependencies;
- any changed module grouping is documented as non-contradictory reorganization.
