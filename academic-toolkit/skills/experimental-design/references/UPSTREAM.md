# UPSTREAM 溯源台账 — experimental-design

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills（技能目录 `skills/experimental-design`）
- Pinned commit: 36d8f13a1e754618794bf42f417884940077b4ae（vendor/forks/scientific-agent-skills 本地快照，2026-08-24 HEAD）
- License: MIT（上游仓库 LICENSE.md + plugin.json 双证；K-Dense Inc.）
- Upstream version: 2.64.0（plugin.json）
- 收编日期: 2026-10-16（仿真建模赛（CSF）能力补齐批）

## 适配说明

- 本地化适应性改写：仅**归一化 frontmatter**（description 改写为路由索引口径 ≤120 字符，符合本仓常驻上下文预算纪律；license/metadata 保留）+ 追加 `ACAT-ADAPTED` 溯源标注。
- **正文与 references/scripts 逐字节照搬**（未做内容编辑）。
- 上游 `compatibility` 段声明的 `uv` 环境与 Python 版本要求**在本仓库不适用**：执行前以 `skills/comp-simulation/scripts/sim_env_probe.py` 探测本机实装版本为准；库缺席如实记 `unavailable`，不阻断。
- 上游有网络/凭据类依赖的脚本不适用本仓离线/受控执行面。
