#!/usr/bin/env python3
"""
将 Markdown 中的 **mermaid** 围栏与（默认）**LaTeX 公式** 转为 PNG，再写定稿 `.md` 并默认生成 Word。

**公式**：**默认不转 PNG**，交由 ``md_to_docx.py`` 渲染为 Word 原生 **OMML 矢量公式**（可编辑、清晰、不糊）；仅 ``--math-png`` 时才先调用同目录 **`math_render.py`**（``matplotlib``）预渲染为 PNG。**Mermaid** 围栏块逐块渲染为 PNG，**保留** `` ```mermaid`` … `` ``` `` 源码，并在其后追加 HTML 注释
``<!-- ![图示](相对路径) -->``（预览不显示图），便于 ``md_to_docx.py`` 将图嵌入 Word（Word **仅**嵌 PNG，不写 mermaid 代码块）。

**Mermaid 渲染后端（``mmdc``）**检测顺序见 ``_find_mmdc_invocation``：
1. ``tools/node_modules``（``npm install`` 官方 ``@mermaid-js/mermaid-cli``）；
2. **PATH 上的 ``mmdc``**（通常为 ``npm install -g @mermaid-js/mermaid-cli``）；
3. **Node.js + npx** 临时拉取 ``@mermaid-js/mermaid-cli``（无本地安装时）。

交底书 **3.2 系统框图**与 **3.4 流程图**均使用 fenced mermaid；**不要** ASCII「文字箭头」流程图或框图。

**降级**：某一围栏 ``mmdc`` 生图失败时**不中断**：该处**保留原** `` ```mermaid`` … `` ``` `` 围栏；其余块照常渲染。仍写出 .md 并**照常尝试** ``md_to_docx.py``（Word 中失败块以代码块形式出现）。

**清晰度**：默认对 ``mmdc`` 传入较大视口（``-w`` / ``-H``）与 ``-s 2``（Puppeteer 像素密度），PNG 在 Word 中按约 5.5 英寸宽嵌入时更锐利。可用 ``--mmdc-scale 3`` 等进一步提高（文件更大）。

用法：
  python tools/mermaid_render.py -i draft.md -o disclosure.md
  # 默认在同目录生成 disclosure.docx；失败时 stderr 会给出可复制的 md_to_docx 命令
  python tools/mermaid_render.py -i draft.md -o out/disclosure.md --docx out/custom.docx
  python tools/mermaid_render.py -i draft.md -o disclosure.md --no-docx   # 仅 Markdown

写出 .md 后**默认**调用 ``md_to_docx.py``；Word 失败不导致进程失败（退出码 0），并提示手动转换。
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _local_mmdc() -> tuple[list[str], bool] | None:
    """``tools/npm install`` 后可用 ``node_modules/.bin/mmdc``，避免每次 npx 拉包。"""
    here = Path(__file__).resolve().parent
    if sys.platform == "win32":
        cand = here / "node_modules" / ".bin" / "mmdc.cmd"
    else:
        cand = here / "node_modules" / ".bin" / "mmdc"
    if cand.is_file():
        return [str(cand)], False
    return None


def _find_mmdc_invocation() -> tuple[list[str], bool]:
    """
    返回 (argv 前缀, use_shell)。
    Windows 上 npx 常为 .ps1，无独立 .exe，需 shell=True 调用 ``npx ...``。
    PATH 中的 ``mmdc`` 一般为 npm 全局安装的官方 CLI。
    """
    local = _local_mmdc()
    if local:
        return local
    mmdc = shutil.which("mmdc")
    if mmdc and Path(mmdc).suffix.lower() not in (".ps1",):
        return [mmdc], False
    if sys.platform == "win32":
        return ["npx", "-y", "@mermaid-js/mermaid-cli", "mmdc"], True
    return ["npx", "-y", "@mermaid-js/mermaid-cli", "mmdc"], False


# ─────────────────────────────────────────────────────────────
# Electron 截图后端：把 mermaid 源码包成 HTML，用 screenshot_capture.py
# (Electron capturePage) 截成 PNG。不依赖 mmdc/Node/Puppeteer——复用平台
# 打包自带的 Chromium 内核，和软著截图同一套。mmdc 不可用时的首选后端。
# ─────────────────────────────────────────────────────────────

_CDN_MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"


def _find_screenshot_tool() -> Path | None:
    """定位 screenshot_capture.py。顺序：环境变量 → 上级 _utils/ → 项目 tools/。

    工作区运行时脚本被复制到 _utils/patent_scripts/，screenshot_capture.py
    在其兄弟目录 _utils/ 下；开发直跑时在项目 tools/。
    """
    env = os.environ.get("MH_SCREENSHOT_TOOL")
    if env and Path(env).is_file():
        return Path(env)
    here = Path(__file__).resolve().parent
    cands = [
        here.parent / "screenshot_capture.py",           # _utils/patent_scripts/ → _utils/
        here.parent.parent / "screenshot_capture.py",    # 再上一层兜底
        here / "screenshot_capture.py",                   # 同目录
    ]
    # 开发直跑：项目根 tools/screenshot_capture.py
    for up in (here, *here.parents):
        cands.append(up / "tools" / "screenshot_capture.py")
    for c in cands:
        if c.is_file():
            return c
    return None


def _electron_capture_available(tool: Path) -> bool:
    """跑 screenshot_capture.py --check，exit 0 表示 Electron 可用。"""
    try:
        r = subprocess.run(
            [sys.executable, str(tool), "--check"],
            capture_output=True, text=True, timeout=60,
        )
        return r.returncode == 0
    except Exception:
        return False


def _local_mermaid_js() -> Path | None:
    """脚本同目录下的本地 mermaid.min.js（随成品脚本分发，免联网）。"""
    cand = Path(__file__).resolve().parent / "mermaid.min.js"
    return cand if cand.is_file() else None


def _mermaid_html(mermaid_source: str) -> str:
    """把一段 mermaid 源码包成可渲染的 HTML。优先本地 mermaid.min.js，无则 CDN。"""
    local = _local_mermaid_js()
    if local:
        src_ref = local.resolve().as_uri()
    else:
        src_ref = _CDN_MERMAID
    body = mermaid_source.strip()
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<script src=\"{src_ref}\"></script>"
        "<style>body{background:#fff;margin:16px}"
        ".mermaid{font-size:16px}</style></head><body>"
        f"<pre class=\"mermaid\">\n{body}\n</pre>"
        "<script>mermaid.initialize({startOnLoad:true});</script>"
        "</body></html>"
    )


def _render_one_mermaid_electron(
    mermaid_source: str,
    png_path: Path,
    tool: Path,
    *,
    width: int,
    height: int,
) -> None:
    """写临时 HTML → 调 screenshot_capture.py 等 <svg> 出现后 fullPage 截图。失败抛异常。"""
    png_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8",
    ) as tmp:
        tmp.write(_mermaid_html(mermaid_source))
        html_path = Path(tmp.name)
    cfg_path = html_path.with_suffix(".cfg.json")
    result_path = html_path.with_suffix(".result.json")
    try:
        import json as _json
        cfg = {
            "viewport": {"width": width, "height": height},
            "resultPath": str(result_path.resolve()),
            "targets": [{
                "file": str(html_path.resolve()),
                "out": str(png_path.resolve()),
                "waitForSelector": "svg",
                "waitMs": 3500,
                "fullPage": True,
            }],
        }
        cfg_path.write_text(_json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(tool), "--config", str(cfg_path.resolve())],
            capture_output=True, text=True, timeout=180,
        )
        ok = r.returncode == 0 and png_path.is_file() and png_path.stat().st_size > 0
        if not ok:
            err = (r.stderr or r.stdout or "").strip()
            raise RuntimeError(f"electron 截图失败 (exit {r.returncode}): {err[:800]}")
    finally:
        for p in (html_path, cfg_path, result_path):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


def _mmdc_extra_args(
    *,
    scale: float,
    width: int,
    height: int,
) -> list[str]:
    """传给 mmdc 的分辨率相关参数（-s 为 Puppeteer deviceScaleFactor，显著影响 PNG 清晰度）。"""
    return [
        "-s",
        str(scale),
        "-w",
        str(width),
        "-H",
        str(height),
    ]


def _render_one_mermaid(
    mermaid_source: str,
    png_path: Path,
    mmdc_base: list[str],
    *,
    use_shell: bool,
    scale: float,
    width: int,
    height: int,
) -> None:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".mmd",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(mermaid_source.strip() + "\n")
        tmp_path = Path(tmp.name)
    try:
        extra = _mmdc_extra_args(scale=scale, width=width, height=height)
        if use_shell:
            parts = [
                *mmdc_base,
                "-i",
                str(tmp_path),
                "-o",
                str(png_path),
                "-b",
                "white",
                *extra,
            ]
            cmd = " ".join(shlex.quote(p) for p in parts)
            r = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
        else:
            cmd = [
                *mmdc_base,
                "-i",
                str(tmp_path),
                "-o",
                str(png_path),
                "-b",
                "white",
                *extra,
            ]
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
            )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            raise RuntimeError(f"mmdc 失败 (exit {r.returncode}): {err[:2000]}")
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


_MMD_START = re.compile(r"^```mermaid\s*$", re.IGNORECASE)
_MMD_END = re.compile(r"^```\s*$")
_MERMAID_HIDDEN_COMMENT_RE = re.compile(
    r"<!--\s*!\[([^\]]*)\]\(([^)]+)\)\s*-->"
)


def _is_mermaid_figure_comment(alt: str, src: str) -> bool:
    s = src.strip().replace("\\", "/")
    if "mermaid_figures" in s:
        return True
    a = alt.strip()
    return a.startswith("图示") or a.startswith("图 ")


def render_markdown_mermaid(
    md_text: str,
    *,
    out_md_path: Path,
    assets_rel: str,
    mmdc_scale: float = 2.0,
    mmdc_width: int = 1400,
    mmdc_height: int = 1050,
) -> tuple[str, int, int]:
    """
    返回 (新 markdown 全文, 成功转为 PNG 的块数, 生图失败而保留围栏的块数)。
    资源目录为 out_md_path.parent / assets_rel。
    失败的块原样写回 `` ```mermaid`` … `` ``` ``，不抛错。
    成功的块写回围栏源码 + 紧随其后的 ``<!-- ![图示](…) -->``（与 ``math_render`` 保留 LaTeX 原文同理）。
    若围栏后已有 mermaid 图示注释，则视为已处理，原样跳过（可重复跑脚本）。
    """
    lines = md_text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    ok = 0
    failed = 0
    block_idx = 0
    assets_dir = out_md_path.parent / assets_rel
    mmdc_base, use_shell = _find_mmdc_invocation()

    # 首选 Electron 截图后端（复用平台自带 Chromium，不依赖 mmdc/Node）。
    # 探测到可用则整份文档都走它；不可用再回落 mmdc。
    _shot_tool = _find_screenshot_tool()
    _use_electron = bool(_shot_tool) and _electron_capture_available(_shot_tool)
    if _use_electron:
        print(f"[mermaid_render] 使用 Electron 截图后端渲染 mermaid：{_shot_tool}", file=sys.stderr)
    else:
        print("[mermaid_render] Electron 截图后端不可用，回落 mmdc/npx", file=sys.stderr)

    while i < len(lines):
        line = lines[i]
        if _MMD_START.match(line):
            fence_open = line
            i += 1
            body: list[str] = []
            while i < len(lines) and not _MMD_END.match(lines[i]):
                body.append(lines[i])
                i += 1
            closing = lines[i] if i < len(lines) else "```\n"
            if i < len(lines):
                i += 1

            # 已定稿：围栏 + 图示注释，不重复渲染
            j = i
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines):
                cm = _MERMAID_HIDDEN_COMMENT_RE.match(lines[j].strip())
                if cm and _is_mermaid_figure_comment(cm.group(1), cm.group(2)):
                    out.append(fence_open)
                    out.extend(body)
                    if not closing.endswith("\n"):
                        closing = closing + "\n"
                    out.append(closing)
                    while i < j:
                        out.append(lines[i])
                        i += 1
                    out.append(lines[i])
                    i += 1
                    ok += 1
                    continue

            block_idx += 1
            fname = f"fig_{ok + 1:03d}.png"
            png_path = assets_dir / fname
            try:
                if _use_electron:
                    try:
                        _render_one_mermaid_electron(
                            "".join(body), png_path, _shot_tool,
                            width=mmdc_width, height=mmdc_height,
                        )
                    except Exception as e_shot:
                        # Electron 单块失败：本块回落 mmdc 再试一次
                        print(
                            f"[mermaid_render] 第 {block_idx} 块 Electron 截图失败，回落 mmdc：{e_shot}",
                            file=sys.stderr,
                        )
                        _render_one_mermaid(
                            "".join(body), png_path, mmdc_base,
                            use_shell=use_shell, scale=mmdc_scale,
                            width=mmdc_width, height=mmdc_height,
                        )
                else:
                    _render_one_mermaid(
                        "".join(body),
                        png_path,
                        mmdc_base,
                        use_shell=use_shell,
                        scale=mmdc_scale,
                        width=mmdc_width,
                        height=mmdc_height,
                    )
            except Exception as e:
                failed += 1
                print(
                    f"[mermaid_render] 第 {block_idx} 个 mermaid 围栏生图失败（已保留源码）：{e}",
                    file=sys.stderr,
                )
                out.append(fence_open)
                out.extend(body)
                if not closing.endswith("\n"):
                    closing = closing + "\n"
                out.append(closing)
                continue
            ok += 1
            rel = f"{assets_rel.strip('/')}/{fname}".replace("\\", "/")
            out.append(fence_open)
            out.extend(body)
            if not closing.endswith("\n"):
                closing = closing + "\n"
            out.append(closing)
            out.append(f"<!-- ![图示 {ok}]({rel}) -->\n")
            continue
        out.append(line)
        i += 1

    return "".join(out), ok, failed


def _print_manual_docx_hint(out_md: Path, docx_out: Path, base_dir: Path, md_script: Path) -> None:
    print(
        "提示：可手动将上述 Markdown 转为 Word（需已 pip install -r requirements.txt）：",
        file=sys.stderr,
    )
    if md_script.is_file():
        parts = [
            sys.executable,
            str(md_script),
            "-i",
            str(out_md),
            "-o",
            str(docx_out),
            "--base-dir",
            str(base_dir),
        ]
        print("  " + " ".join(shlex.quote(p) for p in parts), file=sys.stderr)
    else:
        print(
            "  python tools/md_to_docx.py -i <上述.md> -o <输出.docx> --base-dir <.md 所在目录>",
            file=sys.stderr,
        )


def try_write_docx(out_md: Path, docx_out: Path) -> bool:
    """
    调用同目录下的 md_to_docx.py。成功返回 True；失败打印警告与手动命令，返回 False。
    """
    tools_dir = Path(__file__).resolve().parent
    md_script = tools_dir / "md_to_docx.py"
    base_dir = out_md.parent
    docx_out.parent.mkdir(parents=True, exist_ok=True)

    if not md_script.is_file():
        print("警告：未找到 md_to_docx.py，跳过 Word。", file=sys.stderr)
        _print_manual_docx_hint(out_md, docx_out, base_dir, md_script)
        return False

    cmd = [
        sys.executable,
        str(md_script),
        "-i",
        str(out_md),
        "-o",
        str(docx_out),
        "--base-dir",
        str(base_dir),
    ]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("警告：生成 Word 超时（300s）。", file=sys.stderr)
        _print_manual_docx_hint(out_md, docx_out, base_dir, md_script)
        return False
    except OSError as e:
        print(f"警告：无法启动 md_to_docx：{e}", file=sys.stderr)
        _print_manual_docx_hint(out_md, docx_out, base_dir, md_script)
        return False

    if r.returncode != 0:
        print(f"警告：md_to_docx 失败（退出码 {r.returncode}）。", file=sys.stderr)
        err = (r.stderr or r.stdout or "").strip()
        if err:
            print(err[:2000], file=sys.stderr)
        _print_manual_docx_hint(out_md, docx_out, base_dir, md_script)
        return False

    print(f"已写入 Word: {docx_out}", file=sys.stderr)
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Markdown 内 mermaid 围栏 → PNG，默认再生成同名 Word"
    )
    p.add_argument("-i", "--input", required=True, type=Path, help="含 mermaid 围栏的 .md")
    p.add_argument("-o", "--output", required=True, type=Path, help="输出 .md（图片引用）")
    p.add_argument(
        "--assets-dir",
        default="mermaid_figures",
        help="mermaid 生成 PNG 的相对子目录（默认 mermaid_figures）",
    )
    p.add_argument(
        "--docx",
        type=Path,
        default=None,
        metavar="PATH",
        help="输出 .docx 路径（默认与 -o 同主文件名、扩展名 .docx）",
    )
    p.add_argument(
        "--no-docx",
        action="store_true",
        help="不生成 Word，仅输出替换图片后的 Markdown",
    )
    p.add_argument(
        "--math-png",
        action="store_true",
        help="把 LaTeX 公式先渲染成 PNG（默认关闭：公式在 md_to_docx 里走 Word 原生 OMML 矢量公式，可编辑、更清晰、不糊）",
    )
    p.add_argument(
        "--math-assets-dir",
        default="math_figures",
        help="公式 PNG 相对 -o 输出 .md 的子目录（默认 math_figures）",
    )
    p.add_argument(
        "--mmdc-scale",
        type=float,
        default=2.0,
        metavar="N",
        help="mmdc -s：Puppeteer 缩放（默认 2，约 2 倍像素密度；越大越清晰但文件更大）",
    )
    p.add_argument(
        "--mmdc-width",
        type=int,
        default=1400,
        metavar="PX",
        help="mmdc -w：渲染视口宽度像素（默认 1400，复杂 flowchart 不易裁切）",
    )
    p.add_argument(
        "--mmdc-height",
        type=int,
        default=1050,
        metavar="PX",
        help="mmdc -H：渲染视口高度像素（默认 1050）",
    )
    args = p.parse_args(argv)
    if args.mmdc_scale <= 0:
        print("错误：--mmdc-scale 须为正数", file=sys.stderr)
        return 1
    if args.mmdc_width < 400 or args.mmdc_height < 400:
        print("错误：--mmdc-width / --mmdc-height 建议不小于 400", file=sys.stderr)
        return 1

    in_path = args.input.resolve()
    if not in_path.is_file():
        print(f"错误：找不到输入 {in_path}", file=sys.stderr)
        return 1

    out_path = args.output.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        md = in_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        md = in_path.read_text(encoding="utf-8", errors="replace")

    math_ok = math_fail = 0
    # 公式默认不转 PNG：交给 md_to_docx 走 Word 原生 OMML 矢量公式（可编辑、更清晰）。
    # 仅在显式 --math-png 时才在此预渲染为 PNG。
    if getattr(args, "math_png", False):
        try:
            from math_render import render_markdown_math

            md, math_ok, math_fail = render_markdown_math(
                md,
                out_md_path=out_path,
                assets_rel=getattr(args, "math_assets_dir", "math_figures"),
            )
            if math_ok or math_fail:
                parts_m = [f"公式：{math_ok} 处已转为 PNG"]
                if math_fail:
                    parts_m.append(f"，{math_fail} 处失败已保留原文")
                print("[mermaid_render] " + "".join(parts_m), file=sys.stderr)
        except ImportError:
            print(
                "[mermaid_render] 未安装 matplotlib，跳过公式渲染（pip install matplotlib）",
                file=sys.stderr,
            )

    new_md, n_ok, n_fail = render_markdown_mermaid(
        md,
        out_md_path=out_path,
        assets_rel=args.assets_dir.strip("/\\") or "mermaid_figures",
        mmdc_scale=args.mmdc_scale,
        mmdc_width=args.mmdc_width,
        mmdc_height=args.mmdc_height,
    )

    out_path.write_text(new_md, encoding="utf-8")
    parts = [f"已写入 {out_path}（mermaid：{n_ok} 处已转为 PNG"]
    if n_fail:
        parts.append(f"，{n_fail} 处生图失败已保留 fenced 源码")
    parts.append("）")
    print("".join(parts), file=sys.stderr)
    if n_fail:
        print(
            "[mermaid_render] 已继续生成 Markdown"
            + (" 并将尝试 Word" if not args.no_docx else "")
            + "；请检查 Node/mmdc 或修正语法后重跑本脚本。",
            file=sys.stderr,
        )

    if args.no_docx:
        return 0

    docx_path = (
        args.docx.resolve()
        if args.docx is not None
        else out_path.with_suffix(".docx")
    )
    try_write_docx(out_path, docx_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
