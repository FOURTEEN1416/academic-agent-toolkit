# 绘图资产复用地图（skill-router）

> 两条复用通道：**(A) 包内自持**——本包 `_utils/` + `assets/` 已提取工具箱精华，拷到任意项目即可用；
> **(B) 仓库委派**——若目标工程在 `D:\Desktop\学术工作流` 内，可路由到整套专业绘图技能。
> figure-craft 的差异化定位：**版面级"把已有图提升到投稿质感"**这条主线。

## A. 包内自持资产（零外部依赖）

| 资产 | 路径 | 用途 |
|------|------|------|
| 质感三件套 API | `_utils/figstyle.py` | 渐变/荧光/色板/统一风格，`import figstyle` |
| 绘图通用库 | `_utils/plot_utils.py` | `setup_style` 多色板、图例防遮挡、smart_labels、recipe 图 |
| 代码级闸 | `_utils/figure_check.sh` + `figure_check.py` | 硬编码色/图型反模式/画布尺寸 |
| 文字预算闸 | `_utils/figure_text_budget.py` | 图内解释性文字移 caption |
| PDF 渲染闸 | `_utils/figure_pdf_quality_check.py`(+`paper_source_scope.py`,`fig_include_size.py`) | 字号/对比度/重叠/越界 |
| 规划对账 | `_utils/recipe_audit.py` | 规划图型↔实际代码 |
| 色板真源 | `assets/palette_v6.json` / `assets/palette_registry.json` | 出图取色 |
| 配色手册 | `references/color-system.md` / `scenarios.md` | 场景选色 |
| 配方菜单 | `assets/figure_recipes_*.md` | basic/advanced/competition/empirical/academic |
| 图型规划 | `assets/figure_exemplars.md` | 数量/类型启发式、领域签名图 |

## B. 仓库委派（工程在 academic-toolkit 内时）

| 需求 | 委派技能 | 与 figure-craft 的关系 |
|------|----------|------------------------|
| CNS/Nature/Cell 级投稿图从零起 | `fig-academic` | craft 负责"已有图升级"，academic 负责"从零到顶刊" |
| 不知道画什么图 / 数据怎么可视化 | `fig-visualization-advisor` | craft 的 §一选型可委派给它做诊断 |
| Nature 规范 matplotlib 出图 | `paper-figure-nature` | craft 质感层可叠加其 style 之上 |
| 照参考图复现字体/配色/比例 | `plot-from-image` | craft 无参考图反推能力 → 委派 |
| 用某论文风格套我数据 | `plot-from-data` | 同上，preset 风格路线 |
| 非数据图：架构/路线图（矢量） | `paper-figure-drawio` / `paper-figure-html` | craft 的 gradient_box 是 matplotlib 内轻量版；重工程委派 |
| 方法框架图多方案（AI 生成） | `paper-framework-figure-studio-pro` | craft 不做 AI 生图 → 委派 |
| 找参考图再动手 | `agent-figure-gallery` | 视觉参照检索委派 |
| 出图选色统一系统 | `paper-figure-palette` | craft 已内联其色板；深需色系统计委派 |
| Origin 可编辑 OPJU / 无 Origin 降级 | `fig-plot-edit` / `fig-plot-edit-lite` | 材料谱学/可编辑需求委派 |
| 投稿前图内容评审 | `fig-critique` | craft 管视觉质感，critique 管科学表达 |
| 去灰调色健康检查 | `palette-health-check` | 配色脏了先过它 |
| 图数量/类型规划 | `paper-figure-planner` | 规划阶段用，落地用 craft |
| 竞赛图视觉复核 | `comp-visual-review` | 竞赛交付链复核 |
| 纯库用法（matplotlib/seaborn/plotly） | `matplotlib` / `seaborn` / `plotly` | 底层 API 参照 |

## 决策：委派 or 自持？
- **数值不变、只改视觉**（换图型、加质感、调色、验收）→ 用本包 figure-craft，闭环。
- **从零画顶刊图 / 反推参考图 / AI 框架图 / Origin 可编辑 / 重工程矢量图** → 委派对应专业技能，
  产出后仍可用本包 §四门禁验收。
