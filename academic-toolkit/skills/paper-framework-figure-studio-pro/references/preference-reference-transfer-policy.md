# Preference Reference Transfer Policy v3.2.15f

Uploaded or registered style preference references are analyzed for S1-FIGURE-STRATEGY figure-type and reader-effect suggestions.

After S5, human decisions are outside this assistant workflow.

If the user later selects or restates a style preference as an explicit requirement, record it as a user decision and carry it forward. Do not infer it silently from uploaded examples.

Preference references can inspire visual grammar, not source-paper facts.

## First-round candidate preference carryover

When the user names first-round S2 candidate IDs in or before S3, the named candidates are not merely weak style hints. S3 must save them as `user_preferred_first_round_candidate_ids`. S4 must apply `references/preferred-first-round-carryover-policy-v3215b.md` and allocate at least one second-round S5 local-essence refinement dominated by each preferred S2 candidate for each active S5 style family.

This is a generic lineage contract. It does not assume candidate IDs, image counts, file names, or paper domains. It derives all IDs and styles from prompt indexes, S3 records, candidate matrix rows, and user messages.
