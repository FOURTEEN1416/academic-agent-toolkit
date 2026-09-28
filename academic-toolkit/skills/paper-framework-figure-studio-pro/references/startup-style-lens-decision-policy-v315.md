# Startup Style-Lens Decision Policy v3.1.6

This policy governs early style selection for S1-FIGURE-STRATEGY and formal style treatment selection for S4-CANDIDATE-BRIEF.

The startup atlas boards are first-level entry points, not final style contracts. If a local prompt or UI names them as F1-F4, use this mapping:

| Entry | Atlas board | Decision axis | What it can influence |
|---|---|---|---|
| `F1` | `subtype-overview` | figure role / paper slot | method framework, architecture, pipeline, workflow, mechanism, case walkthrough, evidence board |
| `F2` | `visual-grammar-layout` | structural grammar | block pipeline, central core, swimlanes, graph network, layer stack, storyboard, matrix map, zoom callouts |
| `F3` | `reader-role-detail` | reader question and detail density | first-glance message, parts-and-flow, idea-to-model bridge, temporal story, core case, compact/dense detail |
| `F4` | `visual-communication-styles` | visual communication surface | clean flat, formal schematic, minimal line, blueprint, scientific illustration, isometric, interface metaphor, infographic board |

After the first-level atlas entry is chosen or inferred, S1 and S4 must map it into a second-level `style_lens_id` from `references/style-category-taxonomy-v309b.md`. A style lens is a joint decision about paper narrative, structural grammar, information density, caption burden, icon/arrow/legend semantics, and downstream layer extraction/vector reconstruction feasibility.

## Required Style-Lens Fields

Every S1 sketch candidate card and every S4 formal candidate brief must include:

- `level_1_atlas_entry`: one or more of `F1`, `F2`, `F3`, `F4` or the corresponding atlas board IDs.
- `style_lens_id`: one of the style lens IDs in `style-category-taxonomy-v309b.md`.
- `paper_logic_fit`: why this lens fits the target paper's contribution, method structure, reader question, and evidence.
- `structure_grammar_fit`: the layout grammar and reader path that the lens will use.
- `density_budget`: expected module count, visible labels, formula/symbol load, local-detail allowance, and omitted-to-caption content.
- `caption_burden`: what the caption/legend/body-reference text must explain because the image should not carry it.
- `icon_arrow_legend_semantics`: what icons, arrows, colors, line styles, ports, and legend entries mean.
- `layer_extraction_vector_reconstruction_risk`: whether the lens creates overlap, texture, perspective, dense labels, or other risks for later layer extraction/vector reconstruction, plus mitigation.
- `transfer_boundary`: what may be borrowed from the style reference and what must not be transferred.
- `consensus_space_priority_map`, `visual_weight_plan`, `must_show_for_each_space`, `redundancy_budget`, and `missing_information_risk` when the paper contribution depends on peer spaces, peer model paths, or peer consensus mechanisms.

## Transfer Boundary

Style references and atlas boards are not target-paper evidence. They may transfer:

- layout skeletons;
- reader path and panel rhythm;
- callout strategy;
- abstraction level;
- density discipline;
- generic icon style;
- arrow grammar and legend strategy;
- foreground/background separability principles.

They must not transfer:

- paper-specific facts, module names, datasets, metrics, claims, examples, formulas, or experimental conclusions from reference figures;
- visual structures that contradict the target paper;
- decorative rendering that hides target-paper mechanisms;
- style choices that make semantic primitives hard to separate.

## Enforcement

S2-SKETCH-EXPLORE must stop and request S1 rerun if any planned sketch lacks the required style-lens fields.

S5-CANDIDATE-IMAGE must stop and request S4 rerun if any planned formal candidate lacks the required style-lens fields or if the selected style lens contradicts the paper foundation, S3 structure direction, or branch choice.

After S5, human decisions are outside this assistant workflow.

## First-Round Style Default And Reminder v3.2.15f

For S1/S2, the first-round rendering default is `formal_publication_schematic` / 正式出版风格, even when S1 varies style lenses for communication strategy. S0 must remind users, outside the copyable S1 prompt block, that this is a surface-style default only. The default can be changed by adding an explicit surface-style sentence to the S1 request before S1 prepares S2 prompt packages, or cancelled so S1 derives the surface from paper needs. The allowed first-round surface-style labels are: 正式出版风格、低保真草图、白板线框、干净扁平极简线稿、正式 schematic 布局草案、轻量蓝图精密稿、轻量科学插画、轻量界面隐喻、轻量等距结构、轻量信息图板、手绘故事板、ACM/IEEE/AAAI 双栏论文 line-art schematic. Any selected surface style must work together with the style lens, layout grammar, reader path, density budget, connector hierarchy, and paper-source constraints.

This reminder is non-blocking. Do not stop S0 or S1 to ask a mandatory surface-style question unless the user explicitly asks to choose style interactively. S1-to-S2 handoff must repeat the available first-round surface-style menu only as non-copyable prose outside the suggested S2 prompt. The S1-to-S2 note must explain that S2 follows the S1 prompt-index, so changing the first-round surface after S1 requires rerunning S1 before S2 rather than editing the S2 image-only prompt.
