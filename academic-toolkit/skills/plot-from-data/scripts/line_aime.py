"""
Reproduce: image6.png — AIME avg@32 training curve
Two lines with vertical breakpoint markers + horizontal reference line.
Style: 4-spine box, no grid, right-bottom legend.

薄壳模板：字体族/字号阶梯/线宽/配色循环/保存护栏统一由
academic-toolkit/skills/_utils/plot_utils.py 的 setup_style + save_fig 提供；
本文件只保留该图型的语法差异（曲线、断点线、四边框、图例位置）。
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

OUTPUT = 'figures/fig_line_aime.png'

rng = np.random.default_rng(42)

# ---- 模拟数据 ----
# w/ Dynamic Sampling (purple): 0-2200 steps, rises fast, ends ~0.42
steps_dyn_a = np.arange(0, 2300, 50)
y_dyn_a = 0.43 * (1 - np.exp(-steps_dyn_a / 600))
y_dyn_a += rng.normal(0, 0.012, len(steps_dyn_a))
y_dyn_a = np.clip(y_dyn_a, 0, 0.45)
y_dyn_a[:2] = [0.03, 0.03]   # cold start

# w/o Dynamic Sampling (cyan): 0-9000, slower rise, peaks ~0.42 at step 6000, then drops
steps_nodyn = np.arange(0, 9100, 100)
y_nodyn = 0.38 * (1 - np.exp(-steps_nodyn / 1200))
y_nodyn += rng.normal(0, 0.012, len(steps_nodyn))
y_nodyn = np.clip(y_nodyn, 0, 0.44)
y_nodyn[:2] = [0.01, 0.02]
# After step 6000, add gradual decline
mask = steps_nodyn > 6000
y_nodyn[mask] -= 0.06 * (steps_nodyn[mask] - 6000) / 3000

C_DYN   = '#5B0DAD'   # 更深紫，接近原图
C_NODYN = '#5BBCCA'   # 柔和青绿
C_REF   = '#3D78C2'   # 独立蓝色（参考线，与曲线色区分）
STEP_DYN  = 2200      # 紫色垂直线
STEP_NODYN = 6050     # 青色垂直线
REF_Y = 0.43          # 水平参考线

fig, ax = plt.subplots(figsize=(9.0, 4.8))

# ---- 两条主线 ----
ax.plot(steps_dyn_a, y_dyn_a, color=C_DYN, lw=1.4, zorder=3, label='w/ Dynamic Sampling')
ax.plot(steps_nodyn, y_nodyn, color=C_NODYN, lw=1.4, zorder=3, label='w/o Dynamic Sampling')

# ---- 水平参考线 ----
ax.axhline(REF_Y, color=C_REF, lw=1.5, linestyle='--', zorder=2)

# ---- 两条垂直虚线 ----
ax.axvline(STEP_DYN, color=C_DYN, lw=1.5, linestyle='--', alpha=0.85, zorder=2)
ax.axvline(STEP_NODYN, color=C_NODYN, lw=1.5, linestyle='--', alpha=0.85, zorder=2)

# ---- Axes 样式 ----
ax.set_xlim(-100, 9200)
ax.set_ylim(-0.01, 0.47)
ax.set_xticks([0, 2000, 4000, 6000, 8000])
ax.set_xticklabels(['0', '2000', '4000', '6000', '8000'])
ax.set_yticks([0.0, 0.1, 0.2, 0.3, 0.4])
ax.tick_params(direction='out', length=4, width=0.8)
ax.set_xlabel('Step')
ax.set_ylabel('AIME avg@32')

# 四边框（该图型签名，覆盖随机版式族的 L 形默认）
for sp in ax.spines.values():
    sp.set_visible(True)
    sp.set_linewidth(1.0)

ax.grid(False)

# ---- 图例 ----
ax.legend(
    loc='lower right',
    frameon=True,
    facecolor='white',
    edgecolor='#AAAAAA',
    framealpha=1.0,
    borderpad=0.5,
    labelspacing=0.3,
    handlelength=2.0,
    handletextpad=0.5,
)

set_paper_placement(fig)
save_fig(fig, OUTPUT)
