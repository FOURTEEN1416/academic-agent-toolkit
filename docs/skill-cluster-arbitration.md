# 技能簇仲裁表 · 写论文 / 审稿循环 / 文献检索

> **目的**：三大高密度技能簇内多技能并存，Agent 路由时按本表仲裁"用哪个"，避免凭名字猜。
> **来源纪律**：三簇共 29 个成员的 SKILL.md 已逐个通读（2026-09-22，批次四 B4-3），
> 表中每一条差异断言均有 SKILL.md 原文依据，抽查引用见 `dev-docs/board/reports/batch4-report.md`。
> **维护约定**：簇内新增/改名技能时同步更新本表；不合并技能、不凭空造差异。
> **与路由表的关系**：`科研工具箱/AGENTS.md` §三 是"域 → 技能"的粗路由；本表是簇内细仲裁。

---

## 表一 · 写论文簇（14 成员）

### 簇内结构总览

```
paper-write 变体族（6，产出 paper/ 目录，接引擎 STEP_MANIFEST/门禁）
├── paper-write              英 · LaTeX 会议稿（ICLR/NeurIPS/ICML）· PDF/docx 双模
├── paper-write-zh           中 · LaTeX（ctex 本科/硕士/期刊模板，GB/T 7714）· 双模
├── paper-write-docx         英 · 仅 Word markdown（镜像 paper-write 写作规则）
├── paper-write-zh-docx      中 · 仅 Word markdown（镜像 paper-write-zh）
├── paper-write-nature       英 · Nature 沙漏结构 · 双模
└── paper-write-nature-docx  Nature 风格 · 仅 Word markdown

独立成员（8）
├── paper-writing            五步编排管线：plan→figure→write→compile→improvement（2 轮）
├── paper-writing-ucsb       UCSB SNL 写作方法论（中心句先行/证据-论断配对/五阶段）
├── latex-writing            国赛 CUMCM LaTeX 专用（摘要页精修/三线表/算法伪代码）
├── claude-scientific-writer 15 模块路由器（IMRaD/评审/引用/综述/临床/基金/海报/幻灯）
├── sci-scientific-writing   IMRAD 期刊写作核心 + 深度检索联动（K-Dense 系）
├── nature-scientific-writing IMRAD 期刊写作核心 + Nature 润色节（scientific-agent-skills 系）
├── galaxy-nature-writing    Nature 风格节级起草/重构（作者证据先行，claim-evidence map）
└── galaxy-ml-paper-writing  ML 顶会全流程（claim ledger gate/反幻觉引用/会议清单）
```

### 仲裁表

| 用户意图 | 首选 | 备选 | 触发词差异 | 何时用备选（依据） |
|---------|------|------|-----------|------------------|
| 引擎工作流里的"写论文"步骤（模板 paper_writing 系） | 按模板 `sub_steps` 指定，勿自选 | — | 由 workflow_cli 调度 | 模板已按 language/output_format 解析（template_resolver 自动切 paper-write↔paper-write-zh），手动换技能会丢审计链 |
| 写英文 ML 会议论文（ICLR/NeurIPS/ICML，LaTeX 或 Word） | `paper-write` | `paper-write-docx` | "write paper / draft LaTeX" | `params.output_format == 'docx'` 时用 docx 变体（其 frontmatter 明示 "Use when params.output_format == 'docx'...produces paper/main.md only"） |
| 写中文 LaTeX 论文（学位论文/中文期刊） | `paper-write-zh` | `paper-write-zh-docx` | "写中文论文 / 中文LaTeX" | Word 输出用 zh-docx 变体（"Mirrors paper-write-zh writing rules but produces paper/main.md only"）；zh 版正文内嵌 ctexart/ctexbook/期刊三模板 + gbt7714 |
| Nature/ Nature 系期刊风格稿 | `paper-write-nature` | `paper-write-nature-docx`、`galaxy-nature-writing` | "Nature style / hourglass" | Word 输出用 nature-docx；只重写个别章节、作者已有 claims/figures 时用 galaxy-nature-writing（"Draft, restructure, or plan Nature-style manuscript sections from author-provided claims, results, figures"） |
| 一键从研究叙述到可投稿 PDF（不要逐步指挥） | `paper-writing` | 模板 `paper_writing`（引擎版） | "论文写作全流程 / Workflow 3" | 需要逐步 checkpoint/审计时改走引擎模板（plan→figure→write→compile→improvement 五步被拆成可审计步骤）；paper-writing 技能是同链的技能型快跑版 |
| 改写作方法/段落质量本身（不动内容） | `paper-writing-ucsb` | `galaxy-nature-writing` | "UCSB 写作规范 / 中心句 / topic sentence / evidence-claim pairing" | Nature 系手稿的结构性重构用 galaxy-nature-writing（节级 architecture + claim-evidence map）；ucsb 版特长是五阶段管线 + 强制风格审计 GATE |
| 国赛（CUMCM）论文 LaTeX 排版 | `latex-writing` | `comp-paper-zh`（竞赛链） | 国赛摘要页/三线表/算法伪代码 | 竞赛全流程（含审查/编译/装订）走 comp-paper-zh；latex-writing 只是排版知识件，无引擎步骤契约 |
| 期刊投稿件通用 IMRAD 写作（生物医学/报告规范） | `nature-scientific-writing` 或 `sci-scientific-writing` | `claude-scientific-writer` | "scientific manuscript / IMRAD / CONSORT/STROBE/PRISMA" | 两技能同源（K-Dense scientific-agent-skills / claude-scientific-writer .claude 副本），nature 版尾部多 "Nature-Style Academic Polishing" 节；需要跨模块（临床报告/基金/引用管理/评分）时用 claude-scientific-writer 路由器 |
| ML/AI 顶会从零全流程（含文献、claim 台账、会议清单） | `galaxy-ml-paper-writing` | `paper-write` | "NeurIPS/ICML/ICLR/ACL/AAAI/COLM + 从 repository 写论文" | 只差最后一稿（已有 PAPER_PLAN/NARRATIVE_REPORT）时用 paper-write（引擎步骤契约完整）；galaxy 版自带 Workflow 0（从研究仓库起步）与反幻觉引用门 |
| 临床/基金/海报/幻灯等论文周边文体 | `claude-scientific-writer` | 各专用技能（grant-proposal / paper-poster / paper-slides） | CARE/IHE/SOAP/NSF/NIH/beamerposter | 单一文体有专用技能时优先专用技能（引擎集成更好）；跨多模块综合任务用该路由器按 Module map 加载 |

**变体族速查（两轴定一）**：语言（英/中/Nature 英）× 输出（PDF 双模 / docx 专用）。
docx 专用的三个变体明确"Never produce paper/main.tex / sections/*.tex / references.bib"（参考文献以 markdown 章节内嵌）。

---

## 表二 · 审稿循环簇（6 成员）

| 用户意图 | 首选 | 备选 | 触发词差异 | 何时用备选（依据） |
|---------|------|------|-----------|------------------|
| 改进**研究本身**（补实验/分析/重构论证），最多 4 轮 | `auto-review-loop` | `auto-review-loop-llm` / `auto-review-loop-minimax` | "auto review / 自动审稿循环" | 三者是同一循环的 **API 通道变体**：auto-review-loop 用本仓自带审稿脚本（"本技能用本仓自带审稿脚本，不接外部 LLM API"）；需指定通用 OpenAI 兼容端点用 llm 版（内列 8 提供商表）；指定 MiniMax 官方 API 用 minimax 版（"本技能只走 MiniMax 官方 API，其它 OpenAI 兼容端点改用 auto-review-loop-llm"）。产物同族：NARRATIVE_REPORT.md + AUTO_REVIEW.md + REVIEW_STATE.json |
| 改进**成稿的写作质量**（不动研究设计，2 轮固定） | `auto-paper-improvement-loop` | `auto-review-loop` | "改论文 / improve paper / 论文润色循环" | 分界线是其原文："Runs after /paper-write + /paper-compile. Iterates on writing quality (**not research**)"。要补实验/改分析 → auto-review-loop；只改稿+重编译 → 本技能（产物 paper/main.pdf + PAPER_IMPROVEMENT_LOG.md + _improvement_rounds/ 快照） |
| 竞赛步骤间的**独立逻辑对抗复核**（只读挑错，不放行 fatal） | `comp-review` | `ars-academic-paper-reviewer`（quick/methodology-focus 模式） | "逻辑复核 / 对抗审查 / 方向反/漏变量/跨问矛盾排查" | comp-review 是 CUMCM 链内步骤（comp-code 后 comp-paper 前，默认关、`enable_comp_review=true` 才入链），产物 COMP_REVIEW.md + COMP_REVIEW_VERDICT.json（fatal 计数硬门禁）；非竞赛论文的通用评审用 ars 系 |
| 模拟期刊完整同行评审（5 审稿人 + 编辑决定信 + 修改路线图） | `ars-academic-paper-reviewer` | `claude-scientific-writer` 的 peer-review 模块 | "peer review / simulate review / editorial review / re-review / calibrate reviewer" | 本技能 6 模式（full/re-review/quick/methodology-focus/guided/calibration），**只读不改稿**（IRON RULE: "Reviewers MUST NOT modify the submitted manuscript"）；要量化评分体系或临床报告规范评审 → claude-scientific-writer 对应模块 |
| 投稿前结构化自审（评分表驱动） | `claude-scientific-writer`（peer-review + scholar-evaluation 模块） | `ars-academic-paper-reviewer`（full） | "ScholarEval / 8 维评分" | 需要多角色模拟与 devil's advocate 时用 ars 版（5 审稿人不可互相参照是它的铁律卖点） |
| 竞赛论文成稿后的写作打磨 | `auto-paper-improvement-loop` | `comp-review` | "改论文" | comp-review 只挑逻辑硬错不重写；写作打磨（overclaim 软化/图表-主语句式/记号一致性）归 auto-paper-improvement-loop |

**裁决要点**：三条正交轴选技能——① 改**研究** vs 改**文稿** vs **只评审不改**；② API 通道（本仓脚本/OpenAI 兼容/MiniMax）；③ 领域（CUMCM 步骤内/通用学术）。

---

## 表三 · 文献检索簇（9 成员）

| 用户意图 | 首选 | 备选 | 触发词差异 | 何时用备选（依据） |
|---------|------|------|-----------|------------------|
| 写**成品中文文献综述文档**（6000-10000 字，GB/T 7714） | `literature-review` | `sci-literature-review` | "文献综述 / 综述 / literature review" | 中文主题/中文产出首选 literature-review（AMiner 中文优先 + 反 AI 痕迹写作铁律 + 硬约束：候选池≥2×目标、80% 近 3 年）；英文系统综述（PRISMA/纳排标准）用 sci-literature-review |
| 英文系统性综述（PRISMA 流程、多库纳排、流程图） | `sci-literature-review` | `literature-review`、`ars-litreview` | "systematic review / scoping review / meta-analysis" | 其正文规定 "MANDATORY: Every literature review MUST include at least 1-2 AI-generated figures (PRISMA flow diagram)"；入门定位（还没到写综述那步）用 ars-litreview |
| 进入陌生领域的**入门定位**（要"先读什么/领域地图"，DOCX 指南） | `ars-litreview` | `research-lit` | "litreview / orientation / start here" | ars 版产出 research_guide_*.docx（8 节：优先阅读顺序/领域史/子域指南/研究组/空白），免费无钥 API（PubMed+OpenAlex），PICO/SPIDER/Decomposition 框架；要的是**台账+bib 供写作**时用 research-lit |
| 把**已有资产**（Zotero/Obsidian/本地 PDF）与新检索合成综述台账 | `research-lit` | `comm-lit-review` | "find papers / related work / Zotero + Obsidian" | research-lit 四级源优先级（Zotero→Obsidian→本地→$SCHOLAR_SCRIPT），产物 literature_review.md + references.bib 直接喂 paper-write；通信领域题材改用 comm-lit-review |
| 通信/无线领域文献综述（5G/6G/卫星/频谱等） | `comm-lit-review` | `research-lit` | "wireless / 5G/6G / beamforming / V2X / NTN" | comm 版是 research-lit 的通信域特化：外部源走 IEEE Xplore→ScienceDirect→ACM 阶梯 + Tier A/B/C 期刊会议分级（JSAC/ToN/TWC/SIGCOMM/INFOCOM…）；非通信题材按其正文要求回退通用技能 |
| arXiv 预印本搜索/下载/速览 | `arxiv` | `sci-paper-lookup`（arXiv 库）、`research-lit`（sources: web） | "search arxiv / download paper / arXiv ID" | arxiv 技能带 PDF 落盘（papers/，>10KB 校验、限速重试）与结构化摘要卡；只要元数据不要文件、或要跨库补充时用 sci-paper-lookup |
| 单篇论文查询（DOI/PMID/OpenAlex ID）与跨库元数据核对 | `sci-paper-lookup` | `paper-search`、`scholar-openalex` | "look up this DOI / which database / PMID↔DOI" | sci-paper-lookup 是 10 库路由器（PubMed/PMC/bioRxiv/medRxiv/arXiv/OpenAlex/Crossref/Semantic Scholar/CORE/Unpaywall），按意图选库并返回原始 JSON，含标识符格式表与 429 退避；已知只用 OpenAlex 时直接用 paper-search/scholar-openalex 更轻 |
| OpenAlex 快速检索（关键词搜论文 / 单篇详情 / 引用数排序） | `paper-search` | `scholar-openalex` | "search for papers / landmark papers (cites 排序)" | paper-search 是 bash 脚本轻通道（search.sh/paper.sh，relevance/cites/date 排序）；要做**程序化文献计量**（作者/机构/批量 DOI≤50/游标分页 5000+/字段聚合）用 scholar-openalex 的 Python 客户端 |
| 引文图分析 / 谁引了谁 / 推荐相关论文 | `sci-paper-lookup`（Semantic Scholar 库） | `scholar-openalex` | "citation graph / who cites this / recommendations" | Semantic Scholar 的引用图与推荐是其独有能力（经 sci-paper-lookup 的库路由）；OpenAlex 的 cited_by_count 聚合用 scholar-openalex |

**裁决要点**：先分**目的**——①产成品综述文档（literature-review / sci-literature-review）；②产入门指南（ars-litreview）；③产写作台账+bib（research-lit / comm-lit-review）；④只要检索结果本身（paper-search / scholar-openalex / arxiv / sci-paper-lookup）。再按语言（中/英）与领域（通用/通信/生物医学）收窄。

---

## 与本仓门禁/模板的衔接（供 Agent 参考）

- 引擎模板引用的簇内技能：`paper_writing`/`paper_writing_zh`/`nature_writing` 模板调 paper-write 族
  （language 参数由 template_resolver 自动切换 zh 变体）；`literature_review` 模板调 literature-review；
  `auto_review` 模板调 auto-review-loop。**走模板时不要手动换簇内技能**。
- 审稿循环三变体的产物文件名相同（NARRATIVE_REPORT.md / AUTO_REVIEW.md / REVIEW_STATE.json），
  `auto_review` 模板的 step_manifest 门禁对三者通用；但 `review` named gate 检查的是
  COMP_REVIEW.md 文件族（竞赛链专属），不适用于本簇任何成员（见模板 metadata note）。
- comp-review 与竞赛链的绑定关系（默认关、fatal 硬门禁）记录于其 SKILL.md，本表不复制操作细节。
