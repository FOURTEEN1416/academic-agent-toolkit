# ACM/IEEE/AAAI Line-Art Schematic Style Policy v3.2.15f

This policy defines an optional first-round/S2 surface style and second-round/S5 surface-style treatment. It is inactive by default.

## Activation

Activate this surface style for first-round S2 only when the S1 user prompt or a machine-readable S1 surface-style slot explicitly asks for ACM/IEEE/AAAI, ACM, IEEE, AAAI, two-column line-art, or `acm_ieee_aaai_line_art_schematic` surface style. The S0-to-S1 non-copyable reminder may describe the option, but it does not activate the style by itself. Activate this surface style for second-round S5 only when the S4/S5 user prompt, the S3-to-S4 handoff, or a machine-readable S4 surface-style slot explicitly asks for it.

For the second round, S3 and S4 do not have the same responsibility. S3 must expose the non-copyable S3-to-S4 surface-style options reminder so the user can put a surface-style intent into the next S4 request; S3 does not create S5 prompt packages and does not own the second-round surface-style record. S4 owns the formal candidate matrix, S5 prompt packages, style/treatment slots, and any injected surface-style rule. S4-to-S5 must not remind the user again about surface style; after S4, the next public prompt is S5 image-only.

Even when this surface style is active, it is only the rendering layer. It must be used together with the formal candidate's narrative role, layout grammar, semantic emphasis, density budget, connector hierarchy, and source-grounded constraints.

When active, S1 or S4 must record:

```json
{
  "style_id": "acm_ieee_aaai_line_art_schematic",
  "style_label": "ACM/IEEE/AAAI 双栏论文 line-art schematic",
  "style_family": "publication_line_art",
  "stage_scope": "first_round_s2_or_second_round_s5"
}
```

If the user asks for the whole first round or second round to use this surface style, apply the style block to every affected S2 or S5 prompt package. If the user asks for only selected rows, apply it only to those rows and record row-level scope.

## S0-To-S1 Non-Copyable First-Round Reminder

When S0 closes and gives the S1 next-step prompt, include this full reminder outside the copyable S1 prompt block. Do not summarize, shorten, or omit the option list:

```text
非复制表面风格提示：若希望第一轮 S2 草图采用 ACM/IEEE/AAAI 双栏论文 line-art schematic 表面风格，请不要把本说明复制进默认提示词块；请在下一轮 S1 请求中另行明确写入“第一轮采用 ACM/IEEE/AAAI 双栏论文 line-art schematic 表面风格”。也可以写“取消默认表面风格，请 S1 根据论文实际需要自行设置表面风格”。写入后 S1 会把该表面风格规则或取消默认表面风格的决定记录进受影响的 S2 候选 prompt，不改变论文语义、candidate_id、prompt_path 或 target_image_path。
```

This reminder is non-blocking. Do not pause S0 to ask a surface-style question. S1-to-S2 handoff must repeat the full available first-round surface-style menu only as non-copyable prose outside the copyable S2 image-only prompt. That S1-to-S2 note must explain that S2 follows the S1 prompt-index, that changing the first-round surface after S1 requires rerunning S1 before S2, and must not omit the list of available surface-style options.

## S3-To-S4 Reminder

When S3 closes and gives the S4 prompt, include this full reminder outside the copyable S4 prompt block. Do not summarize, shorten, or omit the option list:

```text
可选第二轮表面风格：S5 正式候选默认由 S4 根据论文需要设置表面风格；表面风格只约束渲染层，不改变候选图的论文语义、布局骨架、连线证据和密度预算。若希望指定第二轮表面风格，请在下一轮 S4 请求中另行写入“第二轮采用 <表面风格名> 表面风格”。可选项包括：正式出版风格、干净扁平极简线稿、轻量蓝图精密稿、轻量科学插画、轻量界面隐喻、轻量等距结构、轻量信息图板、ACM/IEEE/AAAI 双栏论文 line-art schematic。也可以写“取消默认表面风格，请 S4 根据论文实际需要自行设置 S5 表面风格”。低保真草图、白板线框、手绘故事板默认只适合第一轮探索；若要用于第二轮，必须在 S4 请求中明确说明它仍需保持 formal candidate 可读性。
```

This reminder is non-blocking. Do not pause S3 to ask a surface-style question. Do not insert the optional surface-style phrase into the suggested S4 prompt itself.

## S4-To-S5 Reminder

There is no S4-to-S5 surface-style reminder. S4 closes with the S5 image-only prompt only; do not add optional surface-style prose beside or inside that prompt.

## Prompt Block To Inject Into S2 Or S5 Image Prompts

When active, inject or apply the following block to each affected S2 or S5 image prompt package:

```text
Style treatment: ACM/IEEE/AAAI double-column paper line-art schematic.
Create a white-background, vector-like line-art schematic suitable for ACM/IEEE/AAAI two-column research papers. Use thin but print-safe strokes, sparse color, minimal icons, and compact labels. Prefer Arial/Helvetica-like sans-serif labeling with consistent small text; keep labels legible at double-column paper scale. Use line style, shape, brightness, grouping, and pattern as redundant encodings so meaning is not carried by color alone. Keep the drawing close to publication line art: simple boxes, arrows, ports, braces, small callouts, and precise paper-grounded connectors. Avoid gradients, drop shadows, poster-like large titles, design-principle panels, decorative photo thumbnails, glossy illustrations, dense dashboards, marketing graphics, and unsupported icons. Preserve all source-grounded semantics, arrow directions, variable-on-edge rules, modular hierarchy, prompt-index IDs, and S1/S4 negative constraints. If used in S2, keep the batch exploratory and preserve the S1-planned narrative/layout diversity; if used in S5, keep the S4-planned formal candidate differences.
```

## Official-Guideline Basis

Use this as a style synthesis, not as a claim that ACM, IEEE, or AAAI mandates one identical visual template.

- IEEE Author Center says vector graphics are preferred when possible and black-and-white line art needs high resolution if non-vector; IEEE accessibility guidance recommends checking grayscale readability and not depending on color alone.
- Nature final-submission guidance asks for sans-serif lettering, preferably Helvetica or Arial, with consistent figure font usage.
- PLOS figure guidance gives practical production defaults for figures, including 8 pt text and 0.2 mm line width in its example workflow.
- Wiley figure guidance treats flowcharts and diagrams as line art and prefers publication-friendly PDF/EPS-style handling.
- AAAI author instructions require high-resolution two-column submissions and readable non-Type-3 fonts; AAAI LaTeX formatting guidance expects illustration labels to remain at least nine-point type.

Reference URLs:

- https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-graphics-for-your-article/
- https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-graphics-for-your-article/resolution-and-size/
- https://www.nature.com/nature/for-authors/final-submission
- https://journals.plos.org/plosone/s/figures
- https://authors.wiley.com/author-resources/Journal-Authors/Prepare/manuscript-preparation-guidelines.html/figure-preparation.html
- https://aaai.org/conference/aaai/aaai-26/submission-instructions/

## Negative Constraints

Do not use this style option to bypass paper evidence. Do not add decorative icons, stock-photo thumbnails, method-unrelated visual metaphors, color-only distinctions, or large explanatory title panels. If this style conflicts with source-grounded readability for the specific paper, S1 or S4 must record the conflict and either narrow the style scope or ask the user for a trade-off before S2/S5.
