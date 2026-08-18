from tools.codesucker_bridge import run_source_materials
from engine.quality_gates import QualityGate


def test_source_materials_gate_accepts_standard_output(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 50, encoding="utf-8")
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, tmp_path / "workspace")
    result = QualityGate(tmp_path / "workspace").check_source_materials()
    assert result["ok"], result
