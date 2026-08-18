"""补充核心模块测试：template_resolver / opencode_bridge / artifact_manifest 独立覆盖。"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.artifact_manifest import Artifact, ArtifactManifest
from engine.opencode_bridge import StepAction, StepResult
from engine.template_resolver import resolve_template


# ============ template_resolver ============

def _catalog():
    return {
        "demo": {"sub_steps": [
            {"skill_name": "comp-prob-analysis", "output_files": ["A.md"]},
            {"skill_name": "paper-write", "output_files": ["paper/main.tex"]},
            {"skill_name": "comp-literature", "output_files": ["LITERATURE.md"]},
            {"skill_name": "comp-review", "output_files": ["REVIEW.md"]},
        ]},
    }


def test_resolve_keeps_steps_in_order():
    steps = resolve_template("demo", {}, _catalog())
    assert [s["skill_name"] for s in steps] == [
        "comp-prob-analysis", "paper-write", "comp-literature", "comp-review",
    ]


def test_resolve_zh_swaps_paper_writing_skill():
    steps = resolve_template("demo", {"language": "zh"}, _catalog())
    names = [s["skill_name"] for s in steps]
    assert "paper-write-zh" in names
    assert "paper-write" not in names


def test_resolve_skip_literature_and_review():
    steps = resolve_template("demo", {"skip_literature": True, "skip_review": True}, _catalog())
    names = [s["skill_name"] for s in steps]
    assert "comp-literature" not in names
    assert "comp-review" not in names
    assert "comp-prob-analysis" in names


def test_resolve_unknown_template_raises():
    with pytest.raises(KeyError):
        resolve_template("does-not-exist", {}, _catalog())


def test_resolve_docx_output_appends_export_step():
    steps = resolve_template("demo", {"output_format": "docx"}, _catalog())
    assert any(s["skill_name"] == "docx-export" for s in steps)


# ============ opencode_bridge ============

def _action(tmp_path):
    return StepAction(
        workflow_id="wf1", step_id="step1", position=3, skill_name="comp-code",
        display_name="编程实现", workspace=tmp_path, skill_path=tmp_path / "SKILL.md",
        output_files=["code/main.py", "RESULTS.md"], primary_output="RESULTS.md",
        has_checkpoint=True, checkpoint_type="approve",
    )


def test_step_action_instructions_include_key_fields(tmp_path):
    ins = _action(tmp_path).execution_instructions()
    assert "comp-code" in ins
    assert "RESULTS.md" in ins
    assert "等待用户" in ins or "批准" in ins


def test_step_result_defaults():
    r = StepResult(ok=True)
    assert r.stdout == ""
    assert r.stderr == ""
    assert r.artifacts == []
    assert r.duration_seconds == 0.0
    assert r.metadata == {}
    assert r.evidence_path is None


def test_step_result_custom_fields():
    r = StepResult(ok=False, stderr="boom", artifacts=["a.txt"], duration_seconds=1.5)
    assert r.ok is False
    assert r.stderr == "boom"
    assert r.artifacts == ["a.txt"]


# ============ artifact_manifest 独立覆盖 ============

def test_manifest_missing_file_reported():
    result = ArtifactManifest.validate(Path("C:/nonexistent-ws"), ["x.md"])
    assert result["ok"] is False
    assert "x.md" in result["missing"]


def test_manifest_directory_recursion(tmp_path):
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "a.png").write_bytes(b"PNG")
    (tmp_path / "figures" / "sub").mkdir()
    (tmp_path / "figures" / "sub" / "b.json").write_text('{}', encoding="utf-8")

    result = ArtifactManifest.validate(tmp_path, ["figures/"])
    assert result["ok"] is True
    artifact = result["artifacts"][0]
    assert artifact.mime_type == "inode/directory"
    assert artifact.size == 3 + 2  # PNG + {}

    # 目录内容变化 → 哈希变化（防"只声明目录名"的偷懒）
    (tmp_path / "figures" / "c.txt").write_text("zz", encoding="utf-8")
    result2 = ArtifactManifest.validate(tmp_path, ["figures/"])
    assert result2["artifacts"][0].sha256 != artifact.sha256


def test_manifest_empty_directory_treated_missing(tmp_path):
    (tmp_path / "figures").mkdir()
    result = ArtifactManifest.validate(tmp_path, ["figures/"])
    assert result["ok"] is False


def test_manifest_hash_override_checked(tmp_path):
    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    wrong = "0" * 64
    result = ArtifactManifest.validate(tmp_path, [{"path": "f.txt", "sha256": wrong}])
    assert result["ok"] is False
    assert "f.txt" in result["invalid"]
