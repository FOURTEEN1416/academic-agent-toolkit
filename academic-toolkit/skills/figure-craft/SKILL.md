---
name: figure-craft
description: "出版级优化制图（版面级重绘，不重算模型）：图型选型与多样化、渐变质感画法、统一配色注册表、验收与视觉复审。触发：优化图表、改造图、图不好看、柱形图折线图太多、纯色平涂、质感、投稿图、restyle figure、publication-quality polish。"
---

# figure-craft — 出版级优化制图总控

> **定位**：**编排 + 方法**技能，不重复造轮子。它把"图怎么选型、怎么画出质感、怎么验收"三件事收敛成
> 一条可复跑的流水线。
>
> **适用边界**：**版面级**图重绘/优化——数值只来自原图数字化或表格转录，**不重算模型**。
> 需要改数值口径、重跑实验 → 属建模/分析域，交回 `comp-*` / `paper-*` 主链；本技能只接管视觉层。
>
> **收编形态（重要）**：本技能是**增量收编**——只自带工具箱绘图资产里**独有的部分**
> （`_utils/figstyle.py` 质感 API、`assets/palette_registry.json`、`assets/palette_v6.json`、
> `references/` 七篇方法文档）。**与工具箱共享的绘图脚本与配方不复制第二份**，一律引用唯一真源
> `academic-toolkit/skills/_utils/`（避免双副本漂移与查重台账膨胀）。
> 溯源与差异说明见 `SOURCE.md`。

## 何时用哪条路径（先路由，再动手）

| 你的处境 | 走哪 | 深读 |
|----------|------|------|
| 一堆图"都是柱形图/折线图，太单调" | §一 图型选型与多样化 | `references/chart-type-map.md` |
| 图"颜色脏/平涂/AI 感、没有质感" | §二 质感三件套 | `references/plotting-playbook.md` |
| 不知道配色取哪组色 | §三 配色 | `references/scenarios.md` + `assets/palette_registry.json` |
| 有参考图要照着画 | 复用 `plot-from-image` 思路（见 §五资产地图）| `references/skill-router.md` |
| 画完要验收/投稿前把关 | §四 验收管线 | `references/acceptance-gates.md` |
| 遇到渲染方框/图例丢手柄等怪问题 | §六 坑清单 | `references/pitfalls.md` |

---

## §一 图表类型：选型 + 多样化

**核心命题**：同一份数据往往有多种合法图型；"柱形图折线图太多"的解法是**按数据语义换图型**，
而不是调颜色。改法速查（完整版见 `references/chart-type-map.md`）：

| 原图型 | 升级为 | figstyle 落地 |
|--------|--------|---------------|
| 柱状图（排序对比） | **棒棒糖点图** | `ax.vlines` 细杆 + `glow_scatter` 头 + 数值标注 |
| 分组柱状 | **得分点阵** | 按系列 `vlines(alpha≈0.5)` + `glow_scatter` |
| 水平条形 | **渐变条** | `gradient_bar(horizontal=True, fade=0.62)` |
| 双线折线对比 | **差值渐变带** | `gradient_area(baseline=另一条线)` |
| 置信带 | 渐变带 + 图例手柄 | `gradient_area(WARM.TACC, baseline=fit_band)` |
| 垂直剖面 | 水平淡出面 | `fade_area_x` + `glow_line` |
| 密度/分布 | violin/box + 荧光轮廓 | `lighten` 填充 + `PathCollection` 描边 |
| ROC/PR | AUC 渐变区 | `gradient_area` |
| 保留柱形 | **唯一条件**：`gradient_bar`+glow 全套 | 缺一即"纯色平涂"被打回 |

**选型前置**：不确定"这数据该画什么"时，先读共享配方库
`academic-toolkit/skills/_utils/figure_exemplars.md`（图型规划启发式 + 领域签名图触发表）
与 `figure_recipes_{basic,advanced,competition,empirical,academic}.md`。

## §二 绘图方式：质感三件套铁律

每个图形元素 = **浅渐变填充 + 同族加深描边 + 外扩荧光层**，缺一即"纯色平涂"被打回。
全部逻辑已封装进本技能自带的 `_utils/figstyle.py`，直接调用，勿手搓：

```python
import sys; sys.path.insert(0, "academic-toolkit/skills/figure-craft/_utils")
import figstyle as fs           # 本技能 _utils/ 下，零外部依赖（仅需 numpy/matplotlib）
fs.setup_style()                # 字体/字号/色板一次性设定
fs.apply(ax)                    # 坐标轴：左+下轴线、极浅网格、axisbelow
fs.gradient_bar(...)            # 渐变柱/条（替代 ax.bar 平涂）
fs.gradient_area(...)           # 曲线下/差值渐变带（替代 fill_between）
fs.fade_area_x(...)             # 垂直剖面水平淡出面
fs.glow_scatter(...) / fs.glow_line(...)   # 荧光标记 / 荧光线
fs.gradient_box(...)            # 流程图/卡片框（层容器三件套）
fs.PASTEL["green"]              # (fill, edge) 色对；fs.lighten/deepen/ink_of 调色
fs.save_fig(fig, "f.png", "f.pdf")   # PNG(300dpi)+矢量 PDF 双出
```

函数全签名与默认值见 `references/plotting-playbook.md`。**参考构造基准**：
"层容器"架构（底层渐变容器 → 描边 → 内嵌文字）；流程图/框架图按此**重绘**而非截图 raster。

## §三 配色

- 真源：`assets/palette_v6.json`（夏日海滩 v6，T4=底色渐变 / T2=卡片渐变底 / TACC=荧光描边角色）
  与 `assets/palette_registry.json`（9 色板 + 5 场景 + 5 禁用 + 10 规则）。
- 跨技能选色方法论（CVD/灰度合规、分类-顺序-发散三型选择）在唯一真源
  `academic-toolkit/skills/paper-figure-palette/references/color-system.md`（**不复制副本**）。
- 铁律：蓝色系**禁深色**（藏蓝=AI 感），向亮青绿族靠拢；`#00B4AD` 太亮**不作小字**，
  文字/图例墨色单设 `AQUA_INK=#0F7E78`（白底对比度≈6.5）；多系列须"颜色+线型"双编码（`fs.LS_SEQ`）。
- 场景化落地（竞赛 / 期刊投稿 / 学位与课程 / 幻灯海报 / Office 内嵌）见 `references/scenarios.md`。

## §四 验收管线（收口必跑，全绿才算过）

脚本一律引用工具箱唯一真源（路径相对 `academic-toolkit/` 根）：

1. **确定性重生成**：图脚本 `rng=default_rng(42)`，重跑核对数值零改动。
2. **代码级检查**：`bash skills/_utils/figure_check.sh`（硬编码色 / 默认蓝 / 红绿灯 cmap / 缺 setup_style / 图型反模式 / 画布尺寸）。
3. **图内文字预算**：`python skills/_utils/figure_text_budget.py figures`（解释性文字移 caption）。
4. **渲染级 PDF 检查**：`python skills/_utils/figure_pdf_quality_check.py figures --paper paper`
   （插入后 ≥8pt、对比度 ≥4.5、重叠/越界/空白带）。
5. **执行者视觉全页复审**（当前 Agent 独立窗口读图）：montage + 关键页单独渲染——文字检查抓不到的（标题互碰、图例丢手柄、
   面板挤压）只能靠看图。
6. 图型改动后**同步正文措辞**（如"柱状图的形态"→"得分点阵的对比"）。

命令细节与 `gates_override` 豁免机制见 `references/acceptance-gates.md`；
示例豁免文件自带于 `_utils/gates_override.example.json`。

## §五 复用工具箱绘图资产（skill-router）

本技能自带质感层与配色真源；其余专业绘图能力**委派给工具箱既有技能**（不重复收编）。
路由表见 `references/skill-router.md`，摘要：

| 需求 | 委派技能 |
|------|----------|
| CNS/Nature/Cell 级投稿图从零起 | `fig-academic` |
| 不知道画什么图/数据怎么可视化 | `fig-visualization-advisor` |
| 照参考图复现字体/配色/比例 | `plot-from-image` |
| 用某论文风格套我数据 | `plot-from-data` |
| Nature 规范 matplotlib | `paper-figure-nature` |
| 非数据图（架构/路线图） | `paper-figure-drawio` / `paper-figure-html` |
| 方法框架图多方案 | `paper-framework-figure-studio-pro` |
| 出图选色（统一色系统） | `paper-figure-palette` |
| 投稿前图评审 | `fig-critique` |

> 本技能与它们**不冲突**：figstyle 质感层可叠加在任何 matplotlib 产出上；委派路径用于
> "从零画"或"专业图型"，本技能用于"把已有图提升到投稿质感"这条版面级主线。

## §六 已知坑（实测）

见 `references/pitfalls.md`。高频三条：基类 `Patch` 抽象 → 图例手柄用零尺寸 `Rectangle`；
CJK 必须 `font.family=[列表]`、含中文串禁 `$...$` mathtext；`gradient_bar` 替换原 `bar` 后回查图例手柄是否丢。

## 质量铁律（自检四问）

1. 每个大面积填充都走了质感三件套吗？（无纯色平涂）
2. 蓝色系有藏蓝/深蓝残留吗？浅色被误用作细线或小字了吗？
3. 四道检查全绿了吗？视觉复审看过了吗？
4. 数值与原口径一致吗？（版面级：只搬运不重算）

**边界与诚实**：灰度打印下浅色渐变头可能偏弱——靠描边+数值标注缓解，如实声明；
无出处的"真实资料区间"类越界评审要求可拒绝整改（超版面级边界）。无证据＝未执行。
