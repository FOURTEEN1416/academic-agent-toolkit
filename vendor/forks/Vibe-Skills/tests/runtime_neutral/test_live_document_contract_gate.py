from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_SRC = REPO_ROOT / "packages" / "contracts" / "src"
INSTALLER_SRC = REPO_ROOT / "packages" / "installer-core" / "src"
GATE_PATH = REPO_ROOT / "scripts" / "verify" / "live-document-gate.py"
if str(CONTRACTS_SRC) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_SRC))
if str(INSTALLER_SRC) not in sys.path:
    sys.path.insert(0, str(INSTALLER_SRC))

from vgo_contracts import (  # noqa: E402
    load_live_governance_contract,
    validate_live_document_workspace,
)
from vgo_installer.simple_skill_installer import install_vibe_skill  # noqa: E402
from tests.runtime_neutral.live_contract_fixtures import (  # noqa: E402
    seed_live_document_workspace,
)
from tests.runtime_neutral.test_agent_skill_organization_contract import (  # noqa: E402
    agent_skill_organization,
    prepare_local_skill_env,
    resolve_powershell,
)


def _load_gate():
    spec = importlib.util.spec_from_file_location("runtime_live_document_gate", GATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {GATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_repo_live_document_contract_is_executable() -> None:
    contract = load_live_governance_contract(REPO_ROOT)

    validated = validate_live_document_workspace(contract, REPO_ROOT)

    assert len(validated) <= 30
    assert contract.proof_retention.pull_request_days == 30
    assert contract.proof_retention.main_and_scheduled_days == 90
    assert contract.proof_retention.formal_release == "github_release"


def test_live_document_gate_rejects_new_unregistered_markdown() -> None:
    gate = _load_gate()

    try:
        gate.evaluate(REPO_ROOT, ["docs/new-unregistered-live-document.md"])
    except ValueError as exc:
        assert "not registered" in str(exc)
    else:
        raise AssertionError("unregistered governed Markdown should fail the gate")


def test_live_document_gate_cli_passes_for_the_current_workspace() -> None:
    completed = subprocess.run(
        [sys.executable, str(GATE_PATH), "--repo-root", str(REPO_ROOT)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    assert '"result": "PASS"' in completed.stdout


def test_live_document_gate_cli_exposes_the_migration_census() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(GATE_PATH),
            "--repo-root",
            str(REPO_ROOT),
            "--census-mode",
            "migration-report",
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["result"] == "PASS"
    assert payload["census_mode"] == "migration-report"
    assert payload["census"]["governed_markdown_count"] == sum(
        payload["census"]["counts"].values()
    )
    assert payload["census"]["counts"]["registered"] <= 30


def test_real_python_and_powershell_runs_use_only_live_contract_workspace(
    tmp_path: Path,
) -> None:
    powershell = resolve_powershell()
    if powershell is None:
        import pytest

        pytest.skip("PowerShell executable not available")

    skills_dir = tmp_path / "skills"
    install_vibe_skill(
        repo_root=REPO_ROOT,
        skills_dir=skills_dir,
        installed_at_utc="2026-08-11T00:00:00Z",
        source_git_commit="live-contract-test",
    )
    installed_root = skills_dir / "vibe"
    organization = agent_skill_organization()
    host_decision = json.dumps(
        {"agent_skill_organization": organization}, ensure_ascii=False
    )
    env = prepare_local_skill_env(tmp_path)
    env.update(
        {
            "VIBESKILLS_TEST_DISABLE_NETWORK": "1",
            "VGO_COMMIT_SHA": "live-contract-test",
        }
    )

    def run_and_assert(workspace: Path, *, python_entry: bool) -> dict[str, object]:
        seed_live_document_workspace(workspace, source_root=REPO_ROOT)
        contract = load_live_governance_contract(workspace)
        before = sorted(
            path.relative_to(workspace).as_posix()
            for path in workspace.rglob("*")
            if path.is_file()
        )
        expected = sorted(
            [
                "config/live-document-contract.json",
                *[document.path for document in contract.documents],
            ]
        )
        assert before == expected
        if python_entry:
            runtime_src = installed_root / "packages" / "runtime-core" / "src"
            contracts_src = installed_root / "packages" / "contracts" / "src"
            python_env = dict(env)
            python_env["PYTHONPATH"] = os.pathsep.join(
                (str(runtime_src), str(contracts_src))
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(runtime_src / "vgo_runtime" / "canonical_entry.py"),
                    "--repo-root",
                    str(installed_root),
                    "--prompt",
                    "Exercise the live-contract-only governed run.",
                    "--host-id",
                    "codex",
                    "--requested-stage-stop",
                    "plan_execute",
                    "--workspace-root",
                    str(workspace),
                    "--artifact-root",
                    str(workspace),
                    "--host-decision-json",
                    host_decision,
                ],
                cwd=installed_root,
                env=python_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=180,
            )
        else:
            completed = subprocess.run(
                [
                    powershell,
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(
                        installed_root
                        / "scripts"
                        / "runtime"
                        / "invoke-vibe-runtime.ps1"
                    ),
                    "-Task",
                    "Exercise the live-contract-only governed run.",
                    "-RunId",
                    "live-contract-powershell",
                    "-RequestedStageStop",
                    "plan_execute",
                    "-HostDecisionJson",
                    host_decision,
                    "-WorkspaceRoot",
                    str(workspace),
                    "-ArtifactRoot",
                    str(workspace),
                ],
                cwd=installed_root,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=180,
            )
        assert completed.returncode == 0, (
            completed.stdout[-4000:] + "\n" + completed.stderr[-4000:]
        )
        run_roots = [
            path
            for path in (workspace / ".vibeskills" / "runs").iterdir()
            if path.is_dir()
        ]
        assert run_roots
        manifest = json.loads(
            (run_roots[-1] / "manifest.json").read_text(encoding="utf-8")
        )
        assert set(manifest["artifacts"]) >= {
            "requirement",
            "plan",
            "status",
            "proof",
        }
        assert manifest["commit_sha"] == "live-contract-test"
        assert manifest["execution_environment"]
        for relative_path in manifest["artifacts"].values():
            assert (run_roots[-1] / relative_path).is_file()
        assert not (workspace / "docs" / "requirements").exists()
        assert not (workspace / "docs" / "plans").exists()
        assert manifest["legacy_compatibility"]["mode"] == "disabled"
        assert manifest["legacy_compatibility"]["writes"] == []
        return manifest

    powershell_manifest = run_and_assert(
        tmp_path / "powershell-workspace",
        python_entry=False,
    )
    python_manifest = run_and_assert(
        tmp_path / "python-workspace",
        python_entry=True,
    )
    assert set(powershell_manifest["artifacts"]) >= set(python_manifest["artifacts"])
