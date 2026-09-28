# PaperSpine × PaperFigure V5 整合层

本目录实现 PaperSpine、PaperFigure 与交稿后 Publication Cycle 之间的可执行边界：PaperSpine 负责论文论证与规范主稿，FigMirror/PaperFigure 负责科研图创作、审计和整图审阅，PaperSpine Publication Cycle 负责目标核验、投稿包装配、返修和转投的本地产物；整合层负责可恢复编排、宿主适配、前端触发和证据状态。跨界字段只在本目录定义；各模块仍拥有自己的业务真相。

## 已实现闭环

```text
PaperSpine 已确认产物 + 逐图/逐 panel 理解后的 figure_requests.json
  → keep：复用经理解与审阅判定为 publication-ready 的 current_figure
  → redesign/create：generation_plan.json → Agent 原生创作 A/B(/C) → FigMirror 定稿
  → FigMirror 排序与统一整图审阅 UI（keep 以 existing 身份进入同一决定合同）
  → review_decision.json（整图确认）
  → final_paper/figures + 可编辑源 + LaTeX 标记注入
  → figure_body_contract.json（Results/图注/正文引用/主张边界接口）
  → PaperSpine 正文真实引用、LaTeX/Word、逐页逐图最终像素回证与五维 readiness
  → canonical_paper_ready（规范主稿，不等于目标投稿包）
  → Publication Cycle：目标配置 / 投稿包装配 / 返修核验与渲染 / 转投计划
  → awaiting_external_authorization（仅本地投稿包就绪；外部动作未授权）
```

主干状态机为 `initialized → awaiting_candidates → awaiting_review → figures_confirmed → awaiting_paper_integration → canonical_paper_ready`；随后按用户需要进入 `target_profile_ready`、`awaiting_external_authorization`、`rebuttal_validated`、`rebuttal_materials_ready` 或 `destination_rebuild_ready`。全为 `keep` 时生成与候选审阅阶段自动记为不适用。只有 PaperSpine `is_complete=true` 且科学内容、视觉、引用、元数据、可移植性五维 readiness 全绿，才进入 `canonical_paper_ready`。Publication Cycle 的任一结构化失败进入 `blocked` 并保留回执，修复后可重试；`external_action_authorized` 在整合接口中恒为 `false`。旧 1.0 状态会迁移到 1.2，旧“装配即 complete”回到 `awaiting_paper_integration`；旧 1.1 `complete` 迁移为 `canonical_paper_ready`。

`figure_requests.json` 的 1.0 基础字段保持向后兼容。新 PaperSpine 任务使用一份原子 scientific-story contract：figure role、科学问题、单一主论断、预期结论、claim boundary、对应 Results 单元、hero panel，以及每个 panel 的问题、职责、证据锚点和预期读法。一旦出现任一 story 字段，其余字段必须齐备；bridge 会把它们原样传入 `generation_plan.json` 和每个候选的 `generation_request.json`。候选可以改变视觉表达，不能改变科学故事。缺失完整 story 的历史最小请求仍可校验，但不能完成正文装配。

V5 的示意图模式随交付偏好选择：`preferred_format=svg` 显式使用 `direct_vector`；其余偏好默认使用 `img2ppt_hybrid`，执行 AI 源图转前严审、原生 PowerPoint 语义重建、复杂对象真实图片替换和转后严审，并交付可编辑 PPTX + PNG。`high_resolution_raster` 保留为显式兼容路线。数据图仍保持 Matplotlib 矢量输出。

## 快速使用

复制 [integration_job.example.json](examples/integration_job.example.json)，让 PaperSpine 输出目录包含已确认产物和 [figure_requests.example.json](examples/figure_requests.example.json)，然后执行：

```powershell
python 03_联合开发/scripts/paperspine_figure.py validate <integration_job.json>
python 03_联合开发/scripts/paperspine_figure.py advance <integration_job.json>
python 03_联合开发/scripts/paperspine_figure.py host-next <integration_job.json> --host codex
python 03_联合开发/scripts/paperspine_figure.py body-contract <integration_job.json>
python 03_联合开发/scripts/paperspine_figure.py workflow <integration_job.json>
python 03_联合开发/scripts/paperspine_figure.py publication-cycle-describe <integration_job.json>
python 03_联合开发/scripts/paperspine_figure.py publication-cycle-invoke <integration_job.json> <operation-request.json>
python 03_联合开发/scripts/paperspine_figure.py serve <integration_job.json> --port 8765 --open
```

完成 `generation_plan.json` 中的候选图后再次运行 `advance`，即可生成审阅页；在统一 UI 中选择每张整图方案并确认后，系统自动装配到 PaperSpine 的 `final_paper`，同时发布 [正文结合接口](PAPERFIGURE_BODY_INTERFACE.md)。正文与最终像素审计完成后再次 `advance`，进入 `canonical_paper_ready`。此后可在网页“投稿循环”页点击五个真实按钮，或通过 CLI/HTTP 调用 [Publication Cycle 整合接口](PUBLICATION_CYCLE_INTEGRATION.md)。`workflow` / `GET /api/workflow` 返回八段实时证据链。服务只监听 `127.0.0.1`、拒绝非本机 Origin；`GET /api/publication-cycle` 和 `POST /api/publication-cycle` 分别提供状态/描述与本地操作。

## 目录职责

- `contracts/`：集成任务、图请求、状态、审阅决定、Agent 信号、正文结合、全生命周期快照与装配清单的 JSON Schema。
- `src/paperspine_figure_integration/`：契约验证、PaperSpine/FigMirror 桥接、状态机、UI 服务与装配器。
- `adapters/`：Codex、Claude Code 和 PaperSpine 阶段出口说明；两个 AI 宿主共用 `paperspine.figure.next_action` v1.0 协议。
- `ui/`：研究动机、核心贡献、完整候选图、规范主稿和 Publication Cycle 五操作的一体化工作台。
- `integration_tests/`：真实调用 FigMirror CLI 的端到端验收与边界测试。

## 权威与边界

- `integration_state.json` 是恢复进度的权威记录；聊天文本不是状态源。
- `review_decision.json` 必须覆盖全部图件：`redesign/create` 只能确认 A/B/C 中一个完整候选，`keep` 只能确认 `existing`，不得借 `keep` 绕过现图身份。
- 数据图必须提供 `source_data`；publication 模式可要求候选 lineage。
- 每张图可声明 `keep`、`redesign` 或 `create`；`keep/redesign` 必须给出项目根内真实 `current_figure`，只有 `redesign/create` 进入候选生成。story 字段一旦启用必须原子齐备，`hero_panel` 必须指向已声明 panel。
- 示意图可选提供 `data_evidence`，但路径必须指向项目内由数据流程发布的 aggregate-only 证据包；整合层将其传入 FigMirror 候选契约，示意图再通过稳定事实 ID 绑定节点。
- 数据证据桥不授权示意图读取行级数据或重算统计；来源哈希、解释限制和绑定清单必须进入蓝图 manifest 与最终 lineage。
- 最终装配只接受候选目录内、由 `authoring_report.json` 声明的导出，并记录 SHA-256。
- Img2PPT 的 PNG 作为正文出版图，PPTX 真实可编辑源自动复制到 `final_paper/figure_sources/`；SVG 出版图同时登记为可编辑源。
- `figure_body_contract.json` 必须覆盖每张确认图的 Results 单元、正文标签、图注、主张、边界和 panel 证据；PaperSpine 最终门禁会复核资产哈希和正文中的真实 `\ref`。
- `canonical_paper_ready` 不是“图件文件已复制”的别名；它要求最终论文像素回证与 PaperSpine 五维 readiness 全绿，但仍不是 `target_bundle_ready`。
- `deliverables.ready` 只在最近一次成功 `assemble` 回执给出 `submission_bundle_ready=true` 且状态为 `awaiting_external_authorization` 时成立；`deliverables.canonical_ready` 单独表示规范主稿就绪。
- Publication Cycle 请求、结果和哈希回执保存在配置的 `publication.invocation_dir`；请求内路径必须解析到 `project_root` 内，输出目录由下游合同要求为新目录或空目录。
- 整合层不提供外部投稿按钮；`external_action_authorized=false` 是不可放宽的权限边界。
- 自动选择默认关闭；只有 FigMirror 全部门禁通过、排名明确且任务显式允许时才能自动确认。
