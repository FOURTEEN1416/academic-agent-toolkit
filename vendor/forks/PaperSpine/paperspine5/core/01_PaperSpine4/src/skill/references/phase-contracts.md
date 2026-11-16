# Minimal Phase Contracts

Use these contracts for strict-mode specialist dispatch. A phase reads only the listed
inputs, writes only its output, and appends one execution receipt to
`usage_ledger.jsonl`. Role prompts may add domain expertise but may not expand
the claim boundary or replace a gate.

| Phase / Role | Minimum Inputs | Required Output | Receipt Must Record |
|---|---|---|---|
| Scene analyst | scene, target, official evidence, source index | `research_dossier.md` | sources read, venue uncertainty, output hash |
| Exemplar learner | tier, source index, scene rules | `exemplar_learning_dossier.md` | examples actually inspected, learned patterns, output hash |
| SOTA mapper | source index, user materials, contribution context | `sota_gap_map.md` | claim/evidence boundary, conflicts, output hash |
| Evidence mapper | source inventory, analysis outputs, confirmed contribution | `scientific_evidence_ledger.json` | S/C/N/M/O/R links, verification state, gate result |
| Methods reviewer | manuscript + evidence ledger | independent methods review | evidence used, blocker IDs, output hash |
| Contribution reviewer | manuscript + confirmed contribution | independent contribution review | claim-boundary checks, blocker IDs, output hash |
| Clarity/figure reviewer | manuscript + rendered figures/pages | independent clarity/visual review | renders inspected, conflicts, output hash |

Research specialists may work in parallel when useful. A reviewer may combine the Methods, Contribution and Clarity lenses, but the author must not present its own check as independent review. Form independent findings before synthesis, using actual sources and current rendered files; separate role receipts are not a prerequisite.

## Canonical host-to-Runner stage contract

When the installed ProductRunner tools are available, the current host executes
J4-J11 directly. Each transition uses one
`paperspine5.academic-stage-answer/1.0` bound to the current `task_id`, revision,
stage, issue ID, and opaque `resume_token`, submitted only through
`paperspine5_runner_answer_academic_stage`. The host reloads the resulting
snapshot before continuing. Product Web and flat output are read/resume
projections of that same task; neither may create a second writable authority.
The nested Web Agent remains optional and fail-closed, so its blocker never
counts as a stage answer or manuscript completion.
