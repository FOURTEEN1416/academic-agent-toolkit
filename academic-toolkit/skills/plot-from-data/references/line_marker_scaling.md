# Style: line_marker_scaling（离散规模 scaling 折线 + 大实心描边圆点）

**类型**：折线图，x 轴为离散模型参数量（0.6/1.7/4/8），每个数据点大圆标记 + 细置信带
**样例图**：`examples/line_selfdistill_scale.png`（原图）、`examples/line_selfdistill_scale_repro.png`（复现）
**样例来源**：`vendor/forks/paper-plot-skills/originals/line_selfdistill_scale.png`（只读 vendor 快照，仅本地使用、不再分发）
**复现脚本**：`scripts/line_selfdistill.py`（image3 分支；连续训练曲线版见 `line_band_baseline`，umbrella 卡 `line_confidence_band` 的 Type B 在本卡原子化）

## 适用场景
"随规模/随预算变好"类论证：横轴只有 4–6 个离散档位，需要读者逐点读数，
而不是看连续趋势。

## 视觉特征
- 字体：serif + `usetex=True`（Computer Modern；无 TeX 用 STIX Two Text）
- 标题：图上方居中，serif 常规字重（不加粗），约 14pt
- Spine：**四边全显**（与 train 版的 L 形不同），黑色约 1.2pt，刻度朝内
- x 轴：等间距位置 + 手动刻度标签（`[0.6, 1.7, 4, 8]`），**不用对数轴**（避免变形）
- 线：lw≈1.6；绿 `#2CA02C`（主方法）、蓝 `#1F77B4`、浅灰 `#BCBCBC`
- 标记：实心圆 `marker='o'`，s≈90，黑描边 `markeredgewidth≈1.2`，白边内填充即系列色
- 置信带：同色 `fill_between` alpha≈0.12，带宽窄（离散点 std 小）
- 图例：右下角图内，无边框；**系列名在左、线+点 handle 在右**，主方法名加粗

## 关键参数
```python
x_pos = np.arange(len(labels))                    # 0,1,2,3
ax.set_xticks(x_pos); ax.set_xticklabels(['0.6','1.7','4','8'])
ax.plot(x_pos, y, color=c, lw=1.6, marker='o', markersize=9,
        markeredgecolor='black', markeredgewidth=1.2)
ax.fill_between(x_pos, y-lo, y+hi, color=c, alpha=0.12)
ax.legend(frameon=False, loc='lower right', handler_map/handleorder 使文字在前)
for sp in ax.spines.values(): sp.set_visible(True); sp.set_linewidth(1.2)
ax.tick_params(direction='in')
```

## 已知限制
- 档位数 >7 时圆点互相贴近，缩 markersize 到 6 或改 `line_confidence_band` 连续版
- usetex 缺失时图例加粗改 `fontweight='bold'` 即可，视觉差异小
