# Academic Agent Toolkit · 科研工具箱

**一套完整的科研 Agent 工具箱**：把"技能即知识、Agent 即执行者、引擎只编排、门禁保质量"落成可运行的系统。
覆盖 **6 大能力域、269 项能力、244 个技能**——从数模竞赛到学术论文、文献研究、课程材料、知识产权、科研绘图全流程。

`v1.1.0` · 全部能力已公开发布 · `225 tests passed` · 双许可证（核心 CC-BY-NC-4.0 / 公开基准 CC-BY-4.0）

---

## 这是什么

不是提示词合集，而是一套**带质量门禁和审计证据链的 Agent 工程系统**：

- **技能即知识** —— 每个 `skills/<name>/SKILL.md` 是一份可执行的专业作业规程，Agent 读取后自主执行；
- **引擎只编排** —— `engine/` 负责 workflow 状态机、质量门禁、STEP_MANIFEST 溯源、审计存储，绝不代替 Agent 执行；
- **门禁保质量** —— 每步产出强制过门禁（页数/伴随文件/大小/审稿证据），不达标即重做；
- **三层审计** —— L1 拦截式插件（工具调用全留痕，不可绕过）+ L2 编排留痕 + L3 执行申报，交叉比对防伪造。

### 六大能力域（269 项能力）

| 能力域 | 条目 | 代表能力 |
|--------|-----:|----------|
| 课程与研究材料 | 83 | 课程论文/报告/教学大纲生成 |
| 学术论文 | 71 | 论文写作/评审/润色/投稿准备（含 Nature 工作流） |
| 文献与研究 | 41 | 文献检索/综述/深度研究/实验设计 |
| 数模竞赛 | 32 | CUMCM 14 步端到端竞赛流水线（10 项正式验收能力所在域） |
| 图表与文档生产 | 30 | 期刊级科研绘图/信息图/Excalidraw/LaTeX 全家桶 |
| 知识产权材料 | 12 | 软著申请资料（草稿→成品）/专利交底书/基金申请书 |

### 科研绘图（v1.1 新扩展）

集成 9 个上游技能构成完整绘图栈：**scientific-visualization**（期刊级多面板/误差棒/显著性标注/色盲安全/PDF·EPS·TIFF 导出）、matplotlib / seaborn / plotly 三层绘图库技能、**figure-spec**（JSON→SVG 确定性架构图）、graphviz、excalidraw-diagram、mermaid、infographics、scientific-schematics，外加既有的 nature-figure 与 62 篇获奖论文实证规范。全部带 pinned-commit 溯源（`UPSTREAM.md` 台账 26 条）。

## 快速开始

### OpenCode Desktop（正式宿主）

1. 克隆本仓库；
2. 用 OpenCode Desktop 打开仓库根目录（`opencode.json` 已配置默认角色、技能路径、docsearch MCP）；
3. 直接描述任务，例如："按 CUMCM 流程做这道 2024 年 B 题，数据在 data/ 下"。

### ZCode（兼容层）

1. 克隆本仓库；
2. 重建技能联结（Windows）：
   ```
   cmd /c mklink /J .zcode\skills 科研工具箱\skills
   ```
3. 用 ZCode 打开仓库根目录——244 个技能经 `.zcode/skills` 自动发现，docsearch MCP 经 `.zcode/config.json` 自动连接，`/doc-governance` 斜杠命令可用。

> 宿主差异：L1 拦截式审计插件仅 OpenCode 可用；ZCode 下审计降级为 L2+L3 两层，其余功能一致。

### 环境要求

- Python 3.11+（测试基线：`cd 科研工具箱 && python -m pytest -q` → 225 passed）
- TeX Live / XeLaTeX（论文编译类能力需要）
- 可选：视觉模型 API（图表视觉审查）、OpenRouter API（infographics 技能）

## 质量与可信

| 机制 | 说明 |
|------|------|
| 质量门禁 | 每步产出过 named gates（paper_consistency / citation_integrity / experiment_reproduc / figure_provenance / compilation_log） |
| STEP_MANIFEST | 每步记录输入/输出哈希、命令、配置、依赖，产物可复现可审计 |
| 溯源台账 | `tools/check_provenance.py` 校验 26 条 UPSTREAM.md（pinned commit + license），外部集成全可追 |
| 双层基准集 | 公开基准（cumcm_public / six_domains_public，CC-BY-4.0）+ 私有基准（真实题面，不随仓库分发） |
| 测试基线 | 225 项 pytest（工作流状态机/门禁/桥接/审计/配置契约全覆盖） |

## 仓库地图

```
├── 科研工具箱/            产品主体：skills(244) / engine(13) / tools(58+) / tests / data
├── capabilities/          能力目录 catalog.json（269 条，含验收证据与缺口声明）
├── benchmarks/            公开基准集（CC-BY-4.0）
├── docs/superpowers/      设计 spec 与实施计划（dated 快照）
├── governance/            资产台账
├── releases/              发布包（本地构建）
├── AGENTS.md              Agent 入口：宿主支持矩阵 + 硬性规则
└── LOG.md                 操作日志
```

内部真源（`dev-docs/`：truth-index 入口索引、归档区、删除台账）不入仓库。

## 版本

**v1.1.0（2026-08-28）**：全能力公开发布（含软著/专利/基金流水线）· 科研绘图 9 技能扩展 · ZCode 兼容层 · 全库文档治理。详见 [CHANGELOG.md](./CHANGELOG.md)。

## 许可证

- 仓库核心（技能/工具/引擎/配置）：**CC-BY-NC-4.0**（禁商用、禁 AI 训练，见 [LICENSE](./LICENSE)）
- 公开基准集：**CC-BY-4.0**
- 第三方 vendored 组件（CodeSucker core 等）：随各自许可证，见各目录 `UPSTREAM.md` / `LICENSE`

## 联系方式

- QQ：**1991401843**
- GitHub：[FOURTEEN1416](https://github.com/FOURTEEN1416)
