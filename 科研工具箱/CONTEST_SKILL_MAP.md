# CUMCM 竞赛技能全库地图（CONTEST_SKILL_MAP）

> **定位**：全库 257 个技能 × comp_cumcm 14 步工作流的推荐地图。引擎 StepAction 的
> `companion_skills` 字段（2026-09-11 起）每步主动给出本步推荐；本文件是全量真源，
> 含"情境可用"、"外域不接入"与"未接入库"的完整分类账——**任何一个技能都不允许处于"无人知晓"状态**。
> 维护纪律：新增技能入库时必须归入下列五类之一并同步本文件与引擎
> `engine/modex-core/templates.json` 对应步骤（两处同改，防"地图在册、StepAction 不荐"漂移）。
> 零漏网对账已固化为机检：`python tools/check_asset_utilization.py --strict`
> （2026-09-12 起，tests/test_asset_utilization.py 随 pytest 护航）。
> 非技能资产（数据/参考论文/工具脚本/参考图集）由 StepAction 的 `assets` 字段按步暴露
> （2026-09-12 C2 资产机制，同 templates.json 维护），本文件只记技能。

## 使用规则

1. 每步开工：看 StepAction 的 `companion_skills`，按需加载 **1-3 个**（宁缺勿滥，防上下文噪音）。
2. **强制申报（C1 闸，2026-09-11）**：complete 时 evidence 必须含 `companion_skills` 字段——
   `{"used": [...], "skipped": [{"skill": ..., "reason": 非空理由}]}`，恰好覆盖本步推荐清单；
   引擎硬校验，缺申报/覆盖不全 = 步骤失败。**申报 ≠ 强制使用，但"不用"必须留痕给理由**。
3. 辅助技能的产出与结论照常走留痕纪律（来源进产物、检索留证据）。
4. 辅助技能与主技能口径冲突时，以主技能 SKILL.md 为准（主技能是门禁责任人）。
5. 外域类与未接入库类（§四/§五）赛时**不要**为"用而用"地加载；§五未接入库技能确需使用时按情境技能对待并照常留痕。

## 一、主链家族（20 个）

14 步主技能：`comp-prob-analysis` → `comp-literature` → `comp-modeling` → `comp-code` →
`paper-figure` → `paper-figure-drawio` → `comp-review` → `comp-paper-zh` → `comp-consistency` →
`comp-compile-zh` → `comp-visual-review` → `comp-editor` → `comp-final-review` → `comp-final-audit`。
编排器与变体：`comp-pipeline`（8 阶段轻量编排）、`comp-paper-en`/`comp-paper-en-docx`/`comp-paper-zh-docx`（语言/格式变体）、`comp-compile-en`（英文编译）、`comp-stats-topic`（统计建模赛专用模板）。

## 二、每步推荐（StepAction.companion_skills 同步给出）

> **2026-09-12 修剪定案**：S1-S8 赛时申报账本 41 条跳过理由逐条分类（CR 合同冗余/NA 域冲突/
> Dup 重复/ST 低频题型）后，步骤推荐槽位 **54 → 11**（2026-09-19 P4 技能绑定为 step5 补入必用位
> `paper-figure-palette`，11 → 12）——结构性冗余的 41 个技能全部移入 §三在册
> （修剪 ≠ 弃用，按需加载照常留痕），地图↔引擎集合一致性由
> `tests/test_asset_utilization.py::test_map_section2_matches_engine_companions` 机检锁定。
> 修剪依据全文见 LOG 续20/续21；利用率账本：`python tools/check_asset_utilization.py`。

| 步骤 | companion_skills | 一句话用途 |
|------|------------------|-----------|
| 1 赛题分析 | （无） | 五段产出与反 AI 陷阱登记已内嵌 comp-prob-analysis 契约 |
| 2 文献 | citation-check | GB/T 7714 引用格式检查（赛时唯一真实使用记录，有执行器） |
| 3 建模 | sci-sympy | 符号推导验证（facts_audit 只覆盖数值核验，此为符号位互补） |
| 4 编程 | sci-statistical-analysis | 统计检验/数分（数据型问题高频，无其他步骤兜底） |
| 5 图表 | figure-aesthetics-craft, paper-figure-palette | 图形质感技法（渐变合法语义/边色继承/绘图五纪律，recipe 体系外互补层）+ **统一配色注册表（必用：色值不得自创）** |
| 6 架构图 | （无） | drawio_rules/tikz 规范已随主合同加载，方法论备选见 §三 |
| 7 逻辑复核 | （无） | contest_models 独立审稿通道为唯一主通道 |
| 8 论文 | （无） | 写作铁律/去 AI 化（ai_tell_check）/格式（cumcmthesis cls）全部内嵌合同+_utils 脚本 |
| 9 一致性 | analyze-results | 数值口径交叉核对方法论（机器兜底 = 本步资产 paper_data_check） |
| 10 编译 | （无） | Word 交付需求由 output_format=docx 参数机制自动加步，不再重复推荐 |
| 11 视觉审查 | scholar-critique-figures, figure-spec | 外部图审视角清单/图规格说明 |
| 12 编辑 | anti-defensive-writing | 修订删 hedge/免责/过度解释（该技能唯一正确档位，S8 写作期不适用） |
| 13 终审 | scholar-critique-manuscript | 外部审稿人视角批判清单（参考用，不替代独立审稿通道） |
| 14 交付审计 | citation-check, quality-check | 引用终检+产出质量终检（另按 cumcm_2026_format 逐条核验） |

**赛后/场外情境推荐**（不在 14 步内）：`contest-retrospective`（赛后复盘与经验沉淀——留痕取证→场景/坑/清单三分类→每条归因仓库内真实强制点→双写经验库→机检闭环；**每个赛事周期结束后应跑一次**，2026-09-19 入库）、`paper-slides`/`paper-poster`/`sci-latex-posters`（答辩幻灯与海报）、`team-coordination`（三人分工时）、`feishu-notify`（进度通知）、`rebuttal`（答辩质询应答结构）。

## 三、情境可用（64 个，按需加载）

`claude-scientific-writer`（通用科学写作）、`paper-plan`/`paper-analysis`/`assets-inventory`（科研链资产管线，有既有材料时）、`paper-write-zh`/`paper-write-zh-docx`（Markdown 路线写文）、`paper-writing`/`paper-writing-ucsb`（科研写作方法论参考）、`training-check`（产出训练自检）、`editor-agent`/`experiment-agent`（代理执行模式）、`sci-citation-management`（引用管理方法论）、`scholar-accessible-pdf`/`scholar-latex-cleanup`/`scholar-presubmit-checks`（PDF 可及性/LaTeX 清理/预提交检查——投稿向但方法通用）、`novelty-check`（新颖性论证参考）、`idea-creator`（创意法参考）、`auto-paper-improvement-loop`（改进循环，第 12 步后可选）、`sci-scientific-writing`（科学写作规范）、
`palette-health-check`（配色「去灰提彩」体检——把"发灰/发闷/太深"翻译成可机检的 C*/C*max 去灰指标、`deepen` 替代 `darken`、色带入带序单调性复核；S5 出图后或 S11 视觉审查时按需加载，脚本在 `skills/palette-health-check/bin/`，2026-09-12 入库）。
`comp-cumcm-disclosure`（CUMCM AI 工具使用申报双件套入口与门禁——生成/校验《AI工具使用详情.pdf》与正文 AI 使用声明、声明↔详情口径一致双硬闸；配套确定性脚本 `skills/_utils/build_ai_disclosure.py` 与唯一真源 `ai_disclosure_rules.md`，S14 终审前后按需加载，2026-09-12 入库）、
`comp-cumcm-package`（提交打包沙演与合规终审——支撑材料语料/身份扫描（文件名/目录名/PDF 文档属性）/论文与包各 ≤20MB/MD5/`--zip` 沙演防呆闸，人工项见其 `references/submission_checklist.md`，S14 后上传前使用，2026-09-12 入库）、
`paper-figure-palette`（**统一配色体系（多场景）**——先按数据类型选分类/顺序/发散，再按场景（竞赛/期刊投稿/学位与课程/幻灯海报/Office 内嵌）落地；真源 `assets/palette_registry.json`（9 套色板）+ `references/scenarios.md`（三步选色法/10 条规范/禁用清单），机检 `palette_kit.py registry-verify`；本地 8 色板「夏日海滩」同源，与 `palette-health-check` 配套，绘图/视觉审查按需加载，2026-09-13 入库 / 2026-09-19 升级为多场景）。

**§二修剪移入（2026-09-12，41 个）**——被步骤推荐清单移出的结构性冗余/低频技能，
功能多已被主技能合同、内建脚本（data_check/constraint_audit/facts_audit/ai_tell_check）或
其他步骤承接；赛时确需使用时按情境技能对待并照常留痕：

- 拆题/建模（6）：`problem-analysis`（五段拆题已被主流程覆盖）、`model-building`、`model-innovation`、`math-modeling-contest-route-selection`（选题在开引擎前完成）、`scholar-verify-math`（数值核验已由 facts_audit 承担）、`proof-writer`
- 数据/统计（4）：`data-processing`（内建 data_check.py）、`sci-exploratory-data-analysis`（S1 data_profile 建档）、`sci-networkx`（图论题低频）、`dse-loop`（灵敏度由 S3 合同规划）
- 文献检索（5）：`check-citations`（无执行器，功能由 scholar_fetch 等效承担）、`research-lit`、`literature-review`、`paper-search`、`sci-paper-lookup`（S2 契约为台账三查非综述）
- 绘图（8）：`scipilot-figure-skill`（图型已由 S1 FIGURE_MANIFEST 前置定案）、`agent-figure-gallery`、`academic-figure-skill`（精修档位，S11 视觉审查可升级）、`plot-from-data`、`plot-from-image`、`scientific-visualization`、`paper-figure-html`、`eco-community-plots`（生态群落特化）
- 架构图（6）：`paper-framework-figure-studio-pro`（高规格多候选档位）、`visio-image-rebuilder`、`diagram-design`、`scientific-schematics`、`graphviz`、`mermaid-diagram`（drawio/xelatex 主链未用其语法）
- 审稿循环（3）：`auto-review-loop`、`auto-review-loop-llm`、`auto-review-loop-minimax`（备选循环引擎，主通道=contest_models 独立审稿）
- 论文写作（5）：`anti-ai-detection`（词表级检测由 _utils/ai_tell_check 承担）、`latex-writing`（cumcmthesis 模板内嵌）、`result-to-claim`（三要素转写为合同铁律）、`paper-plan-zh`（骨架由合同确定）、`format-profile`（cls 强制格式）
- 编译交付（4）：`docx-export`（output_format=docx 机制自动加步）、`docx-format-check`、`docx-template-map`、`latex-document`

## 四、外域不接入（145 个，赛时不要加载）

| 域 | 技能 | 不接入理由 |
|----|------|-----------|
| ars-* 学术科研套件（22） | ars-academic-paper, ars-academic-paper-reviewer, ars-academic-pipeline, ars-adversarial-reviewer, ars-agent-harness, ars-ai-security, ars-challenge, ars-code-reviewer, ars-deep-research, ars-dossier, ars-experiment-designer, ars-grants, ars-litreview, ars-notebooklm, ars-patent, ars-pr-review-expert, ars-pulse, ars-research, ars-research-summarizer, ars-senior-data-scientist, ars-statistical-analyst, ars-syllabus | 科研立项/申报/专利管线，非数模赛时 |
| nature-* 期刊套件（12） | nature-citation-verifier, nature-data-availability, nature-figure, nature-figure-planner, nature-manuscript-optimizer, nature-paper-bootstrap, nature-paper-workflow, nature-portfolio-playbook, nature-rebuttal-response, nature-results-section-revision, nature-scientific-writing, nature-submission-audit | 期刊投稿口径，与国赛格式/审稿逻辑不符 |
| spine-paper-*（12） | spine-paper-spine 及其 11 个子技能 | 自媒体长文管线 |
| latexpap-*（8） | latexpap-arxiv-paper-writer 等 | arXiv/合作论文管线 |
| galaxy-*（45） | galaxy-ui-ux-pro-max 等 web/obsidian/插件杂域 | 非竞赛域（边缘：galaxy-kaggle-learner/galaxy-publication-chart-skill/galaxy-ml-paper-writing 如需可临时按情境用） |
| dev-*（7） | dev-requirement → dev-selfcheck | 毕设/软件项目管线 |
| 知识产权（5） | copyright-build/draft/source-materials, patent-build/draft | 软著专利域 |
| 课程/人文（9） | course-paper, course-plan, course-report, course-report-plan, humanities-plan/write/write-latex, grant-proposal, thesis-proposal | 课程论文/人文/基金开题域 |
| 科研选题与实验（10） | idea-discovery, idea-discovery-robot, research-pipeline, research-refine, research-refine-pipeline, research-review, experiment-plan, experiment-bridge, monitor-experiment, run-experiment | 长周期科研管线，赛时 3 天用不上 |
| 英文/期刊写作变体（5） | paper-write, paper-write-docx, paper-write-nature, paper-write-nature-docx, paper-compile | 国赛中文链已有 comp-paper-zh/comp-compile-zh |
| scholar 期刊投稿系（6） | scholar-arxiv-metadata, scholar-arxiv-prep, scholar-bib-doi-toggle, scholar-check-refs, scholar-doi-bibtex, scholar-openalex | arXiv/DOI 投稿工具 |
| 基础设施（5 + shared-scripts 目录） | skill-creator-official, acat-doc-governance, codesucker-integration, agent-bootstrap, tool-forge, shared-scripts(目录，非技能) | 仓库治理/技能开发/宿主无关自举与工具铸造/软著，非解题用 |
| 其他（1） | pixel-art | 像素画风，与学术图规范冲突 |

## 五、未接入库（15 个，2026-09-11 对账新增）

以下技能在 skills/ 实存（有 SKILL.md）但未归入前四类任何一类（2026-09-11 机对账发现，
此前处于"无人知晓"状态）。赛时不主动加载；确需使用时按情境技能对待并照常留痕：

- **绘图/可视化**（6）：`matplotlib`、`plotly`、`seaborn`、`visualization`、`infographics`、`excalidraw-diagram`
- **文献/研究辅助**（5）：`arxiv`、`comm-lit-review`、`deep-research`、`sci-literature-review`、`sci-pdf`
- **其他单点**（4）：`ablation-planner`（消融实验规划）、`paper-compile-zh`（中文编译变体，主链用 comp-compile-zh）、`paper-illustration`（论文插图）、`problem-selection`（赛题选择）

## 六、统计（2026-09-19 机对账复核，check_asset_utilization.py）

主链家族 20 + 每步推荐 17（§二 10 unique + 赛后段 7）+ 情境 64（19 + 修剪移入 41 + 新增 4）+ 外域 145 +
未接入库 15 = **261**（与 skills/ 下含 SKILL.md 的目录数逐一相符：零幽灵名、零漏网）。
修剪只改变"哪一步主动推荐"（54→11，P4 后 12 槽位），不改变任何技能的可知性——全部 41 个移入 §三在册。
**P4 技能绑定（2026-09-19）**：comp_cumcm 全部 14 步声明 `metadata.skill_binding`（`main_required` =
主技能契约必须留真实读取痕迹）；step5 另声明 `mandatory: [paper-figure-palette]`（必用、不可 skipped）。
其余步骤的推荐位仍是"申报即可跳过、跳过须给理由"（C1 闸），不做过度强制——
把辅助技能一律设为必用会制造假失败（如无数值推导的题目无法合法使用 sci-sympy）。
对账口径：技能 = skills/ 下含 SKILL.md 的目录（263 目录减 `_utils`/`shared-scripts` 两个非技能目录；
2026-09-19 新增 `contest-retrospective`，260→261）；
主链 = §一具名，推荐 = §二表格 + 赛后段具名，情境 = §三具名，外域 = §四具名 + 六个前缀域
（`ars-*`/`nature-*`/`spine-paper-*`/`latexpap-*`/`galaxy-*`/`dev-*` 按前缀展开）+ 斜杠缩写展开
（如 `copyright-build/draft/source-materials`），未接入库 = §五具名。
**零漏网对账已固化为机检**（词边界+斜杠展开+前缀 fnmatch）：
`python tools/check_asset_utilization.py --strict` + `tests/test_asset_utilization.py::test_real_map_covers_all_skills_zero_missing`
——任何改动本文件的维护者必须跑过机检后方可保留本节统计行。
