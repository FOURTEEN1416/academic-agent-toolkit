#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学术级图表工具库 — 统一风格，供任意驱动 Agent 自由调用。

使用方式：
    from _utils.plot_utils import setup_style, heatmap, forest_plot, trend_plot
    setup_style()  # 初始化学术风格
    heatmap(corr_matrix, output='figures/fig_heatmap.pdf')
"""
import os
import sys
import platform
import numpy as np

# 延迟导入 matplotlib，避免在没有 GUI 的环境报错
_plt = None
_sns = None

def _get_plt():
    global _plt
    if _plt is None:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        _plt = plt
    return _plt

def _get_sns():
    global _sns
    if _sns is None:
        try:
            import seaborn as sns
            _sns = sns
        except ImportError:
            _sns = None
    return _sns


# ============================================================
# 学术配色方案
# ============================================================
PALETTES = {
    # ★ Soft（默认推荐）— 柔和明亮，纯白背景，大面积半透明渐变填充
    # 柔蓝 + 珊瑚粉 + 薄荷绿 + 浅灰 + 淡紫 + 暖杏
    'soft': ['#5B9BD5', '#ED7D7D', '#7BC8A4', '#B0B0B0', '#9B8EC4', '#F4A261'],

    # Tableau 10 — 现代清新，区分度高，适合多组对比
    'tableau': ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC'],

    # NPG / Nature — 鲜明对比，适合生物/化学/自然科学
    'npg': ['#E64B35', '#4DBBD5', '#00A087', '#3C5488', '#F39B7F', '#8491B4', '#91D1C2', '#DC0000', '#7E6148', '#B09C85'],

    # NEJM — 柔和优雅，适合统计/医学类
    'nejm': ['#BC3C29', '#0072B5', '#E18727', '#20854E', '#7876B1', '#6F99AD', '#FFDC91', '#EE4C97'],

    # SciencePlots — 经典学术，适合 IEEE/ACM/工程类论文
    'science': ['#0C5DA5', '#00B945', '#FF9500', '#FF2C00', '#845B97', '#474747', '#9e9e9e'],

    # 色盲友好 (Wong 2011, Nature Methods) — 无障碍首选
    'colorblind': ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#F0E442', '#56B4E9', '#E69F00', '#000000'],

    # 顶刊风格 (Water Research / Nature 级别) — 低饱和莫兰迪色调，SCI 投稿首选
    'journal': ['#4A90B8', '#E8927C', '#7BC8A4', '#B8B8B8', '#F7D097', '#9B8EC4', '#8DBFA3', '#D4A0A0'],

    # ★ Elegant — 柔和通透，清新淡雅，适合统计建模/经管类论文
    # 淡蓝灰 + 暖橙 + 薄荷绿 + 淡紫蓝 + 玫瑰粉 + 暖杏 + 灰蓝 + 淡青
    'elegant': ['#7AAEC8', '#E8945A', '#7BC8A4', '#9B8EC4', '#E0A0A0', '#F0C05A', '#8FAEC0', '#A8C4D8'],

    # ★ Nature — Nature/高影响因子期刊专用，深蓝主色+绿红对比+中性灰
    # 适合 Nature、NeurIPS、ICLR 等顶刊/顶会投稿
    'nature': ['#0F4D92', '#3775BA', '#8BCF8B', '#B64342', '#767676', '#42949E', '#9A4D8E', '#FFD700'],

    # ==== 以下为「数据图随机风格」精选配色库(全部低饱和耐看/期刊级,POC 已验证) ====
    'okabe_ito':    ['#0072B2', '#E69F00', '#009E73', '#CC79A7', '#56B4E9', '#D55E00', '#F0E442'],
    'tol_muted':    ['#4477AA', '#CC6677', '#228833', '#CCBB44', '#66CCEE', '#AA3377', '#999933'],
    'tol_vibrant':  ['#0077BB', '#EE7733', '#009988', '#CC3311', '#33BBEE', '#EE3377', '#5566AA'],
    'nord':         ['#5E81AC', '#BF616A', '#A3BE8C', '#EBCB8B', '#B48EAD', '#88C0D0', '#D08770'],
    'morandi':      ['#8B9DA7', '#B8938A', '#9CA98B', '#C4A69A', '#A6949C', '#7E8A99', '#C9B8A8'],
    'sunburst':     ['#003F5C', '#58508D', '#BC5090', '#FF6361', '#FFA600', '#7A5195', '#EF5675'],
    'ocean':        ['#05668D', '#028090', '#00A896', '#02C39A', '#0A9396', '#3D8DAE', '#94D2BD'],
    'coral':        ['#FF6B6B', '#4ECDC4', '#45B7D1', '#F7A072', '#A06CD5', '#F79256', '#7DCFB6'],
    'spring':       ['#219EBC', '#FB8500', '#6A994E', '#8ECAE6', '#BC4749', '#FFB703', '#023047'],
    'retro':        ['#EA5545', '#EF9B20', '#87BC45', '#27AEEF', '#B33DC6', '#F46A9B', '#BDCF32'],
    'dutch_field':  ['#E60049', '#0BB4FF', '#50E991', '#E6A800', '#9B19F5', '#F58518', '#00BFA0'],
    'wine':         ['#5F0F40', '#9A031E', '#CB793A', '#0F4C5C', '#457B9D', '#7B2D26', '#BC6C25'],
    'pastel':       ['#8AB6D6', '#F6A6B2', '#8FCB9B', '#C3A0D6', '#F9C979', '#7EC4C4', '#E0A0B8'],
    'earth_forest': ['#386641', '#BC4749', '#6A994E', '#A7C957', '#C9A227', '#D4A373', '#7F5539'],
    'teal_orange':  ['#1F6F78', '#FF8C42', '#2A9D8F', '#E76F51', '#457B9D', '#F4A261', '#264653'],
    'candy':        ['#3FA7D6', '#EE6C4D', '#59CD90', '#F4C145', '#C05299', '#4D9DE0', '#E15554'],
    'sage_rose':    ['#84A98C', '#A4243B', '#6B9080', '#C9ADA7', '#52796F', '#D8A48F', '#354F52'],
    'plum_gold':    ['#4B3F72', '#FFC857', '#E9724C', '#255F85', '#C5283D', '#9B5094', '#F2A65A'],
    'cobalt_coral': ['#274690', '#FF7F51', '#1B98E0', '#E8505B', '#47B39C', '#FFD166', '#6A4C93'],
    'moss_clay':    ['#606C38', '#DDA15E', '#BC6C25', '#4A5A2B', '#A68A64', '#7F4F24', '#936639'],
    'flamingo':     ['#3A86FF', '#F72585', '#4CC9F0', '#7209B7', '#4361EE', '#B5179E', '#4895EF'],
    'desert':       ['#E07A5F', '#3D405B', '#81B29A', '#F2CC8F', '#6D597A', '#B56576', '#E56B6F'],
    'peacock':      ['#006D77', '#E29578', '#83C5BE', '#EE9B00', '#CA6702', '#0A9396', '#9B2226'],
    'aurora':       ['#5E81AC', '#A3BE8C', '#B48EAD', '#EBCB8B', '#BF616A', '#88C0D0', '#D08770'],
    'vivid_bold':   ['#E63946', '#457B9D', '#2A9D8F', '#F4A261', '#8338EC', '#3A86FF', '#FB5607'],
    'mint_lav':     ['#4CB5AE', '#B39CD0', '#FF8FA3', '#A8DADC', '#457B9D', '#FCBF49', '#8E7DBE'],
}

# 「随机模式」可抽取的配色池(不含 nature/npg 等有专属逻辑或过于特殊的,只放适合通用随机的)
RANDOM_PALETTE_POOL = [
    'elegant', 'okabe_ito', 'tol_muted', 'tol_vibrant', 'nord', 'morandi', 'sunburst', 'ocean',
    'coral', 'spring', 'retro', 'dutch_field', 'wine', 'soft', 'journal', 'pastel',
    'earth_forest', 'teal_orange', 'candy', 'sage_rose', 'plum_gold', 'cobalt_coral',
    'moss_clay', 'flamingo', 'desert', 'peacock', 'aurora', 'vivid_bold', 'mint_lav',
]

# 默认配色（Elegant — 柔和通透，清新淡雅）
# Stable public containers: ``from plot_utils import PALETTE`` must observe
# later setup calls, without mutating any preset or the caller's color list.
PALETTE = list(PALETTES['elegant'])
PALETTE_LIGHT = []  # initialized after _lighten is defined

COLORS = {
    'primary': '#7AAEC8',     # 淡蓝灰（主色调）
    'secondary': '#E8945A',   # 暖橙（点缀色）
    'accent': '#7BC8A4',      # 薄荷绿
    'gray': '#B8B8B8',
    'light': '#F5F7FA',
    'dark': '#2D2D2D',
    # 语义颜色
    'up': '#7BC8A4',          # 上升/正向 — 薄荷绿
    'down': '#E0A0A0',        # 下降/负向 — 柔玫瑰
    'neutral': '#B8B8B8',     # 中性
    'highlight': '#E8945A',   # 高亮/强调 — 暖橙
    'ref_line': '#AAAAAA',    # 参考线
    'grid': '#E0E0E0',        # 网格线（很淡）
    'text': '#4A4A4A',        # 标注文字
    'bg_box': '#F5F7FA',      # 标注框背景
    'bg_fill': '#C8DFF0',     # 边际/背景填充 — 淡天蓝
    'bg_fill2': '#F0C8C8',    # 第二背景填充 — 淡粉
}


def _fig_seed():
    """确定性种子 = 工作区根目录名的 CRC32(与流程图同源思路)。
    同一篇论文所有图共用同一种子→篇内统一;不同篇各异;重跑不变(可复现)。
    绝不用 random/时间戳。

    ⛔ 种子必须与"脚本从哪个子目录被执行"无关:画图脚本可能从工作区根、
    figures/、code/ 等不同 cwd 运行。若直接用 basename(getcwd()) 当种子,cwd
    一变种子就变——尤其当所有脚本都在 figures/ 里跑时 basename 恒为 'figures',
    导致【所有论文同种子→配色永远同一套】(去指纹形同虚设)。
    因此先从 cwd 向上寻找工作区根标志文件(AGENTS.md 等通用约定)来锚定稳定的工作区名;
    找不到(如裸测试环境)才退回 basename(getcwd()) 旧行为。"""
    import zlib
    name = None
    try:
        d = os.path.abspath(os.getcwd())
        # 向上最多回溯 8 层找含工作区根标志文件的目录 = 工作区根(稳定锚点)
        for _ in range(8):
            if any(os.path.isfile(os.path.join(d, marker))
                   for marker in ('AGENTS.md',)):
                name = os.path.basename(d)
                break
            parent = os.path.dirname(d)
            if parent == d:  # 到达文件系统根,停止
                break
            d = parent
    except Exception:
        name = None
    if not name:
        try:
            name = os.path.basename(os.getcwd()) or 'default'
        except Exception:
            name = 'default'
    return zlib.crc32(name.encode('utf-8', 'replace'))


# 宿主解耦说明（回灌 modex-3 时剥离）：上游版通过读取宿主前端写入工作区根
# CLAUDE.md 的 `<!-- MH_DATA_FIG_* -->` 标记固定配色/版式。工具箱构建不依赖任何
# 宿主配置文件，标记读取器恒返回 None（= 未配置），行为自动退回既有的按工作区
# 种子随机 / 显式传参路径，功能核不受影响。
def _read_data_engine_marker():
    return None


def _read_palette_marker():
    return None


def _read_custom_colors():
    return None


def _read_style_marker():
    return None


# 「高级自定义版式」约束档位 —— 每个维度只给几个安全值(取自 STYLE_FAMILIES 验证过的值域),
# 用户任意组合都不会配出丑图。前端/后端/本文件三处的档位键必须一致。
_STYLE_CUSTOM_DIMS = {
    'frame': ('open', 'journal'),          # 边框:极简左下 / 期刊四面
    'grid': ('none', 'y', 'both'),         # 网格:无 / 横向淡 / 全网格淡
    'lw': ('thin', 'mid', 'thick'),        # 线宽:细 / 中 / 粗
    'font': ('small', 'medium', 'large'),  # 字号:小 / 中 / 大(全局 rcParams,必生效)
    'legend': ('noframe', 'framed'),       # 图例:无框 / 有框
    'bg': ('white', 'graytint'),           # 背景:纯白 / 淡灰底
}


def _read_style_custom_marker():
    return None


# ============================================================
# 「成品风格族」—— 每套是一组经审美验证、彼此自洽的完整版式参数。
# 随机模式按种子从这里【整套】选一个（不再逐旋钮独立乱配 → 杜绝丑组合）。
# 关键：每套都【显式控制刻度四面】，tick_tr=False 时关掉上/右刻度 = 消灭“上右黑点点”。
# ============================================================
STYLE_FAMILIES = {
    'clean_open':     {'spines': ('left', 'bottom'), 'tick_dir': 'out', 'tick_tr': False,
                       'grid': None, 'legend_frame': False, 'patch_edge': 'white',
                       'lw': 1.8, 'ms': 5, 'axis_color': '#666666'},
    'soft_grid':      {'spines': ('left', 'bottom'), 'tick_dir': 'out', 'tick_tr': False,
                       'grid': {'axis': 'y', 'ls': '--', 'alpha': 0.30, 'color': '#CCCCCC'},
                       'legend_frame': False, 'patch_edge': 'white', 'lw': 1.9, 'ms': 5, 'axis_color': '#666666'},
    'framed_journal': {'spines': ('left', 'bottom', 'top', 'right'), 'tick_dir': 'in', 'tick_tr': True,
                       'grid': {'axis': 'both', 'ls': '-', 'alpha': 0.15, 'color': '#DDDDDD'},
                       'legend_frame': True, 'patch_edge': 'white', 'lw': 1.7, 'ms': 4.5, 'axis_color': '#444444'},
    'minimal_bare':   {'spines': ('left', 'bottom'), 'tick_dir': 'out', 'tick_tr': False,
                       'grid': None, 'legend_frame': False, 'patch_edge': 'none',
                       'lw': 2.0, 'ms': 6, 'axis_color': '#888888'},
    'bold_edge':      {'spines': ('left', 'bottom'), 'tick_dir': 'out', 'tick_tr': False,
                       'grid': None, 'legend_frame': False, 'patch_edge': 'white_bold',
                       'lw': 2.1, 'ms': 6, 'axis_color': '#555555'},
    'crisp_dark':     {'spines': ('left', 'bottom', 'top', 'right'), 'tick_dir': 'in', 'tick_tr': True,
                       'grid': None, 'legend_frame': True, 'patch_edge': 'white',
                       'lw': 1.8, 'ms': 5, 'axis_color': '#333333'},
}
_STYLE_FAMILY_NAMES = list(STYLE_FAMILIES.keys())


def _derive_fig_knobs(seed):
    """按种子从 STYLE_FAMILIES 整套选一个（不再逐旋钮独立乱配）。"""
    name = _STYLE_FAMILY_NAMES[(seed // 7) % len(_STYLE_FAMILY_NAMES)]
    fam = dict(STYLE_FAMILIES[name])
    fam['_name'] = name
    return fam


def _knobs_from_custom(spec):
    """把「高级自定义」档位 {frame,grid,lw} 映射成完整 knobs（唯一真相源:
    预生成预览图 与 实际出图 都调本函数，杜绝"预览≠实际"）。
    所有取值来自 STYLE_FAMILIES 验证过的值域，任意组合都自洽好看。
    未开放的维度（描边等）用安全固定值。"""
    _frame = {
        'open':    {'spines': ('left', 'bottom'),               'tick_dir': 'out', 'tick_tr': False,
                    'legend_frame': False, 'axis_color': '#666666'},
        'journal': {'spines': ('left', 'bottom', 'top', 'right'), 'tick_dir': 'in',  'tick_tr': True,
                    'legend_frame': True,  'axis_color': '#444444'},
    }
    _grid = {
        'none': None,
        'y':    {'axis': 'y',    'ls': '--', 'alpha': 0.30, 'color': '#CCCCCC'},
        'both': {'axis': 'both', 'ls': '-',  'alpha': 0.15, 'color': '#DDDDDD'},
    }
    _lw = {'thin': (1.7, 4.5), 'mid': (1.9, 5.0), 'thick': (2.1, 6.0)}
    # 字号:(基准 font.size, label, title, tick) —— 全局 rcParams,必生效
    _font = {'small': (9, 10, 11, 8), 'medium': (11, 12, 13, 10), 'large': (13, 14, 16, 12)}
    _bg = {'white': 'white', 'graytint': '#F7F8FA'}
    # 缺失/非法档位回落到第一档（与 _read_style_custom_marker 的补默认一致）
    f = _frame.get(spec.get('frame'), _frame['open'])
    g = _grid.get(spec.get('grid', 'none'), None) if spec.get('grid') != 'none' else None
    lw, ms = _lw.get(spec.get('lw'), _lw['mid'])
    fs = _font.get(spec.get('font'), _font['medium'])
    facecolor = _bg.get(spec.get('bg'), 'white')
    # legend 维显式选了就覆盖 frame 带的默认；没选则跟随 frame
    _leg = spec.get('legend')
    legend_frame = (_leg == 'framed') if _leg in ('framed', 'noframe') else f['legend_frame']
    return {
        'spines': f['spines'], 'tick_dir': f['tick_dir'], 'tick_tr': f['tick_tr'],
        'legend_frame': legend_frame, 'axis_color': f['axis_color'],
        'grid': g, 'patch_edge': 'white', 'lw': lw, 'ms': ms,
        'font_size': fs, 'facecolor': facecolor,   # ★ 新维(setup_style 用 .get 消费,预设/随机路径无此键不受影响)
        '_name': f"custom({spec.get('frame','open')}/{spec.get('grid','none')}/{spec.get('lw','mid')}"
                 f"/{spec.get('font','medium')}/{spec.get('legend','-')}/{spec.get('bg','white')})",
    }


# ===== Nature / NPG 版式：字号随画布宽反解（★ 不写死）=====
# ⛔⛔ 为什么必须反解，不能写死 16pt：
#   旧代码写 `'font.size': 16  # Nature 标准：正文 16pt` —— 16 不是 Nature 规范值，
#   而是【8 英寸画布 + 缩到 Nature 单栏 89mm】反推出来的：7 × 8 ÷ 3.5 = 16.0。
#   它绑死两个前提，而本管线两个都不成立：
#     · 画布：真实脚本用 4.3–6.2 寸（不是 8 寸）
#     · 输出：Word 插图上限 5.5 寸（不是 89mm=3.5 寸）
#   于是 16pt 落地后是 14–16pt，是 Nature 规范 7pt 的【两倍】。
#   AI 发现放不下，就在脚本里手写了 103 处 fontsize=（6.6/7.0/7.2/7.4/8.0/8.5/11…
#   一套图 13 种字号混用，6 处低于印刷下限）—— 这才是"图看起来乱"的真源头。
#
# 正解：让落地字号恒定，画时字号跟着画布走。
#   落地宽 = min(PAGE_MAX_W_IN, 画布宽)（比 5.5 寸窄的图 Word 不会放大）
#   画时字号 = 目标落地字号 × 画布宽 ÷ 落地宽
PAGE_MAX_W_IN = 5.5       # = md_to_docx 的 _DEFAULT_IMAGE_MAX_W_IN
# 印刷可读下限。⛔ 与 tools/screenshot_capture.py 的 MIN_FONT_PT 保持一致，
#   改一处必须改另一处（那边是出图后的静态闸，这里是画图时的自检）。
MIN_LEGIBLE_PT = 8.0
# 目标落地字号 8.25pt，给最终缩放和 PDF 字号取整留 0.25pt 余量。
# 密集图若因 8pt 发生碰撞，必须扩画布、减少重复标注、把图例移到专用区域或拆图；
# 不能以牺牲印刷可读性换取“无碰撞”。
NATURE_TARGET_PT = 8.25
# 参考画布宽：用于把其余版式量（轴线/刻度/marker）按同一系数等比缩放，
# 使整体观感与旧的「8 寸 + 16pt」设计保持一致的比例关系。
_NATURE_REF_W = 8.0
_NATURE_REF_PT = 16.0
# 旧设计在 8 寸下的各量（作为等比缩放的基准）
_NATURE_BASE = {
    'font.size': 16.0, 'axes.labelsize': 16.0, 'axes.titlesize': 18.0,
    'xtick.labelsize': 14.0, 'ytick.labelsize': 14.0, 'legend.fontsize': 13.0,
    'axes.linewidth': 2.5, 'lines.linewidth': 2.5, 'lines.markersize': 8.0,
    'xtick.major.width': 2.0, 'ytick.major.width': 2.0,
    'xtick.major.size': 6.0, 'ytick.major.size': 6.0,
}


# LaTeX 竞赛链路的上页显示宽：正文宽 6.5in × 按长宽比分档的系数。
# ⛔ 必须与 skills/shared-scripts/fig_include_size.py 的 _BUCKETS 保持一致，
#   改一处必须改另一处。docx 链路是固定 5.5in 上限（md_to_docx），
#   两条链路取【更窄的那个】—— 更窄 = 缩得更狠 = 画时字号要更大，取小才安全。
_LATEX_TEXTWIDTH_IN = 6.5
# ⛔ 2026-08-26 随 fig_include_size.py 一起调大（原 0.85/0.70/0.50/0.42）。
#   有 fig_bucket_doc_sync_check.py 盯着这两处，不一致会 FAIL。
_LATEX_BUCKETS = ((0.80, 0.90), (1.20, 0.80), (1.60, 0.60))
_LATEX_TALL_COEF = 0.46


def _display_width_in(w, h=None):
    """图插进论文后的实际显示宽度（英寸）。h 给了就按长宽比分档。"""
    disp = min(PAGE_MAX_W_IN, w)          # docx 链路：5.5in 上限，窄图不放大
    if h:
        r = h / w
        coef = _LATEX_TALL_COEF
        for hi, c in _LATEX_BUCKETS:
            if r <= hi:
                coef = c
                break
        latex_disp = min(_LATEX_TEXTWIDTH_IN * coef, w)
        disp = min(disp, latex_disp)      # 取更窄的一档
    return max(disp, 0.5)


def set_paper_placement(fig, width_fraction=None, *, textwidth_in=6.5,
                        height_fraction=0.80, textheight_in=9.7,
                        min_font_pt=NATURE_TARGET_PT):
    """Record how ``fig`` will be placed in the final paper.

    The save hook uses this contract to work backwards from the requested
    printed size.  ``width_fraction=None`` keeps the same aspect-ratio buckets
    used by ``fig_include_size.py``; pass the real LaTeX width fraction when it
    is already known.  Word's 5.5 inch image cap is still applied, so one figure
    is safe for both PDF and DOCX output.

    This function deliberately records metadata only.  It does not stretch the
    canvas or override a user's palette/layout choices.
    """
    import math

    def _finite(value, fallback, lo, hi):
        try:
            result = float(value)
        except (TypeError, ValueError):
            return fallback
        return result if math.isfinite(result) and lo <= result <= hi else fallback

    if width_fraction is not None:
        width_fraction = _finite(width_fraction, None, 0.20, 1.0)
        if width_fraction is None:
            raise ValueError("width_fraction must be within [0.20, 1.0]")
    fig._mh_paper_placement = {
        'width_fraction': width_fraction,
        'textwidth_in': _finite(textwidth_in, 6.5, 2.0, 20.0),
        'height_fraction': _finite(height_fraction, 0.80, 0.20, 1.0),
        'textheight_in': _finite(textheight_in, 9.7, 2.0, 30.0),
        'min_font_pt': _finite(min_font_pt, NATURE_TARGET_PT, MIN_LEGIBLE_PT, 20.0),
    }
    return fig


def _paper_display_width_in(fig):
    """Conservative final display width for PDF and DOCX."""
    import math

    try:
        width = float(fig.get_figwidth())
        height = float(fig.get_figheight())
    except Exception:
        return PAGE_MAX_W_IN
    if not (math.isfinite(width) and math.isfinite(height) and width > 0 and height > 0):
        return PAGE_MAX_W_IN
    spec = getattr(fig, '_mh_paper_placement', None) or {}
    fraction = spec.get('width_fraction')
    if fraction is None:
        return _display_width_in(width, height)
    aspect = height / width
    latex_width = float(spec.get('textwidth_in', _LATEX_TEXTWIDTH_IN)) * float(fraction)
    height_limited = (
        float(spec.get('textheight_in', 9.7))
        * float(spec.get('height_fraction', 0.80)) / max(aspect, 1e-9)
    )
    return max(0.5, min(PAGE_MAX_W_IN, width, latex_width, height_limited))


# ═══ Nature 配色同族微调（去指纹）══════════════════════════════════════════
# 为什么需要：两个队都选 Nature 风格时，出图会一模一样 → 可被比对识别。
#   默认配色走 RANDOM_PALETTE_POOL 换整套，但 Nature 不能那么干 ——
#   它那 8 色带语义（蓝=hero method、绿=正向、红=baseline），换套/轮转就语义反了，
#   而且选 Nature 的人要的就是那个蓝。所以改为【同色系内微调】。
#
# ⛔ 必须同族共移，不能逐色独立抖动。实测 15 色 × 7 种子：
#     逐色独立 → 相邻同族色距离只剩 26-51%（blue_main 与 blue_secondary 挤到一起）
#     同族共移 → 保留 89-92%（族内相对关系几乎不变）
#   一族共用一个 (Δh, Δs, Δl)，族内所有色同步平移。
_NATURE_SEMANTIC = {
    'blue_main': '#0F4D92', 'blue_secondary': '#3775BA',
    'green_1': '#DDF3DE', 'green_2': '#AADCA9', 'green_3': '#8BCF8B',
    'red_1': '#F6CFCB', 'red_2': '#E9A6A1', 'red_strong': '#B64342',
    'neutral_light': '#CFCECE', 'neutral_mid': '#767676',
    'neutral_dark': '#4D4D4D', 'neutral_black': '#272727',
    'gold': '#FFD700', 'teal': '#42949E', 'violet': '#9A4D8E',
}
_NATURE_FAMILY = {
    'blue':    ('blue_main', 'blue_secondary'),
    'green':   ('green_1', 'green_2', 'green_3'),
    'red':     ('red_1', 'red_2', 'red_strong'),
    'neutral': ('neutral_light', 'neutral_mid', 'neutral_dark', 'neutral_black'),
    'gold':    ('gold',),
    'teal':    ('teal',),
    'violet':  ('violet',),
}
# 墨色：画线/描边/文字用 —— 对白底必须够对比
_NATURE_INK = ('blue_main', 'blue_secondary', 'red_strong', 'neutral_mid',
               'neutral_dark', 'neutral_black', 'teal', 'violet')
# 填充色：只做面积 —— 本就该浅，不要求高对比，但不许窜进墨色区间
_NATURE_FILL = ('green_1', 'green_2', 'green_3', 'red_1', 'red_2',
                'neutral_light', 'gold')
# 微调幅度：饱和（乘法系数）与明度（加法）的全局上限。
_NATURE_JITTER = (0.040, 0.16, 0.075)      # (Δh 默认, Δs, Δl)

# ⛔⛔ 色相预算【按族分配】，不能一个全局值套所有色 ——
#   各色名的"合法色相区间"宽度差好几倍，一个全局幅度必然是"就着最窄的那个定"，
#   结果宽区间的色白白浪费可变空间（用户反馈"颜色没什么变化"就是这么来的）。
#   实测瓶颈是 gold：合法区间只有 40-60°（金黄很窄，一动就变橙或变柠檬），
#   而蓝有 195-235°、绿有 85-155°。按各族区间宽度的 ~35% 分配 ± 预算：
_NATURE_HUE_BUDGET = {
    'blue':    0.039,      # 区间 40° → ±14°
    'green':   0.069,      # 区间 70° → ±25°
    'red':     0.044,      # 区间 45°（跨 0°）→ ±16°
    'teal':    0.033,      # 区间 35° → ±12°
    'violet':  0.047,      # 区间 50° → ±17°
    'gold':    0.017,      # 区间 20° → ±6°（最窄，必须保守）
    'neutral': 0.0,        # 灰不动色相
}
_NATURE_GRAY_SAT = 0.12                    # 饱和低于此判为中性色（只动明度）
_NATURE_INK_MIN_C = 3.2                    # 墨色对白底最低对比（WCAG 图形线 3.0 + 余量）
_NATURE_FILL_MAX_C = 2.6                   # 填充色最高对比（原始最高 red_2=2.01）
# 留出 PDF 8-bit 颜色量化余量：内存里恰好 4.500 的颜色写入 PDF 后可能变成
# 4.497，进而被外部 4.5/3.0 质量门误判。
_TEXT_CONTRAST_MIN = 4.6                   # 正常字号文字（外部门槛 4.5）
_GRAPHIC_CONTRAST_MIN = 3.1                # 数据线/轮廓（外部门槛 3.0）


def _hex2rgb01(h):
    h = str(h).lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _rgb01_2hex(rgb):
    return '#%02X%02X%02X' % tuple(
        max(0, min(255, int(round(c * 255)))) for c in rgb)


def _rel_luminance(rgb):
    def _f(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (_f(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_on_white(rgb):
    """对白底的 WCAG 对比度（1.0 = 与白等同，21 = 纯黑）。"""
    return 1.05 / (_rel_luminance(rgb) + 0.05)


def _clamp_contrast_hex(hex_c, lo=None, hi=None, steps=48):
    """把颜色的明度往暗/亮推，直到对比度落进 [lo, hi]。

    ⛔ 这是【不变量兜底】，比"把抖动幅度调到最坏色也不越界"更稳：
       以后有人改 nature 配色表，本函数仍然保证墨色够对比、填充够浅，
       不依赖"当前最弱墨色是 teal"这个会过时的事实。
    """
    import colorsys
    h, l, s = colorsys.rgb_to_hls(*_hex2rgb01(hex_c))
    for _ in range(steps):
        c = _contrast_on_white(colorsys.hls_to_rgb(h, l, s))
        if lo is not None and c < lo:
            if l <= 0.02:
                break
            l = max(0.02, l - 0.012)      # 压暗 → 提对比
        elif hi is not None and c > hi:
            if l >= 0.98:
                break
            l = min(0.98, l + 0.012)      # 提亮 → 降对比
        else:
            break
    return _rgb01_2hex(colorsys.hls_to_rgb(h, l, s))


def _family_offset(seed, salt):
    """确定性 [-1, 1] 偏移系数。⛔ 绝不用 random/时间戳 —— 必须可复现。"""
    import zlib
    v = zlib.crc32(('%d|%s' % (seed, salt)).encode('utf-8')) % 2001
    return (v - 1000) / 1000.0


def _nature_project_colors():
    """Explicit project colors override Nature hues, not its layout."""
    marker = _read_palette_marker()
    colors = (_read_custom_colors() if marker == 'custom' else
              PALETTES.get(marker) if marker and marker not in ('random', 'auto', 'nature') else None)
    if not colors:
        return None
    from matplotlib.colors import is_color_like, to_hex
    if not all(is_color_like(c) for c in colors):
        raise ValueError('project palette contains an invalid color')
    return [to_hex(c).upper() for c in colors]


def nature_palette(seed=None):
    """返回本工作区的 Nature 语义配色字典（15 键，已按工作区种子同族微调）。

    ⛔ Nature 出图脚本请调本函数取色，【不要】把 hex 抄成字面量 ——
       抄了就拿不到微调，两个工作区的图会一模一样（可被比对识别）。

    用法：
        from _utils.plot_utils import nature_palette
        C = nature_palette()
        ax.plot(x, y, color=C['blue_main'])

    Args:
        seed: 显式种子（仅测试用）。None = 用工作区名的 CRC32（同篇统一、重跑不变）。

    Returns:
        dict: 键与 paper-figure-nature/SKILL.md 的 PALETTE_NATURE 完全一致，值已微调。
    """
    import colorsys
    selected = _nature_project_colors()
    if selected:
        # Keep legacy semantic keys without reintroducing colors in grayscale.
        roles = ('blue_main', 'blue_secondary', 'green_3', 'red_strong',
                 'neutral_mid', 'teal', 'violet', 'gold')
        out = {key: selected[i % len(selected)] for i, key in enumerate(roles)}
        for key in _NATURE_INK:
            if key in out:
                out[key] = _clamp_contrast_hex(out[key], lo=_NATURE_INK_MIN_C)
        for prefix, base in (('green', out['green_3']), ('red', out['red_strong'])):
            out[prefix + '_1'] = _lighten(base, .8)
            out[prefix + '_2'] = _lighten(base, .5)
        out.update(neutral_light='#DDDDDD', neutral_dark='#444444', neutral_black='#222222')
        return out
    if seed is None:
        seed = _fig_seed()
    _dh_default, ds, dl = _NATURE_JITTER
    out = {}
    for fam, keys in _NATURE_FAMILY.items():
        # ⛔ 色相预算按族取，不用全局值（见 _NATURE_HUE_BUDGET 的长注释）
        dh = _NATURE_HUE_BUDGET.get(fam, _dh_default)
        oh = _family_offset(seed, fam + '|h')
        os_ = _family_offset(seed, fam + '|s')
        ol = _family_offset(seed, fam + '|l')
        for k in keys:
            h, l, s = colorsys.rgb_to_hls(*_hex2rgb01(_NATURE_SEMANTIC[k]))
            if s >= _NATURE_GRAY_SAT:
                # ⛔ 中性色（灰）不动色相/饱和 —— 动了会把灰染上颜色
                h = (h + oh * dh) % 1.0
                # ⛔ 饱和度用【乘法】不能用加法：加法对 S=0.62 与 S=0.47 两色的
                #   相对影响不同，会压缩它们的色度差 —— 实测 40 种子下
                #   red_2/red_strong 的感知距离掉到 78%（同族等量 HLS 偏移只保住
                #   HLS 距离，保不住 Lab 距离，这是我最初的设计假设偏差）。
                #   乘法保持比例结构，族内色度关系才真正不变。
                s = max(0.05, min(1.0, s * (1.0 + os_ * ds)))
            l = max(0.04, min(0.96, l + ol * dl))
            c = _rgb01_2hex(colorsys.hls_to_rgb(h, l, s))
            if k in _NATURE_INK:
                c = _clamp_contrast_hex(c, lo=_NATURE_INK_MIN_C)
            elif k in _NATURE_FILL:
                c = _clamp_contrast_hex(c, hi=_NATURE_FILL_MAX_C)
            out[k] = c
    return out


# Nature 图可用的 marker 序列（散点/折线按需取用）。
# ⛔ 绝不要把 marker 塞进 axes.prop_cycle：`ax.plot(x, y)` 画 500 点平滑曲线时
#   会每个点打一个 marker，糊成一片。marker 只能由脚本【显式】选用。
NATURE_MARKERS = ('o', 's', '^', 'D', 'v', 'P', 'X', '*')


def nature_markers(seed=None):
    """按工作区种子轮转 marker 顺序（去指纹的一维，语义无关）。"""
    if seed is None:
        seed = _fig_seed()
    n = len(NATURE_MARKERS)
    r = (seed // 11) % n
    return NATURE_MARKERS[r:] + NATURE_MARKERS[:r]


# Nature 版式可随机的维度（其余一律钉死，见下面注释）
_NATURE_GRID_OPTS = (
    None,                                                   # 无网格
    {'axis': 'y', 'ls': '--', 'alpha': 0.25, 'color': '#D8D8D8'},   # 淡 y 网格
)
_NATURE_LW_OPTS = (0.85, 1.00, 1.15)        # 线宽/marker 尺寸的等比系数
_NATURE_LEGEND_LOC = ('best', 'upper left', 'upper right', 'lower right')


def _nature_knobs(seed, custom=None):
    """Nature 专用版式旋钮（只含【合法】维度）。

    ⛔ 为什么不复用 STYLE_FAMILIES：那 6 个族里 framed_journal 与 crisp_dark 是
       四边框 + 刻度朝内，违反 Nature 规范（左下两边框 + 刻度朝外）。
       2/6 概率会产出「选了 Nature 却不是 Nature」的图。

    钉死不随机（Nature 的身份）：
      spines=左下 / tick_dir=out / legend 无框 / 白底 / 字号（按画布反解，
      随机会破 8pt 印刷线）

    custom: {'grid': 'none'|'y'|'both', 'lw': 'thin'|'mid'|'thick'} —— 用户手选，
            仅这两维合法；非法维（frame/legend/bg/font）由调用方过滤掉。
    """
    grid = _NATURE_GRID_OPTS[(seed // 3) % len(_NATURE_GRID_OPTS)]
    lw_k = _NATURE_LW_OPTS[(seed // 5) % len(_NATURE_LW_OPTS)]
    # Legend position is driven by geometry, never by the style seed. This is
    # only an initial matplotlib hint; the save guard still checks real space.
    leg = 'best'
    if custom:
        _g = custom.get('grid')
        if _g == 'none':
            grid = None
        elif _g == 'y':
            grid = dict(_NATURE_GRID_OPTS[1])
        elif _g == 'both':
            grid = {'axis': 'both', 'ls': '-', 'alpha': 0.15, 'color': '#E2E2E2'}
        _l = custom.get('lw')
        if _l in ('thin', 'mid', 'thick'):
            lw_k = {'thin': 0.85, 'mid': 1.00, 'thick': 1.15}[_l]
    return {'grid': grid, 'lw_k': lw_k, 'legend_loc': leg}


def nature_font_pt(fig_w_in, fig_h_in=None):
    """按画布尺寸反解 nature 基准字号，使落地后恒为 NATURE_TARGET_PT。

    ⛔ 窄画布不会被放大，所以字号保持 = 目标值，不再往下缩 ——
       否则落地就低于 8pt 印刷线（实测按 1.32×宽 的线性公式在 4.3 寸画布上
       只给 5.7pt，全图大量文字不可读）。
    ⛔ 传高度时按长宽比分档算显示宽：竞赛 LaTeX 链路对近方图只给 4.55in、
       瘦高图只给 2.73in，比 docx 的 5.5in 窄得多 —— 不分档的话方图/竖图
       会因为缩得更狠而字变小。
    """
    import math as _m
    try:
        w = float(fig_w_in)
    except (TypeError, ValueError):
        w = _NATURE_REF_W
    # ⛔ 必须用 isfinite 兜住 inf：单看 `w > 0.5` 时 inf 能通过，
    #   算出来的字号就是 inf，后面 set_fontsize(inf) 会让 matplotlib 抛异常
    #   或画出空白图（实测边界用例抓到）。NaN 同理（NaN > 0.5 为 False，已被拦）。
    if not (_m.isfinite(w) and 0.5 < w < 1000):
        w = _NATURE_REF_W
    h = None
    try:
        if fig_h_in is not None:
            hh = float(fig_h_in)
            if _m.isfinite(hh) and 0.5 < hh < 1000:
                h = hh
    except (TypeError, ValueError):
        h = None
    return NATURE_TARGET_PT * w / _display_width_in(w, h)


# 哪些键是"字号"（地板必须是印刷可读线，不能跟线宽/marker 混用一个地板）
_NATURE_FONT_KEYS = frozenset((
    'font.size', 'axes.labelsize', 'axes.titlesize',
    'xtick.labelsize', 'ytick.labelsize', 'legend.fontsize'))


def nature_rcparams(fig_w_in, fig_h_in=None):
    """返回该画布宽下的整套 nature 版式量（字号 + 线宽 + 刻度 + marker）。

    ⛔⛔ 字号档位的地板必须是 MIN_LEGIBLE_PT（8.0pt），⛔ 不能图省事写 6.0：
       等比缩放会把小档位压穿 —— 8 寸→4.3 寸时系数 k=0.47，
       xtick 14×0.47=6.56pt、legend 13×0.47=6.09pt 全部跌破印刷线。
       实测写 6.0 地板时，真实工作区全图 <8pt 的文字会显著增加，
       最小 6.0pt —— 等于把"字太大"换成了"字太小看不清"，白改。
       钉到 7.0 后层级会被压扁（基准 7.5 / 刻度 7.0 / 图例 7.0 挤在一起），
       这是窄画布的必然代价：想保住可读性就没有拉开层级的空间。
    """
    pt = nature_font_pt(fig_w_in, fig_h_in)
    k = pt / _NATURE_REF_PT          # 相对旧设计的等比系数
    out = {}
    for key, base in _NATURE_BASE.items():
        v = base * k
        if key in _NATURE_FONT_KEYS:
            v = max(MIN_LEGIBLE_PT, v)
        elif key.endswith(('linewidth', 'width')):
            v = max(0.6, v)          # 线太细在 PDF 里会消失
        elif key.endswith('size') and 'major' in key:
            v = max(2.0, v)
        elif key == 'lines.markersize':
            v = max(3.0, v)
        out[key] = round(v, 2)
    return out


def _apply_nature_scale(fig_w_in, fig_h_in=None):
    """把反解出的 nature 版式写进 rcParams。返回实际用的基准字号。

    ⛔ matplotlib 必须【函数内导入】：本模块用惰性导入（见 _get_plt），
       模块级没有 matplotlib 这个名字，写在外面会 NameError。
    """
    import matplotlib
    p = nature_rcparams(fig_w_in, fig_h_in)
    matplotlib.rcParams.update(p)
    return p['font.size']


def setup_style(palette='auto'):
    """初始化学术论文图表风格。调用一次即可。

    Args:
        palette: 配色方案名称。可选值：
            'auto' — 工作区稳定默认配色（有项目配置时优先服从配置）
            'elegant' — ★ 默认推荐：薄荷绿+淡紫+暖杏黄，柔和通透
            'journal' — 顶刊风格，低饱和莫兰迪色调，SCI 投稿首选
            'soft' — 柔蓝+珊瑚粉+薄荷绿+浅灰+淡紫+暖杏
            'tableau' — Tableau 10 现代清新，适合多组对比
            'npg' — Nature 鲜明对比，适合自然科学
            'nejm' — 柔和优雅，适合统计/医学
            'science' — SciencePlots 经典，适合工程类
            'colorblind' — 色盲友好（备选）
            或直接传一个颜色列表 ['#xxx', '#yyy', ...]
    """
    plt = _get_plt()
    import matplotlib
    sns = _get_sns()

    # Project data choices outrank generated script defaults, including explicit
    # gray lists. Do not infer a data choice from any host diagram-style marker.
    # Unconfigured standalone scripts retain the original explicit-palette API.
    _engine = _read_data_engine_marker()
    _selected = _read_palette_marker()
    if _engine == 'nature':
        palette = 'nature'
    elif _engine == 'default':
        palette = 'auto'
    elif _selected in PALETTES or _selected in ('custom', 'random', 'auto'):
        if not isinstance(palette, str) or palette not in ('nature', 'npg'):
            palette = 'auto'

    # ★ 随机模式判定：palette 为 'auto'/None 时启用种子随机（去指纹核心）；
    #   显式传具体配色名（如 'nature'）或颜色列表 → 完全按指定，不随机（向后兼容）。
    _random_mode = (palette == 'auto' or palette is None)
    _seed = _fig_seed() if _random_mode else 0
    if _random_mode:
        # 版式优先级:①高级自定义档位 > ②手选固定风格族 > ③按种子随机(去指纹默认)。
        # 只固定"版式"这一维,配色/字体仍各自独立随机,最大保留篇间自然差异。
        _custom_spec = _read_style_custom_marker()
        _style_pick = _read_style_marker()
        if _custom_spec:
            _knobs = _knobs_from_custom(_custom_spec)
        elif _style_pick:
            _knobs = dict(STYLE_FAMILIES[_style_pick])
            _knobs['_name'] = _style_pick
        else:
            _knobs = _derive_fig_knobs(_seed)
    else:
        _knobs = None

    # 选择配色
    if isinstance(palette, list):
        colors = list(palette)
        if not colors:
            raise ValueError('palette must contain at least one color')
    elif _random_mode:
        _marker = _read_palette_marker()   # 前端手选:配色名 / 'custom' / 'random' / None
        _custom = _read_custom_colors() if _marker == 'custom' else None
        if _custom:
            colors = list(_custom)         # 用户自定义取色 → 直接用（不轮转，尊重用户排序）
        elif _marker and _marker in PALETTES and _marker != 'random':
            _pal_name = _marker            # 用户指定预设 → 配色固定（字体/版式仍按种子随机）
            colors = list(PALETTES[_pal_name])
            _rot = (_seed // 3) % len(colors)
            colors = colors[_rot:] + colors[:_rot]
        else:
            _pal_name = RANDOM_PALETTE_POOL[_seed % len(RANDOM_PALETTE_POOL)]  # 种子选一套
            colors = list(PALETTES[_pal_name])
            _rot = (_seed // 3) % len(colors)  # 同套配色也按种子轮转主色顺序，进一步去重
            colors = colors[_rot:] + colors[:_rot]
    elif palette in PALETTES:
        colors = PALETTES[palette]
    else:
        colors = PALETTES['journal']

    # 更新全局 PALETTE 供其他函数使用
    global PALETTE, PALETTE_LIGHT, COLORS
    from matplotlib.colors import is_color_like, to_hex
    if not all(is_color_like(c) for c in colors):
        raise ValueError('palette contains an invalid color')
    # The downstream luminance helpers operate on opaque RGB hex values.
    # Normalize valid named/RGB colors before mutating exported shared state.
    colors = [to_hex(c).upper() for c in colors]
    PALETTE[:] = colors
    PALETTE_LIGHT[:] = [_lighten(c, 0.4) for c in colors]
    COLORS['primary'] = colors[0]
    COLORS['secondary'] = colors[1] if len(colors) > 1 else colors[0]
    COLORS['accent'] = colors[2] if len(colors) > 2 else colors[0]
    # 语义颜色跟随配色方案
    # ⛔ 语义色经常被脚本直接拿去画阈值线和写注释，不能让浅灰/薄荷绿轮转到
    #    这些角色后在白底上消失。填充仍用原始 PALETTE/PALETTE_LIGHT，语义墨色
    #    只做同色相压暗，既保留用户色系，也守住非文本图形 3:1 的可读线。
    COLORS['primary'] = _clamp_contrast_hex(COLORS['primary'], lo=_GRAPHIC_CONTRAST_MIN)
    COLORS['secondary'] = _clamp_contrast_hex(COLORS['secondary'], lo=_GRAPHIC_CONTRAST_MIN)
    COLORS['accent'] = _clamp_contrast_hex(COLORS['accent'], lo=_GRAPHIC_CONTRAST_MIN)
    COLORS['up'] = _clamp_contrast_hex(
        colors[2] if len(colors) > 2 else colors[0], lo=_GRAPHIC_CONTRAST_MIN)
    COLORS['down'] = _clamp_contrast_hex(
        colors[1] if len(colors) > 1 else colors[0], lo=_GRAPHIC_CONTRAST_MIN)
    COLORS['highlight'] = _clamp_contrast_hex(
        colors[4] if len(colors) > 4 else colors[0], lo=_GRAPHIC_CONTRAST_MIN)

    # SciencePlots is optional. Never install packages inside a figure run.
    # ★ 随机模式【跳过】SciencePlots：它默认 xtick.top/ytick.right + 朝内刻度（=上/右黑点点根源），
    #   且会整体覆盖我们的风格族样式。随机模式下版式完全交给 STYLE_FAMILIES 控制。
    #   非随机（显式指定配色，如 nature）保持原有 SciencePlots 行为，向后兼容。
    _has_scienceplots = False
    if not _random_mode:
        try:
            import scienceplots
            _has_scienceplots = True
        except ImportError:
            # Shared rcParams below provide the publication style and guards
            # without network access or a potentially unbounded package fetch.
            pass
        if _has_scienceplots:
            try:
                plt.style.use(['science', 'no-latex'])
            except OSError:
                _has_scienceplots = False

    # ★ SciencePlots 会设置很小的 figure.figsize 和紧凑的 subplot margins
    # 这里强制重置，防止用户手动指定的 figsize 被 subplot 参数压缩子图
    if _has_scienceplots:
        matplotlib.rcParams.update({
            'figure.figsize': (8, 5),           # 恢复合理默认尺寸
            'figure.subplot.left': 0.1,
            'figure.subplot.right': 0.95,
            'figure.subplot.top': 0.92,
            'figure.subplot.bottom': 0.12,
            'figure.subplot.hspace': 0.3,
            'figure.subplot.wspace': 0.3,
            'figure.constrained_layout.use': False,  # 避免与 tight_layout 冲突
        })

    # ★ 关闭 savefig.bbox='tight' — 无条件生效（不管 SciencePlots 装没装）
    # 否则 ax.text(transAxes, y<0 or y>1) 这种 axes 外标注会让 tight 包围盒爆炸，
    # PDF mediabox 被撑到几十英寸高 → PNG 转换后变成"1496×23966"超长条
    matplotlib.rcParams['savefig.bbox'] = 'standard'
    matplotlib.rcParams['savefig.pad_inches'] = 0.1

    # 用 seaborn 主题（如果可用且没有 SciencePlots）
    if sns and not _has_scienceplots:
        sns.set_theme(style='ticks', font_scale=1.0, rc={
            'axes.edgecolor': '#333333',
            'axes.linewidth': 0.8,
        })
    if sns:
        sns.set_palette(colors)

    # 中文字体（带可用性检测，避免小方框□）
    from matplotlib.font_manager import fontManager
    available_fonts = {f.name for f in fontManager.ttflist}

    if platform.system() == 'Windows':
        zh_candidates = ['Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi', 'FangSong']
    elif platform.system() == 'Darwin':
        zh_candidates = ['PingFang SC', 'Heiti SC', 'STHeiti', 'STSong', 'Arial Unicode MS']
    else:
        zh_candidates = ['Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei',
                         'Droid Sans Fallback', 'SimHei', 'AR PL UMing CN']

    zh_fonts = [f for f in zh_candidates if f in available_fonts]

    # ★ 随机模式：从已装中文字体池里按种子选一个当首选（只在已装的里选=零方框风险）
    if _random_mode and zh_fonts:
        # Prefer academic sans/serif faces; retain calligraphic faces only as
        # missing-glyph fallbacks rather than randomly using them for numerals.
        _academic = [f for f in zh_fonts if f not in ('KaiTi', 'FangSong', 'STKaiti')] or zh_fonts
        _pick = _academic[(_seed // 5) % len(_academic)]
        zh_fonts = [_pick] + [f for f in zh_fonts if f != _pick]

    if not zh_fonts:
        # 没有任何中文字体——尝试加载内置字体文件
        _bundled_font = None
        for search_dir in ['_utils', 'skills/shared-scripts', '../skills/shared-scripts']:
            font_path = os.path.join(search_dir, 'NotoSansSC-Regular.ttf')
            if os.path.isfile(font_path):
                _bundled_font = os.path.abspath(font_path)
                break
        if _bundled_font:
            from matplotlib.font_manager import FontProperties
            fontManager.addfont(_bundled_font)
            fp = FontProperties(fname=_bundled_font)
            zh_fonts = [fp.get_name()]
            print(f"Using bundled Chinese font: {_bundled_font}")
        elif platform.system() == 'Linux':
            # Linux 上尝试自动安装
            try:
                import subprocess
                subprocess.run(['apt-get', 'install', '-y', 'fonts-noto-cjk-extra'],
                               capture_output=True, timeout=30)
                fontManager.__init__()
                available_fonts = {f.name for f in fontManager.ttflist}
                zh_fonts = [f for f in zh_candidates if f in available_fonts]
            except Exception:
                pass
        if not zh_fonts:
            print("WARNING: No Chinese fonts found — Chinese text will show as □")
            print("  Fix: place NotoSansSC-Regular.ttf in skills/shared-scripts/")
            print("  Or install: Windows=SimHei, Linux=fonts-noto-cjk-extra, macOS=built-in")
            zh_fonts = ['DejaVu Sans']

    matplotlib.rcParams.update({
        'font.size': 11,
        'font.family': 'sans-serif',
        'font.sans-serif': zh_fonts + ['Arial', 'Helvetica', 'DejaVu Sans'],
        'axes.unicode_minus': False,
        'axes.labelsize': 12,
        'axes.titlesize': 13,
        'axes.linewidth': 0.8,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'legend.frameon': False,
        'figure.dpi': 300,
        'savefig.dpi': 350,
        'savefig.bbox': 'standard',       # ★ 不用 'tight' — 否则 axes 外文字会撑爆 mediabox
        'savefig.pad_inches': 0.1,        # ★ 配合 standard，留窄边距
        'axes.grid': False,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.facecolor': 'white',
        'figure.facecolor': 'white',
        'text.usetex': False,
        'mathtext.fontset': 'stix',
        'lines.linewidth': 1.8,
        'lines.markersize': 6,
        'patch.edgecolor': 'white',       # 饼图/柱状图块之间白色分隔线
        'patch.linewidth': 1.0,
    })

    # 设置颜色循环 — 这是关键，防止 matplotlib 用默认丑蓝色
    matplotlib.rcParams['axes.prop_cycle'] = matplotlib.cycler(color=colors)

    # ★ 随机模式：按【成品风格族】整套应用版式（自洽、好看；显式控制刻度四面 = 消灭上右黑点）
    if _random_mode and _knobs:
        _f = _knobs
        _ac = _f['axis_color']
        _sp = _f['spines']
        _pe = _f['patch_edge']
        _grid = _f['grid']
        matplotlib.rcParams.update({
            'legend.frameon': bool(_f['legend_frame']),
            'lines.linewidth': _f['lw'],
            'lines.markersize': _f['ms'],
            # 边框：只显示 spines 里列出的面
            'axes.spines.left': ('left' in _sp),
            'axes.spines.bottom': ('bottom' in _sp),
            'axes.spines.top': ('top' in _sp),
            'axes.spines.right': ('right' in _sp),
            'axes.edgecolor': _ac,
            # 刻度：方向 + 是否上/右也画刻度（False=关掉上右刻度=去黑点）+ 颜色 + 长度
            'xtick.direction': _f['tick_dir'], 'ytick.direction': _f['tick_dir'],
            'xtick.top': _f['tick_tr'], 'ytick.right': _f['tick_tr'],
            'xtick.color': _ac, 'ytick.color': _ac,
            'xtick.major.size': 3.5 if _f['tick_dir'] == 'out' else 3,
            'ytick.major.size': 3.5 if _f['tick_dir'] == 'out' else 3,
            # 全局网格：仅 grid.axis=='both' 时全开；'y' 交给制图时按需（gax）。这里设默认样式
            'axes.grid': bool(_grid and _grid.get('axis') == 'both'),
            'grid.linestyle': (_grid or {}).get('ls', '--'),
            'grid.alpha': (_grid or {}).get('alpha', 0.3),
            'grid.color': (_grid or {}).get('color', '#DDDDDD'),
            # 描边：白/加粗白/无
            'patch.edgecolor': {'white': 'white', 'white_bold': 'white', 'none': 'none'}.get(_pe, 'white'),
            'patch.linewidth': {'white': 1.0, 'white_bold': 1.5, 'none': 0.0}.get(_pe, 1.0),
        })
        # ★ 高级自定义新维（字号/背景）——仅 custom 路径的 knobs 有这两键，用 .get 兜底，
        #   预设/随机路径无此键时不覆盖上面设过的默认值（font.size=11 / facecolor=white）。
        _fsz = _f.get('font_size')
        if _fsz:
            _base, _lbl, _ttl, _tk = _fsz
            matplotlib.rcParams.update({
                'font.size': _base, 'axes.labelsize': _lbl, 'axes.titlesize': _ttl,
                'xtick.labelsize': _tk, 'ytick.labelsize': _tk, 'legend.fontsize': _tk,
            })
        _fc = _f.get('facecolor')
        if _fc:
            matplotlib.rcParams['axes.facecolor'] = _fc

    # ★ Nature / NPG 版式：按画布宽反解字号（见 nature_font_pt 的长注释）
    _palette_name = palette if isinstance(palette, str) else None
    global _NATURE_ACTIVE
    _NATURE_ACTIVE = _palette_name in ('nature', 'npg')
    if _NATURE_ACTIVE:
        try:
            _fs0 = matplotlib.rcParams['figure.figsize']
            _w0, _h0 = float(_fs0[0]), float(_fs0[1])
        except Exception:
            _w0, _h0 = _NATURE_REF_W, None
        _apply_nature_scale(_w0, _h0)
        # ⛔ 必须再挂 plt.figure 钩子：setup_style 跑在建图【之前】，
        #   此刻只能按 rcParams 的默认 figsize 反解。脚本一旦显式写
        #   plt.subplots(figsize=(4.4, 3.5))，默认值就作废了 ——
        #   不重解的话 4.4 寸画布仍用 8 寸的字号，回到"字太大"原点。
        _hook_figure_for_nature(plt)

        # ★ Nature 版式随机（去指纹的第二维；配色微调是第一维，见 nature_palette）
        #   ⛔ 只对 palette=='nature' 启用，不碰 'npg' —— npg 是另一套配色，
        #     没有配套的 Nature 版式规范，动它属于超范围。
        #   ⛔ 不复用 STYLE_FAMILIES：那 6 族里 framed_journal / crisp_dark 是
        #     四边框 + 刻度朝内，违反 Nature 规范（左下两边框 + 刻度朝外），
        #     2/6 概率产出「选了 Nature 却不是 Nature」的图。
        if _palette_name == 'nature':
            _nseed = _fig_seed()
            # ★ 把全局 PALETTE / COLORS / prop_cycle 也换成【微调后】的色值。
            #   ⛔ 不做这步会有两个真相源：脚本调 nature_palette() 拿到微调色，
            #     但 plot_utils 内部的通用绘图助手用的是 PALETTE（原始色）——
            #     同一张图上两套蓝，肉眼能看出色差。
            #   PALETTES['nature'] 的 8 色顺序 = blue_main / blue_secondary /
            #   green_3 / red_strong / neutral_mid / teal / violet / gold
            #   （已逐一核对），按同序从语义字典重建。
            _njit = nature_palette(seed=_nseed)
            _NAT_ORDER = ('blue_main', 'blue_secondary', 'green_3', 'red_strong',
                          'neutral_mid', 'teal', 'violet', 'gold')
            _ncolors = _nature_project_colors() or [_njit[k] for k in _NAT_ORDER]
            # ⛔ 不要在这里再写 global —— 本函数前面（选配色那段）已声明过
            #   `global PALETTE, PALETTE_LIGHT, COLORS`，重复声明会触发
            #   SyntaxError: name 'PALETTE' is assigned to before global declaration
            PALETTE[:] = _ncolors
            PALETTE_LIGHT[:] = [_lighten(c, 0.4) for c in _ncolors]
            for role, key in (('primary', 'blue_main'), ('secondary', 'blue_secondary'),
                              ('accent', 'green_3'), ('up', 'green_3'),
                              ('down', 'red_strong'), ('highlight', 'neutral_mid')):
                COLORS[role] = _clamp_contrast_hex(_njit[key], lo=_GRAPHIC_CONTRAST_MIN)
            matplotlib.rcParams['axes.prop_cycle'] = matplotlib.cycler(color=_ncolors)
            if sns:
                try:
                    sns.set_palette(_ncolors)
                except Exception:
                    pass
            # 用户手选（前端只暴露 grid/lw 两维，其余维度在引擎侧已被过滤掉）
            _ncustom = _read_style_custom_marker()
            _nk = _nature_knobs(_nseed, custom=_ncustom)
            _ng = _nk['grid']
            # 钉死项（Nature 的身份，任何种子都不许变）：
            #   左下两边框 / 刻度朝外 / 上右无刻度 / 图例无框 / 白底 /
            #   字号（已由上面 _apply_nature_scale 按画布反解，随机会破 8pt 印刷线）
            matplotlib.rcParams.update({
                'axes.spines.left': True, 'axes.spines.bottom': True,
                'axes.spines.top': False, 'axes.spines.right': False,
                'xtick.direction': 'out', 'ytick.direction': 'out',
                'xtick.top': False, 'ytick.right': False,
                'legend.frameon': False,
                'axes.facecolor': 'white',
                # 随机项 ①：网格（无 / 淡 y / 淡双向）
                # ⛔ 与默认配色路径的差别：那边 'y' 档只设样式、把开关交给制图时
                #   按需调 gax（见上面 906 行附近），所以脚本不主动开就没网格。
                #   Nature 这边【必须自己开】—— 版式随机是引擎的职责，
                #   不能指望 AI 写的脚本去配合，否则这一维随机等于没做。
                #   用 axes.grid.axis 指定只画 y（合法 rcParam，已验证）。
                'axes.grid': bool(_ng),
                'axes.grid.axis': (_ng or {}).get('axis', 'y'),
                'grid.linestyle': (_ng or {}).get('ls', '--'),
                'grid.alpha': (_ng or {}).get('alpha', 0.25),
                'grid.color': (_ng or {}).get('color', '#D8D8D8'),
                # 随机项 ②：图例位置
                'legend.loc': _nk['legend_loc'],
            })
            # 随机项 ③：线宽 / marker 尺寸等比缩放（在反解值基础上 ×0.85~1.15）
            #   ⛔ 必须【乘在反解结果上】而不是写死值 —— 反解值随画布宽变化，
            #     写死会让窄画布的线粗得不成比例。
            _lwk = _nk['lw_k']
            for _key in ('lines.linewidth', 'lines.markersize',
                         'axes.linewidth', 'xtick.major.width', 'ytick.major.width'):
                try:
                    matplotlib.rcParams[_key] = float(matplotlib.rcParams[_key]) * _lwk
                except Exception:
                    pass
            # ⛔ marker 形状【不】进 axes.prop_cycle：`ax.plot(x, y)` 画 500 点
            #   平滑曲线会每点打一个 marker，糊成一片。形状由脚本按需取
            #   nature_markers()（见该函数注释）。

    # ★ Hook plt.savefig — 即使不用 save_fig()，也能自动防遮挡
    _hook_savefig(plt)


_NATURE_ACTIVE = False
_NARROW_WARNED = set()


def _warn_if_canvas_too_narrow(w, h=None):
    """画布过窄时提示：字号已到印刷下限不能再降，
    「字号÷画布宽」明显超过当前印刷目标所对应的基线，密集图仍会互撞。

    ⛔ 这是几何上的死结，不是参数没调好：论文不会把窄图放大，
       所以落地字号 = 画时字号，想保住 8.25pt 就只能接受相应比值。
       出路是【把画布放宽】，不是继续缩字。
    """
    try:
        key = round(float(w), 1)
    except (TypeError, ValueError):
        return
    ratio = nature_font_pt(key, h) / key
    # The old literal 1.375 matched a 7.5 pt target at 5.5 in.  After the
    # print target increased to 8.25 pt it made every normal-width canvas warn
    # (8.25/5.5 == 1.50).  Derive the baseline from the live constants so the
    # warning continues to mean "unusually narrow", not merely "legible".
    ratio_limit = (NATURE_TARGET_PT / PAGE_MAX_W_IN) * 1.02
    if ratio <= ratio_limit or key in _NARROW_WARNED:
        return
    _NARROW_WARNED.add(key)
    print("ℹ 布局密度提示：源画布宽 %.1fin，参考字号/宽度 %.2f（基线 %.2f）。"
          "该比例不作失败依据；若最终尺寸下确有拥挤，给图例/色条留专用区域、重排或拆图，"
          "不要只放大源画布或压小字号。"
          % (key, ratio, ratio_limit),
          file=sys.stderr)


def _hook_figure_for_nature(plt):
    """Hook plt.figure：拿到真实 figsize 后重解一次 nature 字号。

    ⛔ 为什么钩 plt.figure 而不是 plt.subplots：
       subplots 内部就是调 plt.figure，钩前者能同时覆盖
       plt.figure / plt.subplots / add_subplot 三条创建路径。
    ⛔ 为什么不在 savefig 时改 rcParams：那时 Text 对象早已按旧字号建好，
       改 rcParams 对它们【毫无作用】（matplotlib 的字号在创建时就固化）。
       所以必须在建图那一刻改。
    """
    if getattr(plt, '_nature_fig_hooked', False):
        return
    _orig_figure = plt.figure

    def _figure(*args, **kwargs):
        if _NATURE_ACTIVE:
            fs = kwargs.get('figsize')
            if fs is None and args:
                # plt.figure(num, figsize) 位置参数形式
                for a in args[1:]:
                    if isinstance(a, (tuple, list)) and len(a) == 2:
                        fs = a
                        break
            try:
                if fs is not None:
                    w = float(fs[0])
                    h = float(fs[1]) if len(fs) > 1 else None
                    if w > 0.5:
                        _apply_nature_scale(w, h)
                        _warn_if_canvas_too_narrow(w, h)
            except (TypeError, ValueError, IndexError):
                pass          # figsize 畸形 → 保持当前 rcParams，不崩
        return _orig_figure(*args, **kwargs)

    plt.figure = _figure
    plt._nature_fig_hooked = True


def _warn_if_font_chaos(fig):
    """成品自检：同一张图里字号种类过多 → 提示（多半是脚本逐处手写 fontsize=）。

    ⛔ 只提示不改：局部覆盖有时是刻意的（角标、脚注）。但 13 种混用一定是失控 ——
       实测天府杯 C 题三个脚本手写 103 处 fontsize=，一套图 13 种字号，
       其中若干处低于 8pt 印刷线。
    """
    try:
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
    except Exception:
        return
    sizes = {}
    below = 0
    for ax in fig.get_axes():
        cand = (list(ax.get_xticklabels()) + list(ax.get_yticklabels())
                + [ax.xaxis.label, ax.yaxis.label, ax.title] + list(ax.texts))
        lg = ax.get_legend()
        if lg is not None:
            cand += list(lg.get_texts())
        for t in cand:
            if t is None or not t.get_visible() or not t.get_text().strip():
                continue
            try:
                s = round(float(t.get_fontsize()), 1)
            except Exception:
                continue
            sizes[s] = sizes.get(s, 0) + 1
            if s < MIN_LEGIBLE_PT:
                below += 1
    if not sizes:
        return
    if len(sizes) > 6 or below:
        det = "、".join("%.1fpt×%d" % (s, n)
                        for s, n in sorted(sizes.items())[:8])
        msg = "⚠ 字号体系偏乱：同图 %d 种字号（%s）" % (len(sizes), det)
        if below:
            msg += "；其中 %d 处低于 %.1fpt 印刷可读线" % (below, MIN_LEGIBLE_PT)
        msg += "。多半是脚本逐处手写 fontsize= —— 字号应统一交给 setup_style"
        print(msg, file=sys.stderr)


def _hook_savefig(plt):
    """Hook plt.savefig 和 Figure.savefig，在保存前强制修复子图尺寸和文字重叠。"""
    import matplotlib.figure

    if getattr(matplotlib.figure.Figure, '_overlap_hooked', False):
        return  # 已经 hook 过了

    _original_savefig = matplotlib.figure.Figure.savefig

    def _hooked_savefig(self, *args, **kwargs):
        # ★ 强制修复子图尺寸（最高优先级，检测到问题必须修复）
        try:
            _guard_subplot_size(self)
        except Exception:
            pass
        # 类别行过密时先增加纵向画布，再做字号与避让。只扩高度、不扩宽度，
        # 避免论文按固定栏宽缩回去后字号反而变小。
        try:
            _expand_dense_categorical_canvas(self)
        except Exception:
            pass
        # Default logarithmic minor ticks become a dark "comb" once several
        # decades are compressed into a paper-width panel.  Thin them before
        # layout measurement; this changes neither data, limits nor major
        # ticks, but gives labels and neighbouring twin axes real whitespace.
        try:
            _declutter_dense_log_ticks(self)
        except Exception:
            pass
        # ★★ 自适应字号必须在【所有布局修复之前】：
        # ⛔ 字号决定每个 Text 的尺寸，布局修复（折行/让位/收缩 axes）全都依赖它。
        #    反过来做 = 先按旧字号排好版、再改字号，前面的排版全作废。
        try:
            _autofit_fontsize(self)
        except Exception:
            pass
        # Source-space cleanliness is not enough: an oversized canvas may be
        # shrunk sharply by LaTeX/Word.  Work backwards from the final paper
        # placement before measuring collisions, so every later layout pass
        # sees the real print-safe text geometry.
        _ensure_final_print_font(self)
        # 防遮挡修复
        try:
            _auto_fix_overlaps(self)
        except Exception:
            pass
        # 图例与普通文字是两条独立链路：旧实现只有“至少两个用户标注且彼此
        # 重叠”时才会检查图例，导致只有一个标注/完全没有标注的图即使图例
        # 压住整条曲线也直接跳过。这里无条件按真实数据点测一次。
        try:
            _repair_legend_occlusion(self)
        except Exception:
            pass
        # ★ 防遮挡可能又破坏了布局，再强制检查一次
        try:
            _guard_subplot_size(self)
        except Exception:
            pass
        # ★ 确保旋转的刻度标签（斜排长中文）不被画布边缘裁掉
        try:
            _ensure_ticklabels_visible(self)
        except Exception:
            pass
        # ★★ 轴标签出界修复必须是【最后一步】：
        # ⛔ 放在 _save 里（即 fig.savefig 之前）会被本 hook 里的
        #    _guard_subplot_size「重置 subplot margins」把让出的位置推回去 ——
        #    实测出界数只从 29 降到 22，就是被这一步覆盖掉了。
        # ⛔ 也不能放在 _guard_subplot_size 之前，同理会被覆盖。
        # 放这里还有个好处：脚本直接调 fig.savefig()（不走 save_fig）时同样生效。
        try:
            if not _has_3d_axes(self):
                _fix_axis_label_overflow(self)
                # ⛔ 顺序：先修轴标签（可能把标签折成两行、变高），
                #   再腾底部说明的空间 —— 反过来做，折行后又会压上去。
                _fix_figtext_collision(self)
                _fix_axis_label_overflow(self)   # 抬 axes 后复查一次
                # ★★ 兜住"被画布切掉"必须是【最末一步】：
                # ⛔ 上面三步都会挪 axes，放它们之前会被覆盖（同 _guard_subplot_size 那个坑）。
                # ⛔ 它管的是 _fix_axis_label_overflow 抓不到的那些对象 ——
                #    legend(bbox_to_anchor 推到 axes 外)、colorbar 的 set_label、
                #    刻度标签、panel 标号。实测这类占越界的 6/6。
                _fix_clipped_outside(self)
                # ⛔ 救回越界的代价是内容更挤：实测 fig_q3_stress_bars 的 legend 从
                #   画布外拉回来后，压到了底部 fig.text（说明压字 0→1）。
                #   所以要再走一轮"底部说明让位"，然后复查一次越界。
                #   ★ 只做一轮，不循环 —— 两者互为代价，多轮会来回抖。
                _fix_figtext_collision(self)
                _fix_clipped_outside(self)
        except Exception:
            pass
        # Some overflow repairs may reduce an axis label.  Re-assert the final
        # print-size contract once layout has settled, then give legends and
        # annotations one final chance to move around the enlarged text.
        _ensure_final_print_font(self)
        try:
            _auto_fix_overlaps(self)
            _repair_legend_occlusion(self)
        except Exception:
            pass
        # 散点/星号、箭头和柱边界属于不可接受的硬遮挡。自动避让后仍存在时
        # 必须让该图生成失败，迫使脚本删减标注、改固定数值列或增加类别行高度；
        # 不允许带病写入 PDF、也不允许靠缩小字体蒙混过关。
        try:
            _auto_fix_overlaps(self)
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
        # _auto_fix_overlaps may shorten long category labels by reducing their
        # source-space font.  It must never be the final mutating pass: restore
        # the paper-size contract afterwards and do not run another font-
        # shrinking repair.  Any clash caused by the restored type size is a
        # real layout failure and is rejected below.
        _ensure_final_print_font(self)
        # Font changes can also push panel titles beyond the page edge.
        _fix_clipped_outside(self)
        # 最终字号会改变文字 bbox，所以对比度必须在这一刻重算。
        try:
            _ensure_visual_contrast(self)
        except Exception:
            pass
        try:
            unresolved = _unresolved_hard_artist_collisions(self)
            row_overflow = _unresolved_categorical_row_overflow(self)
            legend_text = _unresolved_legend_text_collisions(self)
            legend_data = _unresolved_legend_data_collisions(self)
            renderer = self.canvas.get_renderer()
            clipped = [(kind, obj) for kind, obj, ax, over in _collect_clipped(self, renderer)
                       if (ax is None or not _is_3d_axis(ax))
                       and max(over.values()) > self.dpi / 72.0 * 1.5]
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            unresolved = []
            row_overflow = []
            legend_text = []
            legend_data = []
            clipped = []
        if clipped:
            details = '; '.join(
                str(getattr(obj, 'get_text', lambda: kind)())[:36]
                for kind, obj in clipped[:6]
            )
            raise RuntimeError("图表文字或图例仍超出画布：" + details + "。请缩短标题或重排版面，不能缩小必要文字。")
        if legend_data:
            raise RuntimeError(
                "图例仍遮挡数据：子图 " + ', '.join(map(str, legend_data))
                + "。请为图例建立独立行/列，不改变数据或缩小文字。"
            )
        if unresolved:
            details = '；'.join(
                f"子图{ax_no}“{text or '<空>'}”×{hits}"
                for ax_no, text, hits in unresolved
            )
            raise RuntimeError(
                "图表仍有文字与散点/箭头/柱边界遮挡：" + details
                + "，或有曲线穿过文字。请删去次要结论，或在不改变最终栏宽的前提下增加画布高度/重排。"
            )
        if row_overflow:
            details = '；'.join(
                f"子图{ax_no}“{text or '<空>'}”"
                for ax_no, text in row_overflow
            )
            raise RuntimeError(
                "分类图标注越过所属行边界：" + details
                + "。请删除解释性长句、改用短数值/固定值列，或拆图增加纵向净空。"
            )
        if legend_text:
            details = '；'.join(
                f"子图{ax_no}图例压住“{snippet or '<文字>'}”"
                for ax_no, snippet in legend_text
            )
            raise RuntimeError(
                "图例与注释/面板标题仍有遮挡：" + details
                + "。请把图例移入专用行/列，或删去绘图区内的解释性文字。"
            )
        return _original_savefig(self, *args, **kwargs)

    matplotlib.figure.Figure.savefig = _hooked_savefig
    matplotlib.figure.Figure._overlap_hooked = True


def _has_3d_axes(fig):
    """检测 figure 是否含 3D 轴（Axes3D）。

    含 3D 轴时，所有针对 2D 子图的布局兜底（subplots_adjust / tight_layout /
    set_position 重排）都必须跳过：3D 曲面 + 窄 colorbar 的组合会命中"子图过窄"
    误判，被强行 tight_layout/subplots_adjust 挤塌成一条 colorbar（实测 3D 概率
    曲面图只剩右侧一根竖条）。matplotlib 官方亦声明 tight_layout 不支持 3D 轴。
    """
    try:
        for ax in fig.get_axes():
            if getattr(ax, 'name', '') == '3d' or hasattr(ax, 'get_zlim'):
                return True
    except Exception:
        pass
    return False


def _is_3d_axis(ax):
    """Return whether one axes is 3D without exempting its 2D siblings."""
    try:
        return getattr(ax, 'name', '') == '3d' or hasattr(ax, 'get_zlim')
    except Exception:
        return False


def _lighten(hex_color, amount=0.4):
    """将颜色变浅（用于填充区域）。amount=0 不变，amount=1 变白。"""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f'#{r:02x}{g:02x}{b:02x}'


def _rgba_over(foreground, background):
    """Composite an RGBA foreground over an opaque RGB/RGBA background."""
    fg = tuple(float(v) for v in foreground)
    bg = tuple(float(v) for v in background)
    alpha = fg[3] if len(fg) > 3 else 1.0
    bg_alpha = bg[3] if len(bg) > 3 else 1.0
    # The chart canvas is ultimately opaque.  Resolve a translucent background
    # against white before resolving the foreground.
    base = tuple(bg[i] * bg_alpha + (1.0 - bg_alpha) for i in range(3))
    return tuple(fg[i] * alpha + base[i] * (1.0 - alpha) for i in range(3))


def _contrast_ratio_rgb(a, b):
    la = _rel_luminance(tuple(a[:3]))
    lb = _rel_luminance(tuple(b[:3]))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _readable_text_color(color, background=(1, 1, 1, 1), minimum=_TEXT_CONTRAST_MIN):
    """Return an opaque, hue-preserving readable text color.

    Pastel series colors are useful fills but poor annotation ink.  We first
    move only HLS lightness toward the side opposite the background; black or
    white is used only as a final fallback.  This keeps the selected palette's
    visual identity while preventing labels from disappearing into a bar or
    the page.
    """
    from matplotlib.colors import to_rgba
    import colorsys

    try:
        fg = to_rgba(color)
        bg = to_rgba(background)
    except Exception:
        return color
    bg_rgb = _rgba_over(bg, (1, 1, 1, 1))
    visible_fg = _rgba_over(fg, bg_rgb + (1.0,))
    if _contrast_ratio_rgb(visible_fg, bg_rgb) + 1e-9 >= minimum:
        return color

    h, lightness, saturation = colorsys.rgb_to_hls(*fg[:3])
    # Mid-tone backgrounds may require black even when their luminance is
    # below 0.45. Choose the endpoint with higher real contrast, not a heuristic.
    darken = (_contrast_ratio_rgb((0, 0, 0), bg_rgb)
              >= _contrast_ratio_rgb((1, 1, 1), bg_rgb))
    best = None
    for _ in range(80):
        lightness = max(0.015, lightness - 0.012) if darken else min(0.985, lightness + 0.012)
        candidate = colorsys.hls_to_rgb(h, lightness, saturation)
        ratio = _contrast_ratio_rgb(candidate, bg_rgb)
        if ratio >= minimum:
            best = candidate
            break
    if best is None:
        candidates = ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
        best = max(candidates, key=lambda value: _contrast_ratio_rgb(value, bg_rgb))
    return _rgb01_2hex(best)


def _text_background_rgba(text, ax, renderer):
    """Estimate the visible background directly underneath a Text artist."""
    from matplotlib.colors import to_rgba

    fallback = (1.0, 1.0, 1.0, 1.0)
    try:
        owner = ax.figure if ax is not None else text.figure
        fallback = to_rgba((ax if ax is not None else owner).get_facecolor())
    except Exception:
        pass

    # A text's own bbox patch is the closest and most reliable background.
    try:
        box_patch = text.get_bbox_patch()
        if box_patch is not None and box_patch.get_visible():
            face = to_rgba(box_patch.get_facecolor())
            if face[3] > 0.05:
                return _rgba_over(face, fallback) + (1.0,)
    except Exception:
        pass

    if ax is None:
        return fallback
    try:
        bbox = text.get_window_extent(renderer=renderer)
        text_area = max(bbox.width * bbox.height, 1e-6)
    except Exception:
        return fallback

    candidates = []
    for patch in list(getattr(ax, 'patches', ())):
        if patch is ax.patch or not patch.get_visible():
            continue
        try:
            face = to_rgba(patch.get_facecolor())
            if face[3] <= 0.05:
                continue
            pb = patch.get_window_extent(renderer=renderer)
            iw = min(bbox.x1, pb.x1) - max(bbox.x0, pb.x0)
            ih = min(bbox.y1, pb.y1) - max(bbox.y0, pb.y0)
            coverage = max(iw, 0.0) * max(ih, 0.0) / text_area
            # A multiline label can have its centre in whitespace while its
            # lower line crosses a bar (real failure: the ±2% span over an
            # orange column).  Centre-point tests miss this completely.
            if coverage >= 0.04:
                visible = _rgba_over(face, fallback) + (1.0,)
                current = _rgba_over(to_rgba(text.get_color()), visible)
                candidates.append((_contrast_ratio_rgb(current, visible),
                                   -coverage, max(pb.width * pb.height, 0.0), visible))
        except Exception:
            continue
    if not candidates:
        return fallback
    # Consider uncovered portions against the axes background as well.  Pick
    # the background on which the *current* ink is least readable; repairing
    # that worst case normally also improves the others.
    max_coverage = max(-item[1] for item in candidates)
    if max_coverage < 0.96:
        current = _rgba_over(to_rgba(text.get_color()), fallback)
        candidates.append((_contrast_ratio_rgb(current, fallback), 0.0,
                           float('inf'), fallback))
    return min(candidates, key=lambda item: (item[0], item[1], item[2]))[3]


def _axes_titles(ax):
    return tuple(t for t in (ax.title, getattr(ax, '_left_title', None),
                             getattr(ax, '_right_title', None)) if t is not None)


def _visible_axis_labels(ax):
    """Axis decorations can be hidden while titles, data and legends still draw."""
    if not ax.get_visible() or not getattr(ax, 'axison', True):
        return []
    return [axis.label for axis in (ax.xaxis, ax.yaxis)
            if axis.get_visible() and axis.label.get_visible()]


def _all_text_artists(fig):
    """Yield unique visible text artists with their owning axes."""
    seen = set()
    for ax in fig.get_axes():
        if not ax.get_visible():
            continue
        items = (list(_axes_titles(ax)) + _visible_axis_labels(ax)
                 + _onscreen_tick_labels(ax)
                 + list(ax.texts))
        legend = ax.get_legend()
        if legend is not None:
            items += list(legend.get_texts())
            if legend.get_title() is not None:
                items.append(legend.get_title())
        for item in items:
            if item is None or id(item) in seen:
                continue
            seen.add(id(item))
            try:
                if item.get_visible() and item.get_text().strip():
                    yield item, ax
            except Exception:
                continue
    for legend in getattr(fig, 'legends', ()):
        items = list(legend.get_texts())
        if legend.get_title() is not None:
            items.append(legend.get_title())
        for item in items:
            if item is None or id(item) in seen:
                continue
            seen.add(id(item))
            try:
                if item.get_visible() and item.get_text().strip():
                    yield item, None
            except Exception:
                continue
    for item in fig.texts:
        if id(item) in seen:
            continue
        try:
            if item.get_visible() and item.get_text().strip():
                yield item, None
        except Exception:
            continue


def _ensure_visual_contrast(fig):
    """Enforce contrast for final text and meaningful Line2D data strokes."""
    from matplotlib.colors import to_rgba

    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
    except Exception:
        return

    fixes = 0
    for text, ax in _all_text_artists(fig):
        try:
            background = _text_background_rgba(text, ax, renderer)
            replacement = _readable_text_color(text.get_color(), background)
            if to_rgba(replacement)[:3] != to_rgba(text.get_color())[:3] or (text.get_alpha() or 1.0) < 0.999:
                text.set_color(replacement)
                text.set_alpha(1.0)
                fixes += 1
        except Exception:
            continue

    # Grid lines are intentionally quiet; data/reference strokes are not.
    for ax in fig.get_axes():
        grid_ids = {id(line) for line in list(ax.get_xgridlines()) + list(ax.get_ygridlines())}
        try:
            background = to_rgba(ax.get_facecolor())
        except Exception:
            background = (1, 1, 1, 1)
        bg_rgb = _rgba_over(background, (1, 1, 1, 1))
        for line in ax.get_lines():
            if id(line) in grid_ids or not line.get_visible():
                continue
            try:
                if float(line.get_linewidth()) < 0.45 or float(line.get_alpha() or 1.0) < 0.25:
                    continue
                current = to_rgba(line.get_color())
                visible = _rgba_over(current, bg_rgb + (1.0,))
                if _contrast_ratio_rgb(visible, bg_rgb) + 1e-9 >= _GRAPHIC_CONTRAST_MIN:
                    continue
                replacement = _readable_text_color(
                    current, background, minimum=_GRAPHIC_CONTRAST_MIN)
                line.set_color(replacement)
                line.set_alpha(max(float(line.get_alpha() or 1.0), 0.85))
                fixes += 1
            except Exception:
                continue
    fig._mh_contrast_fixes = fixes


# 初始化 PALETTE_LIGHT（必须在 _lighten 定义之后）
PALETTE_LIGHT[:] = [_lighten(c, 0.4) for c in PALETTE]


def _pull_back_outside_transaxes_text(fig):
    """无条件检测：ax.text(transAxes, y<0 or y>1) 这种 axes 外子图标题，
    转换成 fig.text(figure coords) 钉在画布底部/顶部，且改写到 figure 坐标系。
    
    理由：science 样式默认 savefig.bbox='tight' 会把 axes 外文字算进 PDF mediabox，
    导致页面被异常拉长。即便我们已经全局关掉 savefig.bbox='tight'，AI 代码仍可能
    显式传 bbox_inches='tight'。把这种文本拉到 axes 内或转 figure 坐标都能解决。
    """
    try:
        axes = [ax for ax in fig.get_axes() if ax.get_visible()]
        for ax in axes:
            ax_pos = ax.get_position()
            for t in list(ax.texts):
                try:
                    if t.get_transform() is not ax.transAxes:
                        continue
                    x, y = t.get_position()
                    if y > 1.0:
                        # 拉回 axes 内顶端
                        t.set_position((x, 0.97))
                        t.set_va('top')
                    elif y < 0.0:
                        # 拉回 axes 内底端
                        t.set_position((x, 0.03))
                        t.set_va('bottom')
                except Exception:
                    pass
    except Exception:
        pass


def _auto_shrink_figsize_if_sparse(fig):
    """检测所有 axes 占 figure 总面积比例，过低时强制重排 + 收缩 figsize。
    
    场景：AI 写了 figsize=(10, 12) 但实际只画 2 个小 panel 在底部/顶部，
    剩下大块白边 → 用户看到的就是"图很小，整页白"。
    
    三阶段策略：
    1. subplots_adjust（对 plt.subplots / add_subplot 创建的 axes 有效）
    2. ★ 直接 set_position 强制重排（对 add_axes / GridSpec 手动布局也有效）
       — 按原始相对位置等比例缩放到撑满 figure 80%
       — 同时把 ax.text(transAxes, y>1.0) 反模式拉回 axes 内部
    3. 仍稀疏 → 收缩 figsize
    
    副作用：触发任一阶段修复时，在 fig 上设 `_layout_fixed_by_plot_utils=True`，
    让 _save 用 bbox_inches=None 防止 transAxes 高位标注异常扩展 PDF mediabox。
    """
    try:
        # ★ 3D 轴豁免：等比例重排/收缩 figsize 会破坏 3D 曲面 + colorbar 布局
        if _has_3d_axes(fig):
            return
        # Dedicated shared-legend/colorbar lanes intentionally reduce the
        # union of data axes.  Treating that as accidental blank space would
        # stretch the panels back underneath the reserved lane.
        if bool(getattr(fig, '_mh_manual_layout', False)):
            return

        axes = [ax for ax in fig.get_axes()
                if ax.get_visible() and not ax.get_label().startswith('_')]
        if not axes:
            return

        fig_w, fig_h = fig.get_size_inches()
        if fig_w <= 0 or fig_h <= 0:
            return

        def _compute_union():
            x0_min, y0_min, x1_max, y1_max = 1.0, 1.0, 0.0, 0.0
            for ax in axes:
                pos = ax.get_position()
                x0_min = min(x0_min, pos.x0)
                y0_min = min(y0_min, pos.y0)
                x1_max = max(x1_max, pos.x1)
                y1_max = max(y1_max, pos.y1)
            return x0_min, y0_min, x1_max, y1_max

        x0_min, y0_min, x1_max, y1_max = _compute_union()
        if x1_max <= x0_min or y1_max <= y0_min:
            return

        union_w = x1_max - x0_min
        union_h = y1_max - y0_min
        content_ratio = union_w * union_h

        if content_ratio >= 0.50:
            return  # 占比够，不调

        # ★ 阶段 1：先试 subplots_adjust（对 plt.subplots 创建的 axes 有效）
        try:
            fig.subplots_adjust(left=0.10, right=0.96, top=0.93, bottom=0.10,
                                hspace=0.3, wspace=0.3)
            x0_min, y0_min, x1_max, y1_max = _compute_union()
            new_ratio = (x1_max - x0_min) * (y1_max - y0_min)
            if new_ratio >= 0.50:
                fig._layout_fixed_by_plot_utils = True
                return  # 搞定
        except Exception:
            pass

        # ★ 阶段 2：subplots_adjust 失效（add_axes / GridSpec 手动布局），
        #         直接 set_position 强制重排：按原始相对位置等比例缩放撑满
        # 这是修复 "axes 集中在 figure 一侧（如底部 20%），子图标题被推到顶部" 的关键
        try:
            # 重新读 union（subplots_adjust 可能已变化）
            x0_min, y0_min, x1_max, y1_max = _compute_union()
            union_w = x1_max - x0_min
            union_h = y1_max - y0_min

            # 目标：让 union 撑满 figure 的 (0.08-0.94) × (0.10-0.93) 区域
            target_x0, target_y0 = 0.10, 0.10
            target_w, target_h = 0.85, 0.82

            # 缩放比例（保持各 axes 相对位置）
            scale_w = target_w / union_w if union_w > 0.001 else 1.0
            scale_h = target_h / union_h if union_h > 0.001 else 1.0
            # 不要过度放大（>6x 容易让 add_axes 手动布局变形）
            scale_w = min(scale_w, 6.0)
            scale_h = min(scale_h, 6.0)

            for ax in axes:
                pos = ax.get_position()
                # 相对 union 的偏移
                rel_x = (pos.x0 - x0_min) / max(union_w, 0.001)
                rel_y = (pos.y0 - y0_min) / max(union_h, 0.001)
                # 新位置：把整个 union 投影到 target 区域
                new_x0 = target_x0 + rel_x * target_w
                new_y0 = target_y0 + rel_y * target_h
                new_w = pos.width * scale_w
                new_h = pos.height * scale_h
                # 边界保护
                new_x0 = max(0.02, min(new_x0, 0.95))
                new_y0 = max(0.02, min(new_y0, 0.95))
                new_w = max(0.05, min(new_w, 1.0 - new_x0 - 0.02))
                new_h = max(0.05, min(new_h, 1.0 - new_y0 - 0.02))
                ax.set_position([new_x0, new_y0, new_w, new_h])

            # ★ 把 ax.text(transAxes, y>1.0) 反模式拉回 axes 内部
            # 这种 "axes 外标注" 会被 bbox_inches='tight' 算进 PDF mediabox，
            # 导致页面被异常拉长（"标题在顶部、图在底部、中间一大片白"的根因）
            for ax in axes:
                for t in list(ax.texts):
                    try:
                        if t.get_transform() is ax.transAxes:
                            x, y = t.get_position()
                            if y > 1.0:
                                t.set_position((x, 0.95))
                                t.set_va('top')
                            elif y < 0.0:
                                t.set_position((x, 0.05))
                                t.set_va('bottom')
                    except Exception:
                        pass

            x0_min, y0_min, x1_max, y1_max = _compute_union()
            new_ratio = (x1_max - x0_min) * (y1_max - y0_min)
            if new_ratio >= 0.50:
                fig._layout_fixed_by_plot_utils = True
                return
        except Exception:
            pass

        # ★ 阶段 3：仍稀疏 → 收缩 figsize
        new_w_inches = max(3.5, (x1_max - x0_min) * fig_w * 1.18)
        new_h_inches = max(2.5, (y1_max - y0_min) * fig_h * 1.18)
        new_w_inches = min(new_w_inches, fig_w)
        new_h_inches = min(new_h_inches, fig_h)
        if new_w_inches > fig_w * 0.95 and new_h_inches > fig_h * 0.95:
            return
        fig.set_size_inches(new_w_inches, new_h_inches)
        fig._layout_fixed_by_plot_utils = True
    except Exception:
        # 任何异常都静默跳过，不能让兜底逻辑搞坏正常保图
        pass


def _warn_if_wasted_margin(fig, output):
    """成品自检：保存前实测左边距，明显富余就打提示（不阻塞出图）。

    为什么需要：其他 9 道闸都是静态扫源码，而"左边距被撑爆"取决于 renderer 运行时
    实测，静态扫不出来 —— 历史上这个病就是这样潜伏下来的（对数轴幽灵刻度被当成
    越界，左边距一路顶到封顶 0.40，图上 40% 是白的）。

    判据不能拿"左距 > X%"一刀切：横向条形图配长中文 y 标签（特征重要性、方法对比）
    真的需要 25%+ 的左边距，那是合理的。所以拿【实测 y 标签宽度】当基准，
    只有左边距远超标签实际所需时才提示。
    """
    if _has_3d_axes(fig):
        return  # 3D 轴刻度在投影平面上，边距语义不同
    try:
        axes = [ax for ax in fig.get_axes()
                if ax.get_visible() and not ax.get_label().startswith('_')]
        if not axes:
            return
        fig_w_px = fig.get_size_inches()[0] * fig.dpi
        if fig_w_px <= 0:
            return
        left_px = min(ax.get_position().x0 for ax in axes) * fig_w_px
        if left_px <= 0:
            return
        renderer = fig.canvas.get_renderer()
        # y 刻度标签 + y 轴标题 实际占用的宽度
        need_px = 0.0
        for ax in axes:
            for t in _onscreen_tick_labels(ax, which='y'):
                if t.get_visible() and t.get_text().strip():
                    need_px = max(need_px, t.get_window_extent(renderer=renderer).width)
            lbl = ax.yaxis.label
            if lbl is not None and lbl.get_text().strip():
                need_px += lbl.get_window_extent(renderer=renderer).height
        need_px += 0.02 * fig_w_px  # 刻度线 + 呼吸余量
        # 只在"绝对富余够大"且"相对富余明显"时提示，避免误报刷屏
        if left_px - need_px > 0.06 * fig_w_px and left_px > need_px * 1.6:
            print(f"[plot_utils] WARNING {os.path.basename(str(output))} 左边距偏大: "
                  f"实测 {left_px / fig_w_px * 100:.1f}% 图宽，y 标签实际只需 "
                  f"{need_px / fig_w_px * 100:.1f}% —— 疑似空白浪费，检查坐标轴范围与刻度")
    except Exception:
        pass  # 自检永不影响出图


def _warn_if_data_clipped(fig, output):
    """成品自检：大量数据点落在轴范围外 → 几乎总是 xlim/ylim/zlim 写错。

    为什么必须运行时实测：静态扫源码看不出 `set_xlim(0, L)` 到底对不对 —— 那取决于
    数据坐标系的约定。实测起因是把主胞「边长 L=10000」当成了坐标上界，而数据其实以
    原点为中心（[-L/2, +L/2]），于是负坐标那一半（实测 46%~79% 的点）被静默裁到轴外，
    图上只剩挤在角落的一小撮，matplotlib 不报错、任何静态闸也扫不出来。

    阈值取 20%：合法的「裁掉几个离群点」通常远低于 5%，而坐标系写错必然接近 50%。
    """
    try:
        msgs = []
        for ax in fig.get_axes():
            if not ax.get_visible():
                continue
            is3d = getattr(ax, 'name', '') == '3d' or hasattr(ax, 'get_zlim')
            P = _data_points_in_data_space(ax, is3d)
            if P is None or P.shape[0] < 4:
                continue
            # 大数据集抽样：判「是否 >20% 的点落在轴外」不需要全量 —— 5 万样本的统计
            # 误差 <0.4%，而 90 万点全量实测要 1.74s，白加在每次 save_fig 上。
            # 固定 seed 保证同一张图重复跑结论一致（不引入随机抖动）。
            if P.shape[0] > 50000:
                P = P[np.random.default_rng(0).choice(P.shape[0], 50000, replace=False)]
            axinfo = [(ax.get_xlim(), ax.get_xscale()), (ax.get_ylim(), ax.get_yscale())]
            if is3d:
                axinfo.append((ax.get_zlim(),
                               getattr(ax, 'get_zscale', lambda: 'linear')()))
            for k, ((lo, hi), scale) in enumerate(axinfo):
                if k >= P.shape[1]:
                    break
                v = P[:, k]
                v = v[np.isfinite(v)]
                if scale == 'log':
                    v = v[v > 0]      # log 轴上非正值 matplotlib 本就不画，不算被裁
                if v.size < 4:
                    continue
                lo, hi = min(lo, hi), max(lo, hi)
                n_out = int(((v < lo) | (v > hi)).sum())
                if n_out / v.size > 0.20:
                    msgs.append(
                        f"{'xyz'[k]} 轴: {n_out}/{v.size} ({n_out / v.size:.0%}) 个点落在 "
                        f"[{lo:.4g}, {hi:.4g}] 之外，数据实际范围 [{v.min():.4g}, {v.max():.4g}]")
        if msgs:
            print(f"[plot_utils] ⛔ {os.path.basename(str(output))} 有数据被坐标轴裁掉：")
            for m in msgs[:6]:
                print(f"    {m}")
            print("    这几乎总是 set_xlim/set_ylim/set_zlim 写错。最常见的坑：把「边长/总长 L」")
            print("    当成坐标上界写了 (0, L)，而数据坐标系以原点为中心，应为 (-L/2, +L/2)。")
            print("    先打印数据真实 min/max 再定轴范围；别用 figsize / view_init 掩盖 ——")
            print("    被裁的点是真的没画出来。（若确为有意放大局部 inset，可忽略本条）")
    except Exception:
        pass  # 自检永不影响出图


def _flatten_segments(segs):
    """把 LineCollection / Line3DCollection 的 segments 展平成 (N, 2|3)。

    段等长（绝大多数情况，每段 2 点）时 np.asarray 能直接生成 3 维数组，
    实测 20 万段 39ms；退回 Python 列表推导要 133ms。段长不齐时 asarray 抛
    ValueError（numpy 不再允许 ragged），故用 except 兜住走慢路径。
    """
    try:
        a = np.asarray(segs, dtype=float)
        if a.ndim == 3:
            return a.reshape(-1, a.shape[-1])
    except Exception:
        pass
    return np.asarray([p for seg in segs for p in seg], dtype=float)


def _data_points_in_data_space(ax, is3d):
    """收集该 axes 上确实处于「数据坐标系」的点，返回 (N,2) / (N,3) 或 None。

    精确区分 transform 是本函数的全部难点，判据都是实测出来的：
      · Line2D      → get_transform() is ax.transData（axhline/axvline 是 blended，自动排除）
      · scatter     → offsets 走 get_offset_transform()，**不是** get_transform()
                      （实测 2D scatter 的 get_transform() 返回 IdentityTransform，
                        照搬 Line2D 的判据会把所有散点图漏掉）
      · LineCollection/vlines → get_segments() + get_transform() is ax.transData
      · 3D          → get_segments() 在投影前返回空，必须用私有 _segments3d / _offsets3d；
                      3D 的 transData 是投影后的，故 3D 分支不做 transform 判据
    故意跳过 fill_between(PolyCollection) 与 plot_surface(Poly3DCollection)：
    它们的顶点常含 baseline / 示意平面，位置由代码指定而非数据，算进去会误报。
    """
    pts = []
    for l in getattr(ax, 'lines', []):
        try:
            if is3d and hasattr(l, 'get_data_3d'):
                pts.append(np.asarray(l.get_data_3d(), dtype=float).T)
            elif not is3d and l.get_transform() is ax.transData:
                pts.append(np.asarray(l.get_xydata(), dtype=float))
        except Exception:
            pass
    for c in getattr(ax, 'collections', []):
        try:
            if is3d:
                s3 = getattr(c, '_segments3d', None)
                if s3 is not None and len(s3):
                    pts.append(_flatten_segments(s3))
                    continue
                o3 = getattr(c, '_offsets3d', None)
                if o3 is not None and len(o3) == 3:
                    pts.append(np.asarray(o3, dtype=float).T)
                continue
            hit = False
            if hasattr(c, 'get_offsets') and hasattr(c, 'get_offset_transform'):
                if c.get_offset_transform() is ax.transData:
                    o = np.asarray(c.get_offsets(), dtype=float)
                    if o.size:
                        pts.append(o)
                        hit = True
            if not hit and hasattr(c, 'get_segments') and c.get_transform() is ax.transData:
                sg = c.get_segments()
                if len(sg):
                    pts.append(_flatten_segments(sg))
        except Exception:
            pass
    try:
        pts = [p.reshape(-1, p.shape[-1]) for p in pts if getattr(p, 'size', 0)]
        want = 3 if is3d else 2
        pts = [p for p in pts if p.shape[-1] == want]
        return np.vstack(pts) if pts else None
    except Exception:
        return None


_AXLABEL_BREAKS = ('（', '(', '，', ',', '、', '：', ':', ' ')


def _math_mask(t):
    """返回与 t 等长的布尔表：True = 该字符位于 $...$ 数学区内。

    ⛔ 折行必须知道哪里是数学区：在 `$q_{\\rm order}$` 内部的空格处断开会切断
       $ 配对，mathtext 解析失败 → LaTeX 源码原样印在图上（实测天府杯 C 题
       x 轴标签变成 `预计核销率 $q$（名义 $q_{\\rm order}$ = 0.47257`）。
    """
    inside = False
    out = []
    i = 0
    n = len(t)
    while i < n:
        if t[i] == '$' and (i == 0 or t[i - 1] != '\\'):
            inside = not inside
            out.append(True)          # $ 本身算数学区，不许在它上面断
        else:
            out.append(inside)
        i += 1
    return out


def _wrap_axis_label(txt, parts=2):
    """把过长轴标签在自然分隔处折成 parts 行。⛔ 折行而不是截断 —— 轴标签常带
    关键口径（单位、基准），截掉就丢信息；折行一个字都不少。

    ⛔⛔ 断点只能取在 $...$ 之外，且折完必须校验每行 $ 配对 —— 否则就是把
       "标签被裁" 换成 "图上印 LaTeX 源码"，后者更难看。
    """
    t = str(txt)
    if '\n' in t or len(t) < 10:
        return t
    mask = _math_mask(t)
    mid = len(t) // parts
    best, bestd = None, 10 ** 9
    for i, ch in enumerate(t):
        if mask[i]:
            continue                  # ⛔ 数学区内一律不断
        if ch in _AXLABEL_BREAKS and 3 <= i <= len(t) - 3:
            d = abs(i - mid)
            if d < bestd:
                best, bestd = i, d
    if best is None:
        return t
    # 分隔符留在上一行行尾（中文括号除外，它应带到下一行开头）
    if t[best] in ('（', '('):
        cand = t[:best] + '\n' + t[best:]
    else:
        cand = t[:best + 1] + '\n' + t[best + 1:].lstrip()
    # ⛔ 兜底校验：任一行 $ 数为奇数 → 放弃折行（宁可被裁也不印源码）
    if any(line.count('$') % 2 for line in cand.split('\n')):
        return t
    return cand


def _fix_figtext_collision(fig):
    """图级 fig.text（底部说明/脚注）压住 x 轴标签 → 把说明下移 + 抬高 axes 底边。

    ⛔ 这是实测中肉眼最明显的一类："底部说明文字和 x 轴标签糊成一团"。
       8/15 张真实图中招（fig_q3_reopt_slope 一条说明压住 4 条轴文字）。
    ⛔ 它长期被漏掉，因为体检只扫 axes 级文字（刻度/轴标签/标注/图例），
       fig.texts 根本没进统计 —— 数字报 0 而图上明明糊着。加判据时务必带上它。
    """
    try:
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        fb = fig.get_window_extent(renderer=r)
    except Exception:
        return
    notes = [t for t in fig.texts
             if t.get_visible() and t.get_text().strip()]
    if not notes:
        return

    def axes_boxes():
        out = []
        for ax in fig.get_axes():
            for t in (_onscreen_tick_labels(ax, which='x')
                      + [ax.xaxis.label]):
                if t is None or not t.get_visible() or not t.get_text().strip():
                    continue
                try:
                    out.append(t.get_window_extent(renderer=r))
                except Exception:
                    pass
        return out

    for _ in range(3):
        boxes = axes_boxes()
        if not boxes:
            return
        worst = 0.0
        for t in notes:
            try:
                b = t.get_window_extent(renderer=r)
            except Exception:
                continue
            # 只处理"贴底部"的说明（在 figure 下半部），标题类不动
            if (b.y0 + b.y1) / 2 > fb.y0 + fb.height * 0.30:
                continue
            for ab in boxes:
                dy = min(b.y1, ab.y1) - max(b.y0, ab.y0)
                dx = min(b.x1, ab.x1) - max(b.x0, ab.x0)
                if dx > 0.5 and dy > 0.5:
                    worst = max(worst, dy)
        if worst <= 0.5:
            return
        # ⛔⛔ 优先缩【x 轴标签字号】，⛔ 不要压绘图区：
        #   冲突的真因是轴标签被折成两行后变高、顶到了底部说明，
        #   该退让的是那个标签本身。大幅压 axes（曾写成每轮 5%、共 15%）
        #   会把绘图区挤扁 → 里面的数据标注互相撞上：实测
        #   fig_q1_coverage_cmp 的标注互撞从 3 处暴涨到 14 处，
        #   等于用"标注糊在一起"换掉了"说明压轴标签"，得不偿失。
        # ⛔ 字号【一次降到下限】，⛔ 不要每轮减 1pt：循环预算只有 3 轮，
        #   标签从 11pt 起逐步减到 8pt，轮次全耗在这里、
        #   后面的"抬 axes"分支永远执行不到（实测把力度从 6% 调到 15% 毫无变化，
        #   就是因为那段代码根本没跑）。
        acted = False
        for ax in fig.get_axes():
            lbl = ax.xaxis.label
            if lbl is None or not lbl.get_text().strip():
                continue
            cur = lbl.get_fontsize()
            if cur > 7.0:
                lbl.set_fontsize(7.0)
                acted = True
        if not acted:
            # 字号已到 8pt 下限 → 抬 axes 底边腾空间（每轮 ≤3.5%，累计 ≤10%）。
            # ⛔ 力度是权衡出来的：压太狠（曾用 5%/轮、共 15%）会把绘图区挤扁、
            #   里面的数据标注互撞（coverage_cmp 从 3 处涨到 14 处）；压太轻
            #   （2%/轮、共 6%）则说明仍压着轴标签（跨子图 13 处）。
            #   10% 是实测下"两头都不失控"的点，残余的标注互撞交给
            #   零遮挡算法收拾（它本职就是这个）。
            need = min(worst / max(fb.height, 1) + 0.008, 0.05)
            for ax in fig.get_axes():
                p = ax.get_position()
                nh = p.height - need
                if nh < p.height * 0.70:
                    continue
                ax.set_position([p.x0, p.y0 + need, p.width, nh])
                acted = True
        if not acted:
            return
        try:
            fig.canvas.draw()
            r = fig.canvas.get_renderer()
        except Exception:
            return


def _fix_axis_label_overflow(fig):
    """轴标签溢出 figure 边界 → 折行 → 仍溢出则缩字号 → 仍溢出则让边距。

    ⛔ 这是实测中最大的单项问题：天府杯 C 题 15 张图共 29 处轴标签被画布边缘裁掉
       （最严重 `相对名义情景的倍数（名义 = 1.00，端点数字为绝对值）` 超出 242px）。
       nature 配色的 16pt 让中文轴标签宽度涨 45%，长标签必然出界。
    ⛔ 顺序不能反：先折行（不丢信息）→ 再缩字号（还能读）→ 最后让边距
       （代价最大，会压缩绘图区）。
    """
    plt = _get_plt()
    try:
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
    except Exception:
        return
    try:
        fb = fig.get_window_extent(renderer=r)
    except Exception:
        return

    def over(lbl):
        try:
            b = lbl.get_window_extent(renderer=r)
        except Exception:
            return 0.0
        return max(fb.x0 - b.x0, b.x1 - fb.x1, fb.y0 - b.y0, b.y1 - fb.y1, 0.0)

    targets = []
    for ax in fig.get_axes():
        for lbl in (ax.xaxis.label, ax.yaxis.label):
            if lbl is not None and lbl.get_visible() and lbl.get_text().strip():
                if over(lbl) > 0.5:
                    targets.append((ax, lbl))
    if not targets:
        return

    # ① 折行
    for _ax, lbl in targets:
        w = _wrap_axis_label(lbl.get_text())
        if w != lbl.get_text():
            lbl.set_text(w)
    try:
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
    except Exception:
        return

    # ② 仍溢出 → 缩字号（下限 8pt，最终印刷可读线）
    still = [(ax, l) for ax, l in targets if over(l) > 0.5]
    for _ax, lbl in still:
        try:
            cur = lbl.get_fontsize()
            for _ in range(4):
                if over(lbl) <= 0.5 or cur <= 7.0:
                    break
                cur = max(7.0, cur - 1.0)
                lbl.set_fontsize(cur)
                fig.canvas.draw()
                r = fig.canvas.get_renderer()
        except Exception:
            pass

    # ③ 还溢出 → 【逐个 axes 用 set_position 让位】。
    # ⛔⛔ 不要用 fig.subplots_adjust：实测这批图的子图是 add_axes / GridSpec
    #    手工布局的（位置形如 [0.92-0.95] 的窄色条轴），subplots_adjust 对它们
    #    完全无效 —— 出界数从 29 只降到 25，就是因为这一步空转。
    #    set_position 直接改 axes 矩形，与创建方式无关，一定生效。
    # ⛔ 四个方向都要处理：x 轴标签在右侧子图下方居中时是【往右】溢出的。
    try:
        for _ in range(3):
            fig.canvas.draw()
            r = fig.canvas.get_renderer()
            moved = False
            for ax, lbl in targets:
                try:
                    b = lbl.get_window_extent(renderer=r)
                except Exception:
                    continue
                dl = (fb.x0 - b.x0) / max(fb.width, 1)
                dr = (b.x1 - fb.x1) / max(fb.width, 1)
                db = (fb.y0 - b.y0) / max(fb.height, 1)
                dt = (b.y1 - fb.y1) / max(fb.height, 1)
                if max(dl, dr, db, dt) <= 0.002:
                    continue
                p = ax.get_position()
                x0, y0, w, h = p.x0, p.y0, p.width, p.height
                # 往左溢出 → axes 右移并收窄；其余方向同理。每轮最多让 6%，
                # 且绘图区不小于原来的 55%，防止图被压成条。
                step = 0.06
                if dl > 0.002:
                    d = min(dl + 0.005, step)
                    x0, w = x0 + d, w - d
                if dr > 0.002:
                    w = w - min(dr + 0.005, step)
                if db > 0.002:
                    d = min(db + 0.005, step)
                    y0, h = y0 + d, h - d
                if dt > 0.002:
                    h = h - min(dt + 0.005, step)
                if w < p.width * 0.55 or h < p.height * 0.55:
                    continue
                ax.set_position([x0, y0, w, h])
                moved = True
            if not moved:
                break
    except Exception:
        pass


# 窄条 axes（colorbar / 树状图侧栏）判定：占 figure 不到这个比例就算窄条，
# 修越界时对它【平移】而非【收窄】。实测 colorbar fraction=0.046 → 宽 0.0256。
# 窄条 axes（colorbar / 树状图侧栏）判定：占 figure 不到这个比例就算窄条，
# 修越界时对它【平移】而非【收窄】。实测 colorbar fraction=0.046 → 宽 0.0256。
_NARROW_AXES_FRAC = 0.08


# ============================================================
# 自适应字号：按画布定基准 → 实测遮挡 → 收/放到刚好不撞
# ============================================================
# 各角色相对基准的比例（学术图常规层级：标题略大、刻度略小）
_ROLE_RATIO = {
    'title': 1.15, 'axislabel': 1.05, 'tick': 0.95,
    'anno': 1.00, 'legend': 0.95, 'figtext': 0.95,
}
# 图通常会按约 0.9 倍缩入论文版心。这里约束的是源 PDF 字号，不能直接拿
# “最终印刷 8 pt”当源图下限，否则 8 pt 经缩放只剩约 7.3 pt。宁可让布局门
# 报重叠并要求删字/重排，也不能靠缩小字体掩盖拥挤。
_AUTOFIT_MIN = 9.0
_AUTOFIT_MAX = 13.0                # 再大就不像期刊图了


def _fig_text_roles(fig):
    """把图上所有 Text 按角色归类：[(role, obj, ax)]"""
    got = []
    seen = set()

    def add(role, obj, ax):
        if obj is None or id(obj) in seen:
            return
        try:
            if not obj.get_visible() or not obj.get_text().strip():
                return
        except Exception:
            return
        seen.add(id(obj))
        got.append((role, obj, ax))

    for ax in fig.get_axes():
        if not ax.get_visible():
            continue
        for title in _axes_titles(ax):
            if title.get_visible() and title.get_text().strip():
                add('title', title, ax)
        for lbl in _visible_axis_labels(ax):
            if lbl is not None and lbl.get_text().strip():
                add('axislabel', lbl, ax)
        # ⛔ 必须走 _onscreen_tick_labels 过滤【轴范围外的幽灵刻度】：
        #   matplotlib 会为 xlim 之外的位置也生成 Text 对象（如 xlim=(0,1) 时
        #   仍有 '-0.2' / '1.2'），它们不显示但 get_window_extent 照样返回
        #   画布外的 bbox。用 get_xticklabels() 全取会把它们算进"出画布/互撞"，
        #   实测污染出 3 个假越界（-0.2 左超 76px、1.2 右超 220px），
        #   直接导致 _autofit_fontsize 的打分失真、收放决策跑偏。
        for t in _onscreen_tick_labels(ax):
            if t.get_visible() and t.get_text().strip():
                add('tick', t, ax)
        for t in ax.texts:
            if t.get_visible() and t.get_text().strip():
                add('anno', t, ax)
        lg = ax.get_legend()
        if lg is not None and lg.get_visible():
            for t in lg.get_texts():
                if t.get_text().strip():
                    add('legend', t, ax)
            add('legend', lg.get_title(), ax)
    # Figure-level legends are used by ``shared_legend``.  Older sizing and
    # contrast passes only inspected axes legends, which let a dedicated
    # legend panel silently fall below the final print-size floor.
    for lg in getattr(fig, 'legends', ()):
        if lg is None or not lg.get_visible():
            continue
        for t in lg.get_texts():
            add('legend', t, None)
        add('legend', lg.get_title(), None)
    for t in fig.texts:
        add('figtext', t, None)
    return got


def _weighted_text_percentile(roles, q=0.10):
    """Return a character-weighted source font percentile in points."""
    import math

    samples = []
    for _role, obj, _ax in roles:
        try:
            value = float(obj.get_fontsize())
            weight = len(''.join(str(obj.get_text()).split()))
        except Exception:
            continue
        if math.isfinite(value) and value > 0 and weight > 0:
            samples.append((value, weight))
    if not samples:
        return None
    samples.sort(key=lambda item: item[0])
    target = max(1, int(np.ceil(sum(weight for _, weight in samples) * float(q))))
    seen = 0
    for value, weight in samples:
        seen += weight
        if seen >= target:
            return value
    return samples[-1][0]


def _ensure_final_print_font(fig):
    """Raise source text sizes when paper placement would make them illegible.

    This closes a gap in the former auto-fit path: a clean 12-inch source
    canvas with 10 pt labels had no *source* overlap, so auto-fit returned early
    even though those labels became roughly 5 pt after insertion.  We now judge
    the same character-weighted 10th percentile used by the final PDF gate.

    Only upward scaling is allowed.  If the required scale is extreme, fail
    early and ask the figure author to reduce/restructure the canvas rather than
    manufacture a fragile wall of oversized text.
    """
    import math

    if _has_3d_axes(fig):
        return 0.0
    # Locators format logarithmic/scientific tick labels lazily.  Materialize
    # them before collecting text roles; otherwise a direct helper call made
    # before the first draw can miss superscripts that will later render at a
    # reduced mathtext size.
    try:
        fig.canvas.draw()
    except Exception:
        pass
    roles = _fig_text_roles(fig)
    source_p10 = _weighted_text_percentile(roles)
    if source_p10 is None:
        return 0.0
    try:
        source_width = float(fig.get_figwidth())
    except Exception:
        return 0.0
    if not math.isfinite(source_width) or source_width <= 0:
        return 0.0
    display_width = _paper_display_width_in(fig)
    scale_to_paper = min(1.0, display_width / source_width)
    spec = getattr(fig, '_mh_paper_placement', None) or {}
    target = float(spec.get('min_font_pt', NATURE_TARGET_PT))
    final_p10 = source_p10 * scale_to_paper
    factor = max(1.0, target / max(final_p10, 1e-9))
    if not math.isfinite(factor) or factor > 2.75:
        raise RuntimeError(
            "原生画布相对论文插入尺寸过大，字号需放大超过 2.75 倍才能达到 "
            f"{target:.1f} pt。请收窄画布、减少面板/标注或拆图。"
        )
    # The PDF gate sees rendered glyph spans, not only Matplotlib Text objects.
    # Long-label repairs may reduce just one axis label while the weighted p10
    # remains healthy; mathtext also renders superscripts/subscripts at ~70%
    # of the owning Text size.  Enforce an object-level floor and compensate
    # for reduced math glyphs so no isolated label slips below print size.
    source_floor = target / max(scale_to_paper, 1e-9)
    changed = False
    max_ratio = 1.0
    for _role, obj, _ax in roles:
        try:
            current = float(obj.get_fontsize())
            text = str(obj.get_text())
            required = source_floor
            if any(token in text for token in ('^{', '_{', r'\frac', r'\dfrac', r'\tfrac')):
                required /= 0.70
            new_size = max(current * factor, required)
            if new_size > current + 1e-6:
                obj.set_fontsize(new_size)
                changed = True
                max_ratio = max(max_ratio, new_size / max(current, 1e-9))
        except Exception:
            pass
    fig._mh_final_font_scale = max_ratio
    fig._mh_final_font_pt = max(target, source_p10 * factor * scale_to_paper)
    return max_ratio if changed else 0.0


def _autofit_base_pt(fig):
    """按画布尺寸反解基准字号（与 nature 反解同一套公式，但对所有配色生效）。

    依据：图会被缩到论文页宽（docx 上限 5.5in / LaTeX 按长宽比分档），
    画时字号 × 缩放比 = 上页字号，要让上页恒为 NATURE_TARGET_PT(8.25pt)。
    """
    try:
        w, h = float(fig.get_figwidth()), float(fig.get_figheight())
    except Exception:
        return NATURE_TARGET_PT
    return nature_font_pt(w, h)


# ⛔ 这里曾有一张 `_ROLE_RC_KEY`（角色 → rcParams 键）表，配合 `_is_explicit_pt`
#   想区分"脚本显式写的字号"与"继承默认值的字号"。**已删除，那条路不可用**：
#   `setup_style()` 把 axes.titlesize 设成 13.0，正好等于规范脚本会写的值，
#   两种情况数值相同、分辨不出（matplotlib 的 Text 不记录字号来源）。
#   现在 `_autofit_fontsize` 改用"这张图有没有真问题（重叠 / 破 8pt）"当判据。


def _apply_role_pt(roles, base, orig):
    """按角色比例写字号。orig 是 {id(obj): 原始字号}，用于保住组内相对大小。

    ⛔ 同一角色内可能本来就有多档（比如作者刻意把某个标注写大以强调），
       所以不是一刀切成同一个值，而是【按原值在该角色内的相对位置】映射，
       整组一起缩放 —— 既统一体系，又不抹掉作者的强调意图。
    """
    by_role = {}
    for role, obj, _ax in roles:
        by_role.setdefault(role, []).append(obj)

    def _quant(pt):
        """量化到 0.5pt 阶梯 —— 字号种类必须收敛，否则"体系乱"没治好。

        ⛔ 第一版用连续映射（原值线性映射到 target±10%），结果一张图出 8 种字号，
           跟修之前的 14 种没本质区别。离散阶梯才能真正收敛。
        """
        pt = max(_AUTOFIT_MIN, min(_AUTOFIT_MAX, pt))
        return round(round(pt * 2) / 2, 2)

    for role, objs in by_role.items():
        target = base * _ROLE_RATIO.get(role, 1.0)
        vals = [orig.get(id(o), target) for o in objs]
        lo, hi = min(vals), max(vals)
        # 组内原值差异 <15% → 全组统一；差异大 → 只分两档（保住"强调"意图，
        # 但不再逐个原值各给一档）
        split = (hi - lo) > lo * 0.15 if lo > 0 else False
        mid = (lo + hi) / 2.0
        for o in objs:
            v = orig.get(id(o), target)
            if not split:
                pt = _quant(target)
            else:
                pt = _quant(target * (1.10 if v >= mid else 0.95))
            try:
                o.set_fontsize(pt)
            except Exception:
                pass


def _overlap_score(fig, roles):
    """实测遮挡打分（越小越好）。返回 (总分, 明细dict)。

    权重按"多难看/多损失信息"排：出画布=信息丢失最重，其次互撞，再次出 axes。
    """
    try:
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
    except Exception:
        return 1e9, {}
    W, H = fig.bbox.width, fig.bbox.height
    bbs, metas = [], []
    for role, obj, ax in roles:
        try:
            bbs.append(obj.get_window_extent(renderer=r))
            metas.append((role, ax))
        except Exception:
            pass
    d = {'clash': 0, 'clip': 0, 'out_ax': 0}
    for i in range(len(bbs)):
        for j in range(i + 1, len(bbs)):
            # 同一 axes 的 tick 之间、tick 与轴标签之间都算撞
            if bbs[i].overlaps(bbs[j]):
                d['clash'] += 1
    for (role, ax), b in zip(metas, bbs):
        if b.x0 < -0.5 or b.x1 > W + 0.5 or b.y0 < -0.5 or b.y1 > H + 0.5:
            d['clip'] += 1
        if ax is not None and role in ('anno',):
            try:
                axb = ax.get_window_extent(renderer=r)
                if (b.x0 < axb.x0 - 1 or b.x1 > axb.x1 + 1
                        or b.y0 < axb.y0 - 1 or b.y1 > axb.y1 + 1):
                    d['out_ax'] += 1
            except Exception:
                pass
    score = d['clip'] * 10 + d['clash'] * 3 + d['out_ax'] * 1
    return score, d


def _autofit_fontsize(fig):
    """自适应字号：按画布定基准 → 实测 → 撞了就收、没撞且有余量就放。

    ⛔ 为什么要实测闭环，不能只靠公式：公式只知道画布多大，不知道
       "这张图上有 8 个中文标签挤在 3.6 寸宽里"。实测天府杯 C 题 15 张图
       脚本手写 128 处 fontsize、14 种字号（6.5~16pt，7 处低于印刷线），
       就是 AI 靠公式算不出来、只能逐处试出来的产物。
    ⛔ 底线 8.0pt 不可破（最终印刷可读线，与 screenshot_capture.MIN_FONT_PT 一致）；
       宁可留一点重叠，也不把字缩到看不清 —— 之前"字缩到 4.5pt"就是这么来的。
    ⛔ 3D 轴豁免：字号变化会连带 tight_layout/set_position，挤塌曲面。
    """
    if _has_3d_axes(fig):
        return
    roles = _fig_text_roles(fig)
    if not roles:
        return
    orig = {}
    for _role, obj, _ax in roles:
        try:
            orig[id(obj)] = float(obj.get_fontsize())
        except Exception:
            pass
    if not orig:
        return

    def snap():
        return {id(o): o.get_fontsize() for _r, o, _a in roles
                if id(o) in orig}

    def restore(s):
        for _r, o, _a in roles:
            if id(o) in s:
                try:
                    o.set_fontsize(s[id(o)])
                except Exception:
                    pass

    base0 = _autofit_base_pt(fig)
    before_score, _ = _overlap_score(fig, roles)
    before_snap = snap()

    # ★★ 保守模式判定：脚本已经逐处手写过字号（种类多、且普遍偏小）时，
    #   【只抬破线的那些，不做全图统一】。
    # ⛔ 血的教训：全图统一到画布基准，在 fig_q1_coverage_cmp 上把 31 处 6.6pt
    #    抬高后字会变宽，若不同时重排就可能显著增加标注互撞和出界。
    #    那 31 处小字是 AI 为了"塞得进去"才缩的，抬回去就必然撞 —— 除非同时
    #    加大画布或删标注，而这两件引擎都做不到（画布尺寸由脚本定）。
    #    所以：可读性底线（8pt）必须守，密度过高时应重排，不能继续压字。
    _vals = sorted(orig.values())
    _kinds = len({round(v, 1) for v in _vals})
    _tiny_n = sum(1 for v in _vals if v < _AUTOFIT_MIN - 1e-9)

    # ★★★ 尊重显式字号：脚本自己写了字号的元素，引擎不许改（除非破 8pt 印刷线）。
    #
    # ⛔⛔ 为什么必须加这道分流（用户实测反馈"图变丑了"，逐条量出来的）：
    #   原来的 conservative 判据是 `_kinds >= 4 and _tiny_n > 0` —— 两个条件**都**要
    #   满足才尊重脚本。于是一个**写得规范**的脚本（3 种字号、都不破线）两个条件一个
    #   都不满足，掉进下面的"全图统一"分支，字号被全盘重写：
    #       标题 13 → 11.5（小画布上→8.5）、刻度 8.5 → 9.5、图例 8.5 → 9.5
    #   标题被压小、刻度被放大，**标题/刻度层级从 1.53× 塌到 1.21×** —— 全图字一样大，
    #   这就是"平、土、没层次"的观感来源。
    #   更反过来的是：AI 乱试出来的一堆小字号（种类多、有破线）反而能进保守模式被尊重。
    #   **脚本写得越规范越会被推翻**，逻辑正好反了。
    #
    # ⛔⛔ 闸的判据是"**这张图有没有真问题**"，不是"字号是谁写的"。
    #
    #   我先试过按"脚本显式写的 vs 继承 rcParams 默认值"分流，**那条路走不通**：
    #   `setup_style()` 把 axes.titlesize 设成 **13.0** —— 正好是规范脚本会写的值
    #   （也是 figure_style_guide 推荐表里的值）。于是"显式写 13"和"继承默认 13"
    #   数值完全相同，`get_fontsize()` 分辨不出来（matplotlib 的 Text 不记录来源）。
    #   撞车不是罕见边角，而是**默认情形**，这个判据从根上不可用。
    #
    #   真正该问的是：图上**有没有文字重叠**、**有没有字小到看不清**。两个都没有，
    #   就说明现在这套字号是好的，引擎一个字都不该动 ——
    #   实测 setup_style 的默认值给出 13/10 = 1.30× 的层级本来就合理，可引擎照样
    #   把 **18/18 个元素**全改了，压到 1.18~1.22×（标题变小、刻度变大），
    #   这就是用户说的"图变丑了"。
    only_tiny = [obj for _r, obj, _a in roles
                 if (orig.get(id(obj)) or 99) < _AUTOFIT_MIN - 1e-9]
    if before_score <= 0 and not only_tiny:
        # 没重叠、没破线 → 完全不介入，保住脚本/样式表定下的字号层级
        globals()['_LAST_AUTOFIT_PT'] = None
        return
    if before_score <= 0 and only_tiny:
        # 只有"字太小"这一个问题 → 只抬那几个，别动其余（动了就会打乱层级）
        raised = 0
        for obj in only_tiny:
            try:
                obj.set_fontsize(_AUTOFIT_MIN)
                raised += 1
            except Exception:
                pass
        # 抬完反而撞了 → 整体退回（不做恶）
        sc_now, _ = _overlap_score(fig, roles)
        if raised and sc_now > before_score:
            restore(before_snap)
        globals()['_LAST_AUTOFIT_PT'] = None
        return

    conservative = (_kinds >= 4 and _tiny_n > 0)
    if conservative:
        # 保守模式仍要做【两头收】：破线的抬上来、明显超画布基准的压下去。
        # ⛔ 上限必须用【画布反解基准】而不是固定 13pt：
        #   默认配色 elegant 的 legend.fontsize 固定 10pt、不看画布，在
        #   fig_q1_coverage_cmp（57 个文字挤一张 6 寸图）上 10 处 10pt 撞出 13 对；
        #   同一张图 nature 走反解压到 7.x，只撞 3 对。固定 13pt 的上限拦不住 10pt。
        hi_cap = max(_AUTOFIT_MIN + 1.0, min(_AUTOFIT_MAX, base0 * 1.10))
        for _role, obj, _ax in roles:
            v = orig.get(id(obj))
            if v is None:
                continue
            if v < _AUTOFIT_MIN - 1e-9:
                try:
                    obj.set_fontsize(_AUTOFIT_MIN)
                except Exception:
                    pass
            elif v > hi_cap + 1e-9:
                try:
                    obj.set_fontsize(round(round(hi_cap * 2) / 2, 2))
                except Exception:
                    pass
        best_score, _ = _overlap_score(fig, roles)
        best_snap = snap()
        # ★★ 保守模式也必须有【实测闭环】：
        # ⛔ 反解只算"画布缩到页宽后字多大"，完全不知道"这张图上挤了多少字"。
        #    实测 fig_q1_coverage_cmp 画布 6.2 寸 → 反解 base0=8.45pt 是对的，
        #    但那张图 57 个文字挤在一起，8.45pt 装不下 —— 光压上限只把 10.0
        #    降到 9.5，撞的对数几乎没变（13 对）。必须整体往下收到不撞为止。
        # ⛔ 收的是【当前值的等比例】而不是重设基准 —— 保守模式的前提就是
        #    尊重脚本的相对字号关系，等比例缩放不破坏它。
        if best_score > 0:
            cur = snap()
            for _ in range(5):
                nxt = {k: v * 0.94 for k, v in cur.items()}
                if min(nxt.values()) < _AUTOFIT_MIN - 1e-9:
                    # 到底线了：把所有低于底线的钉在底线，再试一次就收手
                    nxt = {k: max(_AUTOFIT_MIN, v) for k, v in nxt.items()}
                    if all(abs(nxt[k] - cur[k]) < 0.01 for k in cur):
                        break
                restore(nxt)
                cur = nxt
                sc, _ = _overlap_score(fig, roles)
                if sc < best_score:
                    best_score, best_snap = sc, snap()
                if sc == 0:
                    break
            restore(best_snap)
        # 不做恶：整轮下来仍比脚本原样更差就还原
        sc_now, _ = _overlap_score(fig, roles)
        if sc_now > before_score:
            restore(before_snap)
        globals()['_LAST_AUTOFIT_PT'] = None
        return

    # ① 先按画布基准统一一遍
    _apply_role_pt(roles, base0, orig)
    best_score, _ = _overlap_score(fig, roles)
    best_snap = snap()
    best_base = base0

    # ② 撞了 → 逐步收（每轮 ×0.94，最多 4 轮，不破 8pt）
    if best_score > 0:
        base = base0
        for _ in range(4):
            nxt = base * 0.94
            if nxt * min(_ROLE_RATIO.values()) < _AUTOFIT_MIN:
                break
            base = nxt
            _apply_role_pt(roles, base, orig)
            sc, _ = _overlap_score(fig, roles)
            if sc < best_score:
                best_score, best_snap, best_base = sc, snap(), base
            if sc == 0:
                break
    # ③ 没撞且基准还有余量 → 试着放大（更好读），一旦撞就退回
    elif base0 < _AUTOFIT_MAX:
        base = base0
        for _ in range(2):
            nxt = min(base * 1.08, _AUTOFIT_MAX)
            if nxt <= base + 0.01:
                break
            base = nxt
            _apply_role_pt(roles, base, orig)
            sc, _ = _overlap_score(fig, roles)
            if sc > 0:
                break
            best_snap, best_base = snap(), base

    restore(best_snap)
    # ④ 不做恶：自适应后反而更差 → 先退到"只抬破线的那几处"，再不行才全退。
    # ⛔ 不能直接全退：全图统一会把本来合规的元素一起抬高，
    #    字变宽必然多撞几处 → 触发全退 → 连破线的 3 处 6.8pt 也一起退回去了
    #    （实测 fig_q1_p0_vs_sensitivity 就是这样留下 3 处小字）。
    #    只抬破线的那几处，宽度增加最小，多半能保住底线又不新增重叠。
    sc_now, _ = _overlap_score(fig, roles)
    if sc_now > before_score:
        restore(before_snap)
        floor_only = {}
        for _role, obj, _ax in roles:
            v = orig.get(id(obj))
            if v is None:
                continue
            floor_only[id(obj)] = max(_AUTOFIT_MIN, min(_AUTOFIT_MAX, v))
        if any(abs(floor_only[k] - before_snap.get(k, floor_only[k])) > 0.01
               for k in floor_only):
            restore(floor_only)
            sc2, _ = _overlap_score(fig, roles)
            if sc2 > before_score:
                restore(before_snap)     # 连"只抬破线"都变差，才真的全退
    else:
        globals()['_LAST_AUTOFIT_PT'] = round(best_base, 2)


_LAST_AUTOFIT_PT = None


def _collect_clipped(fig, r):
    """收集所有「超出 figure 边界」的对象。返回 [(kind, obj, ax, over_dict)]。

    ⛔ 为什么必须查：本项目 `_save` 固定 `bbox_inches=None`（等大裁剪，
       防 axes 外文字把 PDF mediabox 撑爆 —— 实测出过 1496×23966px 超长条）。
       代价是【超出 figure 的东西被画布边缘直接切掉，输出里完全看不见】
       = 信息丢失，比遮挡更糟。
    ⛔ 实测天府杯 C 题 15 张图有 6 个对象越界，三类根因（都不是轴标签，
       所以 `_fix_axis_label_overflow` 抓不到）：
         ① legend 用 bbox_to_anchor 推到 axes 外
            gen_q3_figs.py:71  bbox_to_anchor=(0.5, -0.30) → 往下超 237px
            gen_q3_figs.py:198 bbox_to_anchor=(1.05, 1.32) → 往上超 40px
         ② colorbar 的 cb.set_label(...) 在色条右侧 → 往右超 61px / 31px
         ③ 刻度标签 / panel 标号轻微越界（≤5px）
    """
    W, H = fig.bbox.width, fig.bbox.height
    axes = list(fig.get_axes())
    out = []

    def add(kind, obj, ax):
        try:
            b = obj.get_window_extent(renderer=r)
        except Exception:
            return
        ov = {'left': max(0.0, -b.x0), 'right': max(0.0, b.x1 - W),
              'bottom': max(0.0, -b.y0), 'top': max(0.0, b.y1 - H)}
        if max(ov.values()) > 0.5:
            out.append((kind, obj, ax, ov))

    for ax in axes:
        if not ax.get_visible():
            continue
        lg = ax.get_legend()
        if lg is not None and lg.get_visible():
            add('legend', lg, ax)
        # colorbar 的 label 挂在色条 axes 的 y/x 轴上
        for lbl in _visible_axis_labels(ax):
            if lbl is not None and lbl.get_visible() and lbl.get_text().strip():
                add('axislabel', lbl, ax)
        for title in _axes_titles(ax):
            if title.get_visible() and title.get_text().strip():
                add('title', title, ax)
        for t in _onscreen_tick_labels(ax):
            if t.get_visible() and t.get_text().strip():
                add('tick', t, ax)
        for t in ax.texts:
            if t.get_visible() and t.get_text().strip():
                add('anno', t, ax)
    for t in fig.texts:
        if t.get_visible() and t.get_text().strip():
            add('figtext', t, None)
    return out


def _worst_over(fig, r):
    """四个方向各自的最大越界像素"""
    tot = {'left': 0.0, 'right': 0.0, 'bottom': 0.0, 'top': 0.0}
    for _k, _o, _ax, ov in _collect_clipped(fig, r):
        for d, v in ov.items():
            if v > tot[d]:
                tot[d] = v
    return tot


def _fix_clipped_outside(fig):
    """把被画布切掉的对象救回来：按方向收缩【所有】axes 腾出空间。

    ⛔ 为什么收缩 axes 而不是挪对象：
       - legend 用 bbox_to_anchor 时位置是 axes 比例，收缩 axes 会带着它一起进来；
         直接改 legend 的 loc 会把作者刻意的"图例放图外"版式改掉。
       - colorbar label 挂在色条 axes 上，收缩色条 axes 同样带它左移。
       所以统一用"腾空间"，不动任何对象自己的位置参数。
    ⛔ 必须【全体 axes 一起收】：只收越界那一个会把多 panel 图的对齐关系搞乱
       （panel 宽度不一致，肉眼一眼就看出来）。
    ⛔ 3D 轴整体豁免：set_position 会把 3D 曲面挤塌（已踩过）。
    """
    if _has_3d_axes(fig):
        return
    try:
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
    except Exception:
        return
    if not _collect_clipped(fig, r):
        return

    W = max(fig.bbox.width, 1.0)
    H = max(fig.bbox.height, 1.0)

    # ── ① 先处理 fig.text ──
    # ⛔ fig.text 用【figure 坐标】，收缩 axes 对它完全无效 —— 必须直接挪它自己。
    #   实测 gen_q1_figs 的 panel 标号 fig.text(0.012, 0.965, 'a') 往上超 4.6px，
    #   收缩 axes 那套跑完它仍然越界（本函数第一版的盲区）。
    for t in list(fig.texts):
        if not (t.get_visible() and t.get_text().strip()):
            continue
        try:
            b = t.get_window_extent(renderer=r)
        except Exception:
            continue
        dx = dy = 0.0
        if b.x1 > W:
            dx = -(b.x1 - W + 2.0)
        if b.x0 < 0:
            dx = -b.x0 + 2.0
        if b.y1 > H:
            dy = -(b.y1 - H + 2.0)
        if b.y0 < 0:
            dy = -b.y0 + 2.0
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            continue
        try:
            x, y = t.get_position()
            # fig.text 的 transform 默认就是 transFigure（0-1 比例）
            t.set_position((x + dx / W, y + dy / H))
        except Exception:
            pass
    try:
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
    except Exception:
        return
    if not _collect_clipped(fig, r):
        return

    # ── ② 其余对象：收缩 / 平移 axes 腾空间 ──
    axes = [ax for ax in fig.get_axes() if ax.get_visible()]
    if not axes:
        return
    # 原始位置留底：任何一步让情况变差就整体还原（不做恶）
    orig = [(ax, ax.get_position().frozen()) for ax in axes]
    base = _worst_over(fig, r)
    base_sum = sum(base.values())

    PAD = 3.0          # 额外留 3px，避免修到刚好贴边又被反复触发
    # 窄条判定阈值：colorbar 实测 0.0256（fraction=0.046），普通 panel ≥0.2
    MAX_TOTAL = 0.24   # 单方向累计最多让 24% figure
    per_dir = {'left': 0.0, 'right': 0.0, 'bottom': 0.0, 'top': 0.0}

    for _ in range(4):
        ov = _worst_over(fig, r)
        if max(ov.values()) <= 0.5:
            break
        moved = False
        for d in ('left', 'right', 'bottom', 'top'):
            need_px = ov[d]
            if need_px <= 0.5:
                continue
            span = W if d in ('left', 'right') else H
            need = (need_px + PAD) / span
            room = MAX_TOTAL - per_dir[d]
            if room <= 0.001:
                continue
            step = min(need, room, 0.10)     # 每轮每方向最多让 10%
            if step <= 0.001:
                continue
            ok = True
            newpos = []
            for ax in axes:
                p = ax.get_position()
                x0, y0, w, h = p.x0, p.y0, p.width, p.height
                # ⛔⛔ 窄条 axes（colorbar）必须【平移】不能【收窄】：
                #   ① 收窄会把色条越改越细，视觉上直接错（色条本来就该是细长条）
                #   ② 实测 colorbar 宽仅 0.0256，减 step 0.009 后 0.0165 会撞上
                #      "w<=0.02" 的退化保护 → ok=False → 整个方向被跳过、
                #      越界一点没修（BUG-07b 就是这么 FAIL 的）
                #   平移则宽度不变，右边缘同样左移 step，与主图收窄后的边缘对齐一致。
                narrow_x = w < _NARROW_AXES_FRAC
                narrow_y = h < _NARROW_AXES_FRAC
                if d == 'left':
                    if narrow_x:
                        x0 = x0 + step
                    else:
                        x0, w = x0 + step, w - step
                elif d == 'right':
                    if narrow_x:
                        x0 = x0 - step
                    else:
                        w = w - step
                elif d == 'bottom':
                    if narrow_y:
                        y0 = y0 + step
                    else:
                        y0, h = y0 + step, h - step
                else:
                    if narrow_y:
                        y0 = y0 - step
                    else:
                        h = h - step
                # 绘图区不得压到原来的 50% 以下，否则宁可留着越界。
                # 窄条走平移、尺寸不变，天然不触发；且不能拿 0.02 绝对值卡它。
                if w < p.width * 0.5 or h < p.height * 0.5:
                    ok = False
                    break
                if (not narrow_x and w <= 0.02) or (not narrow_y and h <= 0.02):
                    ok = False
                    break
                # 平移不能把 axes 推出画布
                if x0 < -0.02 or y0 < -0.02 or x0 + w > 1.02 or y0 + h > 1.02:
                    ok = False
                    break
                newpos.append((ax, [x0, y0, w, h]))
            if not ok:
                continue
            for ax, box in newpos:
                ax.set_position(box)
            per_dir[d] += step
            moved = True
        if not moved:
            break
        try:
            fig.canvas.draw()
            r = fig.canvas.get_renderer()
        except Exception:
            break

    # 不做恶：越界总量没改善就整体还原
    try:
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        after = sum(_worst_over(fig, r).values())
        if after > base_sum - 0.5:
            for ax, p in orig:
                ax.set_position(p)
            fig.canvas.draw()
    except Exception:
        pass


def _save(fig, output):
    """保存图表到指定路径。savefig hook 会自动检测并修复文字重叠。

    PNG 输出强制 350 DPI（与 docx_export PDF→PNG 兜底链路一致），防止 Word 嵌入时中文标签糊。
    PDF/SVG 矢量输出不受 DPI 影响。
    """
    # ★ 子图尺寸防护：检测子图是否被压缩得过小，如果是则修复
    _guard_subplot_size(fig)
    # ★ 无条件拉回 ax.text(transAxes, y<0 or y>1) 反模式（防 bbox=tight mediabox 爆炸）
    _pull_back_outside_transaxes_text(fig)
    # ★ 3D 轴不做 tight_layout；启用了 constrained/compressed layout 或显式声明
    #   _mh_manual_layout 的复杂图也不得再调用 tight_layout。后者会关闭 constrained
    #   layout，并把专用 colorbar/legend 轴重新挤回数据区，正是多面板遮挡的根因。
    try:
        _layout_engine = fig.get_layout_engine()
    except Exception:
        _layout_engine = None
    _manual_layout = bool(getattr(fig, '_mh_manual_layout', False))
    if not _has_3d_axes(fig) and _layout_engine is None and not _manual_layout:
        try:
            fig.tight_layout(pad=0.5)
        except Exception:
            pass
    # ★ tight_layout 后再检查一次，防止 tight_layout 把子图压小
    _guard_subplot_size(fig)
    # ★ axes 内容占比检测：若所有 axes 占 figure 面积 < 50%，自动收缩 figsize
    # 防止 "figsize=(10, 12) 但只画了上面 2 个小 panel，下面 8 寸全白" 这种产物
    _auto_shrink_figsize_if_sparse(fig)
    # ⛔ 轴标签出界修复【不在这里做】—— 移到 _hook_savefig 的最后一步。
    #   放这里会被 hook 里的 _guard_subplot_size 重置 margins 覆盖掉（实测无效）。
    # ★ 空 / 仅空白 路径直接拒绝（避免兜底成隐藏文件 ".pdf"）
    if not output or not str(output).strip():
        raise ValueError("save_fig: output path is empty")
    output = str(output)  # 容 pathlib.Path
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else '.', exist_ok=True)
    # ★ 扩展名兜底：matplotlib.savefig 拿到未知 format（如 'fig_lollipop'）会 raise ValueError。
    # 历史配方里有大量 save_fig(fig, 'figures/fig_xxx') 不带扩展名的写法 —— 自动追加 .pdf（论文场景首选矢量格式）。
    _SUPPORTED_FMTS = ('pdf', 'png', 'svg', 'jpg', 'jpeg', 'eps', 'ps', 'tif', 'tiff', 'webp')
    _basename = os.path.basename(output)
    _maybe_ext = _basename.rsplit('.', 1)[-1].lower() if '.' in _basename else ''
    if _maybe_ext in _SUPPORTED_FMTS:
        _ext = _maybe_ext
    else:
        # 无扩展名 / 不是图像格式（如 'fig.v2'）→ 追加 .pdf
        _ext = 'pdf'
        output = output + '.pdf'
    _save_kwargs = {'format': _ext, 'pad_inches': 0.15}
    # ★ 默认不用 bbox_inches='tight' —— 防止 ax.text(transAxes, y<0 or y>1) 这种
    # axes 外标注让 tight 包围盒爆炸（用户实测过 1496×23966 px 超长条 PNG）。
    # 改用 figsize 等大输出 + _auto_shrink_figsize_if_sparse 把 axes 推到撑满 figure 80%，
    # 既保证 axes label 不被截，又避免 mediabox 爆炸。
    _save_kwargs['bbox_inches'] = None
    if _ext in ('png', 'jpg', 'jpeg'):
        _save_kwargs['dpi'] = 350  # 防中文标签糊（与 docx_export PDF→PNG 兜底链路一致）
    # ★ 成品自检：静态闸扫不出的"边距被撑爆"，在这里实测拦一道（只提示，不阻塞）
    _warn_if_wasted_margin(fig, output)
    # ★ 成品自检：数据被轴范围裁掉（坐标系约定写错，静态扫不出来），同样实测拦一道
    _warn_if_data_clipped(fig, output)
    # ★ 成品自检：字号体系是否失控（逐处手写 fontsize= 的典型症状）
    _warn_if_font_chaos(fig)
    fig.savefig(output, **_save_kwargs)
    _get_plt().close(fig)
    print(f'Saved: {output}')


def _onscreen_tick_labels(ax, which='both'):
    """返回该 axes 上真正落在轴范围内的主刻度标签（Text 对象列表）。

    which: 'both' | 'x' | 'y'，只取对应轴的刻度。

    matplotlib 会为超出 xlim/ylim 的刻度保留 Text 对象——对数轴尤其常见：
    xlim=[10, 2700] 时 10^0（x=1）的刻度对象依然存在，只是不绘制。这种
    "幽灵刻度"的 window_extent 算出来远在画布左侧（实测可达 -457 px），
    若拿去做"标签被画布切掉"的判定，会误判成越界，进而把左边距一路加大
    到封顶值，图上就出现大片空白。

    过滤办法：在轴自身的变换空间里比较（log 轴即 log 空间），只保留位置落在
    [lo, hi] ±0.5% 跨度内的刻度。测不出来时保守保留，维持原有行为。
    """
    # set_axis_off() does not change each Text object's visible flag. Those
    # unpainted ticks must not shrink/reposition a dedicated legend cell.
    if not ax.get_visible() or not getattr(ax, 'axison', True):
        return []
    # ★ 3D 轴：刻度标签落在投影平面上，get_position() 不是数据坐标，与 xlim/ylim
    #   比对无意义（实测越界量会算出上千万像素的垃圾值）。调用方本就豁免 3D，
    #   这里再兜一层，防止将来别处误用。
    try:
        if getattr(ax, 'name', '') == '3d' or hasattr(ax, 'get_zlim'):
            return []
    except Exception:
        pass

    out = []
    pairs = ((ax.xaxis, True), (ax.yaxis, False))
    if which == 'x':
        pairs = pairs[:1]
    elif which == 'y':
        pairs = pairs[1:]
    for axis, is_x in pairs:
        if not axis.get_visible():
            continue
        try:
            labels = [t for t in axis.get_ticklabels() if t.get_visible() and t.get_text()]
        except Exception:
            continue
        if not labels:
            continue
        # 轴的 scale 变换（log/linear/symlog…），把范围判定统一到线性空间
        bounds = None
        try:
            tr = axis.get_transform()
            lo, hi = ax.get_xlim() if is_x else ax.get_ylim()
            a, b = (float(v) for v in np.asarray(tr.transform([lo, hi])).ravel()[:2])
            if b < a:
                a, b = b, a
            span = b - a
            if np.isfinite(a) and np.isfinite(b) and span > 0:
                tol = 0.005 * span
                bounds = (a - tol, b + tol)
        except Exception:
            bounds = None
        if bounds is None:
            out.extend(labels)  # 拿不到范围就不过滤，保持旧行为
            continue
        for t in labels:
            try:
                pos = t.get_position()
                loc = float(pos[0] if is_x else pos[1])
                v = float(np.asarray(tr.transform([loc])).ravel()[0])
                if not np.isfinite(v):
                    continue  # 非法位置（如 log 轴上的 ≤0）必然不显示
                if bounds[0] <= v <= bounds[1]:
                    out.append(t)
            except Exception:
                out.append(t)  # 测量失败时保守保留
    return out


def _ensure_ticklabels_visible(fig):
    """Reserve room for clipped ticks in legacy, unmanaged 2D layouts.

    Constrained/compressed and explicitly manual layouts own their margins.
    Settle the active renderer first; their remaining canvas overflow is handled
    by the final whole-figure clipping pass, not per-axis margin mutations.
    """
    if _has_3d_axes(fig):
        return
    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        engine = fig.get_layout_engine()
    except Exception:
        return
    if engine is not None or bool(getattr(fig, '_mh_manual_layout', False)):
        return

    fig_w_px, fig_h_px = fig.get_size_inches() * fig.dpi
    if fig_w_px <= 0 or fig_h_px <= 0:
        return

    axes = [ax for ax in fig.get_axes()
            if ax.get_visible() and not ax.get_label().startswith('_')]
    if not axes:
        return

    # 统计所有 axes 的刻度标签超出 figure 下边缘/左边缘的最大像素量
    overflow_bottom_px = 0.0
    overflow_left_px = 0.0
    for ax in axes:
        # 只统计落在轴范围内的刻度：轴外的"幽灵刻度"（如 log 轴 xlim=[10,2700]
        # 时残留的 10^0）不会被绘制，却会被误判成越界并撑爆左边距
        try:
            labels = _onscreen_tick_labels(ax)
        except Exception:
            continue
        for t in labels:
            try:
                bb = t.get_window_extent(renderer=renderer)
            except Exception:
                continue
            # figure 坐标系：y=0 在底部，x=0 在左侧
            if bb.y0 < 0:
                overflow_bottom_px = max(overflow_bottom_px, -bb.y0)
            if bb.x0 < 0:
                overflow_left_px = max(overflow_left_px, -bb.x0)

    if overflow_bottom_px <= 1 and overflow_left_px <= 1:
        return  # 没有标签越界，无需处理

    # 换算成 figure 比例，加 1.5% 安全余量
    extra_bottom = overflow_bottom_px / fig_h_px + 0.015
    extra_left = overflow_left_px / fig_w_px + 0.015

    sp = fig.subplotpars
    new_bottom = min(0.45, sp.bottom + extra_bottom)  # 封顶 0.45，防止 axes 被压没
    new_left = min(0.40, sp.left + extra_left)
    # ⚠ 撞顶是异常信号：正常图的标签越界量顶多几十像素，需要 40% 图宽当左边距
    # 说明测量被污染了（历史真实案例：对数轴外的幽灵刻度被算成越界 457px）。
    # 不静默放过，打一行提示便于定位。
    if sp.left + extra_left > 0.40 or sp.bottom + extra_bottom > 0.45:
        print(f"[plot_utils] WARNING 标签越界兜底撞到封顶: "
              f"left {sp.left:.3f}+{extra_left:.3f} bottom {sp.bottom:.3f}+{extra_bottom:.3f} "
              f"(越界实测 左{overflow_left_px:.0f}px 下{overflow_bottom_px:.0f}px) "
              f"—— 若图上出现大片空白，检查是否有轴外刻度/离屏文字污染测量")
    # 保证 bottom < top、left < right，避免非法布局
    new_bottom = min(new_bottom, sp.top - 0.15)
    new_left = min(new_left, sp.right - 0.15)

    applied = False
    try:
        fig.subplots_adjust(
            bottom=max(sp.bottom, new_bottom),
            left=max(sp.left, new_left),
        )
        applied = True
    except Exception:
        applied = False

    # subplots_adjust 对手动布局（add_axes/GridSpec）无效时，直接平移+压缩 axes position
    if not applied or overflow_bottom_px > 2 or overflow_left_px > 2:
        # 重新实测：subplots_adjust 生效后可能已解决
        try:
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
        except Exception:
            pass
        for ax in axes:
            try:
                still_bottom = 0.0
                still_left = 0.0
                labels = _onscreen_tick_labels(ax)  # 同样过滤轴外幽灵刻度
                for t in labels:
                    bb = t.get_window_extent(renderer=renderer)
                    if bb.y0 < 0:
                        still_bottom = max(still_bottom, -bb.y0)
                    if bb.x0 < 0:
                        still_left = max(still_left, -bb.x0)
                if still_bottom <= 1 and still_left <= 1:
                    continue
                pos = ax.get_position()
                dy = still_bottom / fig_h_px + 0.01 if still_bottom > 1 else 0.0
                dx = still_left / fig_w_px + 0.01 if still_left > 1 else 0.0
                ax.set_position([
                    pos.x0 + dx,
                    pos.y0 + dy,
                    max(0.1, pos.width - dx),
                    max(0.1, pos.height - dy),
                ])
            except Exception:
                pass


def _guard_subplot_size(fig):
    """防护：检测子图是否被压缩得过小，如果是则强制修复布局。
    
    常见原因：SciencePlots 的 subplot margins 过紧、tight_layout(pad) 过大、
    ax.text(transAxes) 标签被算入空间分配。
    
    强制修复策略：检测到问题 → 重置 margins → 重新 tight_layout(pad=0.3) → 再验证。
    """
    # ★ 3D 轴豁免：3D 曲面 + 窄 colorbar 会被误判"子图过窄"而挤塌，直接跳过
    if _has_3d_axes(fig):
        return

    # constrained/compressed layout 和带专用 legend/colorbar 轨道的手工 GridSpec
    # 已由调用方完整分配空间；这里再 reset margins/tight_layout 会破坏其布局合同。
    try:
        if fig.get_layout_engine() is not None:
            return
    except Exception:
        pass
    if bool(getattr(fig, '_mh_manual_layout', False)):
        return

    axes = [ax for ax in fig.get_axes() if ax.get_visible() and not ax.get_label().startswith('_')]
    if not axes:
        return

    fig_w, fig_h = fig.get_size_inches()
    if fig_w <= 0 or fig_h <= 0:
        return

    def _is_too_small():
        """检测是否有子图过小。"""
        for ax in axes:
            pos = ax.get_position()
            ax_w_inch = pos.width * fig_w
            ax_h_inch = pos.height * fig_h
            # 子图面积小于 1.5 平方英寸 → 肯定有问题
            if ax_w_inch * ax_h_inch < 1.5:
                return True
            # 子图高度小于 1 英寸 → 太扁了
            if ax_h_inch < 1.0:
                return True
            # 子图宽度小于 2 英寸 → 太窄了
            if ax_w_inch < 2.0:
                return True
        return False
    
    if not _is_too_small():
        return
    
    # ★ 强制修复第一步：重置 subplot margins
    n_axes = len(axes)
    if n_axes == 1:
        fig.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.12)
    else:
        fig.subplots_adjust(left=0.10, right=0.95, top=0.93, bottom=0.10,
                            hspace=0.3, wspace=0.3)
    
    # ★ 强制修复第二步：用小 pad 重新 tight_layout 覆盖之前的大 pad
    try:
        fig.tight_layout(pad=0.3)
    except Exception:
        pass
    
    # ★ 强制修复第三步：如果还是太小，直接放弃 tight_layout，手动设置合理布局
    if _is_too_small():
        if n_axes == 1:
            fig.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.12)
        elif n_axes <= 4:
            fig.subplots_adjust(left=0.08, right=0.96, top=0.94, bottom=0.08,
                                hspace=0.25, wspace=0.25)
        else:
            fig.subplots_adjust(left=0.06, right=0.97, top=0.95, bottom=0.06,
                                hspace=0.2, wspace=0.2)


def _is_annotation(t):
    """是否 ax.annotate 产物（Annotation 有 anncoords，普通 Text 没有）"""
    return hasattr(t, 'anncoords') and hasattr(t, 'set_anncoords')


def move_text_px(t, dx_px, dy_px, renderer=None):
    """★ 全模块唯一的「按像素平移一个 Text/Annotation」入口。

    ⛔⛔ 为什么必须统一走这里（这是查了很久的一类事故）：
       `Annotation.get_position()` 返回的是 xytext 的【原生单位】，随 textcoords 变：
           textcoords='offset points'  → points（1/72 英寸）   ← 真实用法占 58/65
           textcoords='axes fraction'  → axes 比例 0-1
           textcoords='data' / 不传    → 数据坐标
       而普通 Text.get_position() 永远是数据坐标。
       旧代码一律"把数据坐标增量加到 get_position() 上"，于是：
         · offset points 档 → 把数据增量当 points 加，位移量完全错（改了个零头）
         · axes fraction 档 → xlim=(0,500) 时把 -39 加到 0.97 上 = -38 axes fraction，
           标注被甩到画布左外 **44316px**，输出里彻底消失（信息丢失）
       修法：用【锚点像素】做唯一中间量 —— 读出当前锚点像素、加上位移、
       再换算回该对象自己的坐标系写回。Annotation 统一改用 'axes fraction'
       （跟着 axes 走，后续 set_position 收缩 axes 时不会脱锚；用 figure fraction
       则会脱锚 —— 那是 _proto 阶段踩过的坑）。
       ★ 保留 ha/va/rotation 不动：位移是"锚点平移"，不碰对齐方式，
         所以旋转文字、多行文字都不会变形。
    Returns: True 表示确实动了
    """
    if abs(dx_px) < 0.5 and abs(dy_px) < 0.5:
        return False
    fig = t.get_figure()
    if fig is None:
        return False
    if renderer is None:
        try:
            renderer = fig.canvas.get_renderer()
        except Exception:
            return False
    try:
        tr = t.get_transform()
        anchor = tr.transform(t.get_position())
        target = (anchor[0] + dx_px, anchor[1] + dy_px)
    except Exception:
        return False

    if _is_annotation(t):
        ax = getattr(t, 'axes', None)
        try:
            if ax is not None:
                # 换算到 axes fraction 并把坐标系固定过去
                fx, fy = ax.transAxes.inverted().transform(target)
                t.set_anncoords('axes fraction')
                t.set_position((float(fx), float(fy)))
            else:
                fx, fy = fig.transFigure.inverted().transform(target)
                t.set_anncoords('figure fraction')
                t.set_position((float(fx), float(fy)))
            return True
        except Exception:
            return False
    # 普通 Text：沿用它自己的 transform 反解（多为 transData / transAxes）
    try:
        inv = t.get_transform().inverted()
        nx, ny = inv.transform(target)
        t.set_position((float(nx), float(ny)))
        return True
    except Exception:
        return False


def snapshot_text_pos(texts):
    """存下位置状态供回滚（⛔ Annotation 必须连 anncoords 一起存：
    我们会把它改成 'axes fraction'，只还 position 不还坐标系 = 按错的坐标系解释，
    回滚不干净）。"""
    snap = []
    for t in texts:
        anc = None
        if _is_annotation(t):
            try:
                anc = t.get_anncoords()
            except Exception:
                anc = None
        try:
            snap.append((t, t.get_position(), anc))
        except Exception:
            pass
    return snap


def restore_text_pos(snap):
    for t, pos, anc in snap:
        try:
            if anc is not None:
                t.set_anncoords(anc)
            t.set_position(pos)
        except Exception:
            pass


def _text_window_extent(text, renderer):
    """Return only the glyph box, excluding an Annotation's leader arrow.

    ``Annotation.get_window_extent`` returns the union of text and arrow.
    Using that union for collision checks makes every normal callout appear to
    cover its target marker and its own leader.  Calling the Text base-class
    implementation keeps the visible text box while preserving ordinary Text
    behaviour.
    """
    if _is_annotation(text):
        try:
            from matplotlib.text import Text
            return Text.get_window_extent(text, renderer=renderer)
        except Exception:
            pass
    return text.get_window_extent(renderer=renderer)


def _clamp_texts_to_axes(ax, texts, renderer):
    """将超出 axes 边界的文字/标注拉回 axes 内部（保留 4px 内边距）。

    帕累托图、灵敏度图等场景中 annotate 的 xytext 用硬编码偏移，
    数据点靠边时标注就会出界。
    ⛔ 位移统一走 move_text_px —— 它吸收 Text/Annotation 的单位差异，
       这里不许再自己算 get_position() 加减（旧版就是那么写坏的）。
    ⛔ dx/dy 要各自独立判断【且不能互相覆盖】：文字比 axes 还宽时
       左右都会触发，旧代码后写的 dx 会盖掉前一个 → 只贴一边、另一边照样出。
       这里改成"先算需要的位移，再取绝对值较小的那个方向"，保证总溢出不增加。
    """
    try:
        ax_bbox = ax.get_window_extent(renderer=renderer)
    except Exception:
        return

    pad = 4
    for t in texts:
        try:
            b = _text_window_extent(t, renderer)
        except Exception:
            continue
        # 各方向需要的位移
        need_r = (ax_bbox.x1 - pad) - b.x1      # <0 表示要左移
        need_l = (ax_bbox.x0 + pad) - b.x0      # >0 表示要右移
        need_t = (ax_bbox.y1 - pad) - b.y1
        need_b = (ax_bbox.y0 + pad) - b.y0

        def _solve(nl, nr, lo, hi, size):
            """返回该方向的位移。⛔ 装不下时【居中】不要贴边：
               贴边会让另一侧多溢出一个 pad —— 实测 3 寸画布放超长文字，
               居中总溢出 98px，贴边变成 102px（越修越糟）。"""
            avail = (hi - pad) - (lo + pad)
            if size > avail:
                # 无解 → 居中：把中心对到 axes 中心
                cur_c = None
                return None
            if nr < 0:
                return nr
            if nl > 0:
                return nl
            return 0.0

        dx = _solve(need_l, need_r, ax_bbox.x0, ax_bbox.x1, b.width)
        dy = _solve(need_b, need_t, ax_bbox.y0, ax_bbox.y1, b.height)
        if dx is None:      # 横向装不下 → 居中
            dx = ((ax_bbox.x0 + ax_bbox.x1) / 2.0) - ((b.x0 + b.x1) / 2.0)
        if dy is None:
            dy = ((ax_bbox.y0 + ax_bbox.y1) / 2.0) - ((b.y0 + b.y1) / 2.0)
        move_text_px(t, dx, dy, renderer)


def _display_line_paths(ax):
    """Return visible data/reference line paths in display coordinates.

    Grid lines and artists with negligible opacity are deliberately excluded:
    moving a label merely because it crosses a faint grid would make layouts
    unstable, while crossing a real curve/reference line is visually harmful.
    """
    paths = []
    grid_ids = set()
    try:
        grid_ids.update(id(line) for line in ax.get_xgridlines())
        grid_ids.update(id(line) for line in ax.get_ygridlines())
    except Exception:
        pass
    for line in list(getattr(ax, 'lines', ())):
        try:
            if (not line.get_visible() or id(line) in grid_ids
                    or (line.get_alpha() is not None and line.get_alpha() < 0.15)
                    or line.get_linewidth() <= 0
                    or line.get_linestyle() in (None, '', 'None', ' ')):
                continue
            path = line.get_path().transformed(line.get_transform())
            if len(path.vertices) >= 2:
                paths.append(path)
        except Exception:
            continue
    return paths


def _rect_intersection_ratio(inner, outer):
    """Return the fraction of *inner* covered by *outer* in display space."""
    ix0, iy0 = max(inner.x0, outer.x0), max(inner.y0, outer.y0)
    ix1, iy1 = min(inner.x1, outer.x1), min(inner.y1, outer.y1)
    if ix1 <= ix0 or iy1 <= iy0 or inner.width <= 0 or inner.height <= 0:
        return 0.0
    return float((ix1 - ix0) * (iy1 - iy0) / (inner.width * inner.height))


def _display_artist_obstacles(ax, renderer):
    """Collect rendered non-text obstacles that labels must not straddle.

    The old guard saw only Line2D centre paths.  It consequently missed the
    failures that are most obvious to a reader: a value printed through a
    scatter/star marker, an arrow crossing a label, or a label sitting on a
    bar edge.  Obstacles are kept in display coordinates so log/inverted axes
    and mixed coordinate systems need no special cases.

    Bar *interiors* remain legal label areas; :func:`_text_data_hit_score`
    rejects only labels that straddle the bar boundary.  This preserves normal
    in-bar values while catching the unreadable half-in/half-out case.
    """
    from matplotlib.collections import PathCollection
    from matplotlib.container import BarContainer
    from matplotlib.patches import FancyArrowPatch, Polygon
    from matplotlib.transforms import Bbox

    line_paths = list(_display_line_paths(ax))
    arrow_paths = []
    arrow_items = []
    markers = []
    bars = []

    # Keep ownership for annotation leaders.  A leader is expected to meet
    # the edge of its own label and must not make that label fail the guard;
    # it remains an obstacle for every other label.
    annotation_arrow_owners = {}
    for text in getattr(ax, 'texts', ()):
        arrow = getattr(text, 'arrow_patch', None)
        if arrow is not None:
            annotation_arrow_owners[id(arrow)] = id(text)
    seen_arrows = set()

    # Exact bar patches are available through BarContainer.  Using every
    # Rectangle would mistake axvspan/background bands for bars.
    bar_ids = set()
    for container in getattr(ax, 'containers', ()):
        if isinstance(container, BarContainer):
            bar_ids.update(id(patch) for patch in container.patches)

    for patch in getattr(ax, 'patches', ()):
        try:
            if not patch.get_visible() or patch is ax.patch:
                continue
            alpha = patch.get_alpha()
            if alpha is not None and alpha < 0.15:
                continue
            if id(patch) in bar_ids:
                box = patch.get_window_extent(renderer=renderer)
                if box.width > 0.5 and box.height > 0.5:
                    bars.append(box)
                continue
            if isinstance(patch, FancyArrowPatch):
                path = patch.get_path().transformed(patch.get_transform())
                if len(path.vertices) >= 2:
                    arrow_paths.append(path)
                    arrow_items.append((path, annotation_arrow_owners.get(id(patch))))
                    seen_arrows.add(id(patch))
            elif isinstance(patch, Polygon):
                # ax.fill creates Polygon summaries (e.g. forest-plot diamonds),
                # not PathCollection markers. Large regions are not markers.
                box = patch.get_window_extent(renderer=renderer)
                unit = float(ax.figure.dpi) / 72.0
                # A forest-summary diamond can be wide (its width encodes an
                # interval) while remaining a thin marker. Do not mistake it
                # for a large filled region merely because it exceeds 28pt.
                vertices = patch.get_path().transformed(patch.get_transform()).vertices
                if len(vertices) > 1 and np.allclose(vertices[0], vertices[-1]):
                    vertices = vertices[:-1]
                diamond = False
                if len(vertices) == 4 and box.width > .5 and box.height > .5:
                    centre = np.array([(box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2])
                    scaled = np.abs((vertices - centre) / [box.width / 2, box.height / 2])
                    tips = (np.isclose(scaled[:, 0], 1, atol=.03) & (scaled[:, 1] < .03)) | (np.isclose(scaled[:, 1], 1, atol=.03) & (scaled[:, 0] < .03))
                    diamond = bool(np.all(tips))
                if (0.5 < box.height <= 28 * unit
                        and (0.5 < box.width <= 28 * unit or diamond)):
                    markers.append(box)
        except Exception:
            continue

    # Annotation arrows are not consistently exposed through ax.patches.
    for text in getattr(ax, 'texts', ()):
        arrow = getattr(text, 'arrow_patch', None)
        if arrow is None or id(arrow) in seen_arrows or not arrow.get_visible():
            continue
        try:
            path = arrow.get_path().transformed(arrow.get_transform())
            if len(path.vertices) >= 2:
                arrow_paths.append(path)
                arrow_items.append((path, id(text)))
                seen_arrows.add(id(arrow))
        except Exception:
            pass

    dpi = float(getattr(ax.figure, 'dpi', 100.0) or 100.0)

    # scatter / star markers (PathCollection)
    for coll in getattr(ax, 'collections', ()):
        if not isinstance(coll, PathCollection):
            continue
        try:
            if (not coll.get_visible()
                    or (coll.get_alpha() is not None and coll.get_alpha() < 0.15)):
                continue
            offsets = np.asarray(coll.get_offsets(), float)
            if offsets.ndim != 2 or offsets.shape[1] < 2 or not len(offsets):
                continue
            original_count = len(offsets)
            sample_indices = np.arange(original_count, dtype=int)
            if len(offsets) > 5000:
                sample_indices = np.linspace(0, original_count - 1, 5000, dtype=int)
                offsets = offsets[sample_indices]
            disp = coll.get_offset_transform().transform(offsets[:, :2])
            sizes = np.asarray(coll.get_sizes(), float)
            linewidths = np.asarray(coll.get_linewidths(), float)
            for i, (x, y) in enumerate(disp):
                if not np.isfinite([x, y]).all():
                    continue
                source_i = int(sample_indices[i])
                size = sizes[source_i % len(sizes)] if len(sizes) else 36.0
                lw = linewidths[source_i % len(linewidths)] if len(linewidths) else 0.0
                radius = max(2.5, 0.58 * np.sqrt(max(size, 0.0)) * dpi / 72.0
                             + 0.5 * lw * dpi / 72.0)
                markers.append(Bbox.from_extents(x - radius, y - radius,
                                                  x + radius, y + radius))
        except Exception:
            continue

    # Line2D markers are not represented by the centreline path.
    for line in getattr(ax, 'lines', ()):
        try:
            marker = line.get_marker()
            if (not line.get_visible() or marker in (None, '', 'None', ' ')
                    or line.get_markersize() <= 0):
                continue
            # Use the same selected marker path as Matplotlib; markevery may
            # be an index list, slice, stride or display-distance interval.
            # Unselected samples are not visible marker obstacles.
            marker_path = line.get_path()
            if line.get_markevery() is not None:
                from matplotlib.lines import _mark_every_path
                marker_path = _mark_every_path(line.get_markevery(), marker_path,
                                               line.get_transform(), ax)
            xy = np.asarray(marker_path.vertices, float)
            xy = xy[np.isfinite(xy).all(axis=1)]
            if not len(xy):
                continue
            if len(xy) > 5000:
                xy = xy[np.linspace(0, len(xy) - 1, 5000, dtype=int)]
            disp = line.get_transform().transform(xy)
            radius = max(2.5, 0.58 * float(line.get_markersize()) * dpi / 72.0
                         + 0.5 * float(line.get_markeredgewidth() or 0) * dpi / 72.0)
            for x, y in disp:
                markers.append(Bbox.from_extents(x - radius, y - radius,
                                                  x + radius, y + radius))
        except Exception:
            continue
    return {
        'paths': line_paths + arrow_paths,
        'lines': line_paths,
        'arrows': arrow_paths,
        'arrow_items': arrow_items,
        'markers': markers,
        'bars': bars,
    }


def _text_data_hit_score(text, bbox, obstacles):
    """Weighted collision score for one label against rendered artists."""
    core = _bbox_core(bbox, ratio=0.08)
    score = _line_hit_count(bbox, obstacles.get('lines', ())) * 4
    score += sum(
        _line_hit_count(bbox, (path,)) * 4
        for path, owner in obstacles.get('arrow_items', ())
        if owner != id(text)
    )
    for marker in obstacles.get('markers', ()):
        if core.overlaps(marker):
            score += 6
    for bar in obstacles.get('bars', ()):
        ratio = _rect_intersection_ratio(core, bar)
        if ratio <= 0.04:
            continue
        # A label wholly inside a bar is intentional; contrast is handled by
        # _ensure_visual_contrast.  Only boundary-straddling text is harmful.
        inside = (core.x0 >= bar.x0 + 1.5 and core.x1 <= bar.x1 - 1.5
                  and core.y0 >= bar.y0 + 1.5 and core.y1 <= bar.y1 - 1.5)
        if not inside and ratio < 0.96:
            score += 5
    return score


def _hard_artist_hit_count(bbox, obstacles, *, text=None):
    """Count rendered artist clashes that must never be exported.

    Curves are included as well.  An opaque text plate is not an exemption:
    hiding a curve behind a white rectangle is still data occlusion, not a
    valid contrast repair.
    """
    core = _bbox_core(bbox, ratio=0.08)
    count = _line_hit_count(bbox, obstacles.get('lines', ()))
    count += sum(
        _line_hit_count(bbox, (path,))
        for path, owner in obstacles.get('arrow_items', ())
        if text is None or owner != id(text)
    )
    count += sum(1 for marker in obstacles.get('markers', ()) if core.overlaps(marker))
    for bar in obstacles.get('bars', ()):
        ratio = _rect_intersection_ratio(core, bar)
        inside = (core.x0 >= bar.x0 + 1.5 and core.x1 <= bar.x1 - 1.5
                  and core.y0 >= bar.y0 + 1.5 and core.y1 <= bar.y1 - 1.5)
        if ratio > 0.04 and not inside and ratio < 0.96:
            count += 1
    return count


def _unresolved_hard_artist_collisions(fig):
    """Return concise diagnostics for free labels still hitting data artists."""
    issues = []
    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
    except Exception:
        return issues
    for ax_index, ax in enumerate(fig.get_axes(), start=1):
        if not ax.get_visible() or _is_3d_axis(ax):
            continue
        obstacles = _display_artist_obstacles(ax, renderer)
        if not any(obstacles.get(key) for key in ('lines', 'arrows', 'markers', 'bars')):
            continue
        for text in ax.texts:
            if not text.get_visible() or not text.get_text().strip():
                continue
            try:
                box = _text_window_extent(text, renderer)
            except Exception:
                continue
            hits = _hard_artist_hit_count(box, obstacles, text=text)
            if hits:
                snippet = ' '.join(text.get_text().split())[:28]
                issues.append((ax_index, snippet, hits))
                if len(issues) >= 8:
                    return issues
    return issues


def _tick_is_numeric(label):
    import re

    raw = str(label or '').strip().replace('−', '-').replace(',', '')
    if not raw:
        return True
    try:
        float(raw)
        return True
    except ValueError:
        # Matplotlib commonly renders numeric log ticks as
        # ``$\mathdefault{10^{2}}$``.  Strip TeX commands before deciding;
        # otherwise a log axis would be mistaken for categorical rows.
        tex = re.sub(r'\\[A-Za-z]+', '', raw)
        tex = tex.translate(str.maketrans('', '', '${}()[]'))
        return bool(re.fullmatch(r'[0-9+\-−.eE×xX^*/ ]+', tex))


def _categorical_row_locks(ax, texts, renderer):
    """Map row-owned labels to immutable display-space category bands.

    Only genuinely categorical y axes are considered.  Numeric continuous
    axes are intentionally ignored, avoiding accidental constraints on line
    charts.  A label must start close to a row centre to acquire ownership;
    notes in margins or panel summaries remain free.
    """
    try:
        labels = [item for item in ax.get_yticklabels()
                  if item.get_visible() and item.get_text().strip()]
        if len(labels) < 2:
            return {}
        if sum(not _tick_is_numeric(item.get_text()) for item in labels) < max(1, (len(labels) + 1) // 2):
            return {}
        # Use the rendered tick-label centres rather than ``get_yticks()``:
        # locators may retain blank/off-screen ticks, which would create bands
        # for rows that do not actually exist.
        ypix = sorted(float(0.5 * (item.get_window_extent(renderer=renderer).y0
                                  + item.get_window_extent(renderer=renderer).y1))
                      for item in labels)
        gaps = np.diff(ypix)
        pitch = float(np.median(gaps[gaps > 1.0]))
        if not np.isfinite(pitch) or pitch <= 1.0:
            return {}
        axbox = ax.get_window_extent(renderer=renderer)
    except Exception:
        return {}

    edges = [max(axbox.y0, ypix[0] - 0.5 * pitch)]
    edges += [0.5 * (a + b) for a, b in zip(ypix[:-1], ypix[1:])]
    edges += [min(axbox.y1, ypix[-1] + 0.5 * pitch)]
    locks = {}
    for text in texts:
        try:
            box = _text_window_extent(text, renderer)
        except Exception:
            continue
        centre = 0.5 * (box.y0 + box.y1)
        index = int(np.argmin(np.abs(np.asarray(ypix) - centre)))
        if abs(ypix[index] - centre) <= 0.38 * pitch:
            locks[id(text)] = (float(edges[index]), float(edges[index + 1]))
    return locks


def _clamp_texts_to_row_bands(texts, row_locks, renderer):
    """Keep labels inside their original categorical row; return failures."""
    unresolved = 0
    pad = 2.0
    for text in texts:
        band = row_locks.get(id(text))
        if band is None:
            continue
        try:
            box = _text_window_extent(text, renderer)
        except Exception:
            continue
        lo, hi = band[0] + pad, band[1] - pad
        if box.height > hi - lo:
            target = 0.5 * (lo + hi)
            move_text_px(text, 0.0, target - 0.5 * (box.y0 + box.y1), renderer)
            unresolved += 1
            continue
        dy = 0.0
        if box.y0 < lo:
            dy = lo - box.y0
        elif box.y1 > hi:
            dy = hi - box.y1
        if dy:
            move_text_px(text, 0.0, dy, renderer)
    return unresolved


def _categorical_tick_geometry(ax, renderer):
    """Return rendered categorical-row geometry, or ``None`` for numeric axes."""
    try:
        labels = [item for item in ax.get_yticklabels()
                  if item.get_visible() and item.get_text().strip()]
        if len(labels) < 2:
            return None
        non_numeric = sum(not _tick_is_numeric(item.get_text()) for item in labels)
        if non_numeric < max(1, (len(labels) + 1) // 2):
            return None
        boxes = [item.get_window_extent(renderer=renderer) for item in labels]
        ypix = sorted(float(0.5 * (box.y0 + box.y1)) for box in boxes)
        gaps = np.diff(ypix)
        pitch = float(np.median(gaps[gaps > 1.0]))
        if not np.isfinite(pitch) or pitch <= 1.0:
            return None
        return labels, boxes, ypix, pitch
    except Exception:
        return None


def _expand_dense_categorical_canvas(fig):
    """Increase figure height when category rows cannot fit readable labels.

    Width is deliberately unchanged: widening a width-constrained paper figure
    merely makes LaTeX shrink it back down.  Extra height, capped at 8 inches,
    gives horizontal bars, lollipops and Gantt rows real vertical breathing
    room without reducing their final printed font size.
    """
    if _has_3d_axes(fig):
        return False
    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        current_w, current_h = map(float, fig.get_size_inches())
    except Exception:
        return False
    need = 1.0
    for ax in fig.get_axes():
        if not ax.get_visible() or _is_3d_axis(ax):
            continue
        geometry = _categorical_tick_geometry(ax, renderer)
        if geometry is None:
            continue
        _, tick_boxes, _, pitch = geometry
        texts = [text for text in ax.texts
                 if text.get_visible() and text.get_text().strip()]
        locks = _categorical_row_locks(ax, texts, renderer)
        try:
            heights = [box.height for box in tick_boxes]
            heights.extend(_text_window_extent(text, renderer).height
                           for text in texts if id(text) in locks)
        except Exception:
            continue
        if not heights:
            continue
        required = max(22.0, max(heights) + 8.0)
        if pitch < required:
            need = max(need, required / max(pitch, 1.0))
    if need <= 1.03 or current_h >= 8.0 - 1e-6:
        return False
    # Apply the measured scale in one pass.  A conservative 1.45x step left
    # very dense charts half-fixed because the save hook intentionally runs
    # only once.  The 8-inch cap still prevents an over-tall paper figure;
    # anything that cannot fit at that height is rejected below and should be
    # split or have secondary prose removed.
    target_h = min(8.0, current_h * need * 1.04)
    if target_h <= current_h + 0.05:
        return False
    fig.set_size_inches(current_w, target_h, forward=True)
    try:
        fig.canvas.draw()
        fig._mh_canvas_expanded_for_density = (current_h, target_h)
    except Exception:
        pass
    return True


def _unresolved_categorical_row_overflow(fig):
    """Report row-owned annotations that still cross category boundaries."""
    issues = []
    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
    except Exception:
        return issues
    for ax_index, ax in enumerate(fig.get_axes(), start=1):
        if not ax.get_visible() or _is_3d_axis(ax):
            continue
        texts = [text for text in ax.texts
                 if text.get_visible() and text.get_text().strip()]
        locks = _categorical_row_locks(ax, texts, renderer)
        for text in texts:
            band = locks.get(id(text))
            if band is None:
                continue
            try:
                box = _text_window_extent(text, renderer)
            except Exception:
                continue
            if box.y0 < band[0] + 1.5 or box.y1 > band[1] - 1.5:
                snippet = ' '.join(text.get_text().split())[:28]
                issues.append((ax_index, snippet))
                if len(issues) >= 8:
                    return issues
    return issues


def _bbox_core(bbox, ratio=0.10):
    """Slightly inset a text bbox so touching an edge is not a false clash."""
    from matplotlib.transforms import Bbox
    dx = min(max(bbox.width * ratio, 1.0), bbox.width * 0.25)
    dy = min(max(bbox.height * ratio, 1.0), bbox.height * 0.25)
    if bbox.width <= 2 * dx or bbox.height <= 2 * dy:
        return bbox
    return Bbox.from_extents(bbox.x0 + dx, bbox.y0 + dy,
                             bbox.x1 - dx, bbox.y1 - dy)


def _line_hit_count(bbox, paths):
    core = _bbox_core(bbox)
    total = 0
    for path in paths:
        try:
            if path.intersects_bbox(core, filled=False):
                total += 1
        except Exception:
            continue
    return total


def _move_texts_off_data(ax, texts, renderer, row_locks=None):
    """Move annotations away from curves, markers, arrows and bar boundaries.

    The old guard only compared text with *other text*.  A single threshold
    label could therefore sit directly on a curve forever.  This routine uses
    the rendered paths, tries a bounded set of pixel offsets and accepts a move
    only when the objective is strictly better.  Opaque text plates are moved
    too: a white box may improve contrast, but it must never be used to hide a
    curve, marker or bar edge.
    """
    obstacles = _display_artist_obstacles(ax, renderer)
    if (not texts or not any(obstacles.get(key) for key in ('paths', 'markers', 'bars'))):
        return 0
    try:
        axes_box = ax.get_window_extent(renderer=renderer)
    except Exception:
        return 0

    moved = 0
    occupied = []
    for text in texts:
        try:
            bbox = _text_window_extent(text, renderer)
        except Exception:
            continue
        base_hits = _text_data_hit_score(text, bbox, obstacles)
        if base_hits <= 0:
            occupied.append(bbox)
            continue

        base_snap = snapshot_text_pos([text])
        best = (base_hits * 20.0, 0.0, 0.0, bbox)
        # Prefer short vertical moves (the usual academic annotation layout),
        # then diagonals/horizontal moves for crowded panels.
        for dx, dy in ((0, 10), (0, -10), (10, 0), (-10, 0),
                       (8, 8), (-8, 8), (8, -8), (-8, -8),
                       (0, 16), (0, -16), (16, 0), (-16, 0),
                       (0, 22), (0, -22), (22, 0), (-22, 0),
                       (18, 18), (-18, 18), (18, -18), (-18, -18),
                       (0, 28), (0, -28), (28, 0), (-28, 0)):
            restore_text_pos(base_snap)
            if not move_text_px(text, dx, dy, renderer):
                continue
            try:
                candidate = _text_window_extent(text, renderer)
            except Exception:
                continue
            band = (row_locks or {}).get(id(text))
            if band is not None and (candidate.y0 < band[0] + 2.0
                                     or candidate.y1 > band[1] - 2.0):
                continue
            outside = max(0.0, axes_box.x0 + 2 - candidate.x0)
            outside += max(0.0, candidate.x1 - axes_box.x1 + 2)
            outside += max(0.0, axes_box.y0 + 2 - candidate.y0)
            outside += max(0.0, candidate.y1 - axes_box.y1 + 2)
            text_clashes = sum(1 for other in occupied if candidate.overlaps(other))
            score = (_text_data_hit_score(text, candidate, obstacles) * 20.0
                     + text_clashes * 12.0 + outside * 3.0
                     + (abs(dx) + abs(dy)) / 100.0)
            if score < best[0] - 1e-9:
                best = (score, dx, dy, candidate)

        restore_text_pos(base_snap)
        if best[1] or best[2]:
            move_text_px(text, best[1], best[2], renderer)
            try:
                bbox = _text_window_extent(text, renderer)
            except Exception:
                bbox = best[3]
            moved += 1
        occupied.append(bbox)
    return moved


def _auto_fix_overlaps(fig):
    """自动检测并修复 fig 中所有 axes 上的文字重叠。

    策略：
    1. 收集每个 ax 上所有可见的 Text 对象（排除轴标签、标题等）
    2. 计算每对 Text 的 bounding box，检测是否重叠
    3. 如果有重叠，调用 adjustText 自动推开
    4. 同时检测图例是否遮挡数据，如果遮挡则移动图例
    5. 检测 y 轴标签是否被相邻 axes（如分组色条）遮挡
    """
    try:
        renderer = fig.canvas.get_renderer()
    except Exception:
        # 某些后端没有 renderer，跳过检测
        return

    for ax in fig.get_axes():
        # adjustText 的 2D 位移不适用于 3D 投影；但同一 figure 中的普通
        # 2D panel 仍应继续检查，不能因存在一个 3D panel 就整图豁免。
        if _is_3d_axis(ax):
            continue
        # 收集用户添加的 Text 对象（排除轴标签、标题、tick labels）
        user_texts = []
        skip_texts = set()
        # 标记要跳过的系统文本
        if ax.xaxis.label:
            skip_texts.add(id(ax.xaxis.label))
        if ax.yaxis.label:
            skip_texts.add(id(ax.yaxis.label))
        if ax.title:
            skip_texts.add(id(ax.title))
        for t in ax.get_xticklabels() + ax.get_yticklabels():
            skip_texts.add(id(t))

        for t in ax.texts:
            if id(t) in skip_texts:
                continue
            if not t.get_visible():
                continue
            txt = t.get_text().strip()
            if not txt:
                continue
            user_texts.append(t)

        # ★ 边界裁剪：检测标注/文字是否超出 axes 范围，拉回来
        # 即使只有 1 个标注也需要检测（帕累托图等场景）
        if user_texts:
            _clamp_texts_to_axes(ax, user_texts, renderer)
            # Text-vs-curve is independent of text-vs-text and must also run
            # for a single annotation.  This closes the common "one label is
            # printed through by the curve" false-pass.
            row_locks = _categorical_row_locks(ax, user_texts, renderer)
            _clamp_texts_to_row_bands(user_texts, row_locks, renderer)
            _move_texts_off_data(ax, user_texts, renderer, row_locks=row_locks)
            _clamp_texts_to_row_bands(user_texts, row_locks, renderer)
        else:
            row_locks = {}

        if len(user_texts) < 2:
            continue

        # 检测是否有重叠
        has_overlap = False
        bboxes = []
        for t in user_texts:
            try:
                bb = _text_window_extent(t, renderer)
                bboxes.append(bb)
            except Exception:
                bboxes.append(None)

        for i in range(len(bboxes)):
            if bboxes[i] is None:
                continue
            for j in range(i + 1, len(bboxes)):
                if bboxes[j] is None:
                    continue
                if bboxes[i].overlaps(bboxes[j]):
                    has_overlap = True
                    break
            if has_overlap:
                break

        if not has_overlap:
            continue

        # 有重叠 → 尝试用 adjustText 修复
        # ⛔⛔ 必须带【快照 + 不做恶回滚】：adjustText 对 Annotation 是在 points 空间里
        #    推的（能动，但不知道 axes 边界），密集场景会把标注推到 axes 外甚至画布外；
        #    而 clamp 只能拉回 axes 内、救不回"推得太远导致互相更乱"。
        #    实测 35 个 annotate 的场景：互撞 2→3、出界 7 个一个没修好。
        #    所以推完要打分，比原来差就整体还原。
        def _score_local():
            n_clash = 0
            n_out = 0
            try:
                axb2 = ax.get_window_extent(renderer=renderer)
            except Exception:
                axb2 = None
            bs = []
            for t in user_texts:
                try:
                    bs.append(_text_window_extent(t, renderer))
                except Exception:
                    bs.append(None)
            for i2 in range(len(bs)):
                if bs[i2] is None:
                    continue
                for j2 in range(i2 + 1, len(bs)):
                    if bs[j2] is not None and bs[i2].overlaps(bs[j2]):
                        n_clash += 1
            if axb2 is not None:
                for b2 in bs:
                    if b2 is None:
                        continue
                    if (b2.x0 < axb2.x0 - 1 or b2.x1 > axb2.x1 + 1
                            or b2.y0 < axb2.y0 - 1 or b2.y1 > axb2.y1 + 1):
                        n_out += 1
            return n_clash + n_out * 2      # 出界比互撞更严重

        _snap = snapshot_text_pos(user_texts)
        _score0 = _score_local()
        adjust_text = _ensure_adjustText()
        if adjust_text:
            try:
                adjust_text(user_texts, ax=ax,
                            force_points=0.3, force_text=0.5,
                            expand_points=(1.5, 1.5),
                            arrowprops=dict(arrowstyle='', lw=0))
            except Exception:
                # adjustText 失败，尝试简易修复
                _simple_spread(ax, user_texts, bboxes, renderer)
        else:
            _simple_spread(ax, user_texts, bboxes, renderer)

        # adjustText 推开后可能又超出边界，再裁剪一次
        _clamp_texts_to_axes(ax, user_texts, renderer)
        _clamp_texts_to_row_bands(user_texts, row_locks, renderer)
        # ⛔ adjustText 对"只有两三个元素"的场景常常原地不动（它的收敛条件如此），
        #    实测 fig_q3_reopt_slope 的 '1,007' 与 '559' 锚点几乎重合、
        #    axes 还有 338px 高的空档，adjustText 跑完仍 100% 叠着。
        #    → 这里补一轮 _simple_spread（它按像素找空侧推，且会 clamp 回 axes）。
        _sc_mid = _score_local()
        if _sc_mid > 0:
            _snap_mid = snapshot_text_pos(user_texts)
            try:
                _bb_mid = []
                for t in user_texts:
                    try:
                        _bb_mid.append(_text_window_extent(t, renderer))
                    except Exception:
                        _bb_mid.append(None)
                _simple_spread(ax, user_texts, _bb_mid, renderer)
                _clamp_texts_to_row_bands(user_texts, row_locks, renderer)
                if _score_local() > _sc_mid:
                    restore_text_pos(_snap_mid)
            except Exception:
                restore_text_pos(_snap_mid)
        if _score_local() > _score0:
            restore_text_pos(_snap)
            # 还原后再单独 clamp 一次：原始位置本身可能就出界（那是该修的）
            _clamp_texts_to_axes(ax, user_texts, renderer)
            _clamp_texts_to_row_bands(user_texts, row_locks, renderer)

        # 检测图例是否遮挡数据 → 自动挪位
        # ⛔ 但只在【用户没有显式指定位置】时才动（loc='best' / 未传 loc，matplotlib 记为 _loc==0）。
        #    以前无条件覆盖，会把脚本里写的 loc='center left' 无声改成 'upper right'：
        #    作者本来想用图例填补左侧空白，结果图例被挪到右上、左边露出一大片空白，
        #    而且作者查代码只会看到自己写的 center left，根本对不上（实测踩过，很难排查）。
        #    bbox_to_anchor 也挡不住（set_loc 之后 anchor 语义随之改变），所以必须在这里判断。
        legend = ax.get_legend()
        if legend and legend.get_visible():
            _user_fixed = True
            try:
                # _loc == 0 表示 'best'（含未显式传 loc 的默认情形）→ 视为"作者没指定"
                _user_fixed = getattr(legend, '_loc', 0) != 0
            except Exception:
                _user_fixed = False
            if not _user_fixed:
                try:
                    best_loc = check_legend_overlap(ax)
                    legend.set_loc(best_loc)  # matplotlib 3.x
                except (AttributeError, Exception):
                    try:
                        legend._loc = {
                            'upper right': 1, 'upper left': 2,
                            'lower left': 3, 'lower right': 4,
                            'center right': 7, 'center left': 6,
                        }.get(check_legend_overlap(ax), 1)
                    except Exception:
                        pass

        # ★ 检测 user texts 是否和 tick labels 重叠（如标注和 X 轴刻度重叠）
        tick_bboxes = []
        for t in _onscreen_tick_labels(ax):  # 排除轴外幽灵刻度，避免误判重叠
            if t.get_visible() and t.get_text().strip():
                try:
                    tick_bboxes.append(t.get_window_extent(renderer=renderer))
                except Exception:
                    pass
        # ⛔ 推挤方向必须按【屏幕像素】算，不能按数据坐标符号：
        #    反向 y 轴（barh 排名图 invert_yaxis）下"数据值变大"= 屏幕往下，
        #    旧代码 `y + abs(dy)` 会把文字往刻度里推得更深（越修越糟）。
        #    move_text_px 收的就是像素增量，天然不受轴方向影响。
        for i, ut in enumerate(user_texts):
            if bboxes[i] is None:
                continue
            for tb in tick_bboxes:
                if bboxes[i].overlaps(tb):
                    gap = tb.y1 - bboxes[i].y0 + 4.0
                    if move_text_px(ut, 0.0, gap, renderer):
                        try:
                            bboxes[i] = _text_window_extent(ut, renderer)
                        except Exception:
                            pass
                    break
        _clamp_texts_to_row_bands(user_texts, row_locks, renderer)

    # ★ 也处理 annotate 创建的标注（ax.texts 不包含 annotate 的文本部分）
    for ax in fig.get_axes():
        annots = [child for child in ax.get_children()
                  if hasattr(child, 'xyann') or (hasattr(child, 'anncoords') and hasattr(child, 'get_text'))]
        if not annots:
            # annotate 创建的对象在 ax.texts 中（matplotlib 3.x），已经处理过
            # 但也检查 ax.patches 中的 FancyArrowPatch
            pass

    # ★ 检测 y 轴标签是否被相邻 axes（如分组色条）遮挡
    _fix_ylabel_overlap(fig, renderer)


def _fix_ylabel_overlap(fig, renderer):
    """检测并修复 y 轴标签被相邻 axes 遮挡的问题（如聚类热力图的左侧色条）。
    
    三阶段策略：
    1. 检测 y label 是否被左侧 axes（色条/树状图）覆盖 → 把左侧 axes 往左推
    2. 推到 figure 边缘还不够 → 自动截断超长 y label 文本（保留前 N 字 + …）
    3. 仍溢出 figure 左边界 → 减小 y label 字号
    """
    all_axes = fig.get_axes()
    if len(all_axes) < 2:
        # 单 axes 也可能有 y label 溢出 figure 边界的问题
        for ax in all_axes:
            _truncate_ylabels_if_overflow(ax, fig, renderer)
        return
    for ax in all_axes:
        ytick_labels = _onscreen_tick_labels(ax, which='y')  # 排除轴外幽灵刻度
        if not ytick_labels:
            continue
        # 获取 y 轴标签的最左边界（display coords）
        leftmost = None
        for lbl in ytick_labels:
            if not lbl.get_visible() or not lbl.get_text().strip():
                continue
            try:
                bb = lbl.get_window_extent(renderer=renderer)
                if leftmost is None or bb.x0 < leftmost:
                    leftmost = bb.x0
            except Exception:
                continue
        if leftmost is None:
            continue
        # 检查是否有其他 axes 的区域覆盖了这些标签
        ax_bbox_disp = ax.get_window_extent(renderer=renderer)
        pushed = False
        for other_ax in all_axes:
            if other_ax is ax:
                continue
            other_bbox = other_ax.get_window_extent(renderer=renderer)
            # ⛔ 同行约束（修复 bug：多行网格子图被误判为"左侧遮挡物"）
            # 之前漏判：只看 x 横向重叠，不看 y 是否同行 → 同列上下堆叠子图会被误推，
            # 导致左上角子图(a) 被左下角(d)的"遮挡判定"挤压变窄+左移。
            # 现在要求：竖直方向必须实质重叠（重叠 > 较小者高度的 50%）才算"左侧遮挡物"。
            overlap_top = min(ax_bbox_disp.y1, other_bbox.y1)
            overlap_bot = max(ax_bbox_disp.y0, other_bbox.y0)
            v_overlap = overlap_top - overlap_bot
            min_h = min(ax_bbox_disp.height, other_bbox.height)
            if v_overlap <= 0 or (min_h > 0 and v_overlap < min_h * 0.5):
                # 不在同一行（竖直无实质重叠）→ 跳过，不算遮挡物
                continue
            # 如果其他 axes 在当前 axes 左侧且与标签区域重叠
            if other_bbox.x1 > leftmost and other_bbox.x0 < ax_bbox_disp.x0:
                # 计算需要左移的量（figure fraction）
                fig_width = fig.get_window_extent(renderer=renderer).width
                overlap_px = other_bbox.x1 - leftmost + 8  # 8px 额外间距
                shift = overlap_px / fig_width
                # 把遮挡的 axes 往左推（但不能推到 figure 外）
                pos = other_ax.get_position()
                new_x0 = max(0.01, pos.x0 - shift)
                new_width = pos.width - (pos.x0 - new_x0) if new_x0 < pos.x0 else pos.width
                other_ax.set_position([new_x0, pos.y0, max(0.01, new_width), pos.height])
                pushed = True
        # ★ 推完仍可能溢出 figure 左边界 → 触发截断/缩字号兜底
        _truncate_ylabels_if_overflow(ax, fig, renderer)


def _truncate_ylabels_if_overflow(ax, fig, renderer):
    """兜底：当 y label 溢出 figure 左边界（x0 < 0）时，自动截断文本 + 减小字号。"""
    try:
        fig_bbox = fig.get_window_extent(renderer=renderer)
    except Exception:
        return

    # 只看真正会绘制的刻度：轴外的"幽灵刻度"（log 轴常见）位置远在画布左侧，
    # 会被误判成溢出，进而把本来放得下的 y 标签截断成省略号并缩小字号
    ytick_labels = [t for t in _onscreen_tick_labels(ax, which='y')
                    if t.get_visible() and t.get_text().strip()]
    if not ytick_labels:
        return

    # 第一步：检测是否溢出 figure 左边界
    overflow_px = 0
    for lbl in ytick_labels:
        try:
            bb = lbl.get_window_extent(renderer=renderer)
            if bb.x0 < fig_bbox.x0:
                overflow_px = max(overflow_px, fig_bbox.x0 - bb.x0)
        except Exception:
            continue
    if overflow_px <= 0:
        return

    # ⛔⛔ 含 mathtext（$...$）的刻度标签【绝不能按字符截断】——
    #    截断会切断 $ 配对（`$\mathdefault{10^{5}}$` → `$\mathdefault…`），
    #    mathtext 解析失败后 matplotlib 会把 LaTeX 源码【原样印在图上】。
    #    实测天府杯 C 题工作区：2 张图共 10 个刻度变成 "$\mathdefault…" 字面量，
    #    比遮挡难看得多（图上直接显示代码）。
    #    这类标签本来就是 formatter 生成的短数字（10^5 / 0.4 / 500000），
    #    宽度问题该用【缩字号】解决，切字符串没有意义。
    if any('$' in lbl.get_text() for lbl in ytick_labels):
        try:
            cur = ytick_labels[0].get_fontsize()
            need = max(0.55, 1.0 - overflow_px / max(fig_bbox.width * 0.18, 1))
            # ⛔ 下限必须是 8.0pt（= screenshot_capture 的 MIN_FONT_PT 最终印刷可读线），
            #   ⛔ 不能为了塞进画布压到 6.5 —— 那是把"出界"换成"看不清"，
            #   实测继续压字号会扩大不可读文字范围。
            #   压到 8pt 仍不够就交给布局让边距或拆图，不再动字号。
            new_fs = max(MIN_LEGIBLE_PT, cur * need)
            if new_fs < cur - 0.05:
                for lbl in ytick_labels:
                    lbl.set_fontsize(new_fs)
        except Exception:
            pass
        return

    # 第二步：尝试截断超长文本（保留前 N 字 + …）
    # 估算可用字符数：原始最长文本字符数 - 溢出像素 / 单字符宽度
    max_text_len = max((len(lbl.get_text()) for lbl in ytick_labels), default=0)
    if max_text_len > 8:
        # 估算单字符宽度（用最长标签 / 字符数）
        longest_lbl = max(ytick_labels, key=lambda t: len(t.get_text()))
        try:
            longest_bb = longest_lbl.get_window_extent(renderer=renderer)
            char_width = longest_bb.width / max(len(longest_lbl.get_text()), 1)
            # 需要砍掉的字符数 = 溢出像素 / 单字符宽度 + 1 字（… 占位）
            chars_to_cut = int(overflow_px / max(char_width, 1)) + 1
            new_max_len = max(6, max_text_len - chars_to_cut)
            # 整批 set_yticklabels（单 set_text 在重绘时会被 formatter 覆盖）
            current_fontsize = ytick_labels[0].get_fontsize()
            new_texts = []
            for lbl in ytick_labels:
                txt = lbl.get_text()
                if len(txt) > new_max_len:
                    new_texts.append(txt[: new_max_len - 1] + '…')
                else:
                    new_texts.append(txt)
            try:
                ax.set_yticks(ax.get_yticks())
                ax.set_yticklabels(new_texts, fontsize=current_fontsize)
            except Exception:
                for lbl, new_txt in zip(ytick_labels, new_texts):
                    lbl.set_text(new_txt)
        except Exception:
            pass

    # 第三步：再检查仍溢出 → 减字号
    try:
        still_overflow = False
        for lbl in ytick_labels:
            bb = lbl.get_window_extent(renderer=renderer)
            if bb.x0 < fig_bbox.x0:
                still_overflow = True
                break
        if still_overflow:
            current_size = ytick_labels[0].get_fontsize()
            # ⛔ 地板必须是 MIN_LEGIBLE_PT（8.0），⛔ 不能写 6 ——
            #   压到 6pt 是把"溢出"换成"看不清"，两头都不讨好。
            #   实测这行是全图仅剩的 6.0pt 来源（6 处刻度）。
            #   8pt 还塞不下就让边距、缩画布或拆图，不再动字号。
            new_size = max(MIN_LEGIBLE_PT, current_size - 1)
            for lbl in ytick_labels:
                lbl.set_fontsize(new_size)
    except Exception:
        pass


def auto_truncate_yticklabels(ax, max_chars=20, suffix='…'):
    """公开 API：主动截断超长 y tick labels（配方代码可调用，防止 y 轴遮挡）。
    
    用法：
        ax.set_yticklabels(long_method_names, fontsize=10)
        auto_truncate_yticklabels(ax, max_chars=18)  # 超过 18 字符的截断
    
    适用场景：聚类热力图、SHAP 图、特征重要性图 — 这些图 y 轴标签是变量名/方法名，
    遇到长字符串（"average_silhouette_coefficient_2024" 等）会溢出 figure 左边界。
    
    注意：matplotlib 在重绘时可能用 formatter 覆盖单个 Text，所以这里整批 set_yticklabels。
    """
    labels = ax.get_yticklabels()
    if not labels:
        return
    fontsize = labels[0].get_fontsize() if labels else None
    new_texts = []
    for lbl in labels:
        txt = lbl.get_text()
        # ⛔ 含 mathtext（$...$）的一律【原样保留】：按字符截断会切断 $ 配对，
        #   mathtext 解析失败后 LaTeX 源码会原样印在图上（见
        #   _truncate_ylabels_if_overflow 里的同款说明）。
        if '$' in txt:
            new_texts.append(txt)
        elif len(txt) > max_chars:
            new_texts.append(txt[: max_chars - 1] + suffix)
        else:
            new_texts.append(txt)
    # 用 set_yticklabels 整批替换（同时锁定原 tick 位置避免 matplotlib warning）
    try:
        ax.set_yticks(ax.get_yticks())
        if fontsize is not None:
            ax.set_yticklabels(new_texts, fontsize=fontsize)
        else:
            ax.set_yticklabels(new_texts)
    except Exception:
        # 兜底：单个 set_text
        for lbl, new_txt in zip(labels, new_texts):
            lbl.set_text(new_txt)


def _simple_spread(ax, texts, bboxes, renderer):
    """简易重叠修复：沿 y 方向推开重叠文本（adjustText 不可用时的退路）。

    ⛔ 三处旧毛病一起修：
       ① 位移自己算 set_position → 对 Annotation 单位错配（统一走 move_text_px）
       ② 只往上推 → 顶部那个被推出 axes（改成"往空的那侧推"，并夹在 axes 内）
       ③ 只比相邻一对 → 推完不复查，密集时仍残留（改成多轮迭代 + 全对检测）
    """
    if not texts or not bboxes:
        return
    try:
        axb = ax.get_window_extent(renderer=renderer)
    except Exception:
        axb = None

    live = [t for t, b in zip(texts, bboxes) if b is not None]
    if len(live) < 2:
        return

    def bb(t):
        try:
            return t.get_window_extent(renderer=renderer)
        except Exception:
            return None

    for _ in range(4):
        boxes = [(t, bb(t)) for t in live]
        boxes = [(t, b) for t, b in boxes if b is not None]
        boxes.sort(key=lambda p: p[1].y0)
        moved = False
        for k in range(1, len(boxes)):
            t_cur, b_cur = boxes[k]
            _t_prev, b_prev = boxes[k - 1]
            if not b_prev.overlaps(b_cur):
                continue
            gap = b_prev.y1 - b_cur.y0 + 2.0
            # 优先往上推；顶不动（会出 axes）就把【下面那个】往下推
            up_ok = axb is None or (b_cur.y1 + gap) <= axb.y1 - 2
            if up_ok:
                moved |= move_text_px(t_cur, 0.0, gap, renderer)
            else:
                t_prev = boxes[k - 1][0]
                down_ok = axb is None or (b_prev.y0 - gap) >= axb.y0 + 2
                if down_ok:
                    moved |= move_text_px(t_prev, 0.0, -gap, renderer)
                else:
                    # 上下都没地方 → 横向错开半个字宽，至少不完全叠住
                    moved |= move_text_px(t_cur, b_cur.width * 0.5, 0.0, renderer)
        if not moved:
            break
    # 收尾：确保没有被推出 axes
    if axb is not None:
        _clamp_texts_to_axes(ax, live, renderer)

# 公开别名，供外部脚本调用
save_fig = _save


# ============================================================
# 标签防遮挡工具
# ============================================================

def _ensure_adjustText():
    """确保 adjustText 库可用，不可用时自动安装。"""
    try:
        from adjustText import adjust_text
        return adjust_text
    except ImportError:
        try:
            import subprocess
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', 'adjustText', '-q'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            from adjustText import adjust_text
            return adjust_text
        except Exception:
            return None


def smart_labels(ax, xs, ys, texts, colors=None, fontsize=9, fontweight='normal',
                 offset=(8, 0), fmt=None, ha='left', va='center',
                 force_points=0.3, force_text=0.5, avoid_self=True,
                 bbox=None, arrowprops=None, max_labels=50):
    """智能标签标注 — 自动检测并推开重叠标签。

    优先使用 adjustText 库做物理模拟推开；如果不可用，退化为
    基于数据间距的简易偏移策略。

    Args:
        ax: matplotlib Axes 对象
        xs: 标签锚点 x 坐标列表
        ys: 标签锚点 y 坐标列表
        texts: 标签文本列表
        colors: 每个标签的颜色（None 则统一用深灰）
        fontsize: 字号
        fontweight: 字重（'bold' / 'normal'）
        offset: (dx, dy) 像素偏移，adjustText 模式下作为初始偏移
        fmt: 格式化字符串，如 '{:.3f}'，传入时 texts 应为数值列表
        ha/va: 水平/垂直对齐
        force_points: adjustText 的点斥力
        force_text: adjustText 的文本斥力
        avoid_self: 是否避免标签之间重叠
        bbox: 标签背景框样式 dict（如 dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7)）
        arrowprops: 箭头样式 dict（如 dict(arrowstyle='->', color='gray', lw=0.5)）
        max_labels: 超过此数量时跳过标注（数据太密集标注无意义）

    Returns:
        list of Text 对象

    用法示例::

        # 棒棒糖图标注
        smart_labels(ax, scores, y_pos, [f'{s:.3f}' for s in scores],
                     colors=[PALETTE[0]]*len(scores), fontweight='bold')

        # 散点图标注（带箭头）
        smart_labels(ax, x_outliers, y_outliers, gene_names,
                     arrowprops=dict(arrowstyle='->', color='gray', lw=0.5))
    """
    # ⛔ 超限【不能静默返回空】：作者以为标了、实际一个都没画，图上少一批信息
    #    而且没有任何提示（实测踩过）。改成"按间距抽稀保留一部分 + 明确告警"。
    if len(xs) > max_labels:
        import warnings as _w
        step = max(2, int(round(len(xs) / float(max_labels))))
        keep = list(range(0, len(xs), step))[:max_labels]
        _w.warn(f'smart_labels: {len(xs)} 个标签超过 max_labels={max_labels}，'
                f'已按间隔 {step} 抽稀保留 {len(keep)} 个（其余不标）。'
                f'数据太密时建议改用色阶/分档，别逐点标数值。',
                stacklevel=2)
        xs = [xs[i] for i in keep]
        ys = [ys[i] for i in keep]
        texts = [texts[i] for i in keep]
        if colors is not None and not isinstance(colors, str):
            try:
                colors = [colors[i] for i in keep]
            except Exception:
                colors = None

    plt = _get_plt()
    text_objs = []

    # 格式化文本
    if fmt is not None:
        display_texts = [fmt.format(t) for t in texts]
    else:
        display_texts = [str(t) for t in texts]

    default_color = '#333333'

    # 创建 Text 对象
    for i, (x, y, txt) in enumerate(zip(xs, ys, display_texts)):
        c = colors[i] if colors and i < len(colors) else default_color
        fw = fontweight if isinstance(fontweight, str) else (
            fontweight[i] if i < len(fontweight) else 'normal')
        t = ax.text(x, y, txt, fontsize=fontsize, fontweight=fw,
                    color=c, ha=ha, va=va,
                    bbox=bbox if bbox else None)
        text_objs.append(t)

    # 尝试用 adjustText 自动推开
    adjust_text = _ensure_adjustText()
    if adjust_text and avoid_self and len(text_objs) > 1:
        try:
            arrow_kw = arrowprops or dict(arrowstyle='-', color='#cccccc', lw=0.3)
            adjust_text(text_objs, ax=ax,
                        force_points=force_points,
                        force_text=force_text,
                        expand_points=(1.5, 1.5),
                        arrowprops=arrow_kw)
        except Exception:
            # adjustText 失败时退化为手动偏移
            _fallback_offset(ax, text_objs, xs, ys, offset)
    else:
        # 没有 adjustText，用简易偏移
        _fallback_offset(ax, text_objs, xs, ys, offset)

    return text_objs


def _fallback_offset(ax, text_objs, xs, ys, offset):
    """简易防遮挡：根据数据间距计算偏移方向，密集区域交替上下偏移。"""
    if not text_objs:
        return

    fig = ax.get_figure()
    renderer = fig.canvas.get_renderer() if hasattr(fig.canvas, 'get_renderer') else None

    # 获取数据坐标范围
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x_range = xlim[1] - xlim[0] if xlim[1] != xlim[0] else 1
    y_range = ylim[1] - ylim[0] if ylim[1] != ylim[0] else 1

    # 估算标签高度（数据坐标）
    label_height = y_range * 0.035  # 约 3.5% 的 y 轴范围

    # 按 y 坐标排序，检测相邻标签是否过近
    indices = list(range(len(text_objs)))
    indices.sort(key=lambda i: ys[i])

    for k in range(len(indices)):
        i = indices[k]
        # 基础偏移
        dx_data = offset[0] * x_range / 500  # 像素偏移转数据坐标（近似）
        dy_data = offset[1] * y_range / 500

        # 检查与前一个标签是否过近
        if k > 0:
            j = indices[k - 1]
            gap = abs(ys[i] - ys[j])
            if gap < label_height * 1.5:
                # 交替上下偏移
                direction = 1 if k % 2 == 0 else -1
                dy_data += direction * label_height * 0.8

        text_objs[i].set_position((xs[i] + dx_data, ys[i] + dy_data))


def check_legend_overlap(ax, preferred_locs=None):
    """自动选择不遮挡数据的图例位置。

    检测数据分布的稀疏区域，把图例放在最空的角落。

    Args:
        ax: matplotlib Axes 对象
        preferred_locs: 优先尝试的位置列表，默认 ['upper right', 'upper left',
                        'lower right', 'lower left', 'center right']

    Returns:
        最佳位置字符串（可直接传给 ax.legend(loc=...)）
    """
    if preferred_locs is None:
        preferred_locs = ['upper right', 'upper left', 'lower right',
                          'lower left', 'center right', 'center left']

    # 收集所有数据点
    all_x, all_y = [], []
    for line in ax.get_lines():
        xd, yd = line.get_xdata(), line.get_ydata()
        if len(xd) > 0:
            all_x.extend(xd)
            all_y.extend(yd)
    for coll in ax.collections:
        offsets = coll.get_offsets()
        if len(offsets) > 0:
            all_x.extend(offsets[:, 0])
            all_y.extend(offsets[:, 1])

    if not all_x:
        return preferred_locs[0]

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    xmid = (xlim[0] + xlim[1]) / 2
    ymid = (ylim[0] + ylim[1]) / 2

    # 统计每个象限的数据点密度
    quadrant_counts = {
        'upper right': 0, 'upper left': 0,
        'lower right': 0, 'lower left': 0,
        'center right': 0, 'center left': 0,
    }
    for x, y in zip(all_x, all_y):
        if y >= ymid:
            if x >= xmid:
                quadrant_counts['upper right'] += 1
            else:
                quadrant_counts['upper left'] += 1
        else:
            if x >= xmid:
                quadrant_counts['lower right'] += 1
            else:
                quadrant_counts['lower left'] += 1
        # center 区域
        if abs(y - ymid) < (ylim[1] - ylim[0]) * 0.25:
            if x >= xmid:
                quadrant_counts['center right'] += 1
            else:
                quadrant_counts['center left'] += 1

    # 在 preferred_locs 中选密度最低的
    best_loc = min(preferred_locs, key=lambda loc: quadrant_counts.get(loc, 999))
    return best_loc


def _declutter_dense_log_ticks(fig, *, max_minor_ticks=18, min_pitch_px=7.0):
    """Thin only Matplotlib's default log minor ticks when they form a comb.

    The operation is deliberately narrow: custom locators, major ticks, axis
    limits and data are untouched.  Dense default ``LogLocator`` ticks are
    reduced to 2 and 5 within each decade and their labels remain hidden.
    This is especially important for small panels and ``twinx`` axes, where
    eight minor marks per decade can visually merge into a black boundary.
    """
    try:
        from matplotlib.ticker import LogLocator, NullFormatter
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
    except Exception:
        return 0

    changed = 0
    for ax in fig.get_axes():
        if not ax.get_visible() or _is_3d_axis(ax):
            continue
        try:
            axes_box = ax.get_window_extent(renderer=renderer)
        except Exception:
            continue
        for direction, axis, scale, limits, span_px in (
            ('x', ax.xaxis, ax.get_xscale(), ax.get_xlim(), axes_box.width),
            ('y', ax.yaxis, ax.get_yscale(), ax.get_ylim(), axes_box.height),
        ):
            if scale != 'log' or span_px <= 0:
                continue
            locator = axis.get_minor_locator()
            # Respect intentional publication locators supplied by the author.
            if not isinstance(locator, LogLocator):
                continue
            subs = getattr(locator, '_subs', 'auto')
            if not isinstance(subs, str) and subs is not None:
                continue
            try:
                lo, hi = sorted(float(value) for value in limits)
                locs = np.asarray(axis.get_minorticklocs(), dtype=float)
                visible = locs[np.isfinite(locs) & (locs > 0) & (locs >= lo) & (locs <= hi)]
            except Exception:
                continue
            count = int(visible.size)
            pitch = float(span_px) / max(count, 1)
            if count <= max_minor_ticks and pitch >= min_pitch_px:
                continue
            try:
                base = float(getattr(locator, '_base', 10.0))
                axis.set_minor_locator(LogLocator(base=base, subs=(2.0, 5.0), numticks=100))
                axis.set_minor_formatter(NullFormatter())
                ax.tick_params(axis=direction, which='minor', length=2.0, width=0.45)
                changed += 1
            except Exception:
                continue
    try:
        fig._mh_log_tick_declutters = changed
    except Exception:
        pass
    return changed


def _collect_data_points(ax):
    """收集 axes 上所有数据点的**数据坐标**（供实测遮挡用）。

    line / scatter / bar 三类载体的取法都不同，漏一类就会把"其实遮住了"测成"没遮"。
    """
    import numpy as _np
    pts = []
    for line in ax.get_lines():
        xd, yd = line.get_xdata(), line.get_ydata()
        if len(xd):
            pts.append(_np.column_stack([_np.asarray(xd, float),
                                         _np.asarray(yd, float)]))
    for coll in ax.collections:
        n_off = 0
        try:
            off = coll.get_offsets()
            if off is not None and len(off):
                n_off = len(off)
                pts.append(_np.asarray(off, float))
        except Exception:
            pass
        # ⛔ 不能写成"有 offsets 就不看 paths"：`fill_between` 产出的
        #   FillBetweenPolyCollection 的 `get_offsets()` 返回的是**一个原点假点
        #   `[[0,0]]`（不是空数组）**，于是长度检查通过、真实轮廓被跳过 ——
        #   实测置信带只收到 3 个原点假货，"图例压在带子上"完全测不出来。
        # ⛔ 也不能无条件取 paths：`scatter` 的 paths 是 **marker 模板**（单位圆，
        #   顶点在 ±0.5），不是数据坐标，取了会把遮挡算到原点附近去。
        #   判据用"paths 顶点数 > offsets 行数"：
        #     scatter        26 顶点 vs 90 offsets → 不取（模板）
        #     fill_between  103 顶点 vs  1 offset  → 取（真轮廓）
        try:
            paths = coll.get_paths()
            if sum(len(p.vertices) for p in paths) > n_off:
                for path in paths:
                    v = path.vertices
                    if len(v):
                        pts.append(_np.asarray(v, float))
        except Exception:
            pass
    for p in ax.patches:
        try:
            x0, y0 = p.get_xy()               # 柱状图：覆盖柱体内部，而非只取柱顶
            w, h = p.get_width(), p.get_height()
            # 图例经常压在柱体中段；旧版只采三个柱顶点会把这种遮挡测成 0。
            # 3×3 固定网格足以判断，成本与柱数线性，不栅格化整个图形。
            gx = _np.linspace(x0, x0 + w, 3)
            gy = _np.linspace(y0, y0 + h, 3)
            xx, yy = _np.meshgrid(gx, gy)
            pts.append(_np.column_stack([xx.ravel(), yy.ravel()]))
            continue
        except Exception:
            pass
        # ⛔ ax.stairs 产出的是 StepPatch —— 是 Patch 但**没有 get_xy()**，
        #   上面那条会抛异常。而指南推荐用 stairs 画分布图，漏了它等于这类图测不出遮挡
        #   （实测过：返回 None → auto_legend 按"测不出"保持原样 → 图例照样压着数据）。
        #   get_path().vertices 对任何 Patch 子类都通用，比逐类特判稳。
        try:
            v = p.get_path().vertices
            if len(v):
                pts.append(_np.asarray(v, float))
        except Exception:
            continue
    # imshow / matshow 不在 collections 中。若不采样，热力图上的图例即使遮住
    # 整片色块也会得到“无数据点”的假通过。取固定 7×7 网格即可，无需读取像素。
    for image in getattr(ax, 'images', ()):
        try:
            if (not image.get_visible()
                    or (image.get_alpha() is not None and image.get_alpha() < 0.15)):
                continue
            x0, x1, y0, y1 = (float(v) for v in image.get_extent())
            gx = _np.linspace(x0, x1, 7)
            gy = _np.linspace(y0, y1, 7)
            xx, yy = _np.meshgrid(gx, gy)
            pts.append(_np.column_stack([xx.ravel(), yy.ravel()]))
        except Exception:
            continue
    if not pts:
        return None
    arr = _np.vstack(pts)
    return arr[_np.isfinite(arr).all(axis=1)]


def _legend_artist_hits(ax, leg, renderer=None):
    """Detect geometry crossing a legend, even between sparse samples."""
    from matplotlib.transforms import Bbox
    if leg is None or not leg.get_visible() or _is_3d_axis(ax):
        return 0
    if renderer is None:
        ax.figure.canvas.draw()
        renderer = ax.figure.canvas.get_renderer()
    overlap = Bbox.intersection(leg.get_window_extent(renderer), ax.get_window_extent(renderer))
    if overlap is None or overlap.width <= 1 or overlap.height <= 1:
        return 0
    obstacles = _display_artist_obstacles(ax, renderer)
    count = _line_hit_count(overlap, obstacles['paths'])
    count += sum(overlap.overlaps(box) for box in obstacles['markers'])
    count += sum(_rect_intersection_ratio(overlap, box) > .04 for box in obstacles['bars'])
    return count


def _unresolved_legend_data_collisions(fig):
    # Match placement geometry, including fills/images and legends owned by a
    # different panel. A legend outside its own axis can still cover its twin.
    scene = _legend_scene(fig)
    legends = [ax.get_legend() for ax in _legend_axes(fig)] + list(fig.legends)
    boxes = [leg.get_window_extent(scene[0]) for leg in legends
             if leg is not None and leg.get_visible()]
    return [index for index, item in enumerate(scene[4], 1)
            if any(_legend_hits_data(box, [item]) for box in boxes)]


def measure_legend_occlusion(ax, leg):
    """实测图例框盖住了多少个数据点。返回 (遮挡数, 总点数, 图例占绘图区比例)。

    为什么必须实测而不是数象限（check_legend_overlap 的老做法）：
        数象限只能挑出"相对最空"的角，**从不检查图例框放得下放不下**。数据铺满绘图区
        时它照样往里塞 —— 实测 5 条曲线铺满、400 个点，`loc='best'` 仍遮住 13~41 个点，
        而且和固定 `loc='upper right'` 的遮挡数差不多（只是位置不同）。
        真要判断"到底遮没遮"，只能把图例框和数据点都换算到显示坐标去比。
    拿不到渲染器（未 draw / 后端不支持）时返回 (None, None, None)，调用方按"测不出"处理。
    """
    data = _collect_data_points(ax)
    if data is None or leg is None:
        return None, None, None
    fig = ax.figure
    try:
        fig.canvas.draw()
        rend = fig.canvas.get_renderer()
        lb = leg.get_window_extent(rend)
        ab = ax.get_window_extent()
    except Exception:
        return None, None, None
    if lb.width <= 0 or ab.width <= 0:
        return None, None, None
    try:
        disp = ax.transData.transform(data)
    except Exception:
        return None, None, None
    inside = ((disp[:, 0] >= lb.x0) & (disp[:, 0] <= lb.x1) &
              (disp[:, 1] >= lb.y0) & (disp[:, 1] <= lb.y1))
    frac = (lb.width * lb.height) / (ab.width * ab.height)
    return int(inside.sum()), len(data), frac


def measure_legend_text_occlusion(ax, leg, *, overlap_ratio=0.10):
    """Return visible labels/titles materially covered by an axes legend.

    Data-point sampling alone misses a common failure: a legend can occupy a
    numerically empty corner while covering a panel letter, threshold label or
    statistics box.  Bounding boxes are compared in display coordinates so
    mixed transforms (data, axes and figure coordinates) are handled alike.
    """
    if leg is None:
        return []
    fig = ax.figure
    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        legend_box = leg.get_window_extent(renderer)
    except Exception:
        return []
    if legend_box.width <= 0 or legend_box.height <= 0:
        return []

    candidates = list(getattr(ax, 'texts', ()))
    candidates.extend([
        getattr(ax, 'title', None),
        getattr(ax, '_left_title', None),
        getattr(ax, '_right_title', None),
        getattr(ax.xaxis, 'label', None),
        getattr(ax.yaxis, 'label', None),
    ])
    candidates.extend(list(ax.get_xticklabels()) + list(ax.get_yticklabels()))
    candidates.extend(list(getattr(fig, 'texts', ())))

    hits = []
    seen = set()
    for item in candidates:
        if item is None or id(item) in seen:
            continue
        seen.add(id(item))
        try:
            if not item.get_visible() or not str(item.get_text()).strip():
                continue
            box = item.get_window_extent(renderer=renderer)
            # Coverage of the *text* is the meaningful quantity.  A small
            # annotation can be completely hidden by a large legend while
            # occupying only a tiny fraction of the legend itself.
            ratio = _rect_intersection_ratio(box, legend_box)
            intersection_w = max(0.0, min(legend_box.x1, box.x1) - max(legend_box.x0, box.x0))
            intersection_h = max(0.0, min(legend_box.y1, box.y1) - max(legend_box.y0, box.y0))
        except Exception:
            continue
        if ratio >= overlap_ratio and intersection_w >= 2.0 and intersection_h >= 2.0:
            hits.append(item)
    return hits


def _legend_axes(fig):
    """Include native inset axes, which Figure.axes does not enumerate."""
    pending = list(fig.axes)
    result, seen = [], set()
    while pending:
        ax = pending.pop(0)
        if id(ax) in seen:
            continue
        seen.add(id(ax))
        result.append(ax)
        pending.extend(getattr(ax, 'child_axes', ()))
    return result


def _legend_scene(fig, exclude=()):
    """Cache rendered obstacles once per bounded legend placement search."""
    from matplotlib.collections import PathCollection
    from matplotlib.legend import Legend
    from matplotlib.patches import Polygon, StepPatch
    from matplotlib.transforms import Bbox

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    excluded = {id(item) for item in exclude if item is not None}
    text_boxes, legend_boxes, data = [], [], []
    texts = list(fig.texts)
    for ax in _legend_axes(fig):
        if not ax.get_visible():
            continue
        ab = ax.get_window_extent(renderer).frozen()
        obstacles = _display_artist_obstacles(ax, renderer) if not _is_3d_axis(ax) else {
            'paths': [], 'markers': [], 'bars': [ab],
        }
        fills = []
        # stairs() is a StepPatch, not a line or a collection. Its filled
        # interior is data too; vertex-only sampling misses a legend in it.
        for patch in ax.patches:
            if isinstance(patch, (Polygon, StepPatch)) and patch.get_visible():
                path = patch.get_path().transformed(patch.get_transform())
                if patch.get_fill() and patch.get_facecolor()[3] > 0:
                    fills.append(path)
                elif patch.get_edgecolor()[3] > 0:
                    obstacles['paths'].append(path)
        for coll in ax.collections:
            if isinstance(coll, PathCollection) or not coll.get_visible():
                continue
            try:
                if coll.get_alpha() == 0 or not len(coll.get_facecolors()):
                    continue
                if not np.any(coll.get_facecolors()[:, 3] > 0):
                    continue
                fills.extend(path.transformed(coll.get_transform()) for path in coll.get_paths())
            except (AttributeError, ValueError, TypeError):
                pass
        images = [item.get_window_extent(renderer).frozen() for item in ax.images
                  if item.get_visible() and item.get_alpha() != 0]
        data.append((ab, obstacles, fills, images))
        texts.extend(ax.texts)
        texts.extend([ax.title, getattr(ax, '_left_title', None), getattr(ax, '_right_title', None)])
        if ax.axison:
            for axis in (ax.xaxis, ax.yaxis):
                if axis.get_visible():
                    texts.extend([axis.label, axis.get_offset_text()])
            texts.extend(_onscreen_tick_labels(ax))
        for item in ax.get_children():
            if isinstance(item, Legend) and id(item) not in excluded and item.get_visible():
                legend_boxes.append(item.get_window_extent(renderer).frozen())
    for item in fig.legends:
        if id(item) not in excluded and item.get_visible():
            legend_boxes.append(item.get_window_extent(renderer).frozen())
    seen = set()
    for item in texts:
        if item is None or id(item) in seen:
            continue
        seen.add(id(item))
        if item.get_visible() and item.get_text().strip():
            box = item.get_window_extent(renderer)
            if box.width > 0 and box.height > 0 and Bbox.intersection(box, fig.bbox) is not None:
                text_boxes.append(box.frozen())
    return renderer, fig.bbox.frozen(), text_boxes, legend_boxes, data


def _legend_box_safe(box, scene, *, within=None):
    """Actual free space, including adjacent/twin axes; not an area quota."""
    from matplotlib.transforms import Bbox
    _renderer, canvas, texts, legends, data = scene
    bounds = canvas if within is None else within
    if (box.x0 < bounds.x0 - .5 or box.y0 < bounds.y0 - .5
            or box.x1 > bounds.x1 + .5 or box.y1 > bounds.y1 + .5):
        return False
    for other in texts + legends:
        overlap = Bbox.intersection(box, other)
        if (overlap is not None and overlap.width > 2 and overlap.height > 2
                and _rect_intersection_ratio(other, box) >= .10):
            return False
    return not _legend_hits_data(box, data)


def _legend_hits_data(box, data):
    from matplotlib.transforms import Bbox
    for ab, obstacles, fills, images in data:
        overlap = Bbox.intersection(box, ab)
        if overlap is None or overlap.width <= 1 or overlap.height <= 1:
            continue
        if _line_hit_count(overlap, obstacles['paths']):
            return True
        if any(overlap.overlaps(other) for other in obstacles['markers'] + obstacles['bars'] + images):
            return True
        if any(path.intersects_bbox(overlap, filled=True) for path in fills):
            return True
    return False


def _legend_properties(legend):
    """Retain proxy handles, typography, title, and the author's column count."""
    handles = list(getattr(legend, 'legend_handles', getattr(legend, 'legendHandles', ())))
    kw = dict(handles=handles, labels=[item.get_text() for item in legend.get_texts()],
              frameon=legend.get_frame_on(), ncol=getattr(legend, '_ncols', 1))
    if legend.get_texts():
        kw['prop'] = legend.get_texts()[0].get_fontproperties().copy()
    title = legend.get_title()
    if title.get_text():
        kw.update(title=title.get_text(), title_fontproperties=title.get_fontproperties().copy())
    for name in ('numpoints', 'scatterpoints', 'markerscale', 'borderpad', 'labelspacing',
                 'handlelength', 'handleheight', 'handletextpad', 'borderaxespad', 'columnspacing'):
        kw[name] = getattr(legend, name)
    if getattr(legend, '_custom_handler_map', None):
        kw['handler_map'] = legend._custom_handler_map
    return kw


def _restore_legend_lane(fig, legend):
    """Reflow an enlarged managed legend from its base, not a shrinking loop."""
    state = getattr(legend, '_mh_lane_layout', None)
    if state and set(state['placed']) == set(fig.axes) and all(
            np.allclose(ax.get_position().extents, box.extents, atol=1e-6)
            for ax, box in state['placed'].items()):
        for ax, box in state['base'].items():
            ax.set_position(box)


def _legend_lane(fig, axes, handles, labels, *, owner=None, where='auto', ncol=None,
                 exclude=(), **kwargs):
    """Measured compact top/right lane, after in-panel alternatives are exhausted.

    Settle the active layout, then reserve space within the owning panel and
    its twins, or the whole group for a shared legend. Never mutate global
    subplot margins to fix one panel. Fonts and data are untouched.
    """
    from matplotlib.legend import Legend
    from matplotlib.transforms import Bbox

    if where not in ('auto', 'top', 'right'):
        raise ValueError("legend where must be 'auto', 'top' or 'right'")
    scene = _legend_scene(fig, exclude)
    renderer = scene[0]
    group = list(dict.fromkeys(axes))
    positions = {ax: ax.get_position().frozen() for ax in fig.axes}
    region = Bbox.union([positions[ax] for ax in group])
    pixel_region = region.transformed(fig.transFigure)
    gap = 5 * fig.dpi / 72.0
    top_extra = right_extra = 0.0
    for ax in group:
        ab = ax.get_window_extent(renderer)
        tight = ax.get_tightbbox(renderer, bbox_extra_artists=[])
        if tight is not None:
            top_extra = max(top_extra, tight.y1 - ab.y1)
            right_extra = max(right_extra, tight.x1 - ab.x1)
    clean = dict(kwargs)
    for key in ('loc', 'bbox_to_anchor', 'bbox_transform', 'mode', 'ncols', 'borderaxespad'):
        clean.pop(key, None)
    parent = owner if owner is not None else fig
    # Include wider compact rows for many short labels without trying every
    # permutation. At most ten measured column counts, then twelve layouts.
    column_choices = sorted(set(range(1, min(len(labels), 6) + 1)) |
                            {int(np.ceil(len(labels) / rows)) for rows in range(1, 5)})
    if ncol is not None:
        preferred = max(1, min(int(ncol), len(labels)))
        column_choices = [preferred] + [value for value in column_choices if value != preferred]
    options = []
    for columns in column_choices:
        probe = Legend(parent, handles, labels, loc='center', ncols=columns,
                       borderaxespad=0, **clean)
        box = probe.get_window_extent(renderer)
        w, h = box.width, box.height
        if w <= pixel_region.width and h + gap + top_extra < pixel_region.height * .70:
            options.append(((h + gap + top_extra) / pixel_region.height, 'top', columns, w, h))
        if h <= pixel_region.height and w + gap + right_extra < pixel_region.width * .70:
            options.append(((w + gap + right_extra) / pixel_region.width, 'right', columns, w, h))
    # Direction and column count are preferences, never permission to clip.
    options.sort(key=lambda opt: (where != 'auto' and opt[1] != where,
                                  opt[0] + (.03 if ncol is not None and opt[2] != int(ncol) else 0),
                                  opt[2]))
    engine = fig.get_layout_engine()
    manual = getattr(fig, '_mh_manual_layout', False)
    layout_flags = {ax: ax.get_in_layout() for ax in fig.axes}
    committed = False
    try:
        for _cost, side, columns, width, height in options[:12]:
            if side == 'top':
                ratio = 1 - (height + gap + top_extra) / pixel_region.height
                new_region = Bbox.from_extents(region.x0, region.y0, region.x1,
                                               region.y0 + region.height * ratio)
                loc, anchor = 'upper center', ((region.x0 + region.x1) / 2, region.y1)
            else:
                ratio = 1 - (width + gap + right_extra) / pixel_region.width
                new_region = Bbox.from_extents(region.x0, region.y0,
                                               region.x0 + region.width * ratio, region.y1)
                loc, anchor = 'center right', (region.x1, (region.y0 + region.y1) / 2)
            fig.set_layout_engine('none')
            for ax, pos in positions.items():
                if ax in group:
                    x = new_region.x0 + (pos.x0 - region.x0) * new_region.width / region.width
                    y = new_region.y0 + (pos.y0 - region.y0) * new_region.height / region.height
                    ax.set_position([x, y, pos.width * new_region.width / region.width,
                                     pos.height * new_region.height / region.height])
                else:
                    ax.set_position(pos)
            candidate = Legend(parent, handles, labels, loc=loc, ncols=columns,
                               bbox_to_anchor=anchor, bbox_transform=fig.transFigure,
                               borderaxespad=0, **clean)
            updated = _legend_scene(fig, exclude)
            if _legend_box_safe(candidate.get_window_extent(updated[0]), updated):
                make = owner.legend if owner is not None else fig.legend
                result = make(handles, labels, loc=loc, ncols=columns,
                              bbox_to_anchor=anchor, bbox_transform=fig.transFigure,
                              borderaxespad=0, **clean)
                result._mh_lane_layout = {
                    'base': positions, 'placed': {ax: ax.get_position().frozen() for ax in fig.axes},
                    'side': side,
                }
                fig._mh_manual_layout = True
                committed = True
                return result
    finally:
        if not committed:
            for ax, pos in positions.items():
                ax.set_position(pos)
                ax.set_in_layout(layout_flags[ax])
            fig.set_layout_engine(engine if engine is not None else 'none')
            fig._mh_manual_layout = manual
    raise RuntimeError('图例在当前画布内无安全位置；请缩短说明性标签或重排面板，不能缩小必要文字。')


def _legend_outside(ax, where='auto', ncol=None, **kw):
    """Use a measured compact lane, rather than a fixed expanded top strip."""
    fig = ax.figure
    handles, labels = ax.get_legend_handles_labels()
    handles = list(kw.pop('handles', handles))
    labels = list(kw.pop('labels', labels))
    if not handles or not labels:
        return ax.legend(handles, labels, **kw)
    ncol = kw.pop('ncols', ncol)
    fig.canvas.draw()
    own = ax.get_position()
    group = [other for other in fig.axes if other is ax or (
        other.get_visible() and np.allclose(other.get_position().extents, own.extents, atol=1e-6))]
    for other in fig.axes:
        parents = getattr(other, '_colorbar_info', {}).get('parents', [])
        if parents and all(parent in group for parent in parents) and other not in group:
            group.append(other)
    return _legend_lane(fig, group, handles, labels, owner=ax, where=where,
                        ncol=ncol, exclude=[ax.get_legend()], **kw)


# Retained for callers using the measurement API. Area alone is not a clash.
_LEGEND_OCC_TOL = 0.02
_LEGEND_FRAC_TOL = 0.16


def auto_legend(ax, outside=None, where='auto', occ_tol=None, verbose=False, **kwargs):
    """Keep a safe original position, try real inside space, then an outside lane.

    loc/bbox/ncol remain author preferences. All candidates are measured against
    data geometry, fills, labels, twins and neighbouring panels. occ_tol remains
    accepted for source compatibility, but does not permit covering geometry.
    outside=False is a placement preference; the final save guard still checks it.
    """
    defaults = dict(frameon=False, fontsize=9, labelspacing=0.35, handlelength=1.6,
                    borderpad=0.3, fancybox=False, shadow=False)
    if where not in ('auto', 'top', 'right'):
        raise ValueError("legend where must be 'auto', 'top' or 'right'")
    existing = ax.get_legend()
    if existing is not None and not kwargs and outside is None:
        scene = _legend_scene(ax.figure, [existing])
        if _legend_box_safe(existing.get_window_extent(scene[0]), scene):
            return existing
        defaults.update(_legend_properties(existing))
        defaults['loc'] = existing._loc
    defaults.update(kwargs)
    if outside is True:
        return _legend_outside(ax, where=where, **defaults)
    defaults.setdefault('loc', 'upper right')
    leg = ax.legend(**defaults)
    if outside is False or not leg.get_texts():
        return leg
    scene = _legend_scene(ax.figure, [leg])
    if _legend_box_safe(leg.get_window_extent(scene[0]), scene):
        return leg
    # Preserve the original box/columns first; other positions must fit wholly
    # inside the data axis, not creep into the neighbouring panel.
    inner = dict(defaults)
    for key in ('bbox_to_anchor', 'bbox_transform', 'mode', 'loc'):
        inner.pop(key, None)
    for loc in ('upper right', 'upper left', 'lower right', 'lower left',
                'center right', 'center left', 'upper center', 'lower center', 'center'):
        leg = ax.legend(loc=loc, **inner)
        if _legend_box_safe(leg.get_window_extent(scene[0]), scene,
                            within=ax.get_window_extent(scene[0])):
            if verbose:
                print('[auto_legend] safe inside location:', loc)
            return leg
    # Keep the last live legend until a replacement succeeds.
    return _legend_outside(ax, where=where, **inner)


def _repair_legend_occlusion(fig):
    """Preserve safe originals; repair actual clashes, not legend area quotas."""
    repaired = 0
    for ax in fig.get_axes():
        legend = ax.get_legend()
        if legend is None or not legend.get_visible() or not ax.get_visible() or _is_3d_axis(ax):
            continue
        scene = _legend_scene(fig, [legend])
        if _legend_box_safe(legend.get_window_extent(scene[0]), scene):
            continue
        kwargs = _legend_properties(legend)
        if not kwargs['handles'] or not kwargs['labels']:
            continue
        _restore_legend_lane(fig, legend)
        try:
            replacement = auto_legend(ax, loc=legend._loc,
                                      bbox_to_anchor=legend.get_bbox_to_anchor().transformed(fig.transFigure.inverted()),
                                      bbox_transform=fig.transFigure, **kwargs)
            repaired += int(replacement is not None)
        except RuntimeError:
            # Leave a live legend. The final objective collision/clipping check
            # reports the unresolved geometry, not a subjective layout choice.
            pass
    # Figure-level legends also change size after the print-font pass. Do not
    # leave shared legends outside the same repair path used for axes legends.
    for legend in list(fig.legends):
        if not legend.get_visible():
            continue
        scene = _legend_scene(fig, [legend])
        if _legend_box_safe(legend.get_window_extent(scene[0]), scene):
            continue
        kwargs = _legend_properties(legend)
        if not kwargs['handles'] or not kwargs['labels']:
            continue
        _restore_legend_lane(fig, legend)
        try:
            replacement = _legend_lane(
                fig, [ax for ax in fig.axes if ax.get_visible()],
                kwargs.pop('handles'), kwargs.pop('labels'), exclude=[legend], **kwargs)
            if getattr(fig, '_mh_shared_legend_artist', None) is legend:
                replacement._mh_signature = getattr(legend, '_mh_signature', None)
                fig._mh_shared_legend_artist = replacement
            legend.remove()
            repaired += 1
        except RuntimeError:
            pass
    fig._mh_legend_repairs = repaired
    return repaired


def _unresolved_legend_text_collisions(fig):
    """Return concise diagnostics for legends still covering visible text."""
    from matplotlib.transforms import Bbox
    scene = _legend_scene(fig)
    issues = []
    owned = [(i, ax.get_legend()) for i, ax in enumerate(_legend_axes(fig), 1) if ax.get_visible()]
    owned.extend((0, legend) for legend in fig.legends)
    live = [(i, leg) for i, leg in owned if leg is not None and leg.get_visible()]
    boxes = {id(leg): leg.get_window_extent(scene[0]) for _, leg in live}
    for index, legend in live:
        box = boxes[id(legend)]
        others = scene[2] + [other for key, other in boxes.items() if key != id(legend)]
        for other in others:
            intersection = Bbox.intersection(box, other)
            if (intersection is not None and intersection.width > 2 and intersection.height > 2
                    and _rect_intersection_ratio(other, box) >= .10):
                issues.append((index, '相邻标注或图例'))
                break
        if len(issues) >= 8:
            break
    return issues


def _axes_list(axes):
    """Flatten common axes containers without treating strings as iterables."""
    if axes is None:
        return []
    if hasattr(axes, 'plot'):
        return [axes]
    try:
        return [item for item in np.asarray(axes, dtype=object).ravel()
                if item is not None and hasattr(item, 'plot')]
    except Exception:
        return []


def shared_legend(fig, axes=None, *, where='auto', ncol=None, title=None,
                  remove_axes_legends=True, deduplicate=True, **kwargs):
    """Compact measured shared lane for genuinely common series.

    The caller decides semantic equivalence. Explicit top/right preferences
    remain available; auto chooses the fitting lane consuming less panel area.
    """
    axes_list = _axes_list(axes) if axes is not None else [
        ax for ax in fig.get_axes() if ax.get_visible() and not _is_3d_axis(ax)
    ]
    handles, labels, seen = [], [], set()
    for ax in axes_list:
        hh, ll = ax.get_legend_handles_labels()
        for handle, label in zip(hh, ll):
            label = str(label).strip()
            if not label or label.startswith('_') or (deduplicate and label in seen):
                continue
            seen.add(label)
            handles.append(handle)
            labels.append(label)
    if not handles:
        return None
    if where not in ('auto', 'top', 'right'):
        raise ValueError("shared_legend where must be 'auto', 'top' or 'right'")
    old = getattr(fig, '_mh_shared_legend_artist', None)
    excluded = [ax.get_legend() for ax in axes_list] if remove_axes_legends else []
    # Explicit handles are already gathered from the caller's axes. Do not
    # consume a second strip on repeated invocations of the same shared legend.
    signature = (tuple(id(ax) for ax in axes_list), tuple(labels), tuple(id(h) for h in handles),
                 where, ncol, title, repr(kwargs))
    if old in fig.legends and getattr(old, '_mh_signature', None) == signature:
        scene = _legend_scene(fig, excluded + [old])
        if _legend_box_safe(old.get_window_extent(scene[0]), scene):
            return old
    if old in fig.legends:
        _restore_legend_lane(fig, old)
    defaults = dict(frameon=False, labelspacing=0.35, handlelength=1.8,
                    borderpad=0.2, fancybox=False, shadow=False)
    defaults.update(kwargs)
    # A shared lane moves the figure's visible axes together, including colour
    # bars, rather than leaving a colourbar across a newly reserved legend row.
    group = [ax for ax in fig.axes if ax.get_visible()]
    legend = _legend_lane(fig, group, handles, labels, where=where, ncol=ncol,
                          title=title, exclude=excluded + [old], **defaults)
    for item in excluded + ([old] if old in fig.legends else []):
        if item is not None:
            item.remove()
    legend._mh_signature = signature
    fig._mh_shared_legend_artist = legend
    fig._mh_shared_legend = {'where': legend._mh_lane_layout['side'], 'labels': tuple(labels)}
    return legend


def consolidate_shared_legends(fig, axes, *, where='auto', min_series=2,
                               **kwargs):
    """Consolidate legends only when at least two panels share one label set."""
    candidates = []
    for ax in _axes_list(axes):
        labels = tuple(label for label in ax.get_legend_handles_labels()[1]
                       if label and not str(label).startswith('_'))
        if len(labels) >= min_series:
            candidates.append((ax, labels))
    if len(candidates) < 2:
        return None
    reference = candidates[0][1]
    if any(set(labels) != set(reference) for _ax, labels in candidates[1:]):
        return None
    return shared_legend(fig, [ax for ax, _labels in candidates], where=where, **kwargs)


def uncertainty_band(ax, x, lower, upper, *, color=None, alpha=0.14,
                     label=None, zorder=1, **kwargs):
    """Draw a validated uncertainty interval behind its central line.

    Bounds must have equal one-dimensional shapes and satisfy ``lower <= upper``
    at every finite sample.  Invalid intervals fail loudly instead of creating
    self-crossing shaded polygons that look plausible but are mathematically
    wrong.
    """
    x = np.asarray(x)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    if x.ndim != 1 or lower.ndim != 1 or upper.ndim != 1:
        raise ValueError('uncertainty band inputs must be one-dimensional')
    if not (x.shape == lower.shape == upper.shape):
        raise ValueError('x, lower and upper must have identical shapes')
    finite = np.isfinite(lower) & np.isfinite(upper)
    if np.any(lower[finite] > upper[finite]):
        raise ValueError('uncertainty lower bound exceeds upper bound')
    if color is None:
        color = COLORS['secondary']
    defaults = {'linewidth': 0, 'edgecolor': 'none'}
    defaults.update(kwargs)
    return ax.fill_between(
        x, lower, upper, where=finite, interpolate=True, color=color,
        alpha=float(alpha), label=label, zorder=zorder, **defaults
    )


def dynamic_limits(ax, *, x=None, y=None, pad=0.06, include_zero=False):
    """Set compact, data-driven limits while respecting linear/log scales."""
    if not 0 <= float(pad) <= 0.5:
        raise ValueError('pad must be within [0, 0.5]')

    def _flatten(values):
        if values is None:
            return np.array([], dtype=float)
        try:
            if isinstance(values, (list, tuple)) and values and not np.isscalar(values[0]):
                arrays = [np.asarray(item, dtype=float).ravel() for item in values]
                return np.concatenate(arrays) if arrays else np.array([], dtype=float)
            return np.asarray(values, dtype=float).ravel()
        except (TypeError, ValueError):
            # Datetime and categorical axes already have suitable locators;
            # leaving their current limits is safer than coercing them.
            return np.array([], dtype=float)

    def _apply(values, scale, setter):
        values = _flatten(values)
        values = values[np.isfinite(values)]
        if scale == 'log':
            values = values[values > 0]
        if not len(values):
            return
        lo, hi = float(np.min(values)), float(np.max(values))
        if include_zero and scale != 'log':
            lo, hi = min(lo, 0.0), max(hi, 0.0)
        if scale == 'log':
            if lo == hi:
                lo, hi = lo / 1.4, hi * 1.4
            else:
                factor = (hi / lo) ** float(pad)
                lo, hi = lo / factor, hi * factor
        else:
            span = hi - lo
            if span <= 0:
                span = max(abs(lo) * 0.10, 1.0)
            lo, hi = lo - span * float(pad), hi + span * float(pad)
            if include_zero:
                if np.min(values) >= 0:
                    lo = 0.0
                if np.max(values) <= 0:
                    hi = 0.0
        setter(lo, hi)

    if x is not None:
        _apply(x, ax.get_xscale(), ax.set_xlim)
    if y is not None:
        _apply(y, ax.get_yscale(), ax.set_ylim)
    return ax


def declutter_axes(ax, *, grid='auto', grid_axis='y'):
    """Apply restrained spines and optional low-contrast reading guides."""
    if getattr(ax, 'name', '') == 'polar' or _is_3d_axis(ax):
        return ax
    for side in ('top', 'right'):
        try:
            ax.spines[side].set_visible(False)
        except Exception:
            pass
    if grid == 'auto':
        # Heatmaps already encode position with cell boundaries; extra grid
        # lines reduce contrast.  Ordinary quantitative axes benefit from a
        # quiet guide on the value dimension.
        grid = not bool(ax.images) and not bool(getattr(ax, '_mh_vector_heatmap', False))
    if grid:
        ax.grid(True, axis=grid_axis, color=COLORS.get('grid', '#E0E0E0'),
                linestyle='--', linewidth=0.55, alpha=0.28)
        ax.set_axisbelow(True)
    else:
        ax.grid(False)
    return ax


# ============================================================
# 图表函数
# ============================================================

def draw_vector_heatmap(ax, data, *, xlabels=None, ylabels=None, mask=None,
                        annot='auto', annot_limit=48, fmt='.2f', cmap='coolwarm',
                        vmin=None, vmax=None, center=None, square=False,
                        origin='upper', cbar=True, cbar_label=None, cax=None,
                        cell_linewidth=0.35):
    """Draw a vector-cell heatmap with background-aware text contrast.

    Unlike ``imshow``, every cell is a vector rectangle in the PDF.  The same
    rectangle is visible to the save-time contrast guard and the final PDF
    checker, so a dark cell cannot end up with an unreadable gray label.

    ``annot='auto'`` writes values only when the visible matrix has at most
    ``annot_limit`` cells.  Dense matrices retain the color encoding and move
    exact values to a table rather than covering the plot with tiny numbers.
    """
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize, TwoSlopeNorm, to_rgba
    from matplotlib.patches import Rectangle

    if cax is not None and cax.figure is not ax.figure:
        raise ValueError('colorbar axes must belong to the heatmap figure')
    values = np.asarray(data, dtype=float)
    if values.ndim != 2 or values.size == 0:
        raise ValueError('heatmap data must be a non-empty 2D array')
    rows, cols = values.shape
    if xlabels is not None and len(xlabels) != cols:
        raise ValueError('xlabels length must match heatmap columns')
    if ylabels is not None and len(ylabels) != rows:
        raise ValueError('ylabels length must match heatmap rows')
    if mask is None:
        mask_array = np.zeros_like(values, dtype=bool)
    else:
        mask_array = np.asarray(mask, dtype=bool)
        if mask_array.shape != values.shape:
            raise ValueError('heatmap mask shape must match data')
    visible = np.isfinite(values) & ~mask_array
    finite = values[visible]
    if not len(finite):
        raise ValueError('heatmap has no finite, unmasked cells')
    lo = float(np.min(finite) if vmin is None else vmin)
    hi = float(np.max(finite) if vmax is None else vmax)
    if not np.isfinite(lo) or not np.isfinite(hi) or lo > hi:
        raise ValueError('invalid heatmap color limits')
    if lo == hi:
        delta = max(abs(lo) * 0.05, 0.5)
        lo, hi = lo - delta, hi + delta
    if center is not None and lo < float(center) < hi:
        norm = TwoSlopeNorm(vmin=lo, vcenter=float(center), vmax=hi)
    else:
        norm = Normalize(vmin=lo, vmax=hi)
    cmap_obj = _get_plt().get_cmap(cmap)

    annotate = bool(annot)
    if annot == 'auto':
        annotate = int(np.count_nonzero(visible)) <= int(annot_limit)
    elif annot not in (True, False):
        raise ValueError("annot must be True, False or 'auto'")

    for row in range(rows):
        for col in range(cols):
            if not visible[row, col]:
                continue
            value = float(values[row, col])
            face = cmap_obj(norm(value))
            ax.add_patch(Rectangle(
                (col - 0.5, row - 0.5), 1.0, 1.0,
                facecolor=face, edgecolor='white', linewidth=cell_linewidth,
            ))
            if annotate:
                black = _contrast_ratio_rgb(to_rgba('#222222'), face)
                white = _contrast_ratio_rgb(to_rgba('white'), face)
                ink = '#222222' if black >= white else 'white'
                try:
                    text = format(value, fmt)
                except (ValueError, TypeError):
                    text = f'{value:.2f}'
                ax.text(col, row, text, ha='center', va='center', color=ink)

    ax.set_xlim(-0.5, cols - 0.5)
    ax.set_ylim((rows - 0.5, -0.5) if origin == 'upper' else (-0.5, rows - 0.5))
    ax.set_xticks(np.arange(cols))
    ax.set_yticks(np.arange(rows))
    if xlabels is not None:
        rotation = 35 if max((len(str(v)) for v in xlabels), default=0) > 6 else 0
        ax.set_xticklabels(xlabels, rotation=rotation,
                           ha='right' if rotation else 'center')
    if ylabels is not None:
        ax.set_yticklabels(ylabels)
    ax.set_aspect('equal' if square else 'auto')
    ax._mh_vector_heatmap = True
    declutter_axes(ax, grid=False)
    scalar = ScalarMappable(norm=norm, cmap=cmap_obj)
    scalar.set_array([])
    colorbar = None
    if cbar:
        colorbar = ax.figure.colorbar(scalar, ax=ax, cax=cax, fraction=0.047, pad=0.035)
        if cbar_label:
            colorbar.set_label(cbar_label)
        colorbar.outline.set_linewidth(0.7)
    return scalar, colorbar


def vector_heatmap(data, *, output='figures/fig_heatmap.pdf', figsize=(6.2, 4.6),
                   **kwargs):
    """Create and save a publication-ready vector heatmap."""
    plt = _get_plt()
    setup_style()
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    set_paper_placement(fig)
    draw_vector_heatmap(ax, data, **kwargs)
    _save(fig, output)


def heatmap(data, labels=None, output='figures/fig_heatmap.pdf', title=None,
            annot='auto', fmt='.2f', cmap='coolwarm', figsize=(6.2, 4.6)):
    """Correlation heatmap compatibility wrapper using vector cells."""
    values = np.asarray(data, dtype=float)
    mask = np.triu(np.ones_like(values, dtype=bool), k=1)
    return vector_heatmap(
        values, output=output, figsize=figsize, xlabels=labels, ylabels=labels,
        mask=mask, annot=annot, fmt=fmt, cmap=cmap, center=0, square=True,
    )


def forest_plot(coefs, ci_lower, ci_upper, labels, output='figures/fig_forest.pdf',
                figsize=(6, None), xlabel='Coefficient'):
    """回归系数森林图（带置信区间）。
    
    Args:
        coefs: 系数数组
        ci_lower: 置信区间下界
        ci_upper: 置信区间上界
        labels: 变量名列表
        output: 输出路径
    """
    plt = _get_plt()
    setup_style()
    n = len(coefs)
    if figsize[1] is None:
        figsize = (figsize[0], max(3, n * 0.4 + 1))
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    set_paper_placement(fig)

    y_pos = np.arange(n)
    xerr = [np.array(coefs) - np.array(ci_lower), np.array(ci_upper) - np.array(coefs)]

    ax.errorbar(coefs, y_pos, xerr=xerr, fmt='o', color=COLORS['primary'],
                ecolor=COLORS['gray'], elinewidth=1.5, capsize=3, markersize=5)
    ax.axvline(x=0, color=COLORS['accent'], linestyle='--', linewidth=0.8, alpha=0.7)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel(xlabel)
    ax.invert_yaxis()
    dynamic_limits(ax, x=[ci_lower, ci_upper], pad=0.08)
    declutter_axes(ax, grid=True, grid_axis='x')

    _save(fig, output)


def trend_plot(x, y, output='figures/fig_trend.pdf', ci=None,
               xlabel='', ylabel='', label=None, figsize=(7, 4)):
    """时间趋势图（可选置信带）。
    
    Args:
        x: x 轴数据
        y: y 轴数据
        ci: (lower, upper) 置信区间元组，可选
        output: 输出路径
    """
    plt = _get_plt()
    setup_style()
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    set_paper_placement(fig)

    if ci is not None:
        if not isinstance(ci, (tuple, list)) or len(ci) != 2:
            raise ValueError('ci must be a (lower, upper) pair')
        uncertainty_band(ax, x, ci[0], ci[1], color=COLORS['primary'])
        y_extent = [y, ci[0], ci[1]]
    else:
        y_extent = y
    ax.plot(x, y, color=COLORS['primary'], linewidth=1.7, label=label, zorder=2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    dynamic_limits(ax, x=x, y=y_extent, pad=0.06)
    declutter_axes(ax, grid=True, grid_axis='y')
    if label:
        auto_legend(ax)

    _save(fig, output)


def bar_compare(categories, values_dict, output='figures/fig_bar.pdf',
                ylabel='', figsize=(7, 4), show_values='auto'):
    """分组柱状图（带误差棒，多组对比）。
    
    Args:
        categories: 类别列表 ['A', 'B', 'C']
        values_dict: {'方法1': [v1, v2, v3], '方法2': [v1, v2, v3]}
                     或 {'方法1': {'values': [...], 'errors': [...]}}
        output: 输出路径
    """
    plt = _get_plt()
    setup_style()
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    set_paper_placement(fig)

    n_groups = len(categories)
    n_bars = len(values_dict)
    bar_width = 0.8 / n_bars
    x = np.arange(n_groups)

    y_extent = []
    for i, (name, data) in enumerate(values_dict.items()):
        if isinstance(data, dict):
            vals = data['values']
            errs = data.get('errors', None)
        else:
            vals = data
            errs = None
        vals = np.asarray(vals, dtype=float)
        if len(vals) != n_groups:
            raise ValueError(f'{name}: values length must match categories')
        y_extent.append(vals)
        if errs is not None:
            errs = np.asarray(errs, dtype=float)
            if errs.shape != vals.shape or np.any(errs < 0):
                raise ValueError(f'{name}: errors must be non-negative and match values')
            y_extent.extend([vals - errs, vals + errs])
        offset = (i - n_bars / 2 + 0.5) * bar_width
        bars = ax.bar(x + offset, vals, bar_width, label=name,
                       color=PALETTE[i % len(PALETTE)], yerr=errs,
                       capsize=3, error_kw={'linewidth': 0.8})
        label_values = show_values is True or (
            show_values == 'auto' and n_groups * n_bars <= 8
        )
        if label_values:
            ax.bar_label(bars, fmt='%.2f', padding=2)

    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylabel(ylabel)
    dynamic_limits(ax, y=y_extent, pad=0.08, include_zero=True)
    declutter_axes(ax, grid=True, grid_axis='y')
    auto_legend(ax)

    _save(fig, output)


def distribution_plot(data, output='figures/fig_dist.pdf', xlabel='', bins=30, figsize=(6, 4)):
    """核密度 + 直方图。"""
    plt = _get_plt()
    sns = _get_sns()
    setup_style()
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    set_paper_placement(fig)

    if sns:
        sns.histplot(data, bins=bins, kde=True, color=COLORS['secondary'], ax=ax,
                     edgecolor='white', linewidth=0.5)
    else:
        ax.hist(data, bins=bins, density=True, color=COLORS['secondary'],
                edgecolor='white', linewidth=0.5, alpha=0.7)
    ax.set_xlabel(xlabel)
    ax.set_ylabel('Density')

    _save(fig, output)


def scatter_plot(x, y, output='figures/fig_scatter.pdf', xlabel='', ylabel='',
                 hue=None, fit_line=True, figsize=(6, 5)):
    """散点图（可选回归线）。"""
    plt = _get_plt()
    setup_style()
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    if hue is not None:
        for i, (name, mask) in enumerate(hue.items()):
            ax.scatter(np.array(x)[mask], np.array(y)[mask], s=20, alpha=0.6,
                       color=PALETTE[i % len(PALETTE)], label=name)
        auto_legend(ax)
    else:
        ax.scatter(x, y, s=20, alpha=0.6, color=COLORS['secondary'])

    if fit_line:
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        x_line = np.linspace(min(x), max(x), 100)
        ax.plot(x_line, p(x_line), color=COLORS['accent'], linewidth=1, linestyle='--')

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    dynamic_limits(ax, x=x, y=y, pad=0.06)
    declutter_axes(ax, grid=True, grid_axis='y')

    _save(fig, output)


def residual_diagnostic(y_true, y_pred, output='figures/fig_residual.pdf', figsize=(10, 8)):
    """残差诊断四图（QQ图、残差散点、残差直方图、拟合值vs残差）。"""
    plt = _get_plt()
    setup_style()
    fig, axes = plt.subplots(2, 2, figsize=figsize)
    residuals = np.array(y_true) - np.array(y_pred)
    std_resid = (residuals - residuals.mean()) / residuals.std()

    # 1. 残差 vs 拟合值
    ax = axes[0, 0]
    ax.scatter(y_pred, residuals, s=15, alpha=0.5, color=COLORS['secondary'])
    ax.axhline(y=0, color=COLORS['accent'], linestyle='--', linewidth=0.8)
    ax.set_xlabel('Fitted Values')
    ax.set_ylabel('Residuals')

    # 2. QQ 图
    ax = axes[0, 1]
    sorted_resid = np.sort(std_resid)
    n = len(sorted_resid)
    theoretical = np.array([_norm_ppf((i + 0.5) / n) for i in range(n)])
    ax.scatter(theoretical, sorted_resid, s=15, alpha=0.5, color=COLORS['secondary'])
    lim = max(abs(theoretical.min()), abs(theoretical.max())) * 1.1
    ax.plot([-lim, lim], [-lim, lim], color=COLORS['accent'], linestyle='--', linewidth=0.8)
    ax.set_xlabel('Theoretical Quantiles')
    ax.set_ylabel('Standardized Residuals')

    # 3. 残差直方图
    ax = axes[1, 0]
    ax.hist(residuals, bins=25, color=COLORS['secondary'], edgecolor='white', linewidth=0.5, density=True)
    ax.set_xlabel('Residuals')
    ax.set_ylabel('Density')

    # 4. Scale-Location
    ax = axes[1, 1]
    ax.scatter(y_pred, np.sqrt(np.abs(std_resid)), s=15, alpha=0.5, color=COLORS['secondary'])
    ax.set_xlabel('Fitted Values')
    ax.set_ylabel('sqrt(|Standardized Residuals|)')

    fig.tight_layout()
    _save(fig, output)


def _norm_ppf(p):
    """简易正态分位数函数（避免依赖 scipy）。"""
    # Abramowitz and Stegun approximation
    if p <= 0:
        return -4.0
    if p >= 1:
        return 4.0
    if p == 0.5:
        return 0.0
    if p > 0.5:
        return -_norm_ppf(1 - p)
    t = np.sqrt(-2 * np.log(p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return -(t - (c0 + c1 * t + c2 * t ** 2) / (1 + d1 * t + d2 * t ** 2 + d3 * t ** 3))


def multi_line_plot(x, ys, labels, output='figures/fig_multi_line.pdf',
                    xlabel='', ylabel='', figsize=(7, 4), intervals=None):
    """多条线对比图（训练曲线、消融实验等）。

    Args:
        x: x 轴数据
        ys: list of y 数据序列
        labels: 每条线的标签
        output: 输出路径
    """
    plt = _get_plt()
    setup_style()
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    set_paper_placement(fig)

    if len(ys) != len(labels):
        raise ValueError('ys and labels must have the same length')
    if intervals is not None and not isinstance(intervals, dict) and len(intervals) != len(ys):
        raise ValueError('intervals must be a label mapping or align with ys')
    y_extent = []
    for i, (y, label) in enumerate(zip(ys, labels)):
        color = PALETTE[i % len(PALETTE)]
        interval = intervals.get(label) if isinstance(intervals, dict) else (
            intervals[i] if intervals is not None else None
        )
        if interval is not None:
            if not isinstance(interval, (tuple, list)) or len(interval) != 2:
                raise ValueError(f'{label}: interval must be a (lower, upper) pair')
            uncertainty_band(ax, x, interval[0], interval[1], color=color)
            y_extent.extend([interval[0], interval[1]])
        ax.plot(x, y, color=color, linewidth=1.7, label=label, zorder=2)
        y_extent.append(y)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    dynamic_limits(ax, x=x, y=y_extent, pad=0.06)
    declutter_axes(ax, grid=True, grid_axis='y')
    auto_legend(ax)
    _save(fig, output)


def box_plot(data_dict, output='figures/fig_box.pdf', ylabel='', figsize=(7, 4)):
    """箱线图（分布对比）。

    Args:
        data_dict: {'方法A': [values], '方法B': [values]}
        output: 输出路径
    """
    plt = _get_plt()
    setup_style()
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    labels = list(data_dict.keys())
    data = list(data_dict.values())

    bp = ax.boxplot(data, labels=labels, patch_artist=True, widths=0.5,
                    medianprops={'color': COLORS['dark'], 'linewidth': 1.5})
    for i, patch in enumerate(bp['boxes']):
        patch.set_facecolor(PALETTE_LIGHT[i % len(PALETTE_LIGHT)])
        patch.set_edgecolor(PALETTE[i % len(PALETTE)])

    ax.set_ylabel(ylabel)
    _save(fig, output)


def radar_plot(categories, values_dict, output='figures/fig_radar.pdf', figsize=(6, 6)):
    """雷达图（多维度对比）。

    Args:
        categories: 维度名列表 ['Accuracy', 'Speed', 'Memory', ...]
        values_dict: {'方法A': [v1, v2, ...], '方法B': [v1, v2, ...]}
        output: 输出路径
    """
    plt = _get_plt()
    setup_style()
    fig, ax = plt.subplots(1, 1, figsize=figsize, subplot_kw=dict(polar=True))

    n = len(categories)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]  # 闭合

    for i, (name, vals) in enumerate(values_dict.items()):
        values = list(vals) + [vals[0]]  # 闭合
        ax.plot(angles, values, 'o-', linewidth=1.5, color=PALETTE[i % len(PALETTE)], label=name)
        ax.fill(angles, values, alpha=0.1, color=PALETTE[i % len(PALETTE)])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    _save(fig, output)


def subplot_grid(plot_funcs, nrows, ncols, output='figures/fig_grid.pdf',
                 figsize=None, titles=None, shared_legend_where='auto'):
    """多面板子图网格。

    Args:
        plot_funcs: list of callables, 每个接受 (ax,) 参数
        nrows, ncols: 网格尺寸
        output: 输出路径
        titles: 每个子图的标题列表（可选）
    """
    plt = _get_plt()
    setup_style()
    if figsize is None:
        figsize = (4 * ncols, 3.5 * nrows)
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    set_paper_placement(fig)
    if nrows == 1 and ncols == 1:
        axes = np.array([axes])
    axes_flat = axes.flatten()

    for i, func in enumerate(plot_funcs):
        if i < len(axes_flat):
            func(axes_flat[i])
            if titles and i < len(titles):
                axes_flat[i].set_title(titles[i], fontsize=10)

    # 隐藏多余的子图
    for j in range(len(plot_funcs), len(axes_flat)):
        axes_flat[j].set_visible(False)

    fig.tight_layout()
    if shared_legend_where is not False:
        where = ('right' if float(figsize[0]) / max(float(figsize[1]), 1e-9) >= 1.45
                 else 'top') if shared_legend_where == 'auto' else shared_legend_where
        consolidate_shared_legends(fig, axes_flat[:len(plot_funcs)], where=where)
    _save(fig, output)


# ═══ Nature 微调自测 ══════════════════════════════════════════════════════
# 用法：python plot_utils.py --selftest-nature
# ⛔ 改 _NATURE_JITTER / _NATURE_FAMILY / 兜底阈值后必须先跑它。
#   调这套参数时我的【判据本身错了两轮】，每条用例都对应一次实测事故：
#     ① 拿绝对对比 3:1 套所有色 —— 但 green_1(#DDF3DE) 原始就 1.17，
#        它是浅填充、本该低对比 → 所有档位全判"对比不足"（假失败）
#     ② 改用相对保留率套浅填充 —— 1.17→1.03 相对掉 12%，视觉上都是"很浅"
#        → 又是全档误判
#   根因同一个：拿一把尺子量性质不同的量。必须按【用途】分（墨色 / 填充）。
def _selftest_nature(n_seeds=40):
    """Nature 微调不变量自测。返回失败项数（0 = 全过）。"""
    import colorsys

    def _dE(h1, h2):
        """粗略 CIE76 ΔE（够用于"肉眼可辨"量级判断）。"""
        def _lab(hx):
            def _f(c):
                return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            r, g, b = (_f(c) for c in _hex2rgb01(hx))
            X = r * 0.4124 + g * 0.3576 + b * 0.1805
            Y = r * 0.2126 + g * 0.7152 + b * 0.0722
            Z = r * 0.0193 + g * 0.1192 + b * 0.9505

            def _g(t):
                return t ** (1 / 3.0) if t > 0.008856 else (7.787 * t + 16 / 116.0)
            fx, fy, fz = _g(X / 0.95047), _g(Y / 1.0), _g(Z / 1.08883)
            return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))
        a, b = _lab(h1), _lab(h2)
        return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5

    # 相邻同族对（最容易被抖动挤到一起的）—— 与原始距离比，不用绝对阈值
    ADJ = (('blue_main', 'blue_secondary'), ('neutral_mid', 'neutral_dark'),
           ('green_2', 'green_3'), ('red_2', 'red_strong'),
           ('neutral_light', 'neutral_mid'))
    base_adj = {p: _dE(_NATURE_SEMANTIC[p[0]], _NATURE_SEMANTIC[p[1]]) for p in ADJ}

    seeds = [i * 7919 + 13 for i in range(n_seeds)]      # 散开的确定性种子
    pals = [nature_palette(seed=s) for s in seeds]
    fail = []

    # ① 键集必须与 SKILL.md 的 PALETTE_NATURE 完全一致（改了要同步文档）
    for p in pals:
        if set(p) != set(_NATURE_SEMANTIC):
            fail.append('键集不一致')
            break

    # ② 墨色对白底对比 ≥ 下限（可读性硬底线）
    for i, p in enumerate(pals):
        for k in _NATURE_INK:
            c = _contrast_on_white(_hex2rgb01(p[k]))
            if c < 3.0:      # 判据用 WCAG 线 3.0；实现留了 3.2 余量
                fail.append('seed#%d 墨色 %s 对比 %.2f < 3.0' % (i, k, c))

    # ③ 填充色仍"浅"（不许窜进墨色区间）
    for i, p in enumerate(pals):
        for k in _NATURE_FILL:
            c = _contrast_on_white(_hex2rgb01(p[k]))
            if c > 2.8:
                fail.append('seed#%d 填充 %s 对比 %.2f > 2.8' % (i, k, c))

    # ④ 相邻同族色仍分得开 —— 只用【绝对 ΔE 下限】
    #   ⛔ 这条判据我改过两次，两次都错在"用相对量衡量绝对问题"：
    #     第一次用保留率 ≥85%：但 `red_2 vs red_strong` 原始 ΔE=39.37，
    #       保留 79% 后仍有 31.3（可辨阈值的 13 倍），一眼分得开 —— 误判。
    #     第二次加了保留率 ≥75% 兜底：但实测【纯色相旋转、ds=dl=0】时保留率
    #       也只有 76% —— 因为 Lab 距离本身随色相位置变化，整族同步旋转
    #       并不保持 Lab 距离。所以保留率对本设计天然不适用，不是参数没调好。
    #   真正稳定的量是绝对 ΔE：实测各档位都落在 9.3-9.8，与幅度几乎无关。
    #   "两个颜色在同一张图上能不能分开"取决于绝对色差，不取决于它原来差多少。
    _ADJ_MIN_DE = 9.0        # ≈3.9× 可辨阈值(2.3)；实测最坏 9.3，留 0.3 余量
    for i, p in enumerate(pals):
        for pr in ADJ:
            d = _dE(p[pr[0]], p[pr[1]])
            if d < _ADJ_MIN_DE:
                fail.append('seed#%d %s-%s 绝对距离 %.1f < %.1f'
                            % (i, pr[0], pr[1], d, _ADJ_MIN_DE))

    # ⑤ 中性色只动明度：色相/饱和必须与原始一致（动了会把灰染上颜色）
    for i, p in enumerate(pals):
        for k in ('neutral_light', 'neutral_mid', 'neutral_dark', 'neutral_black'):
            h0, _, s0 = colorsys.rgb_to_hls(*_hex2rgb01(_NATURE_SEMANTIC[k]))
            h1, _, s1 = colorsys.rgb_to_hls(*_hex2rgb01(p[k]))
            if abs(s1 - s0) > 0.02 or (s0 >= _NATURE_GRAY_SAT and abs(h1 - h0) > 0.02):
                fail.append('seed#%d 中性色 %s 的色相/饱和被改动' % (i, k))

    # ⑤b 色相必须留在【族内】—— 这是"还是不是 Nature 那个色"的真判据。
    #   ⛔ 比"幅度够不够小"靠得住：幅度是手段，不出族才是目的。
    #     各色名的合法色相区间宽度差好几倍（gold 只有 20°、green 有 70°），
    #     所以色相预算按族分配（见 _NATURE_HUE_BUDGET），这条判据来兜底验证。
    _HUE_BAND = {
        'blue_main': (195, 235), 'blue_secondary': (195, 235),
        'green_1': (85, 155), 'green_2': (85, 155), 'green_3': (85, 155),
        'red_1': (340, 25), 'red_2': (340, 25), 'red_strong': (340, 25),  # 跨 0°
        'teal': (165, 200), 'violet': (280, 330), 'gold': (40, 60),
    }
    for i, p in enumerate(pals):
        for k, band in _HUE_BAND.items():
            hh, _, ss = colorsys.rgb_to_hls(*_hex2rgb01(p[k]))
            if ss < _NATURE_GRAY_SAT:
                continue                       # 灰没有有意义的色相
            deg = hh * 360.0
            lo, hi = band
            inside = (deg >= lo or deg <= hi) if lo > hi else (lo <= deg <= hi)
            if not inside:
                fail.append('seed#%d %s 色相 %.0f° 漂出族 [%d,%d]'
                            % (i, k, deg, lo, hi))

    # ⑥ 去指纹有效：跨种子平均 ΔE ≥ 2.3（肉眼可辨阈值）
    cross = []
    for i in range(len(pals)):
        for j in range(i + 1, len(pals)):
            cross.append(sum(_dE(pals[i][k], pals[j][k])
                             for k in _NATURE_SEMANTIC) / len(_NATURE_SEMANTIC))
    avg_cross = sum(cross) / len(cross) if cross else 0.0
    if avg_cross < 2.3:
        fail.append('跨篇平均 ΔE %.2f < 2.3（去指纹无效）' % avg_cross)

    # ⑦ 同种子必须可复现（绝不能用 random/时间戳）
    if nature_palette(seed=42) != nature_palette(seed=42):
        fail.append('同种子两次调用结果不同（不可复现）')

    # ⑧ 版式旋钮：钉死维度不许出现，自定义要能覆盖
    for s in seeds[:10]:
        kn = _nature_knobs(s)
        if set(kn) != {'grid', 'lw_k', 'legend_loc'}:
            fail.append('版式旋钮键集异常: %s' % sorted(kn))
            break
        if kn['lw_k'] not in _NATURE_LW_OPTS:
            fail.append('lw_k 越界: %s' % kn['lw_k'])
    if _nature_knobs(1, custom={'grid': 'none'})['grid'] is not None:
        fail.append('custom grid:none 未生效')
    if _nature_knobs(1, custom={'lw': 'thick'})['lw_k'] != 1.15:
        fail.append('custom lw:thick 未生效')
    # 非法维必须被忽略（不能把 frame:journal 之类吃进去）
    _k = _nature_knobs(1, custom={'frame': 'journal', 'bg': 'graytint'})
    if set(_k) != {'grid', 'lw_k', 'legend_loc'}:
        fail.append('非法自定义维度未被忽略')

    print('=' * 72)
    print('  Nature 微调不变量自测（%d 个种子 × 15 色）' % n_seeds)
    print('=' * 72)
    print('  幅度 Δh=±%.3f Δs=±%.2f Δl=±%.3f' % _NATURE_JITTER)
    print('  跨篇平均 ΔE = %.2f（阈值 2.3）' % avg_cross)
    print('  墨色最低对比 = %.2f（阈值 3.0）' % min(
        _contrast_on_white(_hex2rgb01(p[k])) for p in pals for k in _NATURE_INK))
    print('  相邻同族最低绝对 ΔE = %.1f（阈值 %.1f，≈%.1f× 可辨阈值）' % (
        min(_dE(p[pr[0]], p[pr[1]]) for p in pals for pr in ADJ),
        _ADJ_MIN_DE,
        min(_dE(p[pr[0]], p[pr[1]]) for p in pals for pr in ADJ) / 2.3))
    if fail:
        print()
        for m in fail[:12]:
            print('  FAIL %s' % m)
        if len(fail) > 12:
            print('  … 另有 %d 条' % (len(fail) - 12))
    print('=' * 72)
    print('  %s（失败 %d 条）' % ('全部通过' if not fail else '⛔ 未通过', len(fail)))
    return len(fail)


if __name__ == '__main__':
    import sys as _sys
    if '--selftest-nature' in _sys.argv:
        _sys.exit(min(_selftest_nature(), 250))
    print('plot_utils.py — 图表样式库。自测：python plot_utils.py --selftest-nature')
