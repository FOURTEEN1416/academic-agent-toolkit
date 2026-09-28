# S0 Foundation Readiness And Candidate Status Policy v3.1.6

After S5, human decisions are outside this assistant workflow.

This policy has two separate responsibilities:

- `S0-PAPER-FOUNDATION` owns paper/source sufficiency, author supplementation, and the risk register for framework-figure drawing.
- `S2-SKETCH-EXPLORE` and `S5-CANDIDATE-IMAGE` own generated-candidate status values and rerun semantics.

Do not move source sufficiency judgment into `S1-FIGURE-STRATEGY`. S1 is a strategy and candidate-card step that consumes the locked S0 foundation.

## Public Step Boundary

The public workflow remains exactly:

```text
After S5, human decisions are outside this assistant workflow.
```

Use these exact step IDs in state, reports, guidance, and next prompts. Do not introduce aliases such as "Stage 1", "readiness stage", "strategy stage", or "clarification stage" as state identifiers. Dynamic substages are internal only and must use their exact substage IDs and modes.

## S0 Foundation Readiness Workflow

`S0-PAPER-FOUNDATION` must read the available paper/source material, build the factual foundation, and decide whether missing or contradictory information affects the requested framework figure.

S0 internal workflow:

1. `S0-00-input-inventory`: register paper files, source text, supplement, user constraints, runtime, canvas defaults, and preference references.
2. `S0-01-paper-deep-read`: write `outputs/S0-paper-foundation/paper-foundation-report.md` using `references/paper-deep-reading-contract.md`.
3. `S0-02-semantic-precision-contract`: write `outputs/S0-paper-foundation/s0-semantic-precision-contract.json` and mirror the same content in the report. Normalize every high-risk vague directive into concrete meaning, visual-safe instruction, forbidden interpretation, role/condition variation decision, and downstream S1/S4 carry-forward.
4. `S0-03-framework-figure-risk-screen`: screen the paper for figure-affecting missing information, ambiguity, contradictions, unsupported lineage, core-module opacity, scope mismatch, or unresolved vague visual directives.
5. `S0-04-author-supplement-request-or-risk-lock`: if information is missing or a high-risk directive cannot be concretely interpreted, write `outputs/S0-paper-foundation/author-supplement-request.md`; if the user declines or chooses to proceed, record that decision instead of asking again in S1.
6. `S0-05-user-response-integration`: integrate author answers into `paper-foundation-report.md`, update `s0-semantic-precision-contract.json`, and write `outputs/S0-paper-foundation/supplement-integration-log.md`.
7. `S0-06-foundation-lock`: write `outputs/S0-paper-foundation/framework-figure-risk-register.md` and update `s0_foundation_readiness_state`.
8. `S0-07-s0-to-s1-handoff`: provide the next copyable prompt for `S1-FIGURE-STRATEGY`; do not execute S1 in the same turn.

If the user supplies additional paper facts after S0 has already completed, update S0 first. Do not let S1 absorb new author facts as an informal side channel.



## S0 Semantic Precision Gate

S0 readiness is not complete if figure-relevant terms remain too vague to draw safely. Phrases that instruct later stages to preserve, show, reflect, highlight, distinguish, compare, align, exchange, interact, specialize, personalize, or differentiate a role/module/condition must be converted into a concrete visual realization contract.

The gate passes only when S0 records:

- a machine-readable `s0-semantic-precision-contract.json`;
- an `ambiguous_directive_normalization` row for each high-risk vague directive;
- an `actor_or_condition_variation_matrix` for repeated roles, actors, conditions, modes, clients, agents, data sources, tasks, domains, or instances;
- a `role_visual_realization_contract` that states whether differences are compact markers, branch-only segments, comparison lanes, parallel lanes, topology/context insets, or caption-only;
- a `process_instance_budget` that forbids duplicated full flows unless source evidence supports different operation sequences or explicit comparison intent;
- negative locks that name likely wrong interpretations.

If the source says that differences exist but does not identify where they affect the workflow, the default safe decision is not to duplicate full flows. Represent the difference compactly and record a risk, or request author supplementation if the uncertainty would materially affect the figure.

## S0 Readiness State

Record the normative readiness state under:

```text
s0_foundation_readiness_state.foundation_readiness_status
```

Allowed values:

- `S0_FOUNDATION_READY`: source material is sufficient for the requested figure scope.
- `S0_FOUNDATION_READY_WITH_RISK`: the figure can proceed, but unresolved minor or accepted risks must be carried forward.
- `S0_NEEDS_AUTHOR_SUPPLEMENT`: source material lacks information that could materially affect figure correctness.
- `S0_NOT_SUITABLE_FOR_COMPLETE_FRAMEWORK`: a complete-paper framework figure would require unsupported invention; S0 may still support a narrowed scoped-mechanism figure if the user accepts that scope.

Issue severity:

- `info`: useful context, not needed for S1.
- `minor`: proceed with a caveat in the risk register.
- `major`: a core relation, lineage, module internal, or figure scope is ambiguous enough to affect the drawing.
- `blocking`: a complete framework would require inventing unsupported paper facts.

If only `info` or `minor` issues exist, S0 may mark `S0_FOUNDATION_READY_WITH_RISK` and continue to S1.

If any `major` or `blocking` issue exists, S0 should stop inside S0 by default, write the author supplement request, and provide copyable prompts for:

1. supplying missing author information;
2. proceeding with known risks;
3. narrowing the requested figure scope.

If the user supplements the material, S0 must update the paper foundation report and supplement integration log before S1 runs.

After S5, human decisions are outside this assistant workflow.

## S1 Consumption Rule

`S1-FIGURE-STRATEGY` consumes:

- `outputs/S0-paper-foundation/paper-foundation-report.md`;
- `outputs/S0-paper-foundation/framework-figure-risk-register.md` when present;
- `s0_foundation_readiness_state`.

S1 may design the figure role, reader question, style lens, visual directions, candidate cards, core-module visibility locks, and at most two evidence-grounded manuscript story improvement proposals. It must not decide whether the paper needs author supplementation. If S1 finds that S0 is missing, stale, or contradictory, it must stop with a pointer to rerun or rerun `S0-PAPER-FOUNDATION`.

## S2/S5 Candidate Status Values

Every generated S2 sketch and S5 formal candidate must carry one active status:

- `PASS`: no material problem found under the active checks.
- `REVISED_PASS`: failed the first check, was fresh-regenerated once, and passed the follow-up check.
- `FLAG_MINOR`: usable downstream, but has a documented minor uncertainty or visual defect.
- `FLAG_MAJOR`: may preserve a useful visual idea, but has a material semantic, lineage, topology, core-detail, or caption-fit risk.
- `BLOCKED`: contradicts the paper, relies on unsupported facts, hides a non-droppable core mechanism, or is too unreadable/ambiguous for normal selection.

After S5, human decisions are outside this assistant workflow.

## No User-Exposed Contract Setting Or Candidate-Level Rerun

The skill exposes no contract-check selector and no S2/S5 candidate-level rerun authorization prompt. S2 and S5 are image-generation-only public stages. If generated candidates are problematic, record or transfer the issue in the appropriate upstream/downstream text stage: S3 reviews S2 images; S4 converts useful S2 risks into S5 prompt constraints; S5 ends after image generation. Any new image batch after S5 requires a new explicit human decision outside this assistant workflow or an explicit upstream rerun request.

## Downstream Propagation

S3 must read the S2 generated images and registry, then write the embedded S2 issue-ledger review and exploration aggregate before direction selection. S3 selects from S0/S1 paper logic, reader question, and S2 visual exploration signals, then records which S2 visual sources and risks S4 must transfer.

S4 must not silently build a clean formal contract from a risky S2 direction. It must convert relevant S2 issues into `s4_prompt_risk_transfer` items and S5 negative constraints, or state that the risk is intentionally carried forward.

S5 does not audit candidates. It only generates formal raster candidates from S4 prompt packages and then ends the assistant workflow.

After S5, human decisions are outside this assistant workflow.

After S5, human decisions are outside this assistant workflow.


## v3.2.4 issue-ledger override

Use issue-ledger audit fields for S2/S5-related review outputs: record concrete issues, severity, rerun eligibility, high-priority issue status, downstream use, and caption burden. Hard contradictions become `BLOCKER_ISSUE` records. Do not use pass/fail labels as the sole selection verdict unless the user explicitly requests a filtering/ranking mode.
