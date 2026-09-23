---
name: fig-plot-edit-lite
description: "无 Origin 的出版级数据图路线：继承 fig-plot-edit 科学绘图纪律（逐列角色确认、方案冻结、官方配色目录、出版图形合同），用 matplotlib+SciencePlots 把 CSV/TXT 实验表格画成 PNG+PDF+SVG 并附校验报告；先提案逐列用途、经用户确认后渲染；源数据不可变，不确定列拒画，产物如实称 publication-informed lite，不冒充 Origin OPJU。"
---

# EditaPlot Lite · 艾迪图轻量版（无 Origin 的 matplotlib 出版级路线）

> **定位**：本技能是 `academic-toolkit/skills/fig-plot-edit/`（Origin 可编辑科研绘图）的**方法论继承者**——
> 当本机无 Origin/OriginPro 时，用 matplotlib + SciencePlots 作为渲染引擎，完整继承其
> 科学决策纪律与出版图形合同，产出出版级 PNG/PDF/SVG。
> **方法论真源**：`academic-toolkit/skills/fig-plot-edit/SKILL.md`（本文件只写差异，冲突时以真源为准）；
> 配色真源复用 fig-plot-edit 官方目录 `academic-toolkit/skills/fig-plot-edit/assets/palettes/palette-catalog.json`。
> **与 fig-plot-edit 的关系**：不是上游副本（无 UPSTREAM 溯源件），渲染代码为本仓原创；
> fig-plot-edit 路线（OPJU 可编辑工程）见该技能——需要 Origin 工程文件时用它，不需要时用本技能。

## 一、环境（宿主中立，任何满足以下条件的 Python 即可）

- CPython 3.10–3.12 + 包：`matplotlib` `scienceplots` `numpy` `pandas` `Pillow`
- 本仓标准 venv：`vendor/forks/editaplot/runtime/.editaplot-venv`（由
  `vendor\forks\editaplot\editaplot.cmd doctor --repair` 建立，已含 numpy/matplotlib/PIL，
  再 `pip install SciencePlots` 即可；vendor/ 不入库，公开 clone 需按 fig-plot-edit SKILL.md §八
  自行获取上游快照，或自建 venv——两者等效，技能只依赖包不依赖路径）。
- 字体：Arial（英文/数字）+ Microsoft YaHei 回退（中文标签）；无 Arial 的机器自动回退系统无衬线体。

## 二、核心流程（三步，对应 fig-plot-edit 8 步的 lite 压缩）

### 第 1 步 propose（列角色提案——Ask first 检查点）

```bash
python scripts/plot_lite.py propose <数据.csv> --intent "<一句话科学目的>"
```

输出 JSON：每列角色（x_axis / error_of:<列> / uncertain / reserved）+ 待确认问题清单 +
源文件 sha256。**把清单报给用户**：哪些列会画、哪些只作误差棒、哪些保留不画、
哪些待确认。`uncertain` 数值列是一个**问题**，不是一条自动新曲线——必须追问，不得代确认。

### 第 2 步 用户确认（科学确认 + 哈希冻结）

用户确认科学目的与逐列用途后，写确认书 JSON（字段：`source_sha256`、`intent`、
`column_roles`——uncertain 列逐列改为 `main_evidence` 或 `reserved`、`chart`、`palette_id`、
`user_confirmed{by}`）。**源文件、列映射、目的任一变化，确认即失效**（render 会拒绝）。

### 第 3 步 render + verify（渲染与校验）

```bash
python scripts/plot_lite.py render <数据.csv> --confirm <确认书.json>
```

门禁链（任一不过即拒绝，不静默回退）：

| 门禁 | 规则 | 继承自 |
|------|------|--------|
| 哈希冻结 | 源 sha256 / 列集合 / 结构角色（x轴·误差棒·保留）与确认书不一致 → 拒绝 | fig-plot-edit 第 3 步 |
| 不确定拒画 | 确认书仍有 `uncertain` 列 → 拒绝 | fig-plot-edit §四 |
| 配色合同 | 图型须在配色 `recommended_charts`；系列数 ≤ `max_qualitative_categories` | fig-plot-edit 官方配色目录 |
| 出版合同 | 白底、Arial+雅黑回退、单栏 9cm（>2 系列双栏 19cm）、无图内标题、图例无框 | fig-plot-edit §五 |
| 源数据不可变 | 渲染后源 sha256 必须不变 | fig-plot-edit §四 |
| 产物校验 | PNG(300dpi)+PDF+SVG 三件齐 + 白底像素检测 + `verify-report.json` | fig-plot-edit 第 8 步 lite 等价 |

产物默认落在源文件旁 `<源文件名>_lite_<时间戳>/`。

## 三、完成口径（如实降级声明）

正式成功 = PNG + PDF + SVG + verify-report 全绿。**本技能产物不含可编辑 Origin 工程（OPJU）**，
对外表述一律用 "publication-informed lite"，不得称 "Origin 出图" 或 "OPJU 可编辑"；
需要 OPJU 时路由回 `skills/fig-plot-edit/`。人工视觉 QA 仍是成功必要条件之一（校验报告不替代看图）。

## 四、被工作流发现的路由面（登记记录）

- 引擎：`engine/modex-core/templates.json` 模板 `scientific_plotting` 的 paper-figure 步
  `companion_skills` 主动推荐本技能（StepAction 可见，C1 申报闸覆盖）；
- 竞赛地图：`CONTEST_SKILL_MAP.md` §三 情境可用（fig-plot-edit-lite 批次，2026-09-23）；
- 目录：`capabilities/catalog.json` figures_and_document_production 域，disposition=routed；
- 路由表：`academic-toolkit/AGENTS.md` §三 科研论文表"没装 Origin 也要出版级数据图"行。

## 五、演示与自检

```bash
python scripts/plot_lite.py propose examples/line_error_demo.csv --intent "演示"
# 按 §二第 2 步写确认书后：
python scripts/plot_lite.py render examples/line_error_demo.csv --confirm <确认书>
```

契约测试：`academic-toolkit/tests/test_editaplot_lite_skill.py`（列分类/门禁负面/渲染校验/catalog 映射）。

## 六、边界（继承 fig-plot-edit 三段式适配，本技能无 Origin COM 故风险更低）

- ✅ Always：读数据、propose 提案、配色查询；
- ⚠️ Ask first：render 写文件前须持有含 `user_confirmed` 的确认书（逐列确认即方向证据；
  同一数据源追加渲染不需重复询问）；
- 🚫 Never：源数据文件不可变（不覆盖/不补列/不编造）；不静默归一化、平滑、拟合、剔异常点；
  uncertain 列不代确认；校验不过不得宣称成功；不把 SVG/PNG 冒充 OPJU。
