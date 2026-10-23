"""
复现 image5: SPICE 论文风格柱状图
特征：分组柱 + 斜线填充（主方法）+ 柱顶数值标注（最优加粗）+ 灰色网格
来源：SPICE: Self-play in corpus environments improves reasoning

薄壳模板：字体族/字号阶梯/线宽/配色循环/保存护栏统一由
academic-toolkit/skills/_utils/plot_utils.py 的 setup_style + save_fig 提供；
本文件只保留该图型的语法差异（分组几何、斜线编码、柱顶数值、边框与图例位置）。
"""

import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

_SKILLS_DIR = Path(__file__).resolve().parents[2]
if str(_SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILLS_DIR))

from _utils.plot_utils import save_fig, set_paper_placement, setup_style

setup_style()

OUTPUT = 'figures/fig_bar_spice.png'

# ── 颜色 & 填充 ───────────────────────────────────────────
# 左图 (ablation)
COLORS_ABL   = ['#FFB695', '#FF7F5E', '#D00000']   # 浅橙/中橙/正红（对齐原图）
HATCHES_ABL  = ['', '', '//']
LABELS_ABL   = ['SPICE (Fixed Challenger)', 'SPICE (No Corpus)', 'SPICE']

# 右图 (comparison)
COLORS_CMP   = ['#D3D3D3', '#A9A9A9', '#D00000']   # 浅灰/中灰/正红（对齐原图）
HATCHES_CMP  = ['', '', '//']
LABELS_CMP   = ['R-Zero', 'Absolute Zero', 'SPICE']

# ── 数据 ─────────────────────────────────────────────────
benchmarks = ['MATH500', "AIME'25", 'GPQA-Diamond', 'MMLU-Pro']
# 最终印刷字号不低于 8pt 后，长类名在单栏宽内放不下 → 在连字符处断行（不缩字号）
benchmarks_display = [b.replace('-', '-\n') for b in benchmarks]

data_abl = {
    'SPICE (Fixed Challenger)': [68.2,  6.7, 26.3, 51.6],
    'SPICE (No Corpus)':        [72.6, 12.3, 31.8, 53.7],
    'SPICE':                    [78.0, 19.1, 39.4, 58.1],
}
data_cmp = {
    'R-Zero':        [72.6,  5.2, 27.8, 53.7],
    'Absolute Zero': [76.2, 13.4, 35.3, 52.6],
    'SPICE':         [78.0, 19.1, 39.4, 58.1],
}

BEST_METHOD = 'SPICE'   # 柱顶数字加粗的方法


def draw_panel(
    ax,
    data_dict,
    colors,
    hatches,
    labels,
    title,
    x_positions,
    total_w,
    xlim,
    legend_anchor,
):
    n_methods = len(labels)
    x         = np.array(x_positions)
    bar_w     = total_w / n_methods

    for i, (label, color, hatch) in enumerate(zip(labels, colors, hatches)):
        vals   = data_dict[label]
        offset = (i - n_methods / 2 + 0.5) * bar_w
        bars   = ax.bar(x + offset, vals, width=bar_w,
                        color=color, hatch=hatch,
                        edgecolor='white',   # 斜线颜色随 edgecolor（本仓基线不另设 hatch.color）
                        linewidth=0.8, zorder=2, label=label)

        is_best = (label == BEST_METHOD)
        if is_best:
            # 只标主方法柱值：三柱并排在印刷字号下放不下逐柱数值，
            # 次要柱的数值读结果表，图面保留"最优加粗"的语义（save_fig 遮挡硬闸要求）
            for bar, v in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        v + 2.0, f'{v}',
                        ha='center', va='bottom',
                        fontweight='bold',
                        color='black',
                        zorder=3,
                        # 白底板：save_fig 的对比度修复以 text bbox 底色判定墨色，
                        # 深红柱顶的标签需要明确的白底才不会再被改成浅灰
                        bbox=dict(boxstyle='square,pad=0.12',
                                  facecolor='white', edgecolor='none'))

    # 轴
    ax.set_xticks(x)
    ax.set_xticklabels(benchmarks_display)
    ax.set_xlabel('Benchmark')
    ax.set_ylabel(r'Accuracy (\%)')
    ax.set_ylim(0, 85)
    ax.set_xlim(*xlim)
    ax.set_title(title, pad=5)

    # 网格（仅 y 轴浅灰虚线）
    ax.yaxis.grid(True, color='#EBEBEB', linewidth=0.7, linestyle='--', zorder=0)
    ax.set_axisbelow(True)

    # 原图为开口式坐标轴：只保留左/下 spine
    for side, spine in ax.spines.items():
        if side in ('top', 'right'):
            spine.set_visible(False)
        else:
            spine.set_linewidth(0.9)
            spine.set_color('#333333')
            spine.set_zorder(4)

    ax.tick_params(length=0)

    # 图例
    handles = [mpatches.Patch(facecolor=c, hatch=h,
                              edgecolor='white', linewidth=0.8,
                              label=l)
               for l, c, h in zip(labels, colors, hatches)]
    leg = ax.legend(handles=handles, loc='upper right',
                    bbox_to_anchor=legend_anchor,
                    framealpha=1.0, facecolor='white',
                    edgecolor='#C8C8C8', fancybox=False,
                    borderpad=0.28, labelspacing=0.26,
                    handlelength=1.7, handletextpad=0.45,
                    borderaxespad=0.28)
    # 只将主方法（BEST_METHOD）的图例文字加粗
    for text in leg.get_texts():
        if text.get_text() == BEST_METHOD:
            text.set_fontweight('bold')


# ── 画布 ─────────────────────────────────────────────────
# 画布宽 8in：按 academic.mplstyle 的“画时字号 = 印刷目标 × figsize宽 / 嵌入宽”
# 反推（12pt × 8in / 5.5in ≈ 8.25pt），避免 save_fig 为 12.8in 画布把字号整体放大后
# 图例压住左上柱顶数值。
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.0, 2.72))

draw_panel(
    ax1,
    data_abl,
    COLORS_ABL,
    HATCHES_ABL,
    LABELS_ABL,
    '(a) SPICE Ablations',
    x_positions=[0.00, 1.00, 2.00, 3.00],
    total_w=0.78,
    xlim=(-0.56, 3.56),
    legend_anchor=(0.992, 0.986),
)
draw_panel(
    ax2,
    data_cmp,
    COLORS_CMP,
    HATCHES_CMP,
    LABELS_CMP,
    '(b) SPICE vs Baselines',
    x_positions=[0.00, 1.00, 2.00, 3.00],
    total_w=0.78,
    xlim=(-0.56, 3.56),
    legend_anchor=(0.992, 0.986),
)

set_paper_placement(fig)
save_fig(fig, OUTPUT)
