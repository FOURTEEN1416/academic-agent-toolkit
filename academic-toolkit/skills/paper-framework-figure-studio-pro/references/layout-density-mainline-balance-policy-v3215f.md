# Layout Density, Mainline Balance, And Context Area Budget Policy v3.2.15f

This policy is paper-neutral. Apply it whenever S1 prepares S2 prompt packages, S4 prepares S5 prompt packages, or S3 transfers visible layout issues into S4 constraints for a research-paper framework, method, architecture, pipeline, or model overview figure.

## Purpose

Research-paper algorithm/model framework figures should usually be compact manuscript schematics, not sparse posters. Whitespace must help grouping and reading order; it must not create empty quadrants, scattered micro-block islands, or a canvas whose visual center is background context rather than the paper's method contribution.

The default for method, algorithm, model, framework, architecture, training/update, optimization, aggregation, interaction, and system-process diagrams is **compact-balanced density**: the core mechanism occupies most of the canvas while remaining readable. Large airy clearances are allowed only when the figure type genuinely needs physical spacing, such as circuit, chip, hardware-layout, board-layout, mechanical assembly, geospatial/map, or other physical-layout drawings, and the prompt package records that exception.

## Required Layout-Density Records

Every S1/S4 prompt package must include the following records before image-only handoff:

```yaml
layout_information_density_plan:
  figure_family: method_framework | algorithm_process | model_architecture | system_interaction | data_pipeline | physical_layout_exception | other
  density_target: compact_balanced | medium_dense_readable | airy_physical_layout_exception
  active_payload_ratio_target: "normally 65-85% of usable canvas for primary method content"
  primary_mechanism_occupancy_target: "normally at least 60% of usable canvas unless a recorded exception applies"
  major_module_count_target: "typically 4-8 compound modules; more requires source-defined primary modules"
  whitespace_function: grouping | connector_corridors | label_legibility | physical_clearance_exception
  fragmentation_repair_plan: merge_microblocks | group_into_compound_modules | move_symbols_to_edges | compress_context | caption_only | none
  verdict: pass | revise | block

canvas_area_budget:
  primary_method_content_pct: number_or_range
  background_context_pct: number_or_range
  legend_notes_pct: number_or_range
  margins_and_gutters_pct: number_or_range
  connector_corridor_pct: number_or_range
  physical_layout_exception: true | false
  exception_reason: string | null
  verdict: pass | revise | block

context_inset_budget:
  context_role: problem_context | actor_topology | environment | dataset_examples | assumptions | legend_like_context | none
  allowed_context_instances: integer
  context_area_target_pct: "normally <= 15%; <= 20% only with source-grounded necessity"
  top_banner_context_allowed: false_by_default
  duplicated_context_panels_allowed: false
  compression_strategy: small_inset | side_chip | corner_badge | boundary_label | caption_only | remove
  verdict: pass | revise | block

mainline_center_of_gravity_gate:
  primary_reader_path: string
  mainline_anchor_region: center | center_left_to_right | center_loop | center_two_band | other
  background_context_region: corner | side_strip | compact_inset | caption_only | none
  center_shift_risk: low | medium | high
  visual_focus_verdict: pass | revise | block
```

Numeric percentages are planning budgets, not pixel-level measurement obligations. They force explicit design intent and prevent prompts from allocating a large top or side area to background material.

## Default Area Rules For Algorithm / Model / Framework Figures

Unless the prompt package records a physical-layout exception:

- The primary method / model / algorithm mechanism should occupy the central visual field and normally about **65-85%** of the usable canvas.
- Background context, motivation, topology, input-role overview, environment, or dataset-example areas should normally stay at **15% or less** of the usable canvas; use up to **20%** only when the reader cannot understand the method without it.
- Legends, note boxes, symbol inventories, and definition lists should usually stay at **10% or less**; move long definitions to caption/manuscript text.
- Margins and gutters should be small but legible. Avoid large empty top bands, empty side columns, empty center gaps, and empty lower corners.
- A context inset must be visually subordinate to the method mainline. It may label actors, topology, or environment, but it must not look like the main contribution.
- Do not place a large background-knowledge panel above the method pipeline unless the figure family is a physical layout, map, or the paper contribution itself is context construction.

## Fragmentation And White-Space Repair

Before writing the image-only prompt, S1/S4 must remove layout fragmentation:

- Merge related microsteps into compound modules with compact internal glyphs.
- Convert scalar variables, thresholds, weights, metrics, and temporary artifacts into edge labels, port labels, tags, or fork/merge labels.
- Bundle connector families so arrows do not force excessive spacing.
- Replace many small isolated boxes with one grouped module, one nested mini-chain, or one concise mechanism card.
- Replace oversized context panels with a corner inset, side strip, badge cluster, boundary label, or caption-only explanation.
- Align modules on a grid or obvious path so the viewer's eye does not jump between islands.

A prompt is blocked when it instructs the image model to create a sparse board of many tiny disconnected items, a giant context/header panel, or a figure where support context takes more visual weight than the method mechanism.

## Prompt Wording Requirement

Every S2/S5 image prompt must include a compact instruction equivalent to:

```text
Use a compact manuscript-framework composition. The primary method mechanism should occupy the central visual field and most of the usable canvas; avoid empty quadrants, oversized margins, large top/side background panels, and scattered micro-block islands. Keep background or topology context as a small subordinate inset or side chip, not as a dominant banner. Group related substeps into compound modules with compact internal motifs, align modules on a clear grid/reading path, and keep whitespace tight but legible. Physical circuit/chip/hardware-layout figures may use larger clearances only when the prompt package records a physical-layout exception.
```

Do not rely on vague phrases such as `clean with lots of whitespace`, `minimal spacious layout`, or `large explanatory top panel` for algorithm/model/framework figures. If the selected surface style is minimal line-art, preserve compact balanced information density rather than making the canvas sparse.

## S3 Issue Categories

S3 issue ledgers must use these reusable categories when visible candidates fail this policy:

- `excessive_whitespace`
- `core_method_underfilled_canvas`
- `fragmented_microblock_scatter`
- `off_center_mainline`
- `top_heavy_context_panel`
- `support_context_area_overrun`
- `legend_or_notes_area_overrun`
- `context_inset_dominates_method`
- `sparse_poster_layout`
- `physical_layout_exception_missing`

Record the affected visible region, why it weakens first-glance method comprehension, and the S4 repair instruction.

## S4 Transfer

When S3 records any issue above, S4 must transfer it into hard prompt constraints, not a soft style preference. Typical repairs are:

- compress or move context to a small inset or caption;
- recenter the primary method path;
- merge scattered microsteps into fewer compound modules;
- reduce empty top/side areas;
- remove duplicate legends and long note panels;
- use edge/port labels instead of standalone variable boxes;
- explicitly set a compact-balanced density target for the S5 formal candidates.

## Non-Hardcoding And Portability

This policy must not name target-paper modules, datasets, variables, candidate IDs, project paths, or generated examples. The concrete percentages, module counts, and context-placement choices are computed from the current paper/source evidence and user constraints. Reusable skill files specify the design gate; project outputs instantiate it.
