# Style: scatter_pareto_frontier（Pareto 前沿星标 + 淡背景散点云）

**类型**：散点图：主方法前沿用大星标 + 粉色虚线连接，非前沿运行点作淡色背景云
**样例图**：`examples/scatter_break.png`（原图，取左面板前沿语法）、`examples/scatter_break_repro.png`（复现）
**样例来源**：`vendor/forks/paper-plot-skills/originals/scatter_break.png`（只读 vendor 快照，仅本地使用、不再分发）
**复现脚本**：`scripts/scatter_break.py`（该脚本的折断轴语法见 `scatter_broken_axis`；本卡抽出其中独立可复用的前沿语法）

## 适用场景
两目标 trade-off（成本 vs 精度类）展示：需要同时表达"这条前沿是我们的方法族"
与"背景里还有很多非前沿采样点"，并给若干外部系统各自专属 marker。

## 视觉特征
- 前沿系列：大星标 `marker='*'`（s≈380），红填充 `#D62728` + 黑描边（`linewidths=1.2`），
  相邻前沿点用浅粉虚线 `#F4B6B6`（lw≈2, ls='--'）按序连接
- 背景云：同系浅粉小圆点（s≈26, alpha≈0.5, 无描边），非 Pareto 运行
- 对比系列：紫色系实线连接的大圆点（`#8172B3`，s≈160，黑描边）；
  单点系统各给独立 marker——橙三角 `^`（`#FF7F0E`）、蓝菱形 `D`（`#1F77B4`）、
  紫叉 `X`（`#7F4FA3`），均 s≈200+、黑描边
- 图例：右下角图内，白底浅灰框，条目顺序 = 主方法→背景→外部系统
- 字体：sans-serif；轴标签约 13pt 加粗；刻度朝外
- Spine：左 + 下（L 形），黑色约 1pt

## 关键参数
```python
ax.scatter(cx, cy, s=26, c='#F4B6B6', alpha=0.5, lw=0)          # 背景云
ax.plot(fx, fy, ls='--', lw=2, color='#F4B6B6', zorder=1)        # 前沿连线
ax.scatter(fx, fy, marker='*', s=380, c='#D62728', edgecolors='black',
           linewidths=1.2, zorder=3)
ax.scatter([x_mce], [y_mce], marker='^', s=220, c='#FF7F0E', edgecolors='black')
```

## 已知限制
- 前沿点 >12 个时虚线连线视觉噪声大，改只描星不连线
- 与折断轴（`scatter_broken_axis`）可叠加，但两卡参数勿同时改 marker 尺寸
