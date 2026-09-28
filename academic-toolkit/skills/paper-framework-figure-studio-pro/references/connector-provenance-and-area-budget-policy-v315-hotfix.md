# Connector Provenance And Area Budget Policy v3.2.0

After S5, human decisions are outside this assistant workflow.

## Core Rule

Every visible connector must be evidence-first. A connector is allowed only when the workflow can state, before image generation:

```text
source element -> target element
paper evidence anchor
semantic relation
line style / arrowhead
min/max visible instances
required visibility status
forbidden misreadings
```

If any field is unknown, do not draw the connector. Put the uncertainty in the caption or omit the relation. If the relation is supported but direction is not, use a non-directional grouping/callout only when that cannot be mistaken for data/model/control flow.

Arrow direction semantics are part of connector provenance and must be validated separately from relation existence. The arrowhead marks the destination: the receiving module, information consumer, updated target, next state, next step, or result. The connector source is the producer, current state, evidence object, input artifact, or action that sends information forward. Reverse arrows are forbidden unless the paper explicitly states a feedback/update relation, and that relation is listed as its own connector with source, target, evidence, and line style. Bidirectional exchange should use two labeled evidence-backed arrows or one explicitly labeled loop; never use a vague double-headed arrow for visual balance.

Connector provenance must also prevent false relay data-flow. A connector may not make a visually intermediate module appear to receive, route, or carry a data/artifact/model/control/evaluation item unless that module actually consumes, transforms, filters, stores, routes, evaluates, updates, or emits the item. If A produces `x` and C consumes `x` while B does not use `x`, do not encode A->B(`x`) or A->B->C(`x`) in the connector table; encode the true A->C relation, a C input/port/tag label, a non-directional association, caption-only handling, or omission.

## Connector Provenance Table

Connector tables are necessary but not sufficient. S1 must first define the candidate's `sketch_model_contract` as a node/edge/port/layout skeleton; then it must include a lightweight `sketch_connector_provenance_table` for every non-trivial arrow, bridge, feedback loop, callout, dashed edge, dotted edge, and merge/split connector expected in the S2 sketch. S4 formal candidate contracts must include the full `connector_provenance_table` for every non-trivial connector in S5. Required fields:

- `connector_id`;
- `source_element`;
- `target_element`;
- `true_consumer_or_transformer`;
- `non_consuming_intermediate_exclusions`;
- `paper_evidence_anchor`;
- `direction_evidence_anchor` for every directed connector;
- `semantic_relation`: one of `local_data_flow`, `model_signal`, `parameter_update`, `sampled_subset`, `same_instance_reuse`, `same_distribution_alignment`, `feedback_to_next_round`, `zoom_reference`, `caption_only_context`, or a target-paper-specific relation;
- `line_style`;
- `target_port`;
- `min_visible_instances`;
- `max_visible_instances`;
- `required_visibility`: `must_show`, `optional`, or `caption_only`;
- `why_connector_is_needed`;
- `relation_supported` and `direction_supported` verdicts for directed connectors;
- `forbidden_misreadings`;
- `false_relay_data_flow_verdict`;
- `delete_if_not_visible_as_planned`: true/false.

S2 and S5 prompts must translate the relevant connector table into plain image-generation constraints. Do not rely on a generic phrase such as "connect the modules" or "show flow arrows".

For S2, the table may be shorter and sketch-oriented, but it must still lock:

- required model nodes and optional context nodes;
- allowed source -> target directions;
- allowed connector ports for high-risk modules and artifacts;
- forbidden reverse arrows;
- edge cardinality and must-show dependency edges;
- forbidden merges/splits;
- compound input drawing mode for multi-input modules;
- primary/replica marking for any repeated artifact copies;
- forbidden topology, including any S0-forbidden hub, bridge, feedback loop, cross-lane shortcut, shared-resource branch, or role/coordination pattern that the target paper does not support;
- legal producers for high-risk artifacts;
- required internal tokens for core modules;
- maximum visual budget for context/background regions.

Low fidelity relaxes polish, typography, and geometry. It does not relax paper semantics.

## Evidence-Locked Prompt Compilation Gate

Before sending any S2 or S5 prompt to the environment-locked image-generation route (`image_gen` in Codex, Create Image / ChatGPT Images 2.0 in ChatGPT web), the assistant must compile the candidate contract into an evidence-locked prompt package. For S2, first compile a `s2_pre_image_contract_sheet`, then compile `sketch_evidence_locked_prompt_package` from that sheet and the S1 sketch card. For S5 it is named `evidence_locked_prompt_package` and is compiled from the S4 formal candidate contract. This package is part of the text/image handoff and must be checked before generation.

Required fields:

- `allowed_connectors`: copied or compressed from `connector_provenance_table`; each item must still have source, target, semantic relation, and evidence anchor.
- `data_consumer_transformer_ledger`: true consumer/transformer mapping for carried items, including non-consuming intermediate modules that must not be shown as relays.
- `false_relay_data_flow_audit`: pass/fail check that no connector routes carried items through modules that do not consume or transform them.
- `required_node_inventory`: the paper-model nodes/tokens that must be visible or validly scoped out.
- `port_binding_lock`: allowed input and output ports for high-risk nodes; wrong-port arrows are audit failures.
- `forbidden_connectors`: arrows, merges, feedback lines, or callouts that the paper does not support and that the image model may be tempted to invent.
- `forbidden_topology`: unsupported graph structures, not only individual arrows.
- `arrow_direction_lock`: the exact allowed direction for each connector; if the reverse direction is wrong, say so explicitly.
- `line_style_lock`: solid/dashed/dotted/elbow/callout style for each relation type.
- `merge_split_lock`: which inputs are allowed to merge at a module and which artifacts are allowed to fork; all other merges/splits are forbidden.
- `edge_cardinality_lock`: min/max visual instances for every high-risk connector; parallel duplicates are forbidden unless explicitly contracted.
- `dependency_visibility_lock`: required dependency edges that must be visibly connected with an arrowhead at the contracted target port.
- `compound_input_lock`: for every multi-input module, the prompt must choose direct input arrows, one merge gate, or label-only grouped input, never an ambiguous mixture.
- `artifact_replica_lock`: whether artifacts may be repeated, which copy is primary, and how every replica is marked as same-instance, sampled-subset, same-distribution, or conceptual proxy.
- `core_internal_tokens_lock`: minimum internal tokens for each core module.
- `area_budget_lock`: approximate maximum visual share for context/background and minimum protected share for core/bridge mechanisms.
- `main_flow_dominance_lock`: the main framework remains the largest single region and first reader path; each detail panel remains smaller and collectively subordinate.
- `model_fidelity_audit_plan`: post-generation checks for node inventory, edge allowlist, edge direction, port binding, forbidden topology, lineage, core internals, area budget, and scope label.
- `visible_edge_inventory_template`: table to fill after generation before accepting the sketch/candidate.
- `prompt_ready_check`: pass/fail statement that every connector requested in the prompt exists in the connector table, every non-droppable core step has a visible token, and the prompt cannot be satisfied by drawing a different model.

If `prompt_ready_check` fails, do not call the image-generation route. Rerun S4 or the prompt first.

The final S2 or S5 image prompt should not include the full evidence table verbatim if that would overload the image model, but it must include the operational locks derived from the table: required nodes, allowed arrows, forbidden arrows, forbidden topology, arrow directions, line styles, port bindings, core internal tokens, merge/split rules, legal artifact producers, and area budget.

After image generation, S2 and S5 must compare the returned image against the same evidence-locked prompt package, not against a looser intuitive reading of the paper.

The prompt must say "do not add extra arrows" whenever connector semantics are high-risk. An invented arrow, a reverse arrow, or a style-only arrow that implies unsupported information transfer must be marked `FLAG_MAJOR` or `BLOCKED`, not accepted as a harmless design choice. Callout or zoom connectors are not data-flow arrows; they should use brackets, labels, stubs, or non-directional leaders unless the arrowhead explicitly means "this main-flow anchor is expanded in this detail panel."

## S2 Low-Fidelity Pre-Image Gate

S2 is the first image-generation stage, so it must catch semantic connector and core-module failures before they become attractive candidate directions. Before each S2 sketch, verify that its S1 sketch card includes:

- `sketch_model_contract`;
- `sketch_required_node_inventory`;
- `sketch_layout_skeleton_contract`;
- `sketch_port_binding_table`;
- `sketch_adjacency_allowlist`;
- `sketch_simplification_contract`;
- `sketch_connector_provenance_table`;
- `sketch_forbidden_connectors`;
- `sketch_forbidden_topology`;
- `sketch_arrow_direction_lock`;
- `sketch_merge_split_lock`;
- `sketch_edge_cardinality_contract`;
- `sketch_dependency_edge_must_show`;
- `sketch_compound_input_policy`;
- `sketch_artifact_replica_policy`;
- `sketch_visible_edge_inventory_template`;
- `sketch_core_internal_tokens_lock`;
- `sketch_area_budget_by_region`;
- `sketch_incoming_lineage_audit`;
- `sketch_model_fidelity_audit_plan`;
- `sketch_prompt_ready_check`.

If any required field is missing or says fail, do not generate that S2 sketch. Rerun S1 first.

The S2 prompt must explicitly tell the image-generation model to prefer omitting an uncertain connector over inventing a plausible-looking connector. Any accidental connector that implies a false relation is a semantic failure, even if the sketch is otherwise visually useful.

S2 post-generation audit must flag and rerun or regenerate sketches that:

- omit a required model node/token without an explicit scoped-probe allowance;
- add a new producer, hub, shortcut, or module that is not in the model contract;
- attach an arrow to the wrong high-risk module or port;
- hide a core module as an empty named box when S1 marks internal substeps as image-required;
- draw a large context/problem/topology region that crowds out core mechanism anchors;
- make a detail panel or named submodule visually larger than the whole-framework main flow;
- connect two train/update/generate/evaluate modules without a S1 evidence row;
- route a carried item through a non-consuming or non-transforming module as a false relay;
- omit or ambiguously draw a dependency edge marked `must_show`;
- duplicate a connector beyond its contracted `max_visible_instances`;
- turn a grouped input label such as `A+B+C` into an unregistered semantic node;
- repeat the same artifact in two visual regions without a primary/replica or same-instance/sampled-subset marker;
- point an update or score path back into data construction without paper support;
- make a high-risk artifact receive incoming arrows from an illegal producer;
- merge inputs before a module when the paper only says those inputs are separate neighbors, signals, or consumers;
- imply any S0-forbidden artifact sharing, evaluation-source sharing, coordination pattern, same-instance reuse, or causal relation.

## No Orphan And No Decorative Connectors

Reject or regenerate any S5 image when a connector:

- points from a module to an unrelated data object;
- merges inputs without paper evidence that they are combined at that step;
- implies a training/evaluation/data-sharing relation not present in the paper;
- points from an update/control/output module back to an upstream construction, selection, transformation, or evidence-building module unless the paper explicitly states such feedback;
- connects two model boxes merely because they are visually close;
- makes a module appear to relay, receive, route, or carry an item that the module does not consume or transform;
- points opposite to the source-to-target direction specified by the connector contract;
- adds extra arrows not listed in the connector contract or not justified by an explicit lightweight S4 prompt lock;
- crosses a core module and can be mistaken as an input/output for that module;
- uses a dashed line whose meaning is unclear or conflicts with the legend.

For generated images, absence of the intended connector is usually less harmful than an invented connector. Prefer missing-safe rerun over accepting a false relation.

## Context/Core Area Budget

Complete-paper framework figures need context, but context is not automatically core. S4 must classify each region as:

- `core_mechanism`;
- `peer_primary_mechanism`;
- `bridge_or_lineage`;
- `context_or_constraint`;
- `caption_only`.

S1 must include `sketch_area_budget_by_region` for S2 sketches when context, topology, problem setup, or background cues compete with the method. S4 must include `area_budget_by_region` with approximate percentages. Default formal candidates should keep `context_or_constraint` regions at or below 15-20% of the canvas unless the paper's core contribution is the context/topology itself. If context exceeds 25%, S1/S4 must justify why that context is a core mechanism rather than background.

When the target paper defines a distinctive system setting, role constraint, access/boundary constraint, topology, or deployment assumption, compact context cues may be necessary. They should not consume space needed to show the paper's core internal mechanisms.

For main-flow plus detail-panel layouts, S1/S4 must additionally record `main_flow_area_budget`, `detail_panel_area_budget`, and `main_flow_dominance_lock`. The main framework must be the largest single area and first reader path. Each detail panel must be smaller than the main framework, and all detail panels must remain subordinate in hierarchy, contrast, and first-glance emphasis. If the generated image makes a single submodule, domain-specific block, modality/task region, formula/example panel, or detail inset the dominant region, reduce or reject it even if the internal module detail is accurate.

## Post-S5 Boundary Removed In v3.2.13

After S5, human decisions are outside this assistant workflow.

After S5, human decisions are outside this assistant workflow.

- every visible connector, edge, callout line, leader line, dashed line, bracket connector, feedback loop, merge/split line, and arrowhead;
- every required connector from the final connector inventory, including those missing from the image;
- every forbidden edge or topology listed in the final contract;
- every main-flow region, detail panel, inset, context block, legend, formula panel, domain/example block, and oversized named submodule region.

After S5, human decisions are outside this assistant workflow.

- `connector_id`;
- contracted `source_element -> target_element`;
- visible source and visible target;
- expected and visible endpoint/port binding;
- expected and visible arrowhead direction;
- expected and visible line style / arrowhead type;
- expected min/max visible instances and observed count;
- required/optional/caption-only status;
- evidence anchor or final-contract row;
- observed crossing, occlusion, label overlap, and callout-vs-data-flow ambiguity;
- result: `OK`, `MINOR-TEXT-FIX`, `MAJOR-FIGURE-FIX`, or `BLOCKER`;
- After S5, human decisions are outside this assistant workflow.

After S5, human decisions are outside this assistant workflow.

- points an arrow to the wrong destination or reverses the contracted source-target relation;
- attaches a connector to the wrong high-risk module, port, artifact, or detail panel;
- adds an unsupported shortcut, hub, feedback loop, merge, split, or decorative arrow;
- omits a must-show dependency edge without a recorded caption-only exception;
- duplicates an edge beyond the contracted maximum or makes parallel duplicate arrows semantically ambiguous;
- uses a dashed/callout/leader line whose visual grammar can be mistaken for a data-flow or model-exchange arrow;
- draws connectors across core modules or labels in a way that changes the implied relation;
- occludes or fuses distinct modules, artifacts, connector endpoints, labels, or icon tokens;
- makes a detail panel, modality/task/domain block, formula panel, example panel, or named submodule visually dominate the main framework;
- violates the contracted final area budget, main-flow dominance lock, or largest-region rule.

After S5, human decisions are outside this assistant workflow.

## Core-First Rerun Order

When an S5 candidate has both visual polish and semantic faults, rerun in this order:

1. Remove false or unsupported connectors.
2. Restore missing internal steps of core modules.
3. Restore the exact paper-defined lineage distinction, such as same instance, sampled subset, same source pool, same distribution, regenerated batch, independent run, or conceptual proxy.
4. Reduce oversized context/background regions.
5. Only then adjust style, spacing, icon polish, or caption burden.

After S5, human decisions are outside this assistant workflow.

## Portable Use Across Papers

This policy is paper-agnostic. It applies to:

- all paper-defined core modules that construct, filter, route, retrieve, plan, verify, score, aggregate, supervise, optimize, store, generate, replay, update, or otherwise transform artifacts or decisions;
- all artifacts reused in multiple paths;
- all diagrams where context/topology/problem setup competes with core mechanism area.

The general rule is: draw fewer connectors, but make every connector defensible from the paper.


## v3.2.4 issue-ledger override

Use issue-ledger audit fields for S2/S5-related review outputs: record concrete issues, severity, rerun eligibility, high-priority issue status, downstream use, and caption burden. Hard contradictions become `BLOCKER_ISSUE` records. Do not use pass/fail labels as the sole selection verdict unless the user explicitly requests a filtering/ranking mode.
