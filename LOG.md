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

## 2026-08-30（C3/C4 样板工程 + 第一类自主部分，无证据 38→33）

- **C4 样板（第二类首个非 figures 基准）**：benchmarks/cumcm_private/grant_proposal_private/——rubric 六条硬性规范全部对应 round-1 实证教训（无键回断言/转化精确/承诺对齐/阈值实测/元声明豁免/PI 零编造），对真实 grant_proposal_c2 判定 **PASS**（六规范+五维度全过）；C4_VERDICT.json。
- **C3 公开基准 GRANT-01**：benchmarks/six_domains_public/GRANT-01/（contract 8 类机检 + evaluate.py + fixture 证据集/主题简报）；正例（真实 P3 工作区）exit=0、负例 exit=1 判别正确——可复用第二域公开基准。
- **第一类自主部分**：galaxy-obsidian 四技能 **vault 文件级演示验收**（真实 round-4 证据集→5 来源笔记/Home/canvas 四段结构，wikilink 15/FM 8/8；v1 补遗漏 FM；如实标注应用级特性未测）；**pixel-art** 88 像素 SVG 真实生成（7px 网格四机检）。
- 无证据 38→33（5 升级）；剩余 33 全部 blocked（需用户凭证/真实任务/网络）。

## 2026-08-30（批次26 收尾：pixel-art 证据字段更正）

- pixel-art 在批次23 时被误将 blocked 措辞写入 current_evidence 字段（登记错位）；批次26 真实执行（88 像素 SVG）后以正确证据更正。教训：blocked 登记只写 current_gap，evidence 字段只放真实执行证据。
- 当前全库：单技能条目 248 条（210 有证据 + 38 blocked 分类留档，含跨域重复条目）。

## 2026-08-30（逐技能 C2 批次27/28/28B：宿主转化 + 模拟任务，无证据 38→8）

- **宿主转化 5**（用户指令：能转则转、不能转物理清除）：galaxy-command-development/plugin-structure/hook-development/agent-identifier 四个 Claude Code 插件开发指南全部加三宿主对照节（.claude ↔ .zcode ↔ opencode），真实资产验证全过（.zcode/commands/doc-governance.md、.zcode/config.json、.zcode/skills 联结、opencode.json、.opencode/agents/、.opencode/plugins/audit-trail.ts L1 审计插件）；paper-search 重建本地 search.sh（OpenAlex keyless）——v1 cites 排序丢相关性、v2/v3 裸 search 与 filter 语义混入无关高引（实测留档），v4 客户端相关性守卫后全相关。**无清除对象**：全部可转化。
- **误 blocked 重分类 7**：daily-coding（14/14 Conventional Commits）/git-workflow/uv-package-manager（uv 0.11.12 真实探测）/training-check（fixture 曲线检查）/results-report/expression-skill/defuddle（定性：需 JS 包保持 blocked）。
- **模拟任务真实执行 11**：copyright-draft/build（vendored codesucker-core 真实 1453 行 TS 源码说明书草稿 + npm test 五项审计证据）/patent-draft/build（真实技术点 3 条权利要求，外部检索缺失如实声明）/dev-code（"--json 输出"发现功能已在库，真实验证）/前端四技能（poster.html 设计评审 + 真实 HTTP 服务 200 内容断言）/comm-lit-review/dse-loop。
- **批次28B**：galaxy-mcp-integration 试点（.zcode/config.json docsearch MCP 实存）+ 最后 8 凭证依赖类定性留档（Kaggle/NotebookLM/Zotero/CLI×2/skill-development/improver/dossier）。
- **最终状态**：无证据单技能条目 **38→8**（8 个全部为凭证依赖类，需用户侧提供 Kaggle/NotebookLM/Zotero 账号或 CLI 安装）；其余 240 条全部有真实证据或转化/映射登记。
- 工具类缺陷再抓 2：paper-search 三连缺陷（排序丢相关性/裸 search OR 语义/filter 混入）+ os.chdir 后相对路径失效。

## 2026-09-03 技能融入
- **anti-defensive-writing**（Kiterlin/anti-defensive-writing, MIT, pinned 2026-09-03）：防御性写作清理技能融入 academic_papers 域。适配=输入/输出契约三件套+STEP_MANIFEST 声明；首用于 PR 论文 Round 3 对抗审稿。capabilities/catalog.json 已登记。
- **math-modeling-contest-route-selection**（y3519712124-ui, MIT, pinned 2026-09-03）：竞赛选题与路线选择技能融入 math_modeling_competition 域。目录展平+契约适配+STEP_MANIFEST；score_topics.py 冒烟通过；catalog 已登记。

## 2026-09-03 测试口径定稿（关联提交 185eec3/9392e88 补记）
- 仓库根 pytest 333 collection errors 根因修复：releases/ dated 快照与 tools/ 裸脚本 test_*.py 排除出收集范围（pytest.ini norecursedirs），双口径基线定型——仓库根 285 passed / 工具箱 242 passed；catalog 合规修正：anti-defensive-writing 与 math-modeling-contest-route-selection 转技能映射条目（短横线 id），补齐 11 条绘图域欠账映射。条目补记于本日审计时补写（原两次提交未记 LOG）。

## 2026-09-09 全库审计与修复（摸底+排查+图谱+全文档通读）
- **通读覆盖**：247 个 SKILL.md 全文逐份；skills references 全量（shared-scripts 22 份+_utils 同副本 sha256 一致、route-selection 12、ars 25、comp-code 防错、copyright-draft 6、nature-figure 6、dev-code、paper 系、绘图/科研库 seaborn/matplotlib/plotly/sci-visualization/scientific-schematics/infographics/excalidraw/graphviz、diagram-design 55 份）；真源链/engine 13 py+44 模板/tools 60 py/tests 根 3+工具箱 42/benchmarks 两层/governance/ASSET_LEDGER/.opencode 4 子智能体/.zcode 命令/opencode.json/参考论文 4 份分析报告/赛前试炼交付文档/workspaces 结构/releases v1+v1.1 快照 diff 核验（comp-paper-zh 与活体一致、catalog 快照冻结属预期）。
- **垃圾清理**：删 科研工具箱/nul（0 字节）+ tools/QUALITY_REPORT.md/QUALITY_REPORT2.md/tmp_docx（3 份内容相同的 docx_precheck 失败报告，源文件已不存在）。
- **catalog 修复**：34 条 capability 的 associated_skills 家族前缀丢失（42 处替换，如 arxiv-metadata→scholar-arxiv-metadata；含 1 处 typo galaxy-post-acceptment→acceptance 复修）；data-fig-vision-check 移 associated_tools。
- **代码卫生**：workflow_runner.py 删 [DEBUG] stderr 残留；run_logger.py 删 `if False else` 死代码。
- **文档修复**：CHANGELOG.md 行99 截断拼接"现锁## [v1.1.0]"与行112 悬空"定"字；FUNDING.md MIT 矛盾改 CC-BY-NC-4.0+定位扩展全学术；README 徽章/仓库地图/域分布表 245→247、269/281→294、域条目 74/42/33/50；LICENSE 旧目录名"数学建模全流程套件"→科研工具箱、releases 表述、排除节改私有范围口径；truth-index 基线刷为 294/247/44/28-28/双口径测试；工具箱 AGENTS.md 删重复"其他工具"表、路由 grad_project/paper_from_assets 改为管线模板真实 sub_steps（原 skills/ 路径不存在）、工具数 32→60 py+16 pyc；skills/CLAUDE.md 225→247、32→60+16、模板表 comp_full/paper_full 改真实模板名；acat-doc-governance 基线 225→242/285 双口径。
- **防线加固**：tests/test_minimum_catalog.py 新增 test_associated_skills_point_to_real_skill_dirs 反向校验（防悬空引用复发），根级收集 285→286。
- **横幅补齐**：dev-docs notes.md/task_plan.md/VISUAL_REVIEW_REPORT.md/code_appendix_full_report.md/code_appendix_report.md 补"仅供追溯"横幅。
- **回归证据**：仓库根 286 passed；工具箱 242 passed；provenance 28/28；skill audit OK（247 技能/44 模板/template_missing_skill=0）。
- **图谱**：dev-docs/CODE_MAP.md 建立（架构分层+引擎/工具/测试/文档全图+文档覆盖清单）。遗留：m3（resume_candidates 重复候选）仍在但无害；ASSET_LEDGER.md 为 2026-08-13 快照已带过期横幅，刷新需重跑 build_asset_ledger.py（未跑，留待下次发布前）。

## 2026-09-09（补遗：diagram-design type-* 与 vendored 库 API 手册全文补齐）
- 首轮审计中仅做结构抽样的文档已全部补齐为逐行全文通读：diagram-design 40 份 type-*.md 图型规范（swimlane/timeline/state/nested/flowchart/tree/er/layers/venn/pyramid/wardley/dependency/org-chart/deployment/gantt/story-map/db-schema/kanban/journey/uml-class/treemap/fishbone/radar/quadrant/bar/scatter/sequence/polar/line/loop/medallion/data-flow/dp-security-matrix/dp-integration/high-level/it-state/process 全部）；seaborn function_reference(772)/objects_interface(963)/examples(824)；matplotlib api_reference(409)/plot_types(469)/common_issues(562)/styling_guide(600)；plotly plotly-express(213)/graph-objects(302)/export-interactivity(453)/layouts-styling(457)/chart-types(488)；scientific-visualization matplotlib_examples(620)。CODE_MAP.md 第 8 节已更新为 100% 全文覆盖。纯文档补读，无代码/数据改动，测试基线不变（根 286/工具箱 242/provenance 28/28）。

## 2026-09-09（补遗 2：claude-scientific-writer 资产补齐 + 全库内部断链防线 A18）
- **用户指出的遗漏（A18 触发）**：claude-scientific-writer 自 initial public release（7529779）起仅含 SKILL.md 孤本，正文引用的 references/ assets/ scripts/ 全部缺失（342 处引用断链），首轮审计漏报。根因：skill_library_audit 的 REF 正则只查 skills/|tools|engine/ 开头的跨技能引用，不查技能内部相对引用。
- **溯源结论**：该 SKILL.md 是某 Claude.ai 用户定制打包版的孤本路由器（含该用户土尔其语/英语双语约定等个人偏好），其合并版 references/<module>.md 平铺结构在上游 K-Dense-AI/claude-scientific-writer 全部 243 个提交历史中均不存在，资产孤本不可得。
- **修复**：①按先 fork 后集成惯例 fork 上游（FOURTEEN1416/claude-scientific-writer）并克隆 v2.9.1 线 main @ 0c72606；②上游 skills/ 下 15 个对应模块目录（343 文件/约 4.0MB 纯文本）原样拷入本技能 modules/<module>/；③SKILL.md 头部加适配说明块（引用一律按 modules/ 前缀解析+API 依赖口径）；④建 references/UPSTREAM.md 溯源台账（Upstream/Pinned commit/License 三必填字段）并注册进 check_provenance.py UPSTREAM_REGISTRY（28→29）；⑤catalog 该条目 current_gap 补记。
- **防线升级（防复发）**：skill_library_audit.py 新增技能内部引用完整性检查（references|scripts|assets 三标准前缀，前置边界防 subscripts/superscripts 词中伪引用）；豁免三级=ACAT-GOVERNANCE 内联标记/UPSTREAM.md 台账/asset_gap_register.json 棘轮登记册；通配符与 {var} 动态占位符自动豁免。全库现状：512 条内部断链（89 技能，集成时只收 SKILL.md 未收上游资产的存量）固化为棘轮登记册 tools/asset_gap_register.json（2026-09-09 基线），新增断链必 FAIL；547 条断链全部透明豁免（512 棘轮+35 台账）。
- **配套**：tests/test_skill_library_integrity.py 新增 test_no_new_unregistered_broken_inner_refs 棘轮守卫；acat-doc-governance SKILL.md 行 29 流程描述措辞精确化（"建上游溯源台账（UPSTREAM.md，置于技能 references/ 下）"，消除机检误匹配）；512 条处置方案（分层：核心技能补资产/长尾批量声明/维持棘轮）登记于 dev-docs/AUDIT_2026-09-09.md A18 待用户拍板。
- **回归证据**：仓库根 287 passed（+1 棘轮守卫）；工具箱 243 passed（+1）；provenance 29/29；skill audit 无 FAIL（247 技能/44 模板）。

## 2026-09-09（补遗 3：A18 专项治理执行——资产拉取+适应性改造+防线硬化）
- **用户裁决**：执行方案甲专项治理；同时指出拉取的 skills 不应直接复制、需做适应性改造。
- **claude-scientific-writer 适应性改造**：新增 modules/ADAPTATION.md（未随包 11 个兄弟模块的替代映射表：pdf/pptx→宿主 document-skills、parallel-cli/research-lookup→web_search 口径、scientific-schematics/infographics→本仓库同名技能；API 依赖门 §2 显性化 45 处 parallel-cli/16 处 OPENROUTER_API_KEY 降级口径）；15 个模块 SKILL.md 头部注入 ACAT-ADAPTED 横幅（正文零改动保持 pinned 可对照）；主 SKILL.md 适配块与 UPSTREAM.md 同步更新。审计标记体系定稿：ACAT-ADAPTED=适应性改造 / ACAT-GOVERNANCE=断链声明。
- **专项治理七批拉取**（累计 399 文件、销账 219 条）：①sci-* 9 技能←K-Dense scientific-agent-skills@36d8f13（130 文件）；②nature-* 2 技能←Yuan1z0825/nature-skills + scientific-agent-skills + claude-scientific-writer .claude 副本混合（含 SKILL.md 引用名对齐上游真实文件名的引用修正：repository-routing→repository-and-identifiers）；③ars-academic-paper/-reviewer/-pipeline 3 技能←franklee16/academic-research-skills（67 文件）；④skill-creator-official←claude-code-templates 聚合 fork；⑤latex-document 35 条全清←ndpvt-web/latex-document-skill@fb5a159（92 文件，WebSearch 溯源）；⑥latexpap-* 8 技能←yunshenwuchuxun/latex-paper-skills（.codex/skills 单技能目录+共享资产，44/44 全覆盖）；⑦spine-* 11 技能←WUBING2023/PaperSpine（dist/claude 单技能分发，本仓库 11 技能为拆分重组编排，32/33）。溯源手段：GitHub code search（PaperSpine/latex-paper-skills）+ WebSearch（latex-document）+ frontmatter 作者字段。
- **每技能收口四件套**：references/UPSTREAM.md 溯源台账（Upstream/Pinned commit/License 三必填，已注册 provenance 29→63 项）+ SKILL.md 头部 ACAT-ADAPTED 横幅 + 登记册销账 + fork-first 全程遵守（新增 fork：latex-document-skill、PaperSpine、latex-paper-skills、skills-1(anthropics)）。
- **上游不可得批量声明（批次 3）**：galaxy-* 35 技能（GitHub 全网无命中，未公开发布）+ comp-code（checks 六份自检协议为集成期规划未创作，补写属内容创作待专项立项）等共 56 个技能生成 ASSET-GAP.md 缺口声明（清单制：列明缺失资产+原因+处置路径）。
- **防线硬化（两轮验证）**：audit 豁免语义重构——①内联标记（就地精确）→②登记册棘轮（权威存量）→③ASSET-GAP.md 清单制（解析声明文件内 `- \`ref\`` 清单，仅豁免清单内条目）；UPSTREAM.md 台账退出机检（纯溯源文档），claude-scientific-writer 35 条 modules/ 映射口径引用入册永续豁免。注入式防线验证：向 galaxy-bug-detective（有 ASSET-GAP）与 sci-networkx（有台账）各注入假断链→首版被文件级声明兜底豁免（防线打穿）→重构后精确 FAIL→还原 OK。登记册终态 325 条/63 技能。
- **回归证据**：仓库根 287 passed；工具箱 243 passed；provenance 63/63；skill audit OK。工作区改动 208 项未提交（待用户确认）。

## 2026-09-09（补遗 4：赛前全链路实测排查——国赛开赛前最后体检）
- **排查方式升级**：本轮以"实测跑通"为准（此前以读代测），对竞赛主链路（comp-* 家族）逐环节冒烟。
- **环境层全绿**：MiKTeX 全家桶（pdflatex/xelatex/latexmk/bibtex/biber）；Python 竞赛库 11 项（numpy/scipy/sympy/pandas/matplotlib/seaborn/sklearn/statsmodels/networkx/pulp，gurobipy 商业授权缺失可接受，pulp+CBC 兜底）；Graphviz dot（PATH 缺失走全路径，口径与记忆一致）；matplotlib 中文出版图（SimHei）渲染正常。
- **comp-code checks 七份自检协议补写**（此前登记为"集成期规划未创作"的功能残缺，本轮补齐）：_index.md 总索引 + consistency（建模-代码契约）+ sanity_check（数值/背景/Bug 排查+S/G 区段）+ optimization（约束闭环+基线同审+求解分层+结构性验证）+ prediction（泄漏/基线/时序 CV/区间校准）+ evaluation（权重可复现/CR/灵敏度/序保持）+ physical（量纲/守恒/收敛/SAT）。协议定位为编排层：判定标准指向 _utils/error_prevention.md 对应章节（单一真源），产出 _tmp/problem_N_check.md（✅/⚠️/❌）+ AUDIT_OK 凭证。comp-code 断链 8 条全销，登记册 325→317 条/62 技能。
- **compile_check.sh 两个真实 bug 修复（实测暴露）**：①`$(grep -c X f || echo 0)` 毒化——grep -c 无匹配时已输出 0 但退出码 1，`|| echo 0` 拼出两行 "0\n0"，后续全部 [ -gt ] 整数判断报 integer expression expected 且**检查静默失效**（11 处同病）；修法=新增 gcount() 消毒函数统一替换，_utils 与 shared-scripts 双副本同步。②PDF 体积阈值对单页样张误报 "compilation likely failed"——改为以 main.log 的 Output written 判编译成功、页数联合判断，体积仅对 >3 页文档 WARN。修复后 compile_check 退出码语义验证正确（有 FAIL→1、全过→0）。
- **LaTeX 全链实测**：xelatex 中文（ctexart）+ booktabs + 插图 + bibtex 全流程通过（含一次真踩 `\ \midrule` 连写 Misplaced \noalign 坑，属测试文件自身问题，已作为 checks 素材）；**国赛模板 cumcmthesis.cls 实测编译通过**（withoutpreface+bwprint 选项，2 页 PDF）。
- **国赛模板链路断裂修复（本轮最严重发现）**：comp-paper-zh 模板逻辑期望 `_templates/<赛事>/`（tex+cls+fonts 整文件夹），但 11 类赛事模板全部缺失且 cp 带 2>/dev/null 静默跳过——比赛时会拖到编译阶段才炸。修复：①按先 fork 后集成惯例拉取 latexstudio/CUMCMThesis（fork FOURTEEN1416 @ 38d1f21，已适配 2026 格式），cumcmthesis.cls+cumcm2026.sty 入库 `skills/comp-paper-zh/_templates/cumcm/`；②SKILL.md 模板分支尾部加**模板落地断言**（cls/sty 未就位立即 exit 1 并给出国赛内置模板补救路径），其余 10 类赛事模板缺失由静默变显式。
- **mmdc 修复（赛前实测暴露）**：新版 puppeteer 要求 chrome-headless-shell 152，本地缓存仅 148-150 → Edge 固定路径方案（按既有记忆口径）：puppeteer-config.json 就位于 ~/.mmdc/ 与 skills/_utils/ + shared-scripts/ 双副本；mmdc 出图实测通过；mermaid-diagram SKILL.md 已回写 `-p` 参数 Windows 口径。
- **已知环境注意事项（写入赛前报告）**：管理员（elevated）终端下 MiKTeX 的 kpsewhich 拒绝执行（security risk 保护），xelatex/latexmk 实测不受影响；建议竞赛期间使用普通权限终端。
- **回归证据**：仓库根 287 passed；工具箱 243 passed；provenance 63/63；skill audit OK；compile_check 冒烟全绿。工作区改动未提交（累计待用户确认）。

## 2026-09-09（补遗 5：赛时运行时工具链实测——审计闸/写作流脚本/引擎编排层）
- **comp-code 审计工具链冒烟全通**：capability_check.py（无清单优雅跳过）+ 6 个 Python 审计工具（capability_audit/claim_code_check/facts_audit/leakage_audit/data_ingest_check/delivery_audit 语法与行为）+ count_subproblems.sh。**claim_code_check 正反四路实测**：内置安全网正向（LpVariable 命中→pass）/反向（linprog 冒充整数规划→HARD FAIL 精确指认）；通用合同正向（M1|must|forbid 管道格式→pass）/反向（must 缺失+forbid 命中双 FAIL）。capability_check 按契约拦截缺 falsifiable_check 的 machine 项。
- **compile_utils.sh / writing_check.sh 冒烟**：编译前清理/封面 cline 自动修复/图片路径规整与图文交织/引用核验/占位符/AI 痕迹等检查项全通（exit 0）。
- **engine 编排层端到端实测（7 轮迭代走通）**：start(comp_cumcm)→next(路由 comp-prob-analysis 含 checkpoint 语义)→complete 证据链。证据 schema 逐层拦截实测：缺字段→schema_version 类型（须整数 1 非字符串）→commands 须对象数组→returncode 须整数 0→outputs 须与 artifacts 一致→防描述性命令→skill_sha256 须匹配→quality gate min_size（comp-prob-analysis=1500B）→全过后 checkpoint 等待→推进 comp-literature。失败步骤锁定不推进（防跳闸语义正确）。
- **AGENTS.md 补 workflow_cli complete 合规证据样例**（赛时照抄即用，避免 agent 赛时多轮被拒）。
- **回归**：audit OK；工具链实测全部通过；工作区清理（保留 paper/cumcm_smoke 编译样例）。

## 2026-09-09（独立审计 → 全量修复）

- **动作**：按无上下文独立审计报告（`dev-docs/INDEPENDENT_AUDIT_REPORT_2026-09-09.md`，P0×1/P1×4/P2×3/P3×3 + 新发现 .pyc 调用面断裂）执行全量修复：①`cumcmthesis.cls` 包序（booktabs 移到 bigstrut/bigdelim 后）修复三线表编译中断 P0，补 `_templates/cumcm/main.tex` 编译验证骨架并登记 UPSTREAM 本地补丁；②`compile_check.sh` 增 `^! ` 硬错误检测+真实 undefined 判据（旧 `\[?\]` 恒 0）；③`workflow_runner.next_action` 增 blocked-checkpoint 硬闸（未 approve 不得推进）；④机检 INNER_REF 扩展 `_utils/shared-scripts` 前缀并修复全库暴露的 17 处真断链（`.pyc` 直调教学全部改为 `.py` 真源 + 防回归测试）；⑤comp-paper-zh/comp-compile-zh 模板死声称修正（5 套 main.tex/huazhong 字体不实声称改现状口径，8 条死路径对比循环改动态探测）；⑥双副本 claim_code_check 同步 + `test_dual_copy_consistency` hash 级防线；⑦mermaid 命令模板补 `-p` 探测、graphviz Windows dot 指引、provenance URL 源强制哈希（正反测试）、`check_review_evidence` reason 遮蔽 bug 修复；⑧README/AGENTS 数字定稿（247/291/294/63）。
- **原因**：用户在审计报告交付后裁定：所有问题全部修复，未验证事项全部补齐，不推诿不遗漏。
- **结果**：修复过程再暴露并处理两个审计未见问题——16 个 `.pyc` 实为 3.11 字节码（本机 3.12 直跑必炸，AGENTS"加密分发件"措辞不实）；review 门禁 strict 在 ZCode 宿主正确拒绝不可达配置模型 mimo-v2.5-free（非绕过）。未验证项 ①②③④⑤⑦ 全部补齐：LLM 真实调用 OK（reviewer/gpt_image 生图/doc_reader/真实 sensenova 终审 fatal=0）、drawio CLI 导出 98KB PNG、L1 插件在位、releases 结构完整、62 篇论文报告符实。
- **验证**：工具箱 `pytest -q` **247 passed**、根 **291 passed**（含 4 项新防线测试）；`skill_library_audit`/`check_provenance` 双 exit 0（63/63）；booktabs 三线表+longtable 教学格式编译全绿；compile_check 正路 exit 0/断表盲工程 exit 1（修前 0）；引擎 blocked 硬闸 CLI 实测（CUMCM 14 步驱动：0-11 全过含 4 次 approve + step9 真实编译 rc=0 + step13 final-audit 独立验证全绿）；A5/双副本/`.pyc`/provenance 四条新防线均做注入破坏反验。

## 2026-09-09（v1.2.2 · ZCode 赛时主控 + 模型去预设）

- **动作**：按用户裁定执行三项——①中断遗漏检查：复跑全套基线（247/291→确认无回退）+ 审计报告发现×commit 核销，捕获残留 README:148 `28/28` 过期数字与审计驱动脚本未入库两处；②模型去预设：新增 `engine/modex-core/contest_models.json` 配置槽（出厂全空）、`load_configured_role_models` 三级宿主中立解析+`model_config_provenance`、strict 未配置显式 warn、`doc_reader`/`tikz_vision_check`/`pyc_loader` 去厂商默认值、comp-visual-review/infographics/scientific-schematics SKILL 与 README/工具箱 AGENTS 措辞同步；③ZCode 主控兼容：`hooks/zcode_audit_l1.py`（PreToolUse/PostToolUse/Failure → operations.jsonl 同格式 + `git add .` 治理拦截）经 `.zcode/config.json` hooks 注册（enabled+三事件，入 git 随仓分发），宿主矩阵/三层审计表/独立性契约测试演化，审计降级句全库清除；④`tools/contest_dryrun/` 审计驱动通用化入库（--ws/--wf/--fig 参数化，冒烟揪出 figures 目录缺失与 datetime.date 误用两个真 bug 并修复验证）。
- **原因**：比赛将以 ZCode 为主控；模型（含视觉）比赛时再配置（示例 GLM 视觉系列），仓库任何预设都是风险源。
- **结果**：ZCode 下 L1 审计自本日起不再是降级项；OpenCode 生产行为不变（配置槽空→agents 回退复证一致）；hook 配置改动需重启会话生效（当前会话仅脚本级实测+12 项测试，宿主触发待新会话复验）。
- **验证**：新增 `test_zcode_host_compat.py` 12 项（三级解析/strict 联动含正反/hook 五态含 deny 留痕/注册契约）全绿；hook 六态 CLI 实测 + `AuditStore.stats` 真读兼容；`chain_driver.py` 全新工作区实跑 step0-3（checkpoint 硬闸×2 approve、真实 pulp 求解、matplotlib 生图、review 步按设计等待）；终局基线 工具箱 **259** / 根 **303**，provenance 63/63、skill_library_audit OK exit 0。

## 2026-09-09（补遗 6：hook 锁死事故修复 fail-open + figures4papers 收编）

- **锁死事故根因定案与修复**：上会话 shell 持久 cwd 漂到 `科研工具箱/skills/` 后全会话硬断，根因是**宿主 hook 语义（exit 2=deny）与 Windows python 找不到脚本的退出码（恰为 2）撞车**——hook 进程层故障被误读成规则拦截。修复三件：①`hooks/zcode_audit_l1.py` 新增 `_cli()` fail-open 入口（main() 崩溃→stderr 警告+exit 0，exit 2 唯一出口=规则拦截且必留痕 permission/deny 事件），头部注释固化设计铁律；②`.zcode/config.json` 按 `zcode-guide:diagnosing-hooks` 官方 schema 净化——删 hook 级 `enabled` 字段（process 白名单仅 command/args/timeoutMs/statusMessage，混入即整 hook 被宿主静默丢弃），保留 `${ZCODE_PROJECT_DIR}` 绝对展开+无 matcher（官方语义=匹配全部）；③契约测试扩 12→20 项：恶意输入 fuzz×4、内部崩溃注入（断言 stderr 含 fail-open）、**仓库外 cwd 放行实测**（锁死场景复现）、config 字段白名单、脚本路径项目根锚定。
- **验证**：契约测试 20/20；锁死现场还原实测 5 场景全对（仓库外 cwd 放行/git add . 拦截 rc=2+理由/锁死 cwd 放行/崩溃 fail-open/审计落账 2 tool_call+1 permission）。宿主层 hook 触发按惯例待仓库内新会话复验。
- **figures4papers 收编（先 Fork 后集成）**：fork ChenLiu-1996/figures4papers → FOURTEEN1416/figures4papers，pinned `3c181f8`（2026-09-06），License 核实为 **CC BY-NC-4.0**（LICENSE 原文；API NOASSERTION 不准）。落地 `skills/paper-figure/references/`：`semantic-palette.md`（颜色→数据角色语义映射+顶刊 PALETTE+消融 alpha 梯度）+ `composition-patterns.md`（构图五模式），UPSTREAM.md 登记并注册 `check_provenance.py`（63→64），SKILL.md Tools and Style 段挂引用防孤儿文件。对比 grep 结论：hatch 全库零覆盖系独有增量；图例面板/灰度现有仅检查规则层，收编件补"怎么构图"知识层，与 figure_style_guide 互补。
- **原因**：用户裁定锁死修复第一优先防复发 + 续执行上会话批准的收割清单。
- **网络路径留痕**：git clone 直连 GitHub 超时、本地代理 127.0.0.1:3128 已死，改走 `gh api repos/<owner>/<repo>/tarball/<sha>` 取源成功（后续同类操作复用）。
- **回归**：工具箱 pytest **267 passed**（基线 259+新增 8 防线）、仓库根 **311 passed**（基线 303+8）、check_provenance **64/64** exit 0。改动均未提交，累计待用户确认。

## 2026-09-10（三图裁定 + hook 二次锁死解锁收尾 · junction 用后即拆）

- **解锁路径定案**：sess_a4bf7993 二次触发 hook 锁死（Bash cd 漂入 `vendor/forks/figures4papers`，旧配置相对路径在该 cwd 下解析失败→python 退出码 2=deny→全通道阻断；盘上 config 已修但该会话宿主进程未重载，软重启无效）。本会话新起后工具通道全部恢复；开局曾按上会话交接建临时 junction `vendor/forks/figures4papers/科研工具箱 → 科研工具箱`（变通方案 B），确认 config 三处 args 均为 `${ZCODE_PROJECT_DIR}` 绝对展开+hook 脚本 `_cli()` fail-open 在位后 `rmdir` 拆除，dir 复核无残留。P1 教训重申：**全程绝对路径，绝不 cd 出仓库根**（该会话此教训已固化至工作区记忆 zcode-hook-exit2-lockup-lesson）。
- **上游核对**：本地 pin `3c181f8` == 上游 ChenLiu-1996/figures4papers main HEAD（compare API：identical，0 ahead/0 behind），fork 推送时间与上游一致——**无需更新**。
- **三图裁定**（用户质疑"三图连排有很大问题，为什么要？"）：逐字通读上游 scientific-figure-making 四份文档（SKILL.md 38 行+common-patterns 74+design-theory 138+tutorials 135，共 385 行）+14 种模式 grep——**上游无"三图连排"硬性规定**。唯一 "1×3" 在 tutorials.md:55（Tutorial 2），第三格是图例专用面板（:79-81 `set_axis_off()`），同句给 "or 2×2" 替代，系"2 数据面板+1 图例面板"示例布局被二手转述成规则。上游真实规则三条均有适用前提：超宽横排=仅多指标对比（common-patterns.md:7-13；(45,12) 级极端画布在国赛 170-180mm 版面必跌破 7-9pt 字号下限，不采纳其极端尺寸）；图例独立面板=仅当图例压数据（:17-25）；同行一致性=约束已连排面板（design-theory.md:64）。**裁定：不采纳"固定三图连排"；`skills/paper-figure/references/composition-patterns.md` 构图五模式维持不变**（超宽面板/独立图例面板本在列），适用前提记入工作区记忆，不改任何文件。
- **销旧账确认**：上会话 3 个待补验 grep（hatch/图例面板/灰度先例）已在补遗 6 记录结论，本轮复核 `.engine/audit/operations.jsonl` 留痕（sess_86a453b5 grep 命令实跑）确认已执行，无需重做。
- **记忆回流**：工作区新增 3 条（three-panel-row-ruling / okabe-ito-data-palette / contest-concept-figure-colors）+ MEMORY.md 索引同步 + 收编记忆互链 + Mem0 shared 回流（首次调用 30s 超时，重试）。
- **验证**：junction 拆除后 `dir` 复核；上游 compare API 返回 identical；裁定证据全部带 文件:行号；本条 LOG 即落账凭证。改动仍均未提交，累计待用户确认。

## 2026-09-10（补遗：三图连排独立复核 + 收尾会话补账）

- **背景**：研究型会话（sess_a4bf7993 之后的延续）曾因 hook P1 再次锁死（其时修复未重载）；真重启后 hook 正常注入（SessionStart/UserPromptSubmit 均跑通），本轮以绝对路径完成剩余核对。
- **上游逐字复核（独立第三遍，验证前会话结论）**：`vendor/forks/figures4papers/scientific-figure-making/` 四文件全文通读（SKILL.md 38 行 / common-patterns 74 / design-theory 138 / tutorials 135）+ 14 种连排表述 grep，**确认上游无"一行三图"硬规定**——唯一 "1×3" 在 tutorials.md:55（Tutorial 2 的图例专用面板，:79-81 `set_axis_off()`，同句给 "or 2×2" 替代）；超宽横排仅适用于多指标对比（common-patterns.md:7-13）；同行一致性规则在 design-theory.md:64。裁定与 09-10 主记录一致：**不采纳固定三图连排，composition-patterns.md 构图五模式维持不变**；潜在修法（超宽面板加"印刷宽度下每面板 ≥45mm"前置条件）仍待用户给方向，本轮未改任何技能文件。
- **旧账销清复核**：上会话 3 个待补验 grep（hatch/图例面板/灰度先例）本会话重跑确认：hatch 已在 paper-figure 三件（SKILL.md / semantic-palette / composition-patterns）；bbox_to_anchor 图例外挪先例 figure_style_guide.md:347；灰度要求 SKILL.md:71。
- **记忆修正**：①figure-style-external-inputs.md（前会话已建但漏索引）补进 MEMORY.md；②figures4papers-evaluation.md 三图段由"核对未完成"改定稿口径（含文件:行号证据）；③MEMORY.md 中 pre-competition-pipeline-facts 行已是"✅P1 已修复"现状（前会话已更新，本轮无需再动）。
- **验证**：本轮 cwd 始终在仓库根（pwd 复核），零 cd 操作；grep/Read 全程绝对路径；hook 正常注入未拦截；本条 LOG 即落账凭证。改动均未提交，累计待用户确认。

## 2026-09-10（外部配色/三图裁定按用户方向落地 + hook 锁死新变体实证）

- **动作（用户裁定"按照推荐方向推进"）**：①`paper-figure/references/composition-patterns.md` 模式一补"印刷宽度前置条件"（⛔ 段：仅当最终印刷宽度÷面板数 ≥45mm 才 1×N 连排，否则 2×2/1×2 堆叠；注明与 SKILL.md "每 panel ≥0.45\textwidth" 守卫同源）；②`semantic-palette.md` 增 §五交叉校验调色板（5.1 Okabe-Ito 数据图实践组合全色值表+配套原则；5.2 国赛概念图写死配色并划死"仅限概念图禁用于数据图"边界；两套均标注"非上游内容/未经赛事实证/冲突时以本库 elegant 板为准"）；③`paper-figure/SKILL.md` 增"外部规范红线"段（概念图/数据图分家、AI 生图禁假坐标轴假精度数字、生成后逐字自检+九段线红线、打印安全三件套、图表门禁提醒归 paper-write 侧）；④`UPSTREAM.md` Local adaptation 补第⑤条登记全部增补及其非上游来源。
- **AI 申报生成器**：按推荐只做立项评估不入库（机会与红线已存工作区记忆 figure-style-external-inputs.md）。
- **验证**：工具箱 pytest **267 passed**；仓库根 **311 passed**；check_provenance **64/64 exit 0**；skill_library_audit OK（316 条）。
- **⚠️hook 锁死新变体（重要实证，推翻"P1 已修复"的覆盖口径）**：本轮 `cd 科研工具箱 && pytest` 成功执行后持久 cwd 停在仓库子目录，下一条起 hook 路径**双重拼接**（`科研工具箱/科研工具箱/hooks/zcode_audit_l1.py`）→ 全工具再次硬阻断不可自愈（cd 回根也被拦）。结论：`${ZCODE_PROJECT_DIR}` 修复只防"漂出仓库"（前会话 cd /tmp 实测正常），**漂进仓库子目录时照样锁死**——路径解析跟随 cwd 拼接。修复方向（待办）：zcode_audit_l1.py 定位逻辑改为"沿 cwd 向上找项目根锚定"或 config 用绝对路径硬编码兜底。本轮经临时 junction `科研工具箱/科研工具箱 → 科研工具箱` 解锁（用户会话外执行），验证后待拆除。
- **纪律重申（升级版）**：Bash 命令**一律禁止 cd**（含"进子目录跑完再回来"的写法），需要子目录上下文时用 `python -m pytest 科研工具箱/` 式根目录相对路径或绝对路径直跑。
- **记忆回流**：figures4papers-evaluation（三图裁定定稿）、figure-style-external-inputs（索引补录）、MEMORY.md 索引同步、pre-competition-pipeline-facts（P1 覆盖口径修正）——本条 LOG 与记忆互为凭证。改动均未提交，累计待用户确认。

## 2026-09-10（hook 根治方案实施：python -c 内联引导器 · 进程级三场景实测通过）

- **动作（用户批准设计，本会话 sess_86a453b5 延续实施）**：①`.zcode/config.json` 三事件 args 改为 `python -c <内联引导器> <mode>`——引导器定位顺序=`ZCODE_PROJECT_DIR`/`CLAUDE_PROJECT_DIR` env → 从 cwd 逐级上溯找 `科研工具箱/hooks/zcode_audit_l1.py`，找到后 `runpy.run_path` 执行（SystemExit 透传，deny=exit 2 保真）；定位失败/执行异常一律 stderr 警告 + exit 0 放行；config 保持随仓可移植（引导器禁盘符硬编码，契约测试把守）。②契约测试改版：废弃 `${ZCODE_PROJECT_DIR}` 路径锚定断言（已被三次锁死证伪），新增 `test_zcode_config_uses_inline_bootstrap`（-c/runpy/env 探测/cwd 上溯/fail-open/禁绝对路径六断言）+ 三条行为回归（伪仓库子目录 cwd 定位并落账 / 子目录 cwd 下 `git add -A` deny exit2 透传+留痕 / 仓库外 cwd fail-open 警告），compat 套件 23 全绿。
- **根因定案补全（两会话证据合并）**：宿主支持 `${VAR}` 展开语法但 `ZCODE_PROJECT_DIR` 不在 hook 进程环境→**静默展开为空**→arg 退化纯相对路径按 shell cwd 拼接（漂出仓库=找不到脚本；漂进仓库子目录=双重拼接，同一机制两变体）；且宿主 cwd 自动重置**只对项目外路径生效**（cd /tmp 触发重置、cd vendor/forks 不触发）——故变量式与"重置兜底"双双无效，只有把定位搬进 python 内部才根治。
- **中途纠偏**：实施曾先行落盘"config 绝对路径"方案，与已批准的可移植设计冲突，已被本引导器取代（未入库即纠正；绝对路径作为本会话过渡态短暂存在，无遗留）。
- **清理**：并行会话遗留临时自指 junction `科研工具箱/科研工具箱` 已 `rmdir` 拆除（复核无残留，目标本体完好）。
- **验证**：进程级三场景冒烟全对——①`cwd=科研工具箱`+正常载荷 rc=0 且 operations.jsonl 落账 tool_call；②同 cwd+`git add .` rc=2+治理理由 stderr+permission/deny 留痕；③系统临时目录+无 env rc=0+"定位失败"fail-open 警告。全量基线：工具箱 **270 passed**（259+前会话 8 防线+本轮 3 回归）、仓库根 **314 passed**、check_provenance 64/64 exit 0。**宿主层（真 hook 触发）待重启会话复验**，协议：cd 进仓库子目录后任意工具调用须正常 + git add . 拦截 + 落账实时。
- **内容更正**：`composition-patterns.md:56` "hatch 全库零覆盖系独有增量"表述有误（`matplotlib/SKILL.md:301` 与 `references/plot_types.md:115` 均有 hatch 覆盖，前会话查重漏检）→ 改为"决策打包"口径（技法非独有，价值在何时用/怎么组合/与门禁衔接）。
- **遗留待用户处理**：`科研工具箱/tools/QUALITY_REPORT.md` 为无关项目（AI 陪伴应用 docx）的陈旧质检产物（源文件已不存在），未入库，建议删除或移出仓库（等方向）；figures4papers 研究收尾三项（上游精读补全/五模式先例补验/第 3 项收割落地）待重启后继续。

## 2026-09-10（脚本定位层根治 · 复核补账：config 恢复注册 + docstring 铁律改写 + 全量复验）

- **背景**：上一条"根治方案实施"（sess_86a453b5）落定引导器形态后，`.zcode/config.json` 工作区又出现一笔未提交改动——整段删除 hooks 注册仅剩 mcp（对应同日"清除项目 hook 注册待复验"的临时裁定）。本条按任务书完成收尾复核：恢复注册、补齐脚本内文档、全量复验。
- **动作**：①`git checkout HEAD -- .zcode/config.json` 恢复三事件 `-c` 引导器注册（内容与 `64dbd56` 定稿一致，`python -m json.tool` 校验合法）；②`zcode_audit_l1.py` docstring 设计铁律段改写：原第 2 条仍写"${ZCODE_PROJECT_DIR} 绝对展开堵死"——该口径已被 09-10 双重拼接事故证伪，替换为"引导器层 fail-open"完整原理（-c 进程永启、定位搬进 python、env→cwd 逐级上溯双通道、任何失败 stderr+exit 0、exit 2 唯一来源 _DENY_RULES）+ 双 cwd 故障史逐案注记；`_audit_dir` env 优先 + `__file__` 回退现状确认未破坏。
- **验证（全部本会话实跑）**：工具箱 pytest **270 passed**（267 基线+3 引导器回归）、仓库根 **314 passed**（311+3）、compat 契约套件 23 全绿（含 -c 六断言与三场景回归）；`check_provenance.py` **64/64 exit 0**；`skill_library_audit.py` **OK**。手动正反验证 14 项全对：三 mode（pre/post/fail）经引导器落账各 1 条 tool_call/tool_result；`cwd=科研工具箱` 子目录无 env 上溯定位成功落账（双重拼接事故场景不锁死）；`git add .` 经引导器 **rc=2** + stderr 治理理由 + permission/deny 留痕（拦截未被架空）；系统 tmpdir 无仓库 **rc=0** + stderr"定位失败"警告（fail-open）。全程零 shell cd（子目录上下文以进程内 chdir 一次性驱动，持久 cwd 未动）。
- **junction 复核**：`dir 科研工具箱` 无 `科研工具箱/科研工具箱` 自指 junction——上条会话已 `rmdir` 拆除，本会话二次确认，**无需再拆**，任务书该项待办销账。
- **⚠️宿主层最终验证待新会话（本会话改动未生效于宿主进程）**：重启会话后协议三条——①cd 进 `科研工具箱/` 后跑任意工具应正常不锁死；②`git add .` 应被拦截 exit 2；③`.engine/audit/operations.jsonl` 应实时新增落账行。三条全过即 P1 根治闭环，记忆档同步销项。
- **提交状态**：改动=config（恢复，与 HEAD 一致故实际零 diff）+ `zcode_audit_l1.py` docstring + 本条 LOG，均未提交待用户确认。

## 2026-09-10（终态裁定：hooks 保持清除态 · 引导器契约冻结于 git 定稿版）

- **裁定（用户，紧接上条）**："保持清除状态"——推翻本会话早前的恢复注册动作：`.zcode/config.json` 工作区回退为**仅 mcp、hooks 块删除**（`json.tool` 校验合法）。引导器根治定稿**冻结在 git `64dbd56`**，脚本本体 `zcode_audit_l1.py`（含本会话 docstring 铁律改写）与全部契约测试保留在库，随时可按定稿形态重新注册启用。
- **测试连带演化**（避免"清除态=测试红"的假回归）：D 段注册契约新增 `_hook_contract_cfg()` 配置源解析——工作区含 hooks 块则活契约直校（注册错了必红）；清除态则回退 `git show HEAD:.zcode/config.json` 校定稿形态；两处皆无则 skip。行为类回归（子目录定位/deny 透传/fail-open）随 `_bootstrap_code()` 一并吃到定稿源，未删任何断言。
- **复验（清除态下全部重跑）**：compat 契约 **23 passed**；工具箱 **270 passed**、仓库根 **314 passed**；从 git HEAD 提取定稿引导器冒烟三场景全对（子目录 cwd 定位落账 rc=0 / `git add .` rc=2+deny 留痕 / tmpdir fail-open+警告）。
- **宿主影响**：当前及新会话均**无 L1 hook**（清除态生效）——审计回到 L2+L3 交叉比对兜底；禁 cd 纪律在重注册前不再由 hook 强制，但"绝对路径操作仓库"好习惯维持。若赛前决定启用 L1：恢复 HEAD 版 hooks 块（或 git revert 本笔清除改动）→ 重启会话 → 按上条三条复验协议走一遍。
- **提交状态**：`M .zcode/config.json`（清除态，相对 HEAD 删 hooks 块）+ `M LOG.md` + `M 科研工具箱/hooks/zcode_audit_l1.py`（docstring）+ `M 科研工具箱/tests/test_zcode_host_compat.py`（契约源演化），均未提交待用户确认。

## 2026-09-10（清除执行收尾：清除态入库 + 陈旧产物 QUALITY_REPORT 删除）

- **执行（用户指令"进行清除"）**：①用户确认清除态四件套（config 清除/脚本 docstring 铁律改写/契约测试演化/前两条 LOG 补记）入库；②`科研工具箱/tools/QUALITY_REPORT.md` 删除——删除前全文读完（11 行，无关项目"AI 陪伴应用 docx"的陈旧质检产物，源文件不存在且不可再生，属误落仓库的临时工具输出）；该文件为 untracked 态，直接 rm 无 git rm 需要。
- **提交前复验（本会话实跑）**：工具箱 **270 passed**、仓库根 **314 passed**（清除态下契约测试经 `git show HEAD` 回退校验定稿形态，全部自洽）。
- **锁死问题闭环声明**：三层解决——技术根治（引导器定稿冒烟三场景全对，冻结于 `64dbd56`）+ 运行时清除（当前无 L1 hook，锁死机制不存在）+ 活体复证（新会话 cd 进 `vendor/forks/figures4papers` 历史事故现场并返回，畅通无阻）。重注册路径：恢复 `64dbd56` 形态 → 重启会话 → 三条复验协议（子目录工具正常/git add . 拦截/落账实时）。
- **figures4papers 研究收尾三项**（上游精读补全/五模式先例补验/第 3 项收割写法范式→acat-doc-governance）待后续会话，fork 本地克隆在 `vendor/forks/figures4papers`（pinned `3c181f8`）随时可续。

## 2026-09-10（figures4papers 收割收官：第 3 项写法范式落地 acat-doc-governance）

- **动作**：①新建 `skills/acat-doc-governance/references/skill-writing-paradigm.md`（37 行）——上游 SKILL.md 写法范式归纳为治理四维度：**超薄主入口**（≤60 行经验参照/100 行硬红线，超线先下沉不先删内容）/**渐进披露**（显式"按需打开禁止预载"+每份下沉件一行 Open when 路由）/**双向适用边界**（When to load / When not to load 成对，只写"何时用"不写"何时不用"的标记补齐）/**单主题切分**（一份 reference 管一题，30~150 行量级，重叠即合并候选）；附治理用法（结构问题归 P3，不阻塞 P0/P1 内容处置）与整改模板。②主文件挂钩：加 5 行范式路由段 + description 补"技能/长文档结构评估"定位。③自清污染：主文件常用命令段陈旧基线 242/285、28/28 更正为 **270/314、64/64**（治理技能自身数字过期，正好撞自家铁律 2"过期声明必须处置"枪口）。④吃自己的狗粮：范式本体下沉 references（37 行），主文件仅 68 行——范式样例即本次改造本身，可引为治理对照样本。
- **来源**：figures4papers `scientific-figure-making/SKILL.md` @ `3c181f8`（CC BY-NC-4.0；溯源已在 paper-figure/references/UPSTREAM.md 登记，台账 64 条，本件引用不新增登记）。
- **验证**：主文件 68 行/参考件 37 行；工具箱 pytest **264 passed + 6 skipped**——6 skip 为**设计内**：清除态入库（`2a86b6c`）后 HEAD config 亦无 hooks 块，D 段注册契约按 `_hook_contract_cfg()` 三级解析走"皆无→skip"，非回归（compat 单套 17+6 复核一致，行为回归未删）；provenance **64 OK**。**至此 figures4papers 三项收割全部落地**（语义调色板/构图五模式/写法范式），评估任务闭环。
