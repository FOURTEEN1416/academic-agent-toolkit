# -*- coding: utf-8 -*-
r"""按图的真实长宽比与文字密度，自动为 LaTeX 插图选择可读宽度。

治的问题：竖长条图(如流程图)和横图套同一个 width，竖图按页宽拉伸后高度撑满整页、
显得巨大。规范做法是按图自身长宽比给约束——竖长的收窄 width、横的放宽。

做法(确定性、通用、零题目常量)：
  1. 读 figures/*.pdf 每张的真实宽高(PyMuPDF)。
  2. 数据图按 r = 高/宽分档；逻辑框图再读取 PDF 内有效字号、文字量和文本块数。
  3. 逻辑框图以“上页后第 10 百分位文字不低于 8pt”为目标，宽度按 0.02 向上取整，
     简图通常落在 0.80~0.88，密图通常落在 0.90~0.98，而不是所有图固定通栏。
  4. 若放到 0.98 仍不够清楚，或图高/宽 > 1.05，不再假装放大能解决：明确要求
     回源 HTML/DrawIO 重排、缩短节点或拆图；height 统一设上限。
  5. 只重写 latex_includes.tex 里每个 \includegraphics 的 width/height 参数，
     keepaspectratio、图路径、caption、label 一律不动。

长宽比分档(r = 高/宽)：
  fig_arch/fig_roadmap/fig_flow/fig_pipeline/fig_framework 且 r <= 1.05
                 横向/近方逻辑框图 -> 密度感知 width 0.80~0.98\textwidth
  r <= 0.80  横图/方图      -> width 0.90\textwidth
  r <= 1.20  近方           -> width 0.80\textwidth
  r <= 1.60  偏竖           -> width 0.60\textwidth
  r  > 1.60  瘦高           -> width 0.46\textwidth
  一律 height 上限 0.80\textheight（keepaspectratio 下只压不放，防撑满页）

数据图分档保持既有插图尺寸契约；它不是图例避让算法。
遮挡应通过独立图例/色条区域、内容重排和最终渲染检查解决，不通过盲目提高宽度系数解决。

⛔ 全软失败：PDF 读不到 / 无 PyMuPDF / 某块解析不了 → 该块保持原样，绝不破坏文件。
   latex_includes.tex 不存在 → 退出 2(跳过，不阻塞)。
退出码：0=已规整/检查通过  1=strict 检出必须回源重排的逻辑框图  2=无文件可处理/依赖缺失(跳过)
用法：python _utils/fig_include_size.py [--figdir figures] [--latex figures/latex_includes.tex] [--dry-run] [--strict]
"""
from __future__ import annotations
import sys
import re
import argparse
import math
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# (阈值上界 r, width 系数) —— r=高/宽；从小到大匹配第一个满足 r<=界 的档
#
# 保持数据图与 plot_utils、文档及编译兜底的分档契约一致。
# 这些系数决定插入尺寸，不证明图例或文字没有遮挡。字号、标签、列数和
# 相邻面板布局都会改变实际占用；历史个例中的面积/遮挡统计不是普遍定律。
# 宽度还受 _HEIGHT_CAP 限制，增加画布高度后也必须复核最终缩放与字号。
# 如需更改系数，同步更新文档与所有运行时副本，并运行 fig_bucket_doc_sync_check.py。
_BUCKETS = [
    (0.80, 0.90),
    (1.20, 0.80),
    (1.60, 0.60),
]
_WIDTH_TALL = 0.46          # r > 1.60 瘦高图（0.50 会撞高度反制线，见上）
_HEIGHT_CAP = 0.80          # height 上限(\textheight)

# 流程/架构/路线类图靠节点文字和连线表达，单凭长宽比无法判断是否需要通栏。
# 以正文净宽 5.5in（与 screenshot_capture --norm-check 的默认值一致）估算上页字号：
# final_font = source_font * (width_coef * textwidth_pt / pdf_width_pt)。
# 用 p10 而不是绝对最小字号，避免一个装饰符号/隐藏 span 把整张图误判为超密；但 p10
# 仍能覆盖至少 10% 的正文字符，不会让一批节点说明悄悄跌到不可读字号。
_LOGIC_PREFIXES = ("fig_arch", "fig_roadmap", "fig_flow", "fig_pipeline", "fig_framework")
_LOGIC_MAX_ASPECT = 1.05
_WIDTH_LOGIC_MIN = 0.80
_WIDTH_LOGIC_MAX = 0.98
_WIDTH_LOGIC_STEP = 0.02
_TARGET_FONT_PT = 8.0
_TEXTWIDTH_PT = 5.5 * 72.0


def _weighted_percentile(items, q: float):
    """items=[(value, weight)] 的加权百分位；空输入返回 None。"""
    good = sorted((float(v), max(1, int(w))) for v, w in items if v and v > 0 and w)
    if not good:
        return None
    total = sum(w for _, w in good)
    target = max(1, math.ceil(total * q))
    seen = 0
    for value, weight in good:
        seen += weight
        if seen >= target:
            return value
    return good[-1][0]


def _pdf_metrics(pdf_path: Path):
    """读取第一页尺寸与文字密度；PDF 不可读返回 None，没文字仍返回几何信息。"""
    try:
        import fitz  # PyMuPDF
    except Exception:
        return None
    try:
        doc = fitz.open(str(pdf_path))
        if doc.page_count < 1:
            doc.close()
            return None
        page = doc.load_page(0)
        rect = page.rect
        w, h = float(rect.width), float(rect.height)
        weighted_sizes = []
        chars = 0
        blocks = 0
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            has_text = False
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = str(span.get("text", "")).strip()
                    size = float(span.get("size", 0) or 0)
                    if not text or size <= 0:
                        continue
                    n = len(text)
                    chars += n
                    weighted_sizes.append((size, n))
                    has_text = True
            if has_text:
                blocks += 1
        doc.close()
        if w <= 0 or h <= 0:
            return None
        return {
            "width_pt": w,
            "height_pt": h,
            "aspect": h / w,
            "font_p10_pt": _weighted_percentile(weighted_sizes, 0.10),
            "chars": chars,
            "blocks": blocks,
        }
    except Exception:
        return None


def _pdf_aspect(pdf_path: Path):
    """返回 PDF 第一页 高/宽 比值 r；读不到返回 None(软失败)。"""
    metrics = _pdf_metrics(pdf_path)
    return metrics.get("aspect") if metrics else None


def _is_logic_figure(name: str) -> bool:
    stem = Path(name).stem.lower()
    return stem.startswith(_LOGIC_PREFIXES)


def _density_floor(chars: int, blocks: int) -> float:
    """文字/节点越多，越不能仅因源字号较大就把图缩得过小。"""
    if chars >= 650 or blocks >= 50:
        return 0.94
    if chars >= 400 or blocks >= 30:
        return 0.88
    return _WIDTH_LOGIC_MIN


def _adaptive_logic_width(metrics) -> tuple[float, dict]:
    """给横向/近方逻辑框图算宽度，并返回可解释诊断。"""
    p10 = metrics.get("font_p10_pt")
    pdf_w = float(metrics.get("width_pt") or 0)
    floor = _density_floor(int(metrics.get("chars") or 0), int(metrics.get("blocks") or 0))
    if not p10 or pdf_w <= 0:
        return _WIDTH_LOGIC_MAX, {
            "status": "fallback", "reason": "PDF 未提取到可用文字字号，保守按最大宽度嵌入",
            "density_floor": floor, "estimated_font_pt": None,
        }
    required = _TARGET_FONT_PT * pdf_w / (float(p10) * _TEXTWIDTH_PT)
    raw = max(_WIDTH_LOGIC_MIN, floor, required)
    rounded = math.ceil((raw - 1e-9) / _WIDTH_LOGIC_STEP) * _WIDTH_LOGIC_STEP
    width = min(_WIDTH_LOGIC_MAX, max(_WIDTH_LOGIC_MIN, rounded))
    estimated = float(p10) * (width * _TEXTWIDTH_PT) / pdf_w
    needs_reflow = required > _WIDTH_LOGIC_MAX + 1e-9
    return round(width, 2), {
        "status": "reflow" if needs_reflow else "ok",
        "reason": ("通栏后有效文字仍低于可读下限，必须重排/拆图" if needs_reflow
                   else "按有效字号与文字密度自适应"),
        "required_width": required,
        "density_floor": floor,
        "estimated_font_pt": estimated,
    }


def _width_for(r: float, name: str = "", metrics=None) -> float:
    if name and _is_logic_figure(name) and r <= _LOGIC_MAX_ASPECT:
        if metrics:
            return _adaptive_logic_width(metrics)[0]
        return _WIDTH_LOGIC_MAX  # 无 PDF 指标时保留旧版兼容行为
    for bound, wcoef in _BUCKETS:
        if r <= bound:
            return wcoef
    return _WIDTH_TALL


def recommend_width_for_pdf(pdf_path: Path, name: str = "") -> dict | None:
    """统一入口：返回 width、指标和是否需要回源重排；不可读 PDF 返回 None。"""
    metrics = _pdf_metrics(pdf_path)
    if not metrics:
        return None
    r = float(metrics["aspect"])
    width = _width_for(r, name or pdf_path.name, metrics)
    diag = {"status": "ok", "reason": "按普通图长宽比分档", "estimated_font_pt": None}
    if _is_logic_figure(name or pdf_path.name):
        if r <= _LOGIC_MAX_ASPECT:
            width, diag = _adaptive_logic_width(metrics)
        else:
            p10 = metrics.get("font_p10_pt")
            effective_w = width * _TEXTWIDTH_PT
            estimated = (float(p10) * effective_w / float(metrics["width_pt"])) if p10 else None
            diag = {
                "status": "reflow",
                "reason": "逻辑框图高/宽超过 1.05；缩窄会导致字小，放宽会占满整页",
                "estimated_font_pt": estimated,
            }
    return {"width": width, **metrics, **diag}


# 匹配一条 \includegraphics[可选opts]{路径}，捕获 opts 与 path
_INC_RE = re.compile(r'(\\includegraphics)(\[[^\]]*\])?(\{[^}]*\})')


def _rewrite_opts(opts: str, w_coef: float) -> str:
    """把 opts([...] 含中括号)里的 width/height 改成按长宽比算的值，keepaspectratio 保留。
    opts 可能为空('' 或 None)→ 生成一份新的。"""
    body = opts[1:-1] if (opts and opts.startswith('[') and opts.endswith(']')) else ''
    parts = [p.strip() for p in body.split(',') if p.strip()]
    kept = []
    has_keep = False
    for p in parts:
        low = p.lower().replace(' ', '')
        if low.startswith('width=') or low.startswith('height='):
            continue  # 丢弃旧的 width/height，稍后统一加
        if low == 'keepaspectratio':
            has_keep = True
            continue
        kept.append(p)  # 其它选项(如 trim/clip/angle)原样保留
    new = [f"width={w_coef:g}\\textwidth", f"height={_HEIGHT_CAP:g}\\textheight", "keepaspectratio"]
    _ = has_keep  # keepaspectratio 无论原来有无都补上(必须有)
    return '[' + ','.join(new + kept) + ']'


def process(latex_path: Path, fig_dir: Path, dry_run: bool, strict: bool = False):
    text = latex_path.read_text(encoding='utf-8', errors='ignore')
    changes = []
    skips = []

    def _sub(m):
        cmd, opts, pathbrace = m.group(1), m.group(2), m.group(3)
        inner = pathbrace[1:-1].strip()  # 去 {}
        # 只处理 .pdf 图；取文件名去 figures/ 前缀，在 fig_dir 找
        name = inner.split('/')[-1].split('\\')[-1]
        if not name.lower().endswith('.pdf'):
            return m.group(0)
        pdf = fig_dir / name
        rec = recommend_width_for_pdf(pdf, name)
        if rec is None:
            skips.append(name)
            return m.group(0)  # 软失败：该块原样不动
        r = float(rec["aspect"])
        wc = float(rec["width"])
        new_opts = _rewrite_opts(opts or '', wc)
        changes.append((name, round(r, 2), wc, rec))
        return cmd + new_opts + pathbrace

    new_text = _INC_RE.sub(_sub, text)
    print("=== fig_include_size：按长宽比规整 \\includegraphics 宽度 ===")
    reflow = []
    for name, r, wc, rec in changes:
        if _is_logic_figure(name) and r <= _LOGIC_MAX_ASPECT:
            est = rec.get("estimated_font_pt")
            tag = (f"逻辑框图·{rec.get('chars', 0)}字/{rec.get('blocks', 0)}块"
                   + (f"·估算p10={est:.1f}pt" if est is not None else "·字号未知"))
        else:
            tag = "横/方" if r <= 0.8 else ("近方" if r <= 1.2 else ("偏竖" if r <= 1.6 else "瘦高"))
        print(f"  {name}: 高/宽={r} ({tag}) -> width={wc:g}\\textwidth, height<={_HEIGHT_CAP:g}\\textheight")
        if rec.get("status") == "reflow":
            reflow.append((name, rec.get("reason", "需要回源重排")))
            print(f"    ⛔ {rec.get('reason')}；不要继续放大，请缩短节点、改横向分栏或拆成两图。")
        elif rec.get("status") == "fallback":
            print(f"    ⚠ {rec.get('reason')}")
    for name in skips:
        print(f"  ⚠ {name}: PDF 读不到/无 PyMuPDF，保持原样(软跳过)")
    if not changes and not skips:
        print("  (latex_includes 里没有 .pdf 的 \\includegraphics，无改动)")
    if dry_run:
        print("  [dry-run] 未写盘。去掉 --dry-run 才实际写入。")
        if strict and reflow:
            print(f"❌ strict：{len(reflow)} 张逻辑框图无法仅靠嵌入宽度保证可读，必须回源重排。")
            return 1
        return 0
    if new_text != text:
        latex_path.write_text(new_text, encoding='utf-8')
        print(f"  ✅ 已更新 {latex_path}（{len(changes)} 张按长宽比/密度规整）")
    else:
        print("  尺寸已符合，无需改动。")
    if strict and reflow:
        print(f"❌ strict：{len(reflow)} 张逻辑框图无法仅靠嵌入宽度保证可读，必须回源重排。")
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="按图长宽比自动定 includegraphics 宽度")
    ap.add_argument("--figdir", default="figures")
    ap.add_argument("--latex", default="figures/latex_includes.tex")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写盘")
    ap.add_argument("--strict", action="store_true", help="逻辑框图需要重排时退出 1，阻止带病编译")
    args = ap.parse_args()
    latex_path = Path(args.latex)
    fig_dir = Path(args.figdir)
    if not latex_path.is_file():
        print(f"⚠ 未找到 {latex_path}，跳过(不阻塞)。")
        return 2
    if not fig_dir.is_dir():
        print(f"⚠ 未找到图目录 {fig_dir}，跳过(不阻塞)。")
        return 2
    return process(latex_path, fig_dir, args.dry_run, args.strict)


if __name__ == "__main__":
    sys.exit(main())
