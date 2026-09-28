# Edge-Label-First And Internal-Motif Prompt Policy v3.2.11

After S5, human decisions are outside this assistant workflow.

This policy is intentionally **paper-agnostic**. It must not encode facts from any particular paper, dataset, method family, project, uploaded example, generated candidate, or prior run. Project outputs may instantiate the rules below with the current paper's source-grounded terms only.

## Purpose

Framework figures should communicate operations and mechanisms, not turn every variable into a small block. The default visual grammar is:

```text
large boxes/panels  = source-grounded modules, operations, systems, or regions
line labels/tags    = intermediate artifacts, variables, metrics, weights, parameters, masks, scores, and carried states
micro-motifs        = compact visual sub-processes inside core compound modules
caption/legend      = definitions that do not need first-glance pixels
```

This policy hardens two generic failure modes:

1. variables, metrics, pseudo-outputs, and pass-through artifacts become standalone chips/blocks even when they should be written on connectors;
2. core compound modules become empty titled boxes or bullet-list text boxes instead of showing a small visual mechanism.

## 1. Edge-Label-First Artifact Policy

Before image prompt generation, every non-module term must be assigned a rendering plan. A non-module term includes artifacts, intermediate variables, pseudo-outputs, tensors, latent states, scalar metrics, scores, losses, weights, probabilities, masks, thresholds, schedules, parameters, and model-state labels.

Required field:

```yaml
edge_label_first_artifact_policy:
  default_rule: inline_edge_label
  terms:
    - term: <current-paper term or symbol>
      semantic_role: pass_through_variable | intermediate_output | material_artifact | metric_or_score | weight_or_parameter | model_state | constraint_note | caption_only
      planned_rendering: inline_edge_label | port_label | attached_tag | labeled_fork_or_merge | small_artifact_glyph | standalone_module_box | caption_only | removed
      standalone_box_allowed: true|false
      standalone_box_exception_reason: <required when true>
      evidence_anchor: <paper/S0/S1/S4/source anchor>
  gate_verdict: pass | revise_before_image_generation | blocked_until_replanned
```

Default: `inline_edge_label`.

A non-module term may become a `small_artifact_glyph` only when the current paper/source evidence and reader path require it to be seen as a distinct object that is stored, sampled, branched, mixed, evaluated, compared, cached, queued, retrieved, or reused as material. Even then, it must remain visually subordinate to primary modules.

A non-module term may become a `standalone_module_box` only with an explicit source-grounded exception. The exception must explain why the term itself functions as a paper-level operation/module rather than an object or label.

## 2. Semantic Graph And Visual Render Graph Separation

Machine-readable semantic graphs may contain artifact nodes for audit and lineage. Image prompts must not expose those audit nodes as visible node obligations unless the visual render graph explicitly promotes them.

Required fields:

```yaml
machine_semantic_graph:
  purpose: audit all source-grounded entities, artifacts, states, variables, and relations
  may_include_artifact_nodes: true
  visible_rendering_authority: false

visual_render_graph:
  purpose: what the image generator is allowed to draw as visual objects
  large_nodes_only: [<primary modules and justified context containers>]
  artifact_node_conversion:
    - semantic_node_or_term: <id or term>
      visual_conversion: inline_edge_label | port_label | attached_tag | labeled_fork_or_merge | small_artifact_glyph | caption_only | removed
      standalone_box_allowed: true|false
      exception_reason: <required if true>
```

Hard gate: if a term's `planned_rendering` is `inline_edge_label`, `port_label`, `attached_tag`, or `labeled_fork_or_merge`, that term must not appear as a visible node label in the image-only prompt. It belongs only in edge/port/connector annotation fields.

## 3. Split Visible Text Contract

Do not use one flat visible-text whitelist for all visible strings. Each prompt package must split text by rendering role:

```yaml
visible_text_contract:
  visible_node_labels:
    - <primary module, justified context, macro group, or allowed glyph label>
  visible_edge_or_port_labels:
    - <carried artifact, variable, metric, weight, parameter, branch label, merge label>
  visible_internal_micro_labels:
    - <short labels inside compound modules; normally 1-4 words each>
  visible_legend_or_caption_labels:
    - <definitions or constraints allowed outside the main flow>
  internal_text_blacklist:
    - node_id
    - edge_id
    - port_id
    - group_id
    - lane_id
    - candidate_id
    - schema keys
    - audit terms
    - file paths
```

Only `visible_node_labels` may appear inside standalone boxes or panels. `visible_edge_or_port_labels` must be written directly on connectors, port stubs, bus/fork labels, or attached tags. The prompt must explicitly forbid enclosing those labels in rectangles, rounded rectangles, bubbles, chips, cards, circles, or standalone nodes unless the `edge_label_first_artifact_policy` records an exception.

## 4. Line-Carried Variable Registry

Every carried non-module term must be registered on a line, port, bus, fork, merge, or tag before image prompting.

Required field:

```yaml
line_carried_variable_registry:
  - term: <current-paper term or symbol>
    source_visual_element: <module/group/port or source edge family>
    target_visual_element_or_group: <module/group/port or target edge family>
    carried_semantics: data_or_artifact | model_state | control_or_gate | evaluation_metric | weight_or_score | branch_or_merge | caption_only
    render_as: inline_edge_label | port_label | attached_tag | labeled_fork_or_merge | no_visible_label
    standalone_box_allowed: false
    exception_reason: null
    evidence_anchor: <paper/S0/S1/S4/source anchor>
```

For outputs that immediately feed the next module, place the output name on the outgoing connector near the arrowhead. For outputs that branch, use one labeled fork connector. For multi-input modules, use one merge/bus connector with inline labels instead of separate parallel artifact boxes.

Do not create false relay labels. A carried variable or artifact may be placed only on a connector, port, fork, merge, or tag that reaches a module that actually consumes, transforms, filters, stores, routes, evaluates, updates, or emits it. If A produces `x` and C consumes `x` while B does not use `x`, do not label A->B with `x`; label the true A->C relation, C's input port, or a caption/legend entry instead.

## 5. Compound Module Internal Visual Motif Plan

Merging low-level steps into a compound module does not authorize an empty or text-only box. For every source-grounded core compound module, plan a tiny visual mechanism.

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

Prompt wording must say: draw a tiny visual mini-process, not a bullet list; use 2-4 micro-glyphs connected by small arrows; labels are annotations, not substitutes for the mechanism. If a core module has no known internal visual motif, either move it to a simpler non-core block, request author clarification, or block prompt generation until the core-detail contract is resolved.

## 6. Prompt Contradiction Audit

Before saving an image-only prompt, scan for contradictions between planned rendering and prompt wording.

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

If a term is planned as an edge/port label, the image-only prompt must not call it a chip, token, block, node, card, box, or rounded rectangle. Use wording such as `write the symbol directly on the connector`, `label the outgoing edge`, `place the term beside the port`, or `mark the fork with this label`.

## 7. Image-Only Prompt Wording Requirements

Every S2/S5 image-only prompt must include these rules, adapted to the current paper's terms:

```text
Only primary modules and justified context containers may be standalone boxes.
Intermediate variables, artifacts, metrics, weights, parameters, and model-state labels default to edge labels, port labels, fork/merge labels, or attached tags.
Do not enclose edge/port labels in boxes, rounded rectangles, bubbles, chips, cards, circles, or standalone nodes.
For branching outputs, draw one labeled fork connector instead of repeated artifact boxes.
For multi-input operations, draw one labeled merge/bus connector instead of separate parallel artifact boxes.
Inside each core compound module, draw a tiny visual mini-process with micro-glyphs and small arrows; do not satisfy the module internals with a bullet list or title-only box.
```

## 8. Audit Issue Categories

S3 review and `deleted_text_recheck` must add issue-ledger entries for:

- `edge_label_eligible_box_error`: a term that should be an edge/port/fork/merge label is drawn as a standalone chip, card, rectangle, bubble, or node;
- `false_relay_data_flow_error`: a term is drawn on an edge into or through a module that does not consume, transform, store, route, evaluate, update, or emit it;
- `line_carried_variable_missing`: a carried variable is neither visible on the connector nor defined by a valid caption/legend plan;
- `visual_render_graph_violation`: a semantic graph artifact node was rendered as a visual node without exception;
- `text_only_core_mechanism_error`: a core compound module contains only a title, empty box, or bullet text while the source requires visible internal mechanism;
- `bullet_list_substitution`: a required internal mechanism was replaced by a vertical text list rather than micro-glyphs or a mini-chain;
- `prompt_rendering_contradiction`: prompt wording asks for labels-on-lines but also instructs the generator to draw chips/tokens/boxes for the same term;
- `unbundled_line_carried_variables`: compatible carried variables are drawn as separate repeated lines or boxes rather than a bus/fork/merge connector.

These issues are generic. Project output descriptions may instantiate them with current-paper terms, but reusable skill files must remain paper-neutral.

## 9. Stage Parity And Rerun

After S5, human decisions are outside this assistant workflow.

- edge-label-first classification;
- visual render graph conversion;
- line-carried variable registry;
- visible text split by node vs edge/port role;
- internal visual motif planning for core compound modules;
- prompt contradiction audit;
- issue-ledger recording of visible variable-as-box and text-only-mechanism failures.

An explicit upstream rerun prompt must carry forward the same edge-label and internal-motif contracts. It may change only issue-ledger-scoped defects unless the user explicitly authorizes a broader rerun.
