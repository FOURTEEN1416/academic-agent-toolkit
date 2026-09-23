#!/usr/bin/env python3
"""doc_reader.py — 完整文档读取器（防止漏读嵌入图片/照片）

背景：docx/pdf 中的关键信息（提交要求、格式规范、题目附图）经常以
嵌入图片/截图形式存在，仅提取文本会漏读。本工具读取文档时自动：
  1. 提取全部文本（段落/表格）
  2. 提取全部嵌入图片（落盘到 visual_review_tasks/docread_<文档名>/）
  3. 为每张图片生成宿主独立窗口识别任务卡——由项目驱动宿主自身视觉能力
     LLM 在独立窗口实际读图转录/描述（2026-09-23 换驱动：不再调用外部视觉 API，
     零 key 零网络），结论回写 verdict 后重跑本命令自动合并
  4. 输出「文本 + 图片内容」合并报告，确保不遗漏

用法：
   python doc_reader.py <文件.docx|文件.pdf> [--out report.md] [--max-images N] [--no-vision] [--allow-vision-failure]
  --no-vision   不做独立窗口图片识别（仅列出图片数量与位置，供人工查看）
  --max-images  最多识别前 N 张图片（默认全部）

输出：默认打印到 stdout；--out 时保存 markdown 报告。
退出码：0 成功；2 参数错误；3 独立窗口识别未就绪（任务卡已生成，--no-vision 时不受影响，
--allow-vision-failure 时降为成功）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def load_project_env() -> None:
    """加载套件 .env（套件环境配置）。"""
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from engine.env_loader import apply_env
        apply_env()
    except ImportError:
        pass


# ============ 宿主独立窗口图片识别（2026-09-23 换驱动，零 key 零网络） ============

TASK_DIR_NAME = "visual_review_tasks"
_REVIEWED_BY_PREFIX = "Reviewed-by:"
_IMAGE_PROMPT = (
    "这是一份竞赛文件中的嵌入图片（可能是截图、示意图、照片或表格图片）。"
    "请完整、逐字转录图片中的所有文字内容（标题、正文、表格、按钮、链接、界面文字等），"
    "不要遗漏任何细节；如果是示意图/照片，请描述其内容与关键信息。"
    "如果是提交要求/格式规范相关截图，请特别完整地转录所有要求条目。"
)


def _stage_image_for_host_window(doc_stem: str, index: int, data: bytes, ext: str,
                                 workspace: Path) -> Path:
    """嵌入图片落盘（供宿主独立窗口读图）。返回图片文件路径。"""
    img_dir = workspace / TASK_DIR_NAME / f"docread_{doc_stem}"
    img_dir.mkdir(parents=True, exist_ok=True)
    img_path = img_dir / f"img_{index}{ext if ext.startswith('.') else '.' + ext}"
    img_path.write_bytes(data)
    return img_path


def _build_docread_task_card(doc_stem: str, staged: list[dict]) -> str:
    """生成独立窗口图片识别任务卡（转录/描述，非质量审核）。"""
    lines = [
        "# 独立窗口文档图片识别任务卡",
        "",
        f"- 来源文档: {doc_stem}",
        "- 执行者要求: 必须由项目驱动宿主的**独立窗口**（视觉审子代理/独立会话，"
        "与读取该文档的窗口隔离）中的视觉能力 LLM **实际读图**执行；"
        "禁止由读取窗口自审。",
        "- 识别要求: " + " ".join(_IMAGE_PROMPT.splitlines()),
        "",
        "## 待识别图片",
        "",
    ]
    lines += [f"- 图片 {s['index']}: {s.get('staged_path', '')}" for s in staged]
    lines += [
        "",
        "## 回写要求（完成后写入本文件同目录的 " + f"docread_{doc_stem}.verdict.md" + "）",
        "",
        "格式（缺一即判证据无效）:",
        "",
        "```markdown",
        f"{_REVIEWED_BY_PREFIX} <执行窗口标识，如 zcode-visual-judge>",
        "",
        "### 图片 1",
        "<逐字转录/描述>",
        "### 图片 2",
        "...",
        "```",
    ]
    return "\n".join(lines) + "\n"


def _collect_docread_verdict(workspace: Path, doc_stem: str) -> tuple[str, dict[int, str]]:
    """收集独立窗口回写的逐图识别结论。返回 (reviewed_by, {图号: 描述})；
    verdict 缺失/无效返回 ("", {})。"""
    vpath = workspace / TASK_DIR_NAME / f"docread_{doc_stem}.verdict.md"
    if not vpath.is_file():
        return "", {}
    reviewed_by = ""
    sections: dict[int, list[str]] = {}
    current: int | None = None
    for raw in vpath.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line.startswith(_REVIEWED_BY_PREFIX):
            reviewed_by = line[len(_REVIEWED_BY_PREFIX):].strip()
            continue
        if line.startswith("### 图片"):
            try:
                current = int(line.replace("### 图片", "").strip())
            except ValueError:
                current = None
            sections.setdefault(current, [])
            continue
        if current is not None and line:
            sections[current].append(line)
    return reviewed_by, {k: "\n".join(v) for k, v in sections.items() if v}


def _load_image_bytes(data: bytes, ext: str) -> tuple[bytes, str]:
    """返回 (字节, mime)。PDF 中的图片直接是嵌入字节。"""
    mime = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".bmp": "image/bmp", ".tiff": "image/tiff",
    }.get(ext.lower(), "image/png")
    return data, mime


# ============ DOCX 读取 ============

def read_docx(path: Path, use_vision: bool, max_images: int) -> dict:
    from docx import Document
    doc = Document(str(path))
    report = {"text": [], "images": []}

    # 段落
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            report["text"].append(t)

    # 表格
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                report["text"].append(" | ".join(cells))

    # 关系表包含正文 inline/floating/VML 图片；页眉和页脚有各自的 part/关系表。
    seen = set()
    parts = [doc.part]
    for section in doc.sections:
        parts.extend((section.header.part, section.footer.part))
    for part in parts:
        for rel in part.rels.values():
            target = getattr(rel, "target_part", None)
            if target is None or not hasattr(target, "blob"):
                continue
            content_type = getattr(target, "content_type", "")
            if not content_type.startswith("image/"):
                continue
            try:
                key = target.partname
                if key in seen:
                    continue
                seen.add(key)
                data = target.blob
                ext = Path(str(target.partname)).suffix
                mime = _load_image_bytes(data, ext)[1]
                info = {"index": len(report["images"]) + 1, "size": len(data), "mime": mime}
                if use_vision and len(report["images"]) < max_images:
                    img_path = _stage_image_for_host_window(
                        path.stem, info["index"], data, ext, Path.cwd())
                    info["staged_path"] = str(img_path)
                    info["pending_host"] = True
                    info["content"] = "[待宿主独立窗口识别：见任务卡]"
                else:
                    info["content"] = "[未识别（--no-vision 或超过上限）]"
                report["images"].append(info)
            except Exception as e:
                report["images"].append({"index": len(report["images"]) + 1, "error": str(e)})
    return report


# ============ PDF 读取 ============

def read_pdf(path: Path, use_vision: bool, max_images: int) -> dict:
    import pymupdf as fitz  # 同 quality_gates：避开 fitz shim 的 stdout 警告
    doc = fitz.open(str(path))
    report = {"text": [], "images": []}

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        text = page.get_text().strip()
        if text:
            report["text"].append(f"--- 第 {page_idx + 1} 页 ---\n{text}")

        # 页面中的嵌入图片
        for img_info in page.get_images(full=True):
            try:
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                data = base_image["image"]
                ext = base_image["ext"]
                mime = _load_image_bytes(data, "." + ext)[1]
                info = {
                    "index": len(report["images"]) + 1,
                    "page": page_idx + 1,
                    "size": len(data),
                    "mime": mime,
                }
                if use_vision and len(report["images"]) < max_images:
                    img_path = _stage_image_for_host_window(
                        path.stem, info["index"], data, ext, Path.cwd())
                    info["staged_path"] = str(img_path)
                    info["pending_host"] = True
                    info["content"] = "[待宿主独立窗口识别：见任务卡]"
                else:
                    info["content"] = "[未识别（--no-vision 或超过上限）]"
                report["images"].append(info)
            except Exception as e:
                report["images"].append({"index": len(report["images"]) + 1, "page": page_idx + 1, "error": str(e)})

    doc.close()
    return report


# ============ 主流程 ============

def main() -> int:
    parser = argparse.ArgumentParser(description="完整文档读取器（防漏读嵌入图片）")
    parser.add_argument("file", help="docx 或 pdf 文件路径")
    parser.add_argument("--out", default="", help="输出 markdown 报告路径")
    parser.add_argument("--max-images", type=int, default=9999, help="最多识别前 N 张图片")
    parser.add_argument("--no-vision", action="store_true", help="不做独立窗口图片识别（仅列出图片）")
    parser.add_argument("--allow-vision-failure", action="store_true",
                        help="独立窗口识别未就绪时仍返回成功（仅供人工复核场景）")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在: {path}", file=sys.stderr)
        return 2

    load_project_env()
    use_vision = not args.no_vision
    suffix = path.suffix.lower()

    if suffix == ".docx":
        report = read_docx(path, use_vision, args.max_images)
    elif suffix == ".pdf":
        report = read_pdf(path, use_vision, args.max_images)
    else:
        print(f"不支持的文件类型: {suffix}（支持 .docx / .pdf）", file=sys.stderr)
        return 2

    # 独立窗口识别结论收集（verdict 存在且合规时合并进报告；须在报告行构建前完成）
    staged = [im for im in report["images"] if im.get("pending_host")]
    if staged:
        reviewed_by, descriptions = _collect_docread_verdict(Path.cwd(), path.stem)
        for im in staged:
            desc = descriptions.get(im["index"])
            if desc:
                im["content"] = desc
                im["pending_host"] = False

    # 输出
    lines = [f"# 文档读取报告: {path.name}", ""]
    lines.append(f"## 文本内容（{len(report['text'])} 段）")
    for t in report["text"]:
        lines.append(t)
        lines.append("")
    lines.append(f"## 嵌入图片（{len(report['images'])} 张）")
    if not report["images"]:
        lines.append("（无嵌入图片）")
    for img in report["images"]:
        page = f"（第{img.get('page')}页）" if img.get("page") else ""
        lines.append(f"### 图片 {img['index']}{page} [{img.get('mime', '?')} {img.get('size', 0)}B]")
        if "error" in img:
            lines.append(f"提取失败: {img['error']}")
        else:
            lines.append(img.get("content", "[无内容]"))
        lines.append("")

    still_pending = [im for im in report["images"] if im.get("pending_host")]
    if still_pending:
        card = _build_docread_task_card(path.stem, still_pending)
        card_path = Path.cwd() / TASK_DIR_NAME / f"docread_{path.stem}.task.md"
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_text(card, encoding="utf-8")
        lines.append(f"> ⛔ 识别任务卡已生成: {card_path}")
        lines.append("> 请派发宿主独立窗口（视觉审子代理/独立会话）按卡实际读图，"
                     f"回写 {TASK_DIR_NAME}/docread_{path.stem}.verdict.md 后重跑本命令合并。")

    output = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"报告已保存: {args.out}")
        # 同时打印摘要
        print(f"文本段数: {len(report['text'])}, 图片数: {len(report['images'])}")
    else:
        print(output)
    pending = any(im.get("pending_host") or im.get("vision_error") for im in report["images"])
    if pending and use_vision and not args.allow_vision_failure:
        print("独立窗口图片识别未就绪；报告已标记，停止后续自动判断。", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
