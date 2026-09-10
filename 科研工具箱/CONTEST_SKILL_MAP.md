# CUMCM 竞赛技能全库地图（CONTEST_SKILL_MAP）

> **定位**：全库 254 个技能 × comp_cumcm 14 步工作流的推荐地图。引擎 StepAction 的
> `companion_skills` 字段（2026-09-11 起）每步主动给出本步推荐；本文件是全量真源，
> 含"情境可用"与"外域不接入"的完整分类账——**任何一个技能都不允许处于"无人知晓"状态**。
> 维护纪律：新增技能入库时必须归入下列四类之一并同步本文件（机检不查本文件，靠评审纪律）。

## 使用规则

1. 每步开工：看 StepAction 的 `companion_skills`，按需加载 **1-3 个**（宁缺勿滥，防上下文噪音）。
2. 辅助技能的产出与结论照常走留痕纪律（来源进产物、检索留证据）。
3. 辅助技能与主技能口径冲突时，以主技能 SKILL.md 为准（主技能是门禁责任人）。
4. 本图未列的技能（外域类）赛时**不要**为"用而用"地加载。

## 一、主链家族（20 个）

14 步主技能：`comp-prob-analysis` → `comp-literature` → `comp-modeling` → `comp-code` →
`paper-figure` → `paper-figure-drawio` → `comp-review` → `comp-paper-zh` → `comp-consistency` →
`comp-compile-zh` → `comp-visual-review` → `comp-editor` → `comp-final-review` → `comp-final-audit`。
编排器与变体：`comp-pipeline`（8 阶段轻量编排）、`comp-paper-en`/`comp-paper-en-docx`/`comp-paper-zh-docx`（语言/格式变体）、`comp-compile-en`（英文编译）、`comp-stats-topic`（统计建模赛专用模板）。

## 二、每步推荐（StepAction.companion_skills 同步给出）

| 步骤 | companion_skills | 一句话用途 |
|------|------------------|-----------|
| 1 赛题分析 | problem-analysis | 轻量拆题对照（题型/约束/坑点/答案形态 1-2 小时版） |
| 2 文献 | citation-check, check-citations, research-lit, literature-review, paper-search, sci-paper-lookup | GB/T 7714 引用检查；三源反幻觉核验；检索与综述方法 |
| 3 建模 | model-building, model-innovation, math-modeling-contest-route-selection, sci-sympy, proof-writer, scholar-verify-math | 多视角选型+国一撞方法查重；符号推导验证；证明严谨性 |
| 4 编程 | data-processing, sci-exploratory-data-analysis, sci-statistical-analysis, sci-networkx, dse-loop, analyze-results | 数据清洗/EDA/统计检验/图论模型/参数扫描/结果分析 |
| 5 图表 | scipilot-figure-skill, agent-figure-gallery, academic-figure-skill, plot-from-data, plot-from-image, scientific-visualization | 选图三轴顾问/图库选参考/CNS 级精修/风格模板/复现成图 |
| 6 架构图 | paper-framework-figure-studio-pro, visio-image-rebuilder, diagram-design, scientific-schematics, graphviz, mermaid-diagram | 高规格框架图/Visio 重建/结构图 |
| 7 逻辑复核 | auto-review-loop, auto-review-loop-llm, auto-review-loop-minimax | 备选自动审稿循环引擎（主通道仍是 contest_models 配置） |
| 8 论文 | anti-defensive-writing, anti-ai-detection, latex-writing, result-to-claim, paper-plan-zh, format-profile | 防过度写作/AI 痕迹检测/LaTeX 规范/结果→结论表述 |
| 9 一致性 | analyze-results | 数值口径交叉核对辅助 |
| 10 编译 | docx-export, docx-format-check, docx-template-map, latex-document | 需交付 Word 版或 LaTeX 排查时 |
| 11 视觉审查 | scholar-critique-figures, figure-spec | 外部图审视角清单/图规格说明 |
| 12 编辑 | anti-defensive-writing | 修订删 hedge/免责/过度解释 |
| 13 终审 | scholar-critique-manuscript | 外部审稿人视角批判清单（参考用，不替代独立审稿通道） |
| 14 交付审计 | citation-check, quality-check | 引用终检+产出质量终检（另按 cumcm_2026_format 逐条核验） |

**赛后/场外情境推荐**（不在 14 步内）：`paper-slides`/`paper-poster`/`sci-latex-posters`（答辩幻灯与海报）、`team-coordination`（三人分工时）、`feishu-notify`（进度通知）、`rebuttal`（答辩质询应答结构）。

## 三、情境可用（20 个，按需加载）

`claude-scientific-writer`（通用科学写作）、`paper-plan`/`paper-analysis`/`assets-inventory`（科研链资产管线，有既有材料时）、`paper-write-zh`/`paper-write-zh-docx`（Markdown 路线写文）、`paper-writing`/`paper-writing-ucsb`（科研写作方法论参考）、`training-check`（产出训练自检）、`editor-agent`/`experiment-agent`（代理执行模式）、`sci-citation-management`（引用管理方法论）、`scholar-accessible-pdf`/`scholar-latex-cleanup`/`scholar-presubmit-checks`（PDF 可及性/LaTeX 清理/预提交检查——投稿向但方法通用）、`novelty-check`（新颖性论证参考）、`idea-creator`（创意法参考）、`auto-paper-improvement-loop`（改进循环，第 12 步后可选）、`sci-scientific-writing`（科学写作规范）。

## 四、外域不接入（144 个，赛时不要加载）

| 域 | 技能 | 不接入理由 |
|----|------|-----------|
| ars-* 学术科研套件（22） | ars-academic-paper, ars-academic-paper-reviewer, ars-academic-pipeline, ars-adversarial-reviewer, ars-agent-harness, ars-ai-security, ars-challenge, ars-code-reviewer, ars-deep-research, ars-dossier, ars-experiment-designer, ars-grants, ars-litreview, ars-notebooklm, ars-patent, ars-pr-review-expert, ars-pulse, ars-research, ars-research-summarizer, ars-senior-data-scientist, ars-statistical-analyst, ars-syllabus | 科研立项/申报/专利管线，非数模赛时 |
| nature-* 期刊套件（13） | nature-citation-verifier, nature-data-availability, nature-figure, nature-figure-planner, nature-manuscript-optimizer, nature-paper-bootstrap, nature-paper-workflow, nature-portfolio-playbook, nature-rebuttal-response, nature-results-section-revision, nature-scientific-writing, nature-submission-audit | 期刊投稿口径，与国赛格式/审稿逻辑不符 |
| spine-paper-*（12） | spine-paper-spine 及其 11 个子技能 | 自媒体长文管线 |
| latexpap-*（8） | latexpap-arxiv-paper-writer 等 | arXiv/合作论文管线 |
| galaxy-*（37） | galaxy-ui-ux-pro-max 等 web/obsidian/插件杂域 | 非竞赛域（边缘：galaxy-kaggle-learner/galaxy-publication-chart-skill/galaxy-ml-paper-writing 如需可临时按情境用） |
| dev-*（7） | dev-requirement → dev-selfcheck | 毕设/软件项目管线 |
| 知识产权（4） | copyright-build/draft/source-materials, patent-build/draft | 软著专利域 |
| 课程/人文（8） | course-paper, course-plan, course-report, course-report-plan, humanities-plan/write/write-latex, grant-proposal, thesis-proposal | 课程论文/人文/基金开题域 |
| 科研选题与实验（10） | idea-discovery, idea-discovery-robot, research-pipeline, research-refine, research-refine-pipeline, research-review, experiment-plan, experiment-bridge, monitor-experiment, run-experiment | 长周期科研管线，赛时 3 天用不上 |
| 英文/期刊写作变体（5） | paper-write, paper-write-docx, paper-write-nature, paper-write-nature-docx, paper-compile | 国赛中文链已有 comp-paper-zh/comp-compile-zh |
| scholar 期刊投稿系（6） | scholar-arxiv-metadata, scholar-arxiv-prep, scholar-bib-doi-toggle, scholar-check-refs, scholar-doi-bibtex, scholar-openalex | arXiv/DOI 投稿工具 |
| 基础设施（4） | skill-creator-official, acat-doc-governance, codesucker-integration, shared-scripts(目录) | 仓库治理/技能开发/软著，非解题用 |
| 其他（1） | pixel-art | 像素画风，与学术图规范冲突 |

## 五、统计

主链家族 20 + 每步推荐 70 + 情境 20 + 外域 144 = **254**（全覆盖，2026-09-11 机对账：零幽灵名、零漏网）。
