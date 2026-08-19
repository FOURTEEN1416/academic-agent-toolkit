import sys, tempfile, json
from pathlib import Path
sys.path.insert(0, '.')
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from engine.template_resolver import resolve_template

# 测试 comp_cumcm 模板解析
catalog = json.load(open('engine/modex-core/templates.json', encoding='utf-8'))
steps = resolve_template('comp_cumcm', {}, catalog)
print(f'comp_cumcm 解析步骤数: {len(steps)}')
for i, s in enumerate(steps):
    checks = s.get('required_checks', [])
    if checks:
        print(f'  步骤 {i}: {s["skill_name"]} -> checks: {checks}')

# 测试 workflow 启动
store = WorkflowStore(Path(tempfile.mkdtemp()) / 'test.db')
runner = WorkflowRunner(store, catalog, Path('skills'))
ws = Path(tempfile.mkdtemp())
workflow = runner.start('comp_cumcm', ws, {'language': 'zh'})
print(f'\nWorkflow 创建成功: {workflow.id}')
print(f'步骤数: {len(workflow.steps)}')
action = runner.next_action(workflow.id)
if action.action:
    print(f'下一步: skill={action.action.skill_name}')
else:
    print('下一步: None (workflow 可能已结束)')