# First-Glance Layout Sanity Policy v3.2.2

Use this policy whenever S1 prepares S2 sketch cards, S1/S4 embedded prompt preparation builds image prompts, S3 review of S2 outputs screens generated images, or S4 prepares formal S5 candidate contracts. Pair it with `references/layout-density-mainline-balance-policy-v3215f.md` for canvas utilization, context-area caps, and mainline center-of-gravity gates.

This policy prevents paper-faithful but unreadable "everything map" figures and repeated-process clutter. It is generic and must not add paper-specific assumptions.

## Failure Pattern To Prevent

A candidate is layout-unsafe when it shows many true paper components but gives the reviewer no fast reading path. Typical symptoms:

- many equal-weight regions compete for attention;
- multiple mechanism islands sit around the canvas with no single dominant story lane;
- dense repeated dots, rows, entities, samples, legends, badges, arrows, or equivalent mini-flows consume area before the main mechanism is understood;
- many tiny data-point/sample-dot icons, copied actor pipelines, or repeated detail panels make the figure look like an inventory dump instead of a framework diagram;
- long border-return arrows, diagonal dashed connectors, or cross-panel callouts make route tracking harder than the method itself;
- constraints, caveats, training details, peer/context panels, and legends look like co-equal method blocks;
- large empty quadrants, oversized top/side panels, or context insets make the main method look visually secondary;
- micro-block islands are spread out with excessive gaps instead of grouped into compound method modules;
- the figure needs the caption or many labels before the reader can identify the main contribution.
- a local mechanism or one paper-primary path is visually clear but presented as if it were the complete framework;
- the framework backbone is visible, but source-grounded core modules are opaque named boxes with no in-place internals or connected detail carriers.

## Reviewer First-Glance Gate

Before `element_layout_plan`, write `reviewer_first_glance_gate`. It must include:

- `one_sentence_takeaway`: the single message a reviewer should get in about 10 seconds;
- `primary_reader_path`: 3-5 ordered visual anchors that form the first scan path;
- `main_flow_region`: the dominant canvas region and approximate visual-weight budget;
- `supporting_regions`: any context, detail, legend, peer, caveat, or training panels, each with its reason and area cap;
- `compression_plan`: repeated primitives or secondary facts to collapse into exemplars, ellipses, grouped stacks, cohort containers, count badges, shared-flow modules, or caption text; load `references/visual-information-economy-and-repetition-control-policy-v322.md` when repeated visual families are present;
- `complexity_budget`: planned counts for main regions, primary anchors, detail panels, in-image labels, connector families, feedback/return arrows, legends, and dense repeated groups;
- `drop_or_caption_list`: truthful but visually expensive facts that will not be drawn in the pixels.
- For complete-paper framework requests, also check that the primary path reaches the locked framework backbone and that every paper-primary path/core module has a visible anchor; otherwise the candidate is scoped or incomplete, even if the layout is visually clean.

If the candidate cannot state this gate clearly, do not build an image-only prompt. Rerun S1/S4, narrow the candidate scope, or move secondary material to caption/legend/body text.

## Default Complexity Budgets

Unless the paper or user explicitly requires more and the prompt records the reason:

- S2 sketch: 3-5 primary anchors, at most 2 supporting/detail regions, at most 6 connector families, at most 1 global feedback/return loop, at most 1 compact legend/caveat cluster.
- S5 formal candidate: 4-7 primary anchors, at most 3 supporting/detail regions, at most 8 connector families, at most 2 feedback/return loops, at most 1 compact legend/caveat cluster.
- Main framework or main reader path: normally about 65-85% of usable visual weight for algorithm/model/framework figures unless a recorded physical-layout exception applies.
- Each detail/support panel: normally under 15% visual weight; all detail/support/context panels together should usually stay under 25-30% and never visually outweigh the method mainline.
- In-image labels: short module names only; move definitions, caveats, and "why this matters" prose to caption.
- Data/sample/entity/agent/model icons: use only a few representative tokens, grouped stacks, ellipses, cohort containers, or aggregate glyphs. Avoid point clouds, scatter-like fills, copied full workflows inside many actors, repeated equivalent panels, and dense distribution backgrounds unless the requested figure is explicitly a statistical/evidence figure.

These budgets are prompt-readiness gates, not aesthetic advice. Do not satisfy them by shrinking text or making tiny crowded panels.

## Routing And Region Rules

- Draw the primary reader path as the cleanest lane. Prefer left-to-right, top-to-bottom, clockwise loop, or swimlane order; do not mix several equal reading orders in one candidate.
- Route feedback, peer exchange, or consensus loops in a reserved corridor that does not cross the primary path or labels.
- Avoid long outer-border arrows unless the paper has one canonical update loop and the source/target are explicit.
- Use containment, grouping, or caption notes for uncertain relations instead of arrows.
- Do not place two separate legends or constraint badges unless each resolves a distinct ambiguity that cannot live in the caption.
- Do not duplicate the same workflow in multiple rows/actors/side panels. Use one canonical shared flow plus compressed repeated groups unless source evidence requires distinct variants.

## Audit Verdicts

During prompt audit, set:

- `first_glance_verdict=PROMPT_READY` when the one-sentence takeaway, primary path, and complexity budget are coherent.
- `first_glance_verdict=PROMPT_READY_WITH_RISK` only when a documented paper requirement forces a complex layout and the compression plan names the risk.
- `first_glance_verdict=PROMPT_BLOCKED` when the candidate is an equal-weight mechanism map, lacks a primary path, exceeds the budget without reason, or relies on dense repeated primitives or duplicated workflows to explain the contribution.

During post-image S3 review and S4 prompt check, mark a generated image `FLAG_MAJOR` or `BLOCKED` if it fails first-glance comprehension, presents a scoped mechanism as the complete framework, or hides required core internals in opaque boxes, uses excessive repeated flows/elements, underfills the canvas with empty space, shifts the visual center to background context, or fragments the method into scattered micro-blocks, even when individual elements and arrows are paper-faithful.


## v3.2.4 issue-ledger override

Use issue-ledger audit fields for S2/S5-related review outputs: record concrete issues, severity, rerun eligibility, high-priority issue status, downstream use, and caption burden. Hard contradictions become `BLOCKER_ISSUE` records. Do not use pass/fail labels as the sole selection verdict unless the user explicitly requests a filtering/ranking mode.


## v3.2.12 S2 Rough-But-Ordered Layout Addendum

For S2 first-round candidates, rendering surface is separate from arrangement quality. A prompt or generated candidate fails first-glance sanity if its chosen surface becomes layout disorder: equal-weight boxes scattered across the canvas, unclear reading order, crossing-heavy routes, oversized legends, or long outer loops that dominate the story.

When S2 explores multiple first-round candidates, first-glance gates must also protect batch usefulness. Each candidate should have one visible visual spine and a distinct narrative role. If the four selected first-round candidates all read as the same left-to-right module map with different colors or minor panel positions, the batch has not tested meaningful figure directions.

Before image generation, every S2 candidate should include concrete placement language: canvas partition, 3-5 anchor locations, supporting-panel caps, route corridors, and anti-overlap constraints. If the layout cannot be described concretely, rerun the candidate card before generating the sketch.
