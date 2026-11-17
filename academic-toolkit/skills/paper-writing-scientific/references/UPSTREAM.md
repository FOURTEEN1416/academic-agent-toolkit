# UPSTREAM 溯源台账 — paper-writing-scientific（混合上游）

- Upstream: 三个来源混合
- Pinned commit: 36d8f13a1e754618794bf42f417884940077b4ae（scientific-agent-skills）/ 9820740d252800ecf0b8fc066ffb5bf9659f4a51（claude-scientific-writer .claude 副本；原 0c7260603be3de4dd5161565ab92e85b31c45eb5）/ bd4e415c1dcaf6df4ca701f8f8492a97e4b49921（nature-skills）
- License: MIT（K-Dense 系）

## 资产来源明细（2026-09-09 专项治理批次 1b）

| 资产 | 来源 |
|---|---|
| references/citation_styles.md, figures_tables.md, imrad_structure.md, reporting_guidelines.md | K-Dense-AI/scientific-agent-skills `skills/scientific-writing/references/` |
| references/writing_principles.md | K-Dense-AI/claude-scientific-writer `.claude/skills/scientific-writing/references/`（安装态副本，根 skills/ 无此文件） |
| SKILL.md 本体 | 本仓库既有版本（改编自 nature-skills nature-writing 系），未改动 |
| references/editor-first-impression.md | 上游全体系无此资产，SKILL.md 已加 ACAT-GOVERNANCE 内联标记，登记册诚实存量保留 |
- 改写融入（2026-09-23/24，R1）：SKILL.md 图像生成 helper 段改写为工具中性 prompt 模板，死路径命令移除。
- 同步复核（2026-11-16，PKG-06 重收编批）：上游 claude-scientific-writer 0c726060→9820740（v2.23.0）区间内，本技能引用的 `references/writing_principles.md` 对应上游 `.claude/skills/scientific-writing/references/writing_principles.md` **零变更**（已逐字比对一致，仅行尾差异）；上游 scientific-writing 模块唯一变化是 SKILL.md 版本号与尾部新增 "Citing Scientific Agent Skills" 段，均不影响本技能引用件。pin 已更新，无需内容合并。
