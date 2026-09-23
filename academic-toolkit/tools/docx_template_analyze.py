# -*- coding: utf-8 -*-
"""docx_template_analyze.py — 把用户上传的 .docx 模板转成可读结构清单。

输出 JSON：
- paragraphs: [{idx, text, style, kind}]   段落清单（kind=heading/normal/empty）
- tables: [{idx, rows, sample}]            表格清单（rows=行数, sample=部分内容）
- sections: 默认推断（title/abstract/body/references/appendix）
- language: 模板主语言推断（zh/en）

用法：
    python docx_template_analyze.py --template path/to/template.docx --output template_map.json

供 Claude SKILL 读取后输出准确的占位映射。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from docx import Document

W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

# 本文件是 academic-toolkit/tools/docx_template_analyze.pyc 的等源重建（原真码只在 pyc 里）。
# 为与 pyc 基准 stdout 逐字节一致，argparse 的 prog 固定为经 .pyc 启动时的名字。
PROG = Path(sys.argv[0]).stem + '.pyc'


def _para_text(p) -> str:
    """提取段落纯文本。"""
    parts = []
    for t in p._element.iter(f'{{{W_NS}}}t'):
        if t.text:
            parts.append(t.text)
    return ''.join(parts)


def _para_style(p) -> str:
    pStyle = p._element.find(f'.//{{{W_NS}}}pPr/{{{W_NS}}}pStyle')
    if pStyle is None:
        return ''
    return pStyle.get(f'{{{W_NS}}}val', '')


def _heading_level(style: str) -> int:
    m = re.match('Heading(\\d+)', style)
    if m:
        return int(m.group(1))
    if style == 'Title':
        return 1
    return 0


def analyze(template_path: Path) -> dict:
    if template_path.suffix.lower() == '.dotx':
        import sys as _sys
        _tools_dir = str(Path(__file__).resolve().parent)
        if _tools_dir not in _sys.path:
            _sys.path.insert(0, _tools_dir)
        from docx_template_fill import _convert_dotx_to_docx
        template_path = _convert_dotx_to_docx(template_path)
    doc = Document(str(template_path))
    body = doc.element.body
    para_idx = 0
    table_idx = 0
    full_text = []
    elements_data = []
    for el in body.iterchildren():
        tag = el.tag
        if tag.endswith('}sectPr'):
            continue
        if tag == f'{{{W_NS}}}p':
            from docx.text.paragraph import Paragraph as _P
            p = _P(el, doc)
            text = _para_text(p)
            style = _para_style(p)
            level = _heading_level(style)
            if not text.strip():
                kind = 'empty'
            elif level > 0:
                kind = 'heading'
            else:
                kind = 'normal'
            elements_data.append({
                'type': 'paragraph',
                'idx': para_idx,
                'text': text.strip(),
                'style': style,
                'level': level,
                'kind': kind,
            })
            para_idx += 1
            if text.strip():
                full_text.append(text)
            continue
        if tag == f'{{{W_NS}}}tbl':
            from docx.table import Table as _T
            tbl = _T(el, doc)
            rows = len(tbl.rows)
            cols = len(tbl.rows[0].cells) if rows else 0
            sample = []
            for r_idx, row in enumerate(tbl.rows[:3]):
                row_cells = [c.text.strip()[:40] for c in row.cells[:5]]
                sample.append(row_cells)
            elements_data.append({
                'type': 'table',
                'idx': table_idx,
                'rows': rows,
                'cols': cols,
                'sample': sample,
            })
            table_idx += 1
    full = ''.join(full_text)
    cn_chars = sum(1 for c in full if '\u4e00' <= c <= '\u9fff')
    language = 'zh' if cn_chars > len(full) * 0.2 else 'en'
    return {
        'language': language,
        'total_paragraphs': para_idx,
        'total_tables': table_idx,
        'elements': elements_data,
        'summary_for_claude': _build_summary(elements_data, language),
    }


def _build_summary(elements_data: list, language: str) -> str:
    """把元素清单转成给 Claude 看的可读摘要。"""
    lines = [f'=== 模板结构清单（语言：{language}）===\n']
    for el in elements_data:
        if el['type'] == 'table':
            lines.append(f"[表 {el['idx']}] {el['rows']} 行 × {el['cols']} 列")
            for ri, row in enumerate(el['sample']):
                lines.append(f'  行 {ri}: {row}')
            continue
        kind_marker = {
            'heading': f"H{el.get('level', 0)} ",
            'empty': '<空> ',
            'normal': '    ',
        }.get(el['kind'], '    ')
        text_preview = el['text'][:80] if el['text'] else ''
        style = f" [{el['style']}]" if el['style'] else ''
        lines.append(f"[段 {el['idx']:3}]{style} {kind_marker}{text_preview}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(prog=PROG, description='分析 .docx 模板的段落 / 表格结构')
    parser.add_argument('--template', '-t', type=Path, required=True)
    parser.add_argument('--output', '-o', type=Path, required=True, help='输出 JSON 路径')
    parser.add_argument('--summary', '-s', type=Path, default=None,
                        help='可选：输出可读摘要 .txt 路径（用于喂给 Claude）')
    args = parser.parse_args()

    result = analyze(args.template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'OK: analyzed → {args.output}')
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(result['summary_for_claude'], encoding='utf-8')
        print(f'     summary → {args.summary}')


if __name__ == '__main__':
    main()
