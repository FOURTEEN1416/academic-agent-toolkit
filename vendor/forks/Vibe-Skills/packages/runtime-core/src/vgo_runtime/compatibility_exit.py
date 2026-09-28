from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _boundary_path(repo_root: Path) -> Path:
    return repo_root / "config" / "kernel-boundary-demotion-matrix.json"


def summarize_compatibility_exit(*, repo_root: Path) -> dict[str, object]:
    resolved_repo_root = repo_root.resolve()
    boundary_payload = _load_json(_boundary_path(resolved_repo_root))
    policy_payload = boundary_payload.get("compatibility_exit_policy", {})
    if not isinstance(policy_payload, dict):
        raise ValueError("kernel boundary payload must contain compatibility_exit_policy object")

    boundaries = boundary_payload.get("capability_boundaries", [])
    if not isinstance(boundaries, list):
        raise ValueError("kernel boundary payload must contain capability_boundaries list")
    boundary_index = {
        str(entry["capability"]): entry
        for entry in boundaries
        if isinstance(entry, dict) and entry.get("capability")
    }

    controlled_capabilities = policy_payload.get("controlled_capabilities", [])
    if not isinstance(controlled_capabilities, list):
        raise ValueError("compatibility exit policy must contain controlled_capabilities list")
    non_negotiable_rules = policy_payload.get("non_negotiable_rules", [])
    if not isinstance(non_negotiable_rules, list):
        raise ValueError("compatibility exit policy must contain non_negotiable_rules list")
    phase_deletion_budgets = policy_payload.get("phase_deletion_budgets", [])
    if not isinstance(phase_deletion_budgets, list):
        raise ValueError("compatibility exit policy must contain phase_deletion_budgets list")

    controlled_entries: list[dict[str, object]] = []
    for raw_entry in controlled_capabilities:
        if not isinstance(raw_entry, dict):
            continue
        capability = str(raw_entry.get("capability") or "").strip()
        boundary_entry = boundary_index.get(capability)
        if boundary_entry is None:
            raise ValueError(f"controlled capability {capability!r} is missing from the boundary map")
        expected_layer = str(raw_entry.get("authority_layer") or "").strip()
        actual_layer = str(boundary_entry.get("authority_layer") or "").strip()
        if expected_layer != actual_layer:
            raise ValueError(
                f"controlled capability {capability!r} expects authority layer {expected_layer!r} but boundary map declares {actual_layer!r}"
            )
        controlled_entries.append(
            {
                "capability": capability,
                "authority_layer": actual_layer,
                "primary_entry_file": str(boundary_entry.get("primary_entry_file") or ""),
                "steady_state_contract": str(boundary_entry.get("steady_state_contract") or ""),
                "kernel_owner_capabilities": list(raw_entry.get("kernel_owner_capabilities") or []),
                "allowed_change_roles": list(raw_entry.get("allowed_change_roles") or []),
                "deletion_target_phase": str(raw_entry.get("deletion_target_phase") or ""),
                "demoted_layers": list(boundary_entry.get("demoted_layers") or []),
            }
        )

    return {
        "policy_version": policy_payload.get("version"),
        "purpose": str(policy_payload.get("purpose") or ""),
        "non_negotiable_rules": non_negotiable_rules,
        "controlled_capabilities": controlled_entries,
        "phase_deletion_budgets": phase_deletion_budgets,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args(argv)

    payload = summarize_compatibility_exit(repo_root=Path(args.repo_root))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
