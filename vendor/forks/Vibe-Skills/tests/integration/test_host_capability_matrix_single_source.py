from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_ROOT = REPO_ROOT / "adapters"
REGISTRY_CONFIG_PATH = REPO_ROOT / "config" / "adapter-registry.json"
REGISTRY_INDEX_PATH = REPO_ROOT / "adapters" / "index.json"
SUPPORTED_CANONICAL_HOSTS = ("codex", "claude-code", "opencode")


def _read_host_profiles() -> list[dict[str, object]]:
    profiles: list[dict[str, object]] = []
    for path in sorted(ADAPTER_ROOT.glob("*/host-profile.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["profile_path"] = path.relative_to(REPO_ROOT).as_posix()
        profiles.append(data)
    return profiles


def _read_registry(path: Path) -> dict[str, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(adapter["id"]): dict(adapter) for adapter in payload["adapters"]}


def test_host_capability_contract_has_unique_machine_rows() -> None:
    profiles = _read_host_profiles()
    adapter_ids = [str(profile["adapter_id"]) for profile in profiles]
    host_names = [str(profile["host_name"]) for profile in profiles]

    assert len(adapter_ids) == len(set(adapter_ids)), "duplicate adapter ids in host profiles"
    assert len(host_names) == len(set(host_names)), "duplicate host names in host profiles"


def test_host_capability_contract_matches_adapter_registry_on_disk() -> None:
    profiles = {str(profile["adapter_id"]): profile for profile in _read_host_profiles()}
    registry = _read_registry(REGISTRY_INDEX_PATH)

    # Generic is intentionally advisory-only and has no adapter-registry row.
    assert set(profiles) == set(registry) | {"generic"}
    for adapter_id, profile in profiles.items():
        if adapter_id == "generic":
            assert profile["status"] == "advisory-only"
            continue
        row = registry[adapter_id]
        assert profile["status"] == row["status"], f"status mismatch for {adapter_id}"
        assert profile["profile_path"] == row["host_profile"], f"profile path mismatch for {adapter_id}"


def test_adapter_registry_mirrors_stay_in_sync_for_canonical_vibe_contracts() -> None:
    config_registry = _read_registry(REGISTRY_CONFIG_PATH)
    index_registry = _read_registry(REGISTRY_INDEX_PATH)
    assert set(config_registry) == set(index_registry)

    for host_id in SUPPORTED_CANONICAL_HOSTS:
        assert config_registry[host_id]["canonical_vibe"] == index_registry[host_id]["canonical_vibe"], host_id


def test_supported_hosts_freeze_runtime_backed_canonical_vibe_contract() -> None:
    registry = _read_registry(REGISTRY_INDEX_PATH)
    expected = {
        "codex": {"entry_mode": "direct_runtime", "launcher_kind": "native_command", "supports_bounded_stop": True},
        "claude-code": {"entry_mode": "bridged_runtime", "launcher_kind": "managed_bridge", "supports_bounded_stop": True},
        "opencode": {"entry_mode": "bridged_runtime", "launcher_kind": "managed_bridge", "supports_bounded_stop": True},
    }

    for host_id, contract_expectation in expected.items():
        canonical_vibe = registry[host_id].get("canonical_vibe") or {}
        assert canonical_vibe.get("entry_mode") == contract_expectation["entry_mode"], host_id
        assert canonical_vibe.get("launcher_kind") == contract_expectation["launcher_kind"], host_id
        assert canonical_vibe.get("fallback_policy") == "blocked", host_id
        assert canonical_vibe.get("allow_skill_doc_fallback") is False, host_id
        assert canonical_vibe.get("proof_required") is True, host_id
        assert canonical_vibe.get("supports_bounded_stop") == contract_expectation["supports_bounded_stop"], host_id
