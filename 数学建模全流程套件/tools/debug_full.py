import sys, json, tempfile, hashlib
from pathlib import Path
sys.path.insert(0, '.')
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from engine.opencode_bridge import StepResult
from engine.quality_gates import QualityGate

workspace = Path(tempfile.mkdtemp(prefix='full-debug-'))
workspace.mkdir(parents=True, exist_ok=True)

ws_parent = workspace.parent
ws_parent.mkdir(parents=True, exist_ok=True)
for skill in ['comp-prob-analysis', 'comp-literature', 'comp-modeling']:
    (ws_parent / 'skills' / skill).mkdir(parents=True, exist_ok=True)
    (ws_parent / 'skills' / skill / 'SKILL.md').write_text(f'skill: {skill}', encoding='utf-8')

catalog = json.loads((Path('engine/modex-core/templates.json')).read_text(encoding='utf-8'))
db = workspace / '.engine' / 'workflow.sqlite'
db.parent.mkdir(parents=True, exist_ok=True)

with WorkflowStore(db) as store:
    runner = WorkflowRunner(store, catalog, ws_parent / 'skills')
    workflow = runner.start('comp_cumcm', workspace, {'language': 'zh'})
    
    # 执行第一步
    r = runner.next_action(workflow.id)
    action = r.action
    (workspace / 'PROBLEM_ANALYSIS.md').write_text('Analysis\n' * 100, encoding='utf-8')
    r = runner.complete_step(workflow.id, StepResult(ok=True, artifacts=['PROBLEM_ANALYSIS.md'], metadata={'execution_evidence': {'schema_version': 1, 'agent': 'test', 'step_id': action.step_id, 'skill_name': action.skill_name, 'skill_sha256': hashlib.sha256((ws_parent / 'skills' / action.skill_name / 'SKILL.md').read_bytes()).hexdigest(), 'commands': [{'command': 'test', 'returncode': 0, 'cwd': '.'}], 'inputs': [], 'outputs': ['PROBLEM_ANALYSIS.md']}}))
    print(f'Step 1: {r.status}')
    
    # 批准检查点
    cp = store._connection.execute('SELECT id FROM checkpoints WHERE workflow_id = ? ORDER BY created_at DESC LIMIT 1', (workflow.id,)).fetchone()
    if cp:
        r = runner.approve_checkpoint(cp['id'], {'approved': True})
        print(f'Checkpoint: {r.status}')
    
    # 执行第二步
    r = runner.next_action(workflow.id)
    action = r.action
    print(f'Step 2: {action.skill_name}')
    (workspace / 'LITERATURE.md').write_text('Lit\n' * 100, encoding='utf-8')
    (workspace / 'literature').mkdir(parents=True, exist_ok=True)
    (workspace / 'literature' / 'search_evidence.json').write_text(json.dumps([{'queries': ['test']}]), encoding='utf-8')
    (workspace / 'paper').mkdir(parents=True, exist_ok=True)
    (workspace / 'paper' / 'references.bib').write_text('@book{test, title={Test}, author={Author}, year={2024}}', encoding='utf-8')
    r = runner.complete_step(workflow.id, StepResult(ok=True, artifacts=['LITERATURE.md', 'literature/search_evidence.json', 'paper/references.bib'], metadata={'execution_evidence': {'schema_version': 1, 'agent': 'test', 'step_id': action.step_id, 'skill_name': action.skill_name, 'skill_sha256': hashlib.sha256((ws_parent / 'skills' / action.skill_name / 'SKILL.md').read_bytes()).hexdigest(), 'commands': [{'command': 'test', 'returncode': 0, 'cwd': '.'}], 'inputs': [], 'outputs': ['LITERATURE.md', 'literature/search_evidence.json', 'paper/references.bib']}}))
    print(f'Step 2: {r.status}')
    
    # 执行第三步
    r = runner.next_action(workflow.id)
    action = r.action
    print(f'Step 3: {action.skill_name}')
    
    # 创建输出文件
    modeling_md = workspace / 'MODELING_REPORT.md'
    modeling_content = '# 建模报告\n\n## METHOD_CLAIMS_MACHINE\nassumptions:\n  - 数据服从正态分布\nscope:\n  - 适用于小规模问题\n\n' + '\n扩展内容 ' * 200
    modeling_md.write_text(modeling_content, encoding='utf-8')
    print(f'File size: {modeling_md.stat().st_size} bytes')
    
    # 检查 STEP_MANIFEST
    manifest_path = workspace / 'STEP_MANIFEST.json'
    print(f'Manifest exists before complete: {manifest_path.is_file()}')
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        print(f'Manifest stepName: {manifest.get("stepName")}')
    
    # 预检门禁
    gate = QualityGate(workspace)
    checks = gate.run_all('comp-modeling', declared_outputs=['MODELING_REPORT.md'], required_checks=['step_manifest', 'modeling_contract'])
    print(f'Pre-check gate: ok={checks["ok"]}, checks={list(checks["checks"].keys())}')
    for name, check in checks['checks'].items():
        if not check.get('ok'):
            print(f'  - {name}: {check.get("reason", check.get("errors", "unknown"))}')
    
    # 完成步骤
    r = runner.complete_step(workflow.id, StepResult(ok=True, artifacts=['MODELING_REPORT.md'], metadata={'execution_evidence': {'schema_version': 1, 'agent': 'test', 'step_id': action.step_id, 'skill_name': action.skill_name, 'skill_sha256': hashlib.sha256((ws_parent / 'skills' / action.skill_name / 'SKILL.md').read_bytes()).hexdigest(), 'commands': [{'command': 'test', 'returncode': 0, 'cwd': '.'}], 'inputs': [], 'outputs': ['MODELING_REPORT.md']}}))
    print(f'Step 3 result: {r.status}')
    print(f'Step 3 message: {r.message[:200]}')
    
    # 检查 STEP_MANIFEST 状态
    print(f'Manifest exists after complete: {manifest_path.is_file()}')
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        print(f'Manifest stepName after: {manifest.get("stepName")}')
