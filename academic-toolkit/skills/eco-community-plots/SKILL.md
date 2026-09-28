---
name: eco-community-plots
description: "生态群落数据专用可视化：物种丰度矩阵、排序图（PCA/NMDS/RDA）、多样性指数、稀疏曲线、群落热图与聚类。触发词：生态群落图、物种丰度、NMDS、RDA、稀疏曲线、多样性指数。"
---

# Eco Community Plots

Six publication-grade R templates vendored from a peer-reviewed community-ecology study
(plastisphere–microalgae). Every template exports **millimetre-sized PDF at print scale**
(58–138 mm), carries significance markers, and prints explained variance on ordination axes —
the three habits this skill exists to propagate.

## Template Catalog

| Template | Method | Script | 适用场景 |
|----------|--------|--------|----------|
| `pcoa_marginal_box` | Bray-Curtis PCoA + 边缘箱线（Tukey 字母）+ PERMANOVA R² 注释 | `scripts/PCoA.R` | 分组样方降维排序：主图+两侧分布箱线 patchwork 拼版（100×106 mm） |
| `rda_biplot_envfit` | vegan `rda` 双标图 + 环境因子箭头（自动标签角度）+ `envfit` R² 显著性条形图 + `permutest`(999) | `scripts/RDA.R` | 环境因子–群落梯度分析（58×58 mm 主图 + 60×68 mm 显著性图） |
| `mantel_heatmap` | linkET Mantel 检验 + RdBu 渐变相关热图 | `scripts/Manteltest.R` | 两个距离矩阵（环境 × 群落）的整体与逐因子关联（138×98 mm） |
| `procrustes_overlay` | vegan `procrustes` 叠加一致性分析 | `scripts/Procrustes.R` | 两套排序/两种群落的一致性比较 |
| `corr_regression_panel` | 多变量回归散点组合（ggpmisc 方程+R² 标注，cowplot 拼版） | `scripts/Correlations.R` | 环境因子 vs 目标指标逐一回归成面板（90×120 mm） |
| `enrich_zscore_compare` | 富集物种 z-score 差异比较（ggsci 配色 + rstatix 显著性） | `scripts/enrich_species_compare.R` | 分组间差异物种富集方向与幅度（128×110 mm） |

## Workflow

1. **选模板**：按数据问题选一行；拿不准时先跑 `pcoa_marginal_box` 看分组是否可分。
2. **备数据**：按下方输入契约准备 CSV，放到脚本同目录（脚本内 `read.csv` 用相对路径，R 工作目录须指向数据所在文件夹）。
3. **改分组列名**：每个脚本顶部"数据读取区"的列名（如 `Carrier`/`Treat`/`Region`）替换成你的分组/梯度列。
4. **跑脚本**：Rscript 或 RStudio；依赖一次性安装见下方依赖清单。
5. **换配色**（可选）：脚本内硬编码色值替换须先过本仓 paper-figure 语义色板（Okabe-Ito 系），禁止引入假精度配色。
6. **导出**：模板默认 PDF（矢量）；投期刊/竞赛按需加 PNG 高 dpi 版本。

## Input Contract

- `otutab.csv`：行=物种/OTU，列=样方，值=丰度（PCoA/Mantel 输入，需转置后计算）。
- `metadata.csv`：行=样方，列=分组变量（如 Carrier/Region），row.names=1。
- `envfactors*.csv`：行=样方，列=环境因子 + 分组列（RDA 输入）。
- `sum_g_*.csv`：行=物种（按属聚合），列=样方（RDA 物种排序输入）。
- 缺列/缺行名时脚本会静默错位——**先 `head()` 核对再跑**，跑不通就修数据，禁止编造数值。

## Output Contract

- 每模板产出 1–2 个矢量 PDF（毫米制印刷尺寸，见目录表）+ 控制台统计结果
  （PERMANOVA R²/P、envfit r/p、约束/非约束方差占比、Procrustes 一致性统计）。
- 统计结果必须原文进入报告表格，禁止只截图不报数。

## 依赖（R 包）

vegan, ape, ggplot2, dplyr, tidyr, reshape2, patchwork, cowplot, gridExtra, ggprism,
ggpmisc, ggsci, ggpubr, rstatix, linkET, multcomp, RColorBrewer, digest

## Provenance & License

- 来源与 pinned commit 见 `references/UPSTREAM.md`。
- **上游未声明 License**：本技能整目录被 .gitignore 隔离（同 plot-from-data 先例），仅本地使用，不得再分发。
- 上游研究数据（CSV/TXT）未 vendored——模板价值在代码范式，数据须换成本地真实数据。

## 执行清单与溯源

若本技能被编排为引擎步骤执行，R 渲染命令经执行会话 `run` 下发（声明 argv、依赖与产物）；
backend（R 版本+包版本）、输入输出与指纹由程序自动采集进执行清单，模型不手工调用
`engine.step_manifest.write_manifest` 或自填 SHA-256；图件另受 figure_provenance 门禁约束。
