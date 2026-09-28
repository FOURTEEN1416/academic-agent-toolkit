# Academic Framework Hierarchy And Image Asset Mirroring Policy v3.2.10 + v3.2.11 Edge-Label Addendum

After S5, human decisions are outside this assistant workflow.

This policy is intentionally **paper-agnostic**. It must not encode facts from any particular paper, dataset, method family, project, candidate, uploaded example, or previous run. Each project must instantiate the fields below from the current paper/source evidence, S0/S1/S4 contracts, and explicit author supplementation only.

## Purpose

Research framework figures need a stable academic information hierarchy. Exploratory style diversity may change layout grammar, reading path, drawing style, density, and callout placement, but it must not collapse the figure into an unstructured variable-node graph. Generated candidates must preserve a clear hierarchy:

```text
macro group / figure thesis
  -> primary method modules or system regions
    -> secondary internal mechanism tokens
      -> artifact, model-state, metric, parameter, and symbol labels
```

This policy hardens three recurring failures:

1. symbols, variables, scalar metrics, and pass-through artifacts become peer-level rectangular blocks;
2. several visually parallel arrows connect the same two blocks even though one bundled connector with labels would be clearer;
3. generated rasters are checkpointed as external registered assets without a human-readable mirror under the stage/candidate output path.

## 1. Visual Role Taxonomy And Rendering Tiers

Before writing an S2/S5 image prompt, every planned visible or caption-visible term must be assigned a `visual_role` and a `render_tier`.

Required field:

```yaml
visual_hierarchy_plan:
  figure_thesis: <one sentence derived from current source evidence>
  reader_path: [<3-7 source-grounded steps>]
  terms:
    - term: <paper/source term or symbol>
      visual_role: actor_context | primary_module | secondary_substep | material_artifact | model_state | metric_or_score | parameter_or_gate_value | constraint_note | caption_only
      render_tier: macro_group | module_box | internal_motif | edge_label | port_label | attached_tag | labeled_fork_or_merge | grouped_glyph | small_artifact_glyph | legend_symbol | caption_only | removed
      standalone_box_allowed: true|false
      standalone_box_exception_reason: <required when true for material_artifact/model_state/metric_or_score/parameter_or_gate_value>
      evidence_anchor: <paper/S0/S1/S4/source anchor>
```

Default treatment:

| visual_role | Default rendering | Standalone full block rule |
| --- | --- | --- |
| `actor_context` | role chip, context strip, boundary label, small participant glyph | allowed only as compact context, not duplicated full workflow unless required |
| `primary_module` | large module/panel/card | allowed and expected when it is on the main reader path |
| `secondary_substep` | internal visual motif or mini-chain inside a parent module | standalone only if it owns a source-supported branch or distinct mechanism |
| `material_artifact` | edge label, port label, labeled fork/merge, or small artifact glyph when justified | standalone only if it is stored, branched, sampled, mixed, evaluated, compared, cached, queued, or reused as a distinct object |
| `model_state` | port label, attached tag, edge label, or small model-state glyph | standalone large block only if the model itself is a primary module |
| `metric_or_score` | edge label, gauge tag attached to an evaluation connector, or caption/legend | not a standalone block by default |
| `parameter_or_gate_value` | attached tag on controlled gate/module or line label | not a standalone block by default |
| `constraint_note` | small guard note / legend / boundary note | never a main module |
| `caption_only` | caption or legend text | no visible block |

A prompt is not ready if it places more than a small number of non-module items at the same visual weight as primary modules without source-grounded exception reasons.

### v3.2.11 edge-label-first addendum

For S2/S5 image prompt packages, default non-module terms to **inline edge labels, port labels, attached tags, or labeled fork/merge connectors**. Do not place a pass-through artifact, scalar, metric, weight, threshold, temporary state, or pseudo-output into a standalone chip/box merely because it is named in the semantic graph. A visible non-module glyph requires the exception fields in `references/edge-label-first-and-internal-motif-policy-v3211.md`.

Prompt packages must include `edge_label_first_artifact_policy`, `visual_render_graph`, `visible_text_contract`, and `line_carried_variable_registry`. A term planned as `edge_label`, `port_label`, `attached_tag`, or `labeled_fork_or_merge` must not appear in the image-only prompt's visible node labels.

## 2. Derived Primary Module Whitelist

Do not hard-code reusable module names. For each project, derive a `primary_module_whitelist` from source-grounded contribution statements, method section headings, algorithm phases, architectural components, or S0/S1/S4 contracts.

Required field:

```yaml
primary_module_whitelist:
  derivation_basis: contribution_statement | method_sections | algorithm_phases | architecture_components | author_supplementation | mixed
  modules:
    - display_label: <current-paper module name>
      evidence_anchor: <paper/S0/S1/S4/source anchor>
      required_internal_tokens: [<substeps/artifacts that must be visible inside, not peer-level blocks>]
  non_module_symbol_policy: artifact_or_symbol_terms_not_in_whitelist_default_to_labels_or_tokens
```

Only `primary_module` entries and explicitly justified `actor_context` containers may become large standalone boxes. Candidate style exploration may vary how these primary modules are grouped, stacked, looped, or inset, but it must not promote every artifact or symbol into a peer-level module.

## 3. Artifact-As-Block Guard

The prompt package and later audits must count non-module blocks.

Required field:

```yaml
artifact_block_guard:
  non_module_standalone_box_count: <int>
  non_module_box_entries:
    - term: <artifact/model/metric/parameter/symbol>
      visual_role: <role>
      reason_if_allowed: <branch/store/compare/sample/mix/evaluate/reuse reason>
      demotion_if_not_allowed: edge_label | port_label | attached_tag | labeled_fork_or_merge | grouped_glyph | internal_motif | caption_only
  edge_label_eligible_box_count_planned: <int>
  variable_as_block_count_threshold: <derived from layout/density budget>
  guard_verdict: pass | revise_before_image_generation | blocked_until_replanned
```

Audit issue categories:

- `artifact_as_block_error`: a non-module artifact/model-state/metric/parameter is drawn as a peer-level full module without its recorded exception;
- `edge_label_eligible_box_error`: a term planned as edge/port/fork/merge label is drawn as any standalone chip, card, rectangle, bubble, or node;
- `variable_as_block_error`: a symbol or pass-through variable is drawn as a box instead of a label/tag/token;
- `hierarchy_flattening`: the image loses macro/module/internal-token/symbol hierarchy;
- `micro_node_overproduction`: too many substeps or quantities are equal-weight nodes for a framework overview.

## 4. Connector Bundling And Edge Economy

A semantic graph may contain many evidence-backed relations, but the visible figure should bundle compatible relations. The prompt must perform visual connector aggregation before image generation.

Required field:

```yaml
connector_bundling_plan:
  connector_families:
    - family_id: CF_...
      semantic_edge_ids: [E_...]
      shared_source_or_group: <module/group/port>
      shared_target_or_group: <module/group/port>
      shared_flow_semantics: data_or_artifact_flow | model_state_or_reference_flow | control_or_gating_flow | evaluation_or_metric_flow | communication_or_exchange_flow | conceptual_dependency | next_round_or_reuse | mixed_line_family
      visible_line_style: solid | dashed | dotted | bracket | bus | fork_merge | no_arrow_grouping
      visible_quantity_labels: [<short labels carried on this connector>]
      split_exception_reason: <required if multiple visible parallel lines are kept>
      evidence_anchor: <paper/S0/S1/S4/source anchor>
  primary_connector_count_planned: <int>
  unlabeled_parallel_connector_count_planned: <int>
  edge_economy_verdict: pass | revise_before_image_generation | blocked_until_replanned
```

Bundling rules:

- If several artifacts jointly enter the same module with the same flow semantics, draw one merge/bus/fork connector and put the quantities on the line or port.
- If one artifact branches to several downstream modules, draw one labeled split connector or one artifact token with a fork, not repeated peer-level artifact boxes.
- If a data flow and a model-state exchange both connect nearby regions, keep them separate because their semantics differ.
- Do not draw unlabeled parallel arrows between the same two visual regions. Each visible line must either have a distinct line style, distinct carried quantity, distinct endpoint/port, or a recorded reason.

Audit issue categories:

- `unbundled_parallel_edges`: multiple visible lines could be one labeled connector family;
- `unlabeled_parallel_edges`: parallel lines have no visible or caption-supported reason;
- `edge_label_missing`: a bundled line carries multiple quantities but does not label them;
- `line_semantics_ambiguous`: the viewer cannot distinguish data/artifact, model/exchange, control/evaluation, or next-round reuse.

## 5. Academic Layout Hierarchy Gate

S2 may vary style and layout, but every candidate must still show academic hierarchy.

Required field:

```yaml
academic_layout_hierarchy_gate:
  macro_groups: [<figure-level regions, spaces, phases, or lanes>]
  primary_modules: [<whitelisted modules>]
  internal_detail_strategy: in_module_mini_chain | internal_visual_motif | side_callout | bottom_cutaway | caption_assisted | mixed
  symbol_rendering_strategy: edge_labels_first | port_labels | tags | labeled_fork_or_merge | justified_glyphs | legend | caption
  main_flow_dominance: low | medium | high
  hierarchy_verdict: pass | revise_before_image_generation | blocked_until_replanned
```

Candidate diversity may change:

- left-to-right vs loop vs swimlane vs two-band vs triptych vs representative-neighborhood grammar;
- placement of callouts and mini-chains;
- compactness, caption burden, and visual style.

Candidate diversity must not change:

- which items are primary modules vs artifacts/symbols;
- source-supported arrow directions;
- forbidden elements/topologies;
- edge semantics and input eligibility;
- the requirement that core mechanisms are visible as internal visual motifs or mini-chains, not empty boxes, title-only modules, or bullet-list substitutions.

## 6. Prompt-Level Negative And Positive Wording

Image prompts must include positive rendering instructions, not just prohibitions.

Required wording pattern:

```text
Render primary method components as the only large module boxes. Render intermediate artifacts, variables, model states, scalar values, metrics, weights, and parameters as edge labels, port labels, attached tags, or labeled fork/merge connectors by default. Do not enclose edge/port labels in rectangles, rounded rectangles, bubbles, chips, cards, circles, or standalone nodes unless the prompt explicitly records a source-grounded glyph/box exception. Merge compatible multi-input or multi-output quantities into labeled bus/fork connectors. Inside each core compound module, draw a tiny visual mini-process with micro-glyphs and arrows; do not replace required internals with a bullet list. Keep only semantically distinct line families separate.
```

Avoid relying only on statements like `do not draw variables as boxes`; models often ignore negative-only constraints when the semantic graph lists those variables as nodes. The visual render graph itself must demote them before prompt writing, and the prompt must avoid the ambiguous words `chip`, `token`, `box`, `card`, or `node` for any term planned as an edge/port label.

## 7. Stage-Local Image Mirror And Registered Image Escrow

Generated raster images must be human-browsable in the stage output tree and restore-safe in checkpoints.

After an approved image-generation route produces a raster, the image-registration unit must create or validate a byte-for-byte stage-local mirror at the prompt-index `target_image_path`, for example:

```text
outputs/<stage-output-root>/candidates/<candidate-id>/image-vNN.png
```

The original generated path may also be retained in a generated-image escrow or provenance registry. Checkpoints may include both:

- **stage-local canonical copy**: the human-facing active image path for that candidate;
- **registered generated-image escrow**: provenance-preserving copy or source path record used for cross-session recovery.

This mirror is a file copy of a generated raster, not a local/programmatic raster substitute. It must not redraw, crop, render, retouch, or alter pixels. If the mirror cannot be created, the candidate must remain `image_generation_registered_but_not_stage_mirrored` or `pending_stage_local_mirror`; later text stages must not imply that the candidate has a complete output-local active image.

S5 `reference_image_paths` are different from `target_image_path`: they point to
already-registered S2 raster outputs used as optional visual inputs for formal
candidate generation. They must not be copied into an S5 candidate target slot
or treated as generated S5 outputs, but cumulative checkpoints must include
them as required existing raster assets when listed in the S5 prompt-index.

Required field in image provenance register:

```yaml
stage_local_image_mirror:
  source_generated_path: <path produced by approved image route>
  target_image_path: <prompt-index target_image_path>
  copy_mode: byte_for_byte_copy | adopted_existing_registered_raster | unavailable
  checksum_source: <sha256 or null>
  checksum_target: <sha256 or null>
  mirror_status: complete | pending | blocked
```

Checkpoint completeness must require every active/generated candidate image to exist at its stage-local active path unless the stage explicitly records it as future/pending. Escrow-only storage is not enough for human-facing candidate outputs.

## 8. Where This Policy Applies In The Workflow

- **S1** must instruct S2 candidates to vary layout without varying the derived visual hierarchy.
- **S1-embedded S2 preparation** must write `visual_hierarchy_plan`, `artifact_block_guard`, `edge_label_first_artifact_policy`, `visual_render_graph`, `line_carried_variable_registry`, `connector_bundling_plan`, `academic_layout_hierarchy_gate`, `internal_visual_motif_plan`, and `prompt_contradiction_audit` for every candidate prompt package.
- **S3 embedded review of S2 outputs** must report `artifact_as_block_count`, `edge_label_eligible_box_count`, `unbundled_parallel_connector_count`, hierarchy failures, text-only core mechanism failures, and mirror completeness.
- **S3** must not recommend directions whose main value depends on variable-as-block clutter or unbundled connector webs.
- **S4** must carry forward hierarchy and connector-bundling contracts into formal candidates.
- **S4-embedded S5 preparation** must be at least as strict as S2; formal candidates should reduce symbol-as-box, edge-label-eligible box, text-only core mechanism, and duplicate-line errors, not preserve them.
- After S5, human decisions are outside this assistant workflow.

## Non-Hardcoding And Portability

Reusable skill files must not include target-paper module names, variables, datasets, candidate IDs, project paths, or generated examples as doctrine. Current-run outputs may instantiate this policy with current-paper terms and examples, but this reference remains a procedure and schema only.
