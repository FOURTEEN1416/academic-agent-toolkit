#!/usr/bin/env python3
"""citation_checker.py — GB/T 7714 参考文献格式检查 + 引用完整性检查
供 citation-check / check-citations 技能使用。

用法:
    python citation_checker.py references.bib              # 检查 bib 文件
    python citation_checker.py paper.md                    # 检查论文中的引用
    python citation_checker.py references.bib --json       # JSON 输出
    python citation_checker.py references.bib --verbose    # 详细输出
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path


def check_bibtex(content: str) -> list[dict]:
    """检查 BibTeX 条目的格式规范（GB/T 7714 相关）"""
    issues = []
    entries = list(re.finditer(r'@(\w+)\s*\{\s*([^,]+),', content))
    if not entries:
        return [{"severity": "error", "line": 0, "msg": "未找到 BibTeX 条目"}]

    for i, match in enumerate(entries):
        etype, key = match.groups()
        # 检查必需字段
        entry_start = match.start()
        entry_block = content[entry_start:entry_start + 2000]
        has_title = 'title' in entry_block
        has_author = 'author' in entry_block
        has_year = 'year' in entry_block

        if not has_title:
            issues.append({"severity": "error", "line": i + 1, "msg": f"条目 {key}: 缺 title"})
        if not has_author:
            issues.append({"severity": "warning", "line": i + 1, "msg": f"条目 {key}: 缺 author"})
        if not has_year:
            issues.append({"severity": "warning", "line": i + 1, "msg": f"条目 {key}: 缺 year"})

        # 类型检查
        valid_types = {'article', 'book', 'inproceedings', 'conference', 'thesis',
                       'phdthesis', 'mastersthesis', 'misc', 'techreport', 'incollection'}
        if etype.lower() not in valid_types:
            issues.append({"severity": "warning", "line": i + 1, "msg": f"条目 {key}: 类型 @{etype} 非常见类型"})

    return issues


def check_markdown_refs(content: str) -> list[dict]:
    """检查 Markdown 论文中的引用完整性（[1] 引用 vs 参考文献列表）"""
    issues = []
    # 提取正文引用
    in_text = set()
    for m in re.finditer(r'\[(\d+(?:[,\-]\d+)*)\]', content):
        for part in m.group(1).split(','):
            if '-' in part:
                a, b = part.split('-')
                in_text.update(range(int(a), int(b) + 1))
            else:
                in_text.add(int(part))

    # 提取参考文献列表
    ref_section = re.search(r'#+\s*参考文献.*?(?=\n#|\Z)', content, re.DOTALL)
    if not ref_section:
        return [{"severity": "info", "line": 0, "msg": "未找到参考文献章节，跳过完整性检查"}]

    ref_text = ref_section.group(0)
    ref_nums = set()
    for m in re.finditer(r'\[(\d+)\]', ref_text):
        ref_nums.add(int(m.group(1)))

    # 正文引用了但参考文献没有
    dangling = in_text - ref_nums
    for r in sorted(dangling):
        issues.append({"severity": "error", "line": 0,
                       "msg": f"断链引用: 正文引用 [{r}] 但参考文献列表无此条目"})

    # 参考文献有但正文没引用
    unused = ref_nums - in_text
    for r in sorted(unused):
        issues.append({"severity": "warning", "line": 0,
                       "msg": f"未引用文献: 参考文献 [{r}] 未被正文引用"})

    # 检查连续性
    if in_text:
        max_ref = max(in_text)
        missing = [n for n in range(1, max_ref + 1) if n not in in_text and n not in ref_nums]
        if missing:
            issues.append({"severity": "warning", "line": 0,
                           "msg": f"引用跳跃: 缺 [{', '.join(map(str, missing))}]"})

    return issues


def main():
    parser = argparse.ArgumentParser(description='GB/T 7714 参考文献检查')
    parser.add_argument('input', help='输入文件（.bib 或 .md）')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"错误: 文件不存在 {args.input}")
        sys.exit(1)

    content = path.read_text(encoding='utf-8', errors='ignore')
    issues = []

    if path.suffix.lower() == '.bib':
        issues = check_bibtex(content)
    elif path.suffix.lower() in ('.md', '.markdown'):
        issues = check_markdown_refs(content)
    else:
        # 自动检测
        if '@' in content and 'title' in content:
            issues = check_bibtex(content)
        else:
            issues = check_markdown_refs(content)

    errors = [i for i in issues if i['severity'] == 'error']
    warnings = [i for i in issues if i['severity'] == 'warning']
    infos = [i for i in issues if i['severity'] == 'info']

    if args.json:
        print(json.dumps({
            "total": len(issues), "errors": len(errors), "warnings": len(warnings),
            "issues": issues,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"引用检查完成: 共 {len(issues)} 个问题 ({len(errors)} 错误, {len(warnings)} 警告)")
        if args.verbose:
            for issue in issues:
                level = {'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}.get(issue['severity'], '•')
                print(f"  {level} {issue['msg']}")

    # 退出码: 有错误返回 1
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
