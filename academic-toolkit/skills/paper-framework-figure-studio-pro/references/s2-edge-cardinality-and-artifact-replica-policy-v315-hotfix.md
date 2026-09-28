# S2 Edge Cardinality And Artifact Replica Policy v3.1.6 Hotfix

After S5, human decisions are outside this assistant workflow.

## Why This Policy Exists

Connector allowlists and port bindings are not enough when the prompt or generated image uses:

- compound input labels such as `A + B + C`;
- branch nodes or merge gates;
- repeated copies of the same artifact in different lanes;
- visually ambiguous gaps where a required dependency arrow should be;
- parallel arrows that may look like two different dependencies.

In these cases, the generated sketch can obey the broad allowed-edge set while still misleading the reader about the paper model. S2 must therefore lock edge cardinality, dependency visibility, compound input encoding, and repeated-artifact semantics before image generation.

## Required S1 Fields

Every S1 sketch candidate card must include these fields in addition to the existing model, connector, lineage, area, and core-module locks:

- `semantic_graph_spec`: a non-visible structured node/port/edge graph with unique internal `node_id`, `edge_id`, and `port_id` values, visible display-label whitelist, and an internal-ID blacklist.
- `sketch_edge_cardinality_contract`: for every required or optional connector, state unique internal `connector_id` / `edge_id`, `source_node_id`, `target_node_id`, `required_or_optional`, `min_visible_instances`, `max_visible_instances`, `target_port`, `line_style`, and whether parallel duplicates are forbidden.
- `sketch_dependency_edge_must_show`: the dependency edges that must be visible as an unbroken arrow with a readable arrowhead at the target port. If a dependency can be carried only by caption, it must be listed as caption-only and must not be drawn as a half-edge.
- `sketch_compound_input_policy`: how multi-input modules are drawn. Choose exactly one representation per module:
  - direct multi-input arrows from each source artifact to the module's input ports; or
  - a small merge gate with one incoming arrow from each source and exactly one outgoing arrow to the module; or
  - a compact grouped input label treated as a label only, with no extra semantic node.
- `sketch_artifact_replica_policy`: whether an artifact may appear more than once, which copy is the primary node, which copies are visual replicas/proxies, how same-instance or sampled-subset status is marked, and how to prevent readers from inferring a new producer.
- `sketch_visible_edge_inventory_template`: a blank table S2 must fill after generation, listing every visible connector extracted from the returned image and mapping it back to exactly one internal `edge_id`.

If any of these fields are missing, S2 must stop and request S1 rerun before generating or continuing sketches.

## Edge Cardinality Rules

Every connector must have a unique internal edge ID and a maximum visual instance count. Internal IDs are never visible text; they are used only for matching generated connectors back to the contract. Default is exactly one visible instance:

```text
edge_id:
  source:
  target:
  required_or_optional:
  min_visible_instances:
  max_visible_instances:
  target_port:
  line_style:
  parallel_duplicate_policy: forbidden
```

Parallel duplicates are forbidden unless the paper explicitly describes multiple distinct signals of the same relation and the card gives each signal a separate connector ID and meaning.

If a generated image draws two arrows with the same source, target, and semantic relation, audit fails unless the S1 card explicitly allowed two instances. If a generated image draws one connector as both a direct arrow and a grouped-label arrow, audit fails unless the grouped label is visually non-semantic and not drawn as a connector target.

## Required Dependency Visibility

Important dependencies must be visible, not implied by spatial proximity or a loose label.

For every `sketch_dependency_edge_must_show` item, S2 post-generation audit must verify:

- source node is visible or validly compressed;
- target node is visible;
- arrow shaft is unbroken enough to be read;
- arrowhead lands on the correct target or target port;
- the edge direction is clear;
- no label or nearby connector makes the source/target ambiguous.

If a required dependency edge is missing, ambiguous, hidden behind a label, or visually swallowed by a merge box, the sketch must be marked `FLAG_MAJOR` or `BLOCKED` unless a fresh regeneration reruns it.

## Compound Input Policy

Compound labels such as `<artifact_A> + <artifact_B> + <artifact_C>` are high-risk because image models often treat them as new intermediate nodes. S1/S2 must decide the encoding before prompt generation using current-paper artifact names only in project outputs.

Allowed patterns:

1. `direct_ports`: draw one arrow from each source artifact to the module input port. Do not also draw a grouped `A+B+C` box as a semantic node.
2. `merge_gate`: draw a small gate labeled `merge` or `inputs`; each source has one arrow into the gate; the gate has exactly one arrow to the module. The gate is not a new algorithmic module unless the paper says so.
3. `grouped_label_only`: place text like `<artifact_A> + <artifact_B> + <artifact_C>` next to the module as a label. Do not draw separate arrows into the label and then another arrow from the label if that would create an unregistered intermediate node.

Forbidden patterns:

- drawing both direct source arrows to a module and a separate grouped input box that also points to the module;
- drawing two visually parallel arrows from the same artifact or same grouped source to the same module;
- hiding a required input by mentioning it only inside a label when the contract says that input edge must be visible;
- letting a grouped input expression become a new producer of downstream artifacts.

## Artifact Replica Policy

When the same artifact must appear in more than one visual region, the card must classify the copies:

```text
artifact_id:
  primary_node:
  replica_nodes:
  replica_relation: same_instance | sampled_subset | same_distribution | conceptual_proxy
  required_visual_marker:
  allowed_connectors_from_replica:
  forbidden_inference:
```

Default rule: prefer one primary artifact node and route legal branches from it. If layout requires a repeated copy, the repeated copy must be marked as a visual replica/proxy such as `<artifact> (same local pool)` or `<artifact> ref`, with a same-instance marker. It must not receive a producer arrow unless it is the primary produced artifact.

For sampled subsets, the subset is a new child artifact with its own source-defined label, such as `<artifact_subset>`, and must be connected by a contracted sampling/selection relation from the primary source object or pool. Do not draw a second unmarked copy of `<artifact>` beside `<artifact_subset>` if readers could infer a second source object, pool, run, or batch.

## Post-Generation Visible Edge Inventory

After each generated S2 sketch, before accepting or registering it as usable, fill a visible-edge inventory:

```text
visible_edge_id:
  perceived_source:
  perceived_target:
  line_style:
  arrowhead_visible:
  matched_contract_edge_id:
  pass_fail:
  reason:
```

Also fill an artifact replica inventory:

```text
visible_artifact_label:
  count:
  primary_or_replica:
  relation_marker_visible:
  legal_producer_visible:
  risk:
```

If a visible connector or artifact copy cannot be matched to exactly one internal edge/node ID in the contract with low ambiguity, or if an internal ID string is visibly rendered in the figure, the sketch cannot be marked as clean. The audit should prefer a `FLAG_MAJOR` or `BLOCKED` status over accepting a false topology as `PASS`.

## Prompt Compilation Requirements

S2 prompts must include compact operational wording for the high-risk cases:

- "Do not create compound input boxes as semantic intermediate nodes."
- "Use exactly one arrow for internal connector `<edge_id>`, but do not draw the `<edge_id>` text."
- "For multi-input module `<M>`, use `<direct_ports | merge_gate | grouped_label_only>`."
- "Artifact `<A>` appears once as the primary node; if repeated, label the copy as `<same instance/proxy>`."
- "Required dependency `<source_node_id -> target_node_id>` must be visible with arrowhead at `<target_port>`, but draw only display labels, not internal IDs."

When the prompt contains a label such as `A + B + C`, it must immediately state whether that label is a node, a merge gate, or label-only.

## Audit Failure Triggers

Mark the sketch `FLAG_MAJOR` or `BLOCKED` when any of the following occur:

- a required dependency edge is absent or ambiguous;
- a visible arrow has no internal edge ID in the contract;
- an allowed connector appears more times than permitted;
- any internal node/edge/port/group/lane ID is visible in the generated figure;
- a compound input label behaves like an unregistered producer;
- direct arrows and a grouped input box duplicate the same dependency;
- repeated artifact copies are unmarked and can be read as distinct pools, batches, memories, tests, or generated sets;
- a sampled subset is shown without its contracted source object/pool or with multiple competing sources;
- an update, score, or weight path visually terminates before the update target despite being a required dependency.

## Portable Use Across Papers

This policy applies to any paper figure with generated, selected, retrieved, validated, scored, weighted, stored, replayed, supervised, or otherwise reused artifacts, plus any multi-input module whose visual copies or edges could change the paper meaning.

General rule: first decide how many times every edge and artifact may appear, then draw. A correct graph drawn once is better than a rich sketch with duplicated or ambiguous dependencies. If a flagged sketch is carried forward, its connector/cardinality risk must remain visible in S3 and later reports.


## v3.2.4 issue-ledger override

Use issue-ledger audit fields for S2/S5-related review outputs: record concrete issues, severity, rerun eligibility, high-priority issue status, downstream use, and caption burden. Hard contradictions become `BLOCKER_ISSUE` records. Do not use pass/fail labels as the sole selection verdict unless the user explicitly requests a filtering/ranking mode.
