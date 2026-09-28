# Preference-Led Second-Round Coverage Policy v3.2.15f

This policy is paper-agnostic. It applies when S3 receives or records explicit user preference signals for one or more first-round S2 candidate IDs.

## Core Rule

When S3 records user-preferred first-round candidate IDs, S4 must preserve those preferences as second-round coverage obligations, but v3.2.15f keeps the S5 prompt-index fixed at exactly two candidates: `F01` and `F02`.

For every S3-recorded preferred first-round candidate ID and every S4-declared active second-round style/treatment slot, S4 must try to include at least one S5 candidate whose role is a local-essence transfer led by that preferred first-round candidate. The active preference/style pair set must be feasible within two S5 candidates. If it is not feasible, S4 must repair, replan, narrow the active style slots, or ask the user for a trade-off before S5 handoff.

S4 must not silently drop preferred-source/style pairs, must not close S4 with uncovered mandatory pairs, and must not create `F03` or any third second-round candidate.

## Required Records

S3 must record preference signals in a paper-neutral structure such as:

```json
{
  "user_preferred_first_round_candidate_ids": ["<candidate_id>"],
  "preference_signal_source": "explicit_user_prompt",
  "preference_weighting_policy": "weighted_signal_not_unconditional_selection"
}
```

S4 must record the coverage obligations and produced rows in a structure such as:

```json
{
  "preference_coverage_policy": "v3.2.15f",
  "preferred_source_ids": ["<candidate_id>"],
  "style_slots": [{"style_id": "<style>", "style_label": "<label>"}],
  "required_pair_count": 0,
  "candidate_budget": 2,
  "coverage_status": "PASS|REPLAN_REQUIRED|FAIL"
}
```

Each S5 candidate row that satisfies this rule must include fields equivalent to:

```json
{
  "candidate_id": "F01",
  "source_first_round_candidate_id": "<candidate_id>",
  "style_id": "<style>",
  "preference_coverage_role": "preferred_first_round_local_essence_lead"
}
```

## Candidate Count And Infeasible Coverage

S4 must derive the required pair count dynamically from:

```text
required_count = number_of_preferred_source_ids x number_of_declared_style_slots
```

The reusable skill must not hard-code a project-specific candidate count, preferred ID list, or style vocabulary. The reusable workflow does, however, impose a fixed v3.2.15f public S5 cap of **two candidates**. If `number_of_preferred_source_ids x number_of_declared_style_slots` exceeds two, S4 must repair/replan, narrow the active style-slot/preference allocation, or request a user decision before S5 handoff.

## Prompt-Package Implications

For each preferred-source local-essence S5 candidate, the prompt package must state that the preferred first-round candidate is a visual preference signal only. It must not import unsupported arrows, unsupported modules, paper-specific claims absent from the source, or first-round mistakes. The prompt must say to preserve the useful local visual essence while repairing issues identified by S3.

## Negative Rule

Do not satisfy this policy by duplicating the same prompt image under multiple candidate IDs. Each required row must have a distinct second-round prompt package and must explicitly bind its preferred source and style slot.
