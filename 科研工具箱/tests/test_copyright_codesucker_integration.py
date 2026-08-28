import json
import shutil
from pathlib import Path

from tools.codesucker_bridge import run_source_materials


def test_standard_rendered_outputs_are_available_for_copyright_build(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 80, encoding="utf-8")
    workspace = tmp_path / "软件著作权申请资料"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, workspace)
    rendered = workspace / "source-materials" / "rendered"
    assert any(path.suffix in {".docx", ".txt"} and path.stat().st_size > 0 for path in rendered.iterdir())
    manifest = json.loads((workspace / "source-materials" / "SOURCE_MATERIALS_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["backend"] == "vendored-codesucker-core"
