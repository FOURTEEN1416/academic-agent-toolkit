# S3 Preference-Carryover And Formal Local-Essence Candidate Policy v3.2.15f

This policy is paper-agnostic. It applies when the S3-DIRECTION-SELECT user prompt names one or more preferred first-round/S2 candidate IDs as a preference signal.

## Core Rule

If S3 receives explicit user-preferred first-round candidate IDs, S3 must record them as a machine-readable `preference_carryover_contract` in the S3 direction record. S4 must preserve them in the formal/S5 candidate matrix, subject to the absolute v3.2.15f maximum of two second-round schemes.

The preference signal is not an automatic winner. S3 still selects direction by source evidence, issue-ledger findings, and figure-contract quality. Once user preference IDs are recorded, S4 must not collapse them into a vague narrative such as "inspired by prior candidates". They must become explicit dominant source bindings for second-round formal candidates or trigger a recorded S4 repair/replan/narrowing decision if the two-candidate cap cannot cover all active pairs.

## Required S3 Recording

S3 must record, without hard-coded IDs or counts:

```json
{
  "preference_carryover_contract": {
    "applies": true,
    "source_stage": "S2-SKETCH-EXPLORE",
    "preferred_source_candidate_ids": ["<ids from user prompt>"],
    "carryover_mode": "dominant_local_essence_candidates_required",
    "style_coverage_rule": "for every active S5 style/treatment group, at least one formal candidate must be user-preference-led when feasible within two candidates",
    "individual_preference_coverage_rule": "each preferred source id must lead at least one formal candidate for every active S5 style/treatment family; keep total S5 second-round schemes <= 2; repair/replan/narrow or request user trade-off if coverage cannot fit"
  }
}
```

The field names may be embedded in a larger direction record, but the preferred IDs and the carryover rules must remain machine-readable.

## Required S4/S5 Matrix Behavior

When the S3 carryover contract applies, S4 must generate the S5 formal candidate matrix so that:

1. Every style/treatment group scheduled for S5 has at least one candidate row marked as `user_preference_led_local_essence` or an equivalent machine-readable preference-led mode when feasible within two rows.
2. The preference-led row for each style/treatment group includes a `dominant_source_candidate_ids` or equivalent field whose values intersect the S3 `preferred_source_candidate_ids`.
3. Across the whole S5 matrix, every preferred source ID appears as a dominant source at least once when the two-candidate budget permits.
4. If the number of style groups and preferred IDs exceeds two, S4 must not expand the matrix. It must repair/replan, narrow the active style-slot/preference allocation, or ask the user for a trade-off before S5 handoff.
5. A hybrid candidate may be valid only if the preferred source remains dominant for that row; a generic hybrid with the preferred ID listed only as weak inspiration does not satisfy this policy.

## Prompt-Package Obligations

Every preference-led formal candidate prompt must contain a compact, paper-neutral provenance line, for example:

```text
Preference-led local essence: preserve the dominant structural strengths of source candidate <ID(s)> while repairing its recorded S2/S3 issues and following the S4 source-grounded prompt contract.
```

This line is a provenance/control instruction, not a request to copy pixels or imitate the original generated image exactly.

## Forbidden Behavior

Do not:

- ignore explicit user-preferred S2 IDs after S3;
- represent user preference only as a scoring bonus while producing no preference-led formal candidate;
- create only one preference-led candidate when multiple active S5 styles/treatments are scheduled and the two-candidate cap can cover them;
- create a third S5 candidate;
- use hard-coded candidate IDs, image counts, paper names, model names, dataset names, or task-specific modules;
- copy the first-round image pixel-for-pixel, or preserve its known defects without repair;
- override source-grounded evidence constraints or checkpoint integrity gates.

## Validation

S4 close must run a generic preference-carryover guard when S3 recorded preferences. The guard must derive preferred IDs, style groups, and candidate rows from S3/S4/S5 state files and prompt-index artifacts, not from fixed candidate-ID or image-count assumptions.
