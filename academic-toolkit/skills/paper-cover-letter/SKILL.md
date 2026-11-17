---
name: paper-cover-letter
description: Use when a journal submission package needs editor-facing pieces: cover letter, significance statement, highlights draft, plus letter-versus-manuscript consistency checklist. Not for technical preflight (use paper-presubmit-checks) or full content audit (use paper-submission-audit).
---

# Cover Letter Package（投稿信配套件）

## Overview

本技能覆盖投稿时随稿提交的三份"给编辑看的"文书与一次信-稿一致性自检：

1. **Cover Letter**（投稿信）——写给目标期刊编辑，说明投什么、为什么适合该刊、原创性声明；
2. **Significance Statement**（意义陈述）——面向非专业读者/跨领域编辑，说明工作为什么重要；
3. **Highlights**（亮点）——3-5 条短句，概括核心贡献（多数出版社要求每条 ≤85 字符）；
4. **信-稿一致性自检单**——逐条核对信中表述与稿件正文/摘要/结论是否一致，防止"信里吹、稿里虚"。

**边界（与同域技能分工）**：

- 目标期刊还没定 → 先走 `paper-journal-selection`（选刊在前，本技能在其后）；
- 稿件内容质量/声明支撑审计 → `paper-submission-audit`（它审稿件本身，本技能只保证"信"与"稿"对齐）；
- 技术性预检（引用格式、图表自包含、数据可用性声明等）→ `paper-presubmit-checks`；
- 收到审稿意见后的回复 → `paper-rebuttal-nature`（期刊 point-by-point）。

## When To Use

适用：稿件定稿前后、准备向期刊投稿时；返修重投需要更新投稿信时；需要把摘要改写成 significance statement 或 highlights 时。

不适用：推荐审稿人名单、版权转让表单填写、投稿系统账号操作——这些属于投稿平台事务，本技能只产出文本草稿。

## Inputs

| 输入 | 必需 | 说明 |
|---|---|---|
| 稿件摘要或结论段 | ✅ | 一致性核对的事实基准 |
| 贡献点清单（2-4 条） | ✅ | 可来自稿件引言末段或作者自述 |
| 目标期刊名 + scope 陈述 | ✅ | 用于"为什么适合本刊"论证 |
| 通讯作者与单位信息 | ✅ | 信头 |
| 既往沟通/预咨询记录 | 可选 | 有则引用（"Following our presubmission inquiry…"） |
| 期刊 cover letter 规范 | 可选 | 部分期刊有固定问题清单，按其模板作答 |

## Outputs

- `COVER_LETTER.md` — 投稿信正文
- `SIGNIFICANCE_STATEMENT.md` — 意义陈述（期刊要求时）
- `HIGHLIGHTS.md` — 亮点条目（期刊要求时）
- `LETTER_CONSISTENCY_CHECK.md` — 一致性自检单（逐项勾稽）

## Workflow

1. **读稿取证**：从摘要与结论提取可声称的贡献（每条注明出处章节）；超出结论的表述一律不得进入信件。
2. **撰写 Cover Letter**，推荐结构：
   - 信头：日期、收件编辑（可写 Dear Editor / 具名）、稿件标题与文章类型；
   - 第 1 段：一句话说清投什么 + 核心发现；
   - 第 2 段：2-4 条贡献点，每条对应稿件中的证据位置；
   - 第 3 段：为什么适合该刊（引用期刊 scope/近期相关文章方向，不编造）；
   - 第 4 段：标准声明——原创、未一稿多投、无利益冲突、所有作者已同意；期刊要求时加 AI 使用披露与数据可用性指向；
   - 落款：通讯作者、单位、联系方式。
3. **撰写 Significance Statement**：100-200 词，面向非本方向读者；先说领域痛点，再说本工作改变了什么，避免行话堆砌。
4. **撰写 Highlights**：3-5 条，每条一个完整短句、≤85 字符（按期刊要求调整），写结果不写过程（"X improves Y by Z"优于"We studied X"）。
5. **跑一致性自检单**（见下节），逐项留痕到 `LETTER_CONSISTENCY_CHECK.md`。
6. **交付**：四件产出齐备；自检单中任何一项不过，先改信或改稿，不带病交付。

## 信-稿一致性自检单

| # | 检查项 | 判据 |
|---|---|---|
| 1 | 创新点表述一致 | 信中每条贡献点都能在摘要/结论中找到同强度表述；信中不得出现稿件没有的新结论 |
| 2 | 数字一致 | 信中引用的效果量/样本量/性能数字与稿件正文完全一致（含单位与百分号） |
| 3 | 术语一致 | 方法与对象命名与稿件一致，不引入新缩写 |
| 4 | scope 命中 | "适合贵刊"的论证引用的是期刊真实 scope 方向，不虚构刊物定位 |
| 5 | 声明齐全 | 原创性、一稿单投、利益冲突、作者同意四项声明在场；按期刊要求补 AI 使用与数据可用性 |
| 6 | 语体与长度 | significance/highlights 符合期刊字数或字符上限 |
| 7 | 无过度声称 | 不出现 "first ever" "revolutionary" "breakthrough" 等无证据强词；谦逊限定与稿件一致 |

## Verification（退出判据）

- [ ] 四份产出文件齐备且互相引用的标题/数字一致；
- [ ] 自检单 7 项全部勾稽通过，未过项已整改或如实记录原因；
- [ ] 信中每一个事实性断言都能指出稿件出处（章节/图表号）；
- [ ] 期刊名称、文章类型、通讯作者信息无误。

## 常见合理化（Common Rationalizations）

- "投稿信是走过场，抄摘要就行" → 抄摘要会丢失"为什么适合本刊"的论证，且常引入稿件没有的旧版表述；按第 2 步结构重写。
- "编辑不会逐字核对" → 审稿人 and 编辑会以信件为基准核对声明；一致性自检单就是为此设的硬闸。
- "亮点条数不够，把结论拆成两句凑数" → 拆句会产生无支撑的半句话；不足 3 条时如实写 2 条并核对期刊下限。

## Worked Example

完整样例（虚构稿件《Adaptive Sampling Reduces Simulation Cost》的投稿信四件套）见
`examples/sample-cover-letter-package.md`。
