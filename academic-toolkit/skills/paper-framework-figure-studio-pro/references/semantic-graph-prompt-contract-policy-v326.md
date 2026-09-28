# Semantic Graph Prompt Contract Policy v3.2.8 + v3.2.11 Visual Render Graph Addendum

After S5, human decisions are outside this assistant workflow.

## Core Rule

Every generated image prompt for a connector-heavy research figure must be compiled from a **semantic graph specification** and a separate **visual render graph** before any style wording is added. Before finalizing `node_registry`, classify planned terms with the v3.2.8 entity/artifact/symbol and entity-density gate: intermediate variables, temporary outputs, scalar metrics, thresholds, and pass-through quantities default to edge labels, port labels, or attached tags rather than standalone nodes unless an explicit exception is recorded; framework-level micro-operations must be merged into compound modules when possible. The graph specification is a non-visual control contract: it defines exact source-grounded entities, ports, edges, edge semantics, allowed direction, cardinality, layout region, and text roles. It is not automatic permission to draw every semantic node. The visual render graph separately decides which semantic nodes become visible objects and which become edge labels, port labels, attached tags, labeled fork/merge annotations, small artifact glyphs, caption-only items, or removed items. The style description may change line roughness, layout grammar, color accents, and density, but it must not add, remove, rename, merge, split, reverse, or decorate semantic graph edges.

## Internal IDs Are Never Visible

Graph IDs are machine-control identifiers only. They must never appear as text in the generated figure, caption, legend, title, or visual labels unless the paper itself defines that text as a display symbol and the prompt explicitly includes it in the visible-text whitelist.

Required separation:

```text
node_id / edge_id / port_id / lane_id / group_id: internal only, never visible.
display_label / visible_group_label / visible_edge_label: optional visible text.
render_label: true only for display labels that should be drawn.
```

The image-only prompt must state this explicitly:

```text
The strings in node_id, edge_id, port_id, lane_id, and group_id are internal layout controls. Do not draw them. Draw only strings listed in the split visible_text_contract. Only visible_node_labels may appear inside standalone boxes; visible_edge_or_port_labels must be written on connectors or ports.
```

## Identifier Uniqueness Rules

Within each candidate graph:

- Every `node_id` is unique. Do not reuse a node ID for two different entities, roles, states, artifacts, or visual copies.
- Every `edge_id` is unique. Do not reuse an edge ID for two different relations, directions, semantics, or visual line styles.
- An `edge_id` must not equal any `node_id`, `port_id`, `group_id`, or `lane_id`.
- A repeated visual copy of the same underlying artifact must receive a distinct `node_id` and an explicit `instance_relation` such as `same_instance_replica`, `sampled_subset`, `same_distribution_proxy`, or `caption_only_reference`.
- A sampled subset is a child artifact, not a duplicate of its source. It needs its own `node_id` and a contracted sampling edge from the source artifact.
- If two visible boxes legitimately carry the same display label, their internal `node_id` values must still be different and the prompt must give a non-visual disambiguator such as lane, owner, round, or instance role.
- Candidate IDs may prefix graph IDs when multiple candidates are generated in one batch, e.g. `C03_N_DIFFUSION`, but the prefix remains non-visible.

Recommended ID prefixes:

```text
G_  graph/group/container
L_  lane/region
N_  node/entity/artifact/module
P_  port
E_  edge/connector
R_  role or repeated-family record
T_  visible text whitelist item
```

## Required Semantic Graph Specification

Each prompt package must include a `semantic_graph_spec` object or section with these fields:

```yaml
semantic_graph_spec:
  graph_id: <internal graph id, not visible>
  candidate_id: <candidate id>
  graph_scope: <what part of the paper/method this graph covers>
  id_visibility_rule: "internal IDs are not visible text"
  node_registry:
    - node_id: N_...
      kind: data_artifact | model | module | metric | control | actor | container | context | replica | subset | note | inline_symbol_annotation | edge_annotation
      display_label: <visible text or empty>
      render_label: true | false
      visual_role: <box/chip/icon/container/etc.>
      region_id: G_... or L_...
      port_ids: [P_...]
      instance_role: primary | same_instance_replica | sampled_subset | same_distribution_proxy | context_only
      evidence_anchor: <paper/S0/S1/S4/source anchor>
      allowed_incoming_edge_ids: [E_...]
      allowed_outgoing_edge_ids: [E_...]
  edge_registry:
    - edge_id: E_...
      source_node_id: N_...
      source_port_id: P_...
      target_node_id: N_...
      target_port_id: P_...
      semantic_type: data_artifact_flow | model_state_update | control_gating | evaluation_score | communication_exchange | dependency | containment | callout
      line_style: solid | dashed | dotted | bracket | no_arrow_grouping
      arrowhead: target | both | none
      render_edge_label: true | false
      visible_edge_label: <optional human-readable label, not edge_id>
      flow_semantics: data_or_artifact_flow | model_state_or_reference_flow | control_or_gating_flow | evaluation_or_metric_flow | communication_or_exchange_flow | conceptual_dependency | containment_or_grouping | callout_or_zoom | next_round_or_reuse | no_arrow_association
      min_visible_instances: 0|1
      max_visible_instances: 1
      direction_evidence: <paper/S0/S1/S4/source anchor>
      forbidden_reverse: true
      forbidden_shortcuts: [<plain-language forbidden source-target claims>]
  visible_text_contract:
    visible_node_labels:
      - <text allowed inside standalone visual nodes>
    visible_edge_or_port_labels:
      - <text allowed only on connectors, ports, tags, forks, or merges>
    visible_internal_micro_labels:
      - <short labels inside internal visual motifs>
    visible_legend_or_caption_labels:
      - <text allowed only in legend/caption support>
  visible_text_whitelist:
    - <flattened list derived from visible_text_contract; not sufficient by itself>
  internal_text_blacklist:
    - "N_"
    - "E_"
    - "P_"
    - "node_id"
    - "edge_id"
    - "port_id"
    - "semantic_graph_spec"
  layout_plan:
    regions: [<region/lane descriptions>]
    reading_order: [<node_id sequence or region sequence, internal only>]
    routing_corridors: [<connector routing rules>]
  symbol_entity_classification:
    - paper_term_or_symbol: <visible or source term>
      visual_semantic_class: actor_or_context | module_or_operation | material_artifact | inline_symbol | control_parameter | caption_only
      planned_rendering: visual_node | inline_edge_label | port_label | attached_tag | labeled_fork_or_merge | small_artifact_glyph | caption_only | removed
      node_exception_reason: <required if inline_symbol/control_parameter becomes a node>
  visual_render_graph:
    large_nodes_only: [<primary modules and justified context containers>]
    artifact_node_conversion:
      - semantic_node_or_term: <id or term>
        visual_conversion: inline_edge_label | port_label | attached_tag | labeled_fork_or_merge | small_artifact_glyph | caption_only | removed
        standalone_box_allowed: true|false
        exception_reason: <required if true>
  line_carried_variable_registry:
    - term: <current-paper term or symbol>
      render_as: inline_edge_label | port_label | attached_tag | labeled_fork_or_merge | no_visible_label
      standalone_box_allowed: false
      evidence_anchor: <paper/S0/S1/S4/source anchor>
  edge_annotation_registry:
    - annotation_id: A_...
      text: <visible symbol or short label>
      attaches_to_edge_ids: [E_...]
      annotation_role: carried_data | carried_model_state | control_value | evaluation_value | branch_label | caption_only
      render_mode: inline_edge_label | port_tag | merge_label | no_visible_label
  internal_visual_motif_plan:
    - parent_module: <current-paper module name>
      core_module: true|false
      internal_layout: mini_chain | stacked_motifs | side_cutaway | micro_pipeline | caption_assisted
      text_only_allowed: false
      bullet_list_allowed: false
  prompt_contradiction_audit:
    verdict: pass | revise_before_image_generation | blocked_until_replanned
  element_granularity_plan:
    figure_role: framework_overview | architecture | pipeline | mechanism_explainer | scoped_detail | comparison
    granularity_target: coarse | medium | detailed
  module_input_contract:
    - module_node_id: N_...
      allowed_inputs: [<node ids or annotation ids>]
      forbidden_inputs: [<unsupported source terms>]
  edge_cardinality_audit:
    duplicate_source_target_pairs: []
    duplicate_allowed_with_distinct_roles: []
    redundant_edge_fix: remove | merge | convert_to_inline_label | route_to_caption | not_needed
```

## Mermaid-Like Relationship Syntax

A Mermaid-like edge list is allowed only as an internal control block. It must not be the only source of visible labels. Use this pattern:

```text
INTERNAL_RELATIONSHIPS_DO_NOT_RENDER_IDS:
E01: N_SOURCE.P_OUT -> N_TARGET.P_IN
     semantic=data_artifact_flow; style=solid; arrowhead=target; render_edge_label=false
```

Do not write prompts where the internal graph IDs look like visible figure labels. The generator must be tinactive that only `display_label` values are visible.

## Image-Only Prompt Compilation Order

The saved image-only prompt must be ordered like this:

1. Reviewer takeaway and reader path.
2. Non-visual graph contract: internal IDs are not visible.
3. Entity/artifact/symbol classification and element granularity plan.
4. Split visible_text_contract with node labels separated from edge/port labels.
5. Visual render graph with large visible nodes limited to primary modules and justified context containers.
6. Line-carried variable registry and edge annotation registry for variables/symbols rendered on lines, forks, merges, tags, or ports.
7. Exact edge registry / relationship list with source and target ports plus flow semantics.
8. Module input contract and edge cardinality audit.
9. Layout plan: regions, lanes, grouping, reading order, port sides, routing corridors.
10. Style plan: stage-appropriate roughness/polish, line weight, color accents, whitespace, icon vocabulary.
11. Negative topology and text constraints: no extra edges, no visible internal IDs, no unlisted labels, no unlisted loops/rails/bands.

Style instructions must come after the graph contract. Aesthetic language cannot introduce vague arrows, rails, loops, halos, callout bands, or return arrows unless those are present in the edge registry with IDs and endpoint rules.

## Visible Text Whitelist Gate

The prompt must list all allowed visible text. This list should include only paper-defined names, symbols, short module labels, and intentionally visible edge labels. Internal IDs, schema keys, audit terms, file paths, candidate IDs, and graph-spec keys must be blacklisted.

If a visible formula or paper symbol is needed, it belongs in `display_label` only when it is a node label; if it is an intermediate value carried by a connector, it belongs in `line_carried_variable_registry` and `edge_annotation_registry.text`, not in `node_id` and not as a standalone node by default. Example:

```text
node_id: N_LOCAL_CLASSIFIER
visible display_label: "classifier φ_i"
```

The figure may draw `classifier φ_i`; it must not draw `N_LOCAL_CLASSIFIER`.

## Audit Requirements

Before image generation, run a graph preflight audit:

- all IDs unique and type-prefixed;
- no ID reused for different entities or relations;
- every edge endpoint points to an existing node and port;
- every required paper relation has exactly one edge ID unless explicitly collapsed into a named connector family;
- every compound input has one chosen encoding: direct ports, merge gate, or label-only;
- every intermediate symbol or control value has been classified as inline edge label, port label, attached tag, labeled fork/merge, justified small artifact glyph, caption-only, or removed;
- every paper-primary module has been derived into a current-paper primary module whitelist and every non-module artifact/symbol has a non-peer rendering unless a source-grounded exception is recorded;
- the visual render graph demotes semantic artifact nodes before prompt wording;
- terms planned as edge/port/fork/merge labels are not present as visible node labels;
- core compound modules have internal visual motif plans when required;
- prompt contradiction audit has no unresolved chip/token/box/node wording for edge-label terms;
- every edge records flow semantics and module input eligibility;
- duplicate source-target edges are merged or justified by distinct roles;
- related multi-input/multi-output routes have connector-bundling records so prompt wording asks for one labeled route instead of unlabeled parallel clutter;
- every repeated artifact copy is declared as replica/proxy/subset;
- visible text whitelist is complete and does not contain internal IDs;
- no vague connector wording remains outside the edge registry.

After image generation, run a visible graph audit:

- every visible box maps to exactly one `node_id` or a permitted visual compression;
- every visible connector maps to exactly one `edge_id` or an allowed collapsed connector family;
- visible variable/symbol/artifact labels appear on their contracted edges/ports/forks/merges/tags rather than as unapproved standalone boxes or chips;
- visible modules preserve macro/module/internal-detail/symbol hierarchy rather than a flat equal-weight symbol graph;
- core compound modules show required visual micro-motifs or mini-chains and are not title-only or bullet-only;
- no internal ID strings are visible;
- no extra arrows, loops, rails, or decorative connectors have appeared;
- line style and arrowhead direction match the edge registry;
- edge labels, if visible, match `visible_edge_label` and not `edge_id`.

## File-Handoff Hardening

When image prompts are saved to files and referenced by an index, the image-generation unit must read the actual file path recorded in `prompt_path`, verify that it exists, and use the full file content as the prompt. The prompt index must not point to a path that differs from the actual saved image-only prompt file. If the runtime uses `image-only-prompt.txt`, the index must say so; if it uses `prompt-v01.md`, that file must exist and contain the full prompt.

Record `prompt_file_read_audit` with:

```yaml
prompt_file_read_audit:
  prompt_path_exists: true|false
  prompt_content_read: true|false
  prompt_content_hash: <hash or unavailable>
  graph_spec_present_in_prompt: true|false
  visible_text_whitelist_present: true|false
  exact_edge_registry_present: true|false
```

If any of these fields fail, do not generate the image. Rerun the prompt/index handoff first.
