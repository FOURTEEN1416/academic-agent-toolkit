# 跨项目科研绘图技能借用提示词（Cross-Project Figure Skills Prompt）

> **用法**：把下方"提示词正文"整段复制，注入其它项目的 agent（作为系统规则附件或任务前导即可）。
> **真源**：技能清单以 `科研工具箱/CONTEST_SKILL_MAP.md`（全库分类账）与 `capabilities/catalog.json`（能力目录）为准，本文件为 2026-09-11 快照（28 个绘图技能）。

---

## 提示词正文（整段复制以下内容注入）

你现在可以**只读借用**一套科研绘图技能库，位置在 `D:\Desktop\数模竞赛\科研工具箱\skills\`（一套完整的科研 Agent 工具箱，下称"技能库"）。请严格遵守文末隔离纪律。

### 一、使用方法（五步）

1. **选技能**：按你的需求从下方清单选 1-2 个（宁缺勿滥，防上下文噪音）。选型困难时按"选型决策树"走。
2. **读手册**：用绝对路径 Read 所选技能的 `SKILL.md`（路径前缀统一为 `D:\Desktop\数模竞赛\科研工具箱\skills\`）。重量级技能（如 paper-figure）的 `references/` 子目录是其配套规范，按 SKILL.md 指引继续读。
3. **执行出图**：按 SKILL.md 的模板/工作流出图。**所有产物（图、脚本、数据、临时文件）只落你当前项目自己的工作区**，相对路径一律以你的工作区为根。
4. **自检**：出图后按 SKILL.md 的质检段落 + 下方"出图红线"逐条自检。
5. **留痕**：如你的项目有引用规范，报告中注明模板来源（"数模竞赛·科研工具箱/<技能名>"）。

### 二、技能清单（28 个 · 6 类）

**A. 论文主图主力（重量级，先读这里）**

| 技能 | 用途 |
|------|------|
| `paper-figure` | 论文数据图总纲：选图三轴、语义化配色（semantic-palette）、构图五模式（composition-patterns）、十八坑清单、图宽/字号纪律 |
| `paper-figure-drawio` | draw.io 源文件级框架图/流程图 |
| `paper-figure-html` | HTML/CSS 高密度信息图表 |
| `figure-spec` | 图规格说明书（尺寸/字号/导出参数的成文规范） |

**B. 风格模板直出（给数据就出图）**

| 技能 | 用途 |
|------|------|
| `plot-from-data` ⚠ | 8 种顶会风格模板（配对增益柱/置信带曲线/断轴散点/双雷达等），选风格+代入数据，dpi=300 |
| `scipilot-figure-skill` | CNS 级图表精修 |
| `academic-figure-skill` | 学术图表范式与 84M 图集参考 |

**C. 图库参考（照着好看的复现）**

| 技能 | 用途 |
|------|------|
| `agent-figure-gallery` | 图库选参考 |
| `plot-from-image` ⚠ | 从参考图逆向复现 |
| `paper-illustration` | 论文插图设计 |

**D. 科学数据图工具链**

| 技能 | 用途 |
|------|------|
| `scientific-visualization` | matplotlib/seaborn/plotly 出版规范：多面板、误差棒、显著性标记、色盲安全、PDF/EPS/TIFF 导出 |
| `matplotlib` / `seaborn` / `plotly` | 三大绘图库语法规范 |
| `eco-community-plots` ⚠ | 群落生态多元统计 R 模板 6 件：PCoA+边缘箱线+PERMANOVA / RDA 双标图+envfit / Mantel 热图 / Procrustes / 回归组合面板 / 富集 z-score（毫米制印刷导出） |
| `galaxy-publication-chart-skill` | 期刊级图表 |
| `visualization` | 通用可视化方法 |

**E. 概念图/框架图/示意图**

| 技能 | 用途 |
|------|------|
| `paper-framework-figure-studio-pro` ⚠ | 高规格框架图 |
| `visio-image-rebuilder` ⚠ | Visio 风格图重建 |
| `diagram-design` | 结构化图示设计 |
| `scientific-schematics` | 科学示意图 |
| `graphviz` / `mermaid-diagram` / `excalidraw-diagram` | 三种声明式/手绘风图引擎 |
| `infographics` | 信息图 |

**F. 出图后质检（配套使用）**

| 技能 | 用途 |
|------|------|
| `scholar-critique-figures` | 外部图审批判清单 |
| `figure-spec` | 图规格核对 |
| `comp-visual-review` | 视觉审查流程 |

⚠ = 无 License 技能（见隔离纪律第 4 条）。

### 三、选型决策树

- 有数据、要出版级数据图 → `plot-from-data`（最快）→ `scientific-visualization`（要统计规范）→ `paper-figure`（要全文统一配色语义）
- 环境/生态/群落多元统计图（PCoA/RDA/Mantel）→ `eco-community-plots`
- 机制图/流程图/技术路线 → `paper-figure-drawio` 或 `graphviz`/`mermaid-diagram`；重设计感 → `diagram-design`/`scientific-schematics`
- 高密度多信息版面 → `paper-figure-html` / `infographics`
- 手头有一张好看的参考图要复现 → `plot-from-image` + `agent-figure-gallery` 找同类
- 出图后 → `scholar-critique-figures` 批判一遍再交付

### 四、出图红线（建议全盘采纳，来源为技能库 paper-figure 系）

1. **语义配色**：主数据/本队方法用蓝（锚点 `#0072B2`，Okabe-Ito 系），对比/基线用橙（`#E69F00`），增量用蓝绿（`#009E73`）；禁止无语义彩虹。
2. **可访问性**：色盲安全 + 灰度打印可辨；颜色不承担全部区分任务，必须加线型/形状冗余编码。
3. **概念图与数据图分家**：示意图不许冒充数据图；**禁止假轴、假精度**（截断轴必须显式标注）。
4. **地图规范**：中国地图必须含九段线，用标准底图。
5. **印刷安全**：单面板宽度 ≥45mm，成图宽 89-183mm；PNG 300dpi + 矢量 PDF 双导出；缩到目标阅读宽度复查字号与遮挡。
6. **学术诚信**：合成/演示数据必须在图注申报；不添加不存在的统计结论；统计结果原文进报告，不许只给图不报数。

### 五、隔离纪律（硬性，逐条遵守）

1. **产物落点**：一切产物只落**你当前项目的工作区**；禁止向 `D:\Desktop\数模竞赛` 下任何路径写入、创建、修改或删除文件——包括技能库内、其 `workspaces/`、`dev-docs/`、`LOG.md` 等一切位置。
2. **只读借用**：技能库文件一律只读；不要把工作目录 cd 到该仓库，用绝对路径引用即可。
3. **门禁不外溢**：技能文档中出现的 STEP_MANIFEST、operations.jsonl、complete_step、C1 申报闸等，属于该仓库自身的引擎质量门禁——外部项目**不触发也不伪造**它们；过程留痕（如有）落你自己的项目。
4. **License 红线**：标 ⚠ 的 5 个技能（plot-from-data、plot-from-image、visio-image-rebuilder、paper-framework-figure-studio-pro、eco-community-plots）上游未声明 License，只可本地只读使用，**禁止复制进其它仓库再分发**；其余技能未经许可同样不得整体搬运。
5. **零干扰**：该仓库可能有赛时会话并行运行——任何写入（含 git 操作、日志、缓存）都可能造成冲突，因此除 Read 之外不对该仓库做任何文件系统操作。
6. **网络与依赖自担**：技能运行所需环境（Python/matplotlib、R/vegan、draw.io、graphviz 等）安装与配置在你自己的项目环境完成，不在技能库内做任何安装动作。

### 六、真源与同步

- 技能清单与全库分类账：`D:\Desktop\数模竞赛\科研工具箱\CONTEST_SKILL_MAP.md`
- 能力目录（机检 schema）：`D:\Desktop\数模竞赛\capabilities\catalog.json`
- 本文件为 2026-09-11 快照；清单变动以上述真源为准。
