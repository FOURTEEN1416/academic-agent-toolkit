---
name: comp-review
description: "数学建模竞赛逻辑对抗复核：编程实现后、论文撰写前，用独立视角挑方向反/重复计量/外推过硬/漏变量/跨问矛盾等硬错。触发词：逻辑复核、对抗审查、模型审查。Use between comp-code and comp-paper。"
argument-hint: [problem-context]
allowed-tools: Bash(*), Read, Grep, Glob, Agent
---

# 竞赛·逻辑对抗复核（独立视角，专挑自查盲区）

**为什么需要这一步**：建模/编程用的是同一个"心智模型"，如果它在建模阶段就把某个方向想反了（如把上界当下界）、或把某项算了两次，**自查时用的还是那个反的脑子，永远看不见**。这一步换一个独立视角，只干一件事——挑七类"数值合法但逻辑错、或得分点缺证据"的硬伤。

## 范围与独立性

本步由引擎分派，不能因为快速模式写占位报告或宣称通过。确定性检查不能替代独立语义审查。没有独立上下文时如实阻塞或报告降级，不能伪造会话。

按当前步骤的 `review_scope` 选择业务输入：竞赛审模型与代码；deep_research审来源、综合论证与边界；grant_proposal审科学问题、方法、可行性、预算依据与申请书；paper_submission审稿件、逐条回复和投稿合同；scientific_plotting审图表的数据语义。非竞赛范围不要求不存在的竞赛题面/建模文件。

## 输入（只读摘要，禁整读大 JSON）

- `PROBLEM_ANALYSIS.md`（题面/逐句表/硬约束）、`DATA_FACTS.json`（数据事实台账）
- `MODELING_REPORT.md`（假设/`LOGIC_CONTRACT_MACHINE`/`CROSS_PROBLEM_LEDGER`）
- `RESULTS.md` + `AUDIT_REPORT.md`（前面各闸的结论）
- `figures/*_results.json` 用 `_utils` 下的 summarize 或 `Grep`/`Read` 局部看，**⛔ 禁 `cat` 整包大 JSON**（吃光 context）

## Step 1: 先看确定性闸的既有结论（不重复劳动）

```bash
# logic_audit / cross_problem_check 已在 comp-code 阶段跑过，先复用它们的裁定作锚点
[ -f AUDIT_REPORT.md ] && grep -nE "外推|特征完整性|重复计量|跨问|矛盾|❌|⚠" AUDIT_REPORT.md | head -30
```

## Step 2: 逐条对撞七类缺口（核心，用证据说话）

对每一类，找**具体代码行/具体数值**当证据，不泛泛而谈：

1. **方向/界反没反**：核对 `LOGIC_CONTRACT_MACHINE.bounds` 声明的上/下界与代码实现是否一致。凡有删失/封顶/反解，代入观测值验证不等号方向。（这是确定性闸抓不到、最需要独立视角的一类）
2. **重复计量**：任何"总量=A+B"，查 A 的拟合/标定是否已吸收 B（如截距用含某分项的总量拟合、又显式加该分项）。
3. **外推口吻过硬**：预测点落在 `DATA_FACTS` 观测区间外的，正文是否用了确定性口吻当"数据结论"（应标"情景模拟、需现场标定"）。
4. **漏真实变量**：`DATA_FACTS` 里 `role=observed` 的关键变量，是否都进了模型；被当"不重要"丢掉的要质疑。
5. **跨问矛盾**：某问算出的关键结论（如峰值/边界）是否与另一问的优化约束/结论冲突。
6. **任务理解 vs 题目原文（⛔ 最该由你独立视角兜的一类）**：拿 `PROBLEM_ANALYSIS.md` 的**关键概念对齐表**和 `MODELING_REPORT.md` 的**目标/约束原文溯源**，逐条核对——建的目标函数/约束/关键量，和题目**原句**要的是不是同一件事？重点抓：求 A 做成了求 B（如覆盖宽度→面积）、最优化方向反（min↔max）、约束理解反、关键量物理含义错、漏做某个明确要求。⛔ **这是"赛题读歪"唯一的独立防线**——下游所有确定性闸都只核"是否忠于建模者的理解"，核不了"理解本身对不对"，只有你带着题目原文重看才可能发现。发现"任务读歪/目标搞错"属 **fatal**（方向全错，回炉重来）。

7. **创新点 / 基线对比 / 验证强度**（对应 `academic-toolkit/skills/math-modeling-contest-route-selection/references/paper-scoring-framework.md` 的 `model_fit_and_originality` 0.16 + `validation_strength` 0.14 = **0.30 权重**，不含 `differentiation` 0.05）：竞赛范围在成稿前以 `MODELING_REPORT.md`、`RESULTS.md`、`figures/*_results.json` 为证据（其他 scope 用对应的结果与验证产物等价核对），按七项做法逐条核对；缺什么就在 `fix` 里写成"需补……"的补做指令：
   - **创新点**
     - *研究张力*：是否用题目里的具体限制/矛盾说明问题为什么值得研究；策略/设计类必须有具体未满足要求，求解计算类允许背景导入，不硬造张力。
     - *贡献增量*：去掉方法名后是否还能说清改变了什么；应落到"方法组合 delta / 策略 delta"，不能只堆"用了 X、Y、Z"。
   - **基线对比**
     - *有解释力的比较*：是否给出能回答"选哪个/控制了什么"的对照——多方法择优、与基准模型对比、跨问/跨情形对照、灵敏度或鲁棒性对照；只报自身方法结果而没有任何对照，即记 finding。
   - **验证强度**
     - *证据对应主张*：每个主结果是否有精确复现值 + 验证手段并列（算法对照误差、R²、扰动实验等）；"误差较小/效果良好"式无支撑形容即记 finding。
     - *条件紧随结论*：结论是否带适用条件、参数口径、约束区间；模型简化是否明示为决策。
     - *资源交付说明*：题目要求的结果文件/附录索引，是否与结果台账、交付清单对齐。
     - *有边界认识*：摘要层面不强求；核对正文"模型评价与推广"是否交代适用范围与局限。
   - **`fix` 字段（强制）**：本类 finding 的 `fix` 必须以 `需补 baseline 对比：` 或 `需补验证：` 开头（可并列，用 `；` 分隔），写明补什么、补到哪个产物/章节、用什么证据判定完成；这是第 8 步成文步的显式输入，不得只写"建议加强"。本类属质量缺口，按 `major`/`minor` 分级，不占用 `fatal`（方向反/重复计量/跨问硬矛盾/任务读歪）名额。
   - **完整对照表**：[`references/oral-practices-bridge.md`](references/oral-practices-bridge.md) 给出七项做法的语料形态、高分加分形态 5 条与 ≤3 条建议纪律；其适用时机是**第 8 步初稿存在后**——本步只产出可执行的 fix 指令，不基于尚未生成的稿件做摘要级范例对照。

⛔ **诚实认知（天花板）**：本复核 AI 与答题同源，有共同盲区，**显著降漏网率但非万无一失**（尤其"任务理解"这类：你也可能和答题时一样误读同一句话）。机器可判的部分已由 logic_audit/cross_problem_check 确定性拦截，本步只兜"确定性查不了的语义残余"。发现存疑处要给出"哪行代码/哪个数/哪句原文"支撑，不做无证据的断言。

## Step 3: 产出裁定（人读 + 机器读）

当通过只读审稿子 Agent 执行时，子 Agent 仅在会话回复中提供报告与 JSON；主 Agent 负责原样、受控地写入以下工作区文件，并在最终复审时登记该会话证据。不要要求只读子 Agent 直接编辑文件。

```bash
# 人读报告
cat > COMP_REVIEW.md <<'EOF'
# 逻辑对抗复核报告
（逐条：问题描述 / 严重性(fatal|major|minor) / 定位(文件:行或数值) / 证据 / 建议）
EOF
```

机器可读裁定 `COMP_REVIEW_VERDICT.json`：
```json
{"findings":[
  {"category":"bound_direction|double_count|extrapolation|missing_feature|cross_problem|task_understanding|innovation_baseline_validation",
   "severity":"fatal|major|minor","where":"calibrate.py:L692 或 Q1峰值","evidence":"...",
   "fix":"需补 baseline 对比：<基线/对照与呈现位置>；需补验证：<验证手段与判定阈值>"}
],"fatal_count":0}
```

第 7 类（`innovation_baseline_validation`）的 `fix` 两个前缀必须可被逐字检索：`需补 baseline 对比：` 用于创新点与基线对比类缺口（缺具体研究张力、缺贡献 delta、缺对照组/基准模型/跨情形对照），`需补验证：` 用于验证强度类缺口（缺敏感性、扰动、消融、极限情形或外部核验）；二者都不适用时仍须写明"本类无缺口"及证据位置。第 8 步成文步把这两类前缀当作显式补做清单逐条落实。


## 执行与产出

使用当前执行会话完成本步工作；产物路径按当前步骤合同。程序采集真实操作、输入输出、版本与运行清单，模型只负责实质成果和领域质量。

建议额外记录：审稿人模型、session_id、审查轮次。

## Step 4: 硬门禁（⛔ 有 fatal 不许放行）

`finish` 调用真实 review 检查器读取裁定。`fatal_count > 0`、裁定无法解析、必需证据缺失均不能通过；不得把解析失败转换为0。当前执行者只根据独立审查的具体发现修订业务产物。
> - `fatal`（方向反/重复计量/跨问硬矛盾/任务读歪）= 退出前必修，回炉重跑。
> - `major/minor`（外推口吻、可疑假设、创新/基线/验证缺口）= 不硬拦，但必须在论文里如实标注为"情景模拟/假设"、禁确定性口吻，并按 `fix` 逐条补齐。

## 退出判据（Verification）

本步完成前逐项自检（不达标即视为未完成）：

- [ ] 由只读子智能体执行并留真实会话证据
- [ ] 发现项按 fatal/major/minor 分级且逐条给依据
- [ ] 每条依据指向具体文件与位置（不是印象）
- [ ] 第 7 类 findings 的 `fix` 均以 `需补 baseline 对比：` 或 `需补验证：` 开头，可直接作为第 8 步补做清单
- [ ] 前轮已闭环项不复述，只列新增项

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "总体没问题" | 无分级清单＝没审；本步产物必须能被逐条核对。 |
| "我自己写的我最清楚" | 作者对自己的假设是盲的：本项目实测独立审稿首轮抓出 2 fatal + 1 major。 |
| "先跳过，时间紧" | 审核是防伪造防线的核心；跳过会让后续所有证据链失去意义。 |

> 本段与 `skills/_utils/anti_rationalization.md`（全局版）配套：本表是本步专属，
> 全局版覆盖跨步骤通用借口。新增借口时优先落到本表（更贴岗位），能泛化再上升。

## 补充参考

- `references/mml-skills/championship-review-method.md`：冠军模式模拟审稿方法（championship 多轮独立审稿闭环）——高强度审稿轮读。（来源 Math-model-skills，MIT，溯源见同目录 UPSTREAM.md）
