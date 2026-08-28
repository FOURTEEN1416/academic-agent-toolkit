#!/usr/bin/env python3
"""把交底书里的**自包含 HTML 图**（系统框图 fig_arch / 流程图 fig_flow）用 Electron
截成 PNG，供 ``md_to_docx.py`` 嵌进 Word；随后默认导出 .docx。**顶替旧 mermaid 出图**。

与竞赛 ``paper-figure-html`` 同一套 Electron 截图后端（``screenshot_capture.py``），差异：
- 竞赛出**矢量 PDF** 供 LaTeX \\includegraphics；专利只出 **PNG 位图**（Word 塞不进矢量 PDF）。
- 出图前先 ``--geom-check`` 几何自检（含公式加 ``--render-math``），把「文字溢出/越界/重叠」
  报给上层；**自修复循环（读 HTML 改 CSS 最多 3 轮）在 patent-build/SKILL.md 指令层**，
  本脚本只负责出图 + 输出自检报告，不自己改 HTML。

图文件名即产物名：``fig_arch.html → figures/fig_arch.png``（确定性 1:1，不用编号）。
草稿 md 用 ``<!-- ![系统框图](figures/fig_arch.png) -->`` 注释引用（图此刻可能尚未生成）；
``md_to_docx.py`` 见路径含 ``figures`` 即判为全幅居中插图 + "图 N" 题注。

**公式**：默认**不转 PNG**，交由 ``md_to_docx.py`` 走 Word 原生 OMML 矢量公式（与上一轮决策一致）。

**降级不中断**：Electron 不可用 / 某张截图失败 → 该图缺失（Word 里显示"[图片缺失]"），
其余照常；仍写 .md 并**照常尝试** ``md_to_docx.py``；导出失败退出码仍 0，stderr 给手动命令。

用法：
  python tools/html_figure_render.py -i 专利交底书/交底书草稿.md -o 专利交底书/交底书.md \\
    --docx 专利交底书/交底书.docx
  # --fig-dir 缺省 = 输入 .md 所在目录（HTML 图与草稿同目录）；PNG 出到 <fig-dir>/figures/
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# PNG 截图视口上限（与 capture.js 的 8000 对齐，防超大图卡死）
_MAX_DIM = 8000
_MIN_DIM = 200


def _find_screenshot_tool() -> Path | None:
    """定位 screenshot_capture.py。顺序：环境变量 → 上级 _utils/ → 项目 tools/。

    与 mermaid_render 同源：工作区运行时脚本被复制到 _utils/patent_scripts/，
    screenshot_capture.py 在兄弟目录 _utils/ 下；开发直跑时在项目 tools/。
    """
    env = os.environ.get("MH_SCREENSHOT_TOOL")
    if env and Path(env).is_file():
        return Path(env)
    here = Path(__file__).resolve().parent
    cands = [
        here.parent / "screenshot_capture.py",         # _utils/patent_scripts/ → _utils/
        here.parent.parent / "screenshot_capture.py",  # 再上一层兜底
        here / "screenshot_capture.py",                 # 同目录
    ]
    for up in (here, *here.parents):
        cands.append(up / "tools" / "screenshot_capture.py")
    for c in cands:
        if c.is_file():
            return c
    return None


def _electron_available(tool: Path) -> bool:
    """跑 screenshot_capture.py --check，exit 0 表示 Electron 可用。"""
    try:
        r = subprocess.run(
            [sys.executable, str(tool), "--check"],
            capture_output=True, text=True, timeout=60,
        )
        return r.returncode == 0
    except Exception:
        return False


def _run_capture_config(tool: Path, cfg: dict) -> dict:
    """写临时 cfg.json → 调 screenshot_capture.py --config → 解析 stdout 里的 res dict。

    返回 {"results": [...]}；失败返回 {"results": [], "error": "..."}。
    ⛔ screenshot_capture.py 的 --config 分支**不理会** cfg 里的 resultPath——它把
    整个 res dict 以 ``json.dumps(..., indent=2)`` 打到 **stdout**。所以这里从 stdout
    抠出「首个 { 到末尾 }」那段 JSON 解析（Electron 噪声走 stderr，不污染 stdout）。
    """
    tmp = Path(tempfile.mkdtemp(prefix="patent_htmlfig_"))
    cfg_path = tmp / "cfg.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    try:
        r = subprocess.run(
            [sys.executable, str(tool), "--config", str(cfg_path)],
            capture_output=True, text=True, timeout=240,
        )
        data = {"results": [], "stderr": (r.stderr or "")[-800:]}
        out = r.stdout or ""
        lo, hi = out.find("{"), out.rfind("}")
        if lo >= 0 and hi > lo:
            try:
                res = json.loads(out[lo:hi + 1])
                data["results"] = res.get("results", [])
            except Exception:
                pass
        return data
    except subprocess.TimeoutExpired:
        return {"results": [], "error": "timeout"}
    except Exception as e:
        return {"results": [], "error": str(e)}
    finally:
        try:
            cfg_path.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            tmp.rmdir()
        except OSError:
            pass


def _geom_report(geom: dict, html_name: str) -> tuple[int, list[str]]:
    """把 capture.js 的几何探针结果整理成 (问题数, 报告行)。与 screenshot_capture 口径一致。"""
    lines: list[str] = []
    if not geom or geom.get("error"):
        return -1, [f"⚠ {html_name} 几何自检无法进行：{geom.get('error') if geom else '无 .fig 或探针无返回'}"]
    overflow = geom.get("overflow") or []
    clip = geom.get("clip") or []
    overlap = geom.get("overlap") or []
    fig = geom.get("fig") or {}
    n = len(overflow) + len(clip) + len(overlap)
    lines.append(f"=== 几何自检: {html_name} ===")
    lines.append(f"画布 {fig.get('w', '?')}x{fig.get('h', '?')} px, 文字块 {geom.get('blocks', '?')} 个")
    if n == 0:
        lines.append("✅ PASS — 无文字溢出 / 越界 / 重叠")
        return 0, lines
    if overflow:
        lines.append(f"❌ 文字溢出被裁 {len(overflow)} 处（盒子太窄/太矮，文字被切）：")
        for o in overflow[:12]:
            lines.append(f"   · 「{o.get('txt')}」 实宽{o.get('sw')}>盒宽{o.get('cw')} 实高{o.get('sh')}>盒高{o.get('ch')}")
    if clip:
        lines.append(f"❌ 越出 .fig 边界 {len(clip)} 处（会被页面裁掉）：")
        for c in clip[:12]:
            sides = []
            for k, name in (("left", "左"), ("top", "上"), ("right", "右"), ("bottom", "下")):
                if c.get(k, 0) > 0:
                    sides.append(f"{name}越{c[k]}px")
            lines.append(f"   · 「{c.get('txt')}」 {' '.join(sides)}")
    if overlap:
        lines.append(f"❌ 文字块重叠 {len(overlap)} 对（内容互相压盖）：")
        for v in overlap[:12]:
            lines.append(f"   · 「{v.get('a')}」 ×「{v.get('b')}」 交叠面积{v.get('area')}px²")
    lines.append(f"⛔ 共 {n} 处几何问题 — 读 HTML 针对性改 CSS 后重跑本脚本。")
    return n, lines


def render_one_html(
    html_path: Path,
    png_path: Path,
    tool: Path,
    *,
    render_math: bool,
) -> tuple[bool, int, list[str]]:
    """先几何自检拿画布尺寸，再按内容真实宽高截紧凑 PNG（无右侧白边）。

    返回 (截图是否成功, 几何问题数[-1=无法检查], 几何报告行)。
    """
    png_path.parent.mkdir(parents=True, exist_ok=True)
    file_abs = str(html_path.resolve())

    # 第一趟：只测量（geomCheck，不出图）→ 拿 .fig 真实宽高 + 溢出/越界/重叠
    geom_target = {"file": file_abs, "geomCheck": True, "waitMs": 1200}
    if render_math:
        geom_target["renderMath"] = True
    gres = _run_capture_config(tool, {
        "viewport": {"width": 1400, "height": 1000},
        "targets": [geom_target],
    })
    grows = (gres.get("results") or [])
    geom = (grows[0].get("geom") if grows else None) or {}
    n_geom, report = _geom_report(geom, html_path.name)

    fig = geom.get("fig") or {}
    # 视口贴合内容真实尺寸 → PNG 不留右侧/底部白边。留 8px 余量防边缘 1px 裁切。
    w = int(fig.get("w") or 0) + 8
    h = int(fig.get("h") or 0) + 8
    w = max(_MIN_DIM, min(w, _MAX_DIM))
    h = max(_MIN_DIM, min(h, _MAX_DIM))

    # 第二趟：按贴合视口出 PNG（fullPage 兜底把窗口拉到内容高度）
    png_target = {"file": file_abs, "out": str(png_path.resolve()), "waitMs": 1500, "fullPage": True}
    if render_math:
        png_target["renderMath"] = True
    pres = _run_capture_config(tool, {
        "viewport": {"width": w, "height": h},
        "targets": [png_target],
    })
    prows = pres.get("results") or []
    ok = bool(prows) and prows[0].get("ok") and png_path.is_file() and png_path.stat().st_size > 1000
    if not ok:
        err = (prows[0].get("error") if prows else None) or pres.get("error") or pres.get("stderr") or "未知"
        report.append(f"❌ {html_path.name} 截图失败：{str(err)[:300]}")
    return ok, n_geom, report


def _try_write_docx(out_md: Path, docx_out: Path) -> bool:
    """复用 mermaid_render.try_write_docx（同目录）调 md_to_docx.py；导入失败则内联兜底。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from mermaid_render import try_write_docx  # type: ignore
        return try_write_docx(out_md, docx_out)
    except Exception as e:
        print(f"警告：无法复用 mermaid_render.try_write_docx（{e}），直接调 md_to_docx.py", file=sys.stderr)
        md_script = Path(__file__).resolve().parent / "md_to_docx.py"
        if not md_script.is_file():
            print("警告：未找到 md_to_docx.py，跳过 Word。", file=sys.stderr)
            return False
        docx_out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(md_script), "-i", str(out_md), "-o", str(docx_out),
               "--base-dir", str(out_md.parent)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except Exception as e2:
            print(f"警告：md_to_docx 启动失败：{e2}", file=sys.stderr)
            return False
        if r.returncode != 0:
            print(f"警告：md_to_docx 失败（退出码 {r.returncode}）。", file=sys.stderr)
            print((r.stderr or r.stdout or "")[:2000], file=sys.stderr)
            return False
        print(f"已写入 Word: {docx_out}", file=sys.stderr)
        return True


def main(argv: list[str] | None = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    p = argparse.ArgumentParser(
        description="交底书内自包含 HTML 图（fig_arch/fig_flow）→ PNG，默认再导出 Word"
    )
    p.add_argument("-i", "--input", required=True, type=Path, help="草稿 .md（含 <!-- ![描述](figures/xxx.png) --> 引用）")
    p.add_argument("-o", "--output", required=True, type=Path, help="定稿 .md（供 md_to_docx 嵌图）")
    p.add_argument("--fig-dir", type=Path, default=None,
                   help="HTML 图所在目录（缺省=输入 .md 所在目录）")
    p.add_argument("--assets-dir", default="figures",
                   help="PNG 输出相对 --fig-dir 的子目录（默认 figures，与 md 引用路径一致）")
    p.add_argument("--docx", type=Path, default=None, metavar="PATH",
                   help="输出 .docx（缺省=与 -o 同名 .docx）")
    p.add_argument("--no-docx", action="store_true", help="只出图 + 写 .md，不导出 Word")
    p.add_argument("--render-math", action="store_true",
                   help="截图前注入 KaTeX 渲染图内 \\(...\\)/\\[...\\] 公式（图内含公式时加）")
    args = p.parse_args(argv)

    in_path = args.input.resolve()
    if not in_path.is_file():
        print(f"错误：找不到输入 {in_path}", file=sys.stderr)
        return 1
    out_path = args.output.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig_dir = (args.fig_dir.resolve() if args.fig_dir else in_path.parent)
    assets_dir = fig_dir / (args.assets_dir.strip("/\\") or "figures")

    # 定稿 md = 草稿原样（图引用注释已在草稿里；md_to_docx 见 PNG 存在即嵌图）
    try:
        md = in_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        md = in_path.read_text(encoding="utf-8", errors="replace")
    out_path.write_text(md, encoding="utf-8")

    # 收集要出的 HTML 图：fig_*.html（系统框图 fig_arch / 流程图 fig_flow）
    html_files = sorted(fig_dir.glob("fig_*.html"))
    tool = _find_screenshot_tool()

    n_ok = n_fail = 0
    total_geom_issues = 0
    if not html_files:
        print(f"[html_figure_render] {fig_dir} 下未找到 fig_*.html（无图可出，仍继续导出）", file=sys.stderr)
    elif tool is None or not _electron_available(tool):
        # 降级不中断：图缺失但 md/docx 仍生成，如实汇报
        print(
            "[html_figure_render] Electron 截图后端不可用 — 跳过出图（Word 中框图/流程图将缺失，"
            "显示 [图片缺失]）。这不阻塞导出，请在汇报里如实说明。",
            file=sys.stderr,
        )
    else:
        print(f"[html_figure_render] 使用 Electron 截图后端：{tool}", file=sys.stderr)
        for hf in html_files:
            png_path = assets_dir / (hf.stem + ".png")
            try:
                ok, n_geom, report = render_one_html(
                    hf, png_path, tool, render_math=args.render_math,
                )
            except Exception as e:
                n_fail += 1
                print(f"[html_figure_render] {hf.name} 出图异常（已跳过）：{e}", file=sys.stderr)
                continue
            for ln in report:
                print(ln, file=sys.stderr)
            if n_geom > 0:
                total_geom_issues += n_geom
            if ok:
                n_ok += 1
                print(f"✅ {hf.name} → {png_path}", file=sys.stderr)
            else:
                n_fail += 1

    print(
        f"[html_figure_render] 出图完成：{n_ok} 张成功"
        + (f"，{n_fail} 张失败/跳过" if n_fail else "")
        + (f"；⚠ 累计 {total_geom_issues} 处几何问题需修（读 HTML 改 CSS 后重跑）" if total_geom_issues else ""),
        file=sys.stderr,
    )

    if args.no_docx:
        return 0
    docx_path = args.docx.resolve() if args.docx is not None else out_path.with_suffix(".docx")
    _try_write_docx(out_path, docx_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
