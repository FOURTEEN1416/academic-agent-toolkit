import json
from pathlib import Path

from engine.quality_gates import QualityGate
from engine.step_manifest import SCHEMA_VERSION, get_step_manifest, validate_manifest, write_manifest


def test_write_and_validate_step_manifest_hashes_inputs_outputs(tmp_path):
    input_path = tmp_path / "data" / "input.txt"
    output_path = tmp_path / "reports" / "result.md"
    input_path.parent.mkdir()
    output_path.parent.mkdir()
    input_path.write_text("input", encoding="utf-8")
    output_path.write_text("output", encoding="utf-8")

    manifest_path = write_manifest(
        workspace=tmp_path,
        step_name="comp-modeling",
        config={"solver": "HiGHS", "timeLimit": 300},
        inputs=[input_path],
        outputs=[output_path],
        backend="scipy 1.14.1",
        commands=[{"command": "python code/main.py", "exitCode": 0}],
        dependencies={"scipy": "1.14.1"},
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = validate_manifest(tmp_path)

    assert result["ok"] is True
    assert manifest["schemaVersion"] == SCHEMA_VERSION
    assert manifest["inputFiles"][0]["path"] == "data/input.txt"
    assert manifest["outputFiles"][0]["path"] == "reports/result.md"
    assert len(manifest["inputFiles"][0]["sha256"]) == 64
    assert len(manifest["outputFiles"][0]["sha256"]) == 64
    assert "configSha256" in manifest


def test_validate_step_manifest_rejects_changed_output_hash(tmp_path):
    output_path = tmp_path / "result.md"
    output_path.write_text("before", encoding="utf-8")
    write_manifest(
        workspace=tmp_path,
        step_name="comp-code",
        outputs=[output_path],
        backend="python 3.12",
    )
    output_path.write_text("after", encoding="utf-8")

    result = validate_manifest(tmp_path)

    assert result["ok"] is False
    assert any("SHA-256" in error and "result.md" in error for error in result["errors"])


def test_quality_gate_runs_required_step_manifest_check(tmp_path):
    output_path = tmp_path / "result.md"
    output_path.write_text("x" * 2500, encoding="utf-8")
    write_manifest(
        workspace=tmp_path,
        step_name="comp-modeling",
        outputs=[output_path],
        backend="manual-test-backend 1.0",
    )

    result = QualityGate(tmp_path).run_all(
        "comp-modeling",
        declared_outputs=["result.md"],
        required_checks=["step_manifest"],
    )

    assert result["ok"] is True
    assert result["checks"]["step_manifest"]["stepName"] == "comp-modeling"


def test_get_step_manifest_returns_none_for_missing_or_invalid_manifest(tmp_path):
    assert get_step_manifest(tmp_path) is None

    (tmp_path / "STEP_MANIFEST.json").write_text("not-json", encoding="utf-8")

    assert get_step_manifest(tmp_path) is None


def test_validate_step_manifest_with_explicit_relative_path(tmp_path):
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    output_path = tmp_path / "result.md"
    output_path.write_text("result", encoding="utf-8")
    manifest_path = write_manifest(
        workspace=tmp_path,
        step_name="paper-write",
        outputs=[output_path],
        backend="latex-template 1.0",
    )
    moved_manifest = manifest_dir / "STEP_MANIFEST.json"
    manifest_path.replace(moved_manifest)

    result = validate_manifest(tmp_path, Path("manifests") / "STEP_MANIFEST.json")

    assert result["ok"] is True
    assert result["outputCount"] == 1


def test_validate_step_manifest_rejects_path_outside_workspace(tmp_path):
    outside = tmp_path.parent / "outside_STEP_MANIFEST.json"
    outside.write_text("{}", encoding="utf-8")

    result = validate_manifest(tmp_path, outside)

    assert result["ok"] is False
    assert "超出工作区" in result["errors"][0]


def test_validate_step_manifest_resolves_suite_level_upstream_provenance(tmp_path):
    output_path = tmp_path / "result.md"
    output_path.write_text("result", encoding="utf-8")
    write_manifest(
        workspace=tmp_path,
        step_name="copyright-source-materials",
        outputs=[output_path],
        backend="vendored-codesucker-core 0.4.4",
        dependencies={"codesucker-core": "0.4.4"},
    )

    result = validate_manifest(tmp_path)

    assert result["ok"] is True
