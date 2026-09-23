# academic-toolkit — 全学术 Agent 系统（宿主无关）

> 这是一套**完整academic-toolkit**（全学术 Agent 工具箱，6 大能力域：数模竞赛、学术论文、文献与研究、
> 课程与研究材料、知识产权材料、图表与文档生产）。
> 数模竞赛（CUMCM）是验证场景之一，不是产品边界。
> **主控 = 当前驱动本项目的 Agent**：任意能读文件、能调用 `python -m engine.workflow_cli`
> 的智能体（Claude Code / Cursor / Gemini CLI / MiMo Desktop / OpenCode / ZCode / 自写脚本）。
> 同一时刻只有一个主控 Agent，不并行双控。
> 引擎（engine/）只负责状态记忆、编排、质量门禁和审计，绝不代执行。
> 本系统完全独立，不依赖任何特定商业宿主。
>
> **宿主适配（可选，非驱动前提）**：OpenCode（`opencode.json`，subagent 角色内联）与
> ZCode（`.zcode/skills` 本地联结）保留为可选适配器。
> 无适配器时协议与 L2/L3 审计完整可用。

---

## 定位（重要）

**执行者 = 当前驱动本项目的 Agent（你）。**
引擎不是执行者，只是"记忆和编排"：
- `workflow_store` — 记录谁做了什么、做到哪、卡在哪（SQLite）
- `workflow_runner` — 告诉你下一步做什么（next_action）
- `quality_gates` / `run_logger` / `audit_store` — 验收标准 + 审计记录 + 操作审计报告

**不存在「调用另一个 agent runtime」的逻辑。** 你读到 `StepAction` 后直接执行技能，
完成后调用 `complete_step` 回报结果。

## 自举与自适应（2026-09-20 泛化）

| 能力 | 命令/技能 |
|------|-----------|
| 驱动契约 | `python -m engine.workflow_cli boot` |
| 能力探测 | `python -m engine.workflow_cli probe` |
| 工具/技能铸造 | `python -m engine.workflow_cli forge --tool/--skill/--adapter` |
| 自举技能 | `skills/agent-bootstrap/` |
| 铸造技能 | `skills/tool-forge/` |

**TOOL_GAP → 铸造**：探测到缺工具/缺技能时，按 tool-forge 协议生成骨架并登记 catalog；
环境类缺口（缺包/缺 CLI）不伪造安装，按 probe hint 配置或改用替代路径。

## 审计体系（三层）

| 层 | 机制 | 记录内容 | 写入位置 | 可否绕过 |
|---|------|---------|---------|---------|
| **L1 拦截式** | **可选**宿主 hook/插件（OpenCode plugin；ZCode `hooks/zcode_audit_l1.py`）。无宿主 hook 时记为 `unavailable`，不阻断 | 工具调用/文件编辑等 | `.engine/audit/operations.jsonl` | 宿主提供时不可绕过；缺席时如实降级 |
| **L2 编排式** | `WorkflowRunner` 引擎侧写入 | workflow 启动/步骤完成/checkpoint | 同一 `operations.jsonl` | 仅当走 runner 流程时 |
| **L3 申报式** | `complete_step()` 的 execution_evidence | skill 哈希、命令、产物 manifest | 工作区 `.engine/evidence/*.json` | 依赖 agent 主动申报（硬门禁） |

> **审计日志卫生**：`operations.jsonl` 不得记录该文件自身的写入事件（历史噪声曾达 98.6%）。

**防绕过检测**：`python -m engine.workflow_cli audit --workspace <工作区>` 生成
`OPERATION_AUDIT_REPORT.json`（操作审计，不覆盖竞赛交付的 `AUDIT_REPORT.json`）。

## 一、系统架构

```
仓库根/
├── AGENTS.md              ← 宿主无关驱动协议入口
├── academic-toolkit/
│   ├── AGENTS.md          ← 你在这里（路由 + 门禁 + 引擎用法）
│   ├── skills/            ← 技能库（每个技能一个 SKILL.md）
│   ├── tools/             ← 工具链（独立可执行脚本）
│   ├── engine/            ← 状态库 + 编排 + 门禁 + 审计（不执行）
│   ├── data/              ← 参考数据
│   └── .env               ← 本地 API 配置（gitignored）
└── capabilities/catalog.json ← 能力目录（技能全量映射）
```

## 二、核心原则

1. **技能即知识**：每个 `skills/<name>/SKILL.md` 描述"如何做一件事"
2. **Agent 即执行者**：当前 Agent 读取 SKILL.md 后自主执行，无需外部调度器
3. **工具即手脚**：`tools/*.py|pyc` 是独立可执行脚本；缺口可 forge
4. **门禁即质量**：每步产出后检查质量，不达标则重做
5. **Agent 定角色**：executor / reviewer / editor
6. **工程原则**：**TOOL_GAP** / **三振升级** / **决策点≠批准** / **无证据＝未执行** —— 见 `skills/_utils/anti_rationalization.md`

## 三、入口路由规则（P3 核心）

### 数模竞赛

| 用户意图 | 路由到 | 自动接续 |
|---------|--------|---------|
| "我要参加国赛/美赛/CUMCM" | `workflow_cli start --template comp_cumcm` | 完整 14 步流程 |
| "帮我分析这个题目" | `skills/comp-prob-analysis/` | → comp-modeling |
| "建立数学模型" | `skills/comp-modeling/` | → comp-code |
| "写求解代码" | `skills/comp-code/` | → comp-review |
| "写竞赛论文" | `skills/comp-paper-zh/` 或 `comp-paper-en/` | → comp-compile |
| "审查我的论文" | `skills/comp-review/` | loop-until-clean |
| "统计建模/数分" | `skills/comp-stats-topic/` | → comp-code |
| "竞赛主链其余步骤" | CONTEST_SKILL_MAP §一 / 模板 `comp_cumcm` | 完整 14 步流程 |

**快速模式开关（可选，竞赛项目级）**：在竞赛项目工作区根的 `AGENTS.md`（项目宪法）中写入一行
`MH_FAST_MODE=1`，12 个主链技能（comp-prob-analysis / comp-modeling / comp-code / comp-review /
paper-figure / paper-figure-drawio / paper-figure-html / nature-figure / comp-paper-zh / comp-paper-en
及两 docx 变体）的流程开头即自动进入快速模式——跳过可选重步骤、省 AI 额度；
确定性闸（logic_audit / cross_problem_check 等）仍兜底。不写则默认全量质量路径。
各技能内以 `grep -q 'MH_FAST_MODE=1' AGENTS.md` 探测（宿主中性，`test_host_neutral_ratchet.py` 钉住）。

### 科研论文

| 用户意图 | 路由到 |
|---------|--------|
| "我要做科研/写论文" | `skills/paper-writing/` 或 `paper-write-zh/` |
| "做文献综述" | `skills/literature-review/` |
| "找研究方向" | `skills/idea-discovery/` |
| "写中文 LaTeX 论文" | `skills/paper-write-zh/` |
| "写 Nature 论文" | `skills/paper-write-nature/` |
| "画论文图表" | `skills/paper-figure/` 或 `paper-figure-drawio/` |
| "不知道用什么图/这数据怎么画" | `skills/scipilot-figure-skill/` |
| "CNS/Nature/Cell 级投稿图" | `skills/academic-figure-skill/` |
| "照着这张图复现" | `skills/plot-from-image/` |
| "用 XX 论文那种风格画" | `skills/plot-from-data/` |
| "重建这张 Visio 图" | `skills/visio-image-rebuilder/` |
| "用 Origin 画可编辑图/导师要 OPJU/材料光谱专用图（XPS/XRD/FTIR/NMR/DSC/EIS）" | `skills/editaplot/`（需本机 Origin 2021+，无则如实降级） |
| "没装 Origin 也要出版级数据图/CSV 可复现出图（matplotlib 路线）" | `skills/editaplot-lite/`（继承 editaplot 纪律：propose→逐列确认→render，PNG+PDF+SVG+校验报告） |
| "论文方法框架图多方案" | `skills/paper-framework-figure-studio-pro/` |
| "找参考图再动手" | `skills/agent-figure-gallery/` |
| "编译论文 PDF" | `skills/paper-compile/` 或 `paper-compile-zh/` |
| "自动审稿" | `skills/auto-review-loop/` |
| "对照优秀论文改进/论文复盘" | `skills/oral-paper-skill/`（与 anti-defensive-writing 删-hedge 互补，修订轮先后用） |

### 其他

| 用户意图 | 路由到 |
|---------|--------|
| "写课程论文/报告" | `skills/course-paper/` 或 `course-report/` |
| "写开题报告" | `skills/thesis-proposal/` |
| "写基金申请书" | `skills/grant-proposal/` |
| "写专利/软著" | `skills/patent-draft/` 或 `copyright-draft/` |
| "一句话生成项目" | 管线模板 `grad_project` |
| "已有资产写论文" | 管线模板 `paper_from_assets` |
| "PDF 合并/拆分/OCR/填表（非竞赛域）" | `skills/sci-pdf/` |
| "Markdown 论文导出 Word" | `skills/docx-export/` |
| "写返修回复/审稿答复" | `skills/rebuttal/` |
| "做会议演讲幻灯/逐页 PPT" | `skills/paper-slides/`（单页海报用 `paper-poster/`） |
| "分析实验结果/对比解读" | `skills/analyze-results/` |
| "赛后复盘/经验沉淀" | `skills/contest-retrospective/` |
| "简历/海报/幻灯片/格式转换" | `skills/latex-document/` |
| **"如何驱动本项目/自举"** | **`skills/agent-bootstrap/`** |
| **"缺工具/造工具/自适应"** | **`skills/tool-forge/`** |

## 四、技能执行协议

```markdown
1. 读取 skills/<name>/SKILL.md
2. 理解：输入契约 / 执行步骤 / 输出契约 / 质量铁律
3. 按步骤执行，每步调用 tools/（缺口则 forge）
4. 产出文件到 StepAction.workspace 或用户指定目录
5. 检查点（has_checkpoint）→ 暂停等用户确认
6. 产出后按质量铁律自检
7. 若有 skill_binding → 先读绑定技能并把命令记入 evidence
```

**动手前扫一眼**：`skills/_utils/anti_rationalization.md`

**审稿/评审类步骤**：凡技能要求外部审稿 API（`reviewer_client.py` 等），一律按统一
《独立评审操作手册》`skills/_utils/independent_review_manual.md` 执行——评审任务卡 →
独立上下文评审（独立子代理/会话/窗口/另一模型均可）→ 缺席降级自审。零 APIKey 零网络。

## 可选宿主配置（非协议前提）

OpenCode：根 `opencode.json` 扫描 `./academic-toolkit/skills`，加载本文件为指令；
agent 定义内联于 `opencode.json`。变更后需重启 OpenCode。

MCP：tracked 配置用占位符 `${DOCSEARCH_MCP_SERVER}` / `${DOCSEARCH_ROOTS}`；
本机绝对路径放未提交本地覆盖。

## 安全注意

- `tools/*.pyc` 审查读同名 `.py`；`pyc_loader.py` 只注入 vision provider 所需 env
- `.env` gitignored，不入库
- `python tools/secret_scan.py --strict` 扫 tracked 面

## 五、工具链调用规范

### 检索/搜索（先检索，再动手）

| 工具 | 用途 | 调用方式 |
|------|------|---------|
| `tools/scholar_fetch.py` | 学术文献五源 fallback | `python tools/scholar_fetch.py search "关键词"` |
| `tools/arxiv_miner.py` | arXiv + DDG | `python tools/arxiv_miner.py --query "..."` |
| `tools/citation_checker.py` | 引用核验 | `python tools/citation_checker.py <文件>` |
| `tools/case_fetcher.py` | 国赛真题 | `python tools/case_fetcher.py <题目>` |
| 宿主 webfetch/websearch | 网页与网络搜索 | 若宿主提供 |

### 文档读取（防漏读嵌入图片）

```bash
python tools/doc_reader.py 作品提交说明.docx --out report.md
python tools/doc_reader.py 题目.pdf --no-vision
```

### 驱动与治理

| 工具 | 用途 | 调用方式 |
|------|------|---------|
| `engine.workflow_cli boot/probe/forge` | 协议/探测/铸造 | 见上文 |
| `tools/gpt_image.py` | 科研插图 | `python tools/gpt_image.py --prompt "..." --output fig.png` |
| `tools/reviewer_client.py` | 外部 LLM 审查 | `python tools/reviewer_client.py --prompt "..."` |
| `tools/project_health_check.py` | 统一健康检查 | `python tools/project_health_check.py --strict` |
| `tools/secret_scan.py` | 密钥/路径卫生 | `python tools/secret_scan.py --strict` |
| `tools/build_skill_index.py` | 技能分层索引 | `python tools/build_skill_index.py [--check\|--emit]` |
| `tools/check_asset_utilization.py` | 资产/地图对账 | `python tools/check_asset_utilization.py [--strict]` |

（其余门禁与图表工具见历史版本全文；能力以 skills/tools 实存为准。）

## 六、质量门禁（P4 核心）

`engine/quality_gates.py`：最小大小 / 伴随文件 / 论文页数 / 图表健康 / named gates。
模型配置解析（宿主中立）：contest_models.json → agents/adapters/*/models.json → 可选宿主 agent 目录。

| 技能 | 最小大小 |
|------|---------|
| comp-prob-analysis | 1500 字节 |
| comp-modeling | 2000 字节 |
| comp-code | 1000 字节 |
| comp-review | 40 字节 |
| comp-paper-zh / en | 10000 字节 |
| paper-write / paper-write-zh | 15000 字节 |

伴随文件示例：comp-code 必须产出 `code/main.py`, `figures/all_results.json`。

## 七、多角色 Agent

| 角色 | 方式 | 用途 |
|------|------|------|
| **executor** | 整套 skills | 建模/写作/代码 |
| **reviewer** | `tools/reviewer_client.py` 或宿主子智能体 | 审查产出 |
| **editor** | 润色 skills | 按审查意见修改 |

流程：executor → reviewer → editor → reviewer（最多 3 轮）。

## 八、视觉能力

`tools/tikz_vision_check.py` / `drawio_vision_check.py` / `data_fig_vision_check.py`；
宿主开不出独立视觉窗口时走人工复核降级路径（见 quality_gates 人工复核校验）。

## 九、入口提示词

```
用户需求：{需求}

我将按以下流程处理：
1. 读协议并 probe（若尚未自举）
2. 路由到技能：{技能名} 或 workflow template
3. 读取技能说明
4. 调用工具执行（缺口则 forge）
5. 产出文件到 {工作区}
6. 质量门禁检查
7. complete_step + evidence（agent={我的标识}）

现在开始，请提供 {需要的输入}
```

## 十、生产工作流引擎

引擎只负责持久化编排、检查点、产物证据和质量门禁。它不启动第二个 Agent 进程，
也不会把未执行的步骤标记为完成。

```powershell
cd academic-toolkit
python -m engine.workflow_cli boot
python -m engine.workflow_cli probe
python -m engine.workflow_cli caps
python -m engine.workflow_cli start --template comp_cumcm --workspace workspaces\cumcm-demo --params '{"language":"zh","agent":"acat-agent"}'
python -m engine.workflow_cli next --wf <workflow_id>
python -m engine.workflow_cli complete --wf <workflow_id> --ok true --artifacts "PROBLEM_ANALYSIS.md" --evidence '{
  "schema_version": 1,
  "agent": "acat-agent",
  "step_id": "<next 返回的 step_id>",
  "skill_name": "comp-prob-analysis",
  "skill_sha256": "<该步 SKILL.md 的 SHA-256>",
  "commands": [{"command": "python scripts/build_analysis.py", "returncode": 0, "cwd": "."}],
  "inputs": [],
  "outputs": ["PROBLEM_ANALYSIS.md"],
  "companion_skills": {"used": ["problem-analysis"], "skipped": []}
}'
```

evidence.agent 为**自由非空字符串**（你的工具名）；schema/哈希/命令/门禁校验不变。

**技能强制绑定（P4）**：模板 `metadata.skill_binding`；`main_required` 须留真实读取痕迹；
`mandatory` 必用且须命令级痕迹。L1 缺席时审计层 `unavailable` 降级，不判通过。

**竞赛解题入口**：CUMCM 等解题任务**一律经工作流引擎启动**后再使用技能——
绕开会丢失审计链。非竞赛任务可按路由表自由加载技能。

**模型配置仓库不预设**：填 `engine/modex-core/contest_models.json` 或
`agents/adapters/*/models.json`，仅供工具脚本与 strict 门禁比对。
