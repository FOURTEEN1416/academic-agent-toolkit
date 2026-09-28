# Style: line_band_baseline（连续训练曲线 + 置信带 + 外部基线点线）

**类型**：折线图，连续 step 训练曲线，半透明置信带，叠加一条灰色点线表示外部参照系统
**样例图**：`examples/line_selfdistill_train.png`（原图）、`examples/line_selfdistill_train_repro.png`（复现）
**样例来源**：`vendor/forks/paper-plot-skills/originals/line_selfdistill_train.png`（只读 vendor 快照，仅本地使用、不再分发）
**复现脚本**：`scripts/line_selfdistill.py`（image2 分支；离散 scaling 版见 `line_marker_scaling`，umbrella 卡 `line_confidence_band` 的 Type A 在本卡原子化）

## 适用场景
展示自身方法随训练/生成预算演进，并需要一条"别人的水平线"（如商用模型、
oracle）作为参照锚点。

## 视觉特征
- 字体：serif + `usetex=True`（Computer Modern）；标题居中常规字重
- Spine：仅左 + 下（L 形开口），黑色约 0.9pt，刻度朝外
- 主线：lw≈2.2（比 scaling 版粗），绿 `#2CA02C` / 蓝 `#1F77B4`，无 marker
- 置信带：同色 alpha≈0.15 `fill_between`，宽度随训练推进收窄（`std·exp(-t/τ)` 模拟）
- 基线参照：水平**点线** `ls=':'`，浅灰 `#9E9E9E`，lw≈2；图例条目文字在前、线在后
- 图例：右下角图内，无边框；主方法名加粗，其余常规
- x 轴刻度：`0, 5000, ...` 或 k 格式化；y 轴留 10% 顶部余量

## 关键参数
```python
t = np.linspace(0, 20000, 200)
std = sigma0 * np.exp(-t / tau) + floor
ax.fill_between(t, y-std, y+std, color=c, alpha=0.15)
ax.plot(t, y, color=c, lw=2.2)
ax.axhline(baseline, color='#9E9E9E', ls=':', lw=2, label='Claude Sonnet 4')
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
ax.legend(frameon=False, loc='lower right')
```

## 已知限制
- 两条主线前段几乎重合时（如样例 0–2500 段），图例颜色是唯一区分，勿再叠第三系列
- 基线点线勿改虚线 `--`——与 `line_confidence_band`/`line_training_curve` 的
  参考线语义冲突（点线=外部系统，虚线=自身阶段分界）
