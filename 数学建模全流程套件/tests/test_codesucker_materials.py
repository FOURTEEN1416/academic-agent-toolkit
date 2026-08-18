import json
import hashlib
from pathlib import Path

from tools.codesucker_bridge import run_source_materials
from tools.codesucker_materials import write_code_pages


def test_code_pages_are_derived_from_selection(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 55, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, workspace)
    output = workspace / "草稿" / "代码-全部.md"
    pages = write_code_pages(workspace, output, "测试软件 V1.0")
    assert pages == 2
    text = output.read_text(encoding="utf-8")
    assert "## 第1页" in text
    assert "source: main.py" in text


def test_manifest_has_output_hashes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 50, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, workspace)
    manifest = json.loads((workspace / "source-materials" / "SOURCE_MATERIALS_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["outputSha256"]
    assert "source-materials/audit.json" in manifest["outputSha256"]
    audit = workspace / "source-materials" / "audit.json"
    assert manifest["outputSha256"]["source-materials/audit.json"] == hashlib.sha256(audit.read_bytes()).hexdigest()
    assert "source-materials/SOURCE_MATERIALS_MANIFEST.json" not in manifest["outputSha256"]
