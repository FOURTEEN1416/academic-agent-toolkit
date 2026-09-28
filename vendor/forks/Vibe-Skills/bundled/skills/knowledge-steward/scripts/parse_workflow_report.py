#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流报告解析脚本
解析autonomous-builder和commit-with-reflection生成的工作流报告
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any


def parse_workflow_report(report_path: str) -> Dict[str, Any]:
    """
    解析工作流报告

    Args:
        report_path: 报告文件路径

    Returns:
        提取的结构化数据
    """
    if not os.path.exists(report_path):
        raise FileNotFoundError(f"Report not found: {report_path}")

    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    extracted = {
        'metadata': extract_metadata(content),
        'user_prompts': extract_section(content, '用户需求与提示词'),
        'workflow_steps': extract_section(content, '工作流记录'),
        'decisions': extract_section(content, '决策点'),
        'errors': extract_section(content, '遇到的错误'),
        'insights': extract_section(content, '核心洞察'),
        'patterns': extract_section(content, '可复用模式'),
        'anti_patterns': extract_section(content, '应避免的反模式'),
        'metrics': extract_metrics(content)
    }

    return extracted


def extract_metadata(content: str) -> Dict[str, str]:
    """提取报告元数据"""
    metadata = {}

    # 提取日期
    date_match = re.search(r'\*\*日期\*\*:\s*(.+)', content)
    if date_match:
        metadata['date'] = date_match.group(1).strip()

    # 提取报告类型
    type_match = re.search(r'\*\*报告类型\*\*:\s*(.+)', content)
    if type_match:
        metadata['report_type'] = type_match.group(1).strip()

    # 提取提交类型
    commit_match = re.search(r'\*\*提交类型\*\*:\s*(.+)', content)
    if commit_match:
        metadata['commit_type'] = commit_match.group(1).strip()

    # 提取会话时长
    duration_match = re.search(r'\*\*会话时长\*\*:\s*(\d+)\s*分钟', content)
    if duration_match:
        metadata['duration'] = int(duration_match.group(1))

    return metadata


def extract_section(content: str, section_name: str) -> str:
    """提取指定章节的内容"""
    # 匹配章节标题
    pattern = rf'##\s+\d+\.\s+{re.escape(section_name)}(.*?)(?=##\s+\d+\.|---|\Z)'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        section_content = match.group(1).strip()
        return section_content

    return ""


def extract_metrics(content: str) -> Dict[str, Any]:
    """提取指标数据"""
    metrics = {}

    # 提取各项指标
    patterns = {
        'total_errors': r'总错误数:\s*(\d+)',
        'critical_errors': r'严重错误数:\s*(\d+)',
        'iterations_count': r'调试迭代次数:\s*(\d+)',
        'success_rate': r'成功率:\s*(\d+)%',
        'lines_added': r'\+(\d+)',
        'lines_deleted': r'-(\d+)\s*行',
        'workflow_steps_count': r'工作流步骤数:\s*(\d+)',
        'decision_points_count': r'决策点数:\s*(\d+)'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            metrics[key] = int(match.group(1))

    return metrics


def parse_multiple_reports(reports_dir: str) -> List[Dict[str, Any]]:
    """
    解析目录中的所有报告

    Args:
        reports_dir: 报告目录路径

    Returns:
        所有报告的解析结果列表
    """
    reports = []
    reports_path = Path(reports_dir)

    # 递归查找所有.md文件
    for md_file in reports_path.rglob('*.md'):
        # 跳过INDEX.md和模板文件
        if md_file.name == 'INDEX.md' or 'template' in md_file.name.lower():
            continue

        try:
            report_data = parse_workflow_report(str(md_file))
            report_data['file_path'] = str(md_file)
            reports.append(report_data)
        except Exception as e:
            print(f"Error parsing {md_file}: {e}")

    return reports


def save_parsed_data(reports: List[Dict[str, Any]], output_path: str):
    """保存解析后的数据为JSON"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parse_workflow_report.py <report_path_or_dir>")
        sys.exit(1)

    input_path = sys.argv[1]

    if os.path.isfile(input_path):
        # 解析单个文件
        result = parse_workflow_report(input_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif os.path.isdir(input_path):
        # 解析目录中的所有报告
        results = parse_multiple_reports(input_path)
        output_path = os.path.join(input_path, 'parsed_reports.json')
        save_parsed_data(results, output_path)
        print(f"Parsed {len(results)} reports. Saved to {output_path}")
    else:
        print(f"Error: {input_path} is not a valid file or directory")
        sys.exit(1)
