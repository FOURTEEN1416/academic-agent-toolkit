"""
Reproduce: image7.png — t-SNE Latent Memory Visualization
Style: light gray grid, 4-spine box, color-coded cluster legend.
（原图的簇内注释框会压住散点，save_fig 遮挡硬闸拒绝导出，已改由图例承担身份区分。）

薄壳模板：字体族/字号阶梯/线宽/配色循环/保存护栏统一由
academic-toolkit/skills/_utils/plot_utils.py 的 setup_style + save_fig 提供；
本文件只保留该图型的语法差异（聚类几何、四边框、图例位置）。
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

OUTPUT = 'figures/fig_scatter_tsne.png'

rng = np.random.default_rng(42)

def cluster(cx, cy, n, rx=8, ry=8, shape='round'):
    """生成一个椭圆形聚类，shape='round'|'elongated'"""
    if shape == 'elongated':
        angles = rng.uniform(0, 2 * np.pi, n)
        r = rng.rayleigh(1.0, n)
        x = cx + rx * r * np.cos(angles)
        y = cy + ry * r * np.sin(angles)
    else:
        x = rng.normal(cx, rx, n)
        y = rng.normal(cy, ry, n)
    return x, y


# ---- 数据集颜色（严格参照原图） ----
DS = {
    'GSM8K':    {'color': '#6A4C93', 'n': 900,  'cx':  10, 'cy':  12, 'rx': 9,  'ry': 12},
    'MATH':     {'color': '#D651A0', 'n': 700,  'cx':  8,  'cy':  32, 'rx': 7,  'ry': 8},
    'GPQA':     {'color': '#F06292', 'n': 300,  'cx':  18, 'cy':  50, 'rx': 5,  'ry': 6},
    'KodCode':  {'color': '#FF8A65', 'n': 500,  'cx':  38, 'cy': -10, 'rx': 9,  'ry': 10},
    'BCB':      {'color': '#FFB74D', 'n': 600,  'cx':  18, 'cy': -30, 'rx': 10, 'ry': 9},
    'ALFWorld': {'color': '#FFF176', 'n': 280,  'cx': -10, 'cy': -42, 'rx': 12, 'ry': 10},  # 黄色！
    'TriviaQA': {'color': '#C888E8', 'n': 700,  'cx': -42, 'cy':   5, 'rx': 14, 'ry': 22},
}

# ---- 注释框已移除：簇内文本会压住散点，save_fig 遮挡硬闸会拒绝导出。
#      数据集身份由图例承担（颜色与 DS 色值一一对应）。----

fig, ax = plt.subplots(figsize=(7.5, 6.2))

for name, cfg in DS.items():
    x, y = cluster(cfg['cx'], cfg['cy'], cfg['n'], cfg['rx'], cfg['ry'])
    ax.scatter(x, y, c=cfg['color'], s=14, alpha=0.55,
               linewidths=0, rasterized=True, label=name, zorder=2)

# ---- Axes 样式 ----
ax.set_xlabel('t-SNE Component 1', fontweight='bold')
ax.set_ylabel('t-SNE Component 2', fontweight='bold')
ax.set_title(
    'Latent Memory Visualization\n(across all benchmarks)',
    fontweight='bold', pad=8, linespacing=1.4,
)

ax.set_xlim(-88, 70)
ax.set_ylim(-75, 80)
ax.xaxis.set_major_locator(plt.MultipleLocator(20))
ax.yaxis.set_major_locator(plt.MultipleLocator(20))

# 四边框，深灰接近原图
for sp in ax.spines.values():
    sp.set_visible(True)
    sp.set_linewidth(0.9)
    sp.set_color('#333333')

ax.tick_params(direction='in', length=4, width=0.8, color='#333333')

# 浅灰点线网格（原图风格）
ax.grid(True, color='#E0E0E0', linewidth=0.6, linestyle=':', zorder=0)
ax.set_axisbelow(True)

# ---- 图例（原图有白底浅灰框） ----
ax.legend(
    loc='upper right',
    frameon=True,
    facecolor='white',
    edgecolor='#CCCCCC',
    framealpha=1.0,
    markerscale=1.0,
    handlelength=0.8,
    handleheight=0.8,
    handletextpad=0.5,
    labelspacing=0.25,
    borderpad=0.5,
    borderaxespad=0.5,
)

set_paper_placement(fig)
save_fig(fig, OUTPUT)
