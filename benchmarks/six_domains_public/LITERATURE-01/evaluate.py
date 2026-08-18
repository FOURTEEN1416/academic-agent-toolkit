#!/usr/bin/env python3
"""LITERATURE-01 验收脚本"""

import os
import re
import json
import sys
from pathlib import Path


def evaluate_literature(workspace: str) -> dict:
    """评估文献综述"""
    results = {
        'structure': {'score': 0, 'max': 30},
        'content': {'score': 0, 'max': 40},
        'format': {'score': 0, 'max': 20},
        'academic': {'score': 0, 'max': 10},
    }
    
    # 检查文件
    files = list(Path(workspace).glob('*.md')) + list(Path(workspace).glob('*.tex'))
    if not files:
        return {'dimensions': results, 'total_score': 0, 'total_max': 100, 'pass': False}
    
    content = ''
    for f in files:
        with open(f, 'r', encoding='utf-8') as fp:
            content += fp.read()
    
    # 结构
    sections = ['摘要', '引言', '方法', '应用', '讨论', '结论']
    found = sum(1 for s in sections if s in content)
    results['structure']['score'] = (found / len(sections)) * 30
    
    # 内容
    methods = ['FedAvg', 'Secure Aggregation', 'Differential Privacy', '联邦学习']
    method_count = sum(1 for m in methods if m in content)
    results['content']['score'] = (method_count / len(methods)) * 40
    
    # 格式
    refs = re.findall(r'\[.*?\]', content)
    results['format']['score'] = min(20, len(refs) * 1)
    
    # 学术
    if '摘要' in content:
        results['academic']['score'] += 5
    if '关键词' in content:
        results['academic']['score'] += 5
    
    total = sum(r['score'] for r in results.values())
    return {'dimensions': results, 'total_score': total, 'total_max': 100, 'pass': total >= 70}


def main():
    if len(sys.argv) < 2:
        print("Usage: evaluate.py <workspace>")
        sys.exit(1)
    
    results = evaluate_literature(sys.argv[1])
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n{'✓' if results['pass'] else '✗'} {results['total_score']}/{results['total_max']}")


if __name__ == '__main__':
    main()
