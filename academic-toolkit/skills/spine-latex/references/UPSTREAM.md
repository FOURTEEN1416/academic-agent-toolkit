# UPSTREAM 溯源台账 — spine（PaperSpine 套件）

- Upstream: https://github.com/WUBING2023/PaperSpine（Claude 适配分发 `dist/claude/skills/paper-spine/`）
- Pinned commit: 1a79bf21c76a73cb31f4310bc42f847a04e91d1a（2026-11-16 实测上游 HEAD，tag v4.0.0；原 1fe46f0，fork FOURTEEN1416/PaperSpine 2026-09-09 拉取）
- License: MIT（2026-11-16 UP-4 落实：上游仓库 LICENSE 原文核验为 MIT License, Copyright (c) 2026 PaperSpine contributors）

## 适配说明

- 本仓库 spine 系 11 个技能为上游单一 paper-spine 技能的**拆分重组**编排；2026-09-09 专项治理批次 2 按各技能 SKILL.md 引用从上游分发目录回填 scripts/references 资产。
- 上游脚本对本仓库为只读工具，编排仍按本仓库各技能 SKILL.md 执行。

## 收编记录

- 2026-09-28：用户裁决允许拉取；自 pin `1fe46f0`（fork FOURTEEN1416/PaperSpine，HEAD 即 pin）回填缺失资产至本技能；上游 LICENSE=MIT 核验通过（sha256 e89308aa6fe435bd…）。部分引用件（humanize-tiers/build-from-materials/paragraph_function_templates/result_narrative_templates）上游 pin 亦无，维持 ASSET-GAP 缺位登记。


## 同步评估（2026-11-16，1fe46f0→1a79bf2 tag v4.0.0，UP-4）

- vendor/forks/PaperSpine 已镜像同步至实测 HEAD（1648 文件更新、9 项上游旧版发布残留清理）；上游 2 个月更新含 v4.0.0 大版本（多语言 README、portable suites/release v6 工作流、INSTALL 文档族等）。
- 本仓 spine 系 11 技能为上游单一 paper-spine 技能的拆分重组编排（脚本/资产只读引用），上游 v4.0.0 技能包结构变化须经逐件 diff 评估后按收编规程重放，本单仅完成 vendor 同步与台账刷新，技能侧重收编待专项。

## 重收编施工记录（2026-11-16，PKG-07 spine 系批）

- references/latex-source-control.md：吸收保护区分级措辞（普通散文编辑保护、受权结构任务可改并验证）、最终编译后逐页/逐图视觉检查（守卫通过≠视觉有效，不可豁免）、Rendered Visual Receipt 清单。
- 套件级 `spine/references/latex.md` 同步吸收模板采用验证、图最终物理尺寸、Word 独立读者面（Pandoc 警告=构建失败、PDF 图栅格化、纯文本回读）、venue 字体优先。
- 未吸收（记入 skipped）：visual_readiness_check.py / word_surface_repair.py / manuscript-format.md 等 v6 资产引用（本仓无对应脚本/文件，相关精神以自包含表述融入）；上游对 `\cite` 硬规则的软化（本仓 latex_guard.py 仍强制，保持一致）。
