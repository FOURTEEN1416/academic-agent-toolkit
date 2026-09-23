# -*- coding: utf-8 -*-
"""配色 v6 目检图板：review/diag/cvd_check_v6.png

5 行（正常 / 红盲 / 绿盲 / 蓝黄盲 / 灰度）× 4 列：
  列0 8 基色 + 墨色派生（deepen，不再 darken）
  列1/2 两条顺序色带 + 模拟后 L* 曲线（应单调下降）
  列3 分类序列的线型 / 标记冗余（色盲下的兜底通道）
配套文本：_cvd_ramp_v6.txt

与 v5 版的差别：色板与深色派生算法全部换成 v6（deepen + 设计色带深端）。
"""
import io
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, rgb_to_hsv
from matplotlib.patches import Rectangle

import palette_cvd_check_v6 as C

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "references", "cvd_check_v6.png")
LOG = os.path.join(ROOT, "_cvd_ramp_v6.txt")

W = C.hex2rgb
dp, lt = C.deepen, C.lighten

# v6 采用的实际停靠点（与 code/gen_figures_v3.py 完全一致）
RAMP = [
    ("水分族 CMAP_MOIST", ["#FFFFFF", lt(C.M4, .58), C.M4, C.M3, C.M2, C.M1,
                          W(C.RAMP_MOIST_DEEP)]),
    ("温度族 CMAP_TEMP", ["#FFFFFF", lt(C.T4, .58), C.T4, C.T3, C.T2, C.TMAIN,
                         C.TACC, W(C.RAMP_TEMP_DEEP)]),
]


def profile(stops, n=257):
    cm = LinearSegmentedColormap.from_list("t", stops)
    rgb = [cm(i / (n - 1))[:3] for i in range(n)]
    L = [C.lightness(c) for c in rgb]
    hsv = [rgb_to_hsv(c) for c in rgb]
    return rgb, L, [h * 360.0 for h, s, v in hsv], [s for h, s, v in hsv]


def worst_backstep(L):
    """色带为「亮→暗」下降序列：回升量 = 沿途相对此前最低点的最大抬升。"""
    L = np.array(L, dtype=float)
    return float(max(0.0, (L - np.minimum.accumulate(L)).max()))


def hue_wobble(H, S):
    """只在有颜色样本（S≥0.18）上统计色相跳变，>5° 记为一次。"""
    keep = [i for i in range(len(H)) if S[i] >= 0.18]
    sig = []
    for a, b in zip(keep, keep[1:]):
        x = H[b] - H[a]
        while x > 180:
            x -= 360
        while x < -180:
            x += 360
        if abs(x) > 5:
            sig.append(abs(x))
    return (float(max(sig)) if sig else 0.0, len(sig))


# ---------------------------------------------------------------- part A
txt = ["# 配色 v6 色带灰度/色相单调性", "",
       "色带方向为「亮 → 暗」，故 L* 应单调**下降**；回升量 >0 即非单调（灰度下会出假亮带）。",
       "色相跳变只在有颜色样本（S≥0.18）上统计，>5° 记为一次跳变。", "",
       "| 色带 | 最大 ΔL* 回升 | 最大色相跳变 | 跳变次数 | 停靠点 L* |", "|---|---|---|---|---|"]
for nm, st in RAMP:
    _, L, H, S = profile(st)
    bs = worst_backstep(L)
    hw, hn = hue_wobble(H, S)
    stopL = " ".join("%.0f" % C.lightness(C._asrgb(s)) for s in st)
    txt.append("| %s | %.2f | %.1f° | %d | %s |" % (nm, bs, hw, hn, stopL))
    print("%-24s backstep=%.2f  hue=%.1f  n=%d" % (nm, bs, hw, hn))
io.open(LOG, "w", encoding="utf-8").write("\n".join(txt))

# ---------------------------------------------------------------- part B
CONDS = [("正常视觉", None), ("红色盲 protanopia", "红色盲 protan"),
         ("绿色盲 deuteranopia", "绿色盲 deutan"), ("蓝黄色盲 tritanopia", "蓝黄色盲 tritan"),
         ("灰度打印", "gray")]
PAL = [W(c) for c in C.PAL_USER]
INK8 = [dp(c, .34) for c in C.PAL_USER]     # v6：设计墨色（f≤0.36 直接返回墨色）
# 物性三序列 / 灵敏度双序列的实际墨色
SER3 = [(dp(C.TACC, .34), "-"), (dp(C.M2, .30), "--"), (dp(C.M4, .46), "-.")]
SER2 = [(dp(C.TMAIN, .30), "o", 7.0), (dp(C.M2, .30), "s", 5.4)]

TXT, MUT = "#2B2B2E", "#6E6E6E"
plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "SimHei"],
                     "axes.unicode_minus": False})

fig = plt.figure(figsize=(15.6, 9.6), dpi=130)
fig.suptitle("用户 8 色板 v6 · 色盲 / 灰度自检（Machado 2009 severity 1.0）",
             fontsize=15, color=TXT, y=0.978)
gs = fig.add_gridspec(len(CONDS) + 1, 4, width_ratios=[2.35, 1.5, 1.5, 2.15],
                      left=0.022, right=0.988, top=0.905, bottom=0.045,
                      hspace=0.50, wspace=0.10)

for c, h in enumerate(["8 基色 ／ 墨色（填充 vs 线条）", "水分族色带 + 亮度曲线",
                       "温度族色带 + 亮度曲线", "分类序列：线型 / 标记冗余"]):
    a = fig.add_subplot(gs[0, c]); a.axis("off")
    a.text(0.0, 0.10, h, fontsize=11.5, color=TXT, fontweight="bold", transform=a.transAxes)

for r, (label, kind) in enumerate(CONDS, start=1):
    def sim(rgb):
        return rgb if kind is None else (C.gray(rgb) if kind == "gray" else C.cvd(rgb, kind))

    # --- 列0 ---
    a = fig.add_subplot(gs[r, 0]); a.axis("off")
    n = len(PAL)
    for i, col in enumerate(PAL):
        a.add_patch(Rectangle((i / n, 0.40), 0.97 / n, 0.40, transform=a.transAxes,
                              facecolor=sim(col), edgecolor="white", lw=1.4))
        a.add_patch(Rectangle((i / n, 0.22), 0.97 / n, 0.14, transform=a.transAxes,
                              facecolor=sim(INK8[i]), edgecolor="none"))
    a.text(0.0, 1.10, label, fontsize=11.2, color=TXT, fontweight="bold",
           transform=a.transAxes, va="bottom")
    a.text(0.0, 0.12, "上：8 基色（填充/色带）　下：墨色 deepen(c)（线条/描边）",
           fontsize=8.0, color=MUT, transform=a.transAxes, va="center")

    # --- 列1/2 ---
    for col, (nm, stops) in enumerate(RAMP, start=1):
        a = fig.add_subplot(gs[r, col]); a.axis("off")
        xs = np.linspace(0, 1, 256)
        cm = LinearSegmentedColormap.from_list("t", stops)
        band = np.array([[sim(cm(v)[:3]) for v in xs]])
        a.imshow(band, aspect="auto", extent=(0, 1, 0.52, 0.88), origin="lower")
        L = np.array([C.lightness(sim(cm(v)[:3])) for v in xs])
        lo, hi = L.min(), L.max()
        Ln = 0.30 * (L - lo) / max(1e-6, hi - lo) + 0.10
        a.plot(xs, Ln, color=TXT, lw=1.2)
        bs = worst_backstep(L)
        a.text(0.0, 0.94, "%s　回升 %.2f L*" % (nm, bs), fontsize=8.4, color=MUT,
               transform=a.transAxes, va="bottom")
        a.text(0.0, 0.03, "曲线 = 模拟后 L*（应单调下降）  |  ΔL* 全距 %.1f" % (hi - lo),
               fontsize=7.6, color=MUT, transform=a.transAxes, va="bottom")
        a.set_xlim(0, 1); a.set_ylim(0, 1)

    # --- 列3 ---
    a = fig.add_subplot(gs[r, 3]); a.axis("off")
    a.set_xlim(0, 1); a.set_ylim(0, 1)
    a.text(0.0, 0.98, "物性三序列 → 线型区分", fontsize=8.4, color=MUT,
           transform=a.transAxes, va="top")
    for i, (col, ls) in enumerate(SER3):
        y = 0.80 - i * 0.13
        a.plot([0.02, 0.46], [y, y], color=sim(col), lw=2.6, ls=ls)
        a.text(0.51, y, "序列 %d" % (i + 1), fontsize=8.4, color=TXT, va="center")
    a.text(0.0, 0.44, "灵敏度双序列 → 标记区分", fontsize=8.4, color=MUT,
           transform=a.transAxes, va="top")
    for i, (col, mk, ms) in enumerate(SER2):
        y = 0.26 - i * 0.15
        a.plot([0.02, 0.46], [y, y], color=sim(col), lw=2.4)
        a.plot([0.14, 0.34], [y, y], color=sim(col), marker=mk, ms=ms, lw=0,
               markeredgecolor="white", markeredgewidth=1.1)
        a.text(0.51, y, "参数 %s20%%" % ("+" if i == 0 else "-"), fontsize=8.4,
               color=TXT, va="center")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT, facecolor="white")
print("->", OUT)
