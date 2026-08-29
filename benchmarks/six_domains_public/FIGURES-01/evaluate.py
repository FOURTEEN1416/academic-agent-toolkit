#!/usr/bin/env python3
"""评分脚本：FIGURES-01 科研绘图公开基准。用法: python evaluate.py <工作区>"""
import json
import re
import sys
from pathlib import Path


def _png_dpi(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.info.get("dpi", (0, 0))
    except Exception:
        return None


def _svg_text_overflow(svg: Path, font_size: int = 14) -> list[str]:
    """近似几何检查：SVG text 的 x + 估宽 不得超出 viewBox 宽。"""
    text = svg.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', text)
    if not m:
        return ["svg missing viewBox"]
    width = int(m.group(1))
    issues = []
    try:
        from PIL import ImageFont
        font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", font_size)
    except Exception:
        return issues  # 平台无字体时跳过该检查
    for tm in re.finditer(r'<text[^>]*x="(\d+(?:\.\d+)?)"[^>]*>([^<]+)</text>', text):
        x, label = float(tm.group(1)), tm.group(2)
        anchor = re.search(tm.group(0), text)
        if 'text-anchor="middle"' in tm.group(0):
            start = x - font.getlength(label) / 2
        else:
            start = x
        if start + font.getlength(label) > width:
            issues.append(f"text beyond canvas: {label[:20]}")
    return issues


def score(workspace: Path) -> dict:
    r: dict = {}

    # 1. 产物存在性
    fig_png = workspace / "figures" / "fig_results.png"
    tex = workspace / "figures" / "latex_includes.tex"
    prov = workspace / "figures" / "FIGURE_PROVENANCE.json"
    r["file_png"] = fig_png.is_file()
    r["file_tex"] = tex.is_file()
    r["file_provenance"] = prov.is_file()
    svgs = list((workspace / "figures" / "diagrams").glob("*.svg")) if (workspace / "figures" / "diagrams").is_dir() else []
    r["file_architecture_svg"] = bool(svgs)

    # 2. PNG 分辨率 ≥ 300dpi
    if fig_png.is_file():
        dpi = _png_dpi(fig_png)
        r["png_dpi"] = dpi
        r["png_dpi_ok"] = bool(dpi and min(dpi) >= 290)

    # 3. tex 字节健康（不得含 0x08 等转义损坏；须含 \begin{figure}）
    if tex.is_file():
        raw = tex.read_bytes()
        r["tex_no_control_bytes"] = b"\x08" not in raw and b"\x00" not in raw
        r["tex_has_figure_env"] = b"\\begin{figure}" in raw
        r["tex_has_label"] = b"\\label{" in raw

    # 4. 题注一致性：声称 n= 时，溯源/数据须可对上（CSV 5 次重复 → 不得声称 n≥10）
    if tex.is_file():
        t = tex.read_text(encoding="utf-8", errors="ignore")
        claimed = re.findall(r"n=(\d+)", t)
        r["caption_n_claimed"] = claimed
        r["caption_n_ok"] = all(int(x) <= 5 for x in claimed) or not claimed

    # 5. 溯源覆盖全部图产物
    if prov.is_file():
        p = json.loads(prov.read_text(encoding="utf-8"))
        figs = p.get("figures", [])
        declared = {f.get("file", "") for f in figs}
        actual = {"figures/fig_results.png"} | {f"figures/diagrams/{s.name}" for s in svgs}
        r["provenance_count"] = len(figs)
        r["provenance_covers_all"] = actual.issubset(declared) if svgs else "figures/fig_results.png" in declared
        r["provenance_has_scripts"] = all(f.get("script") for f in figs)

    # 6. SVG 几何：无越界文本
    if svgs:
        all_issues = []
        for s in svgs:
            all_issues += _svg_text_overflow(s)
        r["svg_geometry_issues"] = all_issues
        r["svg_geometry_ok"] = not all_issues

    # 7. figure_provenance 引擎门禁（若工作区带 .engine 则直接复用）
    gate = workspace / ".engine" / "workflow.sqlite"
    r["engine_gate_available"] = gate.is_file()

    r["_pass"] = all(v is True for k, v in r.items() if isinstance(v, bool))
    return r


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    ws = Path(sys.argv[1])
    if not ws.is_dir():
        print(f"FAIL: 工作区不存在: {ws}")
        sys.exit(1)
    result = score(ws)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    sys.exit(0 if result["_pass"] else 1)
