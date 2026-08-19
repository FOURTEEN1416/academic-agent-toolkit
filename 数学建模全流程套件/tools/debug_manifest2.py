import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, '.')
from engine.step_manifest import write_manifest, validate_manifest

workspace = Path(tempfile.mkdtemp(prefix='manifest-test-'))
workspace.mkdir(parents=True, exist_ok=True)

# 创建文件
(workspace / 'PROBLEM_ANALYSIS.md').write_text('Analysis\n' * 100, encoding='utf-8')
print(f'File exists before write: {(workspace / "PROBLEM_ANALYSIS.md").is_file()}')
print(f'File size: {(workspace / "PROBLEM_ANALYSIS.md").stat().st_size}')

# 写入 manifest
write_manifest(workspace=workspace, step_name='test', config={}, outputs=[workspace / 'PROBLEM_ANALYSIS.md'], backend='test', commands=[{'command': 'test', 'exitCode': 0}], dependencies={})
print(f'Manifest exists after write: {(workspace / "STEP_MANIFEST.json").is_file()}')

# 验证
result = validate_manifest(workspace)
print(f'Validation: ok={result["ok"]}, errors={result["errors"]}')
