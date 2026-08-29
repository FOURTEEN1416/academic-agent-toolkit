---
name: acat-doc-governance
description: "academic-agent-toolkit 仓库专属文档治理规程。做文档盘点、真源刷新、污染源清理、归档、命名治理时使用。内置用户铁律：治理任务必须全文读完所有相关文档（禁止只看文件名）、过期与可疑信息必须清理、不重建≠不读。"
argument-hint: [盘点|清理|归档|全量治理]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent
---

# ACAT 文档治理规程（项目专属）

本仓库（academic-agent-toolkit，`D:\Desktop\数模竞赛`）的文档治理铁律与操作规程。
用户裁定（2026-08-28）已固化如下，任何宿主（OpenCode / ZCode）下的治理任务都必须遵守。

## 用户铁律（违反即返工）

1. **全文阅读铁律**：凡是文档治理任务（盘点/刷新/清理/归档），必须用 Read 工具**逐份完整读完**
   所有相关文档——包括长文档分段读完。**只看文件名、只读开头、只看标题都不算盘点。**
   "不重建（先查后建）"的前提是先全量读完，不是跳过阅读。
2. **污染源清理铁律**：读到以下内容必须处置，不得留着：
   - 过期声明（引用已不存在的路径、被后续事实推翻的数字基线、过时定位表述）；
   - 可疑信息（疑似密钥/token、个人隐私、无证据的"已完成"声明、损坏文本如首字母丢失）；
   - 矛盾真值（同一事实多个版本：以最新实证为准，历史文档加"仅供追溯"横幅）。
3. **定位铁律**：本项目是**完整科研工具箱**（全学术 Agent 工具箱），不只是数模竞赛工具。
   目录名/文档标题/自我指称一律不得窄化为"数学建模/数模"。
4. **集成铁律（2026-08-29 增补）**：新技能"融入"≠ 复制进 `skills/` 目录。按设计哲学
   （`dev-docs/解析/01-总纲` 三层架构 + `docs/superpowers/plans/2026-08-18-systematic-upgrade` 三条钢律
   + CodeSucker 融合案例），完整融入至少含：①SKILL.md 适配套件规范（输入/输出契约+质量铁律）并加
   `## STEP_MANIFEST 产出声明`；②外部能力经稳定 bridge/脚本入口；③named gates 可校验产物；
   ④`engine/modex-core/templates.json` 注册工作流步骤（含 required_checks/metadata）；
   ⑤`references/UPSTREAM.md` 溯源并登记 `tools/check_provenance.py`；⑥对应测试/验收证据。
   缺任何一项即为"堆放"，治理时须标记并补齐。

## 本仓库真源锚点

| 真源 | 路径 | 管什么 |
|------|------|--------|
| 入口索引 | `dev-docs/truth-index.md` | 哪份文档是权威、活性状态 |
| 操作日志 | `LOG.md`（仓库根） | 为什么这样做（粗粒度，按任务） |
| 删除台账 | `dev-docs/DELETION_LOG.md` | 删了/归档了什么，为何 |
| 任务计划 | `task_plan.md`（仓库根） | 当前阶段与验证基线 |
| 主控文档 | `科研工具箱/AGENTS.md`（原数学建模全流程套件） | 架构/审计/路由规则 |
| 能力目录 | `capabilities/catalog.json` | 能力清单与验收证据 |

## 生命周期三态

- **truth**：随变更同步，过期即修（truth-index、AGENTS.md、catalog、LOG）。
- **derived**：一次性报告，沉淀结论后顶部加"仅供追溯（截至日期）"横幅，不再维护。
- **archive**：移入 `dev-docs/archive/`，只读禁改禁删；归档动作记入 DELETION_LOG。

## 治理操作规程

1. 全量通读（铁律 1）→ 2. 建污染清单（文件:行号+证据）→ 3. 分级处置：
   P0 修真源冲突 / P1 加横幅标 derived / P2 归档搬运 / P3 命名统一；
   4. 处置动作逐条记 LOG.md + DELETION_LOG.md；5. 验证（pytest + 探针）后才能声明完成。

## 常用命令

```bash
python -m pytest -q                      # 套件根运行，当前基线 225 passed
python tools/check_provenance.py          # 溯源台账校验
git log --oneline -5                      # 与文档声明的提交状态核对
```
