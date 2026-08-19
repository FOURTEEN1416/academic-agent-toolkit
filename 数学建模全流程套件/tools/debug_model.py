import sys, json, tempfile, hashlib
from pathlib import Path
sys.path.insert(0, '.')
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from engine.opencode_bridge import StepResult
from engine.quality_gates import QualityGate

workspace = Path(tempfile.mkdtemp(prefix='debug-model-'))
workspace.mkdir(parents=True, exist_ok=True)

# 创建技能
ws_parent = workspace.parent
ws_parent.mkdir(parents=True, exist_ok=True)
(ws_parent / 'skills' / 'comp-modeling').mkdir(parents=True, exist_ok=True)
(ws_parent / 'skills' / 'comp-modeling' / 'SKILL.md').write_text('skill: comp-modeling', encoding='utf-8')

catalog = json.loads((Path('engine/modex-core/templates.json')).read_text(encoding='utf-8'))
db = workspace / '.engine' / 'workflow.sqlite'
db.parent.mkdir(parents=True, exist_ok=True)

with WorkflowStore(db) as store:
    runner = WorkflowRunner(store, catalog, ws_parent / 'skills')
    workflow = runner.start('comp_cumcm', workspace, {'language': 'zh'})
    
    # 执行前几步
    for i in range(2):
        r = runner.next_action(workflow.id)
        if r.status == 'advanced':
            action = r.action
            print(f'Step {i+1}: {action.skill_name}')
            # 创建输出文件
            for output in action.output_files:
                p = workspace / output
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('x' * 1000, encoding='utf-8')
            # 完成
            result = runner.complete_step(workflow.id, StepResult(ok=True, artifacts=action.output_files, metadata={'execution_evidence': {'schema_version': 1, 'agent': 'test', 'step_id': action.step_id, 'skill_name': action.skill_name, 'skill_sha256': hashlib.sha256((ws_parent / 'skills' / action.skill_name / 'SKILL.md').read_bytes()).hexdigest(), 'commands': [{'command': 'test', 'returncode': 0, 'cwd': '.'}], 'inputs': [], 'outputs': action.output_files}}))
            print(f'  Result: {result.status}')
            if result.status == 'waiting_checkpoint':
                cp = store._connection.execute('SELECT id FROM checkpoints WHERE workflow_id = ? ORDER BY created_at DESC LIMIT 1', (workflow.id,)).fetchone()
                if cp:
                    runner.approve_checkpoint(cp['id'], {'approved': True})
    
    # 第三步
    result = runner.next_action(workflow.id)
    if result.status == 'advanced':
        action = result.action
        print(f'Step 3: {action.skill_name}')
        
        # 创建输出文件
        modeling_content = '# 建模报告\n\n## METHOD_CLAIMS_MACHINE\nassumptions:\n  - 数据服从正态分布\nscope:\n  - 适用于小规模问题\n\n' + '\n扩展内容 ' * 100
        (workspace / 'MODELING_REPORT.md').write_text(modeling_content, encoding='utf-8')
        fsize = (workspace / 'MODELING_REPORT.md').stat().st_size
        print(f'File size: {fsize} bytes')
        
        # 检查 gate
        gate = QualityGate(workspace)
        checks = gate.run_all('comp-modeling', declared_outputs=['MODELING_REPORT.md'], required_checks=['step_manifest', 'modeling_contract'])
        print(f'Gate before complete: {json.dumps(checks, ensure_ascii=False, indent=2, default=str)}')
        
        # 完成步骤
        result2 = runner.complete_step(workflow.id, StepResult(ok=True, artifacts=['MODELING_REPORT.md'], metadata={'execution_evidence': {'schema_version': 1, 'agent': 'test', 'step_id': action.step_id, 'skill_name': action.skill_name, 'skill_sha256': hashlib.sha256((ws_parent / 'skills' / action.skill_name / 'SKILL.md').read_bytes()).hexdigest(), 'commands': [{'command': 'test', 'returncode': 0, 'cwd': '.'}], 'inputs': [], 'outputs': ['MODELING_REPORT.md']}}))
        print(f'Result: {result2.status}')
        print(f'Message: {result2.message[:200]}')
