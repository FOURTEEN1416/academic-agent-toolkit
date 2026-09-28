from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_SRC = ROOT / "packages" / "contracts" / "src"
if str(CONTRACTS_SRC) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_SRC))

from vgo_contracts.entry_root_guard import EntryRootGuardError, resolve_entry_repo_root


def _write_runtime_root(root: Path) -> None:
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "apps" / "vgo-cli" / "src" / "vgo_cli").mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text("---\nname: vibe\n---\n", encoding="utf-8")
    (root / "config" / "version-governance.json").write_text("{}", encoding="utf-8")
    (root / "config" / "adapter-registry.json").write_text('{"adapters": []}', encoding="utf-8")
    (root / "apps" / "vgo-cli" / "src" / "vgo_cli" / "main.py").write_text(
        "def main():\n    return 0\n",
        encoding="utf-8",
    )


def test_resolve_entry_repo_root_accepts_explicit_runtime_root(tmp_path: Path) -> None:
    runtime_root = tmp_path / "Vibe-Skills"
    _write_runtime_root(runtime_root)

    decision = resolve_entry_repo_root(
        runtime_root,
        script_anchor=runtime_root / "packages" / "runtime-core" / "src" / "vgo_runtime" / "canonical_entry.py",
    )

    assert decision.repo_root == runtime_root.resolve()
    assert decision.auto_corrected is False
    assert decision.reason_code == "repo_root_ok"


def test_resolve_entry_repo_root_autocorrects_workspace_like_input(tmp_path: Path) -> None:
    runtime_root = tmp_path / "Vibe-Skills"
    workspace_root = tmp_path / "bj-refinery"
    _write_runtime_root(runtime_root)
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / ".git").mkdir()
    (workspace_root / "README.md").write_text("# workspace\n", encoding="utf-8")

    decision = resolve_entry_repo_root(
        workspace_root,
        script_anchor=runtime_root / "packages" / "runtime-core" / "src" / "vgo_runtime" / "canonical_entry.py",
    )

    assert decision.repo_root == runtime_root.resolve()
    assert decision.original_repo_root == workspace_root.resolve()
    assert decision.auto_corrected is True
    assert decision.reason_code == "root_role_mismatch_autocorrected"


def test_resolve_entry_repo_root_blocks_when_candidates_are_ambiguous(tmp_path: Path) -> None:
    first_runtime = tmp_path / "install-a"
    second_runtime = tmp_path / "install-b"
    workspace_root = tmp_path / "bj-refinery"
    _write_runtime_root(first_runtime)
    _write_runtime_root(second_runtime)
    workspace_root.mkdir(parents=True, exist_ok=True)

    with pytest.raises(EntryRootGuardError, match="multiple candidate Vibe runtime roots"):
        resolve_entry_repo_root(
            workspace_root,
            script_anchor=first_runtime / "packages" / "runtime-core" / "src" / "vgo_runtime" / "canonical_entry.py",
            installed_runtime_roots=(first_runtime, second_runtime),
        )


def test_resolve_entry_repo_root_uses_dedicated_error_code_for_missing_repo_root() -> None:
    with pytest.raises(EntryRootGuardError) as exc_info:
        resolve_entry_repo_root("   ")

    assert exc_info.value.code == "missing_repo_root"


def test_resolve_entry_repo_root_reports_single_candidate_when_autocorrect_is_skipped(tmp_path: Path) -> None:
    runtime_root = tmp_path / "Vibe-Skills"
    opaque_dir = tmp_path / "opaque-dir"
    _write_runtime_root(runtime_root)
    opaque_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(EntryRootGuardError) as exc_info:
        resolve_entry_repo_root(
            opaque_dir,
            script_anchor=runtime_root / "packages" / "runtime-core" / "src" / "vgo_runtime" / "canonical_entry.py",
        )

    assert exc_info.value.code == "runtime_incomplete"
    assert exc_info.value.candidates == (runtime_root.resolve(),)
    assert "candidate runtime root was found" in str(exc_info.value)
