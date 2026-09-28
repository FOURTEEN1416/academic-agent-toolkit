# Visual Information Economy And Repetition Control Policy v3.2.3

After S5, human decisions are outside this assistant workflow.

This policy is paper-agnostic. It must not encode facts from a particular paper, dataset, task, author, project, file path, or uploaded example. Uploaded images may be treated only as visual anti-pattern evidence, not as scientific source evidence.

## Core Rule: Repetition Must Earn Pixels

A framework figure should expose the method's semantic structure derived from the current paper-core semantics lock, not enumerate every identical instance. Repetition is allowed only when it adds distinct information. Otherwise, compress repeated content into representative exemplars, grouped stacks, ellipses, braces, labels such as "parallel", loop markers, or caption/legend text outside the pixels.

`Complete` does not mean `replicated`. A complete method/framework diagram must preserve every paper-primary mechanism and path, but it must not redraw the same pipeline inside every repeated actor, sample, timestep, branch, or panel unless each copy carries a source-grounded distinction.

## Load Conditions

Load this policy when any of the following is true:

- S1/S2/S3/S4/S5 prepares an image prompt for a paper framework, pipeline, architecture, method, agent, data-flow, or mechanism figure;
- the paper contains repeated entities, agents, samples, data shards, models, rounds, local training loops, communication edges, layers, modules, modalities, or evaluation items;
- the user asks for fewer repeated elements, less clutter, less information redundancy, a cleaner figure, or non-repetitive workflows;
- a previous generated image contains many repeated icons, repeated panels, repeated rows, repeated pipelines, repeated arrows, point-cloud-like samples, decorative clones, or duplicated detail views;
- a detail or inset panel repeats the main diagram rather than adding new source-grounded information.

## Required Repetition Inventory

Before writing an image-only prompt, record repeated visual families through `element_instance_budget`. For repeated workflows, also record `repeated_flow_compression_plan`.

`element_instance_budget` must include:

| Field | Requirement |
| --- | --- |
| `element_class` | Actor, sample, data item, model, pipeline block, arrow family, layer, panel, legend item, result token, or other repeated primitive. |
| `paper_role` | Why this class appears in the method. |
| `semantic_variants` | Distinct roles or conditions that justify multiple visible instances. |
| `visual_plan` | Exemplar, grouped stack, ellipsis, loop marker, compact comparison, caption-only, or remove. |
| `multiplicity_cue` | How the viewer knows the concept repeats without seeing every copy. |
| `redundancy_risk` | What becomes redundant or crowded if all copies are drawn. |
| `verdict` | `keep_distinct`, `compress`, `caption_only`, `remove`, or `block_until_redesigned`. |

The default is to compress unless the source evidence and reader question require distinct visible instances.

## Semantic Uniqueness Rule

Every repeated visible element must pass the `semantic_uniqueness_test`:

- it represents a distinct paper-defined role, state, actor type, time step, comparison condition, error mode, or update target; or
- it is a minimal orientation anchor needed to show that a repeated operation is shared across entities; or
- the user explicitly requests instance-level enumeration and S0/S1/S4 evidence supports that exact enumeration.

If a repeated element does not pass this test, it must be compressed, merged, moved to caption/legend text, or removed before image generation.

## Shared-Flow Rule

When many entities perform the same operation, draw the operation once as a representative shared flow and show multiplicity with a compact aggregate cue. Prefer:

- one representative local pipeline plus a labeled group of peers;
- grouped stacks, small clusters, braces, ellipses, or a "same operation in parallel" cue;
- a single loop arrow with a round/update label instead of repeated round panels;
- one compact legend entry instead of repeating legend labels in every panel;
- a small symbol family for actor types instead of repeated large actors;
- an aggregate distribution cue instead of dense sample dots, point clouds, or repeated data cylinders.

Do not duplicate a full workflow row for every peer, entity, agent, view, dataset split, or round unless each row has a distinct paper-supported semantic role that cannot be represented by a compact comparison.
## Generic Role-Flow Separation

When a paper defines multiple entity variants, do not assume that every variant needs a full workflow lane. First decide whether the variants are:

- context markers for different inputs, roles, modes, modalities, actor types, or conditions;
- participants in the same canonical operation/update flow;
- genuinely distinct branches with source-grounded variant-specific operations;
- comparison conditions whose differences are the point of the figure;
- caption-only context.

Only the third and fourth cases can justify multiple visible full flows. In the first two cases, use a representative canonical flow plus compact variant markers, grouped tokens, braces, a small comparison chip, a role strip, a cohort container, or caption text. This rule is generic and must be filled with the current paper's own terms only in project outputs.


## Repeated Flow Compression

Repeated process chains are high-risk. Before an image-only prompt is saved, record a `repeated_flow_compression_plan` for each repeated workflow candidate:

- `flow_name`: the process or pipeline that might repeat;
- `semantic_variants`: which copies are genuinely different, if any;
- `compression_choice`: exemplar, grouped stack, ellipsis, brace, loop marker, caption-only, or explicit comparison;
- `visible_instances`: the minimum visible instances needed to preserve meaning;
- `not_drawn_instances`: how omitted repetitions are signaled without clutter;
- `why_not_redundant`: what new information any remaining repetition adds.

A prompt is blocked when it asks the image model to draw many equivalent copies of the same flow and the role-flow separation table plus compression plan does not prove that those copies add distinct source-grounded information.

## Distinction-Only Repetition Rule

A repeated element may remain visible only if it contributes at least one distinct paper-relevant meaning:

- a different actor/data role;
- a different state or timestep explicitly important to the method;
- a different input/output artifact;
- a comparison between conditions, baselines, modes, or spaces;
- an uncertainty, gating, evaluation, or selection distinction;
- a necessary topology, communication, or containment cue;
- a local zoom that adds hidden substeps not visible elsewhere.

If two repeated elements differ only by index, placement, decorative color, icon orientation, or label wording, collapse them.


## Symbol And Micro-Operation Compression

When the repeated or dense elements are mathematical variables, scalar quantities, temporary artifacts, control parameters, micro-operations, or many parallel connectors, apply `references/framework-abstraction-flowline-and-rerun-prompt-policy-v328.md` and `references/academic-framework-hierarchy-and-asset-mirroring-policy-v3210.md`. Default to edge labels, attached tags, compound gates, or caption-only explanations rather than full module boxes. A framework figure should not become busy because every pass-through symbol or parameter has been promoted to a standalone entity. Require `entity_density_budget` to justify the number of full visual nodes; otherwise merge, line-label, or caption-only low-level entities before generation.

## Prompt-Writing Constraints

Image-only prompts must explicitly forbid visual cloning when repetition risk exists. Use concise constraints such as:

- draw representative exemplars, not exhaustive duplicates;
- avoid repeated rows of the same pipeline;
- avoid many identical icons, dots, cylinders, cards, arrows, badges, or mini-panels;
- use ellipses, grouped stacks, braces, or a parallel-operation label to indicate multiplicity;
- keep the main reader path dominant and free of redundant side copies;
- do not repeat the same labels in main body, detail panel, legend, and caption.

Do not ask for "many", "dozens", "numerous", "dense", "richly populated", "lots of", or "a grid of" repeated elements unless the figure is explicitly an evidence/distribution figure and the density is source-supported and budgeted.

## Detail Panel Non-Repetition

A detail panel must add source-grounded internal information not already visible in the parent region. It may repeat only a minimal anchor such as the module name, one glyph, or one state token. If a detail panel redraws the same pipeline, the same actors, the same arrows, or the same data tokens without adding a distinct substep or relation, it is a redundancy failure.

When a detail is needed for one repeated actor group, attach it to the representative exemplar and label it as applying to the group. Do not attach equivalent copies of the same detail panel to every repeated actor.

## Audit Gates

During prompt audit, record `visual_information_economy_audit` after the element/layout/routing plan and before exposing the image-only prompt. The audit must report:

- repeated element classes identified;
- compression choice for each class;
- remaining visible instances and why each one adds new information;
- repeated-flow compression plan when a workflow could be duplicated;
- in-image text and legend de-duplication;
- whether any repeated detail panel merely restates the parent flow;
- verdict: `pass`, `risk`, or `block`.

During S2/S5 image audits, mark an image as `FLAG_MAJOR` or `BLOCKED` when it shows substantial non-informative repetition or clones a full workflow for variants that the paper-core semantics lock classifies as context/shared-flow participants, including repeated process lanes with the same blocks and arrows, many identical actors/samples/models/charts/labels, duplicate detail panels, repeated arrows that imply unsupported separate flows, dense sample/icon fields, or redundant legends that consume space needed for core mechanism internals.

If rerun is authorized, the rerun instruction should replace redundant copies with an exemplar-plus-aggregation representation, not merely shrink or rearrange the duplicates.

## Complete-Framework Interaction

For complete method/framework tasks, this policy does not permit hiding core mechanisms. Compression removes redundant instances, not paper-primary mechanisms. If compressing repeated copies would hide a core mechanism, keep one visible source-grounded anchor for that mechanism and move only redundant duplicate copies to grouped cues or caption text.

## Non-Hardcoding And Portability

This policy must remain general. It must not contain target-paper facts, fixed project IDs, absolute paths, user-specific file locations, uploaded-image descriptions as reusable rules, or package-time assumptions about how many entities, agents, samples, panels, or candidates a future paper has. Instance budgets, role-flow separation decisions, and compression plans are computed from the current project's S0/S1/S4 evidence and user constraints. Reusable rules describe how to derive them; reusable rules must not name the derived paper-specific roles, modules, variables, datasets, or candidate fixes.


## v3.2.4 issue-ledger override

Use issue-ledger audit fields for S2/S5-related review outputs: record concrete issues, severity, rerun eligibility, high-priority issue status, downstream use, and caption burden. Hard contradictions become `BLOCKER_ISSUE` records. Do not use pass/fail labels as the sole selection verdict unless the user explicitly requests a filtering/ranking mode.
