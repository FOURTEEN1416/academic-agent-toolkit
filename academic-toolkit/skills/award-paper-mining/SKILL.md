---
name: award-paper-mining
description: 挖掘获奖论文语料并沉淀为可复用统计资产：从公开展示页采集、按题号归档、关键页语义标注到结构化统计报告。触发词：优秀论文挖掘、获奖论文语料、范文库、award paper mining、历年论文归档、论文统计报告。
status: active
---

# award-paper-mining — 获奖论文语料挖掘与统计沉淀

## 定位

把"国赛/美赛优秀论文"从公开展示页沉淀为**可复用的结构化语料与统计资产**，持续喂养
论文写作与文献步的范文参照。本技能固化的是本仓已跑通一届样本（2021-2025 共 62 篇）的
流水线：**抓取 → 归档 → 合并 → 关键页语义标注 → 结构化 JSON → 统计报告**。

**产物落私有资料区**（`assets-local/award-papers/`，gitignored，无再分发权）；
**清单与统计摘要**（本文档同目录的 `references/` 与 `data/award_paper_exemplars.json`）入 git。

## 输入契约

- 目标年份/赛事/题型（如"2026 国赛 A-E"）
- 公开展示源（历年：中国大学生在线 dxs.moe.gov.cn；美赛：COMAP）——**只采集公开往届展示页**
- 复用策略：已有年份只增量补差；整届重跑须先声明

## 执行步骤

1. **抓取与归档**（`年/论文号/页号.jpg` 结构）
   - 逐届抓取公开展示页，按 `年/论文号/` 归档页面件；记录来源 URL 与抓取日期
   - 断链/缺页如实登记，不伪造补全
2. **逐篇合并 PDF**
   - 按篇合并页面为 `年_论文号.pdf`；合并件仅作整篇快读，**页面件是唯一真源**
   - 体积膨胀预警：合并件常达页面件 15 倍，归档前评估冷存储去向
3. **关键页语义标注**（每篇 7 页：封面/摘要/重述/建模/求解/结果/结论）
   - 标注页角色写入结构化条目；这是让语料"可检索/可对照"的关键元数据
4. **结构化 JSON 底座**
   - 每篇一条：`year / paper_id / 题型 / 页数 / 关键页映射 / problem / model / methods / key_takeaways`
   - **字段填充率如实登记**（空字段标 unavailable，不占位编造）
5. **统计报告**（可编码规则优先）
   - 摘要统计（字数区间/四要素完整度）、图表配色统计（口径显式声明：页面级≠图表级）、
     文风量化（样本覆盖数如实标注）
   - 每条统计给**样本量与口径**；口径缺陷在文首更正说明
6. **接线**（把统计资产挂进工作流）
   - 范文清单 → `data/award_paper_exemplars.json`（comp-paper-zh 写作步资产）
   - 统计报告 → templates.json 对应步骤 assets 指针
   - 更新 asset_catalog 台账 + check_asset_utilization 对账

## 输出契约

- 归档语料（`assets-local/award-papers/<年>/<论文号>/`）
- 结构化底座 JSON（每篇一条，填充率登记）
- 统计报告 md（口径声明 + 样本量 + 更正注记）
- git 内：范文清单 JSON + 统计摘要（可指向本地原件）

## 质量铁律

- **只采集公开往届展示页**；当届赛中论文/代码**绝对不采**（学术不端红线）
- 无再分发权的原件**只落私有资料区**，入 git 的只有清单/统计/改写摘编
- 统计口径必须显式（页面级 vs 图表级、样本覆盖数）；不可核验的数字不写
- 字段缺失如实标 unavailable；断链登记，不伪造
- 抓取频率克制，遵守源站 robots 与版权声明

## 关联

- 产物接线：`data/award_paper_exemplars.json`、`data/paper_selfcheck_287.json`
- 消费方：`skills/comp-paper-zh/`（写作范文参照）、`skills/comp-literature/`（同类做法定位）、
  `skills/fig-aesthetics-craft/`（配色/构图参照）
- 语料区：`assets-local/award-papers/`（gitignored，见 asset_catalog.json 的 local_only 条目）
- 回退口径：语料缺席时写作步不阻断——范文参照是可选的增强，非硬门禁
