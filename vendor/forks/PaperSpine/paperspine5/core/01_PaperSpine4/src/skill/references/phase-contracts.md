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

In strict mode, research specialists may run in parallel and reviewers remain
independent until synthesis. In balanced mode, one Agent may combine these
lenses and write a single `structured_review.md`; separate role receipts are
optional unless an actual dispute, high-stakes claim, or user request warrants
independent review.
