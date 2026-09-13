#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper-figure-palette v6 工具箱 —— 色板常量 / LCH 数学 / 体检 / 色卡预览。

用法（任选一个子命令）：
    python palette_kit.py hex               # 打印全部色值（供复制）
    python palette_kit.py check             # 体检：对比度/去灰比/灰度单调/色盲最近对
    python palette_kit.py preview [out.png] # 生成色卡总览图（默认 assets/palette_preview.png）

本脚本独立实现色彩数学（与生成侧脚本互不 import）——共用实现只能验自洽，
验不了正确。仅依赖 numpy 与 matplotlib。
"""
import os
import sys

import numpy as np

# ================================================================ 色板常量（真源：assets/palette_v6.json）
PAL_USER = ["#FEB8B5", "#FEBDAA", "#FDA574", "#FED3A1", "#FEE6A9",
            "#9FE698", "#2BC3F1", "#6FCDFD"]

# 暖族（温度/热/主体 A）
T4 = "#FEE6A9"        # 浅黄   L* 92.0（族内最浅）
T3 = "#FED3A1"        # 浅橙   L* 87.0
T2 = "#FEBDAA"        # 蜜桃   L* 82.0
TMAIN = "#FEB8B5"     # 族锚   L* 81.0
TACC = "#FDA574"      # 高亮   L* 75.5（C* 全 8 色最高，全图唯一荧光）
PAL_WARM = [T4, T3, T2, TMAIN, TACC]

# 冷族（水分/冷/主体 B）
M4 = "#9FE698"        # 浅绿   L* 85.0（族内最浅）
M2 = "#6FCDFD"        # 亮蓝   L* 78.5（= 族锚 MMAIN）
M1 = "#2BC3F1"        # 天蓝   L* 73.5（族内最深）
MMAIN = M2
PAL_COOL = [M4, M2, M1]

# 中性 4 色 + 色带深端 2 色
NEU = "#B6B6B2"       # 参考线 / 次要数据
INK = "#2B2B2E"       # 文字（≈15:1）
CRIT = "#57575A"      # 判据线 / 阈值线
GRID = "#EBE8E3"      # 网格（暖调极浅中性）
SOFT = "#FBF7F1"      # 交替行底色（暖调米白）
RAMP_TEMP_DEEP = "#A3490D"
RAMP_MOIST_DEEP = "#19667F"

# 墨色映射：基色 → 同色相深彩（线条/描边/图例文字；对白底 4.6–5.7:1）
INK_MAP = {
    "#FEB8B5": "#C74C53",
    "#FEBDAA": "#BE4E30",
    "#FDA574": "#A35B31",
    "#FED3A1": "#896330",
    "#FEE6A9": "#76652F",
    "#9FE698": "#438040",
    "#2BC3F1": "#3B7287",
    "#6FCDFD": "#307697",
}

INK_RATIO = 0.65     # 墨色彩度 = 该 (L*,H°) 色域上限的 0.65 倍
LINESTYLES = ["-", "--", "-.", ":", (0, (4, 1, 1, 1))]


# ================================================================ LCH 数学（独立实现）
def _srgb2lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin2srgb(c):
    c = min(1.0, max(0.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _rgb2lab(rgb):
    r, g, b = (_srgb2lin(v) for v in rgb)
    X = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    Y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    Z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b

    def _f(t):
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29
    fx, fy, fz = _f(X / 0.95047), _f(Y / 1.0), _f(Z / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _lab2rgb(lab):
    L, a, bb = lab
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - bb / 200

    def _g(t):
        return t ** 3 if t > 6 / 29 else 3 * (6 / 29) ** 2 * (t - 4 / 29)
    X, Y, Z = 0.95047 * _g(fx), 1.0 * _g(fy), 1.08883 * _g(fz)
    r = 3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z
    g = -0.9692660 * X + 1.8760108 * Y + 0.0415560 * Z
    b = 0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z
    return tuple(_lin2srgb(v) for v in (r, g, b))


def _lab2lin(lab):
    """Lab → 线性 sRGB（不夹取，供色域判定）。"""
    L, a, bb = lab
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - bb / 200

    def _g(t):
        return t ** 3 if t > 6 / 29 else 3 * (6 / 29) ** 2 * (t - 4 / 29)
    X, Y, Z = 0.95047 * _g(fx), 1.0 * _g(fy), 1.08883 * _g(fz)
    r = 3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z
    g = -0.9692660 * X + 1.8760108 * Y + 0.0415560 * Z
    b = 0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z
    return (r, g, b)


def rgb2lch(hexc):
    L, a, b = _rgb2lab(_hex2rgb(hexc))
    return float(L), float((a * a + b * b) ** 0.5), float(np.degrees(np.arctan2(b, a)) % 360.0)


def _hex2rgb(hexc):
    hexc = hexc.lstrip("#")
    return tuple(int(hexc[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _rgb2hex(rgb):
    return "#%02X%02X%02X" % tuple(int(round(255 * min(1.0, max(0.0, v)))) for v in rgb)


def lch2hex(L, C, H):
    a = C * float(np.cos(np.radians(H)))
    b = C * float(np.sin(np.radians(H)))
    return _rgb2hex(_lab2rgb((L, a, b)))


def _in_gamut(L, C, H):
    a = C * float(np.cos(np.radians(H)))
    b = C * float(np.sin(np.radians(H)))
    return all(-1e-6 <= v <= 1 + 1e-6 for v in _lab2lin((L, a, b)))


def cmax_at(L, H):
    """(L*,H°) 下 sRGB 允许的最大彩度（二分）。"""
    lo, hi = 0.0, 180.0
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        if _in_gamut(L, mid, H):
            lo = mid
        else:
            hi = mid
    return lo


def _rel_lum(hexc):
    def f(u):
        u = _srgb2lin(u)
        return u / 12.92 if u <= 0.0031308 else 1.055 * u ** (1 / 2.4) - 0.055
    r, g, b = (_srgb2lin(v) for v in _hex2rgb(hexc))
    lin = (f(r), f(g), f(b))
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_white(hexc):
    """色对白底的 WCAG 对比度。"""
    return (1.0 + 0.05) / (_rel_lum(hexc) + 0.05)


def mix_lab(c1, c2, t):
    """CIELAB 感知均匀插值（族内中段补位与色带的正确插值方式）。"""
    l1, l2 = _rgb2lab(_hex2rgb(c1)), _rgb2lab(_hex2rgb(c2))
    return _rgb2hex(_lab2rgb(tuple(x + (y - x) * t for x, y in zip(l1, l2))))


def lighten(hexc, f=0.6):
    r, g, b = _hex2rgb(hexc)
    return _rgb2hex((r + (1 - r) * f, g + (1 - g) * f, b + (1 - b) * f))


def deepen(hexc, f=0.34):
    """v6 墨色机制：H° 不动、压 L*、彩度取色域上限 INK_RATIO 倍（禁用 darken）。"""
    key = hexc.upper() if hexc.startswith("#") else hexc
    L0, C0, H0 = rgb2lch(hexc)
    ink = INK_MAP.get(key.upper())
    if ink is not None:
        if f <= 0.36:
            return ink
        Lb = rgb2lch(ink)[0]
        L = max(20.0, Lb - (f - 0.36) * 90.0)
        return lch2hex(L, INK_RATIO * cmax_at(L, H0), H0)
    L = max(20.0, L0 - (f / 0.34) * 22.0)
    return lch2hex(L, min(C0, INK_RATIO * cmax_at(L, H0)), H0)


def ramp_lab(stops, n=256):
    """停靠色按 LAB 均匀插值成 n 级列表（供 LinearSegmentedColormap）。"""
    segs = len(stops) - 1
    out = []
    for i in range(n):
        x = i / (n - 1) * segs
        k = min(int(x), segs - 1)
        out.append(mix_lab(stops[k], stops[k + 1], x - k))
    return out


def _cmap(stops):
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("pfp", ramp_lab(stops))


def cmap_temp():
    return _cmap(["#FFFFFF", lighten(T4, .58), T4, T3, T2, TMAIN, TACC, RAMP_TEMP_DEEP])


def cmap_moist():
    return _cmap(["#FFFFFF", lighten(M4, .58), M4, mix_lab(M4, M2, 0.5), M2, M1, RAMP_MOIST_DEEP])


def cmap_main():
    return _cmap(["#FFFFFF", lighten(T4, .48), T3, TMAIN, TACC, RAMP_TEMP_DEEP, deepen(TACC, .52)])


# matplotlib 侧直接可用的 Colormap 单例（import 本模块即得）
try:
    from matplotlib.colors import LinearSegmentedColormap as _LCM
    CMAP_TEMP = _LCM.from_list("pfp_temp", ramp_lab(
        ["#FFFFFF", lighten(T4, .58), T4, T3, T2, TMAIN, TACC, RAMP_TEMP_DEEP]))
    CMAP_MOIST = _LCM.from_list("pfp_moist", ramp_lab(
        ["#FFFFFF", lighten(M4, .58), M4, mix_lab(M4, M2, 0.5), M2, M1, RAMP_MOIST_DEEP]))
    CMAP_MAIN = _LCM.from_list("pfp_main", ramp_lab(
        ["#FFFFFF", lighten(T4, .48), T3, TMAIN, TACC, RAMP_TEMP_DEEP, deepen(TACC, .52)]))
except Exception:                                            # pragma: no cover
    CMAP_TEMP = CMAP_MOIST = CMAP_MAIN = None                # 无 matplotlib 时仅作常量库


# ================================================================ 体检
def _gray(hexc):
    """色转灰度（Rec.709 亮度 → L* 口径近似用 Y）。"""
    y = _rel_lum(hexc)
    return 116 * (y ** (1 / 3)) - 16 if y > (6 / 29) ** 3 else y / (3 * (6 / 29) ** 2) * 116


def _cvd_sim(hexc, kind):
    """粗粒度色盲模拟（Machado 2009 线性近似）。"""
    r, g, b = _hex2rgb(hexc)
    M = {
        "protanopia": ((0.152286, 1.052583, -0.204868),
                       (0.114503, 0.786281, 0.099216),
                       (-0.003882, -0.048116, 1.051998)),
        "deuteranopia": ((0.367322, 0.860646, -0.227968),
                         (0.280085, 0.672501, 0.047413),
                         (-0.011820, 0.042940, 0.968881)),
        "tritanopia": ((1.255528, -0.076749, -0.178779),
                       (-0.078411, 0.930809, 0.147602),
                       (0.004733, 0.691367, 0.303900)),
    }[kind]
    out = [sum(M[i][j] * v for j, v in enumerate((r, g, b))) for i in range(3)]
    return tuple(min(1.0, max(0.0, v)) for v in out)


def _lab_dist(h1, h2):
    l1, l2 = _rgb2lab(_hex2rgb(h1)), _rgb2lab(_hex2rgb(h2))
    return float(np.linalg.norm(np.array(l1) - np.array(l2)))


def check():
    """跑全部体检项；返回是否全过（布尔），过程打印到 stdout。"""
    ok = True

    print("== 1) 去灰比 ratio = C*/Cmax(L*,H°)（暖族目标 ≥0.94，浅端角色允许放宽）==")
    for name, h in zip(["TMAIN", "T2", "TACC", "T3", "T4", "M4", "M1", "MMAIN"], PAL_USER):
        L, C, H = rgb2lch(h)
        r = C / cmax_at(L, H)
        flag = "PASS" if r >= 0.94 or name in ("M4",) else "FAIL"
        ok &= (flag == "PASS") or name == "M4"
        print("  %-6s %s  L*=%5.1f C*=%5.1f H=%6.1f  ratio=%.2f  %s" % (name, h, L, C, H, r, flag))

    print("== 2) 基色/墨色对白底对比度（基色仅填充；墨色需 ≥4.5，文字 INK ≥12）==")
    for base, ink in INK_MAP.items():
        cb, ci = contrast_white(base), contrast_white(ink)
        flag = "PASS" if ci >= 4.5 else "FAIL"
        ok &= (flag == "PASS")
        print("  %s→%s  基色 %.2f:1（填充用）  墨色 %.2f:1  %s" % (base, ink, cb, ci, flag))
    ci = contrast_white(INK)
    print("  INK 文字 %.2f:1  %s" % (ci, "PASS" if ci >= 12 else "FAIL"))
    ok &= ci >= 12

    print("== 3) 族内灰度单调（累积回升 ≤0.5 L*；阈值口径见 color-system §3.3）==")
    for fam_name, fam in (("暖族", PAL_WARM), ("冷族", [M4, mix_lab(M4, M2, .5), M2, M1])):
        lums = [_gray(h) for h in fam]
        run_min, back = lums[0], 0.0
        for v in lums[1:]:
            run_min = min(run_min, v)
            back = max(back, v - run_min)
        flag = "PASS" if back <= 0.5 else "FAIL"
        ok &= (flag == "PASS")
        print("  %s 灰度序 %s  最大回升 %.2f  %s" % (fam_name, ["%.1f" % v for v in lums], back, flag))

    print("== 4) 语义对立对色距（LAB；≥55 为佳）==")
    for a, b, tag in ((TACC, M1, "高亮↔冷深"), (TMAIN, MMAIN, "主锚↔主锚")):
        d = _lab_dist(a, b)
        flag = "PASS" if d >= 55 else "FAIL"
        ok &= (flag == "PASS")
        print("  %s(%s)↔%s(%s)  ΔE=%.1f  %s" % (tag.split("↔")[0], a, tag.split("↔")[1], b, d, flag))

    print("== 5) 色盲最近色对（LAB 距离，≥25 视为可分；叠加线型冗余后更稳）==")
    for kind in ("protanopia", "deuteranopia", "tritanopia"):
        sims = [_rgb2hex(_cvd_sim(h, kind)) for h in PAL_USER]
        best, bd = None, 1e9
        for i in range(len(sims)):
            for j in range(i + 1, len(sims)):
                d = _lab_dist(sims[i], sims[j])
                if d < bd:
                    bd, best = d, (PAL_USER[i], PAL_USER[j])
        flag = "PASS" if bd >= 25 else "WARN"
        print("  %-12s 最近对 %s/%s  ΔE=%.1f  %s" % (kind, best[0], best[1], bd, flag))
    return ok


# ================================================================ 色卡预览
def preview(out_png=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    plt.rcParams.update({
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
        "axes.unicode_minus": False,
    })

    if out_png is None:
        out_png = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "assets", "palette_preview.png")

    fig, axes = plt.subplots(3, 1, figsize=(8.6, 8.0), dpi=150,
                             gridspec_kw={"height_ratios": [3.6, 1.05, 1.05]})
    ax = axes[0]
    ax.set_xlim(0, 10.4), ax.set_ylim(0, 5.2), ax.axis("off")

    def swatch(x, y, hexc, name, note, w=1.0, h=1.0):
        ax.add_patch(Rectangle((x, y), w, h, facecolor=hexc,
                               edgecolor=INK_MAP.get(hexc.upper(), NEU), lw=1.1))
        ax.text(x + w / 2, y + h + 0.14, name, ha="center", fontsize=9.5,
                color=INK, fontweight="bold")
        ax.text(x + w / 2, y - 0.24, hexc, ha="center", fontsize=8.2, color=INK)
        ax.text(x + w / 2, y - 0.52, note, ha="center", fontsize=7.6, color="#57575A")

    ax.text(0.02, 4.95, "暖族（温度 / 热 / 主体 A）", fontsize=10.5, color=INK, fontweight="bold")
    swatch(0.0, 3.45, T4, "T4", "L*92 最浅")
    swatch(1.0, 3.45, T3, "T3", "L*87")
    swatch(2.0, 3.45, T2, "T2", "L*82 蜜桃")
    swatch(3.0, 3.45, TMAIN, "TMAIN", "L*81 族锚")
    swatch(4.0, 3.45, TACC, "TACC", "L*75.5 唯一高亮")
    ax.text(0.02, 2.62, "冷族（水分 / 冷 / 主体 B）", fontsize=10.5, color=INK, fontweight="bold")
    ax.text(3.35, 2.62, "中性（外补）", fontsize=10.5, color=INK, fontweight="bold")
    swatch(0.0, 1.10, M4, "M4", "L*85 最浅")
    swatch(1.0, 1.10, M2, "MMAIN", "L*78.5 族锚")
    swatch(2.0, 1.10, M1, "M1", "L*73.5 与TACC互补")
    for i, (h, n) in enumerate(((GRID, "GRID"), (NEU, "NEU"), (CRIT, "CRIT"), (INK, "INK"))):
        swatch(3.35 + i * 1.0, 1.10, h, n, "", 0.9, 1.0)

    for axc, cm, title in ((axes[1], cmap_temp(), "CMAP_TEMP（温度场）"),
                           (axes[2], cmap_moist(), "CMAP_MOIST（水分场）")):
        grad = np.linspace(0, 1, 256)[None, :]
        axc.imshow(grad, aspect="auto", cmap=cm)
        axc.set_yticks([]), axc.set_xticks([])
        for s in axc.spines.values():
            s.set_visible(False)
        axc.set_title(title, fontsize=9.5, color=INK, loc="left", pad=3)

    fig.tight_layout(pad=1.1)
    fig.savefig(out_png, dpi=200, facecolor="white")
    print("preview ->", out_png)


# ================================================================ CLI
def main(argv):
    if not argv or argv[0] == "hex":
        print("暖族:", " ".join(PAL_WARM))
        print("冷族:", " ".join(PAL_COOL))
        print("中性: GRID=%s NEU=%s CRIT=%s INK=%s SOFT=%s" % (GRID, NEU, CRIT, INK, SOFT))
        print("色带深端: TEMP=%s MOIST=%s" % (RAMP_TEMP_DEEP, RAMP_MOIST_DEEP))
        print("墨色:")
        for k, v in INK_MAP.items():
            print("  %s -> %s" % (k, v))
        return 0
    if argv[0] == "check":
        ok = check()
        print("\n总体：", "ALL PASS" if ok else "存在 FAIL（不得交付）")
        return 0 if ok else 1
    if argv[0] == "preview":
        preview(argv[1] if len(argv) > 1 else None)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
