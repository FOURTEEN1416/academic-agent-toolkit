# LOG.md — 项目操作日志

> 规则：粗粒度记录（按任务/里程碑），每条含日期 + 动作 + 原因 + 结果/验证证据。
> 分工：为什么这样设计 → 本文件；决策拍板 → 对应 spec/dev-docs 真源；当前状态 → task_plan.md / dev-docs/CURRENT_STATE.md。

## 2026-08-28

- **动作**：科研绘图能力扩展——fork 10 个上游仓库到 FOURTEEN1416（academic-research-skills / scientific-agent-skills / nature-skills / claude-code-templates / Auto-claude-code-research-in-sleep / AutoResearchClaw / excalidraw-diagram-skill / openscience / skills(markdown-viewer) / Vibe-Skills），克隆至 `vendor/forks/`（已 gitignore）。
- **原因**：用户要求扩展科研绘图能力并以 fork 为集成来源。
- **结果**：去重择优后集成 9 个新技能到 `数学建模全流程套件/skills/`（scientific-visualization、matplotlib、seaborn、infographics、plotly、scientific-schematics、figure-spec、graphviz、excalidraw-diagram），每个附 `references/UPSTREAM.md` 溯源并登记 `tools/check_provenance.py` 注册表；能力以 `scientific_plotting_expanded` 入册 `capabilities/catalog.json`（figures 域，269 项）。既有 paper-figure / mermaid-diagram / nature-figure / ars-* 为先前已集成的本地增强版，未覆盖。
- **验证**：`python tools/check_provenance.py` 26 条台账全 [OK]，退出码 0。

- **动作**：ZCode 兼容层落地——仓库根 `AGENTS.md`（宿主支持矩阵 + 硬性规则）、`.zcode/config.json`（docsearch MCP，workspace 级）、`.zcode/skills` NTFS 联结指向套件 skills（已 gitignore，重建命令见根 AGENTS.md）；套件 AGENTS.md 增补宿主兼容注记。
- **原因**：原系统仅 OpenCode Desktop 可驱动；用户要求兼容 ZCode。
- **结果**：ZCode 可发现全部 246 个技能条目并自动连接 docsearch MCP；L1 拦截式审计插件无 ZCode 等价物，审计降级 L2+L3（已如实声明）。
- **验证**：`ls .zcode/skills` 返回 246 项且子路径 SKILL.md 可读。

- **动作**：文档治理（按 project-governance 前置治理规程，先查后建）。
- **原因**：用户要求按前置文档治理流程治理本项目。
- **结果**：盘点确认 `dev-docs/truth-index.md` 为既有入口索引（真源分工表 + 缺陷台账维护至 2026-08-17），未重建、未搬文件；探针校准 `python -m pytest -q` = 225 passed（与 task_plan 基线一致，测试平面无漂移）；补齐缺失治理资产：本 LOG.md（项目根此前无操作日志）；刷新 truth-index 与 task_plan 登记 2026-08-28 增补真源。
- **验证**：见上方两条测试/台账证据；本文件即治理产物 C 的落地证据。

## 2026-08-28（第二批：全量文档治理 + 命名对齐 + zcode 治理设定）

- **动作**：全量通读治理——3 个审计代理逐份读完 45+ 份文档（dev-docs 31 份、docs/superpowers 8 份、根公开文档、governance），另手工完成 legacy 文件夹逐字节比对。
- **原因**：用户裁定：文档治理必须读完所有文档（不是看文件名）、可疑/过期信息必须清理、项目定位是完整科研工具箱、质疑两个工具文件夹为何不合并。
- **结果（污染源清理）**：
  - 17 份过期/一次性报告加"仅供追溯"横幅（含根 task_plan 引用的基线矛盾：测试基线 131→225 六版本混用、正式能力数 0/10/17 矛盾、catalog 总数 264/266/268 漂移——均以横幅声明最新实证为准）；
  - COMP_REVIEW.md 系统性文本损坏（行首字母丢失）加损坏声明横幅；PUBLIC_PRIVATE_ASSET_INVENTORY.md 尾部误拼接的过期段落（264 entries/none 正式）删除；CHANGELOG.md"核心：MIT"改为 CC-BY-NC-4.0（与 LICENSE 一致）；b4 测评报告标题诚实化（AI 模拟评审，非人工专家）；LESSONS M6 行"进行中"改"已修复"；governance/ASSET_LEDGER.md 加过期横幅；根 README 过期边界声明更新；科研工具箱/AGENTS.md 的 .env 架构图行中性化。
- **结果（命名对齐）**：`数学建模全流程套件/` → `科研工具箱/`（git mv 保历史）；更新 15 个活跃文件 80 处引用（opencode.json、根/套件 AGENTS.md、README、根 tests×2、套件 tests×2、tools×3、skills/CLAUDE.md、.opencode subagent、.gitignore、truth-index）；docs/superpowers 历史计划保留原文（dated 快照）。套件 AGENTS.md 标题与定位段改写为"完整科研工具箱（6 大能力域），数模竞赛是验证场景之一"。
- **结果（合并裁决）**：`数学建模大赛工具集/` 整包归档至 `dev-docs/archive/数学建模大赛工具集-legacy-20260828/`（未删除），依据见 DELETION_LOG.md。
- **结果（zcode 治理设定）**：新增技能 `acat-doc-governance`（固化用户三铁律：全文读完/污染必清/不窄化定位）+ `.zcode/commands/doc-governance.md` 斜杠命令；根 AGENTS.md 增加"仓库地图（治理入口）"一节。

- **决策记录（2026-08-28）**：用户明确授权 graphviz 与 excalidraw-diagram 两个无上游 LICENSE 的技能随公开仓库推送。已解除 gitignore 排除，UPSTREAM.md/catalog/truth-index 同步改记授权事实与"异议即移除"承诺。

## 2026-08-28（第三批：全能力公开发布 v1.1.0）

- **动作**：按用户裁定将项目所有能力纳入公开发布——catalog 9 项 private_extension（软著 copyright-draft/build、专利 patent-draft/build、grants 等）转 experimental 并记 promotion_history；CHANGELOG 增 v1.1.0 条目；本地组装净化发布包 releases/v1.1（269 能力/247 技能，剔除 .env/sqlite/workspaces/baseline/data/__pycache__，与公开仓库边界一致）；acceptance_testing/sync_release.py 旧路径修正。
- **原因**：用户指示"将该项目所有能力都进行发布"。发布≠转正式：未经 C2-C5 验收的能力保持 experimental 如实状态（正式仍为 10 项），避免伪造验收证据。
- **验证**：pytest 225 passed；发布包净化复查（无 .env/sqlite/私有目录）通过；bundle catalog 分布 {正式:10, experimental:259}。

## 2026-08-29

- **动作**：追加集成 cathrynlavery/diagram-design（28.3k★，MIT，39 类编辑级图表 + drawio/mermaid 源重绘）——fork 至 FOURTEEN1416/diagram-design（pinned ac490fd），技能原样入 科研工具箱/skills/diagram-design，UPSTREAM.md 溯源 + provenance 注册表（26→27），catalog scientific_plotting_expanded 能力与 README 绘图栈同步更新（244→245 技能）。
- **原因**：用户评估后拍板融入；补强绘图栈的"编辑设计级信息图"层，与 figure-spec（确定性）/excalidraw（手绘论证）形成三风格互补。
- **验证**：provenance 27/27；pytest 全量见当次运行结果。

## 2026-08-29（第二批：全量文档治理返工 + 集成整改）

- **动作**：应用户批评返工——逐份全文读完 dev-docs + docs 全部 64 份文档（含上一轮漏盘的 `解析/` 17 份），提取设计哲学（三层架构/编排七模式/SKILL.md 契约结构/三条钢律/CodeSucker 六件套/C1-C6 验收），并据此整改：10 个绘图技能全部补 `## STEP_MANIFEST 产出声明`（40→50），templates.json 注册 `scientific_figure_suite` 工作流模板（4 步，迁移幂等），acat-doc-governance 固化铁律 4（集成六件套），解析/ 17 份补历史横幅（执行 LESSONS 挂账项），truth-index 新增"设计哲学与集成规程锚点"与整改记录，dev-docs/README.md 刷新。
- **原因**：用户裁定：本项目不是简单 skills 仓库合集，是步步有审计、步步可追踪、可用 OpenCode/ZCode 驱动的科研工具箱；此前 2026-08-28 治理漏读 `解析/` 目录、把集成做成了"带溯源的堆放"。
- **验证**：`upgrade_templates.py` 二次运行 changed_steps=0；未知门禁名 0；pytest/provenance 见当次运行。

## 2026-08-29（第二批：绘图能力按设计哲学完成完整接入）

- **背景**：用户批评此前绘图技能集成是"简单堆技能"，违背项目"步步审计、步步可追踪、引擎可驱动"的设计哲学。重读 C1-C6 验收管线定义（dev-docs/docs/superpowers/specs + plans/2026-08-13-cumcm-formal-acceptance.md）后按纪律补齐。
- **动作**：
  1. 引擎注册第 40 个工作流模板 scientific_plotting（figure-spec→diagram-design→paper-figure→scientific-visualization→comp-review 独立评审；SVG 步骤挂 step_manifest、PNG 步骤挂 figure_provenance，门禁按产出类型分配）；
  2. C2 真实验收：引擎驱动 workspaces/plotting_acceptance 真实跑通 5 步（wf b1f55fb0），逐步 STEP_MANIFEST + schema v1 执行证据（含 skill_sha256 防伪），产物全部真实生成（SVG/HTML/PNG300dpi/tex/溯源 JSON）；期间 6 次门禁拒绝（伪证据/产物不齐/缺溯源）如实留档，FAILED→RUNNING 重试走状态机；
  3. 独立评审 subagent 四轮评审（无头渲染截图 + PIL 像素测宽 + 字节检查 + numpy 复算），抓出本人引入的 5+1+1 项缺陷（含 \begin 转义 0x08、文字溢出、节点重叠回归），逐轮修复，终审 PASS（0 fatal/0 major/9 minor），COMP_REVIEW.md/VERDICT 留档；
  4. catalog 新增 10 条逐技能 C1 合同（13 字段，共 279 条），聚合条目 evidence/gap 更新（4 技能 C2 已验、4 技能因运行时依赖未跑如实声明）；
  5. C6 回归：新增 tests/test_plotting_capability.py 4 项（合同 13 字段/模板有效性/溯源注册/门禁分配），全量 229 passed。
- **验证**：pytest 229 passed；check_provenance 27 台账 + vendor 全过；workflow status completed + WORKFLOW_REPORT.json。

## 2026-08-29（第三批：figures 域 C3/C4/C5 闭环 + 技能库补充验证）

- **C3 公开基准**：新建 benchmarks/six_domains_public/FIGURES-01（fixture CSV + contract + evaluate.py 8 类机检），起真实工作区 workspaces/figures_benchmark_c3 引擎驱动 5 步重跑，评审 subagent 两轮（抓出溯源覆盖 1/4 的 major）修复后 evaluate exit 0。
- **C4 私有基准**：benchmarks/cumcm_private/figures_private/C4_style_rubric.md（62 篇获奖论文实证规范），评审员逐条对照判定，抓出期刊图缺中文题注的 major，补题注后复验 PASS（revision 2）。
- **C5 四维指标**：results.json（质量=评估器+双评审；可靠性=5/5 步、证据 rc 全 0、1 轮缺陷闭环；效率=引擎步进 1.7s/墙钟约 25min；成本=0 外部 API）。
- **技能库补充验证（Part B）**：新增 tools/skill_library_audit.py 常驻审计器（frontmatter/体积/编码/引用完整性/模板一致性五类机检）。首轮抓出 23 处真实缺陷：9 个技能无 frontmatter（宿主扫描器不可发现，已补齐）+ 14 处家族前缀改名的断链引用（上游脚本从未入库，已就地加 ACAT-GOVERNANCE 标注防 agent 追 phantom）。146 个 Python 脚本编译检查 0 失败。回归：tests/test_skill_library_integrity.py 4 项。全量 233 passed。
- **诚实边界**：scientific_plotting_expanded 保持 experimental——C1-C6 已闭合但 12 关联技能中 6 个未过 C2；是否提升正式由用户裁决。
