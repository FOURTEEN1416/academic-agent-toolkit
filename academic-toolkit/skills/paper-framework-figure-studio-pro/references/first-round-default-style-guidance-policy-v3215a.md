# First-Round Default Style And Override Reminder Policy v3.2.15f

This source-policy update is packaged in this release as `v3.2.15f`.

“First round” means the S1-prepared, S2-generated candidate batch (`C01`-`C04` by default). It does not mean the S5 formal candidate round.

## Default First-Round Surface

The default first-round surface is `formal_publication_schematic` / 正式出版风格.

Unless the user explicitly overrides it in the S1 request before S1 finalizes S2 prompt packages, every required S2 prompt package and S2 image-only handoff must request a clean publication-style academic framework schematic: polished but restrained vector-like layout, crisp module hierarchy, readable labels, precise arrow routing, light scientific color palette, and manuscript-ready structure.

This default changes only the rendering surface. S1 must first plan eight complementary style combinations, then select the four highest-value combinations for the actual S2 candidates. The selected four must vary across layout grammar, reader path, semantic focus, density, detail strategy, visual rhetoric, style lens, and palette strategy. Those are design hypotheses. Even when a surface style is explicitly set, it must be combined with the other candidate-design dimensions and source-grounded constraints; it must not be treated as the whole candidate style. They do not allow paper-unsupported content, raw-data-sharing implications, cluttered dashboards, contradictory style mixes, or decorative polish that weakens semantic readability.

## Non-Blocking User Reminder

At the end of S0-PAPER-FOUNDATION, when showing the S1 next-step prompt, include the full non-copyable reminder text below that the first-round default is a **surface style** only. The reminder must say that this default surface can be changed by adding an explicit surface-style sentence to the S1 request before S1 prepares S2 prompt packages, or cancelled so S1 can set the rendering surface from the paper's actual needs. This reminder must not pause the workflow or ask a mandatory question.

The reminder must also expose `acm_ieee_aaai_line_art_schematic` / ACM/IEEE/AAAI double-column line-art schematic as an optional first-round surface. This is a selectable first-round S2 surface, not only a second-round S5 treatment.

The reminder is not part of the suggested/copyable S1 prompt. It must be displayed as prose outside any fenced prompt block or other copyable prompt section, so optional surface-style text is not accidentally copied into the default next-step prompt.

Use this exact Chinese user-facing S0-to-S1 handoff reminder. Do not summarize, shorten, or omit the option list:

```text
非复制表面风格提示：第一轮 S2 默认表面风格为正式出版风格；这只约束渲染表面，不等同于候选图的叙事、布局或处理方案。若要修改，请在下一轮 S1 请求中另行明确写入表面风格选择或取消默认表面风格；请不要把本说明复制进默认提示词块。可写例如“第一轮采用 ACM/IEEE/AAAI 双栏论文 line-art schematic 表面风格”，也可以写“取消默认表面风格，请 S1 根据论文实际需要自行设置表面风格”。可选表面风格包括：正式出版风格、低保真草图、白板线框、干净扁平极简线稿、正式 schematic 布局草案、轻量蓝图精密稿、轻量科学插画、轻量界面隐喻、轻量等距结构、轻量信息图板、手绘故事板、ACM/IEEE/AAAI 双栏论文 line-art schematic。
```

The S1 suggested prompt must not carry an editable default-surface-style clause. If the user wants an override or wants to cancel the default surface, they add a separate sentence to the S1 request themselves.

For the ACM/IEEE/AAAI first-round option, expose the concrete user-editable phrase in non-copyable style reminders, not in suggested prompt blocks: `第一轮采用 ACM/IEEE/AAAI 双栏论文 line-art schematic 表面风格`.

For cancelling the default first-round surface, expose the concrete user-editable phrase in non-copyable style reminders, not in suggested prompt blocks: `取消默认表面风格，请 S1 根据论文实际需要自行设置表面风格`.

## Allowed First-Round Surface-Style Options

These options are compatible with S2 only when they remain source-grounded and governed by the same paper-semantics, arrow, hierarchy, density, and prompt-audit contracts.

| Option ID | User-facing label | S2 meaning |
|---|---|---|
| `formal_publication_schematic` | 正式出版风格 | Default. Clean publication-style academic framework schematic for first-round comparison; polished surface, but still one candidate direction. |
| `low_fidelity_sketch` | 低保真草图 | Rough exploratory framework sketch, whiteboard/wireframe feel, short labels, compact-balanced layout. |
| `whiteboard_wireframe` | 白板线框 | Very rough boxes, arrows, grouping, and layout structure with minimal surface polish. |
| `clean_flat_minimal_line` | 干净扁平极简线稿 | Cleaner line-art while still exploratory; no excessive final polish. |
| `formal_schematic_layout_study` | 正式 schematic 布局草案 | More ordered schematic grammar for layout testing. |
| `precision_blueprint_light` | 轻量蓝图精密稿 | Grid/port/routing emphasis for high arrow-risk papers; avoid dense blueprint clutter. |
| `scientific_editorial_light` | 轻量科学插画 | Light scientific editorial treatment with separable modules and restrained texture. |
| `interface_metaphor_light` | 轻量界面隐喻 | UI/control-board metaphor only when it clarifies paper mechanisms without adding facts. |
| `isometric_structure_light` | 轻量等距结构 | Mild dimensional structure only when it does not obscure connectors or labels. |
| `infographic_board_light` | 轻量信息图板 | Compact explanation board, with density and caption burden explicitly budgeted. |
| `hand_drawn_storyboard` | 手绘故事板 | Narrative/storyboard option only when S1 records a close story-to-paper bridge. |

| `acm_ieee_aaai_line_art_schematic` | ACM/IEEE/AAAI double-column line-art schematic | Optional publication-line-art first-round surface. Use only when explicitly requested; keep S2 exploratory and preserve layout/narrative diversity across candidates. |

Forbidden as S2 defaults: photorealism, cinematic rendering, glossy marketing poster style, dense dashboard, decorative texture that makes semantic primitives hard to read, or any style that weakens source-grounding.

## Prompt-Index And State Recording

S1 should record the first-round surface-style decision in state and prompt packages when available. It must also record the eight-to-four style-combination selection required by `references/style-combination-selection-and-human-palette-policy-v3215d.md`. Keep the legacy `first_round_style_*` field names for compatibility, but interpret them as surface-style controls:

- `first_round_default_style_id`: `formal_publication_schematic` unless explicitly overridden;
- `first_round_style_options`: the allowed option menu above;
- `first_round_style_user_reminder`: the full non-copyable reminder text with the complete allowed surface-style option list;
- `first_round_style_override_policy`: include `acm_ieee_aaai_line_art_schematic` as an explicit compatible override that can be requested in the S1 prompt after the S0-to-S1 non-copyable reminder;
- `first_round_surface_style_default_cancellation_policy`: allow an explicit S1-request sentence cancelling the default surface so S1 derives the surface from paper needs without treating cancellation as a request for decorative freedom;
- candidate-level `first_round_style_surface` or equivalent field in S2 prompt packages.

If the user overrides the first-round surface style, record it as an explicit user decision and preserve the override in the S2 prompt-index/prompt packages. A first-round surface-style override does not automatically set S5 formal surface style or treatment; S4 must make or confirm formal candidate style/treatment choices using S3 direction and paper needs.

## Stage Placement

- S0 must mention that first-round surface style is adjustable or cancellable, but only as a non-copyable note outside the suggested S1 prompt.
- S1 consumes any explicit first-round surface style override or default-surface cancellation present in the S1 user request, records it, injects any required style block, and then stops before S2 image generation.
- S1-to-S2 handoff must provide the full non-copyable first-round surface-style menu outside the copyable S2 image-only prompt, so users who missed S0 still know the available alternatives. The note must include the currently recorded first-round surface decision, must list all allowed first-round surface-style options, and must explain that changing it after S1 requires rerunning S1 before S2, because S2 follows the S1 prompt-index. Optional surface-style text must not be placed inside the copyable S2 prompt.
- S2 is image-only and must not discuss or renegotiate surface style; it follows the S1 prompt-index. If no explicit override is recorded in S1 artifacts, S2 uses `formal_publication_schematic`.
- S3/S4 may carry forward human-selected visual preferences, but should not treat an S2 surface as a final S5 surface-style or treatment lock unless the user explicitly says so.

## S1-To-S2 Non-Copyable Options Note

When S1 closes and gives the S2 image-only prompt, include this full reminder outside the copyable S2 prompt block. Do not summarize, shorten, or omit the option list:

```text
非复制表面风格提示：第一轮 S2 默认表面风格为正式出版风格，除非 S1 已在 prompt-index 中记录了显式覆盖或取消默认表面风格；S2 只会按该记录生成图片。若想在运行 S2 前修改第一轮表面风格，需要回到 S1 重做 prompt packages，而不是改 S2 生图提示词。可选表面风格包括：正式出版风格、低保真草图、白板线框、干净扁平极简线稿、正式 schematic 布局草案、轻量蓝图精密稿、轻量科学插画、轻量界面隐喻、轻量等距结构、轻量信息图板、手绘故事板、ACM/IEEE/AAAI 双栏论文 line-art schematic。可在重新执行 S1 时另行写入例如“第一轮采用 轻量蓝图精密稿 表面风格”或“取消默认表面风格，请 S1 根据论文实际需要自行设置表面风格”。
```

This reminder is informational and non-blocking. It must not ask a mandatory question, must not self-trigger an S1 rerun, and must not be copied into the S2 image-only prompt.
