import json
from pathlib import Path

from engine.quality_gates import QualityGate
from tools.codesucker_bridge import run_source_materials


def test_bridge_runs_vendored_backend(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text('print("https://example.test")\n# remove me\n', encoding="utf-8")
    workspace = tmp_path / "workspace"
    manifest = run_source_materials(
        {
            "root": str(project),
            "title": "测试软件 V1.0",
            "owner": "测试主体",
            "extensions": ["py"],
            "excludes": [".git"],
            "linesPerPage": 50,
            "maxPages": 60,
        },
        workspace,
    )
    assert manifest["backend"] == "vendored-codesucker-core"
    assert manifest["coreCommit"] == "b065a1825f4e32dca4c4b7fd8bccf3e020a77c5c"
    assert (workspace / "source-materials" / "audit.json").is_file()
    assert len(json.loads((workspace / "source-materials" / "files.json").read_text(encoding="utf-8"))["files"]) == 1


def test_bridge_writes_explicit_versioned_config_and_passes_source_material_gate(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 80, encoding="utf-8")
    workspace = tmp_path / "workspace"

    manifest = run_source_materials(
        {
            "root": str(project),
            "title": "测试软件 V1.0",
            "extensions": ["py"],
            "linesPerPage": 50,
            "maxPages": 60,
        },
        workspace,
    )

    config = json.loads((workspace / "source-materials.config.json").read_text(encoding="utf-8"))
    assert config["configSchemaVersion"] == 1
    assert config["rulesVersion"] == manifest["rulesVersion"]
    assert config["coreVersion"] == "0.4.4"
    assert config["coreCommit"] == "b065a1825f4e32dca4c4b7fd8bccf3e020a77c5c"
    assert QualityGate(workspace).check_source_materials()["ok"] is True
