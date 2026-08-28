# 科研工具箱 — 科研 Agent 技能库

> 这是一个完全独立的科研/数模竞赛 Agent 技能系统。不依赖任何商业软件，所有技能和工具都是开源的。
> 可以用 Claude Code / Codex CLI / OpenCode / Gemini CLI / 任何 LLM 驱动。

---

## 三层架构

```
skills/       ← 技能层（225 个技能，每个一个 SKILL.md）
tools/        ← 工具层（32 个可执行脚本，调外部能力）
engine/       ← 质量门禁 + 竞赛规则 + API 配置加载
```

## 快速开始

```bash
# 由 Agent（OpenCode/Claude Code 等）直接驱动：
# 1. 读取 AGENTS.md 了解路由规则
# 2. 读取 skills/<name>/SKILL.md 了解技能
# 3. 按技能执行，调用 tools/ 完成具体动作

# 检查环境能力（LaTeX/绘图/API 是否就绪）
python engine/quality_gates.py caps
```

## 工作流模板

| 模板 | 流水线 | 阶段数 |
|------|--------|--------|
| comp_full | 问题分析→建模→求解→论文→审查 | 8 阶段 |
| paper_full | 选题→文献→实验→写作→图表→编译→审查 | 8 阶段 |
| paper_writing | 规划→撰写→编译 | 3 阶段 |
| literature_review | 文献综述 | 1 阶段 |
| course_paper | 课程规划→课程报告 | 2 阶段 |

## 技能发现

当用户说"我要做数模"、"写论文"、"做文献综述"等时，用以下路由规则：

| 用户意图 | 加载技能 |
|---------|---------|
| 拿到题目不知道怎么做 | `comp-prob-analysis` → 自动接 `comp_full` |
| 需要建立数学模型 | `comp-modeling` |
| 需要写代码求解 | `comp-code` |
| 需要写论文 | `comp-paper-zh` 或 `comp-paper-en` |
| 需要审查论文 | `comp-review` 或 `auto-review-loop` |
| 需要搜索文献 | `literature-review` 或 `research-lit` |
| 需要做实验 | `experiment-plan` → `experiment-bridge` |
| 模糊想法 | `idea-discovery` |
| 需要写毕业论文开题 | `thesis-proposal` |
| 需要写基金申请书 | `grant-proposal` |

## 编排规则

1. **顺序流水线**：按模板定义的步骤顺序执行
2. **检查点**：带 📌 的步骤完成后暂停，等用户确认
3. **动态裁剪**：按 `params` 参数增删步骤（`language=zh` 换中文，`skip_literature` 跳过文献）
4. **产物合同**：每阶段产出放在 `workspaces/{wf_id}/` 目录
5. **防编造**：所有引用需过 `tools/scholar_fetch.py` 验证
6. **不跳过完整性检查**：INTEGRITY 阶段必须通过
7. **可复现**：相同输入走相同流程，保证质量一致

## 工具链

| 工具 | 用途 | 来源 |
|------|------|------|
| `tools/scholar_fetch.py` | 学术文献搜索（四级 fallback） | 独立可运行 |
| `tools/gpt_image.py` | 科研插图生成 | 独立可运行 |
| `tools/reviewer_client.py` | 外部 LLM 评审 | 独立可运行 |
| `tools/tikz_vision_check.py` | 图表视觉自检 | 独立可运行 |
| `tools/derive_reference_from_docx.py` | 从参考论文派生格式规范 | 独立可运行 |
| `tools/watchdog.py` | 训练/下载任务监控 | 独立可运行 |

## 外部优化方案

推荐集成以下开源替代来优化现有技能：

| 类别 | 推荐方案 | 仓库 |
|------|---------|------|
| 学术搜索 | paper-search-mcp-nodejs | `Dianel555/paper-search-mcp-nodejs` |
| 学术搜索 | paper-pilot MCP | `aytzey/paper-pilot` |
| 论文审查 | cmu-paper-reviewer | `prometheus-eval/cmu-paper-reviewer` |
| 技能库 | academic-research-skills | `Imbad0202/academic-research-skills` |
| 技能库 | codex-claude-academic-skills | `zLanqing/codex-claude-academic-skills` |
| 数学建模 | math-modeling-skill | `XiaoMaColtAI/math-modeling-skill` |
| 数学建模 | math-modeling-skills | `Lupynow/math-modeling-skills` |
| 图表生成 | nature-paper-hub | `Yang1Bai/nature-paper-hub` |
| DOCX 导出 | pandoc-templates | `TomBener/pandoc-templates` |

## 技能目录结构

每个技能目录包含一个 `SKILL.md` 文件，结构如下：

```markdown
---
name: skill-name
description: "一句话描述。Use when [触发条件]。"
allowed-tools: [Read, Write, Edit, Bash(python:*), WebFetch, WebSearch]
---

# 技能名

## 目的
[2-3 句说明]

## 输入契约
[需要什么文件]

## 执行步骤
[分阶段步骤]

## 输出契约
[生成什么文件]

## 质量铁律
[硬性约束]
```

## 与 AlterLab 技能库集成

本项目可与 `AlterLab-IEU/AlterLab-Academic-Skills` 的 239 个技能配合使用。
克隆后，将 AlterLab 的 `skills/` 子目录并入本项目的 `skills/` 目录即可。

## 与 research-paper-workflow 集成

可与 `Airjiannan05/research-paper-workflow-skill` 的 16 技能家族配合。
该项目的 `rpw-common/` 目录提供了路由规则、源验证和握手协议的参考实现。