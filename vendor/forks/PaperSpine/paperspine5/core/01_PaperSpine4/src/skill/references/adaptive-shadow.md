# Adaptive Research and Obligation Shadow

This is an opt-in migration surface for runtime learning. It is not a domain
profile and is not part of the canonical completion gate in interface version
`0.1-shadow`.

## Boundary

PaperSpine must not encode biology, AI, medicine, humanities, or any other
field's preferences as permanent skill rules. Direction-specific advice must be
learned at runtime by a direction-research Agent; venue-specific obligations
must be learned by a target-research Agent from authority-bearing sources. The
shadow layer stores only general evidence, authority, review, and state-
transition contracts.

Every runtime context requires:

- `context_id`
- `object_kind`
- `destination_channel`
- `as_of`

Venue, year, track, article type, and workflow stage are optional until they
actually apply. Do not invent them merely to satisfy a form.

## Inputs

Create a request conforming to
`references/contracts/adaptive-shadow-request.schema.json` and validate it with:

```bash
python scripts/adaptive_shadow.py adaptive_shadow_request.json \
  --project-root paper_rewriting_output \
  --output adaptive_shadow_result.json
```

The request contains:

1. hash-bound `SourceReceipt` records;
2. independent coverage receipts for target-policy research and direction
   research, including search frontier, stopping reason, residual risk, and a
   deterministic or independent challenger; direction coverage also requires
   an independent direct-competitor omission challenge;
3. a closed, non-Turing-complete `Obligation IR v0` using only `exists`,
   `absent`, `truthy`, `equals`, and `in_set`;
4. exactly one claim-bearing surface and its current artifact hash;
5. an atom-level retention receipt with every omission explained;
6. a current, hash-bound asset inventory identifying the selected candidate and why it is appropriate; recency alone must not override a valid user choice or a scientifically stronger existing figure;
7. a zero-context primary-surface independent review bound to that same hash;
8. a v1 legacy receipt. Legacy FAIL/BLOCKED is preserved, while legacy PASS is
   visible but tainted and has no edge to new READY;
9. for the opt-in shadow experiment, a bounded quality-revision receipt documenting that experiment's configured limit; the historical one-round limit does not cap normal host correction and re-review of the paper;
10. optional figure decisions. Keep a hero, mechanism, model or core figure when its scientific purpose, evidence, readability and role in the paper are adequate; record a competitive delta only when the paper actually makes and supports that comparison.

Hard mandatory/prohibited obligations may be promoted only from an official
machine-parsed structure or an independent verifier receipt. Same-model context
separation may create candidates or advisory hypotheses, but never hard proof.
Legal, ethical, jurisdictional, clinical, and institutional authority still
belongs to a qualified human or institution when applicable.

## Outcome and authority

The only green outcome is `CLAIM_SURFACE_AUDITED`. It means one identified,
hash-bound claim surface passed the shadow checks. It never means:

- the manuscript is complete;
- a delivery or submission bundle is READY;
- a target venue has accepted the work;
- an external action is authorized.

`manuscript_ready`, `delivery_ready`, `submission_ready`, and
`external_action_authorized` are hard-coded false in every shadow result. The
canonical PaperSpine gates remain authoritative.

Truth/authority/permission, process assurance, and quality optimization are a
noncompensatory vector: one red dimension cannot be offset by another green
dimension.

## Immutable revisions

For a migration experiment, append an immutable revision and move `CURRENT`
with compare-and-swap semantics:

```bash
python scripts/adaptive_shadow.py adaptive_shadow_request.json \
  --project-root paper_rewriting_output \
  --store adaptive_shadow_store \
  --expected-current NONE
```

Use the prior revision ID instead of `NONE` for later commits. An existing
revision ID is never overwritten. A stale expected parent is blocked rather
than silently changing `CURRENT`.

## Activation

Run this layer only when the user asks for the adaptive experiment or the run is
explicitly configured with `adaptive_shadow=on`. In `off`/missing mode, do not
create these artifacts and do not add bureaucracy to the normal workflow. In
this shadow version, its result is observational and cannot change
`progress_check.py` completion or publication-cycle authority.

## Maximum licensed claim

The current implementation may be described only as:

> A deterministic, test-covered adaptive contract preview and shadow audit for
> one hash-bound claim surface, with domain-neutral source/authority receipts,
> closed obligation predicates, bounded revision, and fail-closed authority.

It has not earned claims of universal research coverage, excellent-paper
generation, direct submission readiness, field/venue quality, acceptance-rate
improvement, or whole-manuscript adaptive readiness. Synthetic contract tests
are conformance evidence, not behavioral evidence that the research or writing
is high quality. Those claims remain prohibited until the M4/M5 evidence and
human/independent-model calibration defined by the project plan exist.
