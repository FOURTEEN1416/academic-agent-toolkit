# S2/S5 Layout Routing Prompt Audit Policy v3.2.12 + Edge-Label/Internal-Motif + Narrative Layout Addendum

Use this policy whenever `S1-embedded S2 preparation`, `S4-embedded S5 preparation`, or an authorized S2/S5 rerun text unit constructs image-generation prompts. The policy is generic: apply it to any paper framework figure, not to a specific paper, dataset, method family, or example output.

Also apply `references/paper-core-semantics-and-prompt-contract-policy-v323.md`, `references/framework-abstraction-flowline-and-rerun-prompt-policy-v328.md`, `references/academic-framework-hierarchy-and-asset-mirroring-policy-v3210.md`, `references/source-grounded-prompt-audit-and-style-policy-v320.md`, `references/edge-label-first-and-internal-motif-policy-v3211.md`, `references/s2-narrative-layout-divergence-policy-v3212.md` when the unit is a first-round S2 candidate stage, and `references/first-glance-layout-sanity-policy-v318.md`. Load `references/strict-source-grounded-modular-prompt-contract-policy-v3215a.md` for every S1/S4 prompt package. Also load `references/visual-information-economy-and-repetition-control-policy-v322.md` whenever repeated visual families, duplicated subflows, or low-redundancy user preferences are present. That policy is a pre-layout gate: a candidate that cannot state a single reviewer takeaway and a clean primary reader path is not prompt-ready, even if all planned elements are paper-supported.

Also load `references/routing-line-style-and-callout-abstraction-policy-v3215f.md` whenever a candidate uses dashed/dotted lines, feedback/exchange/reuse links, zooms, cutaways, insets, mechanism strips, or detail panels. Treat that policy as a pre-image handoff gate, not a post-generation preference.

## Purpose

S2/S5 image prompts must make reviewer first-glance path, layout, routing, arrow direction, flowline semantics, text, edge-label-first symbol choices, visual render graph conversion, internal visual motif choices, framework granularity, density, repetition compression, and redundancy explicit before image generation. A prompt that only says "draw the workflow", "connect modules", "show interaction", or "add details" is not prompt-ready. A directed arrow is allowed only when both the relation and the exact direction are supported by paper-body evidence, a paper equation/algorithm/figure/table, supplementary material, the S0 deep-reading/foundation report, or an author source clarification recorded in S0. User instructions may narrow scope, forbid misleading content, or set style, but they do not by themselves authorize a new paper element, relation, direction, mechanism token, formula, or claim.

The text unit must first build and audit a prompt package. If the package fails, revise the prompt package and audit again until `PROMPT_READY`, explicitly accepted `PROMPT_READY_WITH_RISK`, or `PROMPT_BLOCKED`. S1 and S4 may run at most five audit/repair cycles; unresolved blockers after the fifth cycle must stop image-handoff and produce a textual residual-risk ledger. Only after the package passes may it show or save the image-only prompt for the next user turn.

## Strict Modular Contract Addendum

S1 and S4 prompt packages must satisfy `references/strict-source-grounded-modular-prompt-contract-policy-v3215a.md` before prompt-index finalization. This means every connector needs an evidence-backed upstream and downstream endpoint; every carried item must point to an actual consumer or transformer rather than a false relay through a visually intermediate module; multiple lines between the same blocks require distinct source-supported carried quantities; transferred variables must live on edges, ports, forks, merges, or tags; the figure must remain modular rather than fragmented; internal submodule motifs must be simple and reviewer-recognizable; duplicated workflows and redundant zooms are blocked; and background context must remain a small support area.

Every image-only prompt must include these hard constraints in its own wording, not only in separate audit notes.

## Required Prompt Package Order

After S5, human decisions are outside this assistant workflow.

1. `evidence_lock`
2. `paper_core_semantics_lock`
3. `role_flow_separation_table` when repeated or variant entity families exist
4. `source_audit_ledger`
5. `local_kb_style_scan`
6. `narrative_strategy_vector` and candidate-specific `layout_projection` for first-round S2 candidates
7. `reviewer_first_glance_gate`
7. `complete_overview_gate` and `core_detail_display_matrix` for complete-paper candidates
8. `symbol_entity_classification`
9. `machine_semantic_graph` and `visual_render_graph`
10. `visible_text_contract` with node labels separated from edge/port labels
11. `edge_label_first_artifact_policy`
12. `line_carried_variable_registry`
13. `element_granularity_plan`
14. `internal_visual_motif_plan` for every core compound module
15. `element_layout_plan`
16. `routing_and_arrow_plan`
17. `flow_semantics_registry`
18. `edge_annotation_registry`
18a. `edge_support_ledger` with source-supported upstream/downstream endpoint evidence
18b. `connector_multiplicity_audit` and `connector_bundling_plan`
18c. `data_consumer_transformer_ledger` and `false_relay_data_flow_audit`
18d. `connector_style_semantic_budget`, `dashed_line_budget`, and `routing_geometry_contract` when line-style or routing ambiguity is possible
19. `module_input_contract`
20. `edge_cardinality_audit`
21. `connector_bundling_plan`
21a. `modularity_not_fragmentation_gate`
21b. `simple_internal_motif_gate`
21c. `background_context_budget_gate`
22. `visual_hierarchy_plan`, `artifact_block_guard`, and `academic_layout_hierarchy_gate` for hierarchy and duplicate/parallel connector risks
23. `arrow_direction_evidence_audit`
24. `text_symbol_verification`
25. `density_and_whitespace_budget`
26. `element_instance_budget and repeated_flow_compression_plan` when repeated visual families are present
27. `redundancy_budget`
28. `visual_information_economy_audit` when repeated visual families are present
29. `detail_panel_new_information_audit`
29a. `callout_abstraction_contract` and `main_detail_nonduplication_gate` when any detail panel, zoom, cutaway, inset, or mechanism strip is present
30. `prompt_contradiction_audit`
30a. `strict_prompt_contract_cycle_log` with no more than five audit/repair cycles
31. `prompt_hallucination_audit`
32. `image_only_prompt`

The selected image-only prompt must preserve this order: first state the one-sentence reviewer takeaway and primary reader path, then state complete-paper coverage and core-detail obligations when applicable, then describe the element layout and granularity decisions, then describe the visual render graph and which mathematical symbols/intermediate values are edge/port/fork/merge labels rather than boxes, then describe internal visual motifs for core compound modules, then describe the contracted edge families, connectors, endpoint/port constraints, flow semantics, line-style budgets, and arrowheads, then state detail-callout abstraction rules, repetition compression, strict modular prompt constraints, and concise stage-appropriate style constraints. The prompt must explicitly say to avoid unsupported arrows, duplicate connector lines, generic dashed helper lines, floating connectors, flow-like zoom pointers, variables as peer boxes, fragmented micro-panels, complex internal mini-workflows, redundant zooms, duplicate parent/detail step chains, and oversized background context. Do not put routing instructions before the reader can identify the elements being connected. Do not use style descriptors to smuggle in unsupported content. Do not use ambiguous words such as chip, token, box, card, or node for any term planned as an edge/port label.

## Evidence Lock

Before drafting layout or routing, re-open the best available paper-grounded sources for the current step:

- S2: S0 foundation/deep-reading report, S0 risk register, and S1 sketch card or contract.
- S5: S0 foundation/deep-reading report, S0 risk register, S3 selected direction, S4 candidate brief, and S4 prompt-risk transfer from relevant S2 audits.

Record only paper-supported facts. For every planned element, connector, arrow, label, symbol, formula, line style, color meaning, visual metaphor, and visual claim, keep a short evidence anchor: paper section/equation/algorithm/figure/table/supplement, S0 deep-reading note, or author source clarification recorded in S0. S1/S4 contract fields may be used only when they cite one of those sources. If no evidence anchor exists, handle the item conservatively: remove it from the image, mark it as a caption-only caveat outside the image, replace an unsupported direction with a non-directional grouping/callout only when the paper supports association but not direction, or route back to S0/S1/S4 for evidence rerun. Also record the `source_audit_ledger` required by `references/source-grounded-prompt-audit-and-style-policy-v320.md`.

## Paper-Core Semantics And Role-Flow Separation

After `evidence_lock` and before style scanning, apply `references/paper-core-semantics-and-prompt-contract-policy-v323.md`. Record `paper_core_semantics_lock` with the current paper's visual thesis, canonical backbone, artifact lineage, control/evaluation signals, topology/boundary constraints, core internals, caption-only facts, and forbidden visual inferences.

When the paper defines repeated or variant entity families, record `role_flow_separation_table`. Distinguish paper-defined role/context differences from truly distinct operation branches. If variants share a process, the layout must use a representative canonical flow plus compressed context markers, groups, braces, labels, or caption support. Multiple full workflow lanes are prompt-blocking unless the source evidence proves that the lanes differ by variant-specific operations or the user explicitly requested a comparison that cannot be compressed.

This gate is generic. It must not introduce target-paper examples into reusable rules. In project outputs, use only the current paper's terms and cite their source anchors.


## Local Knowledge Base Style Scan

Before writing the element layout plan, consult the local style/vector knowledge base as design vocabulary, not scientific evidence. Record `local_kb_style_scan` with the local resources consulted, paper-derived visual needs, selected style lenses, rejected misleading lenses, and the `style_evidence_boundary`. Prefer styles that improve reviewer first-glance, core-detail visibility, lineage clarity, and arrow safety for the target paper. Reject style choices that create unsupported metaphors, invent actors or data sharing, hide core modules, or increase ambiguous arrows. Use `references/vector-library/paper-grounded-style-extension-v320.md` as an additional style option list when helpful.

## Reviewer First-Glance Gate

Before writing element placements, apply `references/first-glance-layout-sanity-policy-v318.md` and record `reviewer_first_glance_gate`.

This gate must reduce the candidate to one primary reader path. It must name the one-sentence takeaway, 3-5 ordered visual anchors, dominant main-flow region, supporting/detail regions with area caps, compression plan, complexity budget, and drop-or-caption list.

If the gate fails, do not continue by adding more labels, panels, arrows, or legends. Rerun the candidate plan, merge secondary regions, move visually expensive facts to caption/legend/body text, or route back to S1/S4.

## Complete Overview Gate

For complete-paper framework requests, write `complete_overview_gate` before `element_layout_plan`. It must include:

- `complete_overview_statement`: "This is a complete-paper overview sketch/candidate, not a scoped submodule-only sketch."
- `framework_backbone_lock`: minimum visible modules/states and output/update targets that make the image a whole-paper framework.
- `paper_primary_paths`: every paper-primary or co-primary space/path that must be reached by the first-read flow or a clearly connected secondary flow.
- `core_detail_display_matrix`: each source-grounded core module, visible input/evidence, internal operation/substep, output/action token, display mode (`in_place_internal_detail` or `side_inset_detail`), and planned element/detail carrier.
- `caption_only_boundary`: details intentionally moved to caption/legend and why they are not core-pixel carriers.

If an overview candidate only explains one module or one paper-primary path, mark it scoped and do not prompt it as a complete framework. If a candidate uses `no detail panels`, it must still show all required core-module internals in place inside the main-flow modules. Missing internal-detail carriers are prompt blockers, not merely audit risks.

## Symbol Classification, Edge-Label-First Rendering, And Framework Granularity

Before `element_layout_plan`, apply `references/edge-label-first-and-internal-motif-policy-v3211.md`. Record `machine_semantic_graph`, `visual_render_graph`, `visible_text_contract`, `edge_label_first_artifact_policy`, `line_carried_variable_registry`, `internal_visual_motif_plan`, and `prompt_contradiction_audit`. The default for carried non-module terms is `inline_edge_label`, not a chip or standalone block. A term planned as an edge/port/fork/merge label must not be listed as a visible node label.

For core compound modules, `internal_visual_motif_plan` must map source-grounded substeps to visual micro-motifs. A prompt is blocked if it asks for only a title, empty box, or bullet list for a core module whose internal mechanism is required by the current paper contract.

Before `element_layout_plan`, load `references/framework-abstraction-flowline-and-rerun-prompt-policy-v328.md` and `references/academic-framework-hierarchy-and-asset-mirroring-policy-v3210.md`; record `symbol_entity_classification`, `edge_annotation_registry`, `element_granularity_plan`, `entity_density_budget`, `compound_gate_registry`, `visual_hierarchy_plan`, `primary_module_whitelist`, `artifact_block_guard`, `connector_bundling_plan`, and `academic_layout_hierarchy_gate`.

- Intermediate variables, temporary outputs, scores, losses, probabilities, thresholds, schedules, and other mathematical quantities default to edge labels, port labels, or attached control tags rather than standalone nodes.
- A variable or metric may become a visible node only when the current paper and reader path require it to be a material object, stored artifact, branch point, comparison target, or independently evaluated item. Record the exception reason.
- Framework overview prompts must merge micro-operations into compound modules when they do not need separate source/target/branch roles. The figure should show core method structure, not a box for every notation token.
- Gate/control pairs should normally appear as one compound gate with an attached tag unless the paper makes each part a separate mechanism.

## Flow Semantics And Edge Labels

Before `arrow_direction_evidence_audit`, record `flow_semantics_registry`, `edge_annotation_registry`, `module_input_contract`, and `edge_cardinality_audit`.

Every arrow or connector must say what it carries or means: data/artifact, model state/reference, control/gating, evaluation/metric, communication/exchange, conceptual dependency, containment, callout/zoom, or next-round reuse. These semantics are prompt/audit metadata; they need not be visible words in the figure unless whitelisted.

The prompt must forbid duplicate source-target arrows with the same role and must prefer labeled merge/split connectors when multiple variables jointly enter one module. An input arrow into a module is allowed only when the source evidence supports that exact input relation and direction. Contextual relevance is not enough.

For every carried item, `data_consumer_transformer_ledger` must identify the producer/source, true consumers, true transformers, and any non-consuming intermediate modules that must not be drawn as relays. If A produces `x` and C consumes `x` while B does not use `x`, the routing plan must not create A->B(`x`) or A->B->C(`x`); use direct A->C routing, C input/port/tag labeling, non-directional association, caption-only handling, or omission.

## Element Layout Plan

Write an explicit layout plan before the prompt. Each visible element or repeated element family must have:

- stable ID, such as `E01`, `E02`, or `Group-A`;
- role in the paper logic;
- evidence anchor;
- region and relative position, such as left input column, center main flow, top context strip, lower detail panel, right output, or side legend;
- relative size or visual-weight budget;
- label/text source and whether the text is allowed inside the image;
- allowed visual primitive family, such as module card, internal visual motif, edge label, port label, labeled fork/merge, justified artifact glyph, model icon, table, chart, graph, set, queue, loop, or callout;
- density cap, including maximum visible repeated tokens or rows before using ellipsis or aggregation.

Whole-framework layout is the default. For a complete-paper framework request, the main flow must remain the largest region and first reader path, normally occupying the central visual field and most usable canvas. A local mechanism, background/context panel, dataset distribution, legend, evidence anchor, formula panel, or detail inset must not become the dominant visual region unless the user explicitly requested a single-submodule explainer or a source-grounded physical-layout exception applies.

For complete-paper candidates, each element must say whether it belongs to the framework backbone, an in-place internal-detail carrier, a connected detail panel, context/constraint support, or caption/legend support. Do not place a core module as only a titled rectangle when the complete overview gate requires internal tokens. Do not let a side inset become the only recognizable method path; it must point back to a compact main-framework anchor.

Use representative samples instead of dense clouds. Repeated dots, tokens, entities, samples, bars, rows, arrows, labels, panels, or examples should normally be limited to a small exemplar set with ellipsis or grouping. If many entities share the same process, draw one canonical shared flow and connect a compressed group/archetype set to it; do not duplicate the full pipeline inside every repeated actor. Do not use dense background distributions, oversized context panels, repeated decorative tokens, or repeated equivalent panels to fill space.

Avoid equal-weight island maps. Context blocks, constraints, peer groups, legends, training details, and update/caveat panels must support the primary reader path; they must not form separate co-dominant centers unless the candidate explicitly uses a controlled swimlane comparison with one scan order.

## Routing And Arrow Plan

After the element layout plan, write a connector table. Every connector or line must have:

- stable connector ID, such as `R01`;
- source element ID and source port/side;
- target element ID and target port/side;
- arrowhead rule: directed arrow, bidirectional arrow, dashed exchange line, non-directional grouping line, callout line, or no line;
- semantic meaning: data/artifact flow, model/state update, control/gating, evaluation/score, communication/exchange, dependency, containment, or caption callout;
- evidence anchor for the relation and, for directed arrows, evidence anchor for the direction; S1/S4 contract source is valid only if it cites paper/S0 evidence;
- path corridor and routing constraint, such as top lane, lower loop, right-side return path, no crossing through labels, no crossing through icons, no arrow into a wrong module;
- forbidden alternatives, including reversed direction, unsupported shortcut, decorative connector, duplicate connector, or ambiguous merge/split.
- false-relay exclusions, including non-consuming/non-transforming nearby modules that must not receive or carry the connector label.

## Edge Whitelist And Port-Binding Contract

After `routing_and_arrow_plan`, compile `edge_whitelist_and_port_contract`. It must restate the allowed connector families in a form the image-only prompt can enforce: source element and port/side, target element and port/side, semantic type, arrowhead rule, relation evidence, direction evidence, maximum copies, compression cue, and forbidden alternatives.

The image-only prompt must include a no-extra-edges rule: draw only the contracted edge families; do not add decorative, shortcut, inferred, or visually convenient arrows; if a connector endpoint would be ambiguous, omit the connector or use a non-directional callout only when association is source-supported. For papers that distinguish data/artifact, model/state, control/gating, evaluation/score, and communication/exchange paths, the prompt must keep those connector families visually separable and must not let one family target another family's endpoint.

Generated-image audits must compare visible connectors to this contract. Unexpected connectors, wrong endpoints, wrong port bindings, unsupported arrows, reversed arrows, or connector crossings that alter meaning are `FLAG_MAJOR` or `BLOCKED` depending on severity.


Arrowheads must point from producer/current state/evidence to consumer/next step/result, or from source model/state to updated target when the paper defines that update. Do not add arrow direction from visual intuition, layout convenience, user preference, common practice, or an uncited downstream contract. Communication/exchange links must be bidirectional or visually coded as exchange only when the paper/S0 evidence supports that relation. If the exact direction is absent or uncertain, omit the arrowhead or use a non-directional grouping/callout plus caption text. Record `arrow_direction_evidence_audit` with separate `relation_supported` and `direction_supported` verdicts for every directed arrow.

## Text And Symbol Verification

Any visible text, abbreviation, variable, formula, metric, dataset name, module name, or claim must be checked against the paper, supplementary material, S0 deep-reading report, or author source clarification recorded in S0 before it is allowed into the prompt. Use the paper's terminology when possible. If the exact wording is not confirmed, use a generic visual token without text, or move the explanation to caption/legend text outside pixels.

Keep in-image text short. Do not put definitions, caveats, reviewer-facing explanations, or long background paragraphs inside the image. If text is needed, record `text_source=paper`, `text_source=supplement`, `text_source=S0`, `text_source=S1/S4 contract`, or `text_source=author_source_clarification`.

## Density And Whitespace Budget

The prompt must set a density budget before image generation:

- S2 sketches: compact-balanced and readable, with grouped coarse elements, short labels, few repeated tokens, tight but legible whitespace, and no underfilled canvas.
- S5 candidates: clean publication schematic density, with modular geometry, non-overlapping labels, separated semantic atoms, routing corridors, and primary method content centered and dominant.

Avoid dense point clouds, repeated sample dots, repeated entity rows, oversized legends, oversized background/context areas, cluttered side explanations, empty quadrants, and top-heavy context panels unless the paper figure goal explicitly requires them and the prompt gives a strict cap under `references/layout-density-mainline-balance-policy-v3215f.md`.

If a region risks crowding, compress repeated items into one exemplar, a small mini-set, an ellipsis, a grouped stack, or a caption note. Do not solve crowding by shrinking labels, adding more panels, splitting one idea into many equal boxes, or routing arrows around the whole canvas.

## Repetition Inventory And Compression Plan

When the candidate contains repeated actors, samples, nodes, models, rounds, tokens, arrows, panels, labels, legends, or equivalent subflows, load `references/visual-information-economy-and-repetition-control-policy-v322.md` and record `element_instance_budget and repeated_flow_compression_plan` before writing the image-only prompt. The plan must name each repeated family, the minimum distinct variants needed, the planned visible instances, the compression method, and the repeated subflow/icon/text/arrow/legend/panel that must not be duplicated.

Use one-copy semantics: each shared process should appear once as the canonical flow, with repeated populations represented by grouped archetypes, stacks, ellipses, cohort containers, count badges, or caption notes. A repeated copy is allowed only when it adds source-grounded new information such as a distinct role, state, timestep, comparison, or topology cue.

The image-only prompt must include an anti-repetition constraint whenever repetition is present: use exemplar compression; no repeated equivalent full pipelines; no repeated equivalent panels; no dense repeated rows/clouds/icons; no duplicate legends; no repeated arrows with the same semantics unless collapsed into a named connector family.

## Redundancy Budget

Every visible element and internal visual motif must pass the `new_information_test`: it adds a distinct paper-relevant mechanism, relation, constraint, comparison, orientation cue, or disambiguation cue. It must not mainly restate another module, label, legend, detail panel, title, or caption.

Detail panels may reveal hidden internal substeps, evidence constraints, or failure-risk distinctions. They must not redraw the same main module chain at a smaller scale unless the purpose is an explicit before/after comparison or a scoped zoom with new information. Do not show the same flow once as a main module and again as a detail panel if the second version does not add a new mechanism. For every detail panel, record `detail_panel_new_information_audit`: parent anchor, new source-grounded information, non-repetition proof, foreign-module exclusion, area budget, and callout-vs-data-flow connector style. A zoom panel that merely repeats the parent module or imports another module's internals is a prompt blocker.

Repeated phase/round/stage flows are allowed only when each segment represents a paper-defined distinct state, actor, mode, or time step. Otherwise use one representative segment plus ellipsis or a loop label.
## Stage-Fidelity Style Check

Record `stage_fidelity_style_check` before `prompt_hallucination_audit`.

- S2 first-round candidates must stay source-grounded, readable, and structurally exploratory even when the default surface is formal publication style. Unless the user explicitly selects a rougher override, use clean publication-style schematic wording; avoid glossy poster, dense dashboard, decorative, or photorealistic wording that conflicts with framework clarity.
- S5 candidates may be polished schematic drafts, but they must inherit the S2/S3/S4 semantic contract and `known_failure_pattern_avoidance` records.
- If a style descriptor encourages repeated cloning, excessive labels, dense connectors, or unsupported metaphors, rewrite the descriptor or block the prompt.



## Narrative Layout Projection Gate v3.2.12

For S2 first-round embedded prompt preparation, apply `references/s2-narrative-layout-divergence-policy-v3212.md` immediately after local style scanning and before element placement. The text unit must write `narrative_strategy_vector`, `layout_projection`, and `layout_grammar_block` for each candidate.

`layout_projection` is the bridge between the shared paper semantic graph and candidate-specific visible composition. It must decide which relations are the main story path, which are secondary/supporting, which appear as grouping/context, and which move to caption. Do not give every candidate the same full edge registry with equal visual priority. A shared edge contract is allowed, but the prompt must tell the image generator which subset forms the dominant reader path for this candidate.

The `layout_grammar_block` must specify concrete relative placement: canvas partition, anchor positions, primary route corridor, feedback/communication corridor, region weights, supporting-panel caps, legend position, and non-overlap rules. Rough sketch style is acceptable; rough layout is not.

Prompt audit must add:

- `layout_projection_check`: primary/secondary/context/caption edge projection exists and matches the candidate narrative;
- `layout_grammar_check`: the prompt contains concrete placement and corridor instructions, not only style labels;
- `anti_similarity_check`: this candidate's visual spine and region map differ from its nearest planned candidates;
- `ordered_surface_check`: the selected first-round surface does not permit chaotic alignment, crossing-heavy routes, or equal-weight module scatter.

If any of these checks fail, do not show or save the image-only prompt as ready. Rerun the candidate prompt package or route back to S1/S4 if the candidate role itself is not distinct.

## Semantic Graph Prompt Gate

Before layout/style prose is finalized, load `references/semantic-graph-prompt-contract-policy-v326.md`, `references/framework-abstraction-flowline-and-rerun-prompt-policy-v328.md`, `references/academic-framework-hierarchy-and-asset-mirroring-policy-v3210.md`, and `references/edge-label-first-and-internal-motif-policy-v3211.md`, then compile the prompt from a non-visible semantic graph specification plus a separate visual render graph. The prompt must contain a split visible text contract, visual render graph, line-carried variable registry, exact edge registry, internal visual motif plan, internal text blacklist, layout plan, routing plan, and style plan in that order. Internal node/edge/port/group/lane IDs are control identifiers only and must not appear in the rendered figure. Terms planned as edge/port/fork/merge labels must not appear in visible node labels.

## Prompt Hallucination Audit

Before showing or saving an image-only prompt, run and record `prompt_hallucination_audit` after the source audit ledger, paper-core semantics lock, role-flow separation table when applicable, local style scan, edge whitelist/port contract, arrow-direction audit, stage-fidelity style check, and detail-panel new-information audit:

- `paper_core_semantics_check`: the prompt follows the current paper thesis, canonical backbone, artifact lineage, control/evaluation sources, topology/boundary constraints, and forbidden visual inferences recorded in `paper_core_semantics_lock`.
- `role_flow_separation_check`: repeated or variant entities are represented according to their source-supported role/flow distinction; shared workflows are not cloned as full lanes.
- `semantic_graph_spec_check`: the prompt contains unique internal IDs, a machine semantic graph, a visual render graph, an exact source-target-port edge registry, a split visible text contract, and an internal text blacklist; internal IDs are explicitly forbidden from rendering.
- `symbol_entity_classification_check`: intermediate symbols, variables, metrics, and control values are edge/port/fork/merge labels or attached tags unless a glyph/box exception is recorded.
- `edge_label_first_check`: every line-carried variable has a registry entry and no edge/port/fork/merge label is requested as a standalone chip/token/box/node.
- `visual_render_graph_check`: semantic artifact nodes are converted to labels, tags, fork/merge labels, glyphs, or caption-only unless a visible-node exception is recorded.
- `internal_visual_motif_check`: every required core compound module has pictorial micro-motifs or a mini-chain; bullet-only or title-only modules are blocked.
- `prompt_contradiction_check`: prompt wording contains no rendering contradiction such as a term classified as edge label but later called a chip, token, box, card, or node.
- `granularity_check`: the figure role justifies the selected detail level; micro-operations are merged into compound modules unless independently source-grounded.
- `flow_semantics_check`: every connector has a data/model/control/evaluation/communication/dependency/containment/callout/reuse semantic type that matches the source evidence.
- `module_input_contract_check`: every arrow into a module is an allowed input with evidence, not a layout convenience or contextual association.
- `edge_cardinality_check`: duplicate same-source same-target edges are removed, merged, or justified by distinct roles.
- `edge_contract_check`: every visible requested connector is in `edge_whitelist_and_port_contract` / exact edge registry, with no unlisted shortcut, decorative, or cross-family arrows.
- `element_support_check`: every element has a paper/deep-reading/source-clarification evidence anchor, or an S1/S4 contract field that cites one.
- `first_glance_check`: the candidate has a one-sentence reviewer takeaway, a 3-5 anchor primary reader path, a dominant main-flow region, and a complexity budget that fits the requested figure role.
- `narrative_strategy_check`: for first-round S2 candidates, the prompt has a source-grounded story question, protagonist/anchor, conflict, resolution path, visual spine, layout archetype, and difference-from-nearest-candidates record.
- `layout_projection_check`: for first-round S2 candidates, shared semantic edges are projected into primary, secondary, context, and caption-only roles rather than all being rendered with equal visual priority.
- `layout_grammar_check`: for first-round S2 candidates, the prompt gives concrete canvas partition, anchors, region weights, route corridors, scan order, non-overlap rules, and anti-similarity directives.
- `complete_overview_check`: complete-paper candidates name the framework backbone, all paper-primary paths, and visible internal-detail carriers for every source-grounded core module; scoped candidates are explicitly scoped and include a global context strategy.
- `layout_support_check`: the region hierarchy matches the requested figure intent and does not demote the whole framework.
- `core_detail_display_check`: every required core module has an in-place mini-chain, internal visual motif, or connected detail carrier; `no detail panels` passes only when all internals are visible in place, and bullet lists do not satisfy this requirement.
- `routing_support_check`: every line, connector, arrowhead, merge, split, and loop has a justified source, target, direction, semantic type, and paper/S0 evidence; directed arrows fail when either relation or exact direction is supported only by visual intuition, user preference, common practice, or an uncited contract.
- `text_support_check`: every visible label, abbreviation, formula, metric, and claim is verified or removed.
- `density_check`: repeated tokens and background/context areas stay within the density budget.
- After S5, human decisions are outside this assistant workflow.
- `repetition_compression_check`: repeated actors, samples, stages, labels, legends, panels, and arrows use exemplar compression or shared-flow representation; repeated equivalent full pipelines and repeated equivalent panels are blocked unless each copy adds source-grounded new information.
- `visual_information_economy_audit`: repeated visual families are inventoried, compressed, and limited by an element-instance budget; no repeated equivalent full pipelines, dense clouds, duplicate legends, or repeated arrows remain without source-grounded distinction.
- `artifact_block_guard`: non-module artifacts, variables, metrics, states, and parameters are not promoted into equal-weight large blocks unless a source-grounded exception is recorded.
- `edge_label_eligible_box_audit`: variables and carried artifacts planned as line labels are not rendered as standalone chips, cards, rectangles, bubbles, or nodes.
- `academic_layout_hierarchy_gate`: the candidate preserves macro/module/internal-detail/symbol hierarchy.
- `connector_bundling_plan`: related inputs/outputs are bundled into connector families with labels; no duplicate or unlabeled parallel connectors remain.
- `redundancy_check`: detail panels and repeated flows add new source-grounded information instead of duplicating the main module, another panel, legend, title, or caption; zoom panels do not import foreign-module content.
- `uncertainty_action`: unsupported or uncertain items are removed, simplified, moved to caption, or sent back to S1/S4 for contract rerun.

If the audit does not pass, do not show the image-only prompt. A failed first-glance gate, unsupported element, unsupported arrow direction, unsupported module input, duplicate edge, variable-as-box error, edge-label-eligible box error, visual-render-graph leakage, text-only core mechanism, bullet-list substitution for required internals, over-decomposed framework layout, uncontracted extra edge, unverified in-image text/symbol/formula, repeated equivalent full pipeline, repeated equivalent panel, stage-style mismatch, or redundant/non-informative detail panel is blocking even when the rest of the layout is attractive. Rerun the current text contract if the fix is local to the prompt package, then re-run the full audit. If the error comes from missing or contradictory paper evidence, route back to S0/S1/S4 as appropriate.

## Audit Output

Save the prompt package in the candidate folder, alongside `prompt-v01.md`. When file artifacts are available, also save a compact audit record such as `prompt-audit-v01.md` or `prompt-audit-v01.json` with:

- candidate ID;
- source files and local style-knowledge resources consulted;
- one-sentence reviewer takeaway and primary reader path;
- element count, repeated-family count, compression choices, and density caps;
- connector count, directed-arrow count, edge whitelist/port-binding summary, flow semantics summary, module-input-contract verdict, duplicate-edge verdict, relation-evidence verdict, direction-evidence verdict, unexpected/forbidden-arrow list;
- symbol/entity classification summary and variables rendered as edge/port labels;
- framework granularity summary, merged micro-operations, and node-exception reasons;
- first-glance verdict and complexity budget;
- text labels allowed;
- removed or caption-only uncertain items;
- repetition-compression verdict, redundancy verdict, and detail-panel new-information verdict;
- final prompt-ready verdict.

The prompt-ready verdict must be one of `PROMPT_READY`, `PROMPT_READY_WITH_RISK`, or `PROMPT_BLOCKED`. Only `PROMPT_READY` and explicitly accepted `PROMPT_READY_WITH_RISK` may proceed to `IMAGE_GENERATE`.


## v3.2.4 issue-ledger override

Use issue-ledger audit fields for S2/S5-related review outputs: record concrete issues, severity, rerun eligibility, high-priority issue status, downstream use, and caption burden. Hard contradictions become `BLOCKER_ISSUE` records. Do not use pass/fail labels as the sole selection verdict unless the user explicitly requests a filtering/ranking mode.
