# Routing Line-Style And Callout Abstraction Policy v3.2.15f

This policy is paper-neutral. Apply it whenever S1 or S4 prepares S2/S5 prompt packages, especially for figures with dashed lines, dotted lines, feedback loops, exchange links, reuse links, zooms, cutaways, insets, mechanism strips, or detail panels.

## Purpose

This policy prevents two generic failure modes:

1. line styles become overloaded, so dashed or dotted lines appear as meaningless helper rails, floating connectors, decorative routes, or visual filler;
2. a main framework module and its zoom/cutaway/detail panel show the same internal workflow, so the figure duplicates content instead of separating overview from detail.

## Line-Style Semantic Budget

Every S1/S4 prompt package must record `connector_style_semantic_budget` before writing the image-only prompt:

```yaml
connector_style_semantic_budget:
  allowed_line_families:
    - family_id: string
      visible_style: solid | dashed | dotted | bracket | thin_callout | bidirectional_exchange | other
      single_semantic_meaning: string
      allowed_endpoint_types: [module, port, fork, merge, state_tag, detail_anchor, callout_anchor]
      max_visible_instances: integer
      required_label_or_anchor: string
      forbidden_uses: [decorative, filler, unlabeled_parallel_line, cross_canvas_rail, false_relay, zoom_pointer_as_data_flow]
  dashed_line_budget:
    total_dashed_families_allowed: integer
    total_dashed_segments_allowed: integer
    long_cross_canvas_dashed_rails_allowed: false
  gate_verdict: pass | revise | block
```

Rules:

- A visible line family may carry one semantic meaning only. Do not use the same dashed style for feedback, uncertainty, similarity, communication, grouping, and zoom at the same time.
- Use solid directed arrows for the main causal/process path unless the source evidence specifically calls for exchange, feedback, reuse, or optionality.
- Prefer brackets or thin callout connectors for zoom/detail anchors. A zoom/cutaway pointer is a visual reference, not a data-flow edge.
- Every dashed or dotted connector needs named endpoints and either a visible label, a nearby anchor marker, or a recorded `required_label_or_anchor` in the prompt package.
- Long auxiliary rails across the canvas are forbidden unless the paper explicitly defines a bus, timeline, iterative loop, or shared communication channel that requires that geometry.
- If a dashed-line meaning cannot be described in one sentence with source support, remove the dashed line before handoff.

## Routing Geometry Contract

Every S1/S4 prompt package must record `routing_geometry_contract`:

```yaml
routing_geometry_contract:
  connector_routes:
    - connector_id: string
      semantic_family_id: string
      source_anchor: string
      target_anchor: string
      source_side: left | right | top | bottom | internal_port
      target_side: left | right | top | bottom | internal_port
      route_corridor: string
      max_bends: integer
      may_cross_modules: false
      may_cross_labels: false
      may_enter_non_consumer_modules: false
      max_visible_copies: 1
      omit_if_ambiguous: true
  floating_connector_guard:
    unanchored_segments_allowed: false
    decorative_segments_allowed: false
```

The image-only prompt must state: draw only the contracted connector families; do not add generic dashed helper lines, decorative rails, unlabeled auxiliary paths, or floating connectors. If an endpoint is ambiguous, omit the connector rather than inventing a visually convenient route.

## Overview / Detail Separation

For every core module that could be shown both in the main framework and in a detail view, S1/S4 must choose exactly one mode:

- `in_place_detail`: the main module itself carries the required internal mechanism; no duplicate zoom/cutaway of the same chain is allowed.
- `abstract_parent_plus_detail_panel`: the main module is abstract, and the source-grounded internal mechanism appears only in the connected detail panel/cutaway/mechanism strip.

Every S1/S4 prompt package with a detail view must record `callout_abstraction_contract`:

```yaml
callout_abstraction_contract:
  detail_strategy: in_place_detail | abstract_parent_plus_detail_panel
  module_records:
    - parent_module: string
      mode: in_place_detail | abstract_parent_plus_detail_panel
      parent_allowed_content: [module_name, one_icon, one_state_tag, one_input_port, one_output_port]
      parent_forbidden_content: [internal_step_chain, mini_algorithm, repeated_detail_glyphs, bullet_list]
      detail_panel_allowed_content: string
      detail_panel_new_information: string
      callout_connector_style: bracket | thin_callout | no_arrow_anchor
      callout_must_not_carry_flow: true
```

If a detail panel exists, it must pass `detail_panel_new_information_audit`: parent anchor, new source-grounded information, non-repetition proof, foreign-module exclusion, area budget, and callout-vs-data-flow connector style.

## Main-Detail Nonduplication Gate

Before image-only handoff, S1/S4 must record `main_detail_nonduplication_gate`:

```yaml
main_detail_nonduplication_gate:
  parent_detail_overlap: none | low | medium | high
  duplicated_internal_steps: []
  foreign_module_internals_in_panel: []
  callout_as_flow_edges: []
  verdict: pass | revise | block
```

Gate rules:

- A parent module and its detail view must not both show the same internal step chain.
- A detail panel must not import internals from another module unless the source evidence explicitly supports that combined local view.
- Callout connectors are visual references. They should normally be brackets or thin neutral lines without arrowheads, and must not be styled like data/model/control/evaluation flow.
- If the parent needs recognizable content, use only module name, one simple icon/state tag, and input/output ports. Put the internal steps in exactly one location.

## Prompt Wording Requirements

Every affected image-only prompt must include these constraints in plain language:

```text
Use only the named connector families listed in the routing contract. No generic dashed helper lines, decorative rails, floating connectors, unlabeled auxiliary paths, or cross-canvas dashed tracks. Every dashed/dotted segment must have an explicit source, target, semantic meaning, and label/anchor. If any connector endpoint is ambiguous, omit the connector.

If a zoom, cutaway, inset, mechanism strip, or detail panel is used, keep the parent main-flow module abstract: module name plus at most one simple icon/state tag and input/output ports. Put internal steps only in the detail view. Do not repeat the same mini-chain in both the parent module and the detail view. Use brackets or thin non-flow callouts; do not use data/model/control arrows as zoom pointers.
```

## S3 Issue Categories

S3 issue ledgers must use these reusable categories when visible candidates fail this policy:

- `meaningless_dashed_line`
- `line_style_semantic_overload`
- `floating_or_unanchored_connector`
- `long_auxiliary_rail`
- `main_detail_duplicate`
- `foreign_detail_import`
- `callout_as_flow_error`

## S4 Transfer

When S3 records any issue above, S4 must transfer it into hard prompt constraints rather than a soft preference. The usual repairs are to reduce connector families, replace flow-like callouts with brackets, make the parent module abstract, move duplicated internal steps to exactly one location, and remove dashed/dotted segments whose endpoints or semantics cannot be source-supported.
