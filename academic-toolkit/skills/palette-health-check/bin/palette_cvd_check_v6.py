# -*- coding: utf-8 -*-
"""配色 v6 复核：色盲 / 灰度自检 + 顺序色带明度单调性检查。

与 _tools/palette_cvd_check_v5.py 的差别
----------------------------------------
1. 色板换成 v6 定稿（_palette_v6.json）。
2. 深色派生由 `darken()`（RGB 等比缩放）换成 `deepen()`（LCH 固定色相 +
   彩度取色域上限的 INK_RATIO 倍），并内置与 gen_figures_v3.py 一致的 INK_MAP。
   → 本脚本**故意重新实现一遍色彩数学**（不 import gen_figures_v3），
     这样它才能作为独立复核，而不是"自己验自己"。

方法
----
- CVD 模拟：Machado et al. (2009) 严重度 1.0 的 3x3 矩阵，作用在**线性 RGB**上。
- 色差：CIE76 ΔE（Lab 欧氏距离）。
- 灰度：CIE L*（D65）与 Rec.709 相对亮度 Y。
- 色带单调性：用**累积口径** max(L - running_min(L))，而非逐样本差分
  （逐样本差分会把几 L* 的回升摊到上百个样本、稀释成 0.0x → 漏报）。

判据
----
- 分类（不同序列）色对：ΔE ≥ 10 才算"色盲下仍可区分"。
- 灰度：|ΔL*| ≥ 5 才算"灰度下仍可区分"。
- 色带：累积回升 ≤ 0.5 L* 视为单调（插值伪影容差）。

输出：_cvd_v6.txt（报告）+ _cvd_v6.json（机器可读）
"""
import io
import itertools
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_TXT = os.path.join(HERE, "..", "data", "_cvd_v6.txt")
OUT_JSON = os.path.join(HERE, "..", "data", "_cvd_v6.json")


# ---------------------------------------------------------------- 颜色工具
def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb2hex(c):
    return "#" + "".join("%02X" % max(0, min(255, round(v * 255))) for v in c)


def s2l(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def l2s(c):
    c = min(1.0, max(0.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def to_lin(rgb):
    return tuple(s2l(v) for v in rgb)


def to_srgb(lin):
    return tuple(min(1.0, max(0.0, l2s(v))) for v in lin)


def lin2xyz(c):
    r, g, b = c
    return (0.4124564 * r + 0.3575761 * g + 0.1804375 * b,
            0.2126729 * r + 0.7151522 * g + 0.0721750 * b,
            0.0193339 * r + 0.1191920 * g + 0.9503041 * b)


_WP = lin2xyz((1.0, 1.0, 1.0))


def f_lab(t):
    return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29


def rgb2lab(rgb):
    X, Y, Z = lin2xyz(to_lin(rgb))
    fx, fy, fz = f_lab(X / _WP[0]), f_lab(Y / _WP[1]), f_lab(Z / _WP[2])
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lab2lin(lab):
    """Lab → 线性 sRGB（**不夹取**，供色域判定）。"""
    L, a, b = lab
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200

    def g(t):
        return t ** 3 if t > 6 / 29 else 3 * (6 / 29) ** 2 * (t - 4 / 29)
    X, Y, Z = 0.95047 * g(fx), 1.0 * g(fy), 1.08883 * g(fz)
    return (3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z,
            -0.9692660 * X + 1.8760108 * Y + 0.0415560 * Z,
            0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z)


def lab2rgb(lab):
    return to_srgb(lab2lin(lab))


def rgb2lch(rgb):
    L, a, b = rgb2lab(rgb)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def in_gamut(L, C, H):
    a = C * math.cos(math.radians(H))
    b = C * math.sin(math.radians(H))
    return all(-1e-6 <= v <= 1 + 1e-6 for v in lab2lin((L, a, b)))


def cmax_at(L, H):
    lo, hi = 0.0, 180.0
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        if in_gamut(L, mid, H):
            lo = mid
        else:
            hi = mid
    return lo


def lch2rgb(L, C, H):
    return lab2rgb((L, C * math.cos(math.radians(H)), C * math.sin(math.radians(H))))


def deltaE(rgb1, rgb2):
    a, b = rgb2lab(rgb1), rgb2lab(rgb2)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def lightness(rgb):
    return rgb2lab(rgb)[0]


def rel_lum(rgb):
    r, g, b = to_lin(rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


MACHADO = {
    "红色盲 protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216),
                  (-0.003882, -0.048116, 1.051998)),
    "绿色盲 deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413),
                  (-0.011820, 0.042940, 0.968881)),
    "蓝黄色盲 tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602),
                    (0.004733, 0.691367, 0.303900)),
}


def cvd(rgb, kind):
    m = MACHADO[kind]
    lin = to_lin(rgb)
    return to_srgb(tuple(sum(m[i][j] * lin[j] for j in range(3)) for i in range(3)))


def gray(rgb):
    v = l2s(rel_lum(rgb))
    return (v, v, v)


# ---------------------------------------------------------------- v6 色板
PAL_USER = ["#FEB8B5", "#FEBDAA", "#FDA574", "#FED3A1", "#FEE6A9",
            "#9FE698", "#2BC3F1", "#6FCDFD"]
FAM = ["温度主色 TMAIN", "温度蜜桃 T2", "深橙高亮 TACC", "温度浅橙 T3", "温度浅黄 T4",
       "水分浅绿 M4", "水分天蓝 M1", "水分主色 MMAIN"]

WARM = ["#FEE6A9", "#FED3A1", "#FEBDAA", "#FEB8B5", "#FDA574"]
COOL = ["#9FE698", "#6FCDFD", "#2BC3F1"]

INK_RATIO = 0.65
INK_MAP = {
    "#FEB8B5": "#C74C53", "#FEBDAA": "#BE4E30", "#FDA574": "#A35B31",
    "#FED3A1": "#896330", "#FEE6A9": "#76652F", "#9FE698": "#438040",
    "#2BC3F1": "#3B7287", "#6FCDFD": "#307697",
}


def _asrgb(c):
    return hex2rgb(c) if isinstance(c, str) else tuple(c)


def _norm_hex(c):
    return rgb2hex(_asrgb(c))


def deepen(hexc, f=0.34):
    """与 code/gen_figures_v3.py 的 deepen() 同法（此处独立重写）。"""
    key = _norm_hex(hexc)
    L0, C0, H0 = rgb2lch(_asrgb(hexc))
    ink = INK_MAP.get(key)
    if ink is not None:
        if f <= 0.36:
            return hex2rgb(ink)
        Lb = rgb2lch(hex2rgb(ink))[0]
        L = max(20.0, Lb - (f - 0.36) * 90.0)
        return lch2rgb(L, INK_RATIO * cmax_at(L, H0), H0)
    L = max(20.0, L0 - (f / 0.34) * 22.0)
    return lch2rgb(L, min(C0, INK_RATIO * cmax_at(L, H0)), H0)


def darken(h, f):
    """v5 旧法，仅用于「v5 → v6 对照」段落。"""
    return tuple(v * (1 - f) for v in _asrgb(h))


def lighten(h, f):
    r, g, b = _asrgb(h)
    return tuple(v + (1 - v) * f for v in (r, g, b))


def mix_lab(c1, c2, t):
    l1, l2 = rgb2lab(_asrgb(c1)), rgb2lab(_asrgb(c2))
    return lab2rgb(tuple(x + (y - x) * t for x, y in zip(l1, l2)))


def ramp_lab(stops, n=256):
    stops = [_asrgb(s) for s in stops]
    segs = len(stops) - 1
    out = []
    for i in range(n):
        x = i / (n - 1) * segs
        k = min(int(x), segs - 1)
        out.append(mix_lab(stops[k], stops[k + 1], x - k))
    return out


T4, T3, T2, TMAIN, TACC = (hex2rgb(c) for c in WARM)
M4, M2, M1 = (hex2rgb(c) for c in COOL)
M3 = mix_lab(M4, M2, 0.5)

FAMT7 = ramp_lab([lighten(T4, .45), T4, T3, T2, TMAIN, TACC, deepen(TACC, .32)], 7)
FAMM7 = ramp_lab([lighten(M4, .55), M4, M3, M2, M1, deepen(M1, .25), deepen(M1, .48)], 7)

RAMP_TEMP_DEEP = "#A3490D"
RAMP_MOIST_DEEP = "#19667F"
CMAP_TEMP = ramp_lab([hex2rgb("#FFFFFF"), lighten(T4, .58), T4, T3, T2, TMAIN, TACC,
                      hex2rgb(RAMP_TEMP_DEEP)], 128)
CMAP_MOIST = ramp_lab([hex2rgb("#FFFFFF"), lighten(M4, .58), M4, M3, M2, M1,
                       hex2rgb(RAMP_MOIST_DEEP)], 128)
# v5 对照色带（同样起止，但深端用 darken）
CMAP_TEMP_V5 = ramp_lab([hex2rgb("#FFFFFF"), lighten(T4, .58), T4, T3, T2, TMAIN, TACC,
                         darken(TACC, .34)], 128)
CMAP_MOIST_V5 = ramp_lab([hex2rgb("#FFFFFF"), lighten(M4, .58), M4, M3, M2, M1,
                          darken(M1, .30)], 128)

SETS = [
    ("温度族 5 色（温度场）", WARM, "填充 / 色带 / 族内递进"),
    ("水分族 3 色（水分场）", COOL, "填充 / 色带 / 族内递进"),
    ("famT 7 级（温度多曲线）", FAMT7, "最多 7 条曲线同图"),
    ("famM 7 级（水分多曲线）", FAMM7, "最多 7 条曲线同图"),
    ("两主色（双序列对比）", [TMAIN, M2], "温度 vs 水分 双线/双填充"),
    ("物性三序列（属性曲线）",
     [deepen(TACC, .34), deepen(M2, .30), deepen(M4, .46)], "fig_q2_property_curves (a)"),
    ("龙卷/雷达双序列", [deepen(TMAIN, .30), deepen(M2, .30)], "sensitivity 双序列"),
    ("墨色派生 8 色（线条）", [deepen(c, .38) for c in PAL_USER], "全部线条 / 描边"),
]

NAMES7 = ["浅端", "2", "3", "4", "5", "6", "深端"]
COND = ["正常 vision", "红色盲 protan", "绿色盲 deutan", "蓝黄色盲 tritan"]


def apply(rgb, cond):
    return rgb if cond == "正常 vision" else cvd(rgb, cond)


def monotone_rise(lums):
    """累积口径回升量：max(L - running_min(L))。"""
    mn, rise = lums[0], 0.0
    for L in lums:
        mn = min(mn, L)
        rise = max(rise, L - mn)
    return rise


def analyse():
    rows = []
    for name, cols, note in SETS:
        cols = [_asrgb(c) for c in cols]
        for cond in COND:
            sim = [apply(c, cond) for c in cols]
            pairs = sorted((deltaE(sim[i], sim[j]), i, j)
                           for i, j in itertools.combinations(range(len(sim)), 2))
            dmin, i, j = pairs[0]
            n_merge = sum(1 for d, _, _ in pairs if d < 10)
            rows.append(dict(set=name, cond=cond, dmin=dmin, i=i, j=j,
                             n_merge=n_merge, n=len(cols), note=note))
        ls = [lightness(c) for c in cols]
        pairs = sorted((abs(ls[i] - ls[j]), i, j)
                       for i, j in itertools.combinations(range(len(ls)), 2))
        dmin, i, j = pairs[0]
        n_bad = sum(1 for d, _, _ in pairs if d < 5)
        rows.append(dict(set=name, cond="灰度 L*", dmin=dmin, i=i, j=j,
                         n_merge=n_bad, n=len(cols), note=note))
    return rows


def fmt_idx(name, i, j):
    if "7 级" in name:
        return NAMES7[i], NAMES7[j]
    if name.startswith("温度族"):
        return FAM[i].split()[0], FAM[j].split()[0]
    if name.startswith("水分族"):
        return FAM[5 + i].split()[0], FAM[5 + j].split()[0]
    if name.startswith("两主色"):
        return ["温度主色", "水分主色"][i], ["温度主色", "水分主色"][j]
    return "色%d" % (i + 1), "色%d" % (j + 1)


def main():
    out = []
    W = out.append
    W("# 配色 v6 复核（色盲 / 灰度 / 色带单调性）")
    W("")
    W("> 方法：Machado 2009（severity 1.0）+ CIE76 ΔE + CIE L*（D65）；")
    W("> 色带单调性用累积口径 `max(L − running_min(L))`。")
    W("> 本脚本**独立重写**色彩数学（不 import gen_figures_v3），作为交叉复核。")
    W("")
    W("## 一、8 色基色量测（含 C*/Cmax 去灰指标）")
    W("")
    W("| 色 | HEX | L* | C* | H° | C*/Cmax | 对白底对比度 | 灰度Y |")
    W("|---|---|---|---|---|---|---|---|")
    for nm, h in zip(FAM, PAL_USER):
        c = hex2rgb(h)
        L, C, H = rgb2lch(c)
        W("| %s | `%s` | %.1f | %.1f | %.1f | %.3f | %.2f:1 | %.3f |" % (
            nm, h.upper(), L, C, H, C / cmax_at(L, H), (1.05) / (rel_lum(c) + 0.05),
            rel_lum(c)))
    W("")
    W("### 1.1 v5 → v6 深色派生对照（线条/描边用色）")
    W("")
    W("| 基色 | v5 `darken` | v6 `deepen`(墨色) | v5 C* | v6 C* | 彩度提升 |")
    W("|---|---|---|---|---|---|")
    for h in PAL_USER:
        d5 = darken(h, .38)
        d6 = deepen(h, .34)
        c5, c6 = rgb2lab(d5), rgb2lab(d6)
        C5 = math.hypot(c5[1], c5[2])
        C6 = math.hypot(c6[1], c6[2])
        W("| `%s` | `%s` | `%s` | %.1f | %.1f | %+.1f |" % (
            h.upper(), rgb2hex(d5), rgb2hex(d6), C5, C6, C6 - C5))
    W("")
    W("## 二、分类用色集：最小 ΔE 与「会合并」对数")
    W("")
    W("| 用色集 | 场景 | 条件 | 最小 ΔE | 最危险色对 | <10 对数 |")
    W("|---|---|---|---|---|---|")
    rows = analyse()
    for r in rows:
        a, b = fmt_idx(r["set"], r["i"], r["j"])
        W("| %s | %s | %s | %.1f | %s ↔ %s | %d/%d |" % (
            r["set"], r["note"], r["cond"], r["dmin"], a, b,
            r["n_merge"], r["n"] * (r["n"] - 1) // 2))
    W("")
    W("## 三、顺序色带明度单调性（累积回升，判据 ≤0.5 L*）")
    W("")
    W("| 色带 | 起 L* | 止 L* | 累积回升 L* | 判定 |")
    W("|---|---|---|---|---|")
    ramp_res = {}
    for nm, ramp in [("CMAP_TEMP（温度）", CMAP_TEMP), ("CMAP_MOIST（水分）", CMAP_MOIST),
                     ("CMAP_TEMP v5 对照", CMAP_TEMP_V5),
                     ("CMAP_MOIST v5 对照", CMAP_MOIST_V5),
                     ("famT 7 级", FAMT7), ("famM 7 级", FAMM7)]:
        ls = [lightness(c) for c in ramp]
        rise = monotone_rise(ls)
        ok = rise <= 0.5
        ramp_res[nm] = dict(start=ls[0], end=ls[-1], rise=rise, ok=ok)
        W("| %s | %.1f | %.1f | %.2f | %s |" % (nm, ls[0], ls[-1], rise,
                                                "OK 单调" if ok else "FAIL 有回升"))
    W("")
    W("## 四、结论")
    W("")
    bad = [r for r in rows if r["cond"] != "灰度 L*" and r["dmin"] < 10]
    badg = [r for r in rows if r["cond"] == "灰度 L*" and r["dmin"] < 5]
    if not bad:
        W("- 所有分类用色集在三种色盲模拟下最小 ΔE 均 ≥10 → **无色盲合并风险**。")
    else:
        W("- 以下集合在色盲模拟下出现 ΔE <10（会合并），必须靠线型/标记冗余区分：")
        for r in bad:
            a, b = fmt_idx(r["set"], r["i"], r["j"])
            W("  - %s @ %s：ΔE=%.1f（%s ↔ %s）" % (r["set"], r["cond"], r["dmin"], a, b))
    if not badg:
        W("- 所有分类用色集灰度下最小 |ΔL*| ≥5 → **灰度打印仍可区分**。")
    else:
        W("- 以下集合灰度下 |ΔL*| <5：")
        for r in badg:
            a, b = fmt_idx(r["set"], r["i"], r["j"])
            W("  - %s：|ΔL*|=%.1f（%s ↔ %s）" % (r["set"], r["dmin"], a, b))
    txt = "\n".join(out)
    io.open(OUT_TXT, "w", encoding="utf-8").write(txt)
    io.open(OUT_JSON, "w", encoding="utf-8").write(
        json.dumps(dict(rows=rows, ramps=ramp_res), ensure_ascii=False, indent=1))
    print(txt)


if __name__ == "__main__":
    main()
