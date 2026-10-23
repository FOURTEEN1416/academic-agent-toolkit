"""figstyle — figure-craft 质感叠加层（样式底层 = 同仓 skills/_utils 唯一真源）。

分层约定：
  · 底层（字体族 / 字号阶梯 / 数据系列色板 / 保存护栏）由
    `academic-toolkit/skills/_utils/academic.mplstyle` 定版，经
    `academic-toolkit/skills/_utils/plot_utils.py` 的 `setup_style()` 加载。
    本模块不定义、也不默认覆盖它们。
  · 叠加层（本模块）：质感三件套、v6 色板 token，以及可选的字体/字号阶梯。
    叠加层一律显式开启——`setup_style(overlay=True)` 才把 figure-craft 字体族与
    字号阶梯压到基线之上；`setup_style(palette="v6")` 才把 v6 色板用作数据系列色。
  · 质感算法真源在 `plot_utils.py`「质感层（可选）」段，本模块只做薄封装。

三条质感铁律（对标高水平参考图集逐像素取色后确立）：
  ① 大面积填充一律浅色渐变（浅端→更浅端），禁止纯色平涂；
  ② 每个填充块配同族饱和描边（边缘"荧光"效果 = 描边外再叠一层半透明加宽描边）；
  ③ 细线/文字用墨色系（ink_of / deepen），浅色严禁直接作细线或文字色。

v6 色板 token：../assets/palette_v6.json（夏日海滩 v6；T4=底色渐变、T2=卡片渐变底、
TACC=荧光描边角色）。相对本文件定位，加载失败回退内置同值。

用法（gen_fig_*.py 顶部）：
    import figstyle as fs
    fs.setup_style()                               # 底层基线（academic.mplstyle）
    fs.apply(ax)                                   # 坐标轴/网格/刻度
    fs.gradient_box(ax, x, y, w, h, fs.PASTEL["green"])   # 流程图/卡片
    fs.save_fig(fig, "out/fig.png", "out/fig.pdf")
需要 figure-craft 的字体/字号阶梯时显式叠加：fs.setup_style(overlay=True)。
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# ---- 底层基线定位（同仓 skills/_utils 唯一真源；缺失时回落 mplstyle / 内置）----
_BASE_MODULE = None
_BASE_LOAD_FAILED = False
_OVERLAY_ACTIVE = False

# 仅在找不到 plot_utils.py 与 academic.mplstyle 时才用的最小兜底
_FALLBACK_BASELINE = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Noto Sans SC", "NotoSansSC", "SimHei", "Microsoft YaHei",
                        "PingFang SC", "Heiti SC", "WenQuanYi Micro Hei",
                        "Arial", "Helvetica", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "savefig.bbox": "standard",
    "savefig.pad_inches": 0.1,
}


def _candidate_dirs():
    """可能存放 plot_utils.py / academic.mplstyle 的目录（仓库内优先）。"""
    dirs = []
    try:
        skills = Path(__file__).resolve().parents[2]   # <toolkit>/skills
        dirs += [skills / "_utils", skills / "shared-scripts"]
    except IndexError:
        pass
    cwd = Path.cwd()
    dirs += [cwd / "skills" / "_utils", cwd / "skills" / "shared-scripts",
             cwd / "academic-toolkit" / "skills" / "_utils",
             cwd / "academic-toolkit" / "skills" / "shared-scripts"]
    seen, out = set(), []
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def _base():
    """加载同仓唯一真源 plot_utils（含 academic.mplstyle 基线）；缺失返回 None。"""
    global _BASE_MODULE, _BASE_LOAD_FAILED
    if _BASE_MODULE is not None:
        return _BASE_MODULE
    if _BASE_LOAD_FAILED:
        return None
    import importlib
    for d in _candidate_dirs():
        if not (d / "plot_utils.py").is_file():
            continue
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
        try:
            mod = importlib.import_module("plot_utils")
        except Exception:
            continue
        if hasattr(mod, "setup_style") and hasattr(mod, "PALETTES"):
            _BASE_MODULE = mod
            return mod
    _BASE_LOAD_FAILED = True
    return None


def _mplstyle_path():
    for d in _candidate_dirs():
        p = d / "academic.mplstyle"
        if p.is_file():
            return p
    return None


def _apply_baseline():
    """无 plot_utils 时也按同一份 academic.mplstyle 起底（口径不分裂）。"""
    p = _mplstyle_path()
    if p is not None:
        matplotlib.rcParams.update(
            matplotlib.rc_params_from_file(str(p), use_default_template=False))
        return str(p)
    matplotlib.rcParams.update(_FALLBACK_BASELINE)
    return "builtin-fallback"


def style_source():
    """当前底层基线来源：'plot_utils' | mplstyle 路径 | 'builtin-fallback'。"""
    if _base() is not None:
        return "plot_utils"
    p = _mplstyle_path()
    return str(p) if p is not None else "builtin-fallback"


# ---- 字号阶梯（叠加层口径：按"插入文档后 ≥8pt"反推，画布约 6.1 in；
#      窄画布需整体再上调。默认不生效，见 setup_style(overlay=True)）----
FS_TITLE = 11.0
FS_LABEL = 10.5
FS_TICK = 9.5
FS_LEGEND = 9.5
FS_ANNO = 9.0
FS_NOTE = 8.5

# ---- v6 色板 token（相对加载，失败回退内置同值；只作显式取色，不设全局）----
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

# 可选叠加色板（仅 setup_style(palette=...) 显式点名时生效；默认色板以
# academic.mplstyle 的 elegant 8 色为准）
FIG_PALETTES = {
    "v6": list(PC),
    "v6_warm": list(WARM_SEQ),
    "v6_cool": list(COOL_SEQ),
}


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


# ---- 字体 / 字号叠加层 ----
def _overlay_fonts():
    """figure-craft 衬线字体链（仅叠加层用；基线用 academic.mplstyle 的 CJK 链）。"""
    avail = {f.name for f in font_manager.fontManager.ttflist}
    fams = [n for n in ("Times New Roman", "Noto Serif SC", "Source Han Serif SC",
                        "SimSun", "DejaVu Serif") if n in avail]
    return fams or ["DejaVu Serif"]


def _rc_pt(key, fallback):
    """读 rcParams 字号（'medium' 之类命名档按 font.size × 倍率换算）。"""
    v = matplotlib.rcParams.get(key, fallback)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        scale = float(font_manager.font_scalings[v])
    except Exception:
        return float(fallback)
    base = matplotlib.rcParams.get("font.size", fallback)
    return float(base if isinstance(base, (int, float)) else fallback) * scale


_FS_ROLES = {
    "title": ("axes.titlesize", FS_TITLE),
    "label": ("axes.labelsize", FS_LABEL),
    "tick": ("xtick.labelsize", FS_TICK),
    "legend": ("legend.fontsize", FS_LEGEND),
    "anno": ("font.size", FS_ANNO),
}


def _pt(role):
    """字号：叠加层开启用 figure-craft 阶梯，否则回落基线 rcParams。"""
    key, overlay_value = _FS_ROLES[role]
    return overlay_value if _OVERLAY_ACTIVE else _rc_pt(key, overlay_value)


def _ink():
    """文字色：叠加层开启用 v6 墨色，否则回落基线 text.color。"""
    return INK if _OVERLAY_ACTIVE else matplotlib.rcParams.get("text.color", "black")


def _apply_overlay():
    global _OVERLAY_ACTIVE
    matplotlib.rcParams["font.family"] = _overlay_fonts()
    matplotlib.rcParams["axes.unicode_minus"] = False
    matplotlib.rcParams.update({
        "font.size": FS_ANNO,
        "axes.titlesize": FS_TITLE,
        "axes.labelsize": FS_LABEL,
        "xtick.labelsize": FS_TICK,
        "ytick.labelsize": FS_TICK,
        "legend.fontsize": FS_LEGEND,
        "legend.frameon": True,
    })
    _OVERLAY_ACTIVE = True


# ---- 质感 API：薄封装，算法真源在 plot_utils「质感层（可选）」----
def _texture(name):
    pu = _base()
    if pu is None or not hasattr(pu, name):
        raise ImportError(
            "figstyle 质感层依赖同仓 plot_utils 的 %s()——请确认 "
            "academic-toolkit/skills/_utils/plot_utils.py 在位（本仓内恒在）" % name
        )
    return getattr(pu, name)


def lighten(*args, **kwargs):
    """颜色变浅：t=0 不变，t=1 变白（实现见 plot_utils.lighten）。"""
    return _texture("lighten")(*args, **kwargs)


def deepen(*args, **kwargs):
    """颜色压暗到同族深端（实现见 plot_utils.deepen）。"""
    return _texture("deepen")(*args, **kwargs)


def gradient_box(*args, **kwargs):
    """浅色渐变填充 + 同族饱和描边 + 外圈荧光（流程图/卡片框）。

    签名与实现见 plot_utils.gradient_box：pastel=(fill, edge)，坐标为 ax 数据系。
    """
    return _texture("gradient_box")(*args, **kwargs)


def gradient_bar(*args, **kwargs):
    """渐变柱体（替代纯色平涂）。签名见 plot_utils.gradient_bar。

    ⚠ 替换原 ax.bar 后回查图例：Rectangle 手柄易丢。
    """
    return _texture("gradient_bar")(*args, **kwargs)


def gradient_area(*args, **kwargs):
    """曲线下/差值渐变带（替代 fill_between）。签名见 plot_utils.gradient_area。"""
    return _texture("gradient_area")(*args, **kwargs)


def fade_area_x(*args, **kwargs):
    """垂直剖面的水平淡出面。签名见 plot_utils.fade_area_x。"""
    return _texture("fade_area_x")(*args, **kwargs)


def glow_scatter(*args, **kwargs):
    """荧光标记：同色大半透明点垫底 + 实心点在上。签名见 plot_utils.glow_scatter。"""
    return _texture("glow_scatter")(*args, **kwargs)


def glow_line(*args, **kwargs):
    """荧光线：加宽半透明同色线垫底 + 主线在上。签名见 plot_utils.glow_line。"""
    return _texture("glow_line")(*args, **kwargs)


def apply(ax, *, grid=True, boxed=False, bg=None):
    """统一坐标轴风格：左+下轴线、极浅网格；字号继承当前基线。"""
    ax.spines["top"].set_visible(bool(boxed))
    ax.spines["right"].set_visible(bool(boxed))
    ax.spines["left"].set_color("#8A8A8A"); ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_color("#8A8A8A"); ax.spines["bottom"].set_linewidth(0.8)
    if boxed:
        for s in ("top", "right"):
            ax.spines[s].set_color("#C9C9C9"); ax.spines[s].set_linewidth(0.6)
    if grid:
        ax.grid(True, color=GRID, linewidth=0.6, zorder=0)
    ax.tick_params(labelsize=_pt("tick"), length=3, color="#8A8A8A")
    ax.set_axisbelow(True)
    ax.set_facecolor(bg) if bg else ax.patch.set_facecolor("white")
    return ax


def label(ax, *, xlabel=None, ylabel=None):
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=_pt("label"), color=_ink())
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=_pt("label"), color=_ink())


def legend(ax, *, loc="upper right", **kw):
    """图例：字号继承基线（叠加层开启时用 figure-craft 阶梯）。

    边框开关随 rcParams.legend.frameon（基线默认无框；叠加层开启有框）。
    """
    return ax.legend(fontsize=_pt("legend"), loc=loc,
                     framealpha=0.92, edgecolor=NEU, fancybox=False, **kw)


def panel_title(ax, text):
    """仅多面板图的 (a)(b) 顶部小标题；单面板图禁止调用（结论进 caption）。"""
    ax.set_title(text, fontsize=_pt("title"), pad=6, color=_ink())


def save_fig(fig, path_png, path_pdf=None):
    """PNG + 可选矢量 PDF 双出；保存护栏随学术基线（禁 bbox_inches='tight'）。

    PNG 的 DPI / 面底色继承 rcParams（academic.mplstyle: savefig.dpi=350）。
    先调 setup_style() 再保存，才能拿到 plot_utils 挂在 Figure.savefig 上的
    布局 / 字号自检 hook。
    """
    _bbox = matplotlib.rcParams.get("savefig.bbox")
    if _bbox in ("standard", "tight"):
        _bbox = None      # ⛔ 基线禁 tight（axes 外文字会把 PDF mediabox 撑爆）
    fig.savefig(path_png, bbox_inches=_bbox)
    if path_pdf:
        fig.savefig(path_pdf, bbox_inches=_bbox)
    plt.close(fig)


def setup_style(palette="auto", *, overlay=False):
    """初始化出图风格：底层走唯一真源，figure-craft 字体/字号/色板是可选叠加层。

    palette 接受 plot_utils.setup_style 的全部取值（'auto'/'elegant'/… 或颜色
    列表），另接受 figure-craft 可选色板 'v6'/'v6_warm'/'v6_cool'。
    overlay=True 才把 figure-craft 衬线字体族与字号阶梯压到基线之上（默认不叠）。
    """
    global _OVERLAY_ACTIVE
    _pal = list(FIG_PALETTES[palette]) if isinstance(palette, str) and palette in FIG_PALETTES else palette
    pu = _base()
    if pu is not None:
        result = pu.setup_style(palette=_pal)
    else:
        _apply_baseline()
        if isinstance(_pal, (list, tuple)) and _pal:
            matplotlib.rcParams["axes.prop_cycle"] = matplotlib.cycler(color=list(_pal))
        result = None
    if overlay:
        _apply_overlay()
    else:
        _OVERLAY_ACTIVE = False
    return result


save = save_fig  # 简写别名
