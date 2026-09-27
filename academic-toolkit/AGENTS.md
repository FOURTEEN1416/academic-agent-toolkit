# academic-toolkit — 全学术 Agent 系统（宿主无关）

**主控 = 当前驱动本项目的 Agent**。同一时刻只有一个主控；不存在「调用另一个 agent runtime」的逻辑。
本仓库服务六大领域：数模竞赛、学术论文、文献与研究、课程与研究材料、知识产权材料、图表与文档生产。绘图不是系统边界。

## 一、架构与所有权

| 层 | 唯一职责 | 位置 |
|---|---|---|
| 当前Agent | 理解任务、领域推理、方法选择、内容与结果解释 | 当前宿主 |
| 技能 | 当前单步的专业作业方法，不重复排整条流程 | `skills/` |
| 执行侧 | 资源读取、文件编辑、真实工具运行、依赖复用、评审收发 | `execution/` |
| 引擎 | 合同解析、状态、唯一验收、检查点与审计 | `engine/` |
| 工具 | 检索、求解、编译、格式化等具体操作 | `tools/` |
| 目录与资产 | 能力、技能索引、数据和参考材料 | `capabilities/`、`data/`、`assets-local/` |

引擎只编排不执行Agent。执行侧不决定研究结论，也不自行批准。工作流SQLite是状态真源，操作表记录真实执行；没有证据不能写成成功。

执行步骤动作走宿主无关的 `StepAction.workspace`（与 `skills/`、宿主无关协议、`workflow_cli` 同口径）：步骤产出与编辑以工作区相对路径登记，不绑定任何宿主私有路径或宿主专属 API。

## 二、启动与执行

在 `academic-toolkit/` 中：

```bash
python -m engine.workflow_cli boot
python -m engine.workflow_cli probe
python -m engine.workflow_cli start --template <模板> --workspace <工作区> --params <业务参数JSON>
python -m engine.workflow_cli next --wf <工作流ID> --db <数据库>
```

已存在工作流则恢复，不重建。`next` 返回当前任务、合同和执行会话；真实主技能与必用技能正文直接提供。入口技能负责选模板，不能嵌套成单个业务步骤。

## 三、任务路由

| 用户任务 | 模板或单步能力 |
|---|---|
| 国赛完整解题 | `comp_cumcm` |
| 华为杯完整解题 | `comp_huawei` |
| 其他数模赛事 | `engine/modex-core/templates.json` 中对应 `comp_*` |
| 找研究方向 | `idea_discovery` |
| 研究到论文 | `full_pipeline` |
| 深度研究综合 | `deep_research` |
| 文献综述 | `literature_review` |
| 英文/中文/Nature论文 | `paper_writing` / `paper_writing_zh` / `nature_writing` |
| 既有资产写论文 | `paper_from_assets` |
| 审稿与返修 | `auto_review` / `paper_submission`；单项用 `paper-rebuttal-nature` |
| 课程论文/报告/人文论文 | `course_paper` / `course_report` / `humanities_paper` |
| 课程教学材料 | `course_teaching` |
| 开题报告 | `thesis_proposal` |
| 基金申请 | `grant_proposal` |
| 毕业设计 | `grad_project` |
| 软著/源程序材料 | `copyright_material` / `copyright_source_materials` |
| 专利交底书 | `patent_disclosure` |
| 学术海报与演示 | `academic_outputs` |
| 科研绘图 | `scientific_plotting` / `scientific_figure_suite` |

单技能按真实任务选取，跨步骤任务使用模板。不要为了使用更多技能而堆调用；候选、实际读取、实际运行与语义贡献分别记录。

### 按需能力与资产

- 完整技能描述：`data/skill_routing_index.json`，运行时按查询返回小候选集，不全量灌入正文。
- 资产台账：`data/asset_catalog.json`，按用途/所属步骤查资料、工具、模型与范文。
- 历史题型：`data/historical_problems.json`、`data/case_patterns.md`。
- 赛事规范：`engine/modex-core/comp_rules.json` 与对应官方格式摘要。
- 写作参考、获奖论文、板块提示与专利原件：`assets-local/`，公开仓不交付的资料缺席须如实说明。
- 图形细分能力：`fig-visualization-advisor`、`fig-academic`、`fig-plot-edit`、`fig-plot-edit-lite`、`paper-framework-figure-studio-pro`、`agent-figure-gallery`。
- 论文改进参考：`paper-oral-exemplar`、`anti-defensive-writing`；PDF等单项工具按实际技能路由。

## 四、唯一执行协议

所有操作经 `python -m engine.workflow_cli session <操作>`，`--session` 使用当前会话文件：

| 操作 | 领域工作 | 程序负责 |
|---|---|---|
| `read --kind workspace --name PATH` | 阅读任务材料 | 内容版本与写作依赖 |
| `read --kind skill/asset --name NAME` | 按需咨询资源 | 真实读取记录 |
| `write --path PATH --stdin` | 保存真实内容 | 原子发布与输出来源 |
| `edit --path PATH --stdin` | 提供唯一old/new修改 | 匹配、并发变化检查、版本留痕 |
| `run --plan PLAN` | 指定实际命令、依赖和产物 | 返回码、时长、摘要、依赖版本 |
| `finish` | 宣告本步工作已准备完成 | 自动证据、统一验收、推进或集中诊断 |

PLAN 的 `nodes` 声明 `id/argv/inputs/outputs`，`depends_on` 指定依赖。模型不手填哈希、返回码、attempt、revision、清单或execution_evidence。

- 原地改稿/代码修复：同路径明确列入 `mutates`，记录before/after且不缓存。
- 无产物核查：`mode=check`、具名id、真实inputs；不生成假文件，内容改变后旧结论失效。
- 只有 `pure=true` 且 `complete_inputs=true` 的确定性节点可复用。输入、代码、程序、环境摘要、依赖版本、合同或输出变化都会失效；这不是操作系统沙箱，不适用于网络和隐藏依赖。
- `needs_work` 保持当前身份修正，一次解决诊断再finish，不为补字段反复retry。
- 工具已有producer manifest由程序保存，保留原输入、后端、依赖和配置；不得复制旧摘要冒充重跑。
- 业务产出结构由模板 `output_contract` 与named gates自动检查；技能描述保留领域要求，不再附手工清单和重复shell验证。

## 五、评审与批准

`session review-request` 指定实际输入、输出和rubric，生成版本绑定任务。宿主提供独立上下文执行，只评不改。`session review-receive` 接收真实原文、评审者和实际宿主调用标识；稿件版本变化必须重新评审。

收发记录证明收到什么、针对哪个版本；不能声称独立认证了模型身份。没有独立上下文则明确缺席，不冒用主控自己做的裁定。研究内部的评审-修订可循环，但不重启整条工作流。

`has_checkpoint` 必须等待真实批准：`workflow_cli approve --checkpoint ID --by <批准人> --db DB`。无回复、非交互模式、FAST_MODE和默认设置都不是批准。不得凭名字自动完成真实竞赛终审；仅明确 `machine_audit_only=true` 的纯机器聚合可自动接续。

## 六、质量与恢复

- `engine/quality_gates.py` 与 `output_contracts.py` 是确定性检查实现；返回具体问题，不以打印PASS代表通过。
- `AUDIT_REPORT.json` 的eligible为预审；当前 `DELIVERY_REPORT.json` 的ready才是机器交付结论。机器结论不等于科学质量获认可。
- `status` 查看真实事实；只有确认进程已停，才能 `recover --operation-id ID --reason REASON --confirm-stopped`，不自动杀进程或清历史。
- `retry` 用于真实失败/批准后版本更新，旧attempt不能写入新步骤。未经验证的历史补录不当作交付成功。
- 程序检查字节，不把mtime当成内容真值；目录检查保留成员集合，不能漏掉新增、删除或兄弟文件变动。
- 宿主原生工具未接入执行侧时，使用真实集成证据接口，不能凭空补返回码或会话。`complete/preflight/backfill`属于集成与历史恢复接口，不是模型日常填写流程。

## 七、审计与安全

| 来源 | 含义 |
|---|---|
| L1 | 可选宿主hook的实际工具事件；缺席标unavailable，不伪造 |
| L2 | 引擎状态、检查点、事务与提交事件 |
| 执行事实 | `execution_operations` 的真实资源/写入/命令/评审记录 |
| L3 | 引擎从事实或外部集成证据生成的已接受回执 |

原始数据、历史证据和科研成果不是清理对象。密钥不写入tracked配置、任务正文、命令参数或产物；只通过执行环境使用。全仓同一主控，代码和数据库不由两个状态所有者同时维护。

## 八、宿主与集成

可选宿主适配器只提供资源发现与L1，不是驱动前提。OpenCode的`opencode.json`、ZCode的`.zcode/skills`按本地需要配置；不使用的宿主不创建空壳。统一数据模型为 `engine.agent_bridge`。

新增能力必须同时具备：专业技能正文、明确输入输出、真实执行入口、必要业务检查、来源许可及验收证据。可复用就复用；没有工具报告TOOL_GAP，不写“已完成”。旧调用迁移后删除无用实现，活跃正文直接改正，不用“以新规则为准”保留矛盾。

## 九、开发验证

更改后运行实际受影响业务链，再运行仓库回归与溯源检查。测试计数以根 `pytest.ini` 为真源；全绿测试不能替代科研质量、外部来源或全业务验收。

```bash
python -m pytest -q
python tools/check_provenance.py
python tools/project_health_check.py --strict
```

内部操作与技术决策写 `dev-docs/LOG.md`；任务计划为 `dev-docs/task_plan.md`。保留原始历史记录，但它们不参与当前执行契约。
