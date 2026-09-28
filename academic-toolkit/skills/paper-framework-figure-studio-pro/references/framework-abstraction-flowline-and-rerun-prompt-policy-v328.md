# Framework Abstraction, Flowline Semantics, And Rerun-Prompt Parity Policy v3.2.8 + v3.2.11 Edge-Label/Internal-Motif Addendum

Use this policy whenever S2/S5, or any future image-stage, prepares or audits a framework, architecture, pipeline, method-overview, workflow, mechanism, data-flow, model-flow, or rerun image prompt. Also apply `references/edge-label-first-and-internal-motif-policy-v3211.md` for line-carried variables, visual render graph conversion, internal visual motifs, and prompt contradiction audits. It is generic and paper-agnostic. It must not encode facts from a particular paper, dataset, method family, user project, uploaded image, or prior run. Project outputs may instantiate these rules with the current paper's own evidence and terms only.

## Purpose

Framework figures must show the method's semantic structure at an appropriate abstraction level. They should not turn every intermediate variable, temporary output, scalar, threshold, metric, or edge annotation into a separate visual module. They must also make each arrow's meaning explicit in the prompt contract so audits can compare the image against the paper/source evidence.

This policy closes four common prompt failures:

1. treating pass-through symbols or intermediate variables as boxed modules;
2. over-decomposing a framework into many equally weighted micro-boxes;
3. drawing unsupported or duplicate arrows because a variable appears near a module;
4. weakening S5 or upstream rerun prompts relative to S2 by omitting graph, line-type, or source-evidence checks;
5. using bullet lists or title-only boxes instead of compact visual sub-processes inside source-grounded core modules.

## Entity / Artifact / Symbol Classification Gate

Before writing `node_registry`, classify every planned visible item with `visual_semantic_class`:

| Class | Meaning | Default visual treatment |
| --- | --- | --- |
| `actor_or_context` | paper-defined participant, condition, environment, or repeated population marker | compact chip/container/context marker |
| `module_or_operation` | transformation, training step, aggregation step, inference step, model, or mechanism with a semantic role | visible module/card/gate |
| `material_artifact` | data/model object that is produced, stored, branched, reused, evaluated, or mixed as a distinct object | visible artifact token only when needed for branching or lineage |
| `inline_symbol` | scalar, variable, temporary output, pseudo-output, score, loss, threshold, edge annotation, or pass-through quantity | line label / port label / small inline tag, not a standalone box by default |
| `control_parameter` | threshold, schedule, hyperparameter, control signal, or gate condition | merge into the controlled gate/module or show as a small attached tag; not equal-weight module by default |
| `caption_only` | useful but not necessary for first-glance pixel meaning | move to caption/legend/body text |

`inline_symbol` and `control_parameter` items must not become standalone nodes unless the current paper and reader path require visible branching, comparison, or reuse and the exception is recorded. When kept as visible text, they should normally be rendered as **inline edge labels, port labels, labeled fork/merge labels, or small tags attached to a module**. Do not call these terms chips/tokens/boxes in the image prompt unless a small-artifact-glyph exception is recorded.

Required prompt-package field:

```yaml
symbol_entity_classification:
  - paper_term_or_symbol: <current-paper term>
    visual_semantic_class: actor_or_context | module_or_operation | material_artifact | inline_symbol | control_parameter | caption_only
    planned_rendering: visual_node | inline_edge_label | port_label | attached_tag | labeled_fork_or_merge | small_artifact_glyph | caption_only | removed
    node_exception_reason: <required only if inline_symbol/control_parameter becomes a node>
    evidence_anchor: <paper/S0/S1/S4/source anchor>
```

## Variables And Intermediate Outputs As Edge Labels

A variable-like output should be drawn on the connector that carries it, rather than as its own box, when all of the following hold:

- it is produced by one module and immediately consumed by one or more known downstream modules;
- it has no internal mechanism to show;
- it is not a persistent store, model, actor, or paper-primary object whose visual identity matters;
- making it a box would add clutter or imply an extra processing step.

Use a compact connector label such as `<symbol>` near the arrow, or a merge connector with multiple inline labels. This applies generically to pseudo-label variables, latent variables, logits, scores, losses, weights, probabilities, masks, schedules, small validation subsets, scalar metrics, and similar mathematical quantities. If such an item branches to two consumers, use one labeled split connector, not two duplicated variable boxes unless the artifact is explicitly a material object.

Required prompt-package field:

```yaml
edge_annotation_registry:
  - annotation_id: A_...
    text: <visible mathematical symbol or short phrase>
    attaches_to_edge_ids: [E_...]
    annotation_role: carried_data | carried_model_state | control_value | evaluation_value | branch_label | caption_only
    render_mode: inline_edge_label | port_tag | merge_label | no_visible_label
    evidence_anchor: <paper/S0/S1/S4/source anchor>
```

The visible-text whitelist must distinguish `visible_node_labels` from `visible_edge_or_port_labels`. A symbol may be whitelisted for an edge label without authorizing a separate visible box.

## Semantic Graph Versus Visual Render Graph Gate

Semantic graphs may contain artifact nodes for audit, lineage, and source coverage. A visual prompt must be compiled from a separate `visual_render_graph` that contains only visible objects the image generator may draw.

Required fields:

```yaml
machine_semantic_graph:
  may_include_artifact_nodes: true
  visible_rendering_authority: false

visual_render_graph:
  large_nodes_only: [<primary module ids and justified context containers>]
  artifact_node_conversion:
    - semantic_node_or_term: <id or term>
      visual_conversion: inline_edge_label | port_label | attached_tag | labeled_fork_or_merge | small_artifact_glyph | caption_only | removed
      standalone_box_allowed: true|false
      exception_reason: <required if true>
```

Hard gate: any term planned as `inline_edge_label`, `port_label`, `attached_tag`, or `labeled_fork_or_merge` must be removed from the visible node registry and represented only in edge/port/annotation registries. If the same term appears both as a visible node label and as an edge/port label without a dual-render exception, the prompt is not ready.

## Line-Carried Variable Registry

Every temporary output, pseudo-output, metric, score, weight, control value, carried parameter, or pass-through artifact must be mapped to a connector, port, fork, merge, or caption before image prompting.

Required field:

```yaml
line_carried_variable_registry:
  - term: <current-paper term or symbol>
    source_visual_element: <module/group/port or source connector family>
    target_visual_element_or_group: <module/group/port or target connector family>
    carried_semantics: data_or_artifact | model_state | control_or_gate | evaluation_metric | weight_or_score | branch_or_merge | caption_only
    render_as: inline_edge_label | port_label | attached_tag | labeled_fork_or_merge | no_visible_label
    standalone_box_allowed: false
    exception_reason: null
    evidence_anchor: <paper/S0/S1/S4/source anchor>
```

For outputs that immediately feed the next module, place the output name on the connector. For outputs that branch, use one labeled fork connector. For multi-input operations, use a merge/bus connector with inline labels. Standalone artifact glyphs remain exceptions, not the default.

## Internal Visual Motif Gate For Compound Modules

A framework overview should merge low-level details into compound modules, but a source-grounded core module must not become an empty titled box or a text-only bullet list.

Required field:

```yaml
internal_visual_motif_plan:
  - parent_module: <current-paper module name>
    core_module: true|false
    abstraction_level: compact | medium | detailed
    internal_layout: mini_chain | stacked_motifs | side_cutaway | micro_pipeline | caption_assisted
    visual_motifs:
      - source_step: <paper-grounded substep or operation>
        motif_type: sample_variants | multi_model_votes | histogram_confidence | threshold_gate | selector_filter | merge_sets | generate_samples | denoise_or_transform | evaluate_gauge | score_to_weight | weighted_peer_update | memory_lookup | routing_switch | compare_paths | custom_source_grounded_motif
        visual_description: <how to draw the motif without paper-specific hardcoding>
        max_words: <0-4 recommended>
        evidence_anchor: <paper/S0/S1/S4/source anchor>
    text_only_allowed: false
    bullet_list_allowed: false
    motif_gate_verdict: pass | revise_before_image_generation | blocked_until_replanned
```

Image prompts must say `draw a tiny visual mini-process, not a bullet list` for core compound modules. Labels may annotate the motif, but text must not replace the motif.

## Prompt Contradiction Audit

Before saving an image-only prompt, run a contradiction audit that checks whether planned edge/port labels are later described as chips, tokens, boxes, cards, or nodes.

Required field:

```yaml
prompt_contradiction_audit:
  contradictions:
    - term: <term or symbol>
      planned_rendering: <planned_rendering>
      conflicting_prompt_phrases: [chip, token, box, card, node, output block, small rectangle]
      fix: replace_with_edge_label_wording | add_exception_reason | move_to_caption | remove_term
  verdict: pass | revise_before_image_generation | blocked_until_replanned
```

## Framework-Level Granularity Gate

Before saving any S2/S5 image prompt, create an `element_granularity_plan`. The plan decides which source-grounded details deserve full module boxes and which should be merged, attached, line-labeled, or moved to caption.

Required field:

```yaml
element_granularity_plan:
  figure_role: framework_overview | architecture | pipeline | mechanism_explainer | scoped_detail | comparison
  granularity_target: coarse | medium | detailed
  elements:
    - paper_term: <current-paper term>
      source_role: core_module | substep | parameter | intermediate_symbol | artifact | metric | context | constraint
      planned_rendering: full_node | compound_module_internal_token | attached_tag | edge_label | grouped_icon | caption_only | removed
      merge_group: <optional compound module id>
      why_this_level: <reader-path and evidence reason>
      clutter_risk: low | medium | high
```

A framework overview should prefer **compound modules with a few internal visual motifs or mini-chain glyphs** over separate equal-weight boxes for every substep. Split a substep into a standalone node only when it has a distinct source-supported input/output, branch, evaluation role, or reader-critical mechanism. Otherwise keep it in the parent module as an icon, stacked micro-motif, attached tag, connector label, or caption phrase.

Micro-operation pairs that function as a gate/parameter pair should generally be rendered as one compound gate with an attached control tag. Do not separate a threshinactive from its filter, a schedule from its sampler, a confidence score from its selector, or a local hyperparameter from its controlled module unless the current paper's source evidence makes that separation necessary for the figure's main question.



## Reviewer-First-Glance Entity Density Gate

Before prompt finalization, compute an `entity_density_budget` from the figure role, canvas, and primary reader path. The budget is paper-agnostic and must be derived for each project; it must not hard-code a method, dataset, candidate ID, or expected number of modules.

Required field:

```yaml
entity_density_budget:
  primary_reader_path_steps: [<3-7 concise semantic steps, source-grounded>]
  top_level_module_budget: <derived from reader path and canvas; not a fixed package constant>
  full_node_count_planned: <count>
  inline_symbol_count_planned: <count>
  compound_module_count_planned: <count>
  density_verdict: sparse | balanced | busy_but_justified | too_dense
  merge_actions:
    - <paper term or planned node> -> <compound module / edge label / attached tag / caption_only>
  first_glance_risk: low | medium | high
```

If `density_verdict` is `too_dense`, the prompt is not ready. Merge low-level entities, demote pass-through symbols to edge labels, or move caption-support details out of the image before image generation. Reviewers should be able to identify the main method backbone and contribution path without tracing every micro-operation or temporary variable.

## Compound Gate And Parameter Merge Rule

A gate and its governing scalar/parameter are usually one visual unit. Render the gate as a compound module with the parameter as an attached tag or line label unless the paper's main claim explicitly requires separating them. This rule covers, generically, threshold-filter pairs, confidence-selector pairs, schedule-sampler pairs, loss-weight-training pairs, and metric-weighting pairs.

Required field:

```yaml
compound_gate_registry:
  - compound_gate_id: CG_...
    controlled_operation: <module/gate>
    attached_parameter_or_symbol: <inline/control symbol>
    render_mode: compound_module | attached_tag | edge_label
    separation_exception_reason: <required if parameter and gate are separate full nodes>
    evidence_anchor: <paper/S0/S1/S4/source anchor>
```

## Input/Output Symbol Line-Label Rule

Temporary method variables, pseudo-outputs, metric values, and carried parameters should normally be written on the line that carries them. The prompt must specify whether the visible mathematical symbol is a data/artifact label, model-state label, control label, evaluation/metric label, or branch label. The symbol label must not imply that a new processing module exists.

For split or merge routes, prefer a single fork/merge connector with one or more edge labels rather than separate standalone boxes for each variable. A separate artifact glyph is allowed only when the artifact must be visually stored, branched, sampled, evaluated, mixed, compared, cached, queued, or reused as a distinct paper-primary object, and the exception must be recorded in `edge_label_first_artifact_policy`.

## Flowline Semantic Typing

Every line, arrow, connector, bracket, callout, merge, split, loop, and feedback relation in S2/S5 prompt packages must have a `flow_semantics` field. The image prompt must state the flow semantics in words even when the final pixels will not visibly print those words.

Allowed baseline types:

```text
data_or_artifact_flow
model_state_or_reference_flow
control_or_gating_flow
evaluation_or_metric_flow
communication_or_exchange_flow
conceptual_dependency
containment_or_grouping
callout_or_zoom
next_round_or_reuse
no_arrow_association
```

For each edge, record:

```yaml
flow_semantics_registry:
  - edge_id: E_...
    flow_semantics: data_or_artifact_flow | model_state_or_reference_flow | control_or_gating_flow | evaluation_or_metric_flow | communication_or_exchange_flow | conceptual_dependency | containment_or_grouping | callout_or_zoom | next_round_or_reuse | no_arrow_association
    visible_line_style: solid | dashed | dotted | bracket | no_arrow_grouping
    visible_arrowhead: target | both | none
    should_visible_label_flow_type: false
    prompt_wording: <plain-language line/arrow meaning for image generator>
    evidence_anchor: <paper/S0/S1/S4/source anchor>
```

Stage prompts must avoid vague connector instructions. Write prompts with statements like `solid arrow meaning local data/artifact flow`, `dashed arrow meaning exchanged model state/reference`, or `dotted arrow meaning control/next-round reuse`. The words need not be printed in the figure unless deliberately whitelisted.

## Direction And Input-Eligibility Gate

A module input is legal only when the paper, algorithm, equation, source-grounded S0/S1/S4 contract, or author clarification supports both the relation and direction. Do not route a data item into a module merely because it is visually nearby, belongs to the same local entity, or appears elsewhere in the method.

For every module, record `module_input_contract`:

```yaml
module_input_contract:
  - module_node_id: N_...
    module_display_label: <visible label>
    allowed_input_families:
      - data_or_artifact_flow
      - model_state_or_reference_flow
      - control_or_gating_flow
      - evaluation_or_metric_flow
    allowed_inputs:
      - source_node_or_annotation: <node id or annotation id>
        role: <why it enters this module>
        evidence_anchor: <paper/S0/S1/S4/source anchor>
    forbidden_inputs:
      - source_node_or_annotation: <unsupported input>
        reason: <why drawing it would be misleading>
```

If an item is relevant context but not an input, show it as a nearby context chip, bracket, or caption-only note rather than an arrow into the module. Do not infer that every local artifact enters every local module; local availability, shared container membership, or visual proximity is not input evidence.

## Edge Cardinality And Duplicate-Line Gate

A prompt must not create duplicate arrows between the same source and target with the same direction, line style, and semantics. Duplicate or converging lines are allowed only when they carry different source-supported roles, distinct artifacts, distinct model states, or intentionally separate lanes.

Required audit field:

```yaml
edge_cardinality_audit:
  duplicate_source_target_pairs: []
  duplicate_allowed_with_distinct_roles: []
  merge_or_split_connectors_used: [<edge ids or connector family ids>]
  redundant_edge_fix: remove | merge | convert_to_inline_label | route_to_caption | not_needed
```

When two variable labels feed the same module as alternative or joint inputs, prefer a single merge connector with inline labels, or one multi-input gate. Do not draw two identical arrows from the same variable/source into the same module unless the source evidence says they are separate roles.

## Post-S5 Boundary Removed In v3.2.13

After S5, human decisions are outside this assistant workflow.

- source-grounded element support;
- entity/artifact/symbol classification;
- element granularity plan;
- semantic graph vs visual render graph separation;
- visible node-label vs edge/port-label whitelist separation;
- edge-label-first artifact policy and line-carried variable registry;
- internal visual motif plan for source-grounded core compound modules;
- prompt contradiction audit;
- exact edge registry with `flow_semantics`;
- module input contract;
- edge cardinality audit;
- forbidden-edge/topology checks;
- prompt-file-read audit when prompts are file-handoff assets.

After S5, human decisions are outside this assistant workflow.

## Rerun Prompt Parity

After S5, human decisions are outside this assistant workflow.

Required rerun fields:

```yaml
rerun_prompt_parity_audit:
  source_prompt_path: <path>
  source_prompt_hash: <hash>
  issue_ledger_path: <path>
  semantic_graph_spec_carried_forward: true|false
  visible_text_whitelist_carried_forward: true|false
  edge_annotation_registry_carried_forward: true|false
  line_carried_variable_registry_carried_forward: true|false
  visual_render_graph_carried_forward: true|false
  internal_visual_motif_plan_carried_forward: true|false
  flow_semantics_registry_carried_forward: true|false
  element_granularity_plan_carried_forward: true|false
  module_input_contract_carried_forward: true|false
  rerun_delta_only_changes_listed_issues: true|false
  no_new_uncontracted_elements_or_edges: true|false
  stage_style_preserved_or_explicitly_authorized: true|false
```

Rerun image prompts must say which errors to remove, but they must also restate the core allowed structure, edge semantics, edge-label-first variable rules, internal visual motif requirements, and forbidden shortcuts. Do not pass a upstream rerun prompt that only says "fix the arrows", "make it cleaner", "remove clutter", or "correct the wrong module" without rebuilding the full prompt contract.

## Audit Additions

S2/S5 text reviews must add issue categories for:

- `symbol_as_box_error`: intermediate variables or control values became full modules without justification;
- `edge_label_eligible_box_error`: a carried term that should be an edge/port/fork/merge label became a standalone chip, card, rounded rectangle, bubble, or node;
- `line_carried_variable_missing`: a carried term is neither visible on its contracted connector nor safely caption/legend-supported;
- `visual_render_graph_violation`: a semantic graph artifact node leaked into the visible render graph without exception;
- `text_only_core_mechanism_error`: a core compound module is title-only, empty, or only a bullet list when internal visual motifs are required;
- `bullet_list_substitution`: the image replaced required internal micro-motifs with a text list;
- `over_decomposition`: framework-level figure split too many micro-operations into equal-weight boxes;
- `unsupported_module_input`: an arrow enters a module without evidence-supported input eligibility;
- `duplicate_edge`: redundant edge(s) share the same source, target, semantics, and role;
- `flow_semantics_mismatch`: drawn line style or direction contradicts its intended data/model/control/evaluation semantics;
- `rerun_contract_drift`: explicit upstream rerun prompt or reruned image lost the original semantic contract.

These categories are generic; the audit description should instantiate them with the current paper's terms in project outputs only.

## Non-Hardcoding And Portability

This policy must remain project-neutral. It must not name a target paper, dataset, method, author, project ID, user file path, generated candidate ID, or uploaded example as reusable doctrine. It defines checks and fields. Current-run reports may cite current-paper variables or examples, but reusable skill files must not bake them in.
