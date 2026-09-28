from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _gitignore_patterns() -> set[str]:
    lines = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    return {
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_vibeskills_local_state_is_ignored_and_classified() -> None:
    policy = json.loads(
        (REPO_ROOT / "config" / "repo-cleanliness-policy.json").read_text(encoding="utf-8")
    )

    assert ".vibeskills/" in _gitignore_patterns()
    assert ".vibeskills/" in policy["shared_repo_ignores"]
    assert ".vibeskills/" in policy["local_noise_paths"]


def test_current_repo_topology_is_classified_as_managed_workset() -> None:
    policy = json.loads(
        (REPO_ROOT / "config" / "repo-cleanliness-policy.json").read_text(encoding="utf-8")
    )

    managed_roots = set(policy["managed_workset_roots"])
    managed_root_files = set(policy["managed_root_files"])

    expected_roots = {
        ".github/",
        "adapters/",
        "agents/",
        "apps/",
        "commands/",
        "core/",
        "dist/",
        "packages/",
        "rules/",
        "schemas/",
        "templates/",
        "tests/",
        "vendor/",
        "vgo_cli/",
    }
    expected_root_files = {
        "CONTRIBUTING.md",
        "README.zh.md",
        "_python_source_roots.py",
        "pyproject.toml",
        "pytest.ini",
        "logo.png",
        "uninstall.ps1",
        "uninstall.sh",
        "vgo_python_source_roots.py",
    }

    assert expected_roots <= managed_roots
    assert expected_root_files <= managed_root_files
