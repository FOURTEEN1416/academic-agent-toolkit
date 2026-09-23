# -*- coding: utf-8 -*-
r"""分档系数一致性闸：fig_include_size.py 的代码 vs 三处文档必须一致。

治的问题：`fig_include_size.py` 的 `_BUCKETS` 决定每张图上页多宽，而
`figure_style_guide.md` 的 native figsize 推荐表是**按那四个系数倒推**的（要保住缩放比
0.90-0.92）。只改一边的后果很隐蔽：
  · 只改代码不改推荐表 → AI 照旧表写 figsize，图被缩得更多、字变小；
  · 只改推荐表不改代码 → figsize 变大但显示宽没变，同样被缩。
两种都不报错、只是"图里字小了"，肉眼极难归因。所以设这道闸。

查六处：
  1. fig_include_size.py 的 `_BUCKETS` + `_WIDTH_TALL`（权威源）
  2. 同文件 docstring 里的分档表
  3. **plot_utils.py 的 `_LATEX_BUCKETS` + `_LATEX_TALL_COEF`** —— 画图时算字号用的那份
  4. figure_style_guide.md 的 native figsize 推荐表
  5. comp-paper-zh/SKILL.md 里"竖长条流程图本就该 X~Y\textwidth"那句举例
  6. compile_utils.sh 的内嵌兜底分档与逻辑框图通栏系数

⛔ 第 3 处是本闸的由来：第一版只查了文档，漏了 plot_utils.py 里**裸元组形式**的同一份
   系数（`((0.80, 0.85), ...)`，不含 "textwidth" 字样，按关键词搜不到）。那份是画图时
   反推字号用的，跟主表脱节的后果是字号算错 —— 同样不报错、只表现为"字偏大或偏小"。

⛔ 全软失败：任何文件读不到 → 退出 2（跳过，不阻塞）。
退出码：0=一致  1=检出不一致(必修)  2=无据可查(跳过)
用法：python _utils/fig_bucket_doc_sync_check.py [--root <仓库根>]
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ⛔ 只要一个反斜杠：markdown/docstring 里写的是 `0.90\textwidth`。
#   （写成 \\\\ 会匹配不到 —— 这个坑我自己踩过一次，repr() 显示的 \\ 是转义后的样子。）
_COEF_RE = re.compile(r"([0-9]*\.?[0-9]+)\\textwidth")

_GUIDE_ROW_PREFIXES = (
    "| r ≤ 0.80",
    "| 0.80 < r ≤ 1.20",
    "| 1.20 < r ≤ 1.60",
    "| r > 1.60",
)


def _load_code_coefs(py_path: Path):
    """从 fig_include_size.py 读权威系数与 docstring 里的表。"""
    spec = importlib.util.spec_from_file_location("_fis_check", py_path)
    if spec is None or spec.loader is None:
        return None, None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    code = [b[1] for b in mod._BUCKETS] + [mod._WIDTH_TALL]
    ds = []
    for line in (mod.__doc__ or "").splitlines():
        if "-> width" in line and "逻辑框图" not in line:
            m = _COEF_RE.search(line)
            if m:
                ds.append(float(m.group(1)))
    logic_max = getattr(mod, "_WIDTH_LOGIC_MAX", getattr(mod, "_WIDTH_LOGIC_WIDE", None))
    return code, ds, logic_max


def _compile_utils_coefs(sh_path: Path):
    """读 compile_utils.sh 内嵌 Python 的同一组兜底常量。"""
    txt = sh_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"_BUCKETS\s*=\s*\[([^\]]+)\]", txt)
    mt = re.search(r"_WIDTH_TALL\s*=\s*([0-9]*\.?[0-9]+)", txt)
    ml = re.search(r"_LOGIC_WIDE\s*=\s*([0-9]*\.?[0-9]+)", txt)
    if not (m and mt and ml):
        return None
    pairs = re.findall(r"\(\s*[0-9.]+\s*,\s*([0-9.]+)\s*\)", m.group(1))
    return [float(x) for x in pairs] + [float(mt.group(1))], float(ml.group(1))


def _plot_utils_coefs(py_path: Path):
    """读 plot_utils.py 的 _LATEX_BUCKETS / _LATEX_TALL_COEF。

    ⛔ 用正则而不是 import：plot_utils.py 有 4000+ 行、import 期会碰 matplotlib 和
       样式标记文件，在闸里执行它太重也容易出无关报错。这两个常量是字面量，正则够用。
    """
    txt = py_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"_LATEX_BUCKETS\s*=\s*\(([^)]*\)[^=]*?)\)\s*$",
                  txt, re.M)
    if not m:
        m = re.search(r"_LATEX_BUCKETS\s*=\s*(\(\([^\n]*\))", txt)
    if not m:
        return None
    nums = [float(x) for x in re.findall(r"([0-9]*\.?[0-9]+)\s*\)", m.group(1))]
    mt = re.search(r"_LATEX_TALL_COEF\s*=\s*([0-9]*\.?[0-9]+)", txt)
    if not mt:
        return None
    return nums + [float(mt.group(1))]


def _guide_coefs(md_path: Path):
    out = []
    for line in md_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith(_GUIDE_ROW_PREFIXES):
            m = _COEF_RE.search(line)
            if m:
                out.append(float(m.group(1)))
    return out


def _paper_example(md_path: Path):
    """comp-paper-zh 里那句「竖长条流程图本就该 X~Y\textwidth」。"""
    txt = md_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"竖长条流程图本就该\s*`([\d.]+)~([\d.]+)", txt)
    return (float(m.group(1)), float(m.group(2))) if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description="分档系数一致性闸")
    ap.add_argument("--root", default=".", help="仓库根（默认当前目录）")
    args = ap.parse_args()
    root = Path(args.root)

    py = root / "skills" / "shared-scripts" / "fig_include_size.py"
    guide = root / "skills" / "shared-scripts" / "figure_style_guide.md"
    paper = root / "skills" / "comp-paper-zh" / "SKILL.md"
    # 支持从 _utils/ 里跑（工作区布局）
    if not py.is_file():
        alt = root / "_utils" / "fig_include_size.py"
        if alt.is_file():
            py, guide = alt, root / "_utils" / "figure_style_guide.md"

    if not py.is_file():
        print(f"⚠ 分档一致性闸：找不到 {py}，跳过(不阻塞)。")
        return 2

    try:
        code, ds, logic_wide = _load_code_coefs(py)
    except Exception as e:
        print(f"⚠ 分档一致性闸：读 {py.name} 失败({e})，跳过(不阻塞)。")
        return 2
    if not code:
        print("⚠ 分档一致性闸：没读到 _BUCKETS，跳过(不阻塞)。")
        return 2

    print("=== 分档系数一致性闸 ===")
    print(f"权威源 {py.name} 的 _BUCKETS+_WIDTH_TALL : {code}")

    fails = []
    if ds and ds != code:
        fails.append((f"{py.name} 的 docstring 分档表", ds, code))
    elif not ds:
        print(f"  ⚠ {py.name} docstring 里没找到分档表（跳过该项）")
    else:
        print(f"  ✓ {py.name} docstring 一致")

    pu = py.parent / "plot_utils.py"
    if pu.is_file():
        p = _plot_utils_coefs(pu)
        if p is None:
            print(f"  ⚠ {pu.name} 里没读到 _LATEX_BUCKETS（跳过该项）")
        elif p != code:
            fails.append((f"{pu.name} 的 _LATEX_BUCKETS+_LATEX_TALL_COEF", p, code))
        else:
            print(f"  ✓ {pu.name} 的 _LATEX_BUCKETS 一致")
    else:
        print(f"  ⚠ 找不到 {pu}（跳过该项）")

    cu = py.parent / "compile_utils.sh"
    if cu.is_file():
        parsed = _compile_utils_coefs(cu)
        if parsed is None:
            print(f"  ⚠ {cu.name} 里没读到分档常量（跳过该项）")
        else:
            ccoefs, clogic = parsed
            if ccoefs != code:
                fails.append((f"{cu.name} 的 _BUCKETS+_WIDTH_TALL", ccoefs, code))
            else:
                print(f"  ✓ {cu.name} 的普通分档一致")
            if logic_wide is not None and clogic != logic_wide:
                fails.append((f"{cu.name} 的 _LOGIC_WIDE", [clogic], [logic_wide]))
            elif logic_wide is not None:
                print(f"  ✓ {cu.name} 的逻辑框图兼容上限与自适应上限一致")
    else:
        print(f"  ⚠ 找不到 {cu}（跳过该项）")

    if guide.is_file():
        g = _guide_coefs(guide)
        if not g:
            print(f"  ⚠ {guide.name} 里没找到推荐表（跳过该项）")
        elif g != code:
            fails.append((f"{guide.name} 的 native figsize 推荐表", g, code))
        else:
            print(f"  ✓ {guide.name} 推荐表一致")
    else:
        print(f"  ⚠ 找不到 {guide}（跳过该项）")

    if paper.is_file():
        ex = _paper_example(paper)
        want = (code[3], code[2])          # (瘦高, 偏竖)
        if ex is None:
            print(f"  ⚠ {paper.parent.name}/SKILL.md 里没找到举例句（跳过该项）")
        elif ex != want:
            fails.append((f"{paper.parent.name}/SKILL.md 的举例区间", list(ex), list(want)))
        else:
            print(f"  ✓ {paper.parent.name}/SKILL.md 举例一致")

    if not fails:
        print("✅ PASS — 代码与文档的分档系数一致。")
        return 0
    print(f"❌ 检出 {len(fails)} 处不一致（必修）：")
    for where, got, want in fails:
        print(f"   · {where}: 写的是 {got}，应为 {want}")
    print("⛔ 改 _BUCKETS 必须同步改这几处，否则 AI 会照旧表写 figsize → 图被缩、字变小，"
          "而且不报任何错、只表现为「图里字小了」，极难归因。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
