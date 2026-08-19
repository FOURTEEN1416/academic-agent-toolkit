import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, '.')
from engine.step_manifest import write_manifest, validate_manifest

workspace = Path(tempfile.mkdtemp(prefix='manifest-debug-'))
workspace.mkdir(parents=True, exist_ok=True)

# 创建文件
(workspace / 'MODELING_REPORT.md').write_text('# 建模报告\n\n## METHOD_CLAIMS_MACHINE\nassumptions:\n  - test\nscope:\n  - test\n\n' + '\n扩展 ' * 200, encoding='utf-8')

# 写入 manifest
manifest_path = write_manifest(
    workspace=workspace,
    step_name='comp-modeling',
    config={'workflow_id': 'test'},
    outputs=[workspace / 'MODELING_REPORT.md'],
    backend='test-backend',
    commands=[{'command': 'test', 'exitCode': 0}],
    dependencies={},
)
print(f'Manifest path: {manifest_path}')
print(f'Manifest exists: {manifest_path.is_file()}')

# 验证 manifest
result = validate_manifest(workspace)
print(f'Validation result: {json.dumps(result, ensure_ascii=False, indent=2, default=str)}')
