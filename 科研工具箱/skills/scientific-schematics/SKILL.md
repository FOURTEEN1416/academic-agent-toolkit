---
name: scientific-schematics
description: Create or refine publication-quality technical diagrams, scientific workflows, architectures, and biological schematics with the native image-generation capability.
category: visualization
allowed-tools: [Read, Write, Edit, generate_image]
---

# Scientific schematics


## Step 0: 多模态 LLM 后端检测（强制，不可跳过）

**本技能是"多模态 LLM 专属技能"：没有图像生成后端就无法工作。开工前必须：**

1. 运行环境检测：`python tools/plotting_env_check.py`（本仓库根/科研工具箱下）；
2. 图像**生成**必须具备图像生成模型后端（如 OpenRouter 的 `OPENROUTER_API_KEY` → Nano Banana Pro / Gemini image 系列；或宿主原生 `generate_image` 后端）；
3. 质量**评审**可用任意多模态视觉模型（免费模型可胜任，如 OpenCode 的 `agnes/agnes-2.5-flash` 视觉审查）；
4. **检测不通过时**：停止执行，向用户明确说明"本技能需要多模态 LLM 图像生成后端"，并给出上方检测器的 `setup_hint` 配置指引。**禁止**用占位图、假图或纯本地绘图冒充 AI 生成结果；
5. 成本纪律：外部 API 调用须经高风险确认并计入 C5 成本指标。

---


Use this skill for technical figures whose scientific structure matters: model
architectures, experimental workflows, study diagrams, biological pathways,
mechanistic illustrations, and conceptual schematics.

## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：图像生成后端与模型名、脚本 generate_schematic.py 参数；外部 API 调用须经高风险确认并计入成本。

## Scope

- Follow the user's requested figure count, subject, and document context.
- When refining an existing paper, inspect the manuscript and current figure
  first. Preserve the paper's claims and unaffected figures.
- Do not expand a figure-editing request into literature review, citation audit,
  peer review, or new experiments unless the user asks for that work.
- For plots derived from numeric data, use the local analysis/plotting tool that
  produced the data. Do not use an image model to invent measurements.

## Native workflow

1. Read the target manuscript, caption, or source figure when one exists.
2. Identify the figure's scientific claim, required components, labels, reading
   order, and output dimensions.
3. Call `generate_image` directly. It resolves connected OpenRouter BYOK or a
   funded OpenScience managed route without exposing credentials to shell code.
4. Inspect the generated file. If a concrete defect remains, make one focused
   edit with `generate_image` using the existing image as the reference.
5. Save the accepted figure in the active session or project workspace and
   update the manuscript only when requested.

Do not invoke bundled Python or CLI image wrappers inside OpenScience. Do not
ask the user to paste a key into chat. If `generate_image` reports that no route
is connected, explain the connection requirement once and offer a deterministic
local diagram only with the user's agreement.

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

Before finishing, confirm that labels are legible, arrows and causal direction
are unambiguous, the caption matches the image, and the figure does not imply
evidence stronger than the underlying study. Report any unresolved visual or
scientific uncertainty plainly.
