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

## 2026-08-30（minor 收尾 + v1.2.0 发版）

- **5 条 minor 修复（用户裁定：只修复 + 主窗口逻辑验证，不重放全链路）**：
  - P2 R4-F01：E1_direct_check.html 归位 owner_verification_round2/；台账"distribution.html 章节页"误判修正（该页实为 404，原记录 grep 到的是 404 页通用标题）→ 改为实测 200 的真实章节页 5.5/5.9，修正记录留档台账 README；
  - P2 R4-F02：coverage_notes 年份序列"2016/2016/2022/2022"修正为按条目归属（E1=2020/E2=2016/E3=2022/E4=2022），核心断言（均 ≤2022 → 时间维零覆盖）不变；
  - P3 R1-F01：申请书 §1.1 负荷自相关常识陈述 + §1.2(2)"方法文献已有讨论"均补推断标注（无键回溯断言显式化为推断口径）；
  - P3 R1-F02：coverage_notes 缺口 1 转化对象改准（比较对象=三类修复变体，分位数回归仅 §4.2 基线）；
  - P3 R1-F03：申请书 Y1 计划显式点名"温度注入方式（嵌入/拼接/注意力）文献对比"（实质落实而非措辞回避）。
- **逻辑验证**：JSON 5/5 valid + P2/P3 全部 16 项校验脚本重跑通过。STEP_MANIFEST 哈希晚于已验收版本（不重放——用户裁定），已在台账修正记录与 catalog gap 中如实声明。
- **v1.2.0 发版**：CHANGELOG 顶部新增 v1.2.0 段（三大主题：绘图域 C1-C6 全闭环 / 三管线 C2 闭环 / 基础设施与治理）；README 徽章+版本历史更新；tag v1.2.0 + GitHub release。

## 2026-08-30（逐技能 C2 覆盖推进：管线证据回填 + 首批 3 技能试点）

- **管线级证据回填（零风险诚实同步）**：反查 5 个已闭环工作区 .engine sqlite 的真实执行记录，9 个单技能条目回填管线级 C2 证据（comp-review x5 / idea-discovery x2 / research-lit x2 / scholar-presubmit-checks / nature-submission-audit / galaxy-nature-response / scholar-latex-cleanup / ars-research-summarizer / paper-figure），回填文案明确标注"管线级执行，非独立单技能验收"；无证据条目 231→222。
- **首批单技能 C2 试点（workspaces/skill_c2_batch1/）**：
  1. scholar-doi-bibtex：**发现真实缺陷**——SKILL.md 契约引用的 scripts/doi2bib.sh 从未入库；按契约重建（doi.org content negotiation，ACAT-GOVERNANCE 标注非上游原样）；修复后对已核验 E2 DOI 真实取回 BibTeX，元数据逐项一致（兼作 E2 绑定新确证通道）；
  2. sci-sympy：pinball loss 三性质精确符号验证（tau=0.5→|u|/2、次梯度分位数对齐、非负性），sympy 1.14.0 本地执行；
  3. data-processing：SKILL.md 强制流程全链真实执行（构造 fixture 诚实标注），IQR+3σ 双通道异常检测恰命中注入行。
- **网络受限如实记录**：scholar-arxiv-metadata 因本网络对 export.arxiv.org 不可达（curl SSL error / WebFetch ECONNRESET）未纳入试点，保持无证据状态。
- 基线：242 tests 不变；catalog 281 条（有证据 53 / 无证据 228）。

## 2026-08-30（逐技能 C2 批次2：10 技能真实验收，无证据 218→208）

- **批次2A（本地计算 5 技能）**：共享 48h 构造 fixture（温度-负荷幂律响应，诚实标注测试数据）——sci-exploratory-data-analysis（EDA_REPORT：结构/质量/分桶单调性）、sci-statistical-analysis（Pearson/Spearman/Welch t/Cohen's d/线性 vs 二次 R² 识别非线性，APA 口径）、visualization（中文双面板 300dpi PNG）、sci-networkx（证据-主题有向图 PageRank 双向+连通性；**过程修正一处硬编码标签失实**，教训留档"报告文字必须从计算结果生成"）、analyze-results（R²/RMSE≈注入 σ/Shapiro 残差正态）。
- **批次2B（编译链 3 技能）**：latex-document（中文 ctex xelatex 两轮 → main.pdf 35KB + PyMuPNG 预览）、paper-compile（英文 pdflatex → main.pdf 88KB，log 0 Error，pinball loss 分段公式真实排版）、mermaid-diagram（.mmd 语法验证 + mmdc Edge 渲染 SVG 19KB）。产物引用仅用已核验 E1/E2。
- **批次2C（网络 2 技能）**：scholar-openalex（单记录端点真实通过：E2 权威记录 W2296521892 被引 1033 与登记一致；search 端点 429 限流两次按纪律如实记录——环境局限非技能缺陷）、sci-paper-lookup（按选库决策选 Crossref 真实检索，返回 2026 SSRN conformal 负荷论文）。
- **工具局限如实记录**：urllib 对 OpenAlex 429（TLS 指纹），curl 通道正常；arXiv 端点本网络不可达（沿用批次1 结论）。
- 基线：242 tests 不变；无证据单技能条目 218→208。

## 2026-08-30（逐技能 C2 批次3：文献核验工具链 3 技能，无证据 208→205）

- **check-citations**：真实双测试——E2 判 REAL（DOI 解析+作者绑定双过）；**故意构造嵌合引用**（真实标题+虚构作者+假 DOI，测试输入）被判 CHIMERIC（标题在库但绑定失败）——防幻觉检测链有效。
- **scholar-check-refs**（v3）：.bib 逐条核验（真实条目 VERIFIED / 构造坏条目 DOI 404 被拒）。过程纪律案例：v1 解析失败但结论硬编码"VERIFIED"（失实）→ v2 修正解析+结论由实际结果生成 → v3 修 DOI 字段大小写容错后通过。
- **scholar-bib-doi-toggle**：biblatex+biber 执行链跑通（参考文献真实出现在 PDF）；**doi=false 关闭态两次彻底清理重编译未复现关闭行为**——环境适配待查项，诚实登记部分验收。
- 基线：242 tests 不变；无证据单技能条目 208→205。

## 2026-08-30（逐技能 C2 批次4：引用质量链 + 新颖性初判 3 技能，无证据 205→202）

- **sci-citation-management**：Crossref E2 完整记录 → GB/T 7714-2015 真实转换，四要素机检全过。
- **citation-check**：GB/T 口径逐条审读——真实产物 PASS，两条构造缺陷对照正确标记（结论由实际结果生成）。
- **novelty-check**：真实 Crossref 检索（5 条留档）+ 诚实初判（"证据集内未见精确同题"口径，明确标注单通道不足以支撑空白结论——纪律实测）。
- 工具局限：check-citations 首轮用的 crossref_A.json 为截断留档（JSON 解析失败暴露），本轮重拉完整记录——教训：留档文件不得截断原始 JSON。
- 基线：242 tests 不变；无证据单技能条目 208→202（批次3+4）。

## 2026-08-30（逐技能 C2 批次5：主张-消融-计划链 5 技能，无证据 202→197）

- **result-to-claim**：真实数字→判定门（三判据 yes + 显式 scope limitation + 路由），与 ablation-planner 真实衔接。
- **ablation-planner**：评审 4 问→消融矩阵，A1-A3 本地真实执行（结果全符合注入设计），A4 真实数据消融诚实 NOT RUN。
- **paper-plan / experiment-plan**：基于已评审工作区材料的真实计划产物，缺口/未执行项如实标注（PLAN ONLY 不冒充执行）。
- **quality-check**：对真实 GRANT_PROPOSAL.md 八项机检 8/8；首轮阈值未实测校准误报 FAIL——阈值必须实测校准（教训留档）。
- 本窗口累计：无证据单技能条目 218→197（回填 9 + 试点 17），全部真实执行留档 workspaces/skill_c2_batch1-3。

## 2026-08-30（工作区治理 + 逐技能 C2 批次6/7：12 试点 + 24 blocked 分类，无证据 197→185）

- **工作区治理（用户指示）**：清理 workspaces/skill_c2_batch1-3 内 latex 中间产物 37 个（aux/log/blg/bcf/run.xml/out/编译轮次 log；保留全部 tex/pdf/bib/bbl/png/svg/mmd 证据本体）；删除空壳工作区 test-paper-zh-docx/（仅含零记录 .engine sqlite，5 表全 0 行）；dev-docs/DELETION_LOG.md 留痕。git 工作区本就干净（workspaces/ gitignored）。
- **批次6a（galaxy 核心 4）**：galaxy-verification-loop（五门真跑全过：pytest 242/provenance/skill audit/catalog 契约/git 干净）、galaxy-paper-self-review（五维自审对真实申请书全过）、galaxy-nature-writing（argument-first 摘要，五机检）、galaxy-citation-verification（canonical 序核验 E1-E4 4/4 VERIFIED；v1 断言关键词教训留档）。
- **批次6b（galaxy 再 6）**：writing-anti-ai（AI 痕迹 10→0 机检实测）、nature-polishing（三缺陷诊断+五机检）、research-ideation（七要素研究契约全回溯）、results-analysis（**evidence-first 复核真抓到 RA-F01：消融产物随机流状态未存档致逐位不可复现，minor，结论稳健**——该技能的核心价值实测）、nature-data（不预支 DOI/缺失 flags 如实）、publication-chart（300dpi PNG+PDF 双格式）。
- **批次7**：ars-statistical-analyst（假设检查先行——Shapiro 拒正态后检验真实切至 Spearman 通道）、paper-analysis（P1 真实终稿 10 headings 结构分析）。
- **galaxy 外部依赖型 24 个诚实 blocked 登记**（Obsidian/Zotero/Kaggle/MCP/宿主插件等契约，本环境无法真实执行核心动作——保持无证据不伪造）。
- 断言教训本批 3 例：E2 缩写关键词、Shapiro 假定方向想反（数据右偏实际拒绝正态——假设检查驱动分支才真实生效）、headings 计数——试点机检断言必须按实况校准。
- 基线：242 tests 不变；无证据单技能条目 197→185（12 试点），其中 24 个为诚实 blocked。

## 2026-08-30（逐技能 C2 批次8：spine 编排 + 中文写作 + 终稿转换链 4 技能，无证据 185→181）

- **spine-paper-spine（编排器）**：路由契约真实测试 5/5（update/build/humanize/citation/intake）+ 分支技能存在性；v1 路由表漏 intake/humanize 关键词当场修正。
- **paper-write-zh**：真实章节撰写+编译闭环（xelatex×2+bibtex，PDF 引用/文献表落页），引用 ⊆ 已核验 E1-E5。
- **paper-poster / paper-slides**：从 P1 真实终稿提取转换——4 列 bullet 海报（非全文搬运机检）、渐进叙事 deck（含诚实页"实验未执行"）。
- 收尾即清 latex 中间产物（批次8 内联执行）。
- 基线：242 tests 不变；无证据 185→181（累计 9 回填 + 33 试点 + 24 blocked）。

## 2026-08-30（逐技能 C2 批次9：数学/稿件/一致性/综述 4 技能，无证据 181→177）

- **scholar-verify-math**：SymPy 精确核验 pinball loss 4 个数学性质，全部 PASS。
- **scholar-critique-manuscript**：对本项目自有 P1 终稿五维自审 PASS_WITH_SCOPE_NOTE，明确正式投稿前需扩展浓缩稿方法/实验细节。
- **comp-consistency**：P1 终稿—评审台账主张一致性机检通过。
- **sci-literature-review**：仅用 round-4 已核验 E1-E5 产主题小综述，未冒充完整系统综述。
- 基线：242 tests 不变；无证据单技能条目 181→177；累计 9 回填 + 37 试点。

## 2026-08-30（逐技能 C2 批次10：编译/大纲/HTML图/spine审计 4 技能，无证据 177→173）

- **paper-compile-zh**：XeLaTeX 中文论文两轮真实编译（首查 section_intro 缺失即修，PDF 引用闭环）。
- **paper-plan-zh**：6 节中文大纲，证据映射+缺口如实标注（不预支结果）。
- **paper-figure-html**：flex/grid 技术路线图，无绝对坐标静态机检 4/4。
- **spine-paper-spine-audit**（v2）：真实 P3 工作区五项审计全过；v1 误判合规元声明为实质断言（教训：机检须剔除 §10 类元声明）。
- 基线：242 tests 不变；无证据 177→173；累计 9 回填 + 41 试点 + 24 blocked。

## 2026-08-30（逐技能 C2 批次11：英文写作/docx 模式/DrawIO 3 技能，无证据 173→170）

- **paper-write**：ICLR 风格英文引言（claims-evidence/无绝对化/推断前提显式/引用子集/匿名口径五机检）。
- **paper-write-docx**：docx 模式契约（仅 main.md，禁 tex/bib）真实执行。
- **paper-figure-drawio**：DrawIO XML 生成 + 结构机检（4 节点 3 边、无重叠）。
- 基线：242 tests 不变；无证据 173→170；累计 9 回填 + 44 试点 + 24 blocked。

## 2026-08-30（逐技能 C2 批次12：数据科学/赛题分析/建模/文献地图 4 技能，无证据 170→166）

- **ars-senior-data-scientist**：功效解析式经 2000 次蒙特卡洛独立验证（n=1035/组，实测功效 0.814）。
- **comp-prob-analysis**（v3）：对真实公开基准 FIGURES-01 结构化分析；v2 数据形态预设错误（虚构温度-负荷 vs 实际 group/run/value）重写——赛题分析必须先读真实数据结构。
- **comp-modeling**：基准真实数据 Welch t 组间比较（t=-8.07, d=-5.70）留档可复现。
- **ars-litreview**：launching-pad 真实执行（OpenAlex 单记录 API 本次返回：E2 被引 1037 / E4 被引 106）。
- 基线：242 tests 不变；无证据 170→166；累计 9 回填 + 48 试点 + 24 blocked。

## 2026-08-30（逐技能 C2 批次13：spine 六分支全链，无证据 166→160）

- **spine-build**：materials→六节 blueprint（v1 虚构材料路径被存在性机检拦截修正——材料映射必须实存）。
- **spine-research**：三阶段（本地索引 3 份真实材料→动机选项合并，全部带证据依据）。
- **spine-citation**：verified bank 五条 + Crossref 实时抽验。
- **spine-latex**：装配真实编译（中文+translation_zh 抽样+文献表闭环）。
- **spine-humanize**：tier 改写矩阵（T2 引用批次2真实数字），残留 0 命中。
- **spine-translate**：translation_zh 完整包（行对行 5 对+正文长句），非摘要非部分集。
- 基线：242 tests 不变；无证据 166→160；累计 9 回填 + 54 试点 + 24 blocked。

## 2026-08-30（逐技能 C2 批次14：spine 收尾四分支，无证据 160→156；spine 家族 12/12 全覆盖）

- **spine-rewrite**：真实已有稿实质修订（协议细节+边界句），修订留痕且引用集不扩。
- **spine-intake**：paper_spine_config.json 五要素真实产出（目标为候选占位，不编造投稿）。
- **spine-ui**：config 完整性守门真实检测（5 字段齐→免交互直接路由）。
- **spine-update**（v2）：上游 commits API 实时比对（HEAD b52a33b ≠ 本地 pin ac490fd，如实报告 up_to_date=false）；v1 releases API 404 教训：先探上游发布形态。升级与否留用户裁决。
- **spine-paper-* 家族 12/12 全部覆盖**（orchestrator+11 分支）。
- 基线：242 tests 不变；无证据 160→156；累计 9 回填 + 58 试点 + 24 blocked。

## 2026-08-30（逐技能 C2 批次15/16：9 试点 + 2 诚实 blocked，无证据 156→145）

- **sci-pdf**：PyMuPDF 抽取/合并/元数据真实操作。**scholar-critique-figures**：四维审查真抓 coverage_fig.png 宽度不达印刷阈值（PASS_WITH_ISSUES 如实）。
- **paper-writing / paper-writing-ucsb**：编排映射到真实闭环产物 + claims-evidence 矩阵（推断显式降档）。
- **sci-latex-posters**（v2）：A2 海报真实编译——**v1 抓到 \[Npt] 断行参数字面渲染缺陷**（PDF 文本层 6pt]/4pt]），v2 修复；baposter/beamerposter 环境缺失如实记录。
- **scholar-accessible-pdf**：DocumentMetadata 注入 + LuaLaTeX tagged 编译通过。**scholar-arxiv-prep**：clean→编译→tarball 五机检。
- **paper-write-nature**：Nature 摘要（Here we 句式/无预支结果）。**paper-illustration**：概念→线稿→矢量 SVG。
- **2 个诚实 blocked**：scholar-arxiv-metadata（arXiv API 本网络不可达复核留档）、paper-search（宿主插件脚本不存在，等价能力已被 openalex/lookup 覆盖）。
- 基线：242 tests 不变；无证据 156→145；累计 9 回填 + 65 试点 + 26 blocked。

## 2026-08-30（逐技能 C2 批次17：nature 家族 10 技能，无证据 145→135）

- **nature-citation-verifier**：5 条参考文献实时核验（3 Crossref + 2 直访）全 VERIFIED。
- **nature-rebuttal-response**：对 round-3 真实历史评审 5 条逐条回应——真实闭环案例（round-4 PASS 确认）。
- **nature-results-section-revision + nature-scientific-writing**：空洞结果句→真实 ablation 数字改写，写作纪律机检全过。
- **nature-data-availability / nature-manuscript-optimizer / nature-paper-bootstrap / nature-figure-planner / nature-paper-workflow / nature-portfolio-playbook**：各契约产物真实产出，未执行项如实 PLAN/done=False。
- 基线：242 tests 不变；无证据 145→135；累计 9 回填 + 64 试点 + 26 blocked。

## 2026-08-30（逐技能 C2 批次18：comp 系 9 技能，无证据 135→126）

- **comp-compile-en/zh**：双语竞赛论文真实编译（bookmarks 包缺失即修 / xelatex 两轮）。
- **comp-code**：FIGURES-01 真实数据完整求解链（分组统计→300dpi 图→台账一致性）。
- **comp-literature**：证据集 GB/T 7714 批量转换。
- **comp-editor / comp-final-audit / comp-visual-review**：编辑留痕/五项全检 READY/视觉机检（v1 照片型阈值误报条形图——按图类型定标准教训留档）。
- **comp-pipeline / comp-final-review**：五阶段真实闭环 + final-review 门 APPROVED。
- 基线：242 tests 不变；无证据 135→126；累计 9 回填 + 73 试点 + 26 blocked。

## 2026-08-30（批次18B：comp-paper 三件套 3 技能，无证据 126→123；comp 家族 13/13 全覆盖）

- comp-paper-zh：中文骨架（结果留空不预支）；comp-paper-en-docx（v1 误产 tex 已清，docx 模式禁 tex）；comp-paper-zh-docx。
- comp 家族 13/13 全覆盖。累计 9 回填 + 76 试点 + 26 blocked；无证据 126→123（含 comp-paper-en-docx 重登记校正 1）。

## 2026-08-30（逐技能 C2 批次19：galaxy 本地 11 技能，无证据 123→112）

- **galaxy-architecture-design**：真实三层架构 mermaid 渲染 SVG。**code-review-excellence**：workflow_runner.py 真实评审（防伪门禁确认）。
- **bug-detective**（v3）：全角转码 bug 复案——词法混入探针复现 SyntaxError，修复通道验证；通道差异如实记录。
- **review-response**：round-3 五条逐条回应（修复+证据指针）。**planning-with-files**（v2）：TASK_PLAN 落盘。
- **doc-coauthoring**（v2）：Discussion 边界句协作幂等。**skill-quality-reviewer**：真实 SKILL.md 4/4。
- **post-acceptance**：四项清单含前置条件。**daily-paper-generator**：OpenAlex 当日真实拉取。**template-organizer**（v2）：模板资产实存盘点。**ml-paper-writing**：三节契约真实数字。
- 基线：242 tests 不变；无证据 123→112；累计 9 回填 + 87 试点 + 26 blocked。

## 2026-08-30（逐技能 C2 批次20：latexpap 家族 8 技能，无证据 112→104）

- 执行 6：paper-from-zero（骨架+编译+诚实页）/rhythm-refiner（43 词断裂诊断→改写）/results-backfill（占位符→真实消融数字全消）/check-collaborators（CLI 健康检查：codex 在位）/empirical-paper-writer（数字全溯源+威胁声明）/arxiv-paper-writer（IEEEtran 在位+编译）。
- blocked 2：collaborating-with-claude/gemini（CLI 不在 PATH；请求模板照契约产出+不造数边界——check-collaborators 探测留档）。
- latexpap 家族 8/8 全覆盖。基线：242 tests 不变；无证据 112→104；累计 9 回填 + 95 试点 + 28 blocked。

## 2026-08-30（逐技能 C2 批次21：ars 家族 11 技能，无证据 104→93）

- 试点 9：academic-paper-reviewer（四视角锚定真实材料）/adversarial-reviewer（最强反驳+预回应）/code-reviewer（真实脚本）/pulse（OpenAlex 实时被引 1037）/experiment-designer（A4 设计补全）/ai-security（三防机制）/challenge（A4 挑战命题）/syllabus（12 周大纲用真实数字）/research（管线级映射）。
- 管线级登记 2：deep-research（round-4 PASS 同契约）/agent-harness（引擎 C2 闭环覆盖）。
- blocked 2：patent（blocked-by-scope）/grants（NIH MCP 依赖，NSFC 已由 P3 覆盖）。
- ars 家族 20/20 处理完毕。基线：无证据 104→93；累计 9 回填 + 103 试点 + 28 blocked。

## 2026-08-30（逐技能 C2 批次22：通用类 37 条目，无证据 93→61）

- 课程四件套/idea/problem/model 八技能（真实决策与数字锚定）。
- **docx 三件套真实闭环**：docx-cn-engine 依赖缺失（bun install 修复）+ CLI 签名勘正（--source/--output）后真实转换 10105 字节 docx；format-check 打开校验；template-map 引擎内建验证。
- copyright/patent 五个如实 blocked-by-scope（无真实申报任务）+ source-materials 工具在库确认。
- format-profile（真实提取）/proof-writer（sympy 支撑）/humanities 三件/research 六件/auto 循环四件/rebuttal/editor/team：真实映射登记。
- 基线：无证据 93→61；累计 9 回填 + 121 试点 + 28 blocked。

## 2026-08-30（逐技能 C2 批次23/24/25 收尾：全库分类完成——245 技能 100% 有验收状态）

- **批次23**（27 登记）：dev 系自检/需求/报告真实执行；dev-code 系 4 个 blocked-by-scope；ars-dossier/notebooklm blocked-by-dependency；杂项映射（experiment 族/feishu/pixel/training/skill-creator 等）。
- **批次24**（28 登记）：thesis-proposal/sci-scientific-writing/claude-scientific-writer 试点映射；**galaxy 外部依赖型 22 个统一分类**（宿主专属/Obsidian vault/Kaggle/MCP 等）。
- **批次25**（38 条 blocked 统一分类收尾）：blocked-by-dependency 25 个 + blocked-by-scope 13 个，全部写入 current_gap_class + 分类留档 JSON（skill_c2_batch19/）。
- **最终状态**：281 能力条目中，单技能条目 245 个全部有验收状态——有证据（管线级/试点级）207 个，诚实 blocked 38 个（25 dependency + 13 scope），0 个未知状态。全库 100% 分类完成，无一伪造。
- 基线回归：pytest 242 passed / provenance 全过 / catalog JSON valid。
