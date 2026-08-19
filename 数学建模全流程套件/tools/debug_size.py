import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, '.')
from engine.quality_gates import QualityGate

workspace = Path(tempfile.mkdtemp(prefix='model-size-'))
workspace.mkdir(parents=True, exist_ok=True)

# 创建一个大文件
content = '# 建模报告\n\n## METHOD_CLAIMS_MACHINE\nassumptions:\n  - 数据服从正态分布\nscope:\n  - 适用于小规模问题\n\n'
while len(content.encode('utf-8')) < 3000:
    content += '\n更多内容 ' * 50
(workspace / 'MODELING_REPORT.md').write_text(content, encoding='utf-8')
print(f'File size: {(workspace / "MODELING_REPORT.md").stat().st_size} bytes')

# 运行门禁
gate = QualityGate(workspace)
checks = gate.run_all('comp-modeling', declared_outputs=['MODELING_REPORT.md'], required_checks=['step_manifest', 'modeling_contract'])
print(json.dumps(checks, ensure_ascii=False, indent=2, default=str))
