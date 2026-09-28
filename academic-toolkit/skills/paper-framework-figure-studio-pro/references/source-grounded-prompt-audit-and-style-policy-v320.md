# Source-Grounded Prompt Audit And Paper-Serving Style Policy v3.2.3 + v3.2.11 Edge-Label/Internal-Motif Addendum

> v3.2.13 override: the assistant workflow ends at S5. This policy applies only to S0-S5 responsibilities and cannot create a assistant stage after S5.


This policy is paper-agnostic. Apply it to any research-paper framework figure, method overview, architecture diagram, pipeline figure, agent workflow, or mechanism explainer. Pair it with `references/paper-core-semantics-and-prompt-contract-policy-v323.md`, `references/edge-label-first-and-internal-motif-policy-v3211.md`, `references/visual-information-economy-and-repetition-control-policy-v322.md`, and `references/strict-source-grounded-modular-prompt-contract-policy-v3215a.md` for all S1/S4 prompt preparation, and additionally whenever semantic-backbone, connector, repeated visual family, variable-rendering, internal-mechanism, modularity, or low-redundancy risks are present. It must never encode facts from a particular paper, dataset, method name, or uploaded example.


## Core Grounding Rule

The image-generation prompt is part of the scientific claim. It must first follow the current paper-core semantics lock. Every requested visible element must be traceable to source evidence before it may enter the prompt:

- module, actor, dataset, artifact, state, variable, metric, formula token, operation label, icon metaphor, legend item, color meaning, line style, connector, arrowhead, merge/split, loop, panel title, callout, and claimed benefit;
- evidence may come from the paper body, equations, algorithms, tables, figures, supplementary material, the S0 deep-reading/foundation report, or author-supplied source clarification recorded in S0;
- S1/S4 contracts are valid only when they cite one of those source anchors;
- a user preference may choose style, emphasis, density, or which supported candidate to continue, but it does not authorize a new scientific relation, arrow direction, module, formula, result, or claim by preference alone.

If support cannot be found, the default action is removal. Other conservative actions are: convert a directed relation into a non-directional grouping/callout when association is supported but direction is not; move a verbal caveat to caption/legend; or block and route back to S0/S1/S4 for evidence rerun. Do not fill missing evidence with common field knowledge, plausible workflow intuition, or attractive visual symmetry.

## Source Audit Ledger

Before the image-only prompt is shown or saved, the text unit must maintain a compact ledger with these columns:

| Field | Requirement |
| --- | --- |
| `item_id` | Stable element or connector ID. |
| `visible_request` | What the prompt asks the image model to draw. |
| `semantic_role` | Paper-logic role: input, state, model, training step, evaluation signal, update, output, context, constraint, or explanation. |
| `evidence_anchor` | Paper section/equation/algorithm/table/figure/supplement line, S0 note, or recorded author source clarification. |
| `evidence_type` | `direct_text`, `equation`, `algorithm_step`, `paper_figure`, `table_result`, `supplement`, `S0_deep_read`, or `author_source_clarification`. |
| `allowed_pixel_form` | Specific visual primitive allowed in the image. |
| `not_allowed` | Unsupported labels, arrows, endpoints, directions, symbols, claims, or decorative embellishments. |
| `verdict` | `keep`, `simplify`, `caption_only`, `remove`, or `block_for_source_rerun`. |

The ledger may be summarized in the displayed response, but it must be sufficiently concrete in saved prompt packages to support later audits.

## Directed Arrow Evidence Protocol

Arrows are high-risk because they imply data flow, control flow, model updates, dependency, causality, evaluation, or communication direction. Every directed arrow must pass two separate checks:

1. `relation_supported`: the source and target are related in the paper or S0 report.
2. `direction_supported`: the paper or S0 report supports the exact arrowhead direction.

A directed arrow is allowed only when both checks pass. The image-only prompt must include an explicit allowed-arrow list, endpoint/port-binding constraints, and a no-extra-arrows constraint whenever arrow semantics matter.

For every connector, record:

- connector ID;
- source element and source port/side;
- target element and target port/side;
- semantic relation: data/artifact flow, model/state update, control/gating, evaluation/score, communication/exchange, dependency, containment, zoom/callout, or other paper-specific relation;
- line style and arrowhead rule;
- relation evidence anchor;
- direction evidence anchor for directed arrows;
- forbidden alternatives: reverse arrow, shortcut, duplicate edge, decorative line, unsupported feedback, unsupported merge/split, wrong producer, wrong consumer, wrong port.

Direction must come from a producer/current-step/evidence object to a consumer/next-step/result, or from a state/model to its explicitly updated target. Feedback, recurrence, bidirectional exchange, and synchronization may be drawn only when source evidence states that relation. If the paper states communication/exchange without a single direction, use a bidirectional exchange notation only when supported; otherwise use a non-directional grouping line, bracket, or caption note. If direction is absent or uncertain, omit the arrowhead.

For every carried item, confirm the actual consumer or transformer. Do not route a data/artifact/model/control/evaluation item through a visually intermediate module unless that module uses, transforms, filters, stores, routes, evaluates, updates, or emits the item. If A produces `x` and C consumes `x` while B does not use `x`, do not draw A->B labeled `x` or A->B->C as a false relay; draw A->C, attach `x` to C's input/port/tag, or move the item to caption/legend when necessary.

## Strict Modular Prompt Contract

S1/S4 image prompts must also pass the strict modular contract: no unsupported connectors; no repeated block-to-block lines unless distinct source-supported quantities are labeled; no false relay data-flow through modules that do not consume or transform the carried item; transferred variables on lines/ports/forks/merges/tags; modular structure rather than fragmented micro-blocks; simple reviewer-recognizable internal motifs; no duplicated workflow or redundant zoom; and background context kept minor. Apply a maximum of five audit/repair cycles before stopping with residual risk.

## Prompt Self-Audit And Revision Loop


- `PROMPT_READY`: all visible elements, text, formulas, connectors, arrows, styles, and detail panels are source-supported and readable;
- `PROMPT_READY_WITH_RISK`: only explicitly recorded, non-misleading limitations remain, and the user or workflow policy permits proceeding with that risk;
- `PROMPT_BLOCKED`: the figure cannot be prompted without unsupported content, contradictory evidence, missing direction evidence, or an unresolved scope/core-detail gap.

Do not expose an image-only prompt with known unsupported elements, invented arrows, uncontracted extra edges, unverified text, unsupported formula symbols, repeated equivalent full pipelines, repeated equivalent panels, edge-label-eligible variables requested as chips/boxes, semantic graph nodes leaking into visual nodes, core modules requested as bullet lists/title-only boxes, stage-style mismatch, misleading detail panels, or a failed first-glance layout gate. Prompt revision is allowed inside the current text-preparation turn because it happens before image generation; it is not the same as post-generation image rerun.

## Unsupported Evidence Diagnosis

When support is missing, record one of these diagnoses:

- `assistant_overreach`: the draft prompt invented or over-specified content; remove or simplify it.
- `paper_underspecified`: the paper names a module or relation but omits enough internal detail to draw it faithfully; record a risk and request author/source supplementation when the missing detail is core.
- `direction_absent`: the paper supports association but not direction; remove arrowhead or use a non-directional grouping/callout.
- `text_symbol_unverified`: visible wording, symbol, or formula token is not confirmed; replace with a generic visual mark or move to caption.
- `edge_label_first_violation`: a carried variable, metric, weight, parameter, or pass-through artifact is requested as a standalone chip/box without exception; convert it to an edge/port/fork/merge label or record a source-grounded artifact glyph exception.
- `false_relay_data_flow`: a carried item is routed through or labeled on a module that does not consume, transform, filter, store, route, evaluate, update, or emit it; reroute to the true consumer/transformer, attach it to the true input/port/tag, move it to caption, or remove the connector.
- `text_only_mechanism`: a source-grounded core module would be drawn as a title-only or bullet-list box; create an internal visual motif plan or block for source rerun.
- `style_misfit`: a visual metaphor, color, icon, or layout grammar creates a claim the paper does not support; choose a more literal style.
- `scope_mismatch`: the requested figure pretends to be complete while only a submodule or partial path is evidence-supported; mark scoped or route back to S1/S4.

If the missing item is central to the paper's claim and cannot be safely omitted, do not fabricate. Block the prompt and ask for S0/S1/S4 rerun or author clarification.

## Detail Panel And Zoom-In New-Information Test

A detail panel, inset, zoom bubble, cutaway, or magnified module is allowed only when it adds source-grounded information that is not already visible in the parent module, title, legend, or caption. It must not be a cosmetic duplicate.

For every detail panel or zoom-in, record:

- `parent_anchor_id`: the main-flow element being expanded;
- `new_information_added`: the specific internal substeps, state transition, formula token, evidence constraint, selection rule, scoring signal, update path, or failure-risk distinction added by the panel;
- `source_anchor_for_new_information`;
- `not_repeated_from_parent`: what the panel intentionally avoids redrawing;
- `foreign_module_exclusion`: content from other modules that must not be imported into this panel;
- `area_budget`: side/detail regions stay visually subordinate to the main framework unless the user explicitly requested a single-submodule explainer;
- `connector_style`: zoom/callout connectors use bracket, leader, stub, or clearly non-data-flow styling unless a data-flow arrow is source-supported.

A detail panel fails if it mainly repeats the main pipeline, duplicates a workflow already visible elsewhere, borrows internal details from another module, becomes the largest or first-glance region in a whole-framework figure, or uses its callout connector in a way that can be mistaken for data/model/control flow.

## Local Knowledge Base Style Selection

Local style and vector libraries are design aids, not scientific evidence. Before S1 creates the orthogonal S2 matrix, and before S2/S5 prompt compilation chooses visual grammar, consult the package's local knowledge resources when available, such as:

- `references/style-category-taxonomy-v309b.md`;
- `references/visual-style-and-board-protocol.md`;
- `references/vector-library/taste-bible-for-scientific-figures.md`;
- `references/vector-library/design_pattern_library_index.jsonl`;
- `references/vector-library/layout_pattern_index.jsonl`;
- `references/vector-library/preference_style_index.jsonl`;
- `references/vector-library/style-token-governance.md`;
- `references/vector-library/paper-grounded-style-extension-v320.md`;
- subtype atlas manifests and board policies when visual examples are needed.

Record a `local_kb_style_scan` with:

- which local resources were consulted;
- paper-derived visual needs: topology, actors, spaces, data/model/control paths, core-detail pressure, arrow-risk level, density limit, symbol need, caption burden, and expected reviewer question;
- selected style lenses and why each serves the paper;
- rejected style lenses and why they would mislead, clutter, over-metaphorize, hide core details, or increase arrow risk;
- `style_evidence_boundary`: a statement that style vocabulary influences layout and visual communication only, not paper facts.

## First-Round Orthogonal Style Combination Protocol

S1 must derive the first-round style space from the paper itself before assigning candidates. The goal is not visual novelty; it is to test multiple faithful reading hypotheses so reviewers can quickly grasp the paper.

Use at least four orthogonal axes, selected from:

- layout grammar: linear, swimlane, loop/lifecycle, hub-and-spoke, matrix/comparison, nested hierarchy, split-space, storyboard, scoped cutaway;
- reader path: problem-to-solution, actor-to-artifact, data-to-model, model-to-update, evidence-to-decision, local-to-global, coarse-to-detail, before-to-after;
- topology emphasis: centralized, decentralized/peer, hierarchical, multi-agent, actor-service, pipeline, retrieval memory, dual-space, multi-view, ensemble, graph/neighborhood;
- detail carrier: in-module mini-chain, internal visual motif, side inset, cutaway, micro-glyphs, formula token, state ladder, tiny table, compact distribution cue;
- connector grammar: straight lanes, orthogonal routing, separated data/model/control styles, bracketed grouping, non-directional association, explicit feedback loop only when supported;
- density: compact macro backbone, balanced overview, medium-detail, dense-but-readable stress test; sparse treatment requires an explicit physical-layout/story exception and must still pass the layout-density gate;
- visual rhetoric: mechanism reveal, contrast/comparison, lifecycle, contract/evidence ledger, consensus/alignment, uncertainty/gating, boundary/constraint, robustness/stress;
- aesthetic treatment: clean flat modular, blueprint grid, soft scientific editorial, compact technical dashboard, precise circuit-like routing, layered glass/cutaway, restrained storyboard.

For each candidate, state the paper-specific communication value being tested: faster first-glance, clearer actor separation, safer arrow semantics, more visible core internals, lower caption burden, stronger contribution reveal, or better handling of a paper-specific ambiguity. Reject a style slot if it differs only by color, ornament, texture, or rendering polish.
## Paper-Core Style Boundary And Stage Fidelity

Before choosing visual polish, load `references/paper-core-semantics-and-prompt-contract-policy-v323.md` and record the current project's `paper_core_semantics_lock`. A style lens may organize the semantics; it must not choose the semantics.

S2 is a first-round candidate exploration stage. Unless the user explicitly asks otherwise, use formal publication-style schematic wording such as clean academic framework figure, crisp module hierarchy, precise arrows, edge/port labels for carried variables, pictorial internal micro-motifs, and restrained color. Do not call S2 outputs final selected figures, glossy posters, photorealistic renders, or dense technical dashboards.

S5 may use cleaner schematic rendering, but it must carry forward S2/S4 risk notes and avoid previously audited failure categories. A polished style cannot rehabilitate unsupported arrows, unverified labels, cloned workflows, or detail panels that repeat rather than explain.


## Prompt-Level Style Rules

Image prompts may include style descriptors only after the source-grounded element and arrow plan is locked. Style descriptors must be operational and bounded:

- specify layout hierarchy, whitespace, grouping, line routing, label budget, icon family, and visual semantics;
- avoid decorative claims such as futuristic, magical, cinematic, photorealistic, or hyper-detailed unless explicitly requested and compatible with a paper figure;
- avoid icons that imply actors, data sharing, supervision, access/boundary constraint, causality, or evaluation not supported by the paper;
- use colors to distinguish source-supported categories or spaces, not to invent categories;
- keep text short and checked against the source ledger; use text as annotation, not as a substitute for required internal visual mechanisms;
- prefer fewer connectors with stronger provenance over visually rich but ambiguous networks; write carried variables on lines/ports/forks/merges by default instead of drawing standalone chips/boxes.

## v3.2.15f Style Combination And Human Palette Gate

Before S1 writes S2 prompt packages, it must follow `references/style-combination-selection-and-human-palette-policy-v3215d.md`: plan eight style-combination proposals, reject contradictory combinations, score the eight proposals, and write prompt packages only for the top four selected combinations. The four selected combinations must be complementary as a batch and internally non-contradictory within each row.

Before S4 writes S5 prompt packages, it must also follow the same human palette contract and prepare exactly two formal prompt rows. S4 must not use a palette that reads like generic AI tech art.

For S1 and S4 prompt audits, add these blocking findings:

- `contradictory_style_combination`: surface, density, visual rhetoric, connector grammar, or typography instructions pull the figure in incompatible directions;
- `style_combination_not_complementary`: selected style ingredients do not reinforce the same reader task or paper communication problem;
- `ai_palette_artifact`: neon gradients, glossy purple-blue glow, rainbow category ramps, glassy orbs, bokeh blobs, poster lighting, or over-saturated cyber palette dominate the schematic;
- `palette_semantics_unsupported`: colors imply unsupported categories, phases, actors, or data/model roles;
- `color_accessibility_risk`: color carries meaning without redundant line/shape/grouping/text cues or fails grayscale readability for manuscript use.

Repair these before S2/S5 image-only handoff. A visually attractive but AI-looking palette is still a prompt defect when it weakens publication readiness or human aesthetic credibility.

## S2/S5 Audit Emphasis

S2 and S5 prompt and image audits must give special attention to:

- unsupported visual elements or labels;
- directed arrows without relation and direction evidence, endpoint/port evidence, or edge-whitelist membership;
- false relay data-flow edges where a carried item is drawn through a non-consuming or non-transforming module;
- arrowheads reversed relative to evidence;
- generic workflow arrows not present in the paper;
- decorative arrows used for visual balance;
- unsupported merge/split, feedback, shortcut, hub, shared-resource, coordination topology, or cross-family connector;
- repeated actors, samples, arrows, panels, legends, or labels that should have been compressed into exemplars/groups/ellipses;
- repeated equivalent full pipelines or equivalent mini-flows that repeat rather than add source-grounded new information, especially when role/context variants could be compressed into a representative flow;
- detail panels that repeat rather than add source-grounded new information;
- detail panels importing another module's information;
- equal-weight island layouts, oversized context, or submodule-dominant figures for complete-paper tasks;
- symbols and formulas that are not necessary source-grounded anchors;
- edge-label-eligible variables, metrics, weights, parameters, or pass-through artifacts drawn as standalone chips/boxes;
- core compound modules whose required internals are title-only, empty, or bullet-list-only rather than micro-motifs;
- S2 style descriptors that make exploratory sketches look like final polished schematics when the user did not request that shift;
- S5 prompts that repeat known S2 failure patterns without an explicit source-grounded fix.

When a generated S2/S5 image contains a known unsupported connector or misleading detail panel, record the issue as `FLAG_MAJOR` or `BLOCKED` unless the stage policy allows and the user pre-authorized one rerun. Do not label such a candidate as clean because it is visually attractive.

## Post-S5 Boundary Removed In v3.2.13


After S5, human decisions are outside this assistant workflow.

- any visible arrow direction is unsupported, reversed, or ambiguous in a way that changes meaning;
- a connector creates a paper-unsupported data flow, control flow, model update, evaluation path, or topology;
- a connector makes a module appear to relay, carry, or receive a data/artifact/model/control/evaluation item that the module does not consume or transform;
- a visible module, label, formula, symbol, dataset, metric, or claim has no source anchor;
- an edge-label-eligible variable or metric is drawn as a standalone block without exception;
- a core mechanism that must be visually explained is shown only as a title or bullet list;
- a detail panel duplicates the main figure or imports content from another module;
- the final layout makes a submodule/detail panel the dominant region in a complete-paper figure;
- the requested user modification contradicts the evidence or weakens a core paper claim.

A caption or legend may clarify a correct visual relation. It must not rescue a false relation.

## File-Reference Prompt Handoff v3.2.4

S2/S5 image prompts can be too long for a reliable visible next-step prompt. embedded prompt preparation stages must save full prompts to files and save a prompt index. User-facing handoff prompts should name the prompt index or final prompt file and instruct the next image-only unit to read it, rather than inlining full candidate prompt bodies.

S2 default style is formal publication-style schematic unless the user explicitly asks for another compatible first-round style. S2 prompts should prefer polished but restrained academic structure, readable grouping, short labels, compact-balanced canvas use, and clear connector routing over glossy decoration or dense dashboard styling.


## v3.2.4 issue-ledger override

Use issue-ledger audit fields for S2/S5-related review outputs: record concrete issues, severity, rerun eligibility, high-priority issue status, downstream use, and caption burden. Hard contradictions become `BLOCKER_ISSUE` records. Do not use pass/fail labels as the sole selection verdict unless the user explicitly requests a filtering/ranking mode.

## First-Round Style Default Reminder v3.2.15f

S2 first-round prompt packages default to `formal_publication_schematic` unless the user explicitly overrides or cancels that surface-style choice in the S1 request before S1 finalizes S2 prompt packages. S0-to-S1 handoffs must include a compact non-blocking surface-style note outside the copyable S1 prompt block; that note lists compatible first-round surface options, including `acm_ieee_aaai_line_art_schematic`, and explains that the default surface may be cancelled so S1 derives the surface from paper needs. S1-to-S2 handoffs must repeat the available first-round surface-style menu as non-copyable prose outside the copyable S2 image-only prompt, so users still know alternatives exist; the note must explain that changing the first-round surface after S1 requires rerunning S1 before S2 because S2 follows the prepared prompt-index. S2 itself is image-only and should not discuss or renegotiate surface style; it follows the S1 prompt-index and the surface-style decision recorded by S1. The selected surface style must work with layout grammar, narrative role, semantic emphasis, density, connector hierarchy, human palette strategy, and source-grounded constraints.

## v3.2.15f source-faithful prompt hardening

In addition to source-grounded style selection, every S1/S4 image prompt must now pass a source-faithfulness and symbol-disambiguation audit before S2/S5 handoff. Every visible entity, relation, connector, symbol, variable, formula, metric, and label must be directly supported by the paper/materials/S0 report or derived through a recorded strict logical inference. Prompt content that contradicts the paper, overloads symbols, reverses arrow semantics, or introduces unsupported data/model/control/evaluation relations is a blocker, not a style issue.
