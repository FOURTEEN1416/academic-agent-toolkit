# No False Relay Data-Flow Policy v3.2.15f

This policy is mandatory whenever S1 prepares S2 prompts, S4 prepares S5 prompts, or S3 records image issues involving connectors. It is paper-neutral and must not encode any project-specific method, variable, dataset, or topology.

## Core Rule

Do not draw a connector that makes a module appear to receive, carry, route, or transfer data, variables, artifacts, metrics, model states, or control signals unless that module actually consumes, transforms, filters, stores, routes, evaluates, updates, or emits that item according to source evidence or a recorded strict logical inference.

If A produces data `x` and C consumes `x` while B does not use, transform, filter, store, or route `x`, do not draw or label A->B as carrying `x` and do not draw A->B->C as if B relays `x`. Use one of these faithful renderings instead:

- draw a direct A->C connector labeled `x` when the relation and direction are source-supported;
- attach `x` to C's input port, incoming edge, or local tag;
- use a non-directional grouping/callout only when the source supports association but not direction;
- move `x` to caption/legend when a direct visible connector would clutter the framework.

## Required Prompt Package Records

Each S1/S4 prompt package must include:

```yaml
data_consumer_transformer_ledger:
  - item: <current-paper data, variable, artifact, metric, state, or control signal>
    producer_or_source: <source module/context>
    true_consumers: [<modules that actually use the item>]
    true_transformers: [<modules that alter/filter/store/route/evaluate/update the item>]
    non_consuming_intermediates: [<nearby modules that must not be drawn as relays>]
    visual_route: direct_connector | input_port_tag | fork_or_merge_label | grouping_callout | caption_only | omitted
    evidence_anchor: <paper/S0/S1/S4/source anchor>
    rendering_decision: keep | simplify | caption_only | remove | block_for_source_rerun

false_relay_data_flow_audit:
  checked_connectors: [<connector IDs>]
  forbidden_false_relays: [<A->B(x), A->B->C(x), or equivalent patterns removed>]
  verdict: pass | revise_before_image_generation | blocked_until_replanned
```

The `edge_support_ledger`, `line_carried_variable_registry`, `routing_and_arrow_plan`, and `edge_whitelist_and_port_contract` must agree with this ledger.

## Blocking Findings

Record `false_relay_data_flow` or `false_relay_data_flow_error` when a planned or generated figure:

- labels an edge into a non-consuming module with a carried item that the module does not use;
- routes a carried item through an intermediate block only because it is visually between producer and consumer;
- makes a module look like a router, memory, filter, or transformer without source support;
- turns a caption-level dependency into a visible data-flow path through unrelated modules.

These findings block S2/S5 handoff during S1/S4 prompt preparation and must be carried as major issues during S3 review.
