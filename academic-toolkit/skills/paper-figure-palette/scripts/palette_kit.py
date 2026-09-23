#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper-figure-palette v6 工具箱 —— 色板常量 / LCH 数学 / 体检 / 色卡预览。

用法（任选一个子命令）：
    python palette_kit.py hex                    # 打印全部色值（供复制）
    python palette_kit.py check                  # 体检：对比度/去灰比/灰度单调/色盲最近对
    python palette_kit.py registry-verify        # 多场景注册表体检（assets/palette_registry.json）
    python palette_kit.py preview [out.png]      # 生成色卡总览图（默认 assets/palette_preview.png）

本脚本独立实现色彩数学（与生成侧脚本互不 import）——共用实现只能验自洽，
验不了正确。仅依赖 numpy 与 matplotlib。
"""
import json
import os
import re
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


# ================================================================ 多场景注册表体检
REGISTRY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "assets", "palette_registry.json")
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# 兜底阈值：注册表 meta.checks 缺失时使用（与真源同值）
_DEFAULT_CHECKS = {"cvd_min_deltaE": 25.0, "cvd_fail_deltaE": 12.0,
                   "sequential_max_backstep": 0.5, "ink_contrast_min": 4.5,
                   "text_contrast_min": 12.0}


def _backstep(colors):
    """累积回升口径的明度单调性（与 assets/palette_v6.json checks 段同口径）。"""
    lums = [_gray(h) for h in colors]
    run, back = lums[0], 0.0
    for v in lums[1:]:
        run = min(run, v)
        back = max(back, v - run)
    return back


def _monotonic_backstep(colors):
    """顺序色带：任一方向有向单调即通过，取两向较小值。"""
    return min(_backstep(colors), _backstep(list(reversed(colors))))


def _cvd_min_deltaE(colors):
    """三型色盲模拟下的最近色对 LAB 距离（越小越难分）。"""
    worst = None
    for kind in ("protanopia", "deuteranopia", "tritanopia"):
        sims = [_rgb2hex(_cvd_sim(h, kind)) for h in colors]
        for i in range(len(sims)):
            for j in range(i + 1, len(sims)):
                d = _lab_dist(sims[i], sims[j])
                if worst is None or d < worst[0]:
                    worst = (d, kind, colors[i], colors[j])
    return worst


def _norm_token(text):
    """禁用清单匹配用归一化：小写 + 去分隔符。"""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _tokens(text):
    """按 - _ / 空格 切词（用于避免 "budget" 命中 "jet" 这类子串误报）。"""
    return {t for t in re.split(r"[-_/\s]+", str(text).lower()) if t}


def _hits_forbidden(name, forbidden_set):
    """名称是否命中禁用清单：归一化全等，或任一词元等于禁用键。

    刻意不做子串包含判断——否则 "budget" 会因含 "jet" 被误杀。
    """
    norm = _norm_token(name)
    if norm in forbidden_set:
        return True
    return bool(_tokens(name) & forbidden_set)


def registry_verify(path=None):
    """多场景色板注册表体检；返回是否全过（FAIL 即 False）。

    检查项（前四类为硬 FAIL，第五类为 WARN）：
      1. 结构：schema_version / scenarios / palettes / forbidden / rules 齐备；
      2. 色值：全部为 6 位 hex，且同一色板内不得重复；
      3. 类型契约：sequential 必须单调（任一方向）；diverging 必须中点最明/最暗且两臂单调；
      4. CVD 契约：cvd_mode=direct 的色板最近色对 ΔE 不得低于 cvd_fail_deltaE；
         cvd_mode=secondary_encoding 的色板必须声明 requires_secondary_encoding=true；
      5. 场景交叉一致：场景引用的色板必须存在、不得引用禁用色板；
         cvd_policy=direct_required 的场景不得映射 secondary_encoding 色板。
    另输出 WARN 级提示（ΔE 介于 fail 与 min 之间、grayscale_required 场景用了填充型色板）。
    """
    import json
    p = path or REGISTRY_PATH
    if not os.path.isfile(p):
        print("✗ 注册表缺失:", p)
        return False
    reg = json.load(open(p, encoding="utf-8"))
    fails, warns = [], []
    checks = dict(_DEFAULT_CHECKS)
    checks.update((reg.get("meta") or {}).get("checks") or {})
    min_de = float(checks["cvd_min_deltaE"])
    fail_de = float(checks["cvd_fail_deltaE"])
    max_back = float(checks["sequential_max_backstep"])

    print("== 0) 结构 ==")
    if reg.get("schema_version") != 1:
        fails.append("schema_version 必须为 1")
    for key in ("scenarios", "palettes", "forbidden", "rules"):
        if not reg.get(key):
            fails.append(f"缺少非空段 {key}")
    palettes = reg.get("palettes") or {}
    scenarios = reg.get("scenarios") or {}
    print("  场景 %d / 色板 %d / 禁用 %d / 规则 %d"
          % (len(scenarios), len(palettes), len(reg.get("forbidden") or []), len(reg.get("rules") or [])))

    print("== 1) 色值合法性与去重 ==")
    invalid_palettes = set()
    for name, pal in palettes.items():
        colors = pal.get("colors") or pal.get("stops") or []
        bad = [c for c in colors if not _HEX_RE.match(str(c))]
        dup = sorted({c for c in colors if colors.count(c) > 1})
        if bad:
            fails.append(f"{name}: 非法 hex {bad}")
            invalid_palettes.add(name)
        if dup:
            fails.append(f"{name}: 色值重复 {dup}")
        print("  %-24s %2d 色  %s" % (name, len(colors), "OK" if not bad and not dup else "FAIL"))

    # 色值非法的色板跳过后续色彩数学（避免在坏输入上算违背直觉的结果或直接抛栈）
    def _usable(key):
        return key not in invalid_palettes and (palettes[key].get("colors") or palettes[key].get("stops"))

    print("== 2) 顺序/发散色带单调性 ==")
    for name, pal in palettes.items():
        kind = pal.get("kind")
        colors = pal.get("stops") or []
        if not _usable(name):
            print("  %-24s 跳过（色值非法）" % name)
            continue
        if kind == "sequential":
            b = _monotonic_backstep(colors)
            flag = "PASS" if b <= max_back else "FAIL"
            if flag == "FAIL":
                fails.append(f"{name}: 顺序色带明度回升 {b:.2f} > {max_back}（非单调，灰度下会出假带）")
            print("  %-24s backstep=%.2f  %s" % (name, b, flag))
        elif kind == "diverging":
            mid = len(colors) // 2
            left, right = colors[:mid + 1], colors[mid:]
            bl = _monotonic_backstep(left)
            br = _monotonic_backstep(right)
            lums = [_gray(c) for c in colors]
            extreme = lums[mid] >= max(lums) - 1e-6 or lums[mid] <= min(lums) + 1e-6
            flag = "PASS" if (bl <= max_back and br <= max_back and extreme) else "FAIL"
            if flag == "FAIL":
                fails.append(f"{name}: 发散色带中点非明度极值或两臂不单调"
                             f"（left={bl:.2f} right={br:.2f} center_extreme={extreme}）")
            print("  %-24s left=%.2f right=%.2f center_extreme=%s  %s"
                  % (name, bl, br, extreme, flag))

    print("== 3) CVD 契约（阈值 fail<%.0f / warn<%.0f）==" % (fail_de, min_de))
    for name, pal in palettes.items():
        if pal.get("kind") != "categorical":
            continue
        colors = pal.get("colors") or []
        mode = pal.get("cvd_mode")
        if not _usable(name):
            print("  %-24s 跳过（色值非法）" % name)
            continue
        d = _cvd_min_deltaE(colors)
        shown = "%.1f" % d[0]
        if mode == "direct":
            if d[0] < fail_de:
                fails.append(f"{name}: 声明可直用（direct）但最近色对 ΔE={d[0]:.1f} < {fail_de}"
                             f"（{d[1]}: {d[2]}/{d[3]}）——应降级为 secondary_encoding 或换色板")
                flag = "FAIL"
            elif d[0] < min_de:
                warns.append(f"{name}: 最近色对 ΔE={d[0]:.1f} < {min_de}（{d[1]}: {d[2]}/{d[3]}），"
                             "建议叠加线型/标记作第二编码")
                flag = "WARN"
            else:
                flag = "PASS"
        elif mode == "secondary_encoding":
            if not pal.get("requires_secondary_encoding"):
                fails.append(f"{name}: cvd_mode=secondary_encoding 必须声明 requires_secondary_encoding=true")
                flag = "FAIL"
            else:
                flag = "PASS（填充型：靠墨色描边+线型+直接标签区分）"
        else:
            fails.append(f"{name}: cvd_mode 缺失或非法（direct / secondary_encoding）")
            flag = "FAIL"
        print("  %-24s minΔE=%5s（%s / %s·%s）  %s"
              % (name, shown, mode, d[1][:5], "%s-%s" % (d[2], d[3]), flag))

    print("== 4) 场景交叉一致 ==")
    forbidden_set = set()
    for item in reg.get("forbidden") or []:
        forbidden_set.add(_norm_token(item.get("id", "")))
        forbidden_set.update(_norm_token(a) for a in (item.get("aliases") or []))
    forbidden_set.discard("")
    for sc in scenarios:
        if not isinstance(sc, dict):
            continue
        sid = sc.get("id", "<无 id>")
        refs = [v for k, v in sc.items() if k in ("categorical", "categorical_alt", "sequential",
                                                  "sequential_alt", "diverging") and v]
        missing = [r for r in refs if r not in palettes]
        if missing:
            fails.append(f"场景 {sid}: 引用了不存在的色板 {missing}")
        hit = [r for r in refs if _hits_forbidden(r, forbidden_set)]
        if hit:
            fails.append(f"场景 {sid}: 引用了禁用色板 {hit}")
        cat = palettes.get(sc.get("categorical") or "", {})
        if sc.get("cvd_policy") == "direct_required" and cat.get("cvd_mode") != "direct":
            fails.append(f"场景 {sid}: cvd_policy=direct_required 却映射 {cat.get('cvd_mode')} 色板"
                         f"（{sc.get('categorical')}）——合规声明与实际能力不符")
        if sc.get("grayscale_required") and cat.get("cvd_mode") == "secondary_encoding":
            warns.append(f"场景 {sid}: 要求灰度可分但用的是填充型色板（{sc.get('categorical')}）——"
                         "类别必须叠加线型/标记，否则黑白打印后不可分")
        print("  %-20s 引用 %d 个色板  %s" % (sid, len(refs), "OK" if not missing and not hit else "FAIL"))

    # 禁用色板不得作为任何色板键存在（换了名字也一样禁）
    for name in palettes:
        if _hits_forbidden(name, forbidden_set):
            fails.append(f"色板 {name} 命中禁用清单")

    if warns:
        print("\n== WARN（不阻断，但需在交付说明中留痕）==")
        for w in warns:
            print("  ⚠️ " + w)
    if fails:
        print("\n== FAIL ==")
        for f in fails:
            print("  ✗ " + f)
    print("\n总体：", "ALL PASS" if not fails else "存在 FAIL（不得作为交付配色依据）")
    return not fails


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
    if argv[0] == "registry-verify":
        # 布尔不能直接作退出码（sys.exit(True) == 1），显式映射为 0/1
        return 0 if registry_verify() else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
