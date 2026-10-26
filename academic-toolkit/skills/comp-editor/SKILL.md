---
name: comp-editor
description: Use when a mathematical modeling competition draft needs controlled edits in response to documented reviewer findings and nine-dimension score losses.
---

# Competition Editor

## Inputs

Read `PAPER_SCORING.json` (the nine-dimension scoring detail produced by the paper-writing step `comp-paper-zh`, step 8 in `comp_cumcm`: each dimension's `score` with its body/figure/table location, plus `fatal_dimensions` and the resulting loss list), `COMP_REVIEW_VERDICT.json`, `VISUAL_REVIEW_VERDICT.json`, the associated markdown reports, the current paper sources, captions, and the canonical result ledger. Treat a missing report or invalid verdict as a blocking issue, not an invitation to infer reviewer intent. `PAPER_SCORING.json` is a conditional input keyed by the workflow template's explicit `paper_scoring` declaration: when the template declares `paper_scoring: true` (its `comp-paper-zh` step lists `PAPER_SCORING.json` in `output_files`), a missing or unparseable scoring file is blocking; when it declares `paper_scoring: false` — or the workflow predates the scoring artifact, or uses `comp-paper-en` — record the absence in `EDITOR_CHANGELOG.md` and work from the verdict findings only, never inventing scores. **No-verdict fallback:** all 23 `comp_*` chains now declare a `comp-review` step (the 2026-10-26 closure batch added `comp_apmcm`/`comp_stats`), so a missing `COMP_REVIEW_VERDICT.json` producer only arises for workflows that predate the `review_inputs` declaration or run outside the `comp_*` family. In that case record the precondition in `EDITOR_CHANGELOG.md` and run the edit pass from the current paper plus the `RESULTS.md` self-audit instead; do not treat an artifact the chain cannot produce as a blocking input.

## Execution

1. Build two worklists: (a) unresolved finding IDs and their requested fixes; (b) loss dimensions from `PAPER_SCORING.json` — only when the template declares `paper_scoring: true` and the file is present. A dimension enters worklist (b) when it appears in `fatal_dimensions` or scores below the 5-point signal of the scoring framework. Prioritize `fatal_dimensions` and dimensions at or below the 3-point signal; a 4-point dimension gets only evidence-located small fixes, not restructuring.
2. For every loss dimension, choose the edit action from the mapping table below. Every edit must cite either a finding ID or a dimension name plus its scoring evidence location.
3. Modify prose, captions, layout, references, or declared delivery materials only for those IDs and dimensions.
4. Do not alter data, model outputs, equations, or headline metrics without a new computation, updated result ledger, and fresh execution evidence from the responsible step.
5. Preserve unresolved fatal findings in the changelog and route them back to modeling, code, or paper writing instead of hiding them through wording changes.
6. Re-run the narrow validation relevant to every changed file, then return the workspace to the final reviewer.
7. When rewording prose, apply the `anti-defensive-writing` skill's removal taxonomy: strip unnecessary hedges, disclaimers, apology-like framing, and over-explanations while preserving methodological limits, accuracy qualifiers, and required AI-use statements.

## 九维失分 → 改稿动作

维度名、0-5 分锚点与权重以 `academic-toolkit/skills/math-modeling-contest-route-selection/references/paper-scoring-framework.md` 为唯一真源；本表只定义改稿动作。

| 失分维度 | 优先改哪类段落 | 补什么内容 | 边界 / 回流 |
|---|---|---|---|
| `deliverable_alignment` | 问题重述、任务分解、每问结果小节、结论 | 补“子问题 → 交付物 → 答案位置”对照表；逐问写清求解对象、口径、单位与最终答案；删与题目要求无关的铺陈 | 只能重述既有结果；缺结果回流对应求解步 |
| `assumption_quality` | 假设章节、模型建立开头 | 删后文未使用的泛化假设；每条假设补必要性、可检验方式，并引用已有的灵敏度/极限情形检验 | 新增检验须由建模或代码步产出，编辑步不得伪造 |
| `model_fit_and_originality` | 模型选择、模型建立、基线对比段 | 补问题特定变量/约束/机制为何贴合本题；补基线、被拒方案与判定试验；把“用了某方法”改写成“该方法解决了本题的哪个困难” | 对比数据或新模型回流建模步 |
| `solution_correctness` | 公式、算法伪代码、参数表、求解器设置、结果表 | 统一符号与代码变量；补初值、参数、停止准则、随机种子与复现命令；核对公式与结果表数值一致 | 数值改动必须重新计算、更新结果账本并附执行证据 |
| `validation_strength` | 验证章节、结果与讨论 | 补基线对比、灵敏度、消融、外部校验或极限情形，并写清结论翻转条件；把“结果合理”改成可核验证据 | 新验证必须由建模或代码步产出；编辑步只组织既有证据 |
| `decision_value` | 结果解释、建议、结论 | 把指标转成排序、阈值、策略或方案选择；每条建议绑定具体结果与适用条件 | 不得超出模型覆盖范围外推 |
| `paper_expression` | 摘要、图表、算法框、章节结构 | 建立“主张 → 图/表”对应；改图注、表头与正文指引；删装饰性图与重复段落；摘要补 baseline、main upgrade、validation、decision | 重绘或换图回流 `paper-figure` 或视觉审查步 |
| `engineering_feasibility` | 实现步骤、复杂度与参数说明、复现附录 | 补运行环境、数据规模、耗时/内存、失败回退与重跑方式 | 需实测的资源数据回流代码步 |
| `differentiation` | 创新点、模型改进、方法选择 | 删通用方法堆叠；补问题特定设计、被拒替代方案与判定试验、基线到升级的对比 | 不得把“组合多个通用方法”写成创新；新对比回流建模或代码步 |

## Outputs

Write `EDITOR_CHANGELOG.md`. For every reviewed finding ID and every loss dimension, record the disposition (`fixed`, `unresolved`, or `not_applicable`), changed files, a concise description of the edit, the validation command or manual check, and the reason for any unresolved item. For a loss dimension also record its original score, the scoring evidence location, the mapped edit action, and whether the loss is closed or must return to modeling, code, figure, or paper writing. Do not claim the paper is delivery-ready; only `comp-final-review` and `comp-final-audit` may make that decision.

以当前 `StepAction.output_files` 与 `required_checks` 为完整验收合同，不只交变更日志。新建的 `comp_cumcm` / `comp_huawei` 工作流会继承前置写作、编译、一致性步骤的输出与检查：修改论文后，重新执行受影响的一致性检查与编译，提交当前论文源文件、PDF、日志和一致性报告；无修改时也须验收当前版本，不能伪造一次重新编译。执行清单覆盖本步完整输出集合，保留真实输入、命令、后端与依赖。旧工作流使用创建时保存的合同，不静默迁移。继承编译合同的编辑步骤还会重新检查当前 PDF 页数，不能沿用修改前的页数通过记录。

编辑完成不等于获准交付。终审预审 `eligible` 不是 `ready`；最终完成或人类批准后，以当前 `DELIVERY_REPORT.json` 为准。报告发布失败时保留 `pending`，通过 `next` 或显式指定工作区、数据库和工作流的 `final-audit` 恢复，不能重写已验收的预审报告。

## 退出判据（Verification）

本步完成前逐项自检（不达标即视为未完成）：

- [ ] 每条修改可追溯（改了什么、依据哪条意见或哪个失分维度）
- [ ] 只改被指出的问题，不顺手改结构
- [ ] 模板声明 `paper_scoring: true` 时，`PAPER_SCORING.json` 的每个失分维度都已处置：改稿闭环，或写明需回流的步骤与理由；声明 `false` 时已在 `EDITOR_CHANGELOG.md` 记明缺件理由并按既判发现处置
- [ ] 失分定位（段落/图/表）与改动一一对应，未用措辞掩盖需重算的失分
- [ ] 改动后与正文数值/结论保持一致
- [ ] 不引入新的事实性断言

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "顺手优化一下表达" | 编辑步的职责是修订而非重构；越界改动会破坏已验证的一致性。 |
| "改完不用记" | 无变更记录即无法复核；变更清单是本步产物。 |
| "评分只是参考，改完 finding 就行" | 成文步的评分是显式产物；不处置失分维度，评分空转，终审会再次扣在同一处。 |
| "语气改强一点更有力" | 删除 hedging 要有依据，不能变成过度断言。 |

> 本段与 `skills/_utils/anti_rationalization.md`（全局版）配套：本表是本步专属，
> 全局版覆盖跨步骤通用借口。新增借口时优先落到本表（更贴岗位），能泛化再上升。
