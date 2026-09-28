# S2 Narrative Strategy And Layout Divergence Policy v3.2.12

Use this policy whenever S1 prepares first-round S2 sketch candidates, S2 embedded prompt preparation builds multi-candidate image-only prompt packages, or S2 embedded image review checks whether generated sketches are sufficiently different to support human selection. The policy is generic and must not encode target-paper names, modules, variables, datasets, domains, or one-project fixes.

## Core Principle

S2 is not a style-gallery stage. S2 is a storytelling and explanation-strategy exploration stage. The first-round candidates should test different faithful ways to explain the paper's method story to a reviewer. Variation in color, marker texture, icon set, or the phrase "whiteboard-like" is insufficient. A valid S2 candidate differs because it changes the reader's narrative path, dominant visual hierarchy, spatial grammar, or mechanism-emphasis hypothesis while preserving the locked paper backbone.

Low-fidelity sketching is not permission for chaotic layout. S2 sketches may be rough in line quality, but their arrangement must be deliberate: clear anchors, predictable scan order, reserved routing corridors, bounded supporting panels, and readable connector families.

## Required Narrative Strategy Vector

Every S1 S2-sketch card and every S2 prompt package must include a `narrative_strategy_vector` before style or layout prose:

- `story_question`: the reviewer question this candidate answers in one sentence;
- `contribution_type_alignment`: how this candidate's main visual spine matches the paper's primary contribution type;
- `protagonist_or_anchor`: the visual protagonist, such as one representative actor, a data artifact, a model state, a space, a round, a bottleneck, or a core mechanism, derived from the current paper;
- `conflict_or_problem`: the paper-grounded difficulty being resolved, such as missing labels, noisy supervision, access/boundary constraint, topology, multimodal mismatch, latency, uncertainty, domain shift, or another source-supported issue;
- `resolution_path`: the 3-5 ordered visual anchors that explain how the method resolves the conflict;
- `dominant_visual_spine`: one of `linear_backbone`, `swimlane`, `cycle`, `hub_and_spoke`, `zoom_callout`, `dual_space`, `comparison`, `storyboard`, `matrix_grid`, `funnel_hourglass`, `layered_stack`, or a paper-justified custom spine;
- `layout_archetype`: the concrete canvas architecture selected from the candidate slot library or a justified paper-specific derivative;
- `primary_emphasis`: which paper-primary path receives the most visual weight and why;
- `secondary_paths`: what remains visible but visually subordinate;
- `caption_or_legend_load`: what true but expensive detail is moved outside the pixels;
- `difference_from_nearest_candidates`: which already planned candidates it must not resemble;
- `layout_nonnegotiables`: 3-7 placement, corridor, grouping, or ordering constraints that make the visual difference enforceable in the image prompt.

A card without this vector is not S2-ready.

## Candidate Slot Library: Narrative Roles, Not Surface Styles

The default first-round S2 batch should choose from distinct explanation roles. Replace or add roles only when the paper demands it, and record the substitution. Do not reuse the same role under a new name.

| Role ID | Narrative role | Typical visual spine | Primary use |
|---|---|---|---|
| `macro_backbone` | fastest whole-method scan | `linear_backbone` or `layered_stack` | reviewer sees the entire method in seconds |
| `actor_centered` | one actor/entity/agent/component as protagonist | `zoom_callout` or `hub_and_spoke` | clarifies local responsibilities and external interactions |
| `artifact_lineage` | data/artifact/message lineage as protagonist | `swimlane` or `funnel_hourglass` | prevents confusion about what is produced, transformed, shared, or not shared; use as a mainline only when contribution-type evidence justifies data/artifact centrality |
| `model_state_lifecycle` | model/state/round progression as protagonist | `cycle` or `state_machine` | clarifies temporal order, updates, feedback, and next-round reuse |
| `multi_space_balance` | peer spaces/paths as co-protagonists | `dual_space`, `parallel_lanes`, or `split_canvas` | clarifies coupled data/model/control/actor spaces without demoting one |
| `signature_mechanism_reveal` | one core mechanism gets strongest hierarchy while the framework remains complete | `main_flow_plus_cutaway` | tests whether a contribution needs a visible internal mechanism to be understood |
| `problem_solution_storyboard` | problem-to-solution story | `storyboard` or `before_after_bridge` | makes the paper's motivation and method payoff intuitive |
| `evidence_or_ablation_story` | evidence-supported design rationale | `comparison`, `matrix_grid`, or `cause_effect_strip` | links method components to paper-supported evidence without becoming an experiment figure |
| `dense_contract_stress_test` | maximum useful detail under readability gates | `precision_grid` or `compact_algorithm_cards` | tests whether a denser but rigorous view is still readable |

The first round does not need all roles. It does need enough role diversity that a human can choose among different ways of telling the method story.

## Pairwise Layout Divergence Gate

Before saving C01-C04 prompt packages, run a pairwise `layout_divergence_gate` over the four selected candidates:

- no two required S2 candidates may share the same triple of `dominant_visual_spine`, `primary_emphasis`, and `resolution_path`;
- at most two candidates may use the same high-level layout family, and if two do, they must differ in protagonist and visual hierarchy;
- at least three distinct `dominant_visual_spine` values should appear in the four-candidate first round unless the paper or user explicitly narrows the style search;
- at least one candidate must test the compact fastest-scan strategy, one must test actor/context grounding when actors are paper-relevant, one must test artifact/lineage clarity only when artifacts or variables are high risk and not merely because datasets are named, one must test temporal/update logic when feedback or rounds are paper-relevant, and one must test core-mechanism visibility when a contribution has non-droppable internals;
- no candidate may make data flow the dominant visual spine for a non-data-centered contribution unless S1 records a source-supported exception under `contribution_type_visual_priority`;
- pairwise overlap in primary module ordering is acceptable only when the canvas architecture and reader question are clearly different;
- if all candidates read as a left-to-right process with similar boxes and loops, the matrix fails even if the labels differ.

Record a compact `s2_layout_divergence_matrix` with candidate ID, narrative role, protagonist, visual spine, grid/region map, primary path, secondary path, and nearest-neighbor difference. Also record the eight-to-four style-combination selection matrix required by `references/style-combination-selection-and-human-palette-policy-v3215d.md`. If either matrix cannot show meaningful differences, rerun S1 or the S2 prompt packages before image generation.

## Layout Projection From Shared Semantics

A complete-framework batch may share the same paper backbone and edge registry, but it must not give every candidate the same visible projection. S2 embedded prompt preparation must convert the common semantic graph into a candidate-specific `layout_projection`:

- `primary_edges`: connector families drawn as the main path;
- `secondary_edges`: connector families compressed, bundled, miniaturized, or moved into a supporting corridor;
- `context_edges`: relations shown by grouping, callout, legend, or caption rather than main arrows;
- `hidden_or_caption_edges`: truthful secondary relations intentionally omitted from pixels with a caption note;
- `module_area_weights`: approximate visual-weight percentages for primary modules, secondary modules, context, detail panels, and legend;
- `layout_density_projection`: compact-balanced density target, context inset cap, usable-canvas occupancy, and physical-layout exception if any;
- `spatial_map`: relative canvas positions such as row/column grid, left/right/top/bottom regions, or radial/loop anchors;
- `route_corridors`: reserved lanes for data, model, control, communication, feedback, comparison, or callout connectors;
- `anti_similarity_directives`: explicit instructions preventing the candidate from becoming a near-copy of another candidate.

Do not dump the entire edge whitelist into every prompt with identical priority. If all edges are visually equal in every candidate, the generator will usually produce similar or cluttered layouts.

## Prompt Layout Grammar Requirements

Each S2 image-only prompt must include a hard `layout_grammar_block` after the reviewer takeaway and before the full edge contract. It must be written in plain natural language that an image generator can follow. It should include:

- canvas partition: number of rows/columns, major regions, or radial zones;
- anchor placement: where the 3-5 primary anchors sit;
- region weights: which region is largest and which are supporting;
- route corridors: where feedback/communication/cross-links travel without crossing the primary path;
- alignment rules: left-to-right, top-to-bottom, clockwise, inside-out, or other dominant scan order;
- non-overlap rules: legends, context panels, detail insets, and loops must not intrude into the main path, consume excessive canvas area, or shift the center of gravity away from the method;
- edge-bundling rule: related variables or artifacts share a labeled connector bus instead of parallel arrows;
- contradiction guard: do not add modules, arrows, or panels not listed in the candidate contract.

Vague phrases like "arrange cleanly", "use a different style", "make it an hourglass", or "use a storyboard" are insufficient unless supported by specific anchors and route corridors.

## S2 Image Audit For Diversity And Arrangement

During S2 embedded image review, assess generated images at two levels:

1. `individual_layout_sanity`: primary path obvious in 10 seconds; no equal-weight module map; major boxes aligned; route corridors reserved; loops do not wrap around and confuse the first read; rough sketch aesthetic remains organized.
2. `batch_narrative_diversity`: the set of generated candidates visibly tests different reader stories. If candidates are near-duplicates, mark a `candidate_similarity_issue` and rerun the corresponding prompt packages rather than judging the paper direction from repetitive outputs.

Record candidate similarity by visible spine, protagonist, first-read path, main module ordering, region map, and edge-routing pattern. If the batch fails diversity because image prompts over-shared the same layout wording, the fix is a prompt-matrix rerun, not paper-specific candidate selection.

## Generic Non-Hardcoding Boundary

Reusable skill files may describe the procedure and fields above, but must not include any target-paper module names, variable names, dataset names, or generated-output fixes. Project outputs may instantiate the fields using the current paper's evidence and risk register.
