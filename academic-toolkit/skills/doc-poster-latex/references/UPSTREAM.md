# UPSTREAM 溯源台账 — doc-poster-latex

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills（技能目录 `skills/latex-posters`）
- Pinned commit: 2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5（2026-11-16 实测上游 main HEAD，v2.72.0 线；原 36d8f13a，2026-08-24/09-09 两代拉取统一）
- License: MIT

## 适配说明

- 2026-09-09 专项治理批次 1a：从 fork https://github.com/FOURTEEN1416/scientific-agent-skills 拉取该技能 references/ assets/ scripts/ 补齐本仓库技能目录（SKILL.md 沿用本仓库既有版本未动）。
- 上游正文中 `research-lookup` 技能与 API 依赖（parallel-cli 等）在本仓库无对应环境，执行时以当前 Agent 的联网检索/网页抓取能力替代，API 调用类脚本不可直接运行。
- 残留断链（上游亦无该资产）：以本技能 ASSET-GAP.md 清单与"根目录平铺"现状为准（登记册无本技能条目；2026-09-28 核对）。


## 同步评估（2026-11-16，36d8f13a→2d2065f v2.72.0，UP-2）

- vendor/forks/scientific-agent-skills 已镜像同步至实测 HEAD。
- ⚠️ 上游 v2.72.0 已移除/重组本技能来源目录 `skills/doc-poster-latex`（新址：latex-posters / pptx-posters）；本仓收编副本为存续快照，后续升级转本地维护为主，如需跟进新上游结构须按收编规程重新评估。

## 重收编落地（2026-11-16，2d2065f 增量改写融入，UP-3）

- assets/ 三份模板.tex、references/ 七份、scripts/ 三份按上游增量补丁融入（15 份与上游旧版全同，应用干净）。references/ai_graphics_for_posters.md 与 poster_content_guide.md 因上游整篇重写（524→117 行收敛）无法增量应用：采纳上游新版（其修正已覆盖本地 2026-09-28 的 texcount CLI 纠偏、Planning assumption 等增量），并在 ai_graphics_for_posters.md 保留本地去工具名适配（"scientific-schematics skill" 改为指向本技能 scripts/ 与手写 TikZ）。脚本契约已随补丁对齐（OpenRouter images 端点、gemini-3.1-flash-image / gemini-3.7-flash、1-2 轮迭代不自动重试、OPENROUTER_API_KEY 环境优先）。
- SKILL.md 保留本仓中文适配文本体系不整篇照搬；择要融入上游增量：AI 生图准确性边界（仅概念图、禁编造数值图表/显微/谱图/结果、不设 AI 占比硬指标）、SVG 先转 PDF、baposter 官方站点失效与存档类 v2.0 依据、generate_schematic 新契约摘要。
- 上游 SKILL.md 的"三模板已本地编译验证（TeX Live 2025/Poppler 26.09）"属上游执行记录，未转述为本仓已完成；"Citing Scientific Agent Skills" 段未收编。
