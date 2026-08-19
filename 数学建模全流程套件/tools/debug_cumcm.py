import sys, json, tempfile, hashlib
from pathlib import Path
sys.path.insert(0, '.')
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from engine.opencode_bridge import StepResult
from engine.quality_gates import QualityGate
from engine.step_manifest import write_manifest

workspace = Path(tempfile.mkdtemp(prefix='cumcm-debug6-'))
workspace.mkdir(parents=True, exist_ok=True)

# 创建技能目录
ws_parent = workspace.parent
ws_parent.mkdir(parents=True, exist_ok=True)
for skill in ['comp-prob-analysis', 'comp-literature']:
    (ws_parent / 'skills' / skill).mkdir(parents=True, exist_ok=True)
    (ws_parent / 'skills' / skill / 'SKILL.md').write_text(f'skill: {skill}', encoding='utf-8')

catalog = json.loads((Path('engine/modex-core/templates.json')).read_text(encoding='utf-8'))
db = workspace / '.engine' / 'workflow.sqlite'
db.parent.mkdir(parents=True, exist_ok=True)

with WorkflowStore(db) as store:
    runner = WorkflowRunner(store, catalog, ws_parent / 'skills')
    workflow = runner.start('comp_cumcm', workspace, {'language': 'zh'})
    
    # 执行第一步
    result = runner.next_action(workflow.id)
    action = result.action
    print(f'Step 1: {action.skill_name}')
    print(f'Output files: {action.output_files}')
    
    # 创建输出文件（确保足够大）
    large_content = 'Analysis\n' * 100 + '\n' * 500  # 大约 1500+ 字节
    (workspace / 'PROBLEM_ANALYSIS.md').write_text(large_content, encoding='utf-8')
    print(f'File size: {(workspace / "PROBLEM_ANALYSIS.md").stat().st_size} bytes')
    
    # 手动创建 STEP_MANIFEST
    write_manifest(
        workspace=workspace,
        step_name='comp-prob-analysis',
        config={'workflow_id': workflow.id},
        outputs=[workspace / 'PROBLEM_ANALYSIS.md'],
        backend='test-backend 1.0',
        commands=[{'command': 'test', 'exitCode': 0}],
        dependencies={},
    )
    print(f'Manifest exists: {(workspace / "STEP_MANIFEST.json").is_file()}')
    
    # 手动运行门禁
    gate = QualityGate(workspace)
    checks = gate.run_all('comp-prob-analysis', declared_outputs=['PROBLEM_ANALYSIS.md'], required_checks=['step_manifest'])
    print(f'Gate result: {json.dumps(checks, ensure_ascii=False, indent=2, default=str)}')
    
    step_result = StepResult(ok=True, artifacts=['PROBLEM_ANALYSIS.md'], metadata={'execution_evidence': {'schema_version': 1, 'agent': 'test', 'step_id': action.step_id, 'skill_name': action.skill_name, 'skill_sha256': hashlib.sha256((ws_parent / 'skills' / action.skill_name / 'SKILL.md').read_bytes()).hexdigest(), 'commands': [{'command': 'test', 'returncode': 0, 'cwd': '.'}], 'inputs': [], 'outputs': ['PROBLEM_ANALYSIS.md']}})
    r = runner.complete_step(workflow.id, step_result)
    print(f'Step 1 complete result: {r.status}')
    print(f'Step 1 message: {r.message[:200]}')
    
    # 检查 checkpoint
    if r.status == 'waiting_checkpoint':
        print('Checkpoint waiting - approving...')
        cp = store._connection.execute('SELECT id FROM checkpoints WHERE workflow_id = ? ORDER BY created_at DESC LIMIT 1', (workflow.id,)).fetchone()
        if cp:
            r2 = runner.approve_checkpoint(cp['id'], {'approved': True})
            print(f'Checkpoint approved: {r2.status}')
    
    # 继续执行
    result2 = runner.next_action(workflow.id)
    print(f'Next action: {result2.status}')
    if result2.status == 'advanced':
        action2 = result2.action
        print(f'Step 2: {action2.skill_name}')
