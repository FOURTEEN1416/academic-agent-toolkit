# 科研工具箱 — 全学术 Agent 系统（原：数学建模全流程套件）

> 这是一套**完整科研工具箱**（全学术 Agent 工具箱，6 大能力域：数模竞赛、学术论文、文献与研究、
> 课程与研究材料、知识产权材料、图表与文档生产），双宿主：**OpenCode 桌面版**（正式宿主）与
> **ZCode**（2026-09-09 起升级为赛时主控宿主，L1 审计经 hook 机制提供等价实现）。
> 数模竞赛（CUMCM）是验证场景之一，不是产品边界。
> **主控 = 当前宿主的 Agent**：OpenCode Desktop 或 ZCode 中承担主控的 agent（你）直接读取技能、
> 调用工具、执行全部工作。同一时刻只有一个宿主主控，不并行双控。
> 引擎（engine/）只负责状态记忆、编排、质量门禁和审计，绝不代执行。
> 本系统完全独立，不依赖任何其他商业软件。
>
> **宿主兼容（2026-08-20 起 · 2026-09-09 ZCode 升级主控）**：ZCode 通过仓库根 `AGENTS.md` +
> `.zcode/`（技能联结 + `hooks` 审计拦截）接入同一套技能库与引擎（见根 AGENTS.md 宿主支持矩阵）。
> ZCode L1 拦截式审计由 `hooks/zcode_audit_l1.py` 实现（PreToolUse/PostToolUse 写
> `operations.jsonl`，与 OpenCode 插件同格式，并含 `git add .` 级拦截示例）；
> 其余规则（引擎只编排、complete_step 回报、门禁）在两个宿主下完全一致。

---

## 定位（重要）

**执行者 = 当前宿主（OpenCode Desktop / ZCode）中承担主控的 Agent（你）。**
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
| **L1 拦截式** | OpenCode plugin（`.opencode/plugins/audit-trail.ts` + 官方 `opencode-logger`）；ZCode 等价：`hooks/zcode_audit_l1.py`（经 `.zcode/config.json` 注册 PreToolUse/PostToolUse/Failure；**fail-open 铁律：hook 自身故障一律 stderr 警告+exit 0 放行，exit 2 唯一来源是规则拦截且必留痕**——2026-09-09 锁死事故后固化，exit 2 与 python 找不到脚本的退出码撞车是事故根因） | 每次工具调用（bash 命令全文/编辑路径/skill 名/task 描述）、文件编辑、会话、权限请求 | 共享根 `.engine/audit/operations.jsonl`（ZCode 同文件）+ OpenCode 另有 `log.jsonl` | ❌ 不可绕过（宿主钩子层，agent 无法跳过） |
| **L2 编排式** | `WorkflowRunner` 引擎侧写入 | workflow 启动/步骤完成（含声明命令）/checkpoint 批准 | 同一 `.engine/audit/operations.jsonl` | ⚠️ 仅当走 runner 流程时 |
| **L3 申报式** | `complete_step()` 的 execution_evidence | skill 哈希、声明命令、输入输出产物、产物 manifest | 工作区 `.engine/evidence/*.json` | ⚠️ 依赖 agent 主动申报 |

> ⚠️ **审计日志卫生规则（2026-09-19 治理收口）**：`operations.jsonl` **不得**记录"该文件自身被写入"的 file watcher 事件——此类自指记录会形成回声式增殖。实测证据：该文件 353,968 行中 **349,146 行（98.6%）**即此类噪声，真实操作记录仅 4,822 行（`tool_call`/`tool_result`/`engine_event`/`file_edit` 等）。历史噪声已于 2026-09-19 清理（199.5 MB → 6.8 MB，原文件 gzip 留档 `.engine/audit/_archive_noise_filtered_20260919/`）。噪声集中在 2026-08-18 / 08-19 / 09-11 三次爆发，09-12 起为 0。**若宿主再次产生此类事件**，应在写入侧过滤（判据：`properties.file` 指向审计日志自身），否则审计可用性与遍历性能都会被噪声拖垮。

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
├── tools/                 ← 工具链（65 个 .py 脚本 + 16 个 .pyc 字节码分发件（3.11 编译版本锁定，调用一律用同名 .py 真源）；2026-09-19 实测：tools/ 顶层 glob *.py=65、*.pyc=16）
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
6. **命名的工程原则**（可直接引用，全部有落地机制）：**TOOL_GAP**（工具够不到世界就报"状态未知"，绝不伪造通过）/ **三振升级**（同一思路失败 3 次必须换路或上报）/ **决策点≠批准** / **无证据＝未执行** / **反合理化优先落到岗位级**——见 `skills/_utils/anti_rationalization.md` §四

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
| "不知道用什么图/这数据怎么画" | `skills/scipilot-figure-skill/`（论证驱动选图+EDA+错误拦截） |
| "CNS/Nature/Cell 级投稿图" | `skills/academic-figure-skill/`（期刊规格+图集+四轮 QA） |
| "照着这张图复现" | `skills/plot-from-image/`（字体/取色/比例测量→复现代码） |
| "用 XX 论文那种风格画" | `skills/plot-from-data/`（8 种顶会风格模板） |
| "重建这张 Visio 图" | `skills/visio-image-rebuilder/`（vsdx 原生形状重建） |
| "论文方法框架图多方案" | `skills/paper-framework-figure-studio-pro/`（候选草案共设计） |
| "找参考图再动手" | `skills/agent-figure-gallery/`（图库检索+偏好选择） |
| "编译论文 PDF" | `skills/paper-compile/` 或 `paper-compile-zh/` |
| "自动审稿" | `skills/auto-review-loop/` |

### 其他

| 用户意图 | 路由到 |
|---------|--------|
| "写课程论文/报告" | `skills/course-paper/` 或 `course-report/` |
| "写开题报告" | `skills/thesis-proposal/` |
| "写基金申请书" | `skills/grant-proposal/` |
| "写专利/软著" | `skills/patent-draft/` 或 `copyright-draft/` |
| "一句话生成项目（毕业设计/软件）" | 管线模板 `grad_project`：dev-requirement → dev-design → dev-code → dev-selfcheck → dev-report |
| "已有资产写论文" | 管线模板 `paper_from_assets`：assets-inventory → paper-plan → paper-analysis → paper-figure(-drawio) → paper-write → paper-compile |
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
7. 若发现绑定技能（StepAction.skill_binding）→ 先读取其 SKILL.md 并把命令记入 evidence
```

**动手前扫一眼反合理化表**：`skills/_utils/anti_rationalization.md` —— 12 条"跳过步骤的常见借口"
及其反驳（每条带本项目真实事故实证与机器判据）。写审核结论前、宣布"完成"前命中任一行，
按表内"正确动作"列执行。该表已作为资产挂在 step7（逻辑复核）与 step14（交付审计）上。

## OpenCode 项目配置

共享项目根为 **git clone 后的仓库根**（本检出目录名 `学术工作流`；公开仓以你本地 clone 路径为准，勿写本机绝对路径）。根 `opencode.json` 使用 `数模专家` 作为默认 primary agent，显式扫描 `./科研工具箱/skills`，并自动加载本文件作为项目指令。四个 agent 定义位于共享项目根 `.opencode/agents/`。`subagent_depth` 固定为 1：数模专家可以派发数模审稿人、数模视觉审查或数模编辑，但子智能体不能继续派发新的子智能体。`share` 固定为 `disabled`，竞赛题目、数据和产物不会被自动共享。

**MCP 路径覆盖（PUBLIC 仓）**：tracked `opencode.json` / `.zcode/config.json` 的 docsearch MCP 使用可移植占位符（`${DOCSEARCH_MCP_SERVER}` / `${DOCSEARCH_ROOTS}`）。若 MCP 装在宿主用户目录，操作员须在**本地未提交配置**中写入本机绝对路径；勿把 `C:\Users\...` 或过期项目根写回 tracked 文件。

修改共享根 `opencode.json`、共享根 `.opencode/agents/` 或套件 `skills/` 后，必须完全退出并重启 OpenCode Desktop；运行中的会话不会热加载这些配置。

## 安全注意（pyc / 密钥 / 路径）

- `tools/*.pyc` 为受控分发件，公开仓**不可源码审查**；审查优先读同名 `.py`。勿在未确认消费者前删除 pyc。
- `tools/pyc_loader.py` 仅将**已识别 vision provider** 的 API key 注入 `.pyc` 子进程 env（非完整 auth.json）；属本地密钥注入面，禁止写入日志/manifest。
- `.env` 保持 gitignored、不入库不入发布包。

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
| `tools/arxiv_fetch.py` | arXiv 论文获取 | `python tools/arxiv_fetch.py "query"` |
| `tools/drawio_vision_check.py` | draw.io 图检查 | `python tools/drawio_vision_check.py fig.png` |
| `tools/paper_data_check.py` | 论文数据一致性 | `python tools/paper_data_check.py workspace/` |
| `tools/docx_precheck.py` | DOCX 格式预查 | `python tools/docx_precheck.py paper.docx` |
| `tools/fix_bare_latex_in_md.py` | 修复裸 LaTeX | `python tools/fix_bare_latex_in_md.py paper.md` |
| `tools/docx_export.py` | DOCX 导出 | `python tools/docx_export.py paper.md paper.docx` |
| `tools/check_asset_utilization.py` | 资产利用率审计（申报账本/技能地图对账/模板资产在位三合一） | `python tools/check_asset_utilization.py [--json] [--strict]` |
| `tools/contest_lessons_check.py` | 实战经验库机检（schema/**强制点在位**/JSON↔MD 双向一致/强制点过度集中告警） | `python tools/contest_lessons_check.py --strict` |
| `tools/skill_trigger_audit.py` | 技能触发条件与能力边界（frontmatter/触发信号/**路由歧义**/主链契约段/目录与地图对账）+ `--route` 词法路由诊断 | `python tools/skill_trigger_audit.py --strict` |
| `tools/context_budget_check.py` | **常驻上下文预算**（技能 frontmatter 是每会话常驻的：预算上限 + 单条上限 + 六类描述污染判据） | `python tools/context_budget_check.py --strict` |
| `tools/build_skill_index.py` | **技能分层常驻**：派生 core/ondemand 分层、生成路由索引（按需层完整描述无损保存）、双向同步描述 | `python tools/build_skill_index.py [--check\|--emit\|--compact]` |
| `tools/project_health_check.py` | **统一健康检查 + 文档漂移检测**（汇总 7 个检查件为 PASS/FAIL/DEGRADED；比对实测测试数与 5 处权威文档基线） | `python tools/project_health_check.py --strict` |

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
方式 2：`tools/drawio_vision_check.py`（draw.io 图专用）
方式 3：`tools/data_fig_vision_check.py`（数据图专用）

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

# 取下一步（返回 skill_name/skill_path/产出文件/checkpoint 语义）
python -m engine.workflow_cli next --wf <workflow_id>

# 完成步骤：execution_evidence 有严格 schema（2026-09-09 赛前实测固化的合规样例，
# 字段缺一/类型错/sha 不符/描述性命令/体积不足都会被逐层拒绝，步骤置 failed 需重开流程）：
#   schema_version 必须是整数 1；commands 必须是非空对象数组且 returncode 为整数 0；
#   outputs 必须与 --artifacts 完全一致；skill_sha256 必须等于该步 SKILL.md 的 SHA-256；
#   产出文件须过 quality gate（如 comp-prob-analysis 的 PROBLEM_ANALYSIS.md ≥1500 字节）；
#   companion_skills 申报（2026-09-11 C1 闸）：步骤带 companion_skills 时必填，used/skipped
#   恰好覆盖推荐清单（skipped 须给非空理由）——强制申报不强制使用，缺申报=步骤失败。
#   used 技能须在命令/产物路径中有真实使用痕迹（技能名或路径出现在命令/产物/输入中）。
#   推荐清单以 next 返回的 StepAction 为准；2026-09-12 修剪后 14 步共 11 个推荐槽位
#   （普遍 0-2 个/步，地图 CONTEST_SKILL_MAP §二），清单为空的步骤可省略 companion_skills 字段。
python -m engine.workflow_cli complete --wf <workflow_id> --ok true --artifacts "PROBLEM_ANALYSIS.md" --evidence '{
  "schema_version": 1,
  "agent": "opencode-desktop",
  "step_id": "<next 返回的 step_id>",
  "skill_name": "comp-prob-analysis",
  "skill_sha256": "<python -c \"import hashlib;print(hashlib.sha256(open(r'"'"'skills/comp-prob-analysis/SKILL.md'"'"','"'"'rb'"'"').read()).hexdigest())\">",
  "commands": [{"command": "python scripts/build_analysis.py", "returncode": 0, "cwd": "."}],
  "inputs": [],
  "outputs": ["PROBLEM_ANALYSIS.md"],
  "companion_skills": {"used": ["problem-analysis"], "skipped": []}
}'
```

上述 `workflow_cli` 命令不是任何宿主的启动命令，也不是数模智能体的运行前提。实际执行者始终是**当前宿主**（OpenCode Desktop 或 ZCode）中承担主控的 Agent；系统不依赖系统 PATH 中存在 `opencode` CLI。OpenCode 桌面端配置、agent 或技能变更后，关闭并重新启动桌面端再验证；ZCode 下变更后重开会话即可（技能经 `.zcode/skills` 联结自动发现，hook 配置改动需重启会话）。**换机部署仅一步**：重建 `.zcode/skills` 联结即可——hook 命令是 `python -c` 内联引导器（先探测项目根 env 变量，再从 cwd 逐级上溯定位 `科研工具箱/hooks/zcode_audit_l1.py`；定位/执行失败一律 stderr 警告+exit 0 放行，exit 2 唯一来源=治理规则命中），随仓分发免改路径。历史教训（2026-09-09/09-10 三次全工具锁死定案）：相对路径与 `${ZCODE_PROJECT_DIR}` 变量式写法在 cwd 漂移下都会让 python 在脚本运行前以退出码 2（=deny）死去——**勿回退到任何路径/变量式 hook 写法**（契约测试 test_zcode_config_uses_inline_bootstrap 把守）。

**技能强制绑定（P4，2026-09-19 落地）——"步骤不会强制调用 skills"的机制层修复**：每个步骤在模板里显式声明 `metadata.skill_binding`（全库 279 个步骤均已声明）：

| 字段 | 语义 | 缺失后果 |
|------|------|---------|
| `main_required`（默认 true） | 本步**主技能契约必须留真实读取痕迹**——证据的命令/输入中须出现 `skills/<main>/SKILL.md`（或技能名）。只填 `skill_sha256` 不算 | 步骤 FAILED（"skill_sha256 只能证明文件被读取过，不能证明契约被遵守"） |
| `main` | 覆盖默认主技能（默认 = `step.skill_name`） | — |
| `mandatory` | 本步**必用**的辅助技能：不得申报 `skipped`，须申报 `used` 且**必须有命令级痕迹**（只出现在产物/输入路径里不算） | 步骤 FAILED |

三层保障：**①执行层**——`complete_step` 硬校验（`engine/workflow_runner.py`），未声明 `skill_binding` 的步骤零影响（向后兼容）；**②审计层**——`engine/audit_store.verify_skill_bindings()` 把声明与 **L1 实际调用记录**（`skill` 工具调用 / 对 SKILL.md 的 `read`）对账，L1 缺席时**如实降级为 `unavailable`**（不判通过），结论进入 `AUDIT_REPORT.json` 的 `gate_outcomes.skill_binding` 与 `skill_binding_detail`；**③指令层**——`StepAction.execution_instructions()` 把绑定要求直接渲染给 agent。
`mandatory` **有意只用一处**（comp_cumcm step5 → `paper-figure-palette`）：把辅助技能一律设为必用会制造假失败（例如无数值推导的题目无法合法使用 `sci-sympy`），其余推荐位维持"申报即可跳过、跳过须给理由"的 C1 闸。测试护航：`tests/test_skill_binding.py`（17 项，含向后兼容与 unavailable 降级）。

**竞赛解题入口铁律（2026-09-11 定稿，产品灵魂条款）**：CUMCM 等竞赛的解题任务**一律经工作流引擎启动**（`workflow_cli start --template comp_cumcm` → 按 `next` 返回的 StepAction 逐步执行）后再使用技能——工作流承载步骤状态、检查点批准、质量门禁与三层审计留痕，绕开引擎直接做题会丢失全部审计链（ZCode 入口：`/comp-start <题号>` 斜杠命令，见 `.zcode/commands/comp-start.md`）。技能的三层发现机制：①引擎 StepAction 显式给出 skill_path（主通道，强制发现）**并随步给出 `companion_skills` 本步推荐辅助技能**（2026-09-11 起，全库 261 技能分类账见 `CONTEST_SKILL_MAP.md`（2026-09-19 实测：**263** 技能目录 − `_utils` − `shared-scripts` = 261 含 SKILL.md；当日新增 `contest-retrospective`）——按需加载 1-3 个，禁止"无人知晓"的闲置技能）；②主控 AGENTS.md 路由表（本文件，宿主自动注入会话）；③技能 frontmatter description 触发词（ZCode 技能清单）。非竞赛任务（文献/写作/绘图等）可自由按路由表加载技能，不受此铁律约束。**非技能资产同步暴露（2026-09-12 C2 资产机制）**：StepAction 另带 `assets` 字段按步给出数据/参考论文/工具脚本/参考图集指针（仓库根相对路径，见 `engine/modex-core/templates.json` 各步 metadata）——用前留痕、完成时随 evidence 申报 `assets` used/skipped（与 companion_skills 同构，运行中旧工作流不受影响）；利用率账本/地图对账/资产在位三合一审计：`python tools/check_asset_utilization.py`。

每个工作流的步骤、检查点和运行事件写入 SQLite。主控 Agent 取得真实产物和执行证据后，才调用 `complete_step()` 推进步骤。**模型配置仓库不预设**（2026-09-09 裁定）：审稿/视觉模型比赛时填入 `engine/modex-core/contest_models.json` 配置槽（或宿主 agent 配置），仅供具体工具脚本与 strict 门禁比对使用，不参与流程调度。
