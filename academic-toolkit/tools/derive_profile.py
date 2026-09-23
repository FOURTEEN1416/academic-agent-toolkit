# -*- coding: utf-8 -*-
"""从用户上传的 docx 模板派生样式 profile（供 docx_export 使用）。

用法：
    python derive_profile.py --input user_template.docx --output derived_profile.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# 本文件是 academic-toolkit/tools/derive_profile.pyc 的等源重建（原真码只在 pyc 里）。
# 原工具经 .pyc 启动，argparse 的 prog 取脚本名；为与 pyc 基准 stdout 逐字节一致，
# 显式把 prog 固定为经 .pyc 启动时的名字（对 .py / .pyc 调用均解析为同一个名字）。
PROG = Path(sys.argv[0]).stem + '.pyc'



def derive_profile_from_docx(template_path: Path) -> dict[str, Any]:
    """读取 docx 模板，分析其样式，返回 docx_export 兼容的 profile 字典。

    采用 analyze_docx.py 的统计方法：扫描每段文字的字体/字号/对齐/缩进/行距，
    取最常见值作为代表性样式。
    """
    from docx import Document

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from analyze_docx import aggregate_styles

    doc = Document(str(template_path))
    styles = aggregate_styles(doc)
    section = doc.sections[0]
    page_top_cm = round(section.top_margin.cm if section.top_margin else 2.5, 2)
    page_bottom_cm = round(section.bottom_margin.cm if section.bottom_margin else 2.5, 2)
    page_left_cm = round(section.left_margin.cm if section.left_margin else 2.5, 2)
    page_right_cm = round(section.right_margin.cm if section.right_margin else 2.5, 2)

    DEFAULT_BODY_PT = 12
    DEFAULT_HEADING1_PT = 16
    DEFAULT_HEADING2_PT = 14
    DEFAULT_HEADING3_PT = 12
    DEFAULT_LINE_SPACING = 1.5
    DEFAULT_INDENT_CHARS = 2
    DEFAULT_FONT_CN_BODY = 'SimSun'
    DEFAULT_FONT_CN_HEADING = 'SimHei'
    DEFAULT_FONT_LATIN = 'Times New Roman'

    body_style = styles.get('body_cn') or {}
    heading1 = styles.get('heading1') or {}
    heading2 = styles.get('heading2') or {}
    heading3 = styles.get('heading3') or {}
    references = styles.get('references_body') or {}

    body_size = body_style.get('size_pt') or DEFAULT_BODY_PT
    h1_size = heading1.get('size_pt') or DEFAULT_HEADING1_PT
    h2_size = heading2.get('size_pt') or DEFAULT_HEADING2_PT
    h3_size = heading3.get('size_pt') or DEFAULT_HEADING3_PT
    line_spacing = body_style.get('line_spacing') or DEFAULT_LINE_SPACING
    indent_pt = body_style.get('first_line_indent_pt') or 0
    indent_chars = round(indent_pt / max(body_size, 12)) if indent_pt > 0 else DEFAULT_INDENT_CHARS
    chinese_body = body_style.get('font') or DEFAULT_FONT_CN_BODY
    chinese_heading = heading1.get('font') or (heading2.get('font') or DEFAULT_FONT_CN_HEADING)
    h1_align = heading1.get('alignment') or 'center'
    h2_align = heading2.get('alignment') or 'left'
    h3_align = heading3.get('alignment') or 'left'
    h1_pagebreak = bool(heading1.get('page_break_before', False))
    space_before = body_style.get('space_before_pt') or 0
    space_after = body_style.get('space_after_pt') or 0

    profile = {
        'profile_name': f'自定义样式（来源：{template_path.name}）',
        '_derived_from': template_path.name,
        'page': {
            'size': 'A4',
            'margin_top_cm': page_top_cm,
            'margin_bottom_cm': page_bottom_cm,
            'margin_left_cm': page_left_cm,
            'margin_right_cm': page_right_cm,
        },
        'fonts': {
            'chinese_heading': chinese_heading,
            'chinese_body': chinese_body,
            'latin': DEFAULT_FONT_LATIN,
            'monospace': 'Consolas',
        },
        'headings': {
            'level1_pt': int(h1_size) if isinstance(h1_size, (int, float)) else DEFAULT_HEADING1_PT,
            'level2_pt': int(h2_size) if isinstance(h2_size, (int, float)) else DEFAULT_HEADING2_PT,
            'level3_pt': int(h3_size) if isinstance(h3_size, (int, float)) else DEFAULT_HEADING3_PT,
            'level4_pt': 11,
            'bold': True,
            'level1_alignment': h1_align,
            'level2_alignment': h2_align,
            'level3_alignment': h3_align,
            'level1_page_break_before': h1_pagebreak,
            'level2_page_break_before': False,
            'level3_page_break_before': False,
        },
        'body': {
            'font_size_pt': int(body_size) if isinstance(body_size, (int, float)) else DEFAULT_BODY_PT,
            'line_spacing': float(line_spacing) if isinstance(line_spacing, (int, float)) else DEFAULT_LINE_SPACING,
            'first_line_indent_chars': indent_chars,
            'space_before_pt': float(space_before),
            'space_after_pt': float(space_after),
        },
        'title': {
            'font_size_pt': 18,
            'bold': True,
            'alignment': 'center',
            'font_family': chinese_heading,
        },
        'table': {
            'top_border_pt': 1.5,
            'header_border_pt': 0.75,
            'bottom_border_pt': 1.5,
            'font_size_pt': 10.5,
            'header_bold': True,
            'cell_alignment': 'center',
        },
        'references': {
            'hanging_indent_cm': 0.74,
            'font_size_pt': references.get('size_pt') or 10.5,
            'numbering_style': 'bracket',
        },
        'image': {
            'max_width_cm': 14,
            'alignment': 'center',
        },
        'code_block': {
            'font_size_pt': 9,
            'line_spacing': 1.0,
            'background_color': 'F5F5F5',
        },
    }
    return profile


def main():
    parser = argparse.ArgumentParser(prog=PROG, description='从 docx 模板派生样式 profile')
    parser.add_argument('--input', '-i', type=Path, required=True, help='用户上传的 docx 模板')
    parser.add_argument('--output', '-o', type=Path, required=True, help='输出 profile JSON 路径')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    if not args.input.exists():
        print(f'✗ 模板文件不存在: {args.input}', file=sys.stderr)
        sys.exit(1)
    if args.input.suffix.lower() != '.docx':
        print(f'✗ 仅支持 .docx 格式，当前: {args.input.suffix}', file=sys.stderr)
        sys.exit(2)

    try:
        profile = derive_profile_from_docx(args.input)
    except Exception as e:
        print(f'✗ 派生失败: {e}', file=sys.stderr)
        sys.exit(3)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'✓ 已派生 profile: {args.output}')
    print(f'  关键参数: H1={profile["headings"]["level1_pt"]}pt / '
          f'正文={profile["body"]["font_size_pt"]}pt / '
          f'行距={profile["body"]["line_spacing"]}x / '
          f'缩进={profile["body"]["first_line_indent_chars"]} 字符')


if __name__ == '__main__':
    main()
