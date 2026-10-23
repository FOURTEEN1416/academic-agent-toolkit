---
name: eco-community-plots
description: "生态群落数据专用可视化：物种丰度矩阵、排序图（PCA/NMDS/RDA）、多样性指数、稀疏曲线、群落热图与聚类。触发词：生态群落图、物种丰度、NMDS、RDA、稀疏曲线、多样性指数。"
---

# Eco Community Plots

Six publication-grade R templates adapted from a peer-reviewed community-ecology study
(plastisphere–microalgae). Every template exports **millimetre-sized PDF at print scale**
(58–138 mm) through one shared style source, carries significance markers, and prints
explained variance on ordination axes — the three habits this skill exists to propagate.

## R 侧样式契约（单一真源 `scripts/_eco_style.R`）

六个脚本都 `source()` 同目录的 `scripts/_eco_style.R`。字体族 / 字号阶梯 / 线宽 / 刻度长 /
语义色板只在该文件里改；脚本内只写差异项（图例位置、轴标题留白、显著性注释放哪），
不得再出现裸 hex 色值与逐处手写 `size =`。

| 项 | 口径 |
|----|------|
| 主题 | `theme_set(eco_theme(<成品宽 mm>))` → `theme_classic()` + `base_family = eco_font()` |
| 字体族回退链 | Noto Sans SC → NotoSansSC → SimHei → Microsoft YaHei → PingFang SC → Heiti SC → WenQuanYi Micro Hei → Arial → Helvetica → DejaVu Sans，取本机第一个可用族；`ECO_FONT_FAMILY` 可强制指定（R 侧不自动注册仓内 `_utils/NotoSansSC-Regular.ttf`） |
| base_size | 按「画时字号 = 印刷目标字号 × figsize宽 ÷ 嵌入显示宽」折算；六个成品宽 58–138 mm 全在 5.5 in（139.7 mm）上限内 ⇒ 缩放比 1 ⇒ base_size = 8.25 pt |
| 字号阶梯（印刷 pt） | 轴标题 8.25 / 刻度与图例 7.0（CJK 印刷下限）/ 图题 9.9；任何文字不低于 5 |
| 线与点 | 轴线 0.45 mm、刻度长 1.09 mm、数据点直径 1.45 mm |
| 分类色 | Okabe-Ito 8 色，`eco_pal(n)` / `eco_pal_named(x)` 按因子水平取；单图系列 ≤6，>8 组必须加 shape/linetype 冗余编码 |
| 语义色 | enriched `#D55E00` / depleted `#0072B2` / ns 中性灰 `0.55`（`eco_sign_pal`）；Mantel P 值三级同源（`eco_pval_pal`） |
| 连续色 | 相关热图保留 RdBu 发散带；顺序量用 viridis/cividis |

上游口径一律写指针（不在本技能复制正文）：

- R 排版与字号下限：`academic-toolkit/skills/fig-academic/references/typography.md`
- R 导出设备（PNG 走 `png(type="cairo")`、PDF 走 `cairo_pdf`、showtext 与 PNG 的配用）：`academic-toolkit/skills/fig-academic/references/r-rendering.md`
- 印刷字号公式与 CJK 字体链：`academic-toolkit/skills/_utils/academic.mplstyle`
- 语义色板仲裁链与 Okabe-Ito 实践组合：`academic-toolkit/skills/paper-figure/references/semantic-palette.md`
- 字号/尺寸机检（接受 `.R`）：`academic-toolkit/skills/fig-academic/scripts/check_figure.py`

## Template Catalog

| Template | Method | Script | 适用场景 |
|----------|--------|--------|----------|
| `pcoa_marginal_box` | Bray-Curtis PCoA + 边缘箱线（Tukey 字母）+ PERMANOVA R² 注释 | `scripts/PCoA.R` | 分组样方降维排序：主图+两侧分布箱线 patchwork 拼版（100×106 mm） |
| `rda_biplot_envfit` | vegan `rda` 双标图 + 环境因子箭头（自动标签角度）+ `envfit` R² 显著性条形图 + `permutest`(999) | `scripts/RDA.R` | 环境因子–群落梯度分析（58×58 mm 主图 + 60×68 mm 显著性图，两组各一套） |
| `mantel_heatmap` | linkET Mantel 检验 + RdBu 渐变相关热图 | `scripts/Manteltest.R` | 两个距离矩阵（环境 × 群落）的整体与逐因子关联（138×98 mm） |
| `procrustes_overlay` | vegan `procrustes` 叠加一致性分析（Mantel/Procrustes 统计量由本次计算写入注记） | `scripts/Procrustes.R` | 两套排序/两种群落的一致性比较（58×58 mm） |
| `corr_regression_panel` | 多变量回归散点组合（ggpmisc 方程+R² 标注，cowplot 拼版） | `scripts/Correlations.R` | 环境因子 vs 目标指标逐一回归成面板（90×120 mm） |
| `enrich_zscore_compare` | 富集物种 z-score 差异比较（ggsci 配色 + rstatix 显著性） | `scripts/enrich_species_compare.R` | 分组间差异物种富集方向与幅度（128×110 mm） |

## Workflow

1. **选模板**：按数据问题选一行；拿不准时先跑 `pcoa_marginal_box` 看分组是否可分。
2. **备数据**：按下方输入契约准备 CSV，放到数据文件夹（脚本内 `read.csv` 用相对路径，R 工作目录须指向数据所在文件夹；样式文件按脚本自身路径自动定位，不依赖工作目录）。
3. **改分组列名**：每个脚本顶部"数据读取区"的列名（如 `Carrier`/`Treat`/`Region`）替换成你的分组/梯度列。
4. **跑脚本**：Rscript 或 RStudio；依赖一次性安装见下方依赖清单。`Rscript scripts/PCoA.R` 即可，脚本会自动 `source()` 同目录的 `_eco_style.R`。
5. **换配色**：分组色改 `eco_pal_named(<你的分组列>)`，方向语义色改 `eco_sign_pal`；禁止在脚本里新写裸 hex，也不得引入"假精度"渐变。
6. **导出**：`ggsave(..., width = <mm>, height = <mm>, units = "mm", device = cairo_pdf)`，`width` 必须写在 `height` 之前（`check_figure.py` 的解析口径）；PNG 高 dpi 版本按 `fig-academic/references/r-rendering.md` 走 `png(type="cairo")`。
7. **新增模板**：必须调用 `eco_theme(<成品宽>)`、用 `eco_*` 取色与取字号，并在上表登记成品 mm 尺寸。

## Input Contract

- `otutab.csv`：行=物种/OTU，列=样方，值=丰度（PCoA/Mantel 输入，需转置后计算）。
- `metadata.csv`：行=样方，列=分组变量（如 Carrier/Region），row.names=1。
- `envfactors*.csv`：行=样方，列=环境因子 + 分组列（RDA 输入）。
- `sum_g_*.csv`：行=物种（按属聚合），列=样方（RDA 物种排序输入）。
- 缺列/缺行名时脚本会静默错位——**先 `head()` 核对再跑**，跑不通就修数据，禁止编造数值。

## Output Contract

- 每模板产出 1–2 个矢量 PDF（毫米制印刷尺寸见目录表）+ 控制台统计结果
  （PERMANOVA R²/P、envfit r/p、约束/非约束方差占比、Procrustes 一致性统计）。
- 统计结果必须原文进入报告表格，禁止只截图不报数。
- 图中注记的统计量必须来自本次运行（如 `Procrustes.R` 从 `protest()`/`mantel()` 取 M2、r 与 p），禁止沿用上游论文数字。

## 依赖（R 包）

vegan, ape, ggplot2 (≥3.4，`linewidth` 语义), dplyr, tidyr, reshape, patchwork, cowplot,
gridExtra, ggpmisc, ggsci, ggpubr, rstatix, linkET, multcomp, RColorBrewer, digest

可选：`systemfonts`（字体族探测，缺省时退回 `sysfonts`/设备字体表）、`showtext`（需要转曲时自行 `showtext_auto()`）。

## Provenance & License

- 来源、pinned commit 与本地化改写范围见 `references/UPSTREAM.md`。
- **上游未声明 License**（无 LICENSE 文件）：本技能按"本地化改写衍生物"形态维护，
  不得据此推断可再分发授权。
- 上游研究数据（CSV/TXT）未 vendored——模板价值在代码范式，数据须换成本地真实数据。

## 执行清单与溯源

若本技能被编排为引擎步骤执行，R 渲染命令经执行会话 `run` 下发（声明 argv、依赖与产物）；
backend（R 版本+包版本）、输入输出与指纹由程序自动采集进执行清单，模型不手工调用
`engine.step_manifest.write_manifest` 或自填 SHA-256；图件另受 figure_provenance 门禁约束。
