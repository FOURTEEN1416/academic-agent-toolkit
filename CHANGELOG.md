# v1.2.0 发布说明（CHANGELOG）

## v1.2.2（2026-09-09）—— ZCode 赛时主控 + 模型去预设（用户裁定）

- **模型不预设（全链落地）**：新增 `engine/modex-core/contest_models.json` 配置槽（出厂四角色全空）；`quality_gates.load_configured_role_models` 改宿主中立三级解析（ACAT_CONTEST_MODELS > 配置槽 > OpenCode agents，逐角色回退）并新增 `model_config_provenance()`；strict 门禁在两处皆空时降级 warn（显式留痕不静默）。工具层去预设：`doc_reader`（原默认 agnes-2.5-flash）、`tikz_vision_check`（原默认 gpt-4o）改为未配置即明确报错；`pyc_loader` auth 查找不再硬编码厂商名（动态发现 provider 优先+全量遍历）；`comp-visual-review`/`infographics`/`scientific-schematics` SKILL 与 README/AGENTS 措辞改为"比赛时配置，仓库不预设"（例：任一具备视觉能力的模型）。
- **ZCode 升格赛时主控宿主**：L1 拦截式审计 hook 等价实现 `科研工具箱/hooks/zcode_audit_l1.py`（PreToolUse/PostToolUse/PostToolUseFailure → 与 OpenCode 插件同格式的 `operations.jsonl`；`git add .` 级治理拦截 exit 2；异常静默绝不打断会话）；`.zcode/config.json` 注册 hooks（enabled + 三事件，随仓库分发）。审计降级句（"ZCode 仅 L2+L3"）全库清除，宿主矩阵/三层审计表/独立性契约测试同步演化。
- **赛前自检入库**：`tools/contest_dryrun/`（14 步全链驱动 + 终审真实模型探针，2026-09-09 审计驱动通用化入库：路径参数化、fig 自生成、终审端点 env 三级解析不预设厂商）。
- **残留修复**：README `28/28` 过期数字 → 63/63。
- **测试**：新增 `tests/test_zcode_host_compat.py` 12 项（三级解析/strict 联动/hook 五态/注册契约）；基线 工具箱 **259** / 仓库根 **303**。

## v1.2.1（2026-09-09）—— 独立审计全量修复

无上下文独立审计（`dev-docs/INDEPENDENT_AUDIT_REPORT_2026-09-09.md`）发现项全量修复：

- **P0 国赛三线表编译中断**：`cumcmthesis.cls` 包序修复（booktabs 移至 bigstrut/bigdelim 之后），SKILL 教授的 `\toprule/\midrule` 与 longtable `\endfirsthead` 格式实测编译通过；补入编译验证的 `_templates/cumcm/main.tex` 骨架；UPSTREAM.md 登记本地补丁。
- **P1 编译门禁盲区**：`compile_check.sh` 新增 `^! ` LaTeX 硬错误检测与真实 undefined-reference 判据（旧 `\[?\]` 恒 0）；"修前放行的断表工程"现 exit 1 拦截。
- **P1 引擎检查点非硬闸**：`workflow_runner.next_action` 新增 blocked-checkpoint 拦截（未 approve 不得推进），回归测试正反两路。
- **P1 模板死声称**：comp-paper-zh 5 套模板声称改为现状如实口径；华中杯分支复用 cumcm 模板；comp-compile-zh 8 条死路径模板对比循环改动态探测+显式跳过。
- **P1 机检前缀盲区**：`skill_library_audit` 内部引用检测扩展 `_utils/`、`shared-scripts/` 前缀；全库暴露 17 处真断链全部修复或内联声明（含 dev-selfcheck/paper-figure 系列；`.pyc` 直调教学全部纠正为 `.py` 真源 + 防回归测试）。
- **P2 双副本漂移**：`claim_code_check.py` 同步；新增 `test_dual_copy_consistency`（hash 级机器防线，注入破坏反验）。
- **P2 mermaid -p 缺失**：可执行命令模板补 `-p` 配置探测；实测裸跑失败→带配置成功。
- **P3 graphviz/环境**：Windows dot 检索指引入技能；provenance 收紧（URL 源强制 7-40 位哈希 Pinned commit，正反测试）；`quality_gates.check_review_evidence` reason 优先级 bug 修复（真因不再被警告文案遮蔽）。
- **验证**：工具箱 247 / 仓库根 291 全绿；两机检 exit 0；CUMCM 14 步全链驱动 0-11 步通过（含 blocked 硬闸 4 次 approve、step9 真实编译、终审由 sensenova/deepseek-v4-flash 真实执行 fatal=0）；step12 strict 门禁在 ZCode 宿主**正确拒绝**（mimo-v2.5-free 配置通道当前环境 503/404 不可达，不可伪造模型证据）；step13 final-audit 独立验证全绿。

> 历史条目保持原样（dated 快照仅供追溯）：以下 v1.2.0 一节中的 242/28/245 为发布时数字，现值见上节与 README 徽章。

---

> 发布日期：2026-08-30
> 宿主：OpenCode Desktop + ZCode（双宿主）
> 变更基线：v1.1.0..HEAD（13 commits）

## 范围（三大主题）

### 1. 科研绘图能力域：C1-C6 全闭环（首个全验收域）

- **设计哲学式集成**（非技能堆放）：引擎模板 `scientific_plotting`（5 步含独立评审门禁）+ 逐技能 C1 合同（13 字段）+ C2 引擎驱动真实验收（SVG/PNG300dpi/溯源 JSON 全真实产物，6 次门禁拒绝留档）
- **C3 公开基准** `benchmarks/six_domains_public/FIGURES-01`（evaluate.py 8 类机检）；**C4 私有基准**（62 篇获奖论文实证样式规范）；**C5 四维指标**（质量/可靠/效率/成本，0 外部 API）
- **本地运行时就绪**：Graphviz 16 + mermaid-cli（Edge 渲染）实渲染验收；`tools/plotting_env_check.py` 一键体检
- **多模态 LLM 专属技能改造**：infographics/scientific-schematics 加 Step 0 生成后端强制检测，禁止占位图冒充
- **技能库常驻审计器** `tools/skill_library_audit.py`（frontmatter/体积/编码/断链/模板一致性五类机检）+ diagram-design（28.3k★ MIT fork）集成

### 2. 三条学术管线建成并全部 C2 闭环（独立评审 PASS）

| 管线 | 引擎模板 | 独立评审 | 亮点 |
|------|---------|---------|------|
| P1 论文投稿与返修 `paper_submission` | 5 步 | 三轮评审终审 PASS（0/0/2） | 初评抓出 8 major（虚构数据集等）全部整改 |
| P2 深度调研 `deep_research` | 4 步 | 四轮评审 round-4 PASS（0/0/2） | 首轮 5 条编造引用全驳→证据层重建；round-3 E2 PII 经 Crossref 全量比对证伪→权威绑定替换；核验台账重建为 curl 原始输出可复现留档 |
| P3 基金申请 `grant_proposal` | 4 步（第 44 个模板） | round-1 一次过 PASS（0/0/3） | NSFC 青年草稿；证据层继承 P2 已核验集合零新增引用；PI 信息全部显式占位禁止编造；future-work 口径 |

- 防编造体系实测有效：引用必须可点开核验、used_in 章节级回链、推断显式标注、"首次/最优"断言禁用、subagent_session 审核独立视角门禁

### 3. 基础设施与治理

- **技能名冲突修复**：113 个 frontmatter name ≠ 目录名归一（宿主扫描遮蔽根因），跨作用域冲突 11→2（余为用户级设计内）
- 5 条 minor（P2×2 + P3×3）措辞级修复并经 16 项逻辑校验（2026-08-30，按用户裁定不重放工作流，修正记录留档）
- README 全面重写（徽章墙/mermaid 架构图/提示框/折叠面板/双宿主快速开始）

## 验收基线

- pytest **242 passed**（figures 域 4 项 + 冲突回归 1 项 + P1/P2 管线 4 项 + P3 管线 4 项新增）
- provenance 台账 28/28；skill audit OK（245 技能 / 44 模板 / template_missing_skill=0）
- catalog **281 条能力**（正式 10 / experimental 271；发布≠转正式，未验收能力保持 experimental）

## 已知限制

- P1/P2/P3 的 C3/C4 基准未建（figures 是目前唯一 C1-C6 全闭环域）；5 条 minor 修复未重放工作流（用户裁定，差异措辞级）
- 逐技能 C2 覆盖率有限，未验收能力保持 experimental
- ars-grants（NIH 专属）依赖外部 MCP，保持 experimental

## 许可

- 核心（套件/配置）：CC-BY-NC-4.0（含禁 AI 训练条款）
- 公开基准集：CC-BY-4.0

---

# v1.0.0 发布说明（CHANGELOG）

> 发布日期：2026-08-17
> 宿主：OpenCode Desktop（唯一正式支持宿主）
> 发布包：`releases/v1/`

## 范围

六大领域 33 个聚合能力（225 个公开技能映射）：

| 域 | 能力 | 状态 |
|----|------|------|
| 数模竞赛 | comp_cumcm_full_pipeline / comp_problem_analysis / comp_modeling / comp_code_solve / comp_paper_zh / comp_review_visual / comp_final_audit / comp_mcm_icm / comp_consistency / comp_literature | **正式**（10） |
| 数模竞赛 | comp_stats_topic | experimental（数据获取证据待补） |
| 学术论文 / 文献研究 / 课程材料 / 知识产权 / 图表文档 | 22 个聚合能力 | experimental（C1+C2 已验，C3/C4 基准待建） |

## 正式能力验收依据（design §7）

- C1 合同完整：33/33（13 字段，0 缺失）
- C2 真实验收：公开基准 P01-P03 + 私有 2025B + 14 步 workflow 流程级验收
- C3/C4 双层基准：公开（合成题）+ 私有（真实题面）端到端通过
- C5 四类指标：多智能体独立评审校准（≥4/5 质量、≥90% 成功率、≥95% 证据完整率、≤15min 效率、≤15 credits 成本）
- C6 回归：204 tests passing（源仓库）+ 发布包 200 tests（160+3skip 套件 + 37+3skip 基准）
- 防伪造机制：requires_subagent + 命令真实性 + review full 模式 + manifest 哈希

## 关键机制

- 三层审计（L1 拦截式 plugin / L2 编排式 runner / L3 申报式 evidence）+ 防绕过检测
- 检查点审批原子事务；质量门禁（大小/伴随/页数/图表/审稿）
- 多角色审稿闭环（executor/reviewer/editor，独立视角强制）

## 许可

- 核心（套件/配置）：CC-BY-NC-4.0（与 LICENSE 文件一致；原记录 MIT 系笔误，2026-08-28 治理修正）
- 公开基准集：CC-BY-4.0
- 私有扩展/真实题面/内部文档：不随包分发

## 已知限制

- 私有扩展能力（专利/软著/基金等 9 条）不在此包，需单独申请
- 跨域能力（论文/文献/课程等 22 个）仅 C1+C2 验收，基准待建，状态 experimental
- **C5 校准已定稿（2026-08-17）**：放弃人工专家复核——多智能体独立评审（2 评审者共识）为最终校准，理由：基于全部真实观测、独立评审一致、保守取值、session 可追溯（见 CALIBRATION.md 方法变更声明）
- 视觉审查依赖视觉 API（不可用时如实记录 unavailable）

## 变更历史

- 2026-08-17：v1.0.0 发布包组装完成（净化：剔除 .env/sqlite/私有技能/私有模板；适配：私有基准与宿主配置测试跳过）
- 2026-08-17：发布前最终复核完成——C5 放弃人工复核定稿；catalog 合规修正强制（10 正式）；全量回归源 214 + 包 200；边界安全扫描无残留；合规修正曾被覆盖后重新强制执行（根因：后续 catalog 重写操作），现已锁定不再变更

## [v1.1.0] - 2026-08-28

### Added

- 科研绘图扩展：集成 9 个上游技能（scientific-visualization / matplotlib / seaborn / plotly / figure-spec / graphviz / excalidraw-diagram / infographics / scientific-schematics），catalog 新增 `scientific_plotting_expanded` 能力
- ZCode 兼容层：根 AGENTS.md（宿主支持矩阵）、`.zcode/config.json`（docsearch MCP）、`.zcode/skills` 技能联结、`/doc-governance` 命令与 `acat-doc-governance` 治理技能
- 全学术定位：主套件目录更名 `科研工具箱/`（原 数学建模全流程套件/），文档定位统一为 6 大能力域科研工具箱

### Changed

- **发布边界（用户裁定 2026-08-28）：项目所有能力公开发布**——9 项 private_extension（软著 copyright-draft/build、专利 patent-draft/build、基金 grants 等）转为 experimental，不再设私有扩展边界；验收状态保持如实（未跑 C2-C5 者仍为实验性，正式仍为 10 项）
- 文档治理：45+ 份文档全文审计，17 份过期快照加"仅供追溯"横幅，修正许可矛盾（MIT→CC-BY-NC-4.0）与多处漂移数字；溯源台账扩至 26 条