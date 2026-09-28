# Core Submodule Detail Policy v3.2.0

After S5, human decisions are outside this assistant workflow.

## Core Rule

A module that carries the paper's core engineering, algorithmic, system, experimental, or methodological innovation must not be an empty generic box. It needs a visible internal mechanism.

This rule is invariant under the fixed candidate contract policy. Removing standalone exhaustive per-image connector/edge/cardinality/area inventories from S2/S5 does not disable core-module internal-detail contracts. S1 and S4 must still write compact internal-detail locks for source-grounded core contribution modules, and S3 must flag S2 images where those modules are drawn as labels, icons, or empty containers without the required internal chain.

Internal mechanism detail must be simple and reviewer-recognizable. Prefer compact, common schematic conventions—model glyph, probability bars, threshinactive gate, merge/fork cue, score tag, or light update loop—over dense miniature algorithms, numeric tables, or uncommon visual metaphors. The goal is to make the module readable in a few seconds, not to redraw the full implementation.

The figure is still a whole-framework figure, not a single-submodule explainer. The visual must show how important contribution modules work at an appropriate submodule level, but no one module should dominate the canvas so much that the global framework becomes secondary. If the main architecture diagram cannot hinactive this detail cleanly, use a balanced main-framework plus detail-panel layout: a top or upper two-thirds main flow with lower detail panels; a left/center main flow with a right-side vertical detail strip; or another inset/callout layout that keeps the global reader path primary. Detail panels must share the same visual language, color semantics, icon family, and connector rules as the main framework.

Main-flow dominance is an invariant. The main framework must be the largest single region, the first reader path, and the highest-priority visual structure. Detail panels, zoom panels, local mechanism cutaways, domain blocks, example panels, and named submodules must be visually subordinate to the main framework. As a default planning budget, allocate roughly 55-70% or more of visual weight to the main flow, keep each detail panel at or below about 20-25%, and keep the combined detail layer below the main framework's visual dominance. A candidate whose largest area is a single submodule, modality/task-specific block, formula panel, example panel, or detail inset is not a whole-framework figure unless the user explicitly requested that narrowed scope.

For S1/S2 sketches and S4/S5 formal candidates, a core module label plus an icon is not sufficient. The candidate must include a core-module internal contract before image generation: `sketch_core_internal_tokens_lock` in S1 for S2, and `core_module_internal_contract` in S4 for S5. The contract must state:

- the required visible inputs;
- the internal operation, change, decision, measurement, selection, routing, validation, actuation, update, construction, or transformation step;
- the required visible output;
- the exact connector provenance for every input and output arrow;
- the allowed input/output ports for the module, so the image-generation model cannot attach a plausible-looking arrow to the wrong side or wrong subtoken;
- the minimum internal visual tokens that must appear in the generated raster;
- a rerun trigger if the generated image collapses the module into an opaque box.

Under the fixed candidate contract policy, this contract may be compact, but it must still be present for every source-grounded core module. Exhaustive connector-provenance inventories, full port tables, and full area-budget ledgers are not exposed as user-selectable contract options; the core module's visible inputs, internal operation, outputs, and opacity gate remain mandatory.

For example, a source-defined core module is not covered by a box labelled only with its acronym. The image must show the paper's own compact internal chain, such as its required inputs or context, operation/substeps, decision/measurement/transformation signal, selection/routing/control/update rule, and output or effect. Use the target paper's own terms and evidence; do not blindly copy any generic example.

The detail view must add information rather than duplicate the main diagram. A side inset, zoom-in panel, cutaway, or split-panel detail is valid only when it has a distinct role:

- the main body gives the global reader path and a compact anchor for the submodule;
- the detail layer expands only the internal substeps, decision points, or token transformations missing from the main body;
- the caption/legend carries definitions, caveats, and dense explanations.

After S5, human decisions are outside this assistant workflow.

Side insets, detail strips, cutaways, and zoom panels are not permission to explain the same thing twice inside the raster or to duplicate the same workflow across many repeated actors. For S5 formal candidates, the detail view must remain locally anchored to the relevant module or path, subordinate to the main reader flow, and limited to information that the main body intentionally compresses. Any repeated element must pass the `new-information test` and the repetition-compression gate in `references/visual-information-economy-and-repetition-control-policy-v322.md`: it must add a distinct mechanism substep, relation, comparison, orientation cue, or disambiguation cue. If a repeated element only restates the main body, title, caption, legend, or another detail layer, it is a hard redundancy failure.

If the paper spends substantial method prose on an idea, provides formulas for it, or explicitly frames it as an improvement over a prior method/baseline, that idea is a core-innovation candidate until S0 records otherwise. It must have a clear visual anchor in the image. Caption text may explain the anchor, but cannot be the only place where the innovation appears.

## Non-Droppable Core Substeps

Reorganization and simplification may change layout, grouping, names, and visual order, but they must not delete source-grounded core substeps. When S0 identifies a core module with an internal sequence, S1 and S4 must split it into non-droppable substeps before S2/S5 image generation.

Generic non-droppable operation classes include:

- preparation, configuration, construction, calibration, fabrication, initialization, or setup that makes a later component, material, state, policy, route, or structure possible;
- transformation, processing, inference, generation, synthesis, measurement, actuation, control, or assembly that changes an input, state, signal, object, structure, sample, material, or condition;
- validation, evaluation, inspection, sensing, comparison, scoring, or verification that produces evidence, confidence, quality, reward, risk, feasibility, or acceptance;
- decision, selection, filtering, routing, scheduling, thresholding, arbitration, or allocation that changes what continues downstream or which action is taken;
- update, aggregation, optimization, feedback, adaptation, compensation, synchronization, storage, or deployment that uses the intermediate evidence, state, signal, structure, or output.

A visible output, state, structure, decision, signal, material, configuration, sample, or effect alone does not cover the upstream operation that creates, selects, transforms, validates, routes, applies, or updates it. A feedback or update arrow alone does not cover the evidence-producing, decision-making, or transformation step that justifies that action. A generic module label such as "processor", "controller", "planner", "fabricator", "sensor", "optimizer", "aggregator", "scheduler", "converter", or "evaluator" is not sufficient when the paper's contribution depends on how that module is constructed, configured, measured, operated, evaluated, connected, or applied.

For example, if a paper states that one module is prepared from accepted inputs, performs a key operation, and then affects a downstream decision, state, structure, control action, artifact, or evaluation, a faithful figure/candidate contract must preserve all three ideas at the appropriate level: source/context, operation/change, and output/effect target. These can be shown as a compact mini-chain, an inset, or a small storyboard panel, but they cannot be silently collapsed into only "module produces output" or only "module is updated".

If the paper frames two or more core spaces, paths, agents, modules, objectives, or model families as peers, each peer inherits the non-droppable rule. A candidate that visibly explains one peer path but reduces another declared peer mechanism to a small "update" box is incomplete. Preserve the target-specific internal sequence, for example proxy or evidence -> score or criterion -> decision or weight -> update/action target.

## Core Operation Chain And Location Binding

Every source-grounded core mechanism must be reduced to the minimum operation chain that makes the claimed artifact, state, signal, structure, decision, material, configuration, route, control action, or effect possible. Use the generic pattern `input/context -> operation/change -> output/effect` unless the paper evidence requires a different sequence. This pattern is a planning guard, not a fixed visual template.

S1 and S4 must bind each image-required core operation to its visual location before image generation. The binding must state:

- `parent_module_id`: the module, block, subsystem, layer, experiment stage, process step, or mechanism container that owns the operation;
- `parent_stage_or_phase`: the phase, loop, path, layer, round, condition, cycle, or branch where the operation occurs when the source supports such a distinction;
- `input_or_context`: the source-supported input, condition, prior state, material, signal, object, or constraint that enters the operation;
- `operation_or_change`: what is created, selected, transformed, measured, routed, validated, applied, controlled, stored, updated, or otherwise changed;
- `output_or_effect`: the source-supported result, state change, action target, downstream consumer, or effect carrier;
- `visible_location_strategy`: in-place mini-chain, side inset, local loop, port/edge tag, storyboard strip, state-transition token, measurement/decision gate, or other compact visual carrier;
- `non_substitution_rule`: the downstream result, effect, arrow, or module title that must not be counted as coverage for this operation.

If a core operation has no recoverable visual location, S1/S4 must either revise the layout, move the operation into a connected detail carrier, or mark the candidate incomplete before image generation. It must not rely on a caption-only explanation when the operation is image-required and source evidence exists.

## First-Round Image Visibility Gate

After S5, human decisions are outside this assistant workflow.

For every S2 sketch and S5 formal candidate, each source-grounded core step marked as image-required for that stage must be recoverable from the image pixels themselves through compact labels, symbols, arrows, icons, mechanism chains, panel order, or a connected inset. The pre-image explanation, figure title, caption, and legend may define symbols and explain why the chain matters, but they cannot be the only place where a non-droppable core step appears.

If a step is essential but would clutter the main architecture, S1/S4 must choose a visual containment strategy before image generation: mini-chain, side inset, zoom-in, cutaway, local loop, storyboard panel, or a small equation/symbol anchor. If none of those can make the step visible, the text stage must mark the candidate incomplete and rerun the design instead of generating an image.

## Two Valid Display Modes

For every core innovation submodule, choose one of these modes before image generation:

1. `in_place_internal_detail`: show the internal mechanism inside the main architecture module. Use nested blocks, micro-flow arrows, gates, token/object transforms, loop markers, retrieval/update paths, or formula tokens when essential.
2. `side_inset_detail`: keep the main module compact, then draw a side inset or zoom-in detail panel that exposes the internal mechanism. Connect it to the main module with a clean callout line or numbered anchor. Prefer several small, coordinated detail panels when multiple modules are important, rather than allowing one enlarged panel to visually overrule the framework.

A candidate may combine both modes only when the result stays readable.

For `side_inset_detail`, use a clean detail connector:

- prefer short callout stubs, elbow connectors, bracketed zoom frames, or numbered anchors;
- avoid long diagonal dashed callouts that cross the main flow or point ambiguously from a module to multiple panels;
- keep zoom/callout connectors visually distinct from model-exchange dashed arrows;
- if a dashed connector is used, its meaning must be recoverable from the figure and caption.

Ambiguous or visually noisy callout paths are not cosmetic. They can make a paper figure semantically misleading and should be treated as image rerun issues.

`no detail panels` is not a third display mode. It is allowed only when every source-grounded core module uses `in_place_internal_detail` inside the main framework module. A candidate that has neither in-place internals nor connected detail panels for a required core module fails the core-module opacity gate even if the module name appears in the main flow.

For complete-paper overview candidates with multiple core modules, do not satisfy this policy by making one module richly detailed while leaving the other paper-primary modules as opaque labels. Each core module needs its own compact visible input -> internal operation/substep -> output/action carrier. The carriers may be tiny, but they must be recoverable from the image pixels and connected to the main framework backbone.


## Detail Panel New-Information And Boundary Rule

When a core module is shown through a side inset, zoom bubble, cutaway, storyboard panel, or detail strip, the detail view must add source-grounded information that is not already visible in the parent module. It must not simply redraw the parent pipeline at larger scale. It also must not import internal steps, symbols, inputs, outputs, or claims belonging to another module unless the paper explicitly states that cross-module relation and the connector contract supports it.

Every detail view must record: `parent_anchor_id`, `new_information_added`, `source_anchor_for_new_information`, `not_repeated_from_parent`, `foreign_module_exclusion`, `area_budget`, and `callout_connector_style`. If the source material lacks enough information to add genuine internals, record `missing_core_detail_evidence` and use an in-place compact token or caption caveat rather than fabricating a detail panel.

A detail view fails the core-detail policy when it duplicates the main flow, becomes the dominant region in a complete-paper figure, uses a callout that looks like unsupported data/model/control flow, or mixes content from another module in a way that changes the paper meaning.

## Mathematical Symbols And Simple Formulas

Internal mechanism detail may include mathematical symbols or a small number of simple formulas when they help reveal the contribution. Use them only when all of these are true:

- the symbol or formula is central to the visible mechanism;
- without this symbol/formula anchor, the figure cannot express the paper's core idea or claimed improvement precisely;
- it is simple enough to understand without reading the full method section;
- it is likely introduced before the architecture figure, or the candidate title/caption/legend can explain it briefly;
- it replaces a long prose explanation rather than adding clutter.

Do not put derivations, multi-line equations, proof fragments, or dense formula explanations into the figure. Put those in the pre-image candidate explanation, caption, legend, or body text.

For symbols such as \(w_i\), prefer visual self-explanation first: place the token near the producing module, connect it with an arrow to the receiving module, and keep the token readable. The caption may add one concise phrase such as "the generated weights \(w_i\) are passed into the aggregation module"; avoid longer explanatory paragraphs unless the user explicitly wants a dense technical figure.

## Required Planning Fields

S1-FIGURE-STRATEGY and S4-CANDIDATE-BRIEF must identify:

- `core_innovation_modules`: the modules that carry the paper's main contribution;
- `core_mechanism_substeps`: the source-grounded internal sequence for each core module;
- `core_module_internal_contract`: for each core module, its visible inputs, internal operation, output, connector provenance, internal tokens, and rerun trigger;
- `core_operation_chain_ledger`: the minimum source-grounded `input/context -> operation/change -> output/effect` chain for each core mechanism;
- `core_operation_location_binding`: where each image-required operation is located in the visual structure and which parent module, stage, loop, path, layer, or phase owns it;
- `operation_result_non_substitution_audit`: proof that visible outputs, states, effects, update arrows, or module titles are not being counted as coverage for the operations that produce or justify them;
- `image_required_core_operation_location_plan`: the concrete pixel-level carrier for every image-required operation, including in-place mini-chain, side inset, local loop, port/edge tag, storyboard strip, state-transition token, measurement/decision gate, or compact formula/symbol token when justified;
- `non_droppable_core_steps`: the subset that must remain visible in the S5 image itself when source evidence exists;
- `image_required_core_steps`: the non-droppable steps that must be visible as pixels in every formal candidate;
- `image_core_step_visibility_plan`: for each image-required step, the concrete visual carrier: in-module mini-chain, side inset, zoom-in, cutaway, storyboard panel, symbol/arrow relation, or simple formula token;
- `substep_coverage_plan`: for each non-droppable substep, whether it appears in the main image, side inset, or storyboard panel, plus any caption text that only explains it;
- `internal_mechanism_summary`: what happens inside each module;
- `detail_display_mode`: `in_place_internal_detail` or `side_inset_detail`;
- `detail_visual_tokens`: internal blocks, arrows, formula tokens, simple formulas, gates, state transitions, memory/retrieval paths, optimization loops, or other visual atoms;
- `visible_math_symbols_or_simple_formulas`: which mathematical tokens are visible and why they are understandable before the full method section;
- `symbol_formula_necessity_proof`: a short reason why each visible symbol/formula is necessary; if no such reason exists, do not draw it;
- `claimed_improvement_visual_anchor`: how any explicitly claimed improvement, formula-backed mechanism, or heavily described innovation appears in the image;
- `empty_box_risk`: whether the candidate risks hiding the core contribution in a blank container;
- `caption_support`: which definitions stay in the pre-image explanation/caption rather than inside pixels;
- `caption_only_core_step_forbidden`: true for S5 formal candidates unless source evidence is missing and the risk is recorded;
- `redundancy_budget`: which elements may repeat between main body and inset, and why;
- `inset_information_division`: what the main body shows, what the inset adds, and what the caption/legend explains;
- `detail_panel_new_information_plan`: parent anchor, source-grounded new information, non-repetition proof, foreign-module exclusion, area budget, and callout-vs-data-flow connector style for each detail panel or zoom;
- `semantic_uniqueness_plan`: the primary visual carrier for each core semantic idea, plus the distinct role of any allowed repetition;
- `no_duplicate_explanation_plan`: how repeated modules, examples, tokens, legend definitions, caveats, and formula meanings will be removed, compressed, moved to caption/legend text, or represented by one exemplar plus ellipsis;
- `connector_quality_plan`: how callout lines, dashed connectors, zoom anchors, and model-exchange arrows are separated and kept readable;
- `main_flow_area_budget`: the approximate area, centrality, contrast, and first-read path reserved for the whole-paper framework;
- `detail_panel_area_budget`: approximate area for each inset/detail panel and the combined detail layer;
- `main_flow_dominance_guard`: pass/fail criterion that the main framework remains the largest region and no named submodule/detail panel becomes visually dominant;
- `largest_region_must_be_main_flow`: true for whole-framework figures unless the user explicitly requested a single-submodule explainer;
- `core_module_opacity_gate`: pass/fail criterion for whether each generated S2/S5 image visibly exposes the core module internals required for that stage rather than only naming the module.
- `sketch_core_internal_tokens_lock`: the S2 first-round version of the core internal token requirement; it must name the minimum visible internal mechanism tokens for each S2 candidate before the environment-locked image-generation route.
- `sketch_port_binding_table`: the S2 first-round port contract for high-risk modules, naming allowed and forbidden inputs/outputs before the environment-locked image-generation route.
- `sketch_prompt_ready_check`: pass/fail criterion for whether the S2 prompt preserves required core internals rather than asking the image-generation model to infer them.
- `consensus_space_priority_map`, `visual_weight_plan`, `must_show_for_each_space`, and `missing_information_risk` when multiple peer spaces or peer consensus mechanisms are part of the contribution.

## What Must Be Visible

When source evidence exists, show at least one of the following for each core innovation module:

- internal data/control flow;
- algorithm step sequence;
- model subcomponent relation;
- token/feature/state transformation;
- material, structure, signal, object, configuration, route, or condition change;
- measurement, sensing, inspection, validation, or decision gate;
- control, actuation, allocation, scheduling, synchronization, storage, or feedback action;
- optimization, matching, retrieval, selection, or update loop;
- loss/objective signal or formula token if it is part of the mechanism;
- interaction between two or more internal entities.

Do not replace these with a decorative icon, a single unlabeled rectangle, or a generic label such as "Core Module" when the paper provides more detail.

Do not add symbols, variables, equations, or formula-like tokens merely to make the figure look technical. They are valid only when they are necessary anchors for the paper's core idea or improvement and are explained by the caption/legend.

If a core module has multiple non-droppable substeps, at least the sequence relation must remain recoverable in the S5 image itself. The image can use short source-specific tokens such as `prepare -> transform`, `sense -> decide`, `measure -> validate`, `configure -> actuate`, or `score -> route`, and the pre-image/caption contract can explain the words. However, the plan must not count a later output, effect, state, arrow, or module title as coverage for the earlier operation that creates, selects, transforms, validates, routes, applies, or updates it.

## Review Rule

After S5, human decisions are outside this assistant workflow.

After S5, human decisions are outside this assistant workflow.

S2 and S5 must run the `core_module_opacity_gate` and `core_step_location_coverage_gate` immediately after each generated image. If any core module appears only as a titled rectangle, icon, high-level label, output/effect token, or update arrow while the paper provides internal operation evidence and the stage lock requires visibility, do not mark the image as a clean pass. Record `missing_core_operation_step`, `missing_operation_location_binding`, `output_or_state_substituted_for_operation`, `opaque_core_module_error`, or `unanchored_core_effect_error` as appropriate. By default, mark the candidate as `FLAG_MAJOR` or `BLOCKED` in the report under `references/s0-foundation-readiness-and-candidate-status-policy-v316.md`. Do not offer candidate-level rerun from this finding; carry the issue into S3/S4 risk transfer, or require an explicit upstream rerun request from the user.

After S5, human decisions are outside this assistant workflow.

- the main framework is not the largest single visual region or first reader path;
- one submodule, domain/modality/task-specific block, zoom panel, example panel, or detail inset takes over the canvas;
- the inset mostly duplicates the main pipeline instead of adding missing internal mechanism;
- the same blocks, icons, labels, and arrows appear in multiple layers without an explicit need;
- any visible panel, key, text block, callout, icon cluster, arrow group, or repeated chain fails the `new-information test`;
- callout connectors cross core flows, point ambiguously, or are visually confused with model-exchange arrows;
- the figure is accurate only after the reader mentally ignores redundant panels, repeated full pipelines, dense repeated primitives, or confusing dashed lines.

If the paper/source material does not contain enough information to draw the internal mechanism, the step must record `missing_core_detail_evidence` and ask for source material or mark the risk. Do not fabricate internal details.


## v3.2.4 issue-ledger override

Use issue-ledger audit fields for S2/S5-related review outputs: record concrete issues, severity, rerun eligibility, high-priority issue status, downstream use, and caption burden. Hard contradictions become `BLOCKER_ISSUE` records. Do not use pass/fail labels as the sole selection verdict unless the user explicitly requests a filtering/ranking mode.
