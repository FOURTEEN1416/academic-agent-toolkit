# Figure Caption Co-Design Policy

Candidates are planned as bundles:

```text
pre-image candidate introduction + generated raster candidate image
```

In v3.2.2, the stronger rule is figure-caption symbiosis: the figure and caption are one explanatory unit. The caption is not a generic afterthought. It must match the adopted figure style, reader path, visual grammar, arrow/color/icon/symbol semantics, and any evidence layer intentionally kept out of the image.

S1 must introduce at least 8 planned S2 sketch candidates before image generation. S4 must introduce every planned S5 formal candidate before image generation.

Required S2 fields:

- candidate_id
- figure_title
- figure_intent
- candidate_scope
- whole_paper_coverage_map
- coverage_status
- scope_limitation when scoped
- global_context_strategy
- pre_image_explanation_draft
- symbol_visual_legend
- in_image_text_budget
- caption_support_note
- reader_understanding_test
- consensus_space_priority_map when applicable
- visual_weight_plan when applicable
- must_show_for_each_space when applicable
- redundancy_budget
- element_instance_budget when repeated visual families are likely
- repeated_flow_compression_plan when repeated workflows are likely
- visual_information_economy_audit when repetition risk exists
- semantic_uniqueness_plan
- no_duplicate_explanation_plan
- dual_use_artifact_plan when applicable
- missing_information_risk

For complete-paper framework requests, S1 must follow `references/complete-framework-candidate-eligibility-policy-v321.md`: every required S2 candidate card must be `complete_method_overview` or `complete_story_overview`, must pass the complete-framework eligibility gate, and must not be scoped, partial, mechanism-only, context-only, or style-only. Scoped probes may appear only as explicitly user-authorized `auxiliary_non_candidate_probes` and must not count toward the required S2 batch. A story-driven candidate counts as complete only if the visible story tokens cover the paper's central problem/constraint, all core method paths, paper-primary spaces/paths, and output/update target. Otherwise it is an auxiliary scoped story probe and must say so.

Required S5 fields:

- candidate_id
- figure_title
- figure_sentence
- pre_image_explanation
- symbol_visual_legend
- in_image_text_budget
- visible_math_symbols_or_simple_formulas
- kept_out_of_image
- reader_understanding_test
- caption_risk_or_missing_context
- image_required_core_steps
- image_core_step_visibility_plan
- core_module_internal_contract
- connector_provenance_table
- area_budget_by_region
- evidence_locked_prompt_package
- consensus_space_priority_map when applicable
- visual_weight_plan when applicable
- must_show_for_each_space when applicable
- redundancy_budget
- element_instance_budget when repeated visual families are likely
- repeated_flow_compression_plan when repeated workflows are likely
- visual_information_economy_audit when repetition risk exists
- semantic_uniqueness_plan
- no_duplicate_explanation_plan
- dual_use_artifact_plan when applicable
- missing_information_risk

After S5, human decisions are outside this assistant workflow.

Caption wording must be style-aware. A mechanism-first schematic caption should describe the mechanism path; a pipeline caption should describe stage transitions and arrow classes; a split train/inference caption should separate phases; an evidence-panel caption may carry target-paper facts, metrics, and caveats that would distract inside the image; a story-like caption must bridge the story back to the paper's own method with close, common concepts.

Borrowed reference layouts can contribute caption strategy, grouping rhythm, reader path, and evidence placement, but their paper-specific facts, numbers, labels, symbols, claims, datasets, and metrics must not transfer into the target-paper caption.

For S5 formal candidates, caption/legend text cannot be the only carrier of a non-droppable core algorithm step. If a step is required to understand the paper contribution, it must appear in the image body, a connected inset, zoom/cutaway, compact mechanism panel, or another visible carrier. The caption may explain the visible step, but it may not replace it.

For source-grounded core modules, `core_module_internal_contract` is required under the fixed candidate contract policy. It is not a user-selectable optional audit layer. A formal S5 candidate is not prompt-ready if a core module is only named in the title, caption, legend, or a high-level box while its internal paper-supported substeps have no planned visual carrier.

For S5 formal candidates, connector meaning also cannot be reruned by caption alone when the connector itself implies a false relation. Any non-trivial arrow must have a preplanned source, target, paper evidence anchor, semantic relation, and line style. If the generated image invents a connector, merges arrows without evidence, or points from an update/score/model module to an upstream data object without source support, the candidate must be reruned or rejected rather than caption-explained.

After S5, human decisions are outside this assistant workflow.

When the paper contribution depends on multiple co-primary spaces, paths, or mechanisms, caption text cannot compensate for visually demoting one primary path to a tiny side note. The image must give each paper-primary space/path visible anchors and a reader path. Caption may define variables, caveats, and exact formulas, but it cannot be the only place where a core mechanism chain appears.

After S5, human decisions are outside this assistant workflow.

S5 defaults to clean publication schematic raster references. These are images, not SVGs. SVG/PPT approximation is only a downstream editability consideration; semantic fidelity, style-caption fit, and paper-grounded icon/arrow/color meaning are more important than forcing a vector-oriented look.

Story-driven narrative candidates marked in S1 or S4 default to compact, non-overfilled internal elements, an obvious reader path, intuitive objects, lightly cartoon-like schematic elements when useful, and an explicit close-to-paper caption bridge.

After S5, human decisions are outside this assistant workflow.

## Generic Caption-Aware Candidate Audit Addendum v3.2.4

After S5, human decisions are outside this assistant workflow.

S4 may plan candidate-level figure/caption division of labor, but no assistant-side caption package is created after S5.
