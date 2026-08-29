# FIGURES-01 科研绘图基准（figures_and_document_production 域）

## 任务

给定 `data/measurements.csv`（3 组 × 5 次重复测量），在目标工作区完成：

1. **数据图**：组间对比图（含误差棒），300dpi PNG 输出到 `figures/fig_results.png`，并写 `figures/latex_includes.tex`（含题注与 label）；
2. **架构图**：用 FigureSpec JSON 渲染一张自描述"测量→统计→成图"流程 SVG 到 `figures/diagrams/`；
3. **溯源**：`figures/FIGURE_PROVENANCE.json` 覆盖全部图产物（文件、生成脚本、数据来源、生成器）；
4. **一致性**：题注声称的统计口径必须与实际计算一致（抽样数、误差棒语义）。

## 评分

运行 `python evaluate.py <工作区>`，全检查通过得 PASS。详见 contract.json。
