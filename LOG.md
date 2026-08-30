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

## 2026-08-29（第四批：本地运行时落地 + 多模态 LLM 专属技能改造）

- **动作**：安装 Graphviz 16.0.0（winget，dot.exe 未入 PATH 已在检测器做兜底定位）与 mermaid-cli（bun 全局，PUPPETEER_SKIP_DOWNLOAD + 系统 Edge 渲染，标准配置写入 ~/.mermaid-puppeteer.json）；两技能 C2 真实验收出图（workspaces/runtime_verification：dot→pipeline.svg、mmdc→benchmark.png）。新增 tools/plotting_env_check.py 环境检测器（技能可用性一览 + 安装指引）。infographics / scientific-schematics 改造为"多模态 LLM 专属技能"：SKILL.md 加 Step 0 强制后端检测（缺生成后端明确报错并给指引，禁止占位图冒充；评审可复用 OpenCode 免费视觉模型 agnes/agnes-2.5-flash），frontmatter 标 requires: multimodal-llm-image-generation。README 环境要求改表格式（必装/推荐/可选 + 一键体检命令）。
- **验证**：plotting_env_check 输出 graphviz ✅ / mermaid ✅ / imagegen ❌（如实）；catalog 同步。

## 2026-08-30（P1/P2 管线建设 + 技能名冲突修复）

- **P1 paper_submission（完成）**：模板 5 步（presubmit→audit→response→camera-ready→独立评审）。C2 三轮评审：初评抓 8 major（虚构数据集 ENWIKI、声称-实况偏差、预支结论）→ 整改 → 复评 2 major → 终审 **PASS**（0/0/2）。二轮工作流对终稿全量重放（STEP_MANIFEST 哈希与修订后文件一致），workflow completed + WORKFLOW_REPORT。
- **P2 deep_research（进行中，诚实受阻）**：模板 4 步。步骤 0-2 完成；首轮评审外部核验发现 5 条引用 0/5 可验证（编造 arXiv 条目），**整体重建**为可核验公开来源（fpp3/GEFCom2014/conformal 专著/M5 Uncertainty/ENTSO-E）；独立评审第三轮因宿主模型速率限制 4 次未能启动（错误码 1302/quota 留档）。所有者按同款外部核验流程完成 **5/5 URL 验证**并留档（registry owner_verification）。工作流停在 comp-review 待独立复核，不伪造通过。
- **技能名冲突修复（用户报告"17 个冲突"）**：全发现面实扫 = 11 组冲突 23 技能（仓库内 4 组 + 用户级遮蔽 7 组）。根因：家族前缀技能改名目录未改 frontmatter name。修复：113 个 frontmatter name 归一为目录名（审计器新增 name_mismatch/name_duplicate 两类机检 + 回归测试）。归一后跨作用域冲突 11→2 组，剩余均为用户级技能包自身（ecc-deep-research 设计内覆盖、microsoft-foundry 双安装），仓库侧清零。
- **验证**：pytest 238 passed（+1 冲突回归）；skill audit OK；provenance 27+vendor 全过。

## 2026-08-30（P2 收官：round-3 评审修复 + round-4 独立评审 PASS + C2 闭环）

- **round-3 评审落地**：宿主配额恢复后 round-3 独立评审实际完成（REJECT，1 fatal/1 major/3 minor）：E2 内嵌 PII S0169207015000155 经 Crossref IJF 全量 3694 条比对+Semantic Scholar 反查+多引擎零足迹+号段缺口四重通道证伪；owner 自报台账 E2 失实 PASS（张冠李戴）。
- **按 findings 逐条修复**：
  1. R3-F01（fatal）：E2 换为 Crossref 权威绑定确证的 S0169207016000133（DOI 10.1016/j.ijforecast.2016.02.001，"Probabilistic energy forecasting: GEFCom2014 and beyond"，Hong/Pinson/Fan/Zareipour/Troccoli/Hyndman，IJF 32(3):896-913），主控 curl 独立复核成立；
  2. R3-F02（major）：核验台账重建为可复现 round-2 版（search_evidence/owner_verification_round2/，curl 原始输出逐条留档，失败通道 403/400/not found 如实记录），round-1 台账作废并留修正记录；
  3. R3-F03：used_in 按全文逐章节正则重扫精确化（校验器强制"不低估不高估"）；
  4. R3-F04：2023-2026 方法演进时间维缺口登记于 coverage_notes + RESEARCH_SUMMARY §2/§3；
  5. R3-F05：IDEA_DISCOVERY §4 两处常识断言补"（推断，…）"标注。
- **工程教训**：subprocess shell=True 经 cmd.exe 传递全角字符会被转码破坏（SyntaxError: unmatched ')'）——校验断言一律改为 UTF-8 脚本文件 + 纯 ASCII 命令调用（.engine/check_round3.py）。
- **round-3 重放**：旧工作流诚实关闭（closure_note），新一轮 4c3b56e9 对终稿重新申报步骤 0-2（10 条验证命令含全部修复断言）。
- **round-4 独立评审 PASS**（0 fatal/0 major/2 minor 记录精度级）：R3 五条修复全部独立复核确认；E1-E5 外部核验全过；2 条 minor（R4-F01 台账辅助记录文件名失实、R4-F02 coverage 年份序列归属）登记待修不阻塞。round-3 评审件归档 review_history/round3/。
- **C2 闭环**：comp-review 步骤完成（evidence 含真实 subagent_session + provenance 检查 rc=0），workflow 4c3b56e9 completed，WORKFLOW_REPORT.json 生成；catalog deep_research_pipeline 证据更新为 C2 完成 + 2 minor 登记待修。
- **验证**：pytest 238 passed；check_provenance 28/28；catalog JSON valid。

## 2026-08-30（P3 收官：grant_proposal 管线建成 + C2 闭环）

- **模板注册**：engine/modex-core/templates.json 第 44 个模板 `grant_proposal`（4 步：idea-discovery→research-lit→grant-proposal→comp-review 独立评审；证据登记步骤挂 step_manifest，评审步骤 requires_subagent + review 门禁）。
- **C2 真实验收（workspaces/grant_proposal_c2，wf 062b95a2）**：
  1. 选题承接 deep_research_c2 round-4 调研结论（"可进入研究提案阶段"的方向 1），资助类型 NSFC 青年——管线衔接即真实科研工作流；
  2. 证据层**原样沿用**上游 round-4 已核验证据集 E1-E5（零新增引用，registry 注明继承来源与上游核验台账路径）；申请人信息全部显式占位【待申请人填实】，禁止编造 PI 履历——基金申请书最高危的编造面；
  3. 核心产物 GRANT_PROPOSAL.md：NSFC 青年 8 节 + 预算概算，future-work 口径（不预支实验结论）、创新性以"本证据集范围内未见"封顶、预算含"以当年度指南为准"口径；
  4. 步骤 0-2 共 13 条校验命令（UTF-8 校验脚本 + ASCII 调用）：结构完整性/无绝对化断言/占位符/future-work/引用子集 ⊆ registry/used_in 章节精确比对/E2 Crossref 绑定/上游台账存在性。
- **round-1 独立评审 PASS**（0 fatal/0 major/3 minor 措辞级）：评审员独立 curl Crossref 复核 E2 绑定 + 重跑全部校验脚本 + used_in 独立扫描 10/10 MATCH；3 条 minor（R1-F01 两处常识陈述建议补推断标注、R1-F02/F03 coverage_notes 转化措辞偏差）登记待修不阻塞。
- **收官**：comp-review 申报完成（evidence 含真实 subagent_session + provenance rc=0）→ workflow completed + WORKFLOW_REPORT.json → catalog 更新（literature_research/grant_proposal 聚合条目管线级 C2 证据 + intellectual_property_materials/grant-proposal 逐技能 C2 证据；ars-grants NIH 专属保持 experimental）。
- **C6 回归**：新增 tests/test_p3_grant_proposal.py 4 项（模板契约/catalog 合同/管线技能存在/防编造门禁配置），全量 **242 passed**；provenance 全过；skill audit OK（44 模板，template_missing_skill=0）。
- **P1/P2/P3 三条管线全部 C2 闭环**。P2 遗留 2 minor + P3 遗留 3 minor 均已登记 catalog 待修。
