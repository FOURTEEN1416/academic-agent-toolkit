# Workflow Recording Guide

## 概述

本文档详细说明autonomous-builder如何记录工作流并生成报告。

## 工作流日志记录

### 何时记录

在Builder Agent的每个会话中，从Step 1开始到Step 7结束，持续记录：
- 用户提示词和需求
- 执行的每个步骤
- 使用的工具和文件
- 做出的决策及理由
- 遇到的错误和解决方案

### 日志文件位置

`.builder/workflow-log.json`

### 日志结构

```json
{
  "session_id": "session-YYYY-MM-DD-NNN",
  "feature_id": "feat-XXX",
  "start_time": "ISO-8601 timestamp",
  "end_time": "ISO-8601 timestamp",
  "user_prompts": [],
  "workflow_steps": [],
  "decisions": [],
  "errors": []
}
```

## 报告生成流程 (Step 8)

### 1. 检查配置

```python
def should_generate_report():
    # 检查项目级配置
    if not os.path.exists('.claude-workflows.yaml'):
        return False

    config = load_yaml('.claude-workflows.yaml')
    if not config.get('enabled', False):
        return False

    if not config.get('skills', {}).get('autonomous-builder', {}).get('workflow_reporting', False):
        return False

    return True
```

### 2. 读取工作流日志

```python
def load_workflow_log():
    log_path = '.builder/workflow-log.json'
    if not os.path.exists(log_path):
        return None

    with open(log_path, 'r', encoding='utf-8') as f:
        return json.load(f)
```

### 3. 加载模板

优先级顺序：
1. `docs/workflows/templates/unified-template.md` (项目本地)
2. `~/.claude/skills/shared-templates/unified-workflow-report.md` (全局)

```python
def load_template():
    local_template = 'docs/workflows/templates/unified-template.md'
    global_template = os.path.expanduser('~/.claude/skills/shared-templates/unified-workflow-report.md')

    if os.path.exists(local_template):
        return read_file(local_template)
    elif os.path.exists(global_template):
        return read_file(global_template)
    else:
        raise FileNotFoundError("Unified template not found")
```

### 4. 填充模板

```python
def fill_template(template, workflow_log, feature_info):
    # 基本信息
    replacements = {
        '{DATE}': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '{REPORT_TYPE}': 'workflow',
        '{COMMIT_TYPE}': feature_info.get('type', 'feature'),
        '{DURATION}': calculate_duration(workflow_log),
        '{FILE_COUNT}': len(workflow_log.get('files_modified', [])),

        # 第1章：概述
        '{SUMMARY}': generate_summary(workflow_log, feature_info),

        # 第2章：用户需求与提示词
        '{USER_REQUIREMENTS}': format_user_requirements(workflow_log),
        '{KEY_PROMPTS}': format_key_prompts(workflow_log),

        # 第3章：工作流记录
        '{WORKFLOW_STEPS}': format_workflow_steps(workflow_log),
        '{DECISION_POINTS}': format_decisions(workflow_log),
        '{TOOLS_USED}': format_tools_used(workflow_log),

        # 第4章：修改内容
        '{FILE_LIST}': format_file_list(workflow_log),
        '{CHANGES_LIST}': format_changes(workflow_log),

        # 第5章：遇到的错误
        '{ERRORS_SECTION}': format_errors(workflow_log),

        # 第6章：根本原因分析
        '{ROOT_CAUSE_WHY}': analyze_root_cause_why(workflow_log),
        '{ROOT_CAUSE_WHAT_LED}': analyze_root_cause_what_led(workflow_log),

        # 第7章：调试过程
        '{INVESTIGATION_STEPS}': format_investigation_steps(workflow_log),
        '{ITERATIONS}': format_iterations(workflow_log),
        '{INVESTIGATION_TIME}': calculate_investigation_time(workflow_log),
        '{IMPLEMENTATION_TIME}': calculate_implementation_time(workflow_log),
        '{TESTING_TIME}': calculate_testing_time(workflow_log),

        # 第8章：经验总结
        '{KEY_INSIGHTS}': generate_key_insights(workflow_log),
        '{PREVENTION_STRATEGIES}': generate_prevention_strategies(workflow_log),
        '{BEST_PRACTICES}': identify_best_practices(workflow_log),

        # 第9章：知识提炼
        '{REUSABLE_PATTERNS}': identify_reusable_patterns(workflow_log),
        '{ANTI_PATTERNS}': identify_anti_patterns(workflow_log),
        '{CHECKLIST}': generate_checklist(workflow_log),

        # 第10章：测试与验证
        '{TEST_CASES}': format_test_cases(workflow_log),
        '{VERIFICATION_STEPS}': format_verification_steps(workflow_log),

        # 第11章：参考资料
        '{REFERENCES}': generate_references(workflow_log),

        # 第12章：指标
        '{TOTAL_ERRORS}': len(workflow_log.get('errors', [])),
        '{CRITICAL_ERRORS}': count_critical_errors(workflow_log),
        '{ITERATIONS_COUNT}': count_iterations(workflow_log),
        '{SUCCESS_RATE}': calculate_success_rate(workflow_log),
        '{LINES_ADDED}': workflow_log.get('lines_added', 0),
        '{LINES_DELETED}': workflow_log.get('lines_deleted', 0),
        '{WORKFLOW_STEPS_COUNT}': len(workflow_log.get('workflow_steps', [])),
        '{DECISION_POINTS_COUNT}': len(workflow_log.get('decisions', [])),

        # 元数据
        '{SKILL_NAME}': 'autonomous-builder',
        '{VERSION}': '1.0.0',
        '{REPORT_ID}': generate_report_id()
    }

    report = template
    for key, value in replacements.items():
        report = report.replace(key, str(value))

    return report
```

### 5. 保存报告

```python
def save_report(report, feature_info):
    # 生成文件名
    date = datetime.now()
    year_month = date.strftime('%Y-%m')
    day = date.strftime('%d')
    category = feature_info.get('type', 'feature')
    desc = feature_info.get('short_desc', 'unnamed')

    filename = f"{day}_workflow_{category}_{desc}.md"
    dir_path = f"docs/workflows/{year_month}"
    file_path = f"{dir_path}/{filename}"

    # 确保目录存在
    os.makedirs(dir_path, exist_ok=True)

    # 写入文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(report)

    return file_path
```

### 6. 更新索引

```python
def update_index():
    # 扫描所有报告
    reports = scan_all_reports('docs/workflows')

    # 生成统计信息
    stats = generate_statistics(reports)

    # 生成索引内容
    index_content = render_index_template(reports, stats)

    # 写入INDEX.md
    with open('docs/workflows/INDEX.md', 'w', encoding='utf-8') as f:
        f.write(index_content)
```

## 详细度控制

根据配置的`detail_level`调整记录详细程度：

### detailed (详细模式)
- 记录所有工具调用
- 记录所有文件操作
- 记录所有决策过程
- 记录完整的错误堆栈

### normal (普通模式)
- 记录关键工具调用
- 记录主要文件修改
- 记录重要决策
- 记录错误摘要

### minimal (精简模式)
- 仅记录步骤概要
- 仅记录最终文件列表
- 仅记录关键决策
- 仅记录错误类型

## 格式化函数示例

### format_workflow_steps

```python
def format_workflow_steps(workflow_log):
    steps = workflow_log.get('workflow_steps', [])
    if not steps:
        return "无记录的步骤"

    formatted = []
    for step in steps:
        formatted.append(f"{step['step']}. **{step['action']}**")
        formatted.append(f"   - 工具: {step['tool']}")
        if step.get('files'):
            formatted.append(f"   - 文件: {', '.join(step['files'])}")
        formatted.append(f"   - 耗时: {step['duration_seconds']}秒")
        formatted.append("")

    return "\n".join(formatted)
```

### format_decisions

```python
def format_decisions(workflow_log):
    decisions = workflow_log.get('decisions', [])
    if not decisions:
        return "无重要决策记录"

    formatted = []
    for decision in decisions:
        formatted.append(f"### {decision['point']}")
        formatted.append(f"**可选方案**: {', '.join(decision['options'])}")
        formatted.append(f"**选择**: {decision['chosen']}")
        formatted.append(f"**理由**: {decision['reason']}")
        formatted.append("")

    return "\n".join(formatted)
```

### format_errors

```python
def format_errors(workflow_log):
    errors = workflow_log.get('errors', [])
    if not errors:
        return "本次会话未遇到错误"

    formatted = []
    for i, error in enumerate(errors, 1):
        formatted.append(f"### 错误 {i}: {error['type']}")
        formatted.append(f"**严重程度**: {error.get('severity', '中等')}")
        formatted.append(f"**错误信息**: {error['message']}")
        if error.get('context'):
            formatted.append(f"**上下文**: {error['context']}")
        formatted.append(f"**解决方案**: {error['solution']}")
        formatted.append(f"**尝试次数**: {error['attempts']}")
        formatted.append("")

    return "\n".join(formatted)
```

## 与Git提交集成

在Step 9 (Git commit)时，提交消息应包含报告引用：

```python
def generate_commit_message(feature_info, report_path):
    message = f"{feature_info['type']}: {feature_info['name']}\n\n"
    message += f"{feature_info['description']}\n\n"

    # 添加工作流指标
    message += f"工作流步骤: {feature_info['workflow_steps_count']}\n"
    message += f"决策点: {feature_info['decision_points_count']}\n"
    message += f"遇到错误: {feature_info['total_errors']}\n"
    message += f"调试迭代: {feature_info['iterations_count']}\n\n"

    # 添加报告引用
    message += f"详见工作流报告: {report_path}\n\n"

    # 添加issue引用（如果有）
    if feature_info.get('issue_number'):
        message += f"Closes #{feature_info['issue_number']}\n\n"

    message += "Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

    return message
```

## 错误处理

### 报告生成失败

如果报告生成失败，不应阻止Git提交：

```python
def generate_workflow_report_safe(workflow_log, feature_info):
    try:
        report_path = generate_workflow_report(workflow_log, feature_info)
        return report_path
    except Exception as e:
        log_error(f"Failed to generate workflow report: {e}")
        # 创建简化版报告
        return create_minimal_report(workflow_log, feature_info)
```

### 配置文件缺失

如果配置文件不存在，使用默认配置：

```python
DEFAULT_CONFIG = {
    'enabled': True,
    'language': 'zh-CN',
    'detail_level': 'detailed',
    'output_dir': 'docs/workflows'
}
```

## 最佳实践

1. **及时记录**: 在每个步骤执行时立即记录，不要事后回忆
2. **详细决策**: 记录决策时包含所有考虑的选项和选择理由
3. **完整错误**: 记录错误时包含完整的上下文和解决过程
4. **清晰提示词**: 记录用户提示词时保持原始表达
5. **准确时间**: 使用精确的时间戳，便于后续分析

## 维护

- **版本**: 1.0.0
- **最后更新**: 2026-02-15
- **维护者**: autonomous-builder skill
