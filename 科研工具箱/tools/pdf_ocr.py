#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_ocr.py — PDF 拆图 + OCR 兜底工具
用途：把 PDF 拆成 PNG，再用 OCR 提取文字
适用：Read 工具无法读 PDF 文本层时（如扫描版 PDF）
作者：QwenPaw 数模竞赛工具集

增强（2026-06-05）：自动探测 tesseract 路径，支持 Windows 默认安装位置
"""

import sys
import os
from pathlib import Path


# 自动探测 tesseract 路径（避免 PATH 没配）
TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/opt/homebrew/bin/tesseract",
]


def find_tesseract() -> str:
    """自动找 tesseract 二进制路径"""
    import shutil
    found = shutil.which("tesseract")
    if found:
        return found
    for cand in TESSERACT_CANDIDATES:
        if Path(cand).exists():
            return cand
    return ""


def split_pdf_to_images(pdf_path: str, output_dir: str = None) -> list:
    """
    把 PDF 拆成 PNG 图片
    返回：图片路径列表
    """
    try:
        import pdfplumber
    except ImportError:
        print("[FAIL] pdfplumber 未安装。运行: pip install pdfplumber")
        return []

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"[FAIL] 文件不存在: {pdf_path}")
        return []

    if output_dir is None:
        output_dir = pdf_path.parent / f".tmp_{pdf_path.stem}_pages"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_paths = []
    with pdfplumber.open(pdf_path) as pdf:
        print(f"[INFO] PDF 总页数: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages, 1):
            # 渲染为高 DPI PNG
            img = page.to_image(resolution=200)
            out_path = output_dir / f"page_{i:03d}.png"
            img.save(str(out_path), format="PNG")
            image_paths.append(str(out_path))
            print(f"  [OK] 第 {i} 页 -> {out_path.name}")

    print(f"[DONE] 共拆出 {len(image_paths)} 张图片，目录: {output_dir}")
    return image_paths


def ocr_image(image_path: str, lang: str = "chi_sim+eng") -> str:
    """
    对单张图片做 OCR
    lang: chi_sim+eng（中文+英文）/ eng（仅英文）
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        print("[FAIL] pytesseract / Pillow 未安装")
        print("       pip install pytesseract Pillow")
        return ""

    # 自动探测 tesseract 路径
    tesseract_path = find_tesseract()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    else:
        print("[WARN] 未找到 tesseract 二进制，OCR 会失败")
        print("       Windows: winget install tesseract-ocr.tesseract")
        print("       macOS:   brew install tesseract tesseract-lang")
        print("       Ubuntu:  sudo apt install tesseract-ocr tesseract-ocr-chi-sim")

    try:
        text = pytesseract.image_to_string(
            Image.open(image_path), lang=lang, config="--psm 6"
        )
        return text
    except Exception as e:
        print(f"[FAIL] OCR 失败: {e}")
        return ""


def batch_ocr(image_paths: list, output_file: str = None, lang: str = "chi_sim+eng") -> str:
    """
    批量 OCR 多张图片，合并输出
    """
    all_text = []
    for i, img_path in enumerate(image_paths, 1):
        print(f"[OCR] 第 {i}/{len(image_paths)} 张: {Path(img_path).name}")
        text = ocr_image(img_path, lang=lang)
        all_text.append(f"\n===== Page {i} =====\n{text}")

    full_text = "\n".join(all_text)

    if output_file:
        Path(output_file).write_text(full_text, encoding="utf-8")
        print(f"[DONE] OCR 结果已保存: {output_file}")
        print(f"       总字符数: {len(full_text)}")

    return full_text


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "/?"):
        print("用法:")
        print("  python pdf_ocr.py <pdf_path> [--ocr] [--out <txt_path>]")
        print()
        print("示例:")
        print("  python pdf_ocr.py 题目.pdf                    # 只拆图")
        print("  python pdf_ocr.py 题目.pdf --ocr              # 拆图 + OCR")
        print("  python pdf_ocr.py 题目.pdf --ocr --out text.txt")
        sys.exit(0 if sys.argv[1:2] == ["--help"] else 1)

    pdf_path = sys.argv[1]
    do_ocr = "--ocr" in sys.argv
    out_path = None
    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]

    # 1. 拆图
    images = split_pdf_to_images(pdf_path)
    if not images:
        sys.exit(1)

    # 2. OCR（可选）
    if do_ocr:
        if out_path is None:
            out_path = Path(pdf_path).with_suffix(".ocr.txt")
        batch_ocr(images, output_file=out_path)


if __name__ == "__main__":
    main()
