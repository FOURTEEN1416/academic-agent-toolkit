# -*- coding: utf-8 -*-
"""分析 LaTeX 模板（.tex/.cls/.sty）的关键格式参数。

提取：页边距 / 字号 / 行距 / 字体 / 段落间距 / 标题样式
用于：让 docx-export 在 Word 输出时近似还原 LaTeX 视觉效果

用法：
    python analyze_latex_template.py --input main.tex --output _derived_profile.json
    python analyze_latex_template.py --input thesis.cls --output _derived_profile.json
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# 本文件是 academic-toolkit/tools/analyze_latex_template.pyc 的等源重建（原真码只在 pyc 里）。
# 为与 pyc 基准 stdout 逐字节一致，argparse 的 prog 固定为经 .pyc 启动时的名字。
PROG = Path(sys.argv[0]).stem + '.pyc'

LATEX_SIZE_PT = {
    'tiny': 5,
    'scriptsize': 7,
    'footnotesize': 8,
    'small': 9,
    'normalsize': 10,
    'large': 12,
    'Large': 14,
    'LARGE': 17,
    'huge': 20,
    'Huge': 25,
    'zihao{0}': 42,
    'zihao{-0}': 36,
    'zihao{1}': 26,
    'zihao{-1}': 24,
    'zihao{2}': 22,
    'zihao{-2}': 18,
    'zihao{3}': 16,
    'zihao{-3}': 15,
    'zihao{4}': 14,
    'zihao{-4}': 12,
    'zihao{5}': 10.5,
    'zihao{-5}': 9,
    'zihao{6}': 7.5,
    'zihao{-6}': 6.5,
}

CTEX_FONT = {
    'songti': 'SimSun',
    'heiti': 'SimHei',
    'fangsong': 'FangSong',
    'kaishu': 'KaiTi',
    'lishu': 'LiSu',
    'youyuan': 'YouYuan',
    'fzxbsong': 'FZXiaoBiaoSong-B05',
    'fsgb': 'FangSong_GB2312',
    'ctexsong': 'SimSun',
    'ctexkai': 'KaiTi',
    'ctexhei': 'SimHei',
    'ctexfs': 'FangSong',
    'STSong': 'STSong',
    'STZhongsong': 'STZhongsong',
    'STHeiti': 'STHeiti',
    'STKaiti': 'STKaiti',
    'STFangsong': 'STFangsong',
}

DEFAULT_PROFILE = {
    'profile_name': 'LaTeX 模板派生样式',
    '_derived_from': 'latex-template',
    '_matched_items': [],
    'page': {'size': 'A4', 'margin_top_cm': 2.5, 'margin_bottom_cm': 2.5,
             'margin_left_cm': 2.5, 'margin_right_cm': 2.5},
    'fonts': {'chinese_heading': 'SimHei', 'chinese_body': 'SimSun',
              'latin': 'Times New Roman', 'monospace': 'Consolas'},
    'headings': {'level1_pt': 16, 'level2_pt': 14, 'level3_pt': 12, 'level4_pt': 11,
                 'bold': True, 'level1_alignment': 'center', 'level2_alignment': 'left',
                 'level3_alignment': 'left', 'level1_page_break_before': False,
                 'level2_page_break_before': False, 'level3_page_break_before': False},
    'body': {'font_size_pt': 12, 'line_spacing': 1.5, 'first_line_indent_chars': 2,
             'space_before_pt': 0, 'space_after_pt': 0},
    'title': {'font_size_pt': 18, 'bold': True, 'alignment': 'center', 'font_family': 'SimHei'},
    'table': {'top_border_pt': 1.5, 'header_border_pt': 0.75, 'bottom_border_pt': 1.5,
              'font_size_pt': 10.5, 'header_bold': True, 'cell_alignment': 'center'},
    'references': {'hanging_indent_cm': 0.74, 'font_size_pt': 10.5, 'numbering_style': 'bracket'},
    'image': {'max_width_cm': 14, 'alignment': 'center'},
    'code_block': {'font_size_pt': 9, 'line_spacing': 1.0, 'background_color': 'F5F5F5'},
}


def _read_tex(path: Path) -> str:
    """读取 .tex/.cls/.sty 文件，多编码 fallback。"""
    raw = path.read_bytes()
    for enc in ('utf-8', 'utf-8-sig', 'gbk', 'gb18030', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f'无法解码 {path}')


def _strip_comments(text: str) -> str:
    """去除 LaTeX 注释（行尾 % 后到换行）。"""
    out = []
    for line in text.split('\n'):
        i = 0
        while i < len(line):
            if line[i] == '%' and (i == 0 or line[i - 1] != '\\'):
                break
            i += 1
        out.append(line[:i])
    return '\n'.join(out)


def _len_to_cm(value: str, unit: str) -> float:
    """LaTeX 长度 → cm。"""
    try:
        v = float(value)
    except ValueError:
        return 0
    unit = unit.lower()
    if unit == 'cm':
        return v
    if unit == 'mm':
        return v / 10
    if unit == 'in':
        return v * 2.54
    if unit == 'pt':
        return v * 0.0352778
    if unit == 'em':
        return v * 0.42
    return 0


def _len_to_pt(value: str, unit: str) -> float:
    """LaTeX 长度 → pt。"""
    try:
        v = float(value)
    except ValueError:
        return 0
    unit = unit.lower()
    if unit == 'pt':
        return v
    if unit == 'cm':
        return v * 28.3465
    if unit == 'mm':
        return v * 2.83465
    if unit == 'in':
        return v * 72
    return 0


def analyze_latex_template(text: str) -> dict[str, Any]:
    """从 LaTeX 模板文本中提取格式参数。"""
    text = _strip_comments(text)
    profile = deepcopy(DEFAULT_PROFILE)
    matched = []
    geo_match = re.search('\\\\geometry\\s*\\{([^}]+)\\}', text)
    if geo_match:
        geo_body = geo_match.group(1)
        for key, scope in (('top', 'margin_top_cm'), ('bottom', 'margin_bottom_cm'),
                           ('left', 'margin_left_cm'), ('right', 'margin_right_cm')):
            m = re.search('\\b' + key + '\\s*=\\s*([\\d.]+)\\s*(cm|mm|in|pt)\\b', geo_body)
            if m:
                profile['page'][scope] = round(_len_to_cm(m.group(1), m.group(2)), 2)
                matched.append(f'页边距 {key}={profile["page"][scope]}cm')
    if 'a4paper' in text.lower() or 'A4' in text:
        profile['page']['size'] = 'A4'
        matched.append('纸张 A4')
    m = re.search('\\\\setmainfont\\s*\\{([^}]+)\\}', text)
    if m:
        profile['fonts']['latin'] = m.group(1).strip()
        matched.append(f'英文主字体 {m.group(1).strip()}')
    m = re.search('\\\\setCJKmainfont\\s*(?:\\[[^\\]]*\\])?\\s*\\{([^}]+)\\}', text)
    if m:
        font_name = m.group(1).strip()
        for cn_term, sys_name in {'宋体': 'SimSun', '黑体': 'SimHei', '仿宋': 'FangSong',
                                  '楷体': 'KaiTi', '微软雅黑': 'Microsoft YaHei'}.items():
            if cn_term in font_name:
                font_name = sys_name
                break
        profile['fonts']['chinese_body'] = font_name
        matched.append(f'中文主字体 {font_name}')
    m = re.search('\\\\@setfontsize\\\\?normalsize\\s*\\{([\\d.]+)\\}\\s*\\{([\\d.]+)\\}', text)
    if m:
        body_pt = float(m.group(1))
        baseline = float(m.group(2))
        profile['body']['font_size_pt'] = round(body_pt, 1)
        if body_pt > 0:
            profile['body']['line_spacing'] = round(baseline / body_pt, 2)
        matched.append(f'正文字号 {body_pt}pt 行距 {profile["body"]["line_spacing"]}x')
    else:
        cls_match = re.search('\\\\documentclass\\s*\\[([^\\]]*)\\]\\s*\\{[^}]+\\}', text)
        if cls_match:
            opts = cls_match.group(1)
            for sz in (10, 11, 12):
                if f'{sz}pt' in opts:
                    profile['body']['font_size_pt'] = sz
                    matched.append(f'正文字号 {sz}pt（来自 documentclass option）')
                    break
    m = re.search('\\\\renewcommand\\*?\\s*\\{?\\\\baselinestretch\\}?\\s*\\{([\\d.]+)\\}', text)
    if m:
        ls = float(m.group(1))
        profile['body']['line_spacing'] = round(ls, 2)
        matched.append(f'行距 {ls}x（baselinestretch）')
    m = re.search('\\\\linespread\\s*\\{([\\d.]+)\\}', text)
    if m:
        ls = float(m.group(1))
        profile['body']['line_spacing'] = round(ls, 2)
        matched.append(f'行距 {ls}x（linespread）')
    m = re.search('\\\\setlength\\\\?\\s*\\{?\\\\parindent\\}?\\s*\\{([\\d.]+)\\s*(em|cm|pt|mm)\\}', text)
    if m:
        v = float(m.group(1))
        unit = m.group(2).lower()
        if unit == 'em':
            profile['body']['first_line_indent_chars'] = int(round(v))
            matched.append(f'首行缩进 {int(round(v))} 字符')
        else:
            pt_val = _len_to_pt(m.group(1), unit)
            chars = int(round(pt_val / max(profile['body']['font_size_pt'], 12)))
            profile['body']['first_line_indent_chars'] = chars
            matched.append(f'首行缩进 {chars} 字符（{v}{unit}）')
    for level, tex_section in ((1, 'section'), (2, 'subsection'), (3, 'subsubsection')):
        m = re.search(
            '\\\\CTEXsetup\\s*\\[[^\\]]*format\\s*=\\s*\\{[^}]*\\\\zihao\\s*\\{(-?\\d+)\\}[^\\]]*\\]\\s*\\{'
            + tex_section + '\\}', text)
        if m:
            zh_num = m.group(1)
            zh_key = f'zihao{{{zh_num}}}'
            if zh_key in LATEX_SIZE_PT:
                profile['headings'][f'level{level}_pt'] = int(LATEX_SIZE_PT[zh_key])
                matched.append(f'H{level} 字号 zihao{{{zh_num}}} ≈ {LATEX_SIZE_PT[zh_key]}pt')
    m = re.search('\\\\titleformat\\s*\\{\\\\section\\}\\s*(?:\\[[^\\]]*\\])?\\s*\\{([^}]*)\\}', text)
    if m:
        fmt = m.group(1)
        zh_match = re.search('\\\\zihao\\s*\\{(-?\\d+)\\}', fmt)
        if zh_match:
            zh_key = f'zihao{{{zh_match.group(1)}}}'
            if zh_key in LATEX_SIZE_PT:
                profile['headings']['level1_pt'] = int(LATEX_SIZE_PT[zh_key])
                matched.append(f'H1 字号 {LATEX_SIZE_PT[zh_key]}pt（titleformat）')
    m = re.search('\\\\setlength\\\\?\\s*\\{?\\\\parskip\\}?\\s*\\{([\\d.]+)\\s*(pt|cm|em|mm)\\}', text)
    if m:
        pt_val = _len_to_pt(m.group(1), m.group(2))
        if pt_val > 0:
            profile['body']['space_after_pt'] = round(pt_val, 1)
            matched.append(f'段后距 {pt_val:.1f}pt')
    if 'gbt7714' in text or 'GBT7714' in text:
        profile['references']['numbering_style'] = 'bracket'
        matched.append('参考文献 GB/T 7714 格式')
    elif 'natbib' in text:
        matched.append('引用使用 natbib')
    if re.search('\\\\centering\\s*\\\\section', text) or 'center' in (
            geo_match.group(0) if geo_match else ''):
        profile['headings']['level1_alignment'] = 'center'
        matched.append('一级标题居中')
    cls_m = re.search('\\\\documentclass\\s*(?:\\[[^\\]]*\\])?\\s*\\{([^}]+)\\}', text)
    if cls_m:
        cls_name = cls_m.group(1).strip()
        matched.append(f'documentclass = {cls_name}')
        if 'cumcm' in cls_name.lower() or 'ctexart' in cls_name.lower():
            pass
        elif 'moderncv' in cls_name.lower() or 'scrartcl' in cls_name.lower():
            pass
    profile['_matched_items'] = matched
    return profile


def main():
    parser = argparse.ArgumentParser(prog=PROG, description='LaTeX 模板 → 样式 profile 派生器')
    parser.add_argument('--input', '-i', type=Path, required=True, help='输入 .tex/.cls/.sty 文件')
    parser.add_argument('--output', '-o', type=Path, required=True, help='输出 profile JSON 路径')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    if not args.input.exists():
        print(f'✗ 输入文件不存在: {args.input}', file=sys.stderr)
        sys.exit(1)
    if args.input.suffix.lower() not in ('.tex', '.cls', '.sty'):
        print(f'✗ 仅支持 .tex/.cls/.sty 格式，当前: {args.input.suffix}', file=sys.stderr)
        sys.exit(2)

    try:
        text = _read_tex(args.input)
        profile = analyze_latex_template(text)
    except Exception as e:
        print(f'✗ 派生失败: {e}', file=sys.stderr)
        sys.exit(3)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding='utf-8')

    matched = profile.get('_matched_items', [])
    print(f'✓ 已派生 profile: {args.output}')
    print(f'  关键参数: 正文 {profile["body"]["font_size_pt"]}pt / '
          f'行距 {profile["body"]["line_spacing"]}x / '
          f'H1 {profile["headings"]["level1_pt"]}pt')
    if matched:
        print(f'  从 LaTeX 模板识别到 {len(matched)} 项参数:')
        for m in matched[:10]:
            print(f'  - {m}')
        return
    print('  ⚠ 未识别出任何参数，使用默认 profile')


if __name__ == '__main__':
    main()
