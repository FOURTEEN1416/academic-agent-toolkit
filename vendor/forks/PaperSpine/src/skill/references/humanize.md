# Authorial Voice Restoration

For the current public host workflow, use the saved preference and the method in
[assertive-scientific-writing.md](assertive-scientific-writing.md). The historical
Runner sequence below documents an older route; its frozen authority files,
receipts and hash-bound author confirmation are not prerequisites for normal
editing or independent review in the single current Skill.

This is the canonical PaperSpine playbook for the legacy `humanize` route.
The capability is **Authorial Voice Restoration**, not AI-detection evasion.

## Purpose and boundary

Restore the author's own scholarly voice after the contribution, claim/evidence
graph, terminology, and a reader-facing manuscript revision have been frozen.
Remove empty framing, mechanical paragraph roles, unsupported evaluative
language, false polish, and repeated scaffolding while preserving scientific
meaning.

Do not:

- promise a detector pass or report a fabricated AI percentage;
- optimize prose against an AI classifier or word blacklist;
- add errors, slang, rhetorical questions, first person, or sentence-length
  variation merely to look human;
- imitate another scholar without explicit authorization;
- use multi-hop translation or back-translation as the final rewrite;
- let a pattern count determine authorship or force a change.

The old `humanize_tier=light|medium|heavy` values remain compatibility switches
that enable this lane. They no longer select detector thresholds. New configs
should use `author_voice_restoration=standard|strict|off`.

## Placement in the workflow

```text
confirmed contribution + frozen claim/evidence/terminology
                        ↓
reader-facing manuscript draft + immutable original snapshot
                        ↓
author-voice profile (authorized corpus or explicit unavailable receipt)
                        ↓
claim/evidence/limitation reverse outline
                        ↓
clean-text no-op decision or minimum necessary rewrite
                        ↓
deterministic invariants + advisory pattern scan
                        ↓
independent semantic audit with veto authority
                        ↓
author confirmation bound to the revised SHA-256
                        ↓
independent editorial review
```

Apply voice restoration after prose exists. The independent reviewer should compare the actual original and revised text using the saved preference; missing historical author-voice receipts do not prevent that review.

## 1. Freeze authority before rewriting

Snapshot the current files that govern the revision, such as
`confirmed_contribution.md`, `scientific_evidence_ledger.json`, the terminology
source, and the current manuscript. Record their relative paths, purposes, and
SHA-256 values in `author_voice_revision.json.authority_files`.

Copy the pre-restoration manuscript to an immutable project-local path such as
`author_voice/original_manuscript.tex`. The revised file normally remains
`final_paper/main.tex`. Never overwrite the only original bytes.

## 2. Build the author-voice profile

Create `author_voice_profile.json` using
`references/contracts/author-voice-profile.schema.json`.

Only use the author's own or explicitly authorized text, preferably:

- prior papers written by the same author;
- proposals or thesis chapters;
- reviewer-response letters;
- research notes that reflect the author's real reasoning.

Snapshot authorized sources under `reference_materials/author_voice/` and bind
each to SHA-256 and `authorization=author_owned|explicitly_authorized`. Record
protected method names, variables, statistical terms, dataset names, and other
terminology whose identity must not drift.

If no authorized corpus is available, set `status=unavailable`, keep
`authorized_sources=[]`, state the reason, and proceed without imitating anyone.
That is an honest limitation, not a reason to borrow a famous writer's voice.

## 3. Decide no-op before rewrite

First ask whether a concrete reader-facing problem exists. A pattern match by
itself is not enough. Clear, accurate, section-appropriate text should be a
clean-text no-op even when it uses a common connector, repeated procedural
syntax, or low sentence-length variance.

For a no-op:

- set `mode=no_op`;
- keep original and revised bytes identical;
- keep `changes=[]`;
- record why the current prose already performs its section function;
- use `semantic_audit.audit_method=deterministic_identity` or an independent
  audit;
- reuse the author's existing preference and authorization; an unchanged passage does not require another hash-bound confirmation.

No-op is positive precision evidence. It is not a missed opportunity to lower
an AI score.

## 4. Rewrite from paragraph function, not surface synonyms

For each affected paragraph, recover four things from the frozen authorities:

1. the claim or question the paragraph owns;
2. the evidence that licenses it;
3. the limitation or alternative that changes interpretation;
4. the paragraph's relationship to the preceding and following units.

Hide the original sentence wording when necessary and rebuild from those
functions. Prefer deletion of empty framing over a synonym replacement. Every
change in `author_voice_revision.json.changes` must have source/revised locators,
a bounded reason, and an evidence anchor.

Apply section-aware rules:

- **Methods:** regular syntax and repeated structures are often correct. Keep
  terminology stable, subjects clear, and one name per concept. Do not force
  burstiness.
- **Results:** state observations directly, keep numbers and comparisons near
  their evidence, and avoid unsupported evaluation.
- **Discussion:** restore the author's prioritization, competing explanations,
  tradeoffs, counterexamples, and genuine limitations. Do not manufacture
  hesitation or confidence.
- **Introduction/Abstract:** delete generic importance framing and make the
  problem-gap-contribution relation specific to the frozen claim boundary.

Back-translation may be used only as a difference probe. Never auto-adopt its
wording. Return to the original claim whenever it exposes a meaning change.

## 5. Hard semantic invariants

Create `author_voice_revision.json` with
`references/contracts/author-voice-restoration.schema.json`. Run:

```bash
python scripts/author_voice_check.py paper_rewriting_output --markdown --write
```

The checker binds and compares:

- original and revised bytes/SHA-256;
- frozen claim/evidence/terminology authorities;
- numbers and units;
- citation keys;
- formulas;
- protected terms and proper names supplied by the profile;
- negation markers;
- causal/associational direction;
- modality, uncertainty, and claim-strength markers.

A deterministic difference is a signal to inspect the affected meaning. Repair genuine changes to numbers, attribution, negation, causal direction or warranted certainty; do not block an equivalent expression merely because marker counts differ. Pattern groups such as empty framing and process leakage remain advisory and never identify an author or require a rewrite by themselves.

## 6. Independent semantic audit and author confirmation

For `mode=rewrite`, a different Agent must compare the frozen original and
revised text without polishing it. The auditor has veto authority and must bind
its receipt to both hashes. All of these counts must be zero:

- `unsupported_new_claims`;
- `claim_strength_drift`;
- `causal_direction_changes`;
- `negation_changes`;
- `modality_uncertainty_changes`;
- `citation_meaning_changes`.

After independent semantic review, retain the current revision and its specific findings. Recheck the passages affected by further edits. Request author input only for a new substantive choice outside existing instructions; routine authorized edits and unchanged passages do not require fresh hash-bound approval.

## Outputs and gate

Required when the lane is enabled:

- `author_voice_profile.json`;
- `author_voice_revision.json`;
- `author_voice_receipt.json`;
- `author_voice_report.md`;
- immutable original manuscript snapshot and authorized corpus snapshots named
  by the contracts.

Gate:

```bash
python scripts/progress_check.py paper_rewriting_output --gate author_voice_restoration
```

The report includes original/revised hashes, change reasons, preserved
invariants, semantic-audit status, descriptive deviation from authorized author
text when available, unresolved diagnostic patterns, and author confirmation.
It explicitly reports `authorship inference=not_performed` and does not claim a
detector pass.

`humanize_check.py` remains a compatibility diagnostic for older artifacts. Its
D1-D5 observations are advisory and have no readiness authority.
