---
name: scientific-schematics
description: "Create or refine publication-quality technical diagrams: method/architecture overviews, pipelines, CONSORT/PRISMA-style flows, experimental workflows, biological pathways, conceptual schematics. For structure-not-data figures; measured-number plots use plotting skills; never hand-drawn TikZ/SVG."
category: visualization
allowed-tools: [Read, Write, Edit, generate_image]
license: MIT
version: 2.0.0
metadata:
    origin: K-Dense-AI/scientific-agent-skills (skills/scientific-schematics, MIT)
    adapted-by: Synthetic Sciences
    skill-author: K-Dense Inc.
---

# Scientific schematics


## Step 0: 多模态 LLM 后端检测（强制，不可跳过）

**本技能是"多模态 LLM 专属技能"：没有图像生成后端就无法工作。开工前必须：**

1. 运行环境检测：`python tools/plotting_env_check.py`（本仓库根/academic-toolkit下）；
2. 图像**生成**必须具备图像生成模型后端（如 OpenRouter 的 `OPENROUTER_API_KEY` → 图像生成模型系列；或执行环境原生 `generate_image` 工具后端）——文首提到的具体型号是上游原文示例，实际后端以 env/比赛时配置为准，仓库不预设；
3. 质量**评审**由驱动方独立窗口的视觉能力 LLM 执行（independent-window/visual-capable，与产图窗口隔离，无需任何 API key）；
4. **检测不通过时**：停止执行，向用户明确说明"本技能需要多模态 LLM 图像生成后端"，并给出上方检测器的 `setup_hint` 配置指引。**禁止**用占位图、假图或纯本地绘图冒充 AI 生成结果；
5. 成本纪律：外部 API 调用须经高风险确认并计入 C5 成本指标。

---


A methodology diagram carries the paper's central idea in one glance — and it is
the figure most often faked: outdated palettes, boxes that say nothing, arrows
that go the wrong way, components the text never mentions. Use this skill for
technical figures whose scientific structure matters, and treat every figure as
a loop: describe it precisely, render it under publication standards, score it
against a rubric, and re-render once from the critique.

## 执行与产出

使用当前执行会话完成本步工作；产物路径按当前步骤合同。程序采集真实操作、输入输出、版本与运行清单，模型只负责实质成果和领域质量。

建议额外记录：图像生成后端与模型名、脚本 generate_schematic.py 参数；外部 API 调用须经高风险确认并计入成本。

## Scope

- Follow the user's requested figure count, subject, and document context.
- When refining an existing paper, inspect the manuscript and current figure
  first. Preserve the paper's claims and unaffected figures.
- Do not expand a figure-editing request into literature review, citation audit,
  peer review, or new experiments unless the user asks for that work.
- For plots derived from numeric data, use the analysis/plotting skill that
  produced the data. Do not use an image model to invent measurements.

## The medium

- `generate_image` is the medium for every diagram in this skill. You supply the
  content — components, connections, labels, emphasis, reading direction — and
  the connected route applies the publication framing: white background, one
  sans-serif face, restrained colorblind-safe palette, verbatim labels, no
  invented parts, no figure numbers or captions baked into the image.
- Iterate at draft resolution and render only the accepted figure at print
  resolution. Set the aspect ratio from the page slot (16:9 or 21:9 for a
  full-width overview, 4:3 or 1:1 for a column). Pass reference images when the
  paper's earlier figures or a cited diagram set the style.
- Do not hand-draw a schematic as TikZ, SVG, Graphviz, Mermaid, or matplotlib
  shapes, and do not offer that as a fallback: language models draw these badly
  and the result reads as an unfinished figure. Exact labels are handled by
  giving the model the exact labels and checking them, not by switching medium.
- Never generate plots of numbers with an image model (hallucinated values,
  repeated elements). Route data plots to the plotting skills (matplotlib,
  seaborn, plotly, scientific-visualization).
- Credential discipline: generate through the connected `generate_image` route
  or an environment-configured API key. Never ask the user to paste a key into
  chat, and never write credentials into shell code or script arguments. If no
  route is connected, say so once and stop (Step 0 above).
- 具体图像模型与后端以 Step 0 检测结果和当前环境配置为准；文中出现的型号名均为示例，不预设。

## Workflow

Copy this checklist and work through it:

- [ ] 1. Read the source and choose the document type.
- [ ] 2. Write the description: type, components, flow, labels, emphasis.
- [ ] 3. Render a draft with `generate_image` (`purpose: "schematic"`).
- [ ] 4. Score the render on the rubric; stop if it meets the threshold.
- [ ] 5. Otherwise re-render once from the critique; keep the better of the two.
- [ ] 6. Render the accepted description at print resolution, trim the margins,
      save, write the caption, and report open issues.

**Step 1 — Read the source.** The method section, the caption slot, and any
existing figure. Identify the claim the figure must make, every component the
text names, the relationships and their direction, and what is input, learned,
frozen, or compared. Note the document type: it sets the bar in Step 4. A figure
that shows a component the text never mentions is wrong even if it is pretty.

**Step 2 — Write the description.** The model draws what it is told and nothing
it can infer, so the description is a specification, not a mood. Name, in this
order:

- **Type**: flowchart, architecture diagram, pipeline, pathway, circuit, block
  diagram.
- **Components**: every element with its exact label as it appears in the text,
  and counts where they matter (`Screened (n = 500)`).
- **Flow and direction**: left-to-right or top-to-bottom, and each connection as
  `A -> B (meaning)`; name the labelled arrows (`RAF -> MEK, labelled
  "phosphorylation"`).
- **Emphasis**: the contribution in a single accent colour; standard parts in
  grey; dashed borders for frozen or optional parts.
- **Style constraints beyond the defaults**: panel letters, a legend, a scale
  bar, the reference figures' palette.

More than about twelve labelled elements needs a second figure or a zoomed
inset, not smaller text. Good and bad descriptions with worked examples are in
[references/review-loop.md](references/review-loop.md); the standards a figure
is judged against are in
[references/best-practices.md](references/best-practices.md) and
[references/style-guide.md](references/style-guide.md).

**Step 3 — Render.** Call `generate_image` with the description as the prompt,
`purpose: "schematic"`, the chosen aspect ratio, draft resolution, and any
reference images. Do not restate the publication framing — the route adds it.
Do not ask for a title, caption, or figure number.

**Step 4 — Score it.** Open the PNG and score it yourself on the rubric, 0–2
points each:

| Criterion | 2 points means |
| --- | --- |
| Scientific accuracy | every named component present and labelled exactly, every connection present and in the right direction, nothing invented |
| Clarity and readability | the claim is legible at a glance, one visual hierarchy, no ambiguous element |
| Label quality | every element labelled, no misspelling, sizes consistent and readable at column width |
| Layout and composition | one reading direction, balanced whitespace, nothing overlapping or clipped |
| Professional appearance | flat, crisp, white background, restrained colorblind-safe palette, no decoration |

The threshold depends on where the figure goes: **journal 8.5**, conference,
thesis, or grant **8.0**, preprint or report **7.5**, poster **7.0**, slides
**6.5**. Write the score and the specific issues into the session record. A
misspelled label or a wrong arrow is a failure regardless of the total.

**Step 5 — Refine once.** If the score is below the threshold, re-render from
the same description with the issues appended as constraints ("the arrow from
Encoder to Decoder is reversed; remove the third block labelled 'Model'; the
label 'Randomised' is misspelled"), or pass the failed render back with an edit
intent when the layout is right and only details are wrong. Score again and keep
the better of the two renders. Two renders at most: if connectivity still fails,
simplify the description (fewer components, one panel, a stated reading order)
and render that. A correct simple diagram beats a wrong detailed one.

**Step 6 — Finalize.** Render the accepted description at print resolution into
the working folder (`figs/<name>.png` beside a paper), then trim the uniform
background margin the model painted around the content:
`python scripts/trim_margins.py figs/<name>.png`（原位裁边，3% pad；`--out` 出副本）.
Use the trimmed file's real aspect ratio when sizing it in the manuscript. Write
the caption from the claim (bold phrase, then what the arrows and colours mean,
every abbreviation defined), reference it in the text before it appears, and
report anything the image could not do: a label the model kept misspelling, a
component simplified, a panel dropped. Record the description that produced the
accepted render so the figure can be regenerated.

One figure is faster done in the current session than delegated: a worker starts
without your context and re-reads the source. For two or more figures, hand each
background worker the checklist above plus the component list, the document type
and its threshold, and the output path, and ask it back for the score, the file,
and what it changed.

## Refining an existing diagram

For a human-drawn figure that needs polish, keep the content and change only the
style: pass the original as the reference image, describe the same components
and connections with the new palette, typography, and spacing, and score it with
the same rubric. A polish that adds or removes a box is a failure.

## Prompt contract

Include:

- figure purpose and target audience;
- exact components and relationships;
- reading direction and visual hierarchy;
- every required label, symbol, legend, and panel marker;
- restrained, colorblind-safe styling and a clean background;
- aspect ratio and space for the intended caption or page layout;
- instructions to avoid decorative, unsupported, or fabricated scientific
  details.

Example:

```json
{
  "prompt": "Conference-paper schematic of a protein-language-model analysis. Left-to-right flow: aligned protein sequences, frozen encoder, sparse feature extraction, mutation intervention, and held-out functional validation. Label every stage and distinguish observed data from hypotheses. Clean white background, restrained colorblind-safe palette, readable typography, no decorative elements.",
  "output_path": "figures/method_overview.png",
  "model": "google/gemini-3-pro-image",
  "aspect_ratio": "16:9"
}
```

## Acceptance check

Before finishing, confirm the render met the document-type threshold in Step 4,
that labels are legible, arrows and causal direction are unambiguous, the caption
matches the image, and the figure does not imply evidence stronger than the
underlying study. An unscored figure counts as unscored, not as passed. Report
any unresolved visual or scientific uncertainty plainly.

## References

- [references/best-practices.md](references/best-practices.md) — publication
  standards, accessibility, and journal requirements (the judging criteria).
- [references/style-guide.md](references/style-guide.md) — composition, colour,
  typography, shape vocabulary, and arrow constraints for methodology diagrams.
- [references/review-loop.md](references/review-loop.md) — the
  generate–review–refine loop, the review log, prompt-engineering tips, and
  four worked examples.
- `scripts/generate_schematic.py` / `scripts/generate_schematic_ai.py` — CLI and
  Python fallback implementing the same loop over an OpenRouter-compatible image
  route; `scripts/trim_margins.py` — post-render margin trim.
