"""figstyle — 出版级"质感三件套"共享绘图规范（figure-craft 真源）。

三条铁律（对标高水平参考图集逐像素取色后确立）：
  ① 大面积填充一律浅色渐变（浅端→更浅端），禁止纯色平涂；
  ② 每个填充块配同族饱和描边（边缘"荧光"效果 = 描边外再叠一层半透明加宽描边）；
  ③ 细线/文字用墨色系（ink_of / deepen），浅色严禁直接作细线或文字色。

色板真源：../assets/palette_v6.json（夏日海滩 v6；T4=底色渐变、T2=卡片渐变底、
TACC=荧光描边角色）。相对本文件定位，加载失败回退内置同值——零外部依赖。

用法（gen_fig_*.py 顶部）：
    import figstyle as fs
    fs.apply(ax)                                   # 统一坐标轴/网格/刻度
    fs.gradient_box(ax, x, y, w, h, fs.PASTEL["green"])   # 流程图/卡片
    fs.save_fig(fig, "out/fig.png", "out/fig.pdf")
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import to_rgb, LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch

# ---- 字体：衬线拉丁 + 中文衬线跨 family 回退（含中文串禁混 $...$ mathtext）----
_avail = {f.name for f in font_manager.fontManager.ttflist}
_fams = [n for n in ("Times New Roman", "Noto Serif SC", "Source Han Serif SC",
                     "SimSun", "DejaVu Serif") if n in _avail]
plt.rcParams["font.family"] = _fams or ["DejaVu Serif"]
plt.rcParams["axes.unicode_minus"] = False

# ---- 字号阶梯（按"插入文档后 ≥8pt"反推，画布约 6.1 in；窄画布需整体再上调）----
FS_TITLE = 11.0
FS_LABEL = 10.5
FS_TICK = 9.5
FS_LEGEND = 9.5
FS_ANNO = 9.0
FS_NOTE = 8.5

# ---- v6 色板（相对加载，失败回退内置同值）----
_V6 = Path(__file__).resolve().parent.parent / "assets" / "palette_v6.json"
try:
    _p = json.load(open(_V6, encoding="utf-8"))
    _w = {c["key"]: c["hex"] for c in _p["warm_family"]["colors"]}
    _c = {c["key"]: c["hex"] for c in _p["cool_family"]["colors"]}
    if not str(_c.get("M3", "#")).startswith("#"):
        _c["M3"] = "#90D9CB"  # 真源里 M3 是 mix_lab 表达式，解析为 LAB 中点实值
    _n = {c["key"]: c["hex"] for c in _p["neutrals"]}
    _INK = _p["ink_map"]
except Exception:
    _w = {"T4": "#FEE6A9", "T3": "#FED3A1", "T2": "#FEBDAA", "TMAIN": "#FEB8B5", "TACC": "#FDA574"}
    _c = {"M4": "#9FE698", "M3": "#90D9CB", "MMAIN": "#6FCDFD", "M1": "#2BC3F1"}
    _n = {"INK": "#2B2B2E", "CRIT": "#57575A", "NEU": "#B6B6B2", "GRID": "#EBE8E3", "SOFT": "#FBF7F1"}
    _INK = {}

# 青绿族浅色对应的原墨色是藏蓝系（#3B7287/#307697），一律本地覆盖为深青绿
# #0F7E78（白底对比度≈6.5，满足"细线/文字用深端"，且不属蓝色深色）。暖族墨色不变。
for _k in ("#2BC3F1", "#6FCDFD"):
    if isinstance(_INK.get(_k), dict):
        _INK[_k] = dict(_INK[_k], ink="#0F7E78")


class WARM:
    T4, T3, T2, TMAIN, TACC = _w["T4"], _w["T3"], _w["T2"], _w["TMAIN"], _w["TACC"]
    DEEP = "#A3490D"          # 暖族深端
    MID = "#C74C53"           # TMAIN 墨色


class COOL:
    M4, M3, MMAIN, M1 = _c["M4"], _c["M3"], _c["MMAIN"], _c["M1"]
    # 蓝色系禁深色（藏蓝 = AI 感）：向亮青绿族靠拢，DEEP 端锚定 #00B4AD。
    # 任何填充/柱体/细线不得取深蓝。
    DEEP = "#00B4AD"          # 青绿族深端（亮青绿，非藏蓝）


INK, CRIT, NEU, GRID, SOFT = _n["INK"], _n["CRIT"], _n["NEU"], _n["GRID"], _n.get("SOFT", "#FBF7F1")

WARM_SEQ = [WARM.DEEP, WARM.MID, WARM.TMAIN, WARM.T3, WARM.T4]    # 深→浅（时间/位置越远越浅）
COOL_SEQ = [COOL.DEEP, "#2CC8BC", COOL.M1, COOL.MMAIN, COOL.M4]   # 青绿深端→浅端（无藏蓝）
LS_SEQ = ["-", (0, (4, 1.5)), (0, (1, 1)), (0, (3, 1, 1, 1))]
# 数据曲线主色（族深端，满足"细线用墨色/深端"铁律；浅色禁作细线）
PC = [COOL.DEEP, COOL.M1, WARM.MID, WARM.TACC]
PC_INK = [COOL.DEEP, "#2CC8BC", WARM.MID, "#A35B31"]
# 青绿族文字/小元素墨色（#00B4AD 只作线/填充，不作小字）
AQUA_INK = "#0F7E78"


def ink_of(hexv):
    """浅色填充 → 同色系墨色（描边/文字用）。"""
    v = _INK.get(hexv.upper()) or _INK.get(hexv)
    return v["ink"] if isinstance(v, dict) else (v or hexv)


# ---- pastel 框色对（fill 浅端 + 同族饱和描边，逐像素取自参考图集）----
PASTEL = {
    "yellow": ("#F7E8C3", "#D89060"),
    "orange": ("#F6DCC8", "#C97A46"),
    "blue":   ("#DCF5F1", "#3ECFBE"),   # 蓝族 = 亮青绿浅底 + 青绿描边（禁藏蓝）
    "green":  ("#E2F0DC", "#78A878"),
    "rose":   ("#F2DCDC", "#C08478"),
    "gray":   ("#EFEDE8", "#9A968A"),
}


def _rgb2hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v * 255)))) for v in rgb)


def lighten(hexv, t):
    r, g, b = to_rgb(hexv)
    return _rgb2hex((r + (1 - r) * t, g + (1 - g) * t, b + (1 - b) * t))


def deepen(hexv, t=0.45):
    r, g, b = to_rgb(hexv)
    return _rgb2hex((r * (1 - t), g * (1 - t), b * (1 - t)))


def gradient_box(ax, x, y, w, h, pastel, *, vertical=True, rounding=0.12,
                 glow=0.30, lw=1.3, zorder=2, alpha_top=0.62):
    """浅色渐变填充 + 同族饱和描边 + 外圈半透明"荧光"描边（质感三件套）。

    pastel: (fill, edge) 二元组，如 PASTEL["green"]；坐标为 ax 数据系。
    返回 FancyBboxPatch（可 set_clip 后放文字）。流程图/卡片框首选。
    """
    fill, edge = pastel
    top = lighten(fill, alpha_top)
    bot = fill
    cmap = LinearSegmentedColormap.from_list("gb", [bot, top] if vertical else [top, bot])
    rs = min(w, h) * rounding
    style = f"round,pad=0,rounding_size={rs}"
    halo = FancyBboxPatch((x, y), w, h, boxstyle=style,
                          facecolor="none", edgecolor=edge,
                          linewidth=lw + 3.2, alpha=glow, zorder=zorder - 0.5)
    ax.add_patch(halo)
    n = 64
    g = np.linspace(0, 1, n)
    grad = (g.reshape(-1, 1) if vertical else g.reshape(1, -1))
    im = ax.imshow(grad, cmap=cmap, extent=(x, x + w, y, y + h),
                   origin="lower" if vertical else "upper", aspect="auto", zorder=zorder)
    box = FancyBboxPatch((x, y), w, h, boxstyle=style,
                         facecolor="none", edgecolor=edge, linewidth=lw,
                         zorder=zorder + 0.6, mutation_aspect=1)
    ax.add_patch(box)
    im.set_clip_path(box)
    return box


def _rgba(hexv, a):
    r, g, b = to_rgb(hexv)
    return (r, g, b, a)


def gradient_bar(ax, x0, y0, w, h, color, *, horizontal=False, fade=0.78,
                 lw=1.0, glow=0.30, zorder=3):
    """渐变柱体（替代纯色平涂）。

    远离基线的一端取饱和色、基线端渐浅；同色加宽半透明描边作"荧光"边。
    horizontal=True 时沿 x 方向渐变（右端饱和）。
    ⚠ 替换原 ax.bar 后回查图例：Rectangle 手柄易丢。"""
    from matplotlib.patches import Rectangle
    top, bot = color, lighten(color, fade)
    cmap = LinearSegmentedColormap.from_list("gb2", [bot, top])
    rect = Rectangle((x0, y0), w, h, facecolor="none", edgecolor=color,
                     linewidth=lw, zorder=zorder + 0.6)
    halo = Rectangle((x0, y0), w, h, facecolor="none", edgecolor=color,
                     linewidth=lw + 2.6, alpha=glow, zorder=zorder - 0.5)
    ax.add_patch(halo)
    ax.add_patch(rect)
    n = 48
    grad = (np.linspace(0, 1, n).reshape(1, -1) if horizontal
            else np.linspace(0, 1, n).reshape(-1, 1))
    im = ax.imshow(grad, cmap=cmap, extent=(x0, x0 + w, y0, y0 + h),
                   origin="lower", aspect="auto", zorder=zorder)
    im.set_clip_path(rect)
    return rect


def gradient_area(ax, x, y, color, *, baseline=0.0, max_alpha=0.5, zorder=1):
    """曲线下渐变填充：贴曲线处有色、向基线渐隐（替代纯色 fill_between）。

    baseline 可为标量或同长数组——传另一条线即得"差值渐变带"；
    方向按两端均值自动翻转。"""
    from matplotlib.patches import Path, PathPatch
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    bl = np.broadcast_to(np.asarray(baseline, float), x.shape)
    verts = np.vstack([np.column_stack([x, y]),
                       np.column_stack([x[::-1], bl[::-1]])])
    patch = PathPatch(Path(verts), facecolor="none", edgecolor="none", zorder=zorder)
    ax.add_patch(patch)
    lo = min(float(np.min(y)), float(np.min(bl)))
    hi = max(float(np.max(y)), float(np.max(bl)))
    y_up = float(np.mean(y)) >= float(np.mean(bl))
    c0 = _rgba(color, 0.02) if y_up else _rgba(color, max_alpha)
    c1 = _rgba(color, max_alpha) if y_up else _rgba(color, 0.02)
    cmap = LinearSegmentedColormap.from_list("ga", [c0, c1])
    grad = np.linspace(0, 1, 64).reshape(-1, 1)
    im = ax.imshow(grad, cmap=cmap, extent=(float(x.min()), float(x.max()), lo, hi),
                   origin="lower", aspect="auto", zorder=zorder)
    im.set_clip_path(patch)
    return patch


def fade_area_x(ax, x_curve, y, color, *, max_alpha=0.38, zorder=1):
    """横向渐变面：x 越靠近曲线值越饱和、向 x=0 渐隐（垂直剖面/廓线用）。"""
    from matplotlib.path import Path as MPath
    from matplotlib.patches import PathPatch
    x_curve = np.asarray(x_curve, float)
    y = np.asarray(y, float)
    pts = np.column_stack([np.concatenate([x_curve, np.zeros_like(y[::-1])]),
                           np.concatenate([y, y[::-1]])])
    patch = PathPatch(MPath(pts), facecolor="none", edgecolor="none", zorder=zorder)
    ax.add_patch(patch)
    cmap = LinearSegmentedColormap.from_list(
        "fx", [_rgba(color, 0.03), _rgba(color, max_alpha)])
    g = np.linspace(0, 1, 64).reshape(1, -1)
    im = ax.imshow(g, cmap=cmap, extent=(0, float(x_curve.max()), float(y.min()), float(y.max())),
                   origin="lower", aspect="auto", zorder=zorder)
    im.set_clip_path(patch)
    return patch


def glow_scatter(ax, x, y, color, *, s=42, alpha=0.26, scale=2.8, zorder=3, **kw):
    """荧光标记：同色大半透明点垫底 + 实心点在上（棒棒糖头、得分点阵）。"""
    ax.scatter(x, y, s=s * scale, c=color, alpha=alpha, linewidths=0, zorder=zorder - 0.3)
    return ax.scatter(x, y, s=s, c=color, zorder=zorder, **kw)


def glow_line(ax, x, y, color, *, lw=1.8, alpha=0.22, zorder=3, **kw):
    """荧光线：加宽半透明同色线垫底 + 主线在上。"""
    ax.plot(x, y, lw=lw + 2.8, color=color, alpha=alpha,
            solid_capstyle="round", zorder=zorder - 0.3)
    return ax.plot(x, y, lw=lw, color=color, zorder=zorder, **kw)


def apply(ax, *, grid=True, boxed=False, bg=None):
    """统一坐标轴风格：左+下轴线、极浅网格；bg=面板浅底色（如 '#FDFBF6'）。"""
    ax.spines["top"].set_visible(bool(boxed))
    ax.spines["right"].set_visible(bool(boxed))
    ax.spines["left"].set_color("#8A8A8A"); ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_color("#8A8A8A"); ax.spines["bottom"].set_linewidth(0.8)
    if boxed:
        for s in ("top", "right"):
            ax.spines[s].set_color("#C9C9C9"); ax.spines[s].set_linewidth(0.6)
    if grid:
        ax.grid(True, color=GRID, linewidth=0.6, zorder=0)
    ax.tick_params(labelsize=FS_TICK, length=3, color="#8A8A8A")
    ax.set_axisbelow(True)
    ax.set_facecolor(bg) if bg else ax.patch.set_facecolor("white")
    return ax


def label(ax, *, xlabel=None, ylabel=None):
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=FS_LABEL, color=INK)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=FS_LABEL, color=INK)


def legend(ax, *, loc="upper right", **kw):
    return ax.legend(fontsize=FS_LEGEND, frameon=True, framealpha=0.92,
                     edgecolor=NEU, fancybox=False, loc=loc, **kw)


def panel_title(ax, text):
    """仅多面板图的 (a)(b) 顶部小标题；单面板图禁止调用（结论进 caption）。"""
    ax.set_title(text, fontsize=FS_TITLE, pad=6, color=INK)


def save_fig(fig, path_png, path_pdf=None):
    fig.savefig(path_png, dpi=300, bbox_inches="tight", facecolor="white")
    if path_pdf:
        fig.savefig(path_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def setup_style(palette="elegant", **kw):
    """出图脚本统一风格入口（figure_check.sh 认这个 token）。

    同包内有 plot_utils 时委托其 setup_style（PALETTES 全家桶：nature/tableau/
    npg/nejm/colorblind…），否则仅保证本模块的字体与字号 rcParams 已生效。
    坐标轴级样式仍由 apply(ax) 负责，两者不冲突。"""
    try:
        from plot_utils import setup_style as _ps
        return _ps(palette=palette, **kw)
    except Exception:
        plt.rcParams["font.family"] = _fams or ["DejaVu Serif"]
        plt.rcParams["axes.unicode_minus"] = False
        return None


save = save_fig  # 简写别名
