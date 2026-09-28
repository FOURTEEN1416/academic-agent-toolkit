# Style: bar_grey_hatch_highlight（灰阶分组柱 + 红色斜线填充强调主方法）

**类型**：分组柱状图（每组 3 柱），主方法用红底白斜线 hatch 从灰阶中脱颖而出
**样例图**：`examples/bar_spice.png`（原图，取 (b) 面板）、`examples/bar_spice_repro.png`（复现）
**样例来源**：`vendor/forks/paper-plot-skills/originals/bar_spice.png`（只读 vendor 快照，仅本地使用、不再分发）
**复现脚本**：`scripts/bar_spice.py`（同一原图 (a) 面板的暖色版见 `bar_grouped_hatch`，本卡是灰阶单强调色版）

## 适用场景
主方法 vs 2 个同族 baseline 的 benchmark 对比；希望读者注意力**只**落在主方法上
（灰阶弱化对手，红色 hatch 独占强调）。与 `bar_grouped_hatch` 的区别：全图单强调色、
对手去彩、主方法数值标签加粗。

## 视觉特征
- 颜色：浅灰 `#D9D9D9` / 中灰 `#A6A6A6`（两个 baseline）+ 正红 `#D00000`（主方法，
  hatch=`'//'`，白色斜线，`edgecolor` 与 facecolor 同红）
- 数值标签：柱顶上方；baseline 用灰色常规字，主方法用**黑色加粗**（约 11pt，serif）
- 图例：右上角图内，无边框或极浅框；主方法条目文字加粗红色
- Spine：仅左 + 下（开口式），深灰细线
- 网格：仅水平方向极浅灰实线（`color='#EEEEEE'`，`lw=0.8`，`axis='y'`）
- 字体：serif（Times/Palatino 感），轴标签约 13pt 常规不加粗
- 柱宽：组内 3 柱紧凑（w≈0.25，间隙≈0.02），组间距大

## 关键参数
```python
COLORS = ['#D9D9D9', '#A6A6A6']
C_MAIN = '#D00000'
ax.bar(x + i*w, vals[i], width=0.25, color=COLORS[i])
ax.bar(x + 2*w, ours, width=0.25, color=C_MAIN, hatch='//', edgecolor=C_MAIN)
for rect in bars_main:
    ax.text(rect.get_x()+w/2, rect.get_height()+0.5, f'{v:.1f}',
            fontweight='bold', ha='center', fontsize=11)
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
ax.grid(axis='y', color='#EEEEEE', lw=0.8)
```

## 已知限制
- 超过 3 系列时灰阶层次不够，改回 `bar_grouped_hatch` 的渐进色方案
- hatch 在 dpi<200 输出会发灰，保持 dpi=300
