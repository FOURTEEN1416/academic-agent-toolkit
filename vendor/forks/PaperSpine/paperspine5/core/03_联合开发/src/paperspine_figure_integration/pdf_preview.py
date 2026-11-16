"""Local PDF page previews for browsers without a built-in PDF viewer."""
from __future__ import annotations

import html
import io
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


def _run(program: str, arguments: list[str]) -> bytes:
    executable = shutil.which(program)
    if not executable:
        raise ValueError("本机缺少 PDF 预览组件，请下载原文件查看。")
    try:
        result = subprocess.run([executable, *arguments], capture_output=True, timeout=30,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("PDF 页面预览暂时无法生成，请重试或下载原文件查看。") from exc
    if result.returncode:
        raise ValueError("此 PDF 暂时无法生成页面预览，请下载原文件查看。")
    return result.stdout


def _number(value: object, default: float = 0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _point(page: object, x: object, y: object) -> tuple[float, float]:
    """PDF points -> fractions of pdftoppm's rotated MediaBox (not CropBox)."""
    box = page.mediabox
    width, height = float(box.width), float(box.height)
    if width <= 0 or height <= 0:
        raise ValueError("Invalid PDF page dimensions")
    px = (_number(x, float(box.left)) - float(box.left)) / width
    py = (_number(y, float(box.top)) - float(box.bottom)) / height
    rotation = int(page.rotation) % 360
    sx, sy = {0: (px, 1 - py), 90: (py, px),
              180: (1 - px, py), 270: (1 - py, 1 - px)}.get(rotation, (px, 1 - py))
    return max(0, min(1, sx)), max(0, min(1, sy))


def _external_uri(value: object) -> str | None:
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    # PDF actions are data: never execute JavaScript, Launch, file or GoToR.
    if parts.scheme.lower() in {"http", "https"} and parts.hostname:
        return value
    if parts.scheme.lower() == "mailto" and parts.path:
        return value
    return None


def _link_layout(body: bytes, page_count: int) -> tuple[list[dict], str]:
    """Read annotations only; never rewrite PDF bytes or fetch a linked resource."""
    try:
        from pypdf import PdfReader
        from pypdf.generic import Destination, Fit
    except ImportError:
        return [], "链接层组件暂不可用；页面仍可阅读，请通过原下载入口打开PDF中的链接。"
    try:
        reader = PdfReader(io.BytesIO(body))
        if len(reader.pages) != page_count:
            raise ValueError("PDF page count mismatch")
        named = reader.named_destinations
        layouts = []
        for page in reader.pages:
            w, h = float(page.mediabox.width), float(page.mediabox.height)
            if int(page.rotation) % 180:
                w, h = h, w
            if not all(math.isfinite(v) and v > 0 for v in (w, h)):
                raise ValueError("Invalid PDF page dimensions")
            layouts.append({"width": w, "height": h, "links": [], "targets": []})

        def destination(raw: object) -> tuple[int, float, float] | None:
            if hasattr(raw, "get_object"):
                raw = raw.get_object()
            if isinstance(raw, str):
                found = named.get(raw) or named.get(raw.lstrip("/")) or named.get("/" + raw.lstrip("/"))
                if found is None:
                    return None
                raw = found.dest_array
            if isinstance(raw, dict):
                raw = raw.get("/D")
            if not isinstance(raw, (list, tuple)) or len(raw) < 2:
                return None
            mode = str(raw[1])
            dest = Destination("preview", raw[0], Fit(mode, raw[2:]))
            number = reader.get_destination_page_number(dest)
            if number is None or not 0 <= number < page_count:
                return None
            page = reader.pages[number]
            box = page.mediabox
            x, y = float(box.left), float(box.top)
            if mode == "/XYZ":
                x, y = _number(dest.left, x), _number(dest.top, y)
            elif mode in {"/FitH", "/FitBH"}:
                y = _number(dest.top, y)
            elif mode in {"/FitV", "/FitBV"}:
                x = _number(dest.left, x)
            elif mode == "/FitR":
                # The visual top-left of a rectangular destination after rotation.
                points = [_point(page, px, py) for px in (dest.left, dest.right)
                          for py in (dest.bottom, dest.top)]
                return number, min(p[0] for p in points), min(p[1] for p in points)
            elif mode in {"/Fit", "/FitB"}:
                return number, 0, 0
            else:
                return None
            return number, *_point(page, x, y)

        unreadable = False
        for page_index, page in enumerate(reader.pages):
            for annotation in page.get("/Annots", []):
                try:
                    item = annotation.get_object()
                    if item.get("/Subtype") != "/Link" or int(item.get("/F", 0)) & (1 | 2 | 32):
                        continue
                    rect = item.get("/Rect")
                    if not rect or len(rect) != 4:
                        continue
                    corners = [_point(page, px, py) for px in (rect[0], rect[2])
                               for py in (rect[1], rect[3])]
                    left, top = min(p[0] for p in corners), min(p[1] for p in corners)
                    width = max(p[0] for p in corners) - left
                    height = max(p[1] for p in corners) - top
                    if not width or not height:
                        continue
                    action = item.get("/A", {})
                    if hasattr(action, "get_object"):
                        action = action.get_object()
                    link = {"left": left, "top": top, "width": width, "height": height}
                    if action.get("/S") == "/URI":
                        uri = _external_uri(action.get("/URI"))
                        if not uri:
                            continue
                        link.update(href=uri, external=True, label="打开PDF外链：" + uri)
                    else:
                        if "/A" in item and action.get("/S") != "/GoTo":
                            continue
                        target = destination(action.get("/D") if action else item.get("/Dest"))
                        if target is None:
                            continue
                        target_page, tx, ty = target
                        target_id = f"pdf-destination-{page_index + 1}-{len(layouts[page_index]['links']) + 1}"
                        layouts[target_page]["targets"].append({"id": target_id, "left": tx, "top": ty})
                        link.update(href="#" + target_id, external=False,
                                    label=f"PDF内部链接：跳转到第 {target_page + 1} 页的目标位置")
                    layouts[page_index]["links"].append(link)
                except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError):
                    unreadable = True
        return layouts, "个别PDF链接无法解析；其余可用链接与页面保留。" if unreadable else ""
    except Exception:
        # A malformed annotation tree must not erase an otherwise readable PDF.
        return [], "此PDF的链接层暂时无法读取；请通过原下载入口核对链接。"


def _position(item: dict) -> str:
    return ";".join(f"{key}:{item[key] * 100:.6f}%" for key in ("left", "top", "width", "height")
                    if key in item)


def pdf_response(body: bytes, filename: str, request_path: str, task_id: str) -> tuple[bytes, str]:
    """Render exact verified PDF bytes; never claim document quality from a preview."""
    if len(body) > 64 * 1024 * 1024 or not body.startswith(b"%PDF-"):
        raise ValueError("文件不适合在线预览，请下载后在本机查看。")
    parts = urlsplit(request_path)
    query = parse_qs(parts.query)
    with tempfile.TemporaryDirectory(prefix="paperspine-pdf-preview-") as directory:
        root = Path(directory)
        source = root / "source.pdf"
        source.write_bytes(body)
        if query.get("preview") == ["page"]:
            page_text = query.get("page", [""])[0]
            if not page_text.isascii() or not page_text.isdigit() or not 1 <= int(page_text) <= 256:
                raise ValueError("无效的 PDF 页码。")
            _run("pdftoppm", ["-f", page_text, "-l", page_text, "-singlefile", "-scale-to", "1600",
                               "-png", str(source), str(root / "page")])
            output = root / "page.png"
            if not output.is_file():
                raise ValueError("此 PDF 页不存在。")
            return output.read_bytes(), "image/png"
        info = _run("pdfinfo", [str(source)]).decode("utf-8", errors="replace")
        match = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
        if not match or not 1 <= int(match[1]) <= 256:
            raise ValueError("此 PDF 页数不适合在线预览，请下载原文件查看。")
        pages = int(match[1])
    layouts, notice = _link_layout(body, pages)
    title = html.escape(filename)
    back = "/?" + urlencode({"task_id": task_id})
    blocks = []
    for page in range(1, pages + 1):
        page_query = {**query, "preview": ["page"], "page": [str(page)]}
        url = urlunsplit(("", "", parts.path, urlencode(page_query, doseq=True), ""))
        loading = "eager" if page == 1 else "lazy"
        layout = layouts[page - 1] if layouts else None
        ratio = f' style="aspect-ratio:{layout["width"]}/{layout["height"]}"' if layout else ""
        layers = []
        if layout:
            for target in layout["targets"]:
                layers.append(f'<span class="pdf-target" id="{target["id"]}" tabindex="-1" '
                              f'style="{_position(target)}"></span>')
            for link in layout["links"]:
                escaped = html.escape(link["label"], quote=True)
                external = ' target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer"' if link["external"] else ""
                layers.append(f'<a class="pdf-link" href="{html.escape(link["href"], quote=True)}" '
                              f'style="{_position(link)}" aria-label="{escaped}" title="{escaped}"{external}></a>')
        blocks.append(f'<figure id="pdf-page-{page}"><figcaption>第 {page} / {pages} 页</figcaption>'
                      f'<div class="pdf-page"{ratio}><img loading="{loading}" '
                      f'src="{html.escape(url, quote=True)}" alt="{title} 第 {page} 页">'
                      f'{"".join(layers)}</div></figure>')
    page_html = (f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{title} · 预览</title>'
                 '<meta name="viewport" content="width=device-width,initial-scale=1">'
                 '<meta name="referrer" content="no-referrer">'
                 '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
                 'img-src \'self\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
                 '<style>body{margin:0;background:#eee;font:16px system-ui;color:#222}header{padding:16px;'
                 'background:white}figure{margin:16px auto;max-width:1000px}figcaption{padding:8px}'
                 '.pdf-page{position:relative;background:white}.pdf-page[style] img{position:absolute;height:100%;min-height:0}'
                 'img{display:block;width:100%;height:auto;min-height:200px;background:white}a{color:#215d42}'
                 '.pdf-link{position:absolute;display:block;z-index:2;min-width:2px;min-height:2px}'
                 '.pdf-link:hover,.pdf-link:focus-visible{outline:2px solid #215d42;background:#215d421a}'
                 '.pdf-target{position:absolute;width:1px;height:1px;scroll-margin-top:24px;pointer-events:none}'
                 '.pdf-target:target{outline:3px solid #215d42}</style>'
                 f'<header><a href="{html.escape(back, quote=True)}" target="_top">返回论文任务</a>'
                 f'<h1>{title}</h1><p>{pages} 页 · 原文件的页面预览</p>'
                 f'<p>{html.escape(notice) if notice else "可点击原PDF中的文献、图表链接；外链在新标签打开。"}</p>'
                 f'</header>{"".join(blocks)}</html>')
    return page_html.encode("utf-8"), "text/html; charset=utf-8"
