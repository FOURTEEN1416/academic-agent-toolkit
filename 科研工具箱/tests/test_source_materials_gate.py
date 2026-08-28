from tools.codesucker_bridge import run_source_materials
from engine.quality_gates import QualityGate
import json


def test_source_materials_gate_accepts_standard_output(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 50, encoding="utf-8")
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, tmp_path / "workspace")
    result = QualityGate(tmp_path / "workspace").check_source_materials()
    assert result["ok"], result


def test_source_materials_gate_requires_cleaned_json_and_report(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 50, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, workspace)

    (workspace / "source-materials" / "cleaned.json").unlink()
    (workspace / "source-materials" / "SOURCE_MATERIALS_REPORT.md").unlink()

    result = QualityGate(workspace).check_source_materials()

    assert result["ok"] is False
    assert "cleaned.json" in result["reason"]
    assert "SOURCE_MATERIALS_REPORT.md" in result["reason"]


def test_source_materials_gate_rejects_output_hash_mismatch(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 50, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, workspace)

    audit = workspace / "source-materials" / "audit.json"
    audit.write_text("[]", encoding="utf-8")

    result = QualityGate(workspace).check_source_materials()

    assert result["ok"] is False
    assert "outputSha256" in result["reason"] or "哈希" in result["reason"]


def test_source_materials_gate_rejects_page_count_over_max_pages(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 120, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"], "linesPerPage": 50, "maxPages": 60}, workspace)

    manifest_path = workspace / "source-materials" / "SOURCE_MATERIALS_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["config"]["maxPages"] = 1
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    result = QualityGate(workspace).check_source_materials()

    assert result["ok"] is False
    assert "maxPages" in result["reason"] or "页数" in result["reason"]


def test_source_materials_gate_rejects_stats_page_overrun(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 120, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"], "linesPerPage": 50, "maxPages": 60}, workspace)

    stats_path = workspace / "source-materials" / "stats.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    stats["estimatedPages"] = 999
    stats_path.write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")

    result = QualityGate(workspace).check_source_materials()

    assert result["ok"] is False
    assert "estimatedPages" in result["reason"] or "maxPages" in result["reason"]


def test_source_materials_gate_requires_rendered_outputs_in_manifest_hashes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 50, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, workspace)

    manifest_path = workspace / "source-materials" / "SOURCE_MATERIALS_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outputSha256"] = {
        key: value for key, value in manifest["outputSha256"].items()
        if "/rendered/" not in key
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    result = QualityGate(workspace).check_source_materials()

    assert result["ok"] is False
    assert "rendered" in result["reason"] or "outputSha256" in result["reason"]


def test_source_materials_gate_rejects_tampered_rendered_file(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 50, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, workspace)

    rendered = workspace / "source-materials" / "rendered"
    target = next(rendered.iterdir())
    target.write_text("tampered", encoding="utf-8")

    result = QualityGate(workspace).check_source_materials()

    assert result["ok"] is False
    assert "哈希" in result["reason"] or "不一致" in result["reason"]


def test_source_materials_gate_rejects_empty_cleaned_section(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 50, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, workspace)

    cleaned_path = workspace / "source-materials" / "cleaned.json"
    cleaned = json.loads(cleaned_path.read_text(encoding="utf-8"))
    cleaned["cleaned"] = []
    cleaned_path.write_text(json.dumps(cleaned, ensure_ascii=False), encoding="utf-8")

    result = QualityGate(workspace).check_source_materials()

    assert result["ok"] is False
    assert "cleaned" in result["reason"] or "有效源码" in result["reason"]


def test_source_materials_gate_rejects_report_content_tamper(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 50, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, workspace)

    report_path = workspace / "source-materials" / "SOURCE_MATERIALS_REPORT.md"
    report_path.write_text("# broken report\n", encoding="utf-8")

    result = QualityGate(workspace).check_source_materials()

    assert result["ok"] is False
    assert "report" in result["reason"].lower() or "SOURCE_MATERIALS_REPORT" in result["reason"]
