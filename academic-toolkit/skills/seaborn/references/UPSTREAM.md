# Seaborn 技能来源记录

- Upstream: https://github.com/FOURTEEN1416/scientific-agent-skills（fork 自 K-Dense-AI/scientific-agent-skills， 科研绘图能力扩展集成）
- Pinned commit: 2d2065f
- Checklist date: 2026-11-16
- Local use: `skills/seaborn/`（SKILL.md 及附带 references/assets/scripts）
- License: MIT（见仓库 LICENSE.md）
- Local adaptation: 改写融入（2026-11-16，PKG-05，上游 SKILL v1.2→v1.5）：保留执行与产出段、交付护栏注（共享 save_fig + academic.mplstyle）、示例出厂色环替换为定版低饱和色板；融入上游 errorbar/units 抽样单元语义、权重与配对设计约束、KDE 边界偏差提示、objects_interface 重构纠错版（221 行）及 function_reference/grids/palettes/plotting/examples 的 0.13.2 复核修正。

## Upgrade rule

上游 fork 更新后，对比 SKILL.md 与附带资产再同步；同步后刷新本文件的 Pinned commit 与 Checklist date。
