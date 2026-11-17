# Matplotlib 技能来源记录

- Upstream: https://github.com/FOURTEEN1416/scientific-agent-skills（fork 自 K-Dense-AI/scientific-agent-skills， 科研绘图能力扩展集成）
- Pinned commit: 2d2065f
- Checklist date: 2026-11-16
- Local use: `skills/matplotlib/`（SKILL.md 及附带 references/assets/scripts）
- License: MIT（见仓库 LICENSE.md）
- Local adaptation: 改写融入（2026-11-16，PKG-05，上游 SKILL v1.1→v1.4）：保留执行与产出段、academic.mplstyle 产图基线划界、savefig bbox 交付护栏（tight 仅预览）、出厂定性色环禁用、CJK 字体链与基线字号；融入上游 3.11.2 版本口径、3.11 API 迁移提示、后端说明、Scientific Checks 段、colormap 归一化要点、布局引擎不混用、脚本用法（--no-show/--output）与 styling 的共享色标/缺失值段。

## Upgrade rule

上游 fork 更新后，对比 SKILL.md 与附带资产再同步；同步后刷新本文件的 Pinned commit 与 Checklist date。
