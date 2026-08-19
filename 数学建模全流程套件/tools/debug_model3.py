import sys, json, tempfile, hashlib
from pathlib import Path
sys.path.insert(0, '.')
from engine.quality_gates import QualityGate

workspace = Path(tempfile.mkdtemp(prefix='model-debug3-'))
workspace.mkdir(parents=True, exist_ok=True)

# 创建 MODELING_REPORT.md 包含 METHOD_CLAIMS_MACHINE 块
modeling_md = workspace / 'MODELING_REPORT.md'
modeling_content = """# 建模报告\n\n## METHOD_CLAIMS_MACHINE\nassumptions:\n  - 数据服从正态分布\nscope:\n  - 适用于小规模问题\n  - 计算复杂度 O(n^2)\n\n## 模型推导\n\n"""
modeling_content += "\n扩展内容 " * 200
modeling_md.write_text(modeling_content, encoding="utf-8")
print(f"File size: {modeling_md.stat().st_size} bytes")

# 手动运行门禁
gate = QualityGate(workspace)
checks = gate.run_all('comp-modeling', declared_outputs=['MODELING_REPORT.md'], required_checks=['step_manifest', 'modeling_contract'])
print(json.dumps(checks, ensure_ascii=False, indent=2, default=str))
