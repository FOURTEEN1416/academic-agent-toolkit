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
