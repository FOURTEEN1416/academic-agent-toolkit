# -*- coding: utf-8 -*-
"""扫描并修复 Markdown 中"裸 LaTeX 块公式（缺 $$ 包围）"。

用法：
    python tools/fix_bare_latex_in_md.py <path/to/REPORT.md>          # 仅扫描报告
    python tools/fix_bare_latex_in_md.py <path/to/REPORT.md> --fix    # 自动包 $$

判定为"裸 LaTeX 块公式行"：
1. 当前行不在已有 $$...$$ 块内
2. 当前行不在 ```...``` 代码块内
3. 当前行不在 `inline code` 内
4. 当前行不被 $...$ 行内公式完整覆盖
5. 行内出现典型 LaTeX 命令（\tag / \\sqrt / \\hat / \frac / \\dot / \begin{ 等）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

LATEX_CMDS = (
    'tag|sqrt|hat|frac|tfrac|dfrac|dot|ddot|vec|widehat|widetilde|'
    'begin\\{(?:aligned|cases|bmatrix|pmatrix|matrix|equation|align)|'
    'cdot|pm|mp|in\\b|exists|forall|big|Big|bigg|Bigg|cap|cup|sum|prod|int|'
    'partial|nabla|infty|leq|geq|neq|approx|sim|propto|alpha|beta|gamma|'
    'delta|theta|lambda|mu|sigma|omega|phi|psi|varnothing|varepsilon|varphi'
)
PATTERN = re.compile('\\\\(' + LATEX_CMDS + ')')


def scan(text: str) -> list[tuple[int, str]]:
    """返回 (line_no, original_line_stripped) 的违规行列表。"""
    lines = text.split('\n')
    in_code = False
    in_dd = False
    bad = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        dd_count = stripped.count('$$')
        if dd_count == 1 and stripped == '$$':
            in_dd = not in_dd
            continue
        if dd_count >= 2 and stripped.startswith('$$') and stripped.endswith('$$'):
            continue
        if in_dd:
            continue
        line_no_inline = re.sub('`[^`\\n]+`', '', line)
        line_no_inline = re.sub('\\$[^\\n$]+\\$', '', line_no_inline)
        if not PATTERN.search(line_no_inline):
            continue
        has_tag = bool(re.search('\\\\tag\\{|\\\\begin\\{', line_no_inline))
        has_relation = bool(re.search('[=≤≥≠≈]|\\\\leq|\\\\geq|\\\\neq|\\\\approx', line_no_inline))
        starts_with_cmd = bool(re.match('^\\s*\\\\[a-zA-Z]+', line_no_inline))
        cmd_count = len(re.findall('\\\\[a-zA-Z]+', line_no_inline))
        if has_tag or starts_with_cmd or (has_relation and cmd_count >= 1) or cmd_count >= 3:
            bad.append((i, stripped[:90]))
    return bad


def fix(text: str) -> tuple[str, int]:
    """自动给违规行包上 $$ 块。返回 (新文本, 修复行数)。"""
    bad = scan(text)
    if not bad:
        return text, 0
    bad_lines = {ln for ln, _ in bad}
    lines = text.split('\n')
    new_lines = []
    for i, line in enumerate(lines, 1):
        if i in bad_lines:
            if new_lines and new_lines[-1].strip() != '':
                new_lines.append('')
            new_lines.append('$$')
            new_lines.append(line.strip())
            new_lines.append('$$')
            new_lines.append('')
        else:
            new_lines.append(line)
    return '\n'.join(new_lines), len(bad_lines)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    target = Path(sys.argv[1])
    if not target.exists():
        print(f'❌ 文件不存在: {target}')
        sys.exit(2)
    do_fix = '--fix' in sys.argv
    text = target.read_text(encoding='utf-8')
    bad = scan(text)
    if not bad:
        print(f'✓ {target}: 公式包围检查通过（{len(text.splitlines())} 行）')
        return
    print(f'❌ {target}: 发现 {len(bad)} 处裸 LaTeX（缺 $$ 包围）')
    for ln, s in bad[:20]:
        print(f'  L{ln}: {s}')
    if len(bad) > 20:
        print(f'  ... 还有 {len(bad) - 20} 处')
    if do_fix:
        new_text, n = fix(text)
        backup = target.with_suffix(target.suffix + '.bak')
        backup.write_text(text, encoding='utf-8')
        target.write_text(new_text, encoding='utf-8')
        print(f'\n✓ 已修复 {n} 行（原文件备份到 {backup.name}）')
        return
    print('\n（加 --fix 参数自动修复，会先备份到 .bak）')


if __name__ == '__main__':
    main()
