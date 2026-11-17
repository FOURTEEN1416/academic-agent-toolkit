# UPSTREAM 溯源台账 — spine（PaperSpine 套件）

- Upstream: https://github.com/WUBING2023/PaperSpine（Claude 适配分发 `dist/claude/skills/paper-spine/`）
- Pinned commit: 1a79bf21c76a73cb31f4310bc42f847a04e91d1a（2026-11-16 实测上游 HEAD，tag v4.0.0；原 1fe46f0，fork FOURTEEN1416/PaperSpine 2026-09-09 拉取）
- License: MIT（2026-11-16 UP-4 落实：上游仓库 LICENSE 原文核验为 MIT License, Copyright (c) 2026 PaperSpine contributors）

## 适配说明

- 本仓库 spine 系 11 个技能为上游单一 paper-spine 技能的**拆分重组**编排；2026-09-09 专项治理批次 2 按各技能 SKILL.md 引用从上游分发目录回填 scripts/references 资产。
- 上游脚本对本仓库为只读工具，编排仍按本仓库各技能 SKILL.md 执行。
- 改写融入（2026-09-23，R1）：Integration 段安装指引改为随仓使用口径。

## 收编记录

- 2026-09-28：用户裁决允许拉取；自 pin `1fe46f0`（fork FOURTEEN1416/PaperSpine，HEAD 即 pin）回填缺失资产至本技能；上游 LICENSE=MIT 核验通过（sha256 e89308aa6fe435bd…）。部分引用件（humanize-tiers/build-from-materials/paragraph_function_templates/result_narrative_templates）上游 pin 亦无，维持 ASSET-GAP 缺位登记。


## 同步评估（2026-11-16，1fe46f0→1a79bf2 tag v4.0.0，UP-4）

- vendor/forks/PaperSpine 已镜像同步至实测 HEAD（1648 文件更新、9 项上游旧版发布残留清理）；上游 2 个月更新含 v4.0.0 大版本（多语言 README、portable suites/release v6 工作流、INSTALL 文档族等）。
- 本仓 spine 系 11 技能为上游单一 paper-spine 技能的拆分重组编排（脚本/资产只读引用），上游 v4.0.0 技能包结构变化须经逐件 diff 评估后按收编规程重放，本单仅完成 vendor 同步与台账刷新，技能侧重收编待专项。

## 重收编施工记录（2026-11-16，PKG-07 spine 系批）

- SKILL.md：新增「Boundaries And Honest No-Op」节——吸收上游 Authorial Voice Restoration 定位中的诚实边界（不承诺检测器通过/不伪造 AI 率、模式匹配不强制改写、清晰文本 no-op 是精准性证据、禁多跳翻译回译作最终改写、保留作者含义与术语）。
- 保持本仓 D1–D5 检测维度、tier 指令与 humanize_check.py 闸门（本仓裁决：pipeline 内 tier 驱动 humanize 步骤，与 paper-humanize / anti-ai-detection 分工不变）。
- 未吸收（记入 skipped）：author_voice_profile/author-voice contracts 等 v6 资产链、humanize_tier→author_voice_restoration 的字段更替（本仓 config 与脚本仍以 humanize_tier 为准）。
