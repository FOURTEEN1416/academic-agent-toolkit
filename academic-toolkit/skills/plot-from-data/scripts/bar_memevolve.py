"""
复现 image1: MemEvolve 论文风格柱状图
特征：配对柱（baseline vs method）+ 箭头 + 红色百分比标注 + 虚线参考线
来源：MemEvolve: Meta-Evolution of Agent Memory Systems

薄壳模板：字体族/字号阶梯/线宽/配色循环/保存护栏统一由
academic-toolkit/skills/_utils/plot_utils.py 的 setup_style + save_fig 提供；
本文件只保留该图型的语法差异（几何、标注、边框可见性、图例位置）。
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

_SKILLS_DIR = Path(__file__).resolve().parents[2]
if str(_SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILLS_DIR))

from _utils.plot_utils import save_fig, set_paper_placement, setup_style

setup_style()

OUTPUT = 'figures/fig_bar_memevolve.png'

# ── 颜色系统 ──────────────────────────────────────────────
COLOR_BASELINE = '#A8C8E8'   # 浅钢蓝，baseline 柱
COLOR_METHOD   = '#1B3D6E'   # 深海军蓝，method 柱
COLOR_DELTA    = '#CC2200'   # 红色，标注增益

# ── 数据 ─────────────────────────────────────────────────
panels = [
    {
        'title': 'OWL-Workforce',   # emoji 字体不支持，用文字替代
        'groups': ['Web', 'xBench', 'TaskCraft', 'GAIA'],
        'baseline': [58.1, 55.2, 58.7, 59.3],
        'method':   [62.3, 61.2, 65.5, 61.0],
        'delta':    ['+7.1%', '+10.9%', '+11.9%', '+2.7%'],
        'ylim':     (40, 71),   # 原图左图 Y 轴 40-70
    },
    {
        'title': 'CK-Pro',
        'groups': ['Web', 'xBench', 'TaskCraft', 'GAIA'],
        'baseline': [61.2, 55.8, 63.8, 58.1],
        'method':   [63.8, 64.8, 67.8, 63.1],
        'delta':    ['+4.2%', '+16.1%', '+4.8%', '+8.4%'],
        'ylim':     (40, 76),   # 原图右图 Y 轴 40-75
    },
]

# ── 画布 ─────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharey=False)

BAR_W    = 0.28
GAP      = 0.01      # 两柱几乎紧贴（原图约为 0）
ARROW_KW = dict(arrowstyle='->', color='black', lw=1.2)

for ax, panel in zip(axes, panels):
    groups   = panel['groups']
    baseline = np.array(panel['baseline'])
    method   = np.array(panel['method'])
    delta    = panel['delta']
    n        = len(groups)
    x        = np.arange(n)

    # 柱体
    ax.bar(x - (BAR_W + GAP) / 2, baseline, width=BAR_W,
           color=COLOR_BASELINE, zorder=3)
    ax.bar(x + (BAR_W + GAP) / 2, method,   width=BAR_W,
           color=COLOR_METHOD,   zorder=3)

    # 虚线参考线（baseline 高度）
    for i, (bl, me) in enumerate(zip(baseline, method)):
        # 水平虚线从 baseline 柱顶延伸到 method 柱顶
        ax.plot([x[i] - BAR_W, x[i] + BAR_W + GAP / 2],
                [bl, bl], color='black', lw=0.9, ls='--', zorder=4)

        # 箭头（baseline 顶 → method 顶）
        ax.annotate('', xy=(x[i] + (BAR_W + GAP) / 2, me - 0.3),
                    xytext=(x[i] + (BAR_W + GAP) / 2, bl + 0.3),
                    arrowprops=ARROW_KW, zorder=5)

        # 红色百分比标注
        ax.text(x[i] + (BAR_W + GAP) / 2, me + 0.6,
                delta[i], color=COLOR_DELTA,
                ha='center', va='bottom', fontweight='bold')

    # 轴装饰：原图轴标签明显加粗
    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontweight='bold')
    ax.set_ylabel('Accuracy (Pass@1)', fontweight='bold')
    ax.set_ylim(*panel['ylim'])
    ax.yaxis.set_major_locator(plt.MultipleLocator(5))

    # 四边框全显（该图型签名，覆盖随机版式族的 L 形默认）
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(1.5)
        spine.set_color('black')
    ax.tick_params(length=0)
    ax.set_axisbelow(True)

    # 标题（左上角）：粗体，颜色深蓝对应原图
    ax.text(0.04, 0.97, panel['title'], transform=ax.transAxes,
            fontweight='bold', va='top', ha='left', color='#003F6C')

set_paper_placement(fig)
save_fig(fig, OUTPUT)
