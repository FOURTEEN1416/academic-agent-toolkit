# Style: table_heatmap_numeric（数值表 + 单元格红色热力底纹）

**类型**：无坐标轴数值表（per-class 指标对比），单元格按数值深浅上红色底纹
**样例图**：`examples/classwise_iou.png`（原图）、`examples/classwise_iou_repro.png`（复现）
**样例来源**：`vendor/forks/paper-plot-skills/originals/classwise_iou.png`（只读 vendor 快照，仅本地使用、不再分发）
**复现脚本**：`scripts/table_classwise_iou.py`（改编自 `vendor/forks/paper-plot-skills/plot-from-image/scripts/classwise_iou_table.py`）

## 适用场景
20+ 个类别、2 行方法对比（Base vs Ours），既要精确数值又要一眼看出强弱分布；
普通 heatmap 太"图"、普通表格太"干"时的折中方案。

## 视觉特征
- 字体：serif（Computer Modern 感），数值约 13pt，行/列标签同族不加粗
- 布局：无 axes 边框、无网格线；行标签左对齐（`Base` / `Ours`），列标签在数值行下方
- 底纹：**每列两行中数值更高者**上红色底纹，深浅 ∝ 两行差值绝对值
  （差 ~15 → 深红近 `#B2182B` 且白字；差 ~1 → 极浅粉近白黑字；打平不上色）
- 面板标题：`(b) Class-Wise IoU Results` 居中置于表下方，serif 约 16pt
- 尾列 `avg.` 与其他列同权重，不加竖线分隔

## 关键参数
```python
fig, ax = plt.subplots(figsize=(16.71, 2.09))  # AR=8.0，与样例一致
ax.set_axis_off()
# 每格：Rectangle((col, row), 1, 1, facecolor=cmap(norm(v)), edgecolor='none')
ax.text(x, y, f'{v:.1f}', ha='center', va='center', fontsize=13,
        color='white' if v > hi_thresh else 'black')
ax.text(-0.5, y_row, label, ha='right', va='center', fontsize=13)  # 行标签
```

## 数据替换约定
```python
LABELS = [...]        # 列标签（20 项，含 avg.）
BASE   = np.array([...])
OURS   = np.array([...])
```
行数不限于 2；颜色归一化范围取全表 min/max。

## 已知限制
- 列数 > 24 时文字重叠，需降字号或拆两面板
- 红色系外配色需自行重定 cmap，保持"单色相 + 白→深"即可不破坏风格
