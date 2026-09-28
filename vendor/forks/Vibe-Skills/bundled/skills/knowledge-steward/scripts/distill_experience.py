#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
经验提炼脚本
从多个工作流报告中提炼经验、模式和最佳实践
"""

import os
import json
from collections import Counter, defaultdict
from typing import Dict, List, Any
from pathlib import Path
from parse_workflow_report import parse_multiple_reports


def distill_experience(reports_dir: str) -> Dict[str, Any]:
    """
    从多个报告中提炼经验

    Args:
        reports_dir: 报告目录路径

    Returns:
        提炼的经验总结
    """
    # 解析所有报告
    reports = parse_multiple_reports(reports_dir)

    if not reports:
        return {"error": "No reports found"}

    # 提取各类信息
    prompts = extract_all_prompts(reports)
    patterns = identify_patterns(reports)
    error_stats = analyze_errors(reports)
    best_practices = extract_best_practices(reports)
    anti_patterns = extract_anti_patterns(reports)

    # 生成经验总结
    summary = {
        'analysis_date': get_current_date(),
        'total_reports': len(reports),
        'date_range': get_date_range(reports),
        'top_prompts': rank_by_effectiveness(prompts)[:10],
        'common_patterns': patterns,
        'frequent_errors': error_stats,
        'best_practices': best_practices,
        'anti_patterns': anti_patterns,
        'metrics_summary': calculate_aggregate_metrics(reports)
    }

    return summary


def extract_all_prompts(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """提取所有用户提示词"""
    prompts = []

    for report in reports:
        user_prompts_section = report.get('user_prompts', '')
        if user_prompts_section:
            # 简单提取，实际可以更复杂
            prompt_lines = [line.strip() for line in user_prompts_section.split('\n') if line.strip()]
            for line in prompt_lines:
                if line and not line.startswith('#'):
                    prompts.append({
                        'text': line,
                        'report': report.get('file_path', ''),
                        'success': report.get('metrics', {}).get('success_rate', 0)
                    })

    return prompts


def rank_by_effectiveness(prompts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """根据成功率排序提示词"""
    # 按成功率排序
    sorted_prompts = sorted(prompts, key=lambda x: x.get('success', 0), reverse=True)

    # 去重并统计使用次数
    unique_prompts = {}
    for prompt in sorted_prompts:
        text = prompt['text']
        if text not in unique_prompts:
            unique_prompts[text] = {
                'text': text,
                'count': 1,
                'avg_success_rate': prompt['success']
            }
        else:
            unique_prompts[text]['count'] += 1

    return list(unique_prompts.values())


def identify_patterns(reports: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """识别重复出现的模式"""
    patterns = []
    pattern_texts = []

    for report in reports:
        patterns_section = report.get('patterns', '')
        if patterns_section:
            # 提取模式
            lines = patterns_section.split('\n')
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    pattern_texts.append(line.strip())

    # 统计频率
    pattern_counter = Counter(pattern_texts)

    # 返回出现2次以上的模式
    for pattern, count in pattern_counter.most_common():
        if count >= 2:
            patterns.append({
                'pattern': pattern,
                'frequency': count
            })

    return patterns


def analyze_errors(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """分析常见错误"""
    error_types = defaultdict(lambda: {'count': 0, 'solutions': []})

    for report in reports:
        errors_section = report.get('errors', '')
        if errors_section:
            # 简单的错误类型提取
            # 实际应该更复杂的解析
            if 'TypeError' in errors_section:
                error_types['TypeError']['count'] += 1
            if 'CORS' in errors_section:
                error_types['CORS']['count'] += 1
            if '类型错误' in errors_section:
                error_types['类型错误']['count'] += 1

    # 转换为列表
    error_stats = []
    for error_type, data in error_types.items():
        error_stats.append({
            'type': error_type,
            'count': data['count']
        })

    # 按频率排序
    error_stats.sort(key=lambda x: x['count'], reverse=True)

    return error_stats


def extract_best_practices(reports: List[Dict[str, Any]]) -> List[str]:
    """提取最佳实践"""
    practices = []

    for report in reports:
        insights_section = report.get('insights', '')
        if insights_section:
            lines = insights_section.split('\n')
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    practices.append(line.strip())

    # 去重
    return list(set(practices))


def extract_anti_patterns(reports: List[Dict[str, Any]]) -> List[str]:
    """提取反模式"""
    anti_patterns = []

    for report in reports:
        anti_patterns_section = report.get('anti_patterns', '')
        if anti_patterns_section:
            lines = anti_patterns_section.split('\n')
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    anti_patterns.append(line.strip())

    # 去重
    return list(set(anti_patterns))


def calculate_aggregate_metrics(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算聚合指标"""
    total_errors = 0
    total_iterations = 0
    success_rates = []
    total_steps = 0

    for report in reports:
        metrics = report.get('metrics', {})
        total_errors += metrics.get('total_errors', 0)
        total_iterations += metrics.get('iterations_count', 0)
        if 'success_rate' in metrics:
            success_rates.append(metrics['success_rate'])
        total_steps += metrics.get('workflow_steps_count', 0)

    return {
        'total_errors': total_errors,
        'avg_errors_per_report': total_errors / len(reports) if reports else 0,
        'total_iterations': total_iterations,
        'avg_iterations_per_report': total_iterations / len(reports) if reports else 0,
        'avg_success_rate': sum(success_rates) / len(success_rates) if success_rates else 0,
        'total_workflow_steps': total_steps,
        'avg_steps_per_report': total_steps / len(reports) if reports else 0
    }


def get_current_date() -> str:
    """获取当前日期"""
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d')


def get_date_range(reports: List[Dict[str, Any]]) -> Dict[str, str]:
    """获取报告的日期范围"""
    dates = []
    for report in reports:
        date = report.get('metadata', {}).get('date', '')
        if date:
            dates.append(date)

    if dates:
        return {
            'start': min(dates),
            'end': max(dates)
        }
    return {'start': '', 'end': ''}


def save_experience_summary(summary: Dict[str, Any], output_path: str):
    """保存经验总结"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python distill_experience.py <reports_dir>")
        sys.exit(1)

    reports_dir = sys.argv[1]

    if not os.path.isdir(reports_dir):
        print(f"Error: {reports_dir} is not a valid directory")
        sys.exit(1)

    # 提炼经验
    summary = distill_experience(reports_dir)

    # 保存结果
    output_path = os.path.join(reports_dir, 'experience_summary.json')
    save_experience_summary(summary, output_path)

    print(f"Experience summary saved to {output_path}")
    print(f"\nSummary:")
    print(f"- Total reports analyzed: {summary.get('total_reports', 0)}")
    print(f"- Top prompts identified: {len(summary.get('top_prompts', []))}")
    print(f"- Common patterns: {len(summary.get('common_patterns', []))}")
    print(f"- Frequent errors: {len(summary.get('frequent_errors', []))}")
