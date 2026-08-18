#!/usr/bin/env python3
"""
ACADEMIC-01 验收脚本
评估学术论文能力：结构完整性、内容质量、格式规范
"""

import os
import re
import json
import sys
from pathlib import Path


def evaluate_paper(workspace: str) -> dict:
    """评估论文"""
    results = {
        'structure': {'score': 0, 'max': 30, 'details': []},
        'content': {'score': 0, 'max': 40, 'details': []},
        'format': {'score': 0, 'max': 20, 'details': []},
        'academic': {'score': 0, 'max': 10, 'details': []},
    }
    
    # 检查论文文件
    paper_files = list(Path(workspace).glob('*.tex')) + list(Path(workspace).glob('*.md'))
    if not paper_files:
        results['structure']['details'].append('未找到论文文件')
        return results
    
    paper_content = ''
    for f in paper_files:
        with open(f, 'r', encoding='utf-8') as fp:
            paper_content += fp.read()
    
    # 1. 结构完整性评估 (30分)
    required_sections = ['摘要', '引言', '相关工作', '方法', '应用', '讨论', '结论']
    found_sections = sum(1 for s in required_sections if s in paper_content)
    section_score = (found_sections / len(required_sections)) * 20
    results['structure']['score'] = section_score
    results['structure']['details'].append(f'找到 {found_sections}/{len(required_sections)} 个必要章节')
    
    # 检查图表
    figures = re.findall(r'\\begin\{figure\}|!\[.*?\]\(.*?\)', paper_content)
    if len(figures) >= 3:
        results['structure']['score'] += 10
        results['structure']['details'].append(f'图表数量充足: {len(figures)}')
    else:
        results['structure']['score'] += len(figures) * 3
        results['structure']['details'].append(f'图表数量不足: {len(figures)}/3')
    
    # 2. 内容质量评估 (40分)
    # 检查方法覆盖
    methods = ['LIME', 'SHAP', 'Attention', 'Concept Bottleneck', '可解释性']
    method_count = sum(1 for m in methods if m.lower() in paper_content.lower())
    method_score = (method_count / len(methods)) * 20
    results['content']['score'] = method_score
    results['content']['details'].append(f'覆盖 {method_count}/{len(methods)} 个核心方法')
    
    # 检查应用案例
    cases = re.findall(r'应用案例|实际应用|案例研究|case study', paper_content, re.IGNORECASE)
    if len(cases) >= 3:
        results['content']['score'] += 20
        results['content']['details'].append(f'应用案例充足: {len(cases)}')
    else:
        results['content']['score'] += len(cases) * 7
        results['content']['details'].append(f'应用案例不足: {len(cases)}/3')
    
    # 3. 格式规范评估 (20分)
    # 检查参考文献
    refs = re.findall(r'\\cite\{.*?\}|\[.*?\]', paper_content)
    if len(refs) >= 15:
        results['format']['score'] += 10
        results['format']['details'].append(f'参考文献充足: {len(refs)}')
    else:
        results['format']['score'] += len(refs) * 0.67
        results['format']['details'].append(f'参考文献不足: {len(refs)}/15')
    
    # 检查LaTeX格式
    latex_commands = re.findall(r'\\section|\\subsection|\\begin|\\end', paper_content)
    if len(latex_commands) >= 10:
        results['format']['score'] += 10
        results['format']['details'].append('LaTeX格式规范')
    else:
        results['format']['score'] += len(latex_commands)
        results['format']['details'].append(f'LaTeX命令较少: {len(latex_commands)}')
    
    # 4. 学术规范评估 (10分)
    # 检查摘要
    if '摘要' in paper_content and 'abstract' in paper_content.lower():
        results['academic']['score'] += 5
        results['academic']['details'].append('包含中英文摘要')
    
    # 检查关键词
    if '关键词' in paper_content or 'keywords' in paper_content.lower():
        results['academic']['score'] += 5
        results['academic']['details'].append('包含关键词')
    
    # 计算总分
    total_score = sum(r['score'] for r in results.values())
    total_max = sum(r['max'] for r in results.values())
    
    return {
        'dimensions': results,
        'total_score': total_score,
        'total_max': total_max,
        'pass': total_score >= total_max * 0.7
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: evaluate.py <workspace>")
        sys.exit(1)
    
    workspace = sys.argv[1]
    results = evaluate_paper(workspace)
    
    print(json.dumps(results, ensure_ascii=False, indent=2))
    
    if results['pass']:
        print(f"\n✓ 通过: {results['total_score']}/{results['total_max']}")
    else:
        print(f"\n✗ 未通过: {results['total_score']}/{results['total_max']}")


if __name__ == '__main__':
    main()
