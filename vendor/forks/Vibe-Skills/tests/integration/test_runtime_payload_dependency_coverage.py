from __future__ import annotations

import json
from pathlib import Path

from tests.issue_167_runtime_surfaces import ISSUE_167_MANAGED_RUNTIME_SURFACES


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_json(relpath: str) -> dict:
    return json.loads((REPO_ROOT / relpath).read_text(encoding="utf-8"))


def _expanded_runtime_payload() -> tuple[set[str], set[str]]:
    governance = _load_json("config/version-governance.json")
    packaging = governance["packaging"]
    payload = packaging["runtime_payload"]

    files = {str(path).replace("\\", "/").strip("/") for path in payload.get("files") or []}
    directories = {str(path).replace("\\", "/").strip("/") for path in payload.get("directories") or []}
    for manifest_entry in packaging.get("manifests") or []:
        manifest = _load_json(str(manifest_entry["path"]))
        files.update(str(path).replace("\\", "/").strip("/") for path in manifest.get("files") or [])
        directories.update(str(path).replace("\\", "/").strip("/") for path in manifest.get("directories") or [])
    return files, directories


def _payload_covers(relpath: str, files: set[str], directories: set[str]) -> bool:
    normalized = relpath.replace("\\", "/").strip("/")
    if normalized in files:
        return True
    return any(normalized == directory or normalized.startswith(f"{directory}/") for directory in directories)


def test_expanded_runtime_payload_covers_governed_runtime_dependency_surfaces() -> None:
    files, directories = _expanded_runtime_payload()
    required = [
        *ISSUE_167_MANAGED_RUNTIME_SURFACES,
        "scripts/runtime/Invoke-VibeCanonicalEntry.ps1",
        "scripts/verify/vibe-canonical-entry-truth-gate.ps1",
        "config/plugins-manifest.codex.json",
        "config/vibe-entry-surfaces.json",
        "config/secrets-policy.json",
        "config/tool-registry.json",
        "adapters/index.json",
        "adapters/codex/settings-map.json",
        "adapters/claude-code/settings-map.json",
    ]

    missing = [path for path in required if not _payload_covers(path, files, directories)]
    assert missing == [], f"expanded runtime payload is missing governed dependency surfaces: {missing}"


def test_runtime_script_manifest_includes_issue_167_governed_verify_gates() -> None:
    manifest = _load_json("config/runtime-script-manifest.json")
    expected = {
        "scripts/verify/vibe-canonical-entry-truth-gate.ps1",
        "scripts/verify/vibe-no-silent-fallback-contract-gate.ps1",
        "scripts/verify/vibe-no-self-introduced-fallback-gate.ps1",
        "scripts/verify/vibe-release-truth-consistency-gate.ps1",
    }

    assert expected <= set(manifest["files"])
    assert expected <= set(manifest["role_groups"]["files"]["verification_gates"])


def test_runtime_config_manifest_includes_issue_167_operator_preview_contract() -> None:
    manifest = _load_json("config/runtime-config-manifest.json")

    assert "config/operator-preview-contract.json" in set(manifest["files"])
    assert "config/operator-preview-contract.json" in set(manifest["role_groups"]["files"]["runtime_governance_files"])
