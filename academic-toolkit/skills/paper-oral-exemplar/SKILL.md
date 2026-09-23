---
name: paper-oral-exemplar
description: "对照优秀论文范例改稿件与复盘：883 篇顶会 Oral 蒸馏七项做法，compare/reflect 双模式，含数模章节桥接表。触发词：对照优秀论文、论文复盘、范例对照、向好论文学习。"
---
<!-- ==================== 本仓适配块（Academic Agent Toolkit, 2026-09-22 整技能收编 A 批次） ==================== -->
<!-- 上游: Adkid-Zephyr/oral-paper-skill（无 LICENSE 文件，pinned @ a2c4bc4，2026-09-22）；以下正文为上游原文，仅头部/尾部适配。溯源与许可状态见 references/UPSTREAM.md -->

## 本仓适配：输入/输出契约与触发条件

**触发条件（本仓场景）**：论文修订轮（auto-review-loop / comp-review 之后）、摘要/引言/贡献声明定稿前的"对照范例"检查、学习复盘（想理解优秀论文为什么好）、竞赛论文终审前的对照自查。

**输入契约**：稿件或 idea（md/tex/pdf 文本均可）+ 阶段与论文类型声明（方法/理论/实证/系统/资源/立场，数模论文按桥接表归类）+ 可选范例材料（上游语料 883 张已核查证据卡在其仓库 `research/abstract_distillation/cards/`，本地副本在 `vendor/forks/oral-paper-skill/`，gitignored）。

**输出契约（两模式二选一，按用户请求）**：
1. 对照改进模式：≤3 条源链接建议，每条六要素——Practice（范例做法）/ Source（论文+链接+阅读层级+位置）/ Relevance（为何适用本稿）/ Observation（稿件现状）/ Action（具体改法）/ Reflection（复盘问题）；无适合来源时标注"通用研究建议"，禁止编造引用；
2. 学习复盘模式：单做法讲解 + 已核查实例 + 一个针对用户稿件的复盘练习。

**质量铁律（上游纪律，本仓强化）**：
- 阅读层级不越级——摘要级证据不得冒充全文/图表/证明结论；归因必须带实际查看位置；
- 不输出录取概率、Oral 评分、GO/WAIT/KILL 默认裁决；
- 七项做法是"编辑动作"不是评分表，按需选 1-3 项，不强套每篇论文；
- 无证据的建议标注为推断；不虚构实验结果或成功形态的假想曲线。

**数模/通用桥接表（七项做法 → 论文章节，本仓本地化增量）**：

| 做法 | 通用论文章节 | 数模竞赛论文章节 |
|------|------------|----------------|
| 写清研究张力 | 引言/问题重述 | 摘要页、问题重述（"为什么重要"具体化） |
| 明确贡献增量 | 引言/贡献声明 | 摘要、模型建立（去掉模型名说清改变什么） |
| 证据对应主张 | 结果/论证 | 模型求解与结果分析（每个主张对应哪张表/图） |
| 有解释力的比较 | 实验/讨论 | 模型对比、灵敏度分析（说明控制了什么变量） |
| 条件紧随结论 | 定理/范围声明 | 模型假设、模型评价（适用范围不省略） |
| 资源支持的研究 | 数据/代码可用性 | 附录（代码/数据可复现说明） |
| 有边界的认识 | 结论 | 结论与推广（读者能带走什么、何时不适用） |

## STEP_MANIFEST 产出声明

- artifacts: 对照建议（≤3 条六要素）或复盘练习 + 所用做法清单
- gates: 来源溯源三件套（论文+链接+阅读层级）；输出模式与用户请求匹配；无录取预测/评分
- evidence: 建议清单即执行证据，落盘至工作区 .engine/evidence/
# Oral Paper Skill

Turn useful practices from exemplary papers into concrete revisions and focused learning. Offer two services: **compare and improve** a manuscript, or **learn and reflect** on a practice. Preserve the author's research purpose and judgment.

The current knowledge base includes semantic extraction of 883 abstracts from 884 official event records, source checks, and cross-paper synthesis. It is abstract-level evidence, not 883 full-paper readings or an explanation of Oral selection. For provenance, read [sources and reading levels](references/oral-patterns.md).

## Start from the author's purpose

Identify the requested artifact, contribution type, stage, and relevant constraints. Use the supplied draft, results, and examples before asking for more. Ask only when missing information would materially change the advice or authorization.

Several coherent contributions are allowed. Missing evidence in an early idea differs from evidence contradicting a result claim. Do not turn a writing or learning request into an automatic decision to abandon research.

## Choose a relevant practice and example

Read [abstract-derived practices and examples](references/abstract-derived-practices.md) when applying the distilled knowledge. Select only the practices useful for this request; do not run every paper through all seven.

1. **Specify the research tension.** Identify an unmet requirement or an observation that makes the question worth investigating. Do not manufacture a prior-work failure.
2. **State the contribution delta.** Name the changed output, operation, representation, assumption, or enabled activity. A method name and “novel” do not explain the difference.
3. **Match evidence to the claim.** Identify the measured or proved property. Keep attempts distinct from success, a proxy from the whole capability, and proposed evaluation from reported outcomes.
4. **Choose a meaningful comparison.** Explain what decision it resolves, what stays fixed, and what changes. For efficiency, identify the actual resource unit and accounting boundary; active parameters, tokens, latency, memory and total cost are different quantities.
5. **Keep conditions beside conclusions.** Preserve the model class, quantifier, guarantee regime, comparator and numerical convention that give the result its meaning.
6. **Explain what the resource enables.** Connect contents or interfaces to a research activity. Distinguish intended uses, demonstrated uses and release commitments.
7. **Extract a bounded lesson.** Explain what readers can reconsider or investigate, separating observation, interpretation and a proposed action. State what would limit transfer.

These are editorial moves supported by examples, not measured universal traits or admission criteria. Their usefulness for a new manuscript is a reasoned recommendation, not a demonstrated causal effect.

Choose exemplars by problem, contribution, evidence needs and resource constraints—not fame alone. Use [archetype guidance](references/archetypes.md) for theory, empirical, systems, resource, method and position-paper differences. A resource need not also deliver a new mechanism or a superior model; a descriptive finding need not claim causality.

## Keep source attribution precise

For an attributed practice, identify the paper, source link, and inspected abstract unit, section or figure. The curated examples have been checked against their original abstracts; their numbered units belong to the stored snapshot, not official section numbers.

- Separate **what the source says**, **why the practice might help**, and **what you propose for this draft**. An application suggestion is not an experiment the authors necessarily ran.
- Abstracts support framing, stated contributions and author-reported evidence. Inspect the relevant full text or actual figure before attributing experimental rigor, proof details or figure design to a paper.
- Preserve consequential qualifiers: structural-assumption-free is not assumption-free; a reported maximum error is not automatically a proved bound; an unspecified percentage is not automatically percentage points; a future release is not present availability.
- Keep genuinely unspecified source facts unknown. Do not repair them from intuition or treat absence from an abstract as absence from the full paper.
- If a suitable source is unavailable, label advice as general research guidance. Do not invent citations or make the user supply references merely to satisfy a template.

Do not reload the entire corpus for a single edit. Use a small, relevant comparison set and retrieve additional material only when the recommendation depends on it.

## Compare and improve

Locate the draft's important claim and its current support. For each high-priority change, connect:

**draft location → relevant source practice → concrete revision or feasible next check → why it fits → important limit.**

Default to at most three improvements. Prioritize changes that alter understanding or interpretation over cosmetic resemblance. If no useful gap is apparent, say so rather than inventing criticism.

When asked to edit, deliver the revised text, figure plan or experiment protocol directly. Keep the title, abstract, introduction and main evidence coherent, without forcing every section to repeat one claim. Preserve the author's story unless actual evidence requires changing its scope.

For a proposed experiment, specify only what changes the decision: the claim, comparison, unit of analysis, relevant controlled conditions, outcome, and how results would change the interpretation. “Match everything” may answer the wrong question; distinguish component attribution from comparing systems as delivered. If a claim is already contradicted, do not use prose to conceal it.

## Learn and reflect

Teach one useful practice with a small sourced example. Explain its purpose and an important exception, then give one focused exercise on the user's paragraph, comparison or plan. Label any invented teaching example or illustrative rewrite explicitly.

If the user requests both modes, prioritize the artifact and explain only the lessons that affected it. Use [the comparison guide](references/review-scorecard.md) only when a structured retrospective would help.

## Evidence and delivery

Keep observed findings, supported claims, inferences, plans and invalidated claims distinct, without burdening every response with status labels. Do not turn pilots, mechanical checks or AI judgments into prevalence, transfer, novelty or readiness claims. Planned figures must not contain fabricated results or success-shaped mock curves.

ORAL can remain an optional mnemonic: central question, reader-visible evidence, meaningful alternatives, and a lasting lesson. It is not the empirical conclusion of the corpus analysis, a score, or a required sequence.

Before delivery, check the few things that matter: source fidelity, applicability, a concrete change, and consistency with the actual evidence. Self-review and format validation are not evidence of measured user benefit.

Keep the response concise. Do not default to GO/WAIT/KILL, Oral-level ratings, acceptance predictions, or another literature survey when the user asked for a revision.
