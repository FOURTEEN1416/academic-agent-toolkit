# UPSTREAM 溯源台账 — pymoo

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills（技能目录 `skills/pymoo`）
- Pinned commit: 2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5（2026-11-16 实测上游 main HEAD，v2.72.0 线；原 36d8f13a，2026-08-24/09-09 两代拉取统一）
- License: MIT（上游仓库 LICENSE.md + plugin.json 双证；K-Dense Inc.）
- Upstream version: 2.72.0（plugin.json，2026-11-16 重收编时实测；原 2.64.0）
- 收编日期: 2026-10-16（仿真建模赛（CSF）能力补齐批）；2026-11-16 重收编（PKG-04 仿真与强化学习包）

## 适配说明

- 本地化适应性改写：仅**归一化 frontmatter**（description 改写为路由索引口径 ≤120 字符，符合本仓常驻上下文预算纪律；license/metadata 保留）+ 追加 `ACAT-ADAPTED` 溯源标注。
- **正文与 references/scripts 逐字节照搬**（未做内容编辑）。
- 上游 `compatibility` 段声明的 `uv` 环境与 Python 版本要求**在本仓库不适用**：执行前以 `skills/comp-simulation/scripts/sim_env_probe.py` 探测本机实装版本为准；库缺席如实记 `unavailable`，不阻断。
- 上游有网络/凭据类依赖的脚本不适用本仓离线/受控执行面。


## 同步评估（2026-11-16，36d8f13a→2d2065f v2.72.0，UP-2）

- vendor/forks/scientific-agent-skills 已镜像同步至实测 HEAD（2780 文件更新、246 项删除——含上游移除的 vendored docx/pdf/pptx/xlsx）。
- 上游 v2.72.0 本技能目录仍在，正文有更新（本仓技能侧差异 14 处，上游含 SKILL.md 重写与新增 references）。
- 2026-11-16 重收编落地（PKG-04）：SKILL.md 融入 v1.6 增量——pymoo 0.6.2 重审与依赖面（moocore/cma/alive_progress/Deprecated）、结果对象 G/H/CV 与可行性契约（return_least_infeasible、None 结果）、单目标最大化取负口径、MOEA/D 不支持约束、SPEA2/Feasibility-first 表更正、best practices 重写（尺度/符号一致性、callbacks 优于 save_history 深拷贝）、终止子 `f_tol` 工厂名废弃与 DefaultMultiObjectiveTermination 有界用法、Das-Dennis 方向数公式、Pareto 近似非最优性证书、PseudoWeights 语义、有界 demo 免责与 MPLBACKEND=Agg。新增上游参考件 references/lifecycle.md（SKILL.md 已引用）。references 7 件、scripts 5 件取上游新版，按逐字节照搬惯例以 LF 写入；上游文末 Citing 节未收编。
