from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify" / "live-document-gate.py"
DEVELOPER_ENTRY_GATE = REPO_ROOT / "scripts" / "verify" / "vibe-developer-entry-gate.ps1"
DEVELOPER_ENTRY_CONTRACT = REPO_ROOT / "references" / "developer-entry-contract.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("live_document_gate", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_live_document_gate_accepts_registered_additions() -> None:
    module = _load_module()

    result = module.evaluate(REPO_ROOT, ["README.md"])

    assert result["result"] == "PASS"
    assert result["registered_document_count"] <= 30
    assert result["validated_added_documents"] == ["README.md"]


def test_live_document_gate_rejects_unregistered_governed_additions() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="not registered"):
        module.evaluate(REPO_ROOT, ["docs/new-unregistered-guide.md"])


def test_live_document_gate_ignores_markdown_outside_governed_roots() -> None:
    module = _load_module()

    result = module.evaluate(REPO_ROOT, ["bundled/skills/example/SKILL.md"])

    assert result["validated_added_documents"] == []


def test_live_document_gate_reports_backlog_and_strict_failure() -> None:
    module = _load_module()
    contract = module.load_live_governance_contract(REPO_ROOT)
    tracked_paths = [
        *(document.path for document in contract.documents),
        "THIRD_PARTY_LICENSES.md",
        "docs/unregistered-history.md",
        "bundled/skills/example/SKILL.md",
    ]

    migration = module.evaluate(
        REPO_ROOT,
        [],
        census_mode="migration-report",
        tracked_markdown_paths=tracked_paths,
    )
    strict = module.evaluate(
        REPO_ROOT,
        [],
        census_mode="strict",
        tracked_markdown_paths=tracked_paths,
    )

    assert migration["result"] == "PASS"
    assert migration["census_mode"] == "migration-report"
    assert migration["census"]["counts"] == {
        "registered": len(contract.documents),
        "excluded": 1,
        "unregistered": 1,
    }
    assert strict["result"] == "FAIL"
    assert strict["census_mode"] == "strict"
    assert strict["failure"] == "strict census found 1 unregistered governed Markdown document"
    assert strict["census"] == migration["census"]


def test_developer_entry_uses_stable_live_contract_without_dated_plan() -> None:
    contract_text = DEVELOPER_ENTRY_CONTRACT.read_text(encoding="utf-8")
    contributing_text = CONTRIBUTING.read_text(encoding="utf-8")
    gate_text = DEVELOPER_ENTRY_GATE.read_text(encoding="utf-8-sig")

    assert "config/live-document-contract.json" in contract_text
    assert "config/live-document-contract.json" in contributing_text
    assert "docs/plans/" not in contract_text
    assert "post-upstream-governance-developer-entry-plan" not in contributing_text
    assert "contributing_links_live_contract" in gate_text
    assert "contributing_links_plan_entry" not in gate_text


def test_collect_added_paths_treats_renamed_markdown_as_an_addition(
    tmp_path: Path,
) -> None:
    module = _load_module()
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "contract@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Contract Test"],
        cwd=tmp_path,
        check=True,
    )
    old_path = tmp_path / "docs" / "old-history.md"
    old_path.parent.mkdir(parents=True)
    old_path.write_text("# Old\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    base_ref = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        text=True,
    ).strip()
    old_path.rename(tmp_path / "docs" / "new-live.md")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "rename"], cwd=tmp_path, check=True)

    added_paths = module.collect_added_paths(tmp_path, base_ref)

    assert added_paths == ["docs/new-live.md"]


def test_collect_tracked_markdown_paths_is_nul_safe_and_deterministic(
    tmp_path: Path,
) -> None:
    module = _load_module()
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    tracked_paths = [
        tmp_path / "README.md",
        tmp_path / "docs" / "Guide With Spaces.MD",
        tmp_path / "docs" / "ignored.txt",
    ]
    for path in tracked_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Tracked\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)

    assert module.collect_tracked_markdown_paths(tmp_path) == [
        "docs/Guide With Spaces.MD",
        "README.md",
    ]


def test_collect_tracked_markdown_paths_reflects_worktree_state(
    tmp_path: Path,
) -> None:
    module = _load_module()
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    removed = tmp_path / "docs" / "removed.md"
    removed.parent.mkdir(parents=True)
    removed.write_text("# Removed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    removed.unlink()

    untracked = tmp_path / "docs" / "untracked.md"
    untracked.write_text("# Untracked\n", encoding="utf-8")

    assert module.collect_tracked_markdown_paths(tmp_path) == [
        "docs/untracked.md",
    ]
