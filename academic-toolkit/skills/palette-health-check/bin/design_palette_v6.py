# -*- coding: utf-8 -*-
"""配色 v6 设计器：提亮 + 提彩度 + 去灰，且修正"墨色调深即发灰"的结构性缺陷。

用户反馈（原文）："有几个颜色还是太深了，且有点点发灰，而且不够鲜艳，不够亮眼的那种感觉，有点克制了似乎。"

诊断（v5 实测 C*/C*max，即**彩度占该明度下 sRGB 色域上限的比例**——这才是"发灰"的客观度量）：
    TMAIN #FDB0AE  C*/max = 0.962  已近上限
    T2    #FDB49E  C*/max = 0.959  已近上限
    TACC  #fba270  C*/max = 0.930  已近上限
    T3    #ffcd92  C*/max = 0.999  满彩度
    T4    #fce198  C*/max = 0.847  ← 偏灰
    M4    #b0d7aa  C*/max = 0.269  ← 极灰（"发灰"主凶）
    M1    #65bddf  C*/max = 0.720  ← 偏灰
    MMAIN #58C7FC  C*/max = 0.956  已近上限

两个结构性结论：
  A. **暖族 5 色已贴近 sRGB 色域上限**。对高明度粉彩（pastel），"更亮"与"更艳"在 sRGB 里是
     互斥的（提 L* 必然掉 C*）。所以暖族的"发灰"感来自**明度高**这一设计选择本身，
     只能靠小幅调 L* 与提高彩度占比改善，不能靠暴力加饱和。
  B. **真正的"发灰"在水分族（M4/M1）与派生暗色上**。特别是 `darken(c, f)` 这种
     "向黑等比缩放 RGB"的调深方式会**同比例砍掉彩度** → 得到的是浑浊的深灰彩，
     不是饱满的深色。这是"有点点发灰"的另一半原因。

v6 改法：
  1) 基色：色相 H° 一律不动；族内 L* 严格单调；把 C* 推到该 (L*,H°) 下色域上限的指定比例。
     - TMAIN/T2/T3/TACC/MMAIN 本就 ≥0.93，维持高比例，仅做微小明度调整（不更深）。
     - T4 → 0.95、M1 → 0.95、M4 → 0.55（M4 是冷色带"浅端"，不能推到极限，否则变荧光绿
       且与暖族粉彩打架，故只提到"清新浅绿"档）。
  2) 派生暗色：用 **deepen(c, L*)** 取代 darken(c, f) —— 保持色相、指定明度、
     彩度仍取该处色域上限的 0.90 → 得到**饱满的深色**而非浑浊的黑化色。
  3) 色带深端同步改用 deepen()。

产物：_palette_v6.json + review/diag/palette_v6_preview.png
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
OUT = os.path.join(ROOT, "data", "_palette_v6.json")
PREVIEW = os.path.join(ROOT, "references", "palette_v6_preview.png")


# ---------------------------------------------------------------- 色彩工具
def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb2hex(c):
    return "#" + "".join("%02X" % max(0, min(255, round(v * 255))) for v in c)


def s2l(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def l2s_raw(c):
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def l2s(c):
    return l2s_raw(min(1.0, max(0.0, c)))


def lin2xyz(c):
    r, g, b = c
    return (0.4124564 * r + 0.3575761 * g + 0.1804375 * b,
            0.2126729 * r + 0.7151522 * g + 0.0721750 * b,
            0.0193339 * r + 0.1191920 * g + 0.9503041 * b)


_WP = lin2xyz((1.0, 1.0, 1.0))


def f_lab(t):
    return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29


def rgb2lab(rgb):
    X, Y, Z = lin2xyz(tuple(s2l(v) for v in rgb))
    fx, fy, fz = f_lab(X / _WP[0]), f_lab(Y / _WP[1]), f_lab(Z / _WP[2])
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lab2rgb_raw(lab):
    L, a, b = lab
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200

    def g(t):
        return t ** 3 if t > 6 / 29 else 3 * (6 / 29) ** 2 * (t - 4 / 29)
    X, Y, Z = 0.95047 * g(fx), 1.0 * g(fy), 1.08883 * g(fz)
    return tuple(l2s_raw(v) for v in
                 (3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z,
                  -0.9692660 * X + 1.8760108 * Y + 0.0415560 * Z,
                  0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z))


def lab2rgb(lab):
    return tuple(min(1.0, max(0.0, v)) for v in lab2rgb_raw(lab))


def lch2rgb_raw(L, C, h):
    r = math.radians(h)
    return lab2rgb_raw((L, C * math.cos(r), C * math.sin(r)))


def lch2rgb(L, C, h):
    return tuple(min(1.0, max(0.0, v)) for v in lch2rgb_raw(L, C, h))


def rgb2lch(rgb):
    L, a, b = rgb2lab(rgb)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def in_gamut(rgb, tol=1e-4):
    return all(-tol <= v <= 1 + tol for v in rgb)


def cmax_at(L, h):
    lo, hi = 0.0, 180.0
    for _ in range(52):
        m = (lo + hi) / 2
        if in_gamut(lch2rgb_raw(L, m, h)):
            lo = m
        else:
            hi = m
    return lo


def rel_lum(rgb):
    r, g, b = (s2l(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_white(rgb):
    return 1.05 / (rel_lum(rgb) + 0.05)


def deltaE(r1, r2):
    a, b = rgb2lab(r1), rgb2lab(r2)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def at_ratio(L, h, ratio):
    """在 (L*,h) 下取色域上限的 ratio 倍彩度。"""
    C = cmax_at(L, h) * ratio
    return lch2rgb(L, C, h), C


def deepen(hexc, L_target, ratio=0.90):
    """**保色相**调深：固定 H°，把 L* 压到 L_target，彩度取该处上限的 ratio。
    取代 darken(c,f)（后者向黑等比缩放 RGB，会把彩度一起砍掉 → 浑浊发灰）。

    注意 ratio 必须**适度**：低明度处色域允许的彩度极高，若取 0.9 会得到
    荧光红/荧光绿等与本套粉彩家族完全断裂的颜色。故线条色统一取 ~0.62：
    比 darken() 明显更饱满（去"灰"），又不至于变成霓虹色。
    """
    h = rgb2lch(hex2rgb(hexc) if isinstance(hexc, str) else hexc)[2]
    return at_ratio(L_target, h, ratio)[0]


def lightest_L_for_contrast(h, need, hi=70.0, lo=20.0, ratio=0.62):
    """求满足「对白底 ≥ need:1」的最亮 L*（更亮 = 对比度更低，故二分求上界）。"""
    best = lo
    for _ in range(40):
        mid = (lo + hi) / 2
        c = at_ratio(mid, h, ratio)[0]
        if contrast_white(c) >= need:
            best = mid
            lo = mid
        else:
            hi = mid
    return best


# ---------------------------------------------------------------- v6 目标
# (key, 名称, 族, 源 HEX, 目标 L*, 彩度占比, 备注)
BASE = [
    ("TMAIN", "温度主色（暖锚）", "warm", "#FDB0AE", 81.0, 0.97, "微提亮 +0.5L*，彩度已近上限"),
    ("T2",    "温度蜜桃",        "warm", "#FDB49E", 82.0, 0.97, "**提亮 +2.4L***：原 79.6 低于提亮后的 TMAIN(81.0)，会破坏族内单调"),
    ("TACC",  "深橙高亮",        "warm", "#fba270", 75.5, 0.96, "提亮 +1.0L*"),
    ("T3",    "温度浅橙",        "warm", "#ffcd92", 87.0, 0.96, "提亮 +1.5L*"),
    ("T4",    "温度浅黄",        "warm", "#fce198", 92.0, 0.95, "**提彩度** 0.847→0.95，去灰"),
    ("M4",    "水分浅绿",        "cool", "#b0d7aa", 85.0, 0.45, "**提彩度** 0.269→0.45，去灰主凶；受浅端角色约束不上极限"),
    ("M1",    "水分天蓝",        "cool", "#65bddf", 73.5, 0.95, "**提彩度** 0.720→0.95，去灰"),
    ("MMAIN", "水分主色（冷锚）", "cool", "#58C7FC", 78.5, 0.97, "提亮 +2.5L*（原为 76.0，偏深）"),
]

# 墨色（线条/描边）：以「对白底 4.6:1」的最亮明度为基准，再按 offset 下压，
# 既保证可读性下限，又保住彼此间的灰度差（v5 的 darken 版灰度差仅 0.4 L*）。
INK_OFF = {
    "TMAIN": 0.0, "T2": 1.5, "TACC": 3.0, "T3": 4.5, "T4": 6.0,
    "M4": 1.0, "M1": 4.0, "MMAIN": 2.5,
}
INK_RATIO = 0.65
INK_MIN_CONTRAST = 4.6

# 顺序色带深端（热图/曲面最高值端）：v5 用 darken(c,.34/.30) → 浑浊深棕/深灰蓝。
# v6 改用 deepen()，得到 YlOrRd / GnBu 那种"饱和深红 / 饱和深蓝"的标准深端。
RAMP_DEEP = {"TEMP": ("TACC", 42.0), "MOIST": ("M1", 40.0)}


def src_ratio(hexc, f, L_target):
    """某个基准色用 darken(c,f) 调深后的"彩度占比"，用于设定**不可回退下界**。

    实测发现：darken() 对**浅色暖调**最伤（把 C*/Cmax 砍到 0.35–0.5，故"发灰"），
    但对**蓝调**伤害小（原本就在 0.74 左右）。因此统一取
    `ratio = max(目标, 原占比)`，保证「只改善、不回退」。
    """
    old = tuple(v * (1 - f) for v in hex2rgb(hexc))
    Lo, Co, h = rgb2lch(old)
    return Co / max(1e-9, cmax_at(L_target, h))


def main():
    rows = []
    for key, name, fam, src, L, ratio, note in BASE:
        h = rgb2lch(hex2rgb(src))[2]
        rgb, C = at_ratio(L, h, ratio)
        ink_L = lightest_L_for_contrast(h, INK_MIN_CONTRAST, ratio=INK_RATIO) - INK_OFF[key]
        r_ink = max(INK_RATIO, src_ratio(src, 0.38, ink_L))
        ink = at_ratio(ink_L, h, r_ink)[0]
        rows.append(dict(key=key, name=name, fam=fam, src=src.upper(), hex=rgb2hex(rgb),
                         L=L, C=C, Cmax=cmax_at(L, h), ratio=ratio, H=h, note=note,
                         dE=deltaE(hex2rgb(src), rgb),
                         ink=rgb2hex(ink), ink_L=round(ink_L, 1),
                         ink_ratio=round(r_ink, 3),
                         ink_contrast=contrast_white(ink),
                         old_ink=rgb2hex(tuple(v * 0.62 for v in hex2rgb(src)))))

    hdr = "%-6s %-16s %-5s %-9s %-9s %6s %6s %6s %6s %6s %6s" % (
        "key", "名称", "族", "v5 HEX", "v6 HEX", "L*旧", "L*新", "C*旧", "C*新",
        "C/max", "ΔE")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        Lo, Co, _ = rgb2lch(hex2rgb(r["src"]))
        print("%-6s %-16s %-5s %-9s %-9s %6.1f %6.1f %6.1f %6.1f %6.2f %6.1f" %
              (r["key"], r["name"], r["fam"], r["src"], r["hex"], Lo, r["L"], Co, r["C"],
               r["ratio"], r["dE"]))

    ok = True
    print()
    for fam in ("warm", "cool"):
        seq = sorted([r for r in rows if r["fam"] == fam], key=lambda r: -r["L"])
        Ls = [r["L"] for r in seq]
        print("   %-4s 族 L* 递减: %s" % (fam, ["%.1f" % v for v in Ls]))
        if Ls != sorted(Ls, reverse=True):
            ok = False
    # 【v6 补强】族内"清单排序"单调还不够 —— 必须再验**实际入带顺序**（gen_figures_v3.py
    #   里 CMAP_* 与 famT 的停靠点顺序）也单调。上一版正是漏了这一步：清单按 L* 排序看是
    #   单调的，但入带序是 T4→T3→T2→TMAIN→TACC，TMAIN(81.0) > T2(79.5) →
    #   顺序色带出现 1.55 L* 的假亮带，而清单检查报 PASS。
    RAMP_ORDER = {
        "TEMP": ["T4", "T3", "T2", "TMAIN", "TACC"],
        "MOIST": ["M4", "M3", "MMAIN", "M1"],
    }
    by_key = dict((r["key"], r) for r in rows)
    for tag, order in RAMP_ORDER.items():
        Ls = []
        for k in order:
            if k == "M3":
                # 族内中段：M4 与 MMAIN 的 LAB 中点
                lo = rgb2lch(hex2rgb(by_key["M4"]["hex"]))[0]
                hi = rgb2lch(hex2rgb(by_key["MMAIN"]["hex"]))[0]
                Ls.append(0.5 * (lo + hi))
            else:
                Ls.append(by_key[k]["L"])
        print("   %-5s 入带序 %s L*: %s" % (tag, "→".join(order), ["%.1f" % v for v in Ls]))
        rise = 0.0
        mn = Ls[0]
        for L in Ls:
            mn = min(mn, L)
            rise = max(rise, L - mn)
        if rise > 0.5:
            print("!! %s 入带序非单调：累积回升 %.2f L* (>0.5) → 灰度会出假亮带" % (tag, rise))
            ok = False
        else:
            print("      入带序累积回升 %.2f L* → OK" % rise)
    for r in rows:
        hn = rgb2lch(hex2rgb(r["hex"]))[2]
        d = abs(hn - r["H"]); d = min(d, 360 - d)
        if d > 1.5:
            print("!! %s 色相漂移 %.2f°" % (r["key"], d)); ok = False
        if r["ink_contrast"] < 4.5:
            print("!! %s 墨色对白底对比度仅 %.2f:1 (<4.5)" % (r["key"], r["ink_contrast"]))
            ok = False
    print("\n族内单调 / 色相保持 / 墨色对比度：%s" % ("PASS" if ok else "FAIL"))

    print("\n墨色（线条）新旧对照：")
    for r in rows:
        oi, ni = hex2rgb(r["old_ink"]), hex2rgb(r["ink"])
        Lo, Co, _ = rgb2lch(oi); Ln, Cn, _ = rgb2lch(ni)
        print("  %-6s darken(.38) %s (L*%4.1f C*%5.1f, %4.2f:1)  →  deepen %s (L*%4.1f C*%5.1f, %4.2f:1)"
              % (r["key"], r["old_ink"], Lo, Co, contrast_white(oi),
                 r["ink"], Ln, Cn, r["ink_contrast"]))

    print("\n顺序色带深端（v5 darken → v6 deepen）：")
    ramps = {}
    for tag, (bk, Ld) in RAMP_DEEP.items():
        src = dict((r["key"], r) for r in rows)[bk]["src"]
        f = 0.34 if tag == "TEMP" else 0.30   # 与 gen_figures_v3.py 中 darken(TACC,.34)/(M1,.30) 一致
        h = rgb2lch(hex2rgb(src))[2]
        rr = 0.92                              # 色带深端是极小面积，取色域上限 92%，做最饱满的深端
        new = at_ratio(Ld, h, rr)[0]
        old = tuple(v * (1 - f) for v in hex2rgb(src))
        Lo, Co, _ = rgb2lch(old); Ln, Cn, _ = rgb2lch(new)
        ramps[tag] = rgb2hex(new)
        print("  CMAP_%-5s 深端 %s (L*%4.1f C*%5.1f)  →  %s (L*%4.1f C*%5.1f, 占比%.2f)"
              % (tag, rgb2hex(old), Lo, Co, rgb2hex(new), Ln, Cn, rr))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(dict(rows=rows, ramps=ramps, ok=ok), f, ensure_ascii=False, indent=1)
    print("\n-> %s" % OUT)

    # ---- 预览图
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
        plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "SimHei"],
                             "axes.unicode_minus": False})
        fig, axes = plt.subplots(2, 1, figsize=(9.2, 4.2))
        for ax, tag in zip(axes, ("v5（现用）", "v6（提亮·提彩·去灰）")):
            src = tag.startswith("v5")
            for i, r in enumerate(rows):
                c = hex2rgb(r["src"] if src else r["hex"])
                ax.add_patch(Rectangle((i, 0.45), 0.92, 0.45, facecolor=c,
                                       edgecolor="white", lw=1.2))
                ink = hex2rgb(r["old_ink"] if src else r["ink"])
                ax.add_patch(Rectangle((i, 0.22), 0.92, 0.16, facecolor=ink, edgecolor="none"))
                ax.text(i + 0.46, 0.60, r["key"], ha="center", va="center",
                        fontsize=7.5, color="#2B2B2E")
            ax.set_xlim(-0.3, 8.1); ax.set_ylim(0, 1.05); ax.axis("off")
            ax.text(-0.25, 0.95, tag, fontsize=10, color="#2B2B2E")
            ax.text(-0.25, 0.10, "上：8 基色（填充/色带）　下：线条色", fontsize=7,
                    color="#6E6E6E")
        fig.suptitle("配色 v5 → v6 对照", fontsize=12, color="#2B2B2E")
        os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)
        fig.savefig(PREVIEW, dpi=140, facecolor="white", bbox_inches="tight")
        print("-> %s" % PREVIEW)
    except Exception as e:
        print("[warn] 预览图未生成：", e)


if __name__ == "__main__":
    main()
