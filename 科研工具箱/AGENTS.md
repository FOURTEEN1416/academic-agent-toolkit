# 科研工具箱 — 全学术 Agent 系统（原：数学建模全流程套件）

> 这是一套**完整科研工具箱**（全学术 Agent 工具箱，6 大能力域：数模竞赛、学术论文、文献与研究、
> 课程与研究材料、知识产权材料、图表与文档生产），为 **OpenCode 桌面版**适配，ZCode 兼容层可用。
> 数模竞赛（CUMCM）是验证场景之一，不是产品边界。
> **OpenCode Desktop 是唯一主控**：当前 agent（你）直接读取技能、调用工具、执行全部工作。
> 引擎（engine/）只负责状态记忆、编排、质量门禁和审计，绝不代执行。
> 本系统完全独立，不依赖任何其他商业软件。
>
> **宿主兼容（2026-08-20 起）**：ZCode 通过仓库根 `AGENTS.md` + `.zcode/` 兼容层接入同一套
> 技能库与引擎（见根 AGENTS.md 宿主支持矩阵）。ZCode 下 L1 拦截式审计插件暂无等价物，
> 审计依赖 L2 编排式 + L3 申报式两层；其余规则（引擎只编排、complete_step 回报、门禁）
> 在两个宿主下完全一致。

---

## 定位（重要）

**执行者 = OpenCode 桌面版中运行的 agent（你）。**
引擎不是执行者，只是"记忆和编排"：
- `workflow_store` — 记录谁做了什么、做到哪、卡在哪（SQLite）
- `workflow_runner` — 告诉你下一步做什么（next_action）
- `quality_gates` / `run_logger` / `audit_store` — 验收标准 + 审计记录 + 操作审计报告

**不存在"调用另一个 opencode"的逻辑。** 你读到 `StepAction` 后直接执行技能，
完成后调用 `complete_step` 回报结果。

## 审计体系（三层，缺一不可）

系统对"智能体做了什么"采用**三层审计**，互相补充、不可互相替代：

| 层 | 机制 | 记录内容 | 写入位置 | 可否绕过 |
|---|------|---------|---------|---------|
| **L1 拦截式** | OpenCode plugin（`.opencode/plugins/audit-trail.ts` + 官方 `opencode-logger`） | 每次工具调用（bash 命令全文/编辑路径/skill 名/task 描述）、文件编辑、会话、权限请求 | 共享根 `.engine/audit/operations.jsonl` + `log.jsonl` | ❌ 不可绕过（运行时钩子，agent 无法跳过） |
| **L2 编排式** | `WorkflowRunner` 引擎侧写入 | workflow 启动/步骤完成（含声明命令）/checkpoint 批准 | 同一 `.engine/audit/operations.jsonl` | ⚠️ 仅当走 runner 流程时 |
| **L3 申报式** | `complete_step()` 的 execution_evidence | skill 哈希、声明命令、输入输出产物、产物 manifest | 工作区 `.engine/evidence/*.json` | ⚠️ 依赖 agent 主动申报 |

**防绕过检测**：`engine/audit_store.detect_unreported_operations()` 交叉比对
L1 实际执行的操作 vs L3 申报的命令/产物，发现"实际发生了但未申报"的操作即标记
`warning` 并写入 `OPERATION_AUDIT_REPORT.json`。该文件是操作审计，不得覆盖竞赛交付步骤生成的 `AUDIT_REPORT.json`。生成命令：

```bash
python -m engine.workflow_cli audit --workspace <工作区>   # 生成 OPERATION_AUDIT_REPORT.json
```

## 一、系统架构

```
套件/
├── AGENTS.md              ← 你在这里（Agent 入口路由）
├── skills/                ← 技能库（由 opencode.json 的 skills.paths 自动扫描，每个技能一个 SKILL.md）
├── tools/                 ← 工具链（32 个可执行脚本）
├── engine/                ← 状态库 + 编排 + 质量门禁 + 审计（不执行）
├── data/                  ← 参考数据（模型库/题型规律/历史题目）
├── .env                   ← 本地 API 配置（gitignored，不入库不入发布包）
└── .gitignore             ← 排除 .env 和 __pycache__
```

## 二、核心原则

1. **技能即知识**：每个 `skills/<name>/SKILL.md` 描述"如何做一件事"
2. **Agent 即执行者**：OpenCode 读取 SKILL.md 后自主执行，无需外部调度器
3. **工具即手脚**：`tools/*.py|pyc` 是独立可执行脚本，被技能通过 Bash 调用
4. **门禁即质量**：每步产出后检查质量（页数/伴随文件/大小），不达标则重做
5. **Agent 定角色**：executor（执行）/ reviewer（审查）/ editor（润色）

## 三、入口路由规则（P3 核心）

当用户提出需求时，按以下规则路由到技能：

### 数模竞赛（用户最常用）

| 用户意图 | 路由到 | 自动接续 |
|---------|--------|---------|
| "我要参加国赛/美赛/CUMCM" | `skills/comp-pipeline/` | 完整 8 阶段流程 |
| "帮我分析这个题目" | `skills/comp-prob-analysis/` | → comp-modeling |
| "建立数学模型" | `skills/comp-modeling/` | → comp-code |
| "写求解代码" | `skills/comp-code/` | → comp-review |
| "写竞赛论文" | `skills/comp-paper-zh/` 或 `comp-paper-en/` | → comp-compile |
| "审查我的论文" | `skills/comp-review/` | loop-until-clean |
| "统计建模/数分" | `skills/comp-stats-topic/` | → comp-code |

### 科研论文

| 用户意图 | 路由到 |
|---------|--------|
| "我要做科研/写论文" | `skills/paper-writing/` 或 `paper-write-zh/` |
| "做文献综述" | `skills/literature-review/` |
| "找研究方向" | `skills/idea-discovery/` |
| "写中文 LaTeX 论文" | `skills/paper-write-zh/` |
| "写 Nature 论文" | `skills/paper-write-nature/` |
| "画论文图表" | `skills/paper-figure/` 或 `paper-figure-drawio/` |
| "编译论文 PDF" | `skills/paper-compile/` 或 `paper-compile-zh/` |
| "自动审稿" | `skills/auto-review-loop/` |

### 其他

| 用户意图 | 路由到 |
|---------|--------|
| "写课程论文/报告" | `skills/course-paper/` 或 `course-report/` |
| "写开题报告" | `skills/thesis-proposal/` |
| "写基金申请书" | `skills/grant-proposal/` |
| "写专利/软著" | `skills/patent-draft/` 或 `copyright-draft/` |
| "一句话生成项目" | `skills/grad_project/` |
| "已有资产写论文" | `skills/paper_from_assets/` |
| "合并/拆分/加密/OCR/填表单 PDF" | `skills/sci-pdf/` | 通用 PDF 工具；读取题面/论文内容用 `doc_reader.py` |
| "做简历/海报/幻灯片/小抄/格式转换" | `skills/latex-document/` | 通用 LaTeX 文档；竞赛论文写作用 `comp-paper-zh`、编译用 `comp-compile-zh` |

## 四、技能执行协议

当路由到一个技能后，按以下协议执行：

```markdown
1. 读取 skills/<name>/SKILL.md
2. 理解 SKILL.md 的：输入契约 / 执行步骤 / 输出契约 / 质量铁律
3. 按步骤执行，每步调用 tools/ 完成具体动作
4. 产出文件到 `StepAction.workspace` 指定的工作区
5. 检查点（SKILL.md 标记 has_checkpoint）→ 暂停等用户确认
6. 产出后按质量铁律自检
```

## OpenCode 项目配置

共享项目根 `D:\Desktop\数模竞赛\opencode.json` 使用 `数模专家` 作为默认 primary agent，显式扫描 `./科研工具箱/skills`，并自动加载本文件作为项目指令。四个 agent 定义位于共享项目根 `.opencode/agents/`。`subagent_depth` 固定为 1：数模专家可以派发数模审稿人、数模视觉审查或数模编辑，但子智能体不能继续派发新的子智能体。`share` 固定为 `disabled`，竞赛题目、数据和产物不会被自动共享。

修改共享根 `opencode.json`、共享根 `.opencode/agents/` 或套件 `skills/` 后，必须完全退出并重启 OpenCode Desktop；运行中的会话不会热加载这些配置。

## 五、工具链调用规范

### 检索/搜索工具（先检索，再动手，禁止闭门造车）

任何任务开始前：若涉及方案选型、工具选择、文献引用、题目背景、竞品方法、报告写作，**必须先搜索再动手**。检索到的来源与查询词必须写入步骤产物（可追溯），未检索直接动手视为违规。

| 工具 | 用途 | 调用方式 |
|------|------|---------|
| `tools/scholar_fetch.py` | 学术文献搜索（AMiner/Semantic Scholar/CrossRef/DBLP/OpenAlex 五源 fallback） | `python tools/scholar_fetch.py search "关键词" --max 5` |
| `tools/arxiv_miner.py` | arXiv + DuckDuckGo 实时检索 | `python tools/arxiv_miner.py --query "关键词"` |
| `tools/citation_checker.py` | 引用核验 | `python tools/citation_checker.py <文件>` |
| `tools/codesucker_bridge.py` | 离线软著源码发现、清洗、分页、审计与 DOCX/TXT 输出 | `python tools/codesucker_bridge.py --config <config.json> --workspace <workspace>` |
| `tools/case_fetcher.py` | 国赛真题/优秀论文搜索 | `python tools/case_fetcher.py <题目>` |
| MCP `firecrawl_search` | 通用网络搜索（方案/工具/竞品检索） | firecrawl_search(query=...) |
| MCP `github_search_repositories` / `github_search_code` | GitHub 开源方案检索（有成熟方案不重复造轮子） | github_search_repositories(query=...) |
| 内置 `webfetch` / `websearch` | 网页抓取与网络搜索 | webfetch(url=...) |

### 其他工具

| 工具 | 用途 | 调用方式 |
|------|------|---------|
| `tools/gpt_image.py` | 科研插图生成 | `python tools/gpt_image.py --prompt "..." --output fig.png` |
| `tools/reviewer_client.py` | 外部 LLM 审查 | `python tools/reviewer_client.py --prompt "..."` |
| `tools/tikz_vision_check.py` | TikZ 图自检 | `python tools/tikz_vision_check.py fig.png` |
| `tools/derive_reference_from_docx.py` | 格式派生 | `python tools/derive_reference_from_docx.py ref.docx` |
| `tools/arxiv_fetch.pyc` | arXiv 论文获取 | `python tools/arxiv_fetch.pyc "query"` |
| `tools/drawio_vision_check.pyc` | draw.io 图检查 | `python tools/drawio_vision_check.pyc fig.png` |
| `tools/paper_data_check.pyc` | 论文数据一致性 | `python tools/paper_data_check.pyc workspace/` |
| `tools/docx_precheck.pyc` | DOCX 格式预查 | `python tools/docx_precheck.pyc paper.docx` |
| `tools/fix_bare_latex_in_md.pyc` | 修复裸 LaTeX | `python tools/fix_bare_latex_in_md.pyc paper.md` |
| `tools/docx_export.pyc` | DOCX 导出 | `python tools/docx_export.pyc paper.md paper.docx` |

### 文档读取（防漏读嵌入图片，必须使用）

**任何 docx/pdf 文档读取任务，必须用 `tools/doc_reader.py`**——纯文本提取会漏读嵌入图片/截图（提交要求、格式规范、题目附图常以图片形式存在）：

```bash
python tools/doc_reader.py 作品提交说明.docx --out report.md   # 完整读取（文本+图片视觉识别）
python tools/doc_reader.py 题目.pdf --no-vision                # 仅列出图片位置（无视觉 API 时）
```

该工具自动：提取全部文本（段落/表格）→ 提取全部嵌入图片 → 用多模态视觉模型识别每张图片内容 → 输出合并报告。**禁止只用 python-docx/fitz 提取文本后直接判断文档内容。**

### 其他工具

| 工具 | 用途 | 调用方式 |
|------|------|---------|
| `tools/gpt_image.py` | 科研插图生成 | `python tools/gpt_image.py --prompt "..." --output fig.png` |
| `tools/reviewer_client.py` | 外部 LLM 审查 | `python tools/reviewer_client.py --prompt "..."` |
| `tools/tikz_vision_check.py` | TikZ 图自检 | `python tools/tikz_vision_check.py fig.png` |
| `tools/derive_reference_from_docx.py` | 格式派生 | `python tools/derive_reference_from_docx.py ref.docx` |
| `tools/arxiv_fetch.pyc` | arXiv 论文获取 | `python tools/arxiv_fetch.pyc "query"` |
| `tools/drawio_vision_check.pyc` | draw.io 图检查 | `python tools/drawio_vision_check.pyc fig.png` |
| `tools/paper_data_check.pyc` | 论文数据一致性 | `python tools/paper_data_check.pyc workspace/` |
| `tools/docx_precheck.pyc` | DOCX 格式预查 | `python tools/docx_precheck.pyc paper.docx` |
| `tools/fix_bare_latex_in_md.pyc` | 修复裸 LaTeX | `python tools/fix_bare_latex_in_md.pyc paper.md` |

## 六、质量门禁（P4 核心）

每个技能产出后，用以下门禁检查质量（`engine/quality_gates.py` 实现）：

### 最小大小门禁（_STEP_MIN_SIZE）
每个技能产出文件必须 ≥ 指定大小，否则视为"敷衍产出"：

| 技能 | 最小大小 |
|------|---------|
| comp-prob-analysis | 1500 字节 |
| comp-modeling | 2000 字节 |
| comp-code | 1000 字节 |
| comp-review | 40 字节 |
| comp-paper-zh | 10000 字节 |
| comp-paper-en | 10000 字节 |
| paper-write | 15000 字节 |
| paper-write-zh | 15000 字节 |

### 伴随文件门禁（_STEP_REQUIRED_COMPANIONS）
某些技能必须产出指定伴随文件：

| 技能 | 必需伴随文件 |
|------|------------|
| comp-code | `code/main.py`, `figures/all_results.json` |

### 论文页数门禁（`check_paper_pages`）
按 `engine/modex-core/comp_rules.json` 中竞赛明确规定的总页数上限检查 PDF。正文最低页数仅在规则明确给出且实现了专用正文页数门禁时检查；不得把总页数上限误作正文页数下限。

### 图表健康门禁（_check_figures_step_health）
检查图表是否生成、格式正确、无重叠/截断。

## 七、多角色 Agent（P5 核心）

系统支持三个角色协作：

| 角色 | 工具 | 用途 |
|------|------|------|
| **executor**（执行者） | 整套 skills | 完成主要工作（建模/写作/代码） |
| **reviewer**（审稿人） | `tools/reviewer_client.py` | 审查产出质量，找问题 |
| **editor**（编辑人） | `tools/reviewer_client.py` + 润色 skills | 根据审查意见润色修改 |

**推荐流程**：executor 产出 → reviewer 审查 → editor 修改 → reviewer 复审（loop-until-clean，最多 3 轮）

## 八、视觉能力（P6）

系统支持用 Vision LLM 分析图片（检查图表质量、识别内容）：

方式 1：`tools/tikz_vision_check.py`（TikZ 图专用）
方式 2：`tools/drawio_vision_check.pyc`（draw.io 图专用）
方式 3：`tools/data_fig_vision_check.pyc`（数据图专用）

## 九、入口提示词

当用户只给一个需求时，用以下框架启动：

```
用户需求：{需求}

我将按以下流程处理：
1. 路由到技能：{技能名}
2. 读取技能说明
3. 调用工具执行
4. 产出文件到 {工作区}
5. 质量门禁检查
6. 展示结果

现在开始，请提供 {需要的输入}（如题目/数据/要求）
```

## 十、生产工作流引擎

OpenCode Desktop 是技能执行者；`engine` 只负责持久化编排、检查点、产物证据和质量门禁。它不启动第二个 OpenCode 进程，也不会把未执行的步骤标记为完成。

```powershell
# 仅用于开发/诊断：检查套件 runtime 或系统 PATH 中的可选能力
python -m engine.workflow_cli caps

# 创建持久化工作流；状态库默认保存到 .engine/workflow.sqlite
python -m engine.workflow_cli start --template comp_cumcm --workspace workspaces\cumcm-demo --params '{"language":"zh"}'
```

上述 `workflow_cli` 命令不是 OpenCode Desktop 的启动命令，也不是数模智能体的运行前提。实际执行者始终是 OpenCode Desktop 中加载的“数模专家”；系统不依赖系统 PATH 中存在 `opencode` CLI。桌面端配置、agent 或技能变更后，关闭并重新启动 OpenCode Desktop，再在桌面会话中验证 agent 和技能发现。

每个工作流的步骤、检查点和运行事件写入 SQLite。Desktop Agent 取得真实产物和执行证据后，才调用 `complete_step()` 推进步骤。Agnes/商汤配置仅由具体工具脚本使用，不参与流程调度。
