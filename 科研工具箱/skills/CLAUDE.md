# 科研工具箱 — 科研 Agent 技能库（宿主无关）

> 完全独立的科研/数模竞赛 Agent 技能系统。不依赖任何特定商业宿主。
> 任意能读文件、能执行 Python CLI 的智能体均可驱动：Claude Code / Cursor /
> Gemini CLI / MiMo Desktop / OpenCode / ZCode / 自写脚本等。

---

## 三层架构

```
skills/       ← 技能层（263 个技能，每个一个 SKILL.md；含 agent-bootstrap / tool-forge）
tools/        ← 工具层（tools/ 顶层 .py + 受控 .pyc 分发件；调用一律用同名 .py 真源）
engine/       ← 编排（44 模板）+ 状态库 + 质量门禁 + 审计 + 宿主无关驱动协议
```

## 快速开始（任意 Agent）

```bash
# 1. 读仓库根 AGENTS.md 与本目录 AGENTS.md
# 2. 驱动契约与能力探测
cd 科研工具箱
python -m engine.workflow_cli boot
python -m engine.workflow_cli probe
# 3. 按路由读 skills/<name>/SKILL.md，或 start 工作流
# 4. 缺工具时自适应铸造
python -m engine.workflow_cli forge --tool <name> --purpose "..."
```

自举技能：`skills/agent-bootstrap/` · 铸造技能：`skills/tool-forge/`
可选适配器：仓库根 `agents/adapters/`（协议不依赖）

## 工作流模板

全部模板定义在 `engine/modex-core/templates.json`。常用：

| 模板 | 流水线 | 说明 |
|------|--------|------|
| `comp_cumcm`（及 comp_mcm/comp_huawei 等竞赛变体） | 分析→建模→求解→论文→审查 | 竞赛端到端 |
| `paper_submission` | 规划→撰写→评审→返修 | 论文投稿管线 |
| `paper_writing` / `paper_writing_zh` | 规划→撰写→编译 | 论文写作 |
| `literature_review` | 文献综述 | 单阶段 |
| `course_paper` | 课程规划→课程报告 | 2 阶段 |
| `grad_project` | 需求→设计→编码→自测→报告 | 毕业设计/软件项目 |

## 技能发现

| 用户意图 | 加载技能 |
|---------|---------|
| 如何驱动本项目 / 自举 | `agent-bootstrap` |
| 缺工具 / 造工具 / 自适应 | `tool-forge` |
| 拿到题目不知道怎么做 | `comp-prob-analysis` → `comp_cumcm` 管线 |
| 需要建立数学模型 | `comp-modeling` |
| 需要写代码求解 | `comp-code` |
| 需要写论文 | `comp-paper-zh` 或 `comp-paper-en` |
| 需要审查论文 | `comp-review` 或 `auto-review-loop` |
| 需要搜索文献 | `literature-review` 或 `research-lit` |
| 需要做实验 | `experiment-plan` → `experiment-bridge` |
| 模糊想法 | `idea-discovery` |
| 开题 / 基金 | `thesis-proposal` / `grant-proposal` |

## 编排规则

1. **顺序流水线**：按模板步骤顺序执行
2. **检查点**：完成后暂停，等用户确认
3. **动态裁剪**：按 `params` 增删步骤
4. **产物合同**：工作流产出放在 StepAction.workspace
5. **防编造**：引用需检索验证；**无证据＝未执行**
6. **TOOL_GAP**：工具够不到就 forge 或如实上报，不伪造通过
7. **可复现**：相同输入走相同流程

## 工具链（示例）

| 工具 | 用途 |
|------|------|
| `tools/scholar_fetch.py` | 学术文献搜索 |
| `tools/gpt_image.py` | 科研插图生成 |
| `tools/reviewer_client.py` | 外部 LLM 评审 |
| `tools/doc_reader.py` | DOCX/PDF 完整读取（含嵌入图） |
| `engine.workflow_cli boot/probe/forge` | 协议 / 探测 / 铸造 |

## 技能目录结构

```markdown
---
name: skill-name
description: "是什么 + 触发词（何时使用）"
---

# 技能名
## 触发 / 输入契约 / 执行步骤 / 输出契约 / 质量铁律
```

## 集成提示

外部技能库并入 `skills/` 后须：补 catalog 映射、CONTEST_SKILL_MAP 归类、
`build_skill_index.py --emit`，并遵守质量铁律。
