---
name: research-review
description: "Get a deep critical review of research via external reviewer. Use when user says ”review my research”, ”help me review”,"
argument-hint: [topic-or-scope]
allowed-tools: Bash(*), Read, Grep, Glob, Write, Edit, Agent
---

# 独立研究评审

## 目标与输入

对当前研究方案、证据和论证进行独立批评。输入为实际方案、论文/代码、结果、已知问题及本轮修改。评审不是生成漂亮分数，不得用自述、占位结果或模型名证明质量。

## 执行

1. 从当前步骤合同读取评审范围和输出路径；只读检查相关输入，避免把实现过程的辩护带进审查上下文。
2. 用 `session review-request` 创建版本绑定任务：逐个指定真实输入、输出 `review_report.md` 和具体rubric。任务记录由程序写入，不手算哈希。
3. 当前宿主把任务交给独立上下文，评审者只提供结论原文，不修改研究成果。宿主没有独立上下文时明确告知未具备，不把自审当独立评审。
4. 用 `session review-receive` 接收实际评审原文、评审者和实际宿主调用标识；程序检查输入版本未改变并绑定返回文件。调用标识属于可追溯信息，不宣称密码学认证了独立性。
5. 依据评审发现修正研究工作，再针对新版本复审；不要沿用旧版本裁定。需要人类决定时等待明确批准。
6. `finish` 统一检查产物与执行事实，当前Agent不另拼execution_evidence或预填返回码。

## 评审重点

- 问题与方法是否匹配，是否存在逻辑断裂、过强假设或数据泄漏。
- 核心贡献相对于最接近工作的真实增量，能否被替代解释推翻。
- 数值结果、统计口径、基线、公平性和可复现条件。
- 哪个最小实验、分析或改写能够解决每个具体问题。
- 已经有证据支持什么、仍不能支持什么；可接受反例和负面结果。

## 输出

`review_report.md`（或当前合同规定路径）包含：评审输入与范围、总体判断、按fatal/major/minor排序的发现、精确定位、证据、最小修复、剩余风险。保留评审原文；分数只能来自实际评审。没有完成独立评审时明确标注，不生成通过结论。
