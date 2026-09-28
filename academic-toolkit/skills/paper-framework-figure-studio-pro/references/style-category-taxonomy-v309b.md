# Style Category Taxonomy v3.0.9b

This reference merges the style/category systems extracted from:

- `paper-vector-library-builder-final-library.zip`
- `paper-vector-figure-skills-v0.6-deepread-reference-index.zip`

Use it when S1-S4 need richer style choices and when S4 builds the formal candidate matrix. It is a design taxonomy, not a source-paper fact base.

## Source A: Final Vector Library Taxonomy

The final library is grounded in 541 audited papers, 3239 figure-story-architecture links, 2805 final reference rows, 691 canonical icons, 2313 icon aliases, 501 PPT primitives, 31 design patterns, 31 layout patterns, and 100 paper-derived motif records.

### Figure Subtypes

- `evidence_chart`
- `graph_or_network`
- `retrieval_flow`
- `data_or_embedding_map`
- `qualitative_example`
- `method_architecture`

### Layout Grammars

- `small_multiples_or_chart_panel`
- `node_edge_graph_layout`
- `query_context_retrieval_answer_flow`
- `map_or_distribution_panel`
- `example_grid_or_before_after_panel`
- `left_to_right_modular_pipeline`

### Architecture Topologies

- `graph_network`
- `retrieval_augmented_flow`
- `train_infer_split`
- `loop_or_feedback`
- `pipeline_or_modular_system`
- `unknown_caption_only`

### Figure Roles

- `support_empirical_claim_or_ablation`
- `explain_graph_structure_or_dependency_flow`
- `explain_retrieval_augmented_reasoning_flow`
- `explain_dataset_distribution_or_representation_space`
- `show_qualitative_behavior_or_case`
- `explain_method_or_system_architecture`

### Density And Symbol Levels

- Density: `low`, `medium`, `high`
- Formula/symbol burden: `none_or_caption_only`, `low`, `medium`
- Vector buildability scores present in the source index: `0.82`, `0.52`, `0.4`

### Borrowable Design Pattern Families

- reviewer-first grouping and reading order
- caption anchors that separate visual strategy from paper-specific facts
- small-multiple comparison rhythm
- claim-to-chart captioning
- evidence placement
- module grouping
- stage-output chips
- typed arrows for data/control flow
- distribution overview
- semantic grouping
- legend strategy

### Style Token

`iclr_clean_flat_modular_v1` is the starter token. It means:

- vector-first rebuild;
- reviewer-first information grouping;
- clean academic figure language;
- caption carries paper-specific claims;
- do not transfer source-paper facts, exact numbers, or unsupported labels.

## Source B: v0.6 Deep-Read Reference Index Taxonomy

The v0.6 package contributes a deep-read-backed retrieval and transfer system. Its main point is that style selection should not be surface-only: it should consider paper story, architecture topology, claim-evidence logic, reader path, and vector buildability.

### Paper Story Signature Axes

- `reader_question`
- `problem_type`
- `gap_type`
- `core_insight`
- `contribution_type`
- `story_arc`: `problem_to_method`, `mechanism_first`, `example_first`, `architecture_first`, `evidence_first`, `failure_to_guardrail`, `comparison_first`
- `desired_reviewer_effect`
- `main_claims`
- `evidence_roles`
- `caption_burden`
- `allowed_reorganization`

### Model Architecture Signature Axes

- `model_family`
- `modality`
- `topology_family`
- `module_roles`
- `training_flow`
- `inference_flow`
- `data_flow_pattern`
- `control_flow_pattern`
- `feedback_loops`
- `loss_or_objective_signals`
- `memory_retrieval_tool_use`
- `main stage outputs`
- `expected_module_count`
- `complexity_level`

### Figure Signature Axes

- `figure_subtype`
- `paper_slot`
- `reader_path`
- `layout_grammar`
- `panel_rhythm`
- `module_grouping_strategy`
- `stage-output visibility`
- `icon_landmarks`
- `arrow_grammar`
- `evidence_treatment`
- `symbol_density`
- `text_density`
- `style_family`
- `vector_buildability`
- `ppt_editability`

### Preference Style Dimensions

- palette;
- layout rhythm;
- shape language;
- icon style;
- arrow grammar;
- typography;
- dimensionality;
- abstraction level;
- density;
- evidence treatment;
- tone;
- positive and negative preferences;
- vector risk;
- transfer strength: `weak`, `medium`, `strong`, `locked`.

### Reference Retrieval Groups

- `direct_story_architecture_match`
- `architecture_match_style_different`
- `story_match_architecture_different`
- `visual_style_match_only`
- `evidence_treatment_reference`
- `do_not_use_due_to_mismatch`

## Two-Level Startup Style Model

The saved atlas boards and any local F1-F4 thumbnails are first-level routing aids. They narrow the design question before selecting a formal style lens, but they are not final candidate contracts.

| First-level entry | Atlas board | Primary decision axis | Secondary decision required |
|---|---|---|---|
| `F1` | `subtype-overview` | figure role / paper slot | choose a `style_lens_id` that fits the paper's contribution and reader question |
| `F2` | `visual-grammar-layout` | structural grammar / reader path | choose a `style_lens_id` that fits module topology, arrow grammar, and panel rhythm |
| `F3` | `reader-role-detail` | reader effect / density level | choose a `style_lens_id` that fits detail budget, caption burden, and reviewer question |
| `F4` | `visual-communication-styles` | visual communication surface | choose a `style_lens_id` that fits paper logic, not only visual taste |

The second-level style lens must bind together:

- paper narrative task;
- structural grammar and reader path;
- density/detail budget;
- caption/legend/body-text burden;
- icon, arrow, color, and legend semantics;
- downstream layer extraction/vector reconstruction feasibility;
- transfer boundary from any style reference.

Style references are not target-paper facts. They may transfer layout skeleton, reader path, panel rhythm, abstraction level, callout strategy, icon style, arrow grammar, density discipline, and legend strategy. They must not transfer paper-specific facts, labels, modules, datasets, metrics, formulas, examples, claims, or exact visual structures.

## v3.0.9b Merged Style Lenses

Use these lenses to make the formal candidate matrix less single-track. In v3.2.15f, S4 must still fit the final S5 prompt-index into exactly two candidates, so style lenses are planning ingredients rather than a license to create a larger matrix.

| Lens ID | Style Lens | Best For | Typical Layout/Asset Hints | Density / Caption Burden | Reconstruction Risk |
|---|---|---|---|---|---|
| `schematic_precision` | Schematic precision / formal architecture | methods, systems, architecture boundaries | modular pipeline, typed arrows, exact interfaces | medium density; caption defines interfaces and constraints | low if modules and ports stay separated |
| `editorial_clarity` | Clean editorial flat / minimal line-art | intro or method overview needing fast comprehension | compact grouped modules, strong hierarchy, low text density | low density; caption carries definitions and caveats | low |
| `mechanism_snapshot` | Mechanism intuition snapshot | explaining why the core idea works | central mechanism, zoom callout, cause-effect arrows | medium density; caption explains local mechanism assumptions | medium if zoom detail duplicates or overlaps main path |
| `evidence_infographic` | Mini-evidence infographic | linking method to result or ablation | side evidence card, metric badge, small-multiple cue | medium density; caption carries exact metrics and evidence limits | medium if badges/charts become too small |
| `graph_reasoning` | Graph/network reasoning | GNNs, dependency graphs, causal/relational logic | node-edge graph layout, edge semantics, compact legend | medium-high density; legend must define node/edge types | medium-high if edges cross or nodes overlap |
| `retrieval_flow` | Retrieval/RAG/query-context-answer flow | RAG, agents, tool use, memory, search | query-context-retrieval-answer grammar | medium density; caption disambiguates data vs control flow | medium if retrieved context tokens crowd the path |
| `data_embedding_map` | Data/embedding/distribution map | representations, manifolds, latent spaces, datasets | map/distribution panel, clusters, arrows, legend | medium density; caption explains axes/clusters if not explicit | medium if clusters and labels fuse |
| `qualitative_walkthrough` | Example or before/after walkthrough | showing one case through the method | grid, storyboard, before/after strip | medium density; caption maps example panels to method steps | medium if visual examples dominate method logic |
| `train_infer_split` | Training vs inference split | papers with different optimization/deployment paths | split lanes, shared model core, output chips | medium density; caption clarifies shared vs phase-specific modules | low-medium if lanes are clearly separated |
| `loop_feedback` | Loop/feedback/self-improvement cycle | agents, RL, iterative refinement, self-training | cyclic path, feedback port, iteration marker | medium density; caption defines iteration/update semantics | medium if loop arrows cross main modules |
| `taxonomy_matrix` | Taxonomy/matrix overview | high-density survey or category map when explicitly requested | matrix grid, grouped cells, caption-heavy support | high density; caption carries definitions and boundaries | high if cells contain tiny text |
| `premium_scientific` | Premium scientific illustration, vector-safe | high first-glance appeal without posterization | restrained color, landmark icons, separable foreground | low-medium density; caption carries precise mechanism labels | medium if illustration becomes textured or perspective-heavy |
| `plain_language_hand_drawn_storyboard` | Hand-drawn whiteboard / lightly narrative everyday-example storyboard | making a complex method understandable by analogizing the algorithm/model category into a faithful everyday example | 3-5 sketch panels, hand-drawn arrows, simple characters/objects, sticky-note labels, model-detail mini-chain, story-to-method mapping | low-medium density; caption must bridge story to paper mechanism | high for formal S5 unless explicitly justified |

## Candidate Style-Lens Contract

Every S1 sketch candidate and S4 formal candidate must record:

- `level_1_atlas_entry`;
- `style_lens_id`;
- `paper_logic_fit`;
- `structure_grammar_fit`;
- `density_budget`;
- `caption_burden`;
- `icon_arrow_legend_semantics`;
- `layer_extraction_vector_reconstruction_risk`;
- `transfer_boundary`.
- `consensus_space_priority_map`, `visual_weight_plan`, `must_show_for_each_space`, `redundancy_budget`, and `missing_information_risk` when the paper contribution relies on peer spaces or peer consensus mechanisms.

## Selection Rule

For S1/S2, sample broad directions across subtype, layout grammar, reader path, first-glance hook, density/detail pressure, visual rhetoric, style lens, and palette strategy. S1 must first create eight complementary style-combination proposals, then select the highest-value four for `C01`-`C04`. The sampling should be orthogonal only where it helps communicate the target paper framework: each variation should improve paper-work showcase value, reviewer attraction, aesthetic clarity, or human publication taste. S1 candidate cards must include the full style-lens contract, complementarity rationale, and the first-round `s2_style_feature_vector` so S2 can generate sketches from explicit design logic.

For S4, choose style lenses by paper need while producing exactly two final S5 candidates:

1. Pick the active structural directions from S3.
2. For each direction, choose style lenses that differ in visual rhetoric, density, reader path, evidence treatment, caption burden, and reconstruction risk.
3. Prefer one reviewer-first low-density/balanced overview option.
4. Include one mechanism/detail/evidence option only when the target paper has a mechanism or evidence anchor worth showing.
5. Keep the default two formal S5 candidates in clean publication schematic raster style. Hand-drawn, whiteboard, sketch-note, comic, or story-like treatments are optional only when the user explicitly requests them or S4 explicitly justifies them and they fit the two-row cap.
6. Record `level_1_atlas_entry`, `style_lens_id`, `source_taxonomy_refs`, `paper_logic_fit`, `structure_grammar_fit`, `density_budget`, `caption_burden`, `icon_arrow_legend_semantics`, `palette_strategy`, `palette_anti_ai_artifact_rules`, `layer_extraction_vector_reconstruction_risk`, `icon_family_hints`, and `transfer_boundary` in the candidate brief.

For any optional story-like candidate, S4 must provide the story-to-method mapping and explain why it helps the reader. The image must remain a generated raster candidate grounded in paper modules, symbols, sample types, weights, arrows, and update relations.

Do not use style lenses to import facts from reference papers. Only borrow layout skeletons, reader paths, panel rhythm, abstraction level, stage-output visualization, callout strategy, evidence placement, icon style, arrow grammar, density discipline, and style family.

## First-Round Surface Menu v3.2.15f

S1/S2 style lenses describe paper-serving communication strategy. The first-round rendering surface has its own default and override menu. Unless explicitly overridden, the first-round S2 surface is `formal_publication_schematic` / 正式出版风格. Compatible first-round surfaces are: `formal_publication_schematic`, `low_fidelity_sketch`, `whiteboard_wireframe`, `clean_flat_minimal_line`, `formal_schematic_layout_study`, `precision_blueprint_light`, `scientific_editorial_light`, `interface_metaphor_light`, `isometric_structure_light`, `infographic_board_light`, `hand_drawn_storyboard`, and `acm_ieee_aaai_line_art_schematic`.

These surfaces must remain exploratory; they do not turn S2 into publication-ready S5 rendering.
