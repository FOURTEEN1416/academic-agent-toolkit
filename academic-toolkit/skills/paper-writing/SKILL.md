---
name: paper-writing
description: "论文写作入口：按语言与目标选择 paper_writing / paper_writing_zh / nature_writing / paper_from_assets 工作流，由引擎分派规划、分析、绘图、写作、编译与改进循环各步，从叙述式报告走到可投稿 PDF。"
argument-hint: [narrative-report-path-or-topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, Skill
---

# 论文写作入口

本技能负责把用户目标映射到现有工作流，不自行调度第二套步骤。

## 输入

读取研究叙述、已有结果、目标期刊/会议、语言和交付格式。缺少真实实验或引用证据时先定位缺口，不把未知结果补成论文结论。

## 路由

- 英文研究论文：`paper_writing`。
- 中文研究论文：`paper_writing_zh`。
- Nature 风格论文：`nature_writing`。
- 从现有资料起步：`paper_from_assets`。

若任务已有工作流 ID，恢复该工作流，不重复创建。没有工作流时，用 `python -m engine.workflow_cli start --template <模板> --workspace <工作区> --params <业务参数JSON>` 创建，再用 `next` 领取当前步骤。

## 执行边界

`next` 提供当前步骤的目标、产物、必要技能及执行会话。仅执行当前步骤，不提前调用后续写作、编译或评审。业务产出用会话的 `read/write/edit/run` 完成，`finish` 自动记录与验收并给下一步。

- 论文大纲须把论断与证据对应，不能以图表数量代替研究内容。
- 语言、页数、格式、图表与引用约束来自本次目标和模板，不固定成某个会议或模型。
- 人工检查点必须等待真实批准；无人回复不等于同意。
- 编译、审稿、返修是不同的业务步骤；不得通过入口技能再排一套隐式循环。
- 评审需要独立上下文；不能以自审或读取技能冒充已完成独立审稿。

## 交付

以工作流当前合同和最终质量结论为准交付正文、源文件、参考文献、编译结果及修改记录。说明证据缺口和未完成事项，不把生成 PDF 等同达到投稿质量。执行清单、指纹和状态由程序维护，不要求模型另写机械回执。
