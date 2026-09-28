---
name: plot-from-data
description: "有数据且指定论文风格时，套用预置样式产出投稿级 matplotlib 图。"
---

# Plot From Data

Generate a paper-quality figure by picking a style template and filling it with user data. All outputs are `dpi=300` PNG.

## Available Styles

| Style | Type | Script | 适用场景 |
|-------|------|---------|---------|
| `bar_paired_delta` | 柱状图 | `scripts/bar_memevolve.py` | Baseline vs method 配对对比 + 增益箭头 |
| `bar_grouped_hatch` | 柱状图 | `scripts/bar_spice.py` | 多方法消融，主方法斜线填充，柱顶数值 |
| `line_confidence_band` | 折线图 | `scripts/line_selfdistill.py` | 带置信区间的训练曲线 |
| `line_training_curve` | 折线图 | `scripts/line_aime.py` | 垂直断点线 + 水平参考线 |
| `line_loss_with_inset` | 折线图 | `scripts/line_loss_inset.py` | L 形 spine + 局部放大 inset |
| `scatter_tsne_cluster` | 散点图 | `scripts/scatter_tsne.py` | t-SNE 聚类 + 注释框 |
| `scatter_broken_axis` | 散点图 | `scripts/scatter_break.py` | 折断 X 轴，多 marker 系列 |
| `radar_dual_series` | 雷达图 | `scripts/radar_dora.py` | 双方法多维对比，正八边形网格 |
| `bar_grey_hatch_highlight` | 柱状图 | `scripts/bar_spice.py` | 灰阶分组 + 红斜线独占强调主方法 |
| `line_band_baseline` | 折线图 | `scripts/line_selfdistill.py` | 连续训练曲线 + 置信带 + 外部基线点线 |
| `line_marker_scaling` | 折线图 | `scripts/line_selfdistill.py` | 离散 scaling + 大描边圆点，四边全显 |
| `scatter_pareto_frontier` | 散点图 | `scripts/scatter_break.py` | Pareto 前沿星标 + 淡背景散点云 |
| `table_heatmap_numeric` | 数值表 | `scripts/table_classwise_iou.py` | 无轴数值表 + 胜格红色热力底纹 |

## Style Samples（examples/，仅本地）

`examples/` 收录 20 张风格样例（10 原图 + 10 复现图），来自只读 vendor 快照
`vendor/forks/paper-plot-skills/{originals,repro}/`。**红线：样例仅本地使用、
不再分发**，本技能整体 gitignored，样例与卡片不得进入任何将公开分发的产物。
2026-09-22 风格卡扩编批（V3）新增上表后 5 张卡片。

## Workflow

```
1. 确认用户的图类型和数据
2. 选择对应 style（如不确定，询问用户或根据数据形状推断）
3. 读取对应 references/<style_name>.md 获取精确参数
4. 复制对应 scripts/<script>.py，替换数据区（脚本顶部有清晰注释标注数据区）
5. 运行：python3 scripts/<script>.py
6. 检查输出，必要时微调颜色/标签/字号
```

## Data Substitution Tips

每个 repro 脚本的数据区在文件顶部，通常是 `np.array(...)` 或字典。替换规则：
- 保持数组维度和类型不变
- 若类别数变化（如从 4 组改为 6 组），同步调整颜色列表和宽度计算
- x 轴标签、图例标签直接修改对应字符串列表

## Detailed Style Parameters

Read the corresponding file in `references/` for exact `rcParams`, colors, font sizes, spine settings, and tick directions before generating:

- Bar: `references/bar_paired_delta.md`, `references/bar_grouped_hatch.md`, `references/bar_grey_hatch_highlight.md`
- Line: `references/line_confidence_band.md`, `references/line_training_curve.md`, `references/line_loss_with_inset.md`, `references/line_band_baseline.md`, `references/line_marker_scaling.md`
- Scatter: `references/scatter_tsne_cluster.md`, `references/scatter_broken_axis.md`, `references/scatter_pareto_frontier.md`
- Radar: `references/radar_dual_series.md`
- Table: `references/table_heatmap_numeric.md`
