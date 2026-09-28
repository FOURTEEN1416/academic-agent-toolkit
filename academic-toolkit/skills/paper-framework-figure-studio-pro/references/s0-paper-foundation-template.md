# S0 Paper Foundation Template

S0-PAPER-FOUNDATION initializes state, builds the factual base, screens framework-figure readiness, handles author supplementation, and locks unresolved risks before S1-FIGURE-STRATEGY runs.

Required sections when paper/source material is available:

1. Input material inventory.
2. Problem, assumptions, and contribution summary.
3. Method/algorithm/model pipeline.
4. Module inventory: input, output, role, dependency.
5. Training and inference flow.
6. Objective/loss/equation interpretation.
7. Terminology map: paper term -> figure label -> allowed shorthand.
8. Arrow semantics table.
9. Core innovation modules and internal mechanism evidence.
10. Heavily described, formula-backed, or explicitly improved mechanisms that need visual anchors.
11. Non-droppable core substeps.
12. Figure-relevant omissions and uncertainty.
13. Caption-supported facts, numbers, datasets, metrics, caveats, and formula explanations.
14. Framework-figure risk screen: missing information, contradictions, unsupported lineage, core-module opacity, and scope mismatch.
15. Author supplement request, if major/blocking issues remain.
16. Supplement integration log, if the user provides additional information.
17. Framework-figure risk register with downstream carry-forward instructions.
18. Semantic precision contract: normalize every figure-relevant vague directive into concrete meaning, visual-safe instruction, forbidden interpretation, and downstream S1/S4 carry-forward.
19. Role / actor / condition variation matrix: for every repeated role, actor, client, agent, modality, condition, dataset, mode, domain, or instance, state whether it shares the canonical workflow, where it truly diverges, how it must be shown, and whether full-flow repetition is forbidden or source-supported.
20. Process instance budget and duplicate-flow lock: default to one canonical process unless source evidence proves distinct process instances are scientifically necessary.
21. S1 strategy hints.

Required S0 output files:

- `outputs/S0-paper-foundation/paper-foundation-report.md`;
- `outputs/S0-paper-foundation/s0-semantic-precision-contract.json`;
- `outputs/S0-paper-foundation/framework-figure-risk-register.md` when any risk, caveat, declined supplement, or scoped override exists;
- `outputs/S0-paper-foundation/author-supplement-request.md` when author information is needed;
- `outputs/S0-paper-foundation/supplement-integration-log.md` when author information is added after the first S0 read.

Required state key:

```text
s0_foundation_readiness_state.foundation_readiness_status
```

Allowed values:

- `S0_FOUNDATION_READY`;
- `S0_FOUNDATION_READY_WITH_RISK`;
- `S0_NEEDS_AUTHOR_SUPPLEMENT`;
- `S0_NOT_SUITABLE_FOR_COMPLETE_FRAMEWORK`.

After S5, human decisions are outside this assistant workflow.

After S5, human decisions are outside this assistant workflow.

Default canvas is 16:9 unless the user requests another ratio.

Default S1 planning count is eight style-combination proposals. Default S2 output count is four sketches from C01-C04 prompt packages. Default S4/S5 formal count is two candidates, F01-F02. S5 candidates remain generated raster images. Their icons, arrows, colors, and caption plans should optimize paper meaning; SVG/PPT editability is secondary.


## S0 Semantic Precision Contract Requirements

S0 must apply `references/s0-semantic-precision-and-role-variation-lock-policy-v3215f.md` before closing. Broad statements such as "preserve role differences", "show each actor", "highlight heterogeneity", "reflect interaction", or equivalent source-derived wording must not remain as standalone drawing guidance. They must be converted into rows with:

- source phrase and evidence anchor;
- concrete scientific meaning;
- visual-safe implementation instruction;
- explicit forbidden interpretation;
- downstream S1/S4 fields that must carry the constraint.

For repeated roles/actors/conditions, S0 must explicitly choose one representation from `representative_shared_flow`, `branch_only_where_distinct`, `parallel_lanes_required`, `comparison_lanes_required`, `topology_or_context_inset_only`, or `caption_only`. If the repeated entities share the same canonical workflow, S0 must state that full-flow repetition is forbidden and prescribe compact role/condition markers instead.

If S0 cannot determine whether a phrase means shared-flow markers, local branching, parallel lanes, comparison lanes, topology inset, or caption-only context, mark the ambiguity as `major` or `blocking` and request author supplementation or lock the risk before S1.
