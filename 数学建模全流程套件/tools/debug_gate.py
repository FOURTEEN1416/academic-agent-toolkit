import sys, json, tempfile, hashlib
from pathlib import Path
sys.path.insert(0, '.')
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from engine.opencode_bridge import StepResult
from engine.quality_gates import QualityGate

workspace = Path(tempfile.mkdtemp(prefix='gate-debug-'))
workspace.mkdir(parents=True, exist_ok=True)

ws_parent = workspace.parent
ws_parent.mkdir(parents=True, exist_ok=True)
(ws_parent / 'skills' / 'comp-prob-analysis').mkdir(parents=True, exist_ok=True)
(ws_parent / 'skills' / 'comp-prob-analysis' / 'SKILL.md').write_text('skill: comp-prob-analysis', encoding='utf-8')

catalog = json.loads((Path('engine/modex-core/templates.json')).read_text(encoding='utf-8'))
db = workspace / '.engine' / 'workflow.sqlite'
db.parent.mkdir(parents=True, exist_ok=True)

with WorkflowStore(db) as store:
    runner = WorkflowRunner(store, catalog, ws_parent / 'skills')
    workflow = runner.start('comp_cumcm', workspace, {'language': 'zh'})
    
    r = runner.next_action(workflow.id)
    action = r.action
    print(f'Step: {action.skill_name}')
    
    # 创建足够大的输出文件 (至少1500字节)
    large_content = 'Analysis\n' * 100 + '\n' * 500
    (workspace / 'PROBLEM_ANALYSIS.md').write_text(large_content, encoding='utf-8')
    print(f'File size: {(workspace / "PROBLEM_ANALYSIS.md").stat().st_size} bytes')
    
    # 预检门禁
    gate = QualityGate(workspace)
    checks = gate.run_all('comp-prob-analysis', declared_outputs=['PROBLEM_ANALYSIS.md'], required_checks=['step_manifest'])
    print(f'Pre-check: ok={checks["ok"]}')
    for name, check in checks['checks'].items():
        print(f'  {name}: ok={check.get("ok")}, reason={check.get("reason", "")}')
    
    # 完成步骤
    r = runner.complete_step(workflow.id, StepResult(ok=True, artifacts=['PROBLEM_ANALYSIS.md'], metadata={'execution_evidence': {'schema_version': 1, 'agent': 'test', 'step_id': action.step_id, 'skill_name': action.skill_name, 'skill_sha256': hashlib.sha256((ws_parent / 'skills' / action.skill_name / 'SKILL.md').read_bytes()).hexdigest(), 'commands': [{'command': 'test', 'returncode': 0, 'cwd': '.'}], 'inputs': [], 'outputs': ['PROBLEM_ANALYSIS.md']}}))
    print(f'Complete: {r.status}')
    print(f'Message: {r.message}')
    
    # 检查 checkpoint
    if r.status == 'waiting_checkpoint':
        print('Checkpoint waiting - approving...')
        cp = store._connection.execute('SELECT id FROM checkpoints WHERE workflow_id = ? ORDER BY created_at DESC LIMIT 1', (workflow.id,)).fetchone()
        if cp:
            r2 = runner.approve_checkpoint(cp['id'], {'approved': True})
            print(f'Approved: {r2.status}')
