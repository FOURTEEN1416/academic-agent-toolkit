# Style Combination Selection And Human Palette Policy v3.2.15f

This policy is paper-neutral. Apply it whenever S1 prepares S2 prompt packages or S4 prepares S5 prompt packages.

## S1 First-Round Candidate Count

S1 must not prepare eight S2 image prompt packages. S1 must first design exactly eight candidate style combinations as a planning pool, then select exactly four final S2 candidates from that pool.

The eight planning combinations are not image candidates. They are scored style-combination proposals, such as `SC01`-`SC08`, used to choose the final `C01`-`C04` prompt packages. S2 must generate exactly four images from the S1 prompt-index.

The S1 output must include:

- `style_combination_pool`: exactly eight proposed combinations;
- `style_combination_selection_matrix`: numeric or ordinal scoring for all eight;
- `selected_style_combinations`: exactly four rows mapped to `C01`-`C04`;
- `rejected_style_combinations`: the four unselected planning combinations with concise reasons;
- `combination_complementarity_rationale`: why each selected combination's style ingredients reinforce rather than contradict one another;
- `palette_human_taste_contract`: the non-AI-looking color plan that all selected S2 prompt packages inherit;
- `layout_density_contract`: compact-balanced density, canvas area, context inset, and mainline focus plan that all selected S2 prompt packages must pass.

## Complementary, Not Contradictory

A style combination may combine axes such as layout grammar, reader path, density, detail carrier, visual rhetoric, surface style, connector grammar, typography, and palette. These axes must be mutually supportive.

Block or repair a combination when it contains contradictions such as:

- overly sparse minimal first-glance layout plus intentionally dense dashboard treatment;
- low-fidelity whiteboard surface plus publication-polished micro-typography expectations;
- hand-drawn storyboard surface plus strict ACM/IEEE/AAAI double-column line-art treatment in the same row;
- isometric/decorative perspective plus high-risk edge-label-first connector semantics that require flat clarity;
- bright multi-hue marketing palette plus manuscript-ready scientific schematic intent;
- metaphor/story treatment that conflicts with the required source-grounded module/arrow hierarchy.

For every selected row, record a short complementarity explanation. The explanation should name how the axes help one another, for example: "precision blueprint grid complements typed-edge routing because both prioritize port alignment and arrow disambiguation", or "scientific editorial light complements mechanism cutaway because restrained color and soft grouping make the internal motif legible without turning it into a poster".

## Selection From Eight To Four

S1 must score the eight planning combinations before writing S2 prompt packages. Use paper-specific reasoning, but keep reusable score fields generic:

- `paper_work_showcase_value`;
- `reviewer_attraction_hook`;
- `source_faithfulness_safety`;
- `complementarity_score`;
- `layout_divergence_value`;
- `core_mechanism_visibility`;
- `palette_human_taste_score`;
- `image_generation_feasibility`;
- `caption_burden_control`;
- `layout_density_and_mainline_balance`;
- `overall_selection_score`.

Select the four highest overall options only after applying hard gates, including the layout-density and mainline-balance gate from `references/layout-density-mainline-balance-policy-v3215f.md`. A lower-scoring option may replace a higher-scoring option only when needed to preserve essential batch diversity, and that replacement must be recorded in `selection_tiebreak_or_diversity_override`.

The final four must still form a useful set: normally one fastest-scan overview, one actor/space or topology/context view when relevant, one artifact/lineage or temporal/update view when relevant, and one core-mechanism/detail-emphasis view. If the paper makes one family irrelevant, substitute another source-grounded reader problem rather than adding a near-duplicate.

## Prompt-Index And IDs

S1 must create S2 prompt packages only for `C01`-`C04`, unless a future version explicitly changes the public count. The prompt-index must contain exactly four rows. The selected planning combination id may be recorded as `source_style_combination_id`, but it must not replace the candidate id.

S2 must read the prompt-index and generate exactly those four raster images. It must not generate images for the four rejected planning combinations.

## Human Palette Contract

Every S1 and S4 image prompt package must include a human-aesthetic palette contract. The goal is not a single fixed palette; the goal is to avoid the recognizable "AI diagram" look.

Required palette constraints:

- use a restrained, publication-grade palette with one primary accent, one secondary accent, and quiet neutrals unless the paper semantics require more categories;
- prefer softened scientific tones, muted blues/teals/greens/slates, graphite neutrals, and limited warm highlights over neon gradients, rainbow category coloring, glossy purple-blue glows, and over-saturated cyber palettes;
- keep large backgrounds white, near-white, or very light neutral unless the user explicitly requests a dark figure and readability remains publication-safe;
- use color redundantly with shape, line style, grouping, labels, or icons; never rely on color alone for meaning;
- avoid gradient blobs, bokeh/orb decoration, glassmorphism, glossy poster lighting, stock-illustration drama, generic AI-blue/purple gradients, and excessive saturated color ramps;
- choose colors to separate source-supported spaces, paths, or roles, not to invent new semantic categories;
- check grayscale legibility for line-art or manuscript contexts.

Every selected S1 combination and every S4 formal candidate must record:

- `palette_strategy`;
- `palette_semantic_mapping`;
- `palette_anti_ai_artifact_rules`;
- `human_aesthetic_rationale`;
- `color_accessibility_note`.

## S4 / S5 Formal Candidate Count

S4 must prepare exactly two S5 image prompt packages and a two-row S5 prompt-index, normally `F01`-`F02`. S5 must generate exactly two raster images.

If S3 preference carryover plus active S4 style/treatment slots would require more than two preference-led rows, S4 must repair/replan the style-slot allocation or ask the user to narrow preferences/styles before closing. It must not silently drop a recorded preference, and it must not create a third S5 candidate.

S4 must include the same human palette contract in every S5 prompt package. Formal candidates should look manuscript-ready and human-designed, not like generic AI-generated tech art.

