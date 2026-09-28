from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_public_docs_do_not_present_router_modules_as_current_user_path() -> None:
    public_docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.zh.md",
        REPO_ROOT / "SKILL.md",
    ]

    for path in public_docs:
        content = path.read_text(encoding="utf-8")
        assert "scripts/router/modules" not in content, path


def test_router_readme_names_python_runtime_as_current_routing_owner() -> None:
    content = (REPO_ROOT / "scripts" / "router" / "README.md").read_text(encoding="utf-8")

    required_claims = (
        "Current routing semantic owner",
        "packages/runtime-core/src/vgo_runtime/router_contract_runtime.py",
        "resolve-pack-route.ps1 is a compatibility bridge",
        "Python direct-first",
        "modules/ is legacy/helper/compatibility",
    )
    for claim in required_claims:
        assert claim in content


def test_skill_and_provider_docs_name_python_router_owner_before_bridge() -> None:
    skill_text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    router_text = (REPO_ROOT / "scripts" / "router" / "README.md").read_text(encoding="utf-8")
    skill_claims = (
        "packages/runtime-core/src/vgo_runtime/router_contract_runtime.py",
        "scripts/router/resolve-pack-route.ps1",
        "compatibility bridge",
    )
    router_claims = (
        "Current routing semantic owner: `packages/runtime-core/src/vgo_runtime/router_contract_runtime.py`.",
        "resolve-pack-route.ps1 is a compatibility bridge",
        "modules/ is legacy/helper/compatibility",
    )
    forbidden_claims = (
        "Local installed specialist recommender: `scripts/router/resolve-pack-route.ps1`",
        "The canonical router remains:\n\n- `scripts/router/resolve-pack-route.ps1`",
    )

    for claim in skill_claims:
        assert claim in skill_text
    for claim in router_claims:
        assert claim in router_text
    for content in (skill_text, router_text):
        for claim in forbidden_claims:
            assert claim not in content


def test_runtime_contract_names_python_owner_and_powershell_bridge() -> None:
    contract = json.loads((REPO_ROOT / "config" / "runtime-contract.json").read_text(encoding="utf-8"))
    authority = contract["authority"]

    assert authority["local_installed_skill_recommender"] == "packages/runtime-core/src/vgo_runtime/router_contract_runtime.py"
    assert authority["local_installed_skill_recommender_bridge"] == "scripts/router/resolve-pack-route.ps1"
    assert authority["canonical_router"] == "legacy packet field name only; runtime authority remains vibe"


def test_runtime_protocol_names_python_router_owner_before_bridge() -> None:
    content = (REPO_ROOT / "protocols" / "runtime.md").read_text(encoding="utf-8")

    required_claims = (
        "semantic owner `packages/runtime-core/src/vgo_runtime/router_contract_runtime.py`",
        "compatibility bridge `scripts/router/resolve-pack-route.ps1`",
        "Python direct-first",
    )
    forbidden_claims = (
        "Internal specialist recommender",
        "specialist recommendation logic remains in `scripts/router/resolve-pack-route.ps1`",
    )

    for claim in required_claims:
        assert claim in content
    for claim in forbidden_claims:
        assert claim not in content


def test_orchestration_core_hard_removal_gate_checks_python_owner_before_bridge() -> None:
    content = (REPO_ROOT / "scripts" / "verify" / "vibe-orchestration-core-hard-removal-gate.ps1").read_text(encoding="utf-8")

    assert 'local_installed_skill_recommender' in content
    assert 'local_installed_skill_recommender_bridge' in content
    assert 'packages/runtime-core/src/vgo_runtime/router_contract_runtime.py' in content
    assert 'scripts/router/resolve-pack-route.ps1' in content
    assert 'internal_specialist_recommender' not in content


def test_orchestration_core_hard_removal_gate_runs_cleanly() -> None:
    shell = (
        shutil.which("pwsh")
        or shutil.which("pwsh.exe")
        or shutil.which("powershell")
        or shutil.which("powershell.exe")
    )
    if not shell:
        pytest.skip("PowerShell executable not available")

    gate = REPO_ROOT / "scripts" / "verify" / "vibe-orchestration-core-hard-removal-gate.ps1"
    result = subprocess.run(
        [shell, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(gate)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stdout + result.stderr
