# UPSTREAM 溯源台账 — sympy

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills（技能目录 `skills/sympy`）
- Pinned commit: 2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5（2026-11-16 实测上游 main HEAD，v2.72.0 线；原 36d8f13a，2026-08-24/09-09 两代拉取统一）
- License: MIT

## 适配说明

- 2026-09-09 专项治理批次 1a：从 fork https://github.com/FOURTEEN1416/scientific-agent-skills 拉取该技能 references/ assets/ scripts/ 补齐本仓库技能目录（SKILL.md 沿用本仓库既有版本未动）。
- 上游正文中 `research-lookup` 技能与 API 依赖（parallel-cli 等）在本仓库无对应环境，执行时以驱动 Agent 的 web_search/web_fetch 能力替代，API 调用类脚本不可直接运行。
- 残留断链（上游亦无该资产）：以本技能 ASSET-GAP.md 清单与"根目录平铺"现状为准（登记册无本技能条目；2026-09-28 核对）。


## 同步评估（2026-11-16，36d8f13a→2d2065f v2.72.0，UP-2）

- vendor/forks/scientific-agent-skills 已镜像同步至实测 HEAD（2780 文件更新、246 项删除——含上游移除的 vendored docx/pdf/pptx/xlsx）。
- 上游 v2.72.0 本技能目录仍在，正文有更新（本仓技能侧差异 8 处，上游含 SKILL.md 重写与新增 references）；技能侧重收编待专项按改写融入规程执行（本仓含 ACAT-ADAPTED 适配层与归一化 frontmatter，不盲目覆盖）。

## 重收编落地（2026-11-16，2d2065f 增量改写融入，UP-3）

- SKILL.md：SymPy 1.14.0 收敛与 mpmath 1.3.0 兼容说明（`>=1.14` 改为 pin `==1.14.0`）；求解域声明（`solveset` 默认复数域、`ConditionSet` ≠ `EmptySet`、`nsolve` 局部根）；新增"保持数学含义与输入信任"一节（假设须有依据、`==` 是结构比较、`parse_expr`/字符串 `sympify`/`lambdify` 可执行代码且非沙箱）；`fsolve` 改 `full_output=True` 校验收敛；纠偏 `simplify(force=True)` 误导性建议；evalf 精度不可回补说明；Quick Reference 与示例补 `oo` 导入、`expr.evalf()` 方法口径。上游 "Citing Scientific Agent Skills" 段未收编。
- references/advanced-topics.md、code-generation-printing.md、core-capabilities.md、core_capabilities.md：按上游增量补丁融入（含 `is_primitive_root` 归位、`Permutation(0,1,2,size=4)`、`truth_table` 可迭代化、`powerset()`、`roots()` 局部性说明、统计有理数化与独立性提醒、`gamma(Rational(1,2))`、codegen 双产物落盘、解析信任边界重写、`parse_latex(strict=True)` 与 ANTLR 4.11 运行时、mpmath 精度与 `mp.workdps` 等）。
- references/matrices-linear-algebra.md、physics-mechanics.md：本地 2026-09-28 适配稿已领先上游旧版，按"本仓裁决成果不回退"原则保留本地修正（如 `NonInvertibleMatrixError` 探测、`inertia()` 工厂、`joint_axis`、sho1d、`rewrite(StateSpace)`、梁/桁架/缆索反力 API），在其上补入上游增量：逆矩阵符号参数 `det().is_zero` 三值语义注记、`condition_number()` 谱条件数、`mgamma` 显式狄拉克表示、单位约定注意事项改写；上游 review.md（自测记录）未收编。
