# Authorial Voice Restoration Evaluation

This file replaces detector-threshold calibration for the legacy `humanize`
route. AI-detector scores may be recorded as secondary observations when a user
already has them, but they are never acceptance gates and never justify a
revision by themselves.

## Primary evaluation set

Use frozen train/validation/test manuscripts and include all of these controls:

- mechanically polished prose with known empty framing and paragraph-template
  defects;
- revisions containing seeded number, unit, citation, formula, protected-term,
  negation, causality, modality, and claim-strength drift;
- unsupported-new-claim mutations;
- section-specific Methods, Results, and Discussion cases;
- strong human-authored text that should remain a clean-text no-op;
- authorized and unavailable author-corpus cases;
- stale hash, non-independent audit, and stale author-confirmation cases.

## Hard metrics

- number/unit/citation/formula/protected-term drift: 0;
- negation/causal direction/modality/claim-strength drift: 0;
- unsupported new claims: 0;
- stale authority, audit, or author-confirmation false clears: 0;
- false rewrite rate on clean-text no-op controls;
- author blind preference for revised versus original;
- independent domain-expert judgment of clarity and scientific fidelity;
- wall time, model tokens/cost when available, and author-review time.

Pattern precision/recall may be measured for individual diagnostic groups, but
pattern density is not an authorship label. Record section role so standard
Methods repetition is not counted as a defect by default.

## Optional detector observation

If a user supplies an external detector result, record platform, date,
language, discipline, document hash, exact revision hash, and the platform's
own uncertainty. Never optimize thresholds from one result, promise transfer to
another platform, or describe the detector as proof of authorship.

## Adoption rule

Adopt a new rule only when it improves held-out clarity/voice preference or
repair precision without any semantic-invariant regression and without
increasing the clean-text false-rewrite rate. A lower detector score alone is
insufficient.
