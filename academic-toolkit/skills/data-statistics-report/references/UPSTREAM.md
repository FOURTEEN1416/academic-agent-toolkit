# UPSTREAM 溯源台账 — data-statistics-report

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills（技能目录 `skills/statistical-analysis`）
- Pinned commit: 2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5（2026-11-16 实测上游 main HEAD，v2.72.0 线；原 36d8f13a，2026-08-24/09-09 两代拉取统一）
- License: MIT

## 适配说明

- 2026-09-09 专项治理批次 1a：从 fork https://github.com/FOURTEEN1416/scientific-agent-skills 拉取该技能 references/ assets/ scripts/ 补齐本仓库技能目录（SKILL.md 沿用本仓库既有版本未动）。
- 上游正文中 `research-lookup` 技能与 API 依赖（parallel-cli 等）在本仓库无对应环境，执行时以当前 Agent 的联网检索/网页抓取能力替代，API 调用类脚本不可直接运行。
- 残留断链（上游亦无该资产）：以本技能 ASSET-GAP.md 清单与"根目录平铺"现状为准（登记册无本技能条目；2026-09-28 核对）。


## 同步评估（2026-11-16，36d8f13a→2d2065f v2.72.0，UP-2）

- vendor/forks/scientific-agent-skills 已镜像同步至实测 HEAD。
- ⚠️ 上游 v2.72.0 已移除/重组本技能来源目录 `skills/data-statistics-report`（新址：statistical-analysis / statistical-power）；本仓收编副本为存续快照，后续升级转本地维护为主，如需跟进新上游结构须按收编规程重新评估。

## 重收编落地（2026-11-16，2d2065f 增量改写融入，UP-3）

- references/ 五份与 scripts/assumption_checks.py 按上游增量补丁融入（路径映射 data-statistics-report→statistical-analysis，应用干净；`python -I -m py_compile` 校验通过）。assumption_checks.py 为上游整体重写版：分组输出改 `outliers_per_group`，`is_normal`/`is_homogeneous` 降级为"未拒绝"legacy 别名，>5000 观测不返回二元 Shapiro 判定，拒绝 inf/退化样本/缺失组标签。
- SKILL.md 保留本仓文本体系，融入上游增量：安装段改专用环境 pin 口径（Pingouin 0.7.0 / SciPy 1.18.1 / statsmodels 0.15.0 / PyMC 6.3.2 / ArviZ 1.3.0，Python 3.12+，Windows 用 Scripts/python.exe）；兼容性注记补 Pingouin 0.7 行为修复、`ttest` 绝对值 Cohen's d 与 observed power 警示、`correction='auto'` 按样本量不按方差证据、PyMC 6 DataTree 与 ArviZ 1 `ci_prob`；t 检验示例改预指定 `correction=True` + 显式带符号 d + APA 尾部 p 表述；ANOVA 示例补 Tukey（Hedges' g）与 Welch+Games-Howell 备选；贝叶斯示例补 seed/chains/cores 与收敛诊断告诫（R-hat/ESS/MCSE/divergences/后验预测）；假设 violated 处置删除"n>30 万能"表述并按上游语义改写；效应量-vs-p 值表述对齐"与零模型不相容"口径。
- 上游新增 "Citing Scientific Agent Skills" 段属上游自我引用话术，未收编。
