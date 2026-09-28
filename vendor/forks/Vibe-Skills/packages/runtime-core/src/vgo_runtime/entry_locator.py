from __future__ import annotations

import argparse
import json
from pathlib import Path


CHANGE_KIND_TO_CAPABILITY = {
    "task-understanding": "task_understanding",
    "planning": "plan_construction",
    "execution": "execution",
    "verification": "verification",
    "local-skill-extension": "local_skill_extension",
}


CHANGE_KIND_TO_VERIFICATION = {
    "task-understanding": {
        "recommended_test_targets": [
            "tests/unit/test_local_kernel_planning.py",
        ],
        "focused_test_command": "py -3 -m pytest tests/unit/test_local_kernel_planning.py -q",
    },
    "planning": {
        "recommended_test_targets": [
            "tests/unit/test_local_kernel_planning.py",
        ],
        "focused_test_command": "py -3 -m pytest tests/unit/test_local_kernel_planning.py -q",
    },
    "execution": {
        "recommended_test_targets": [
            "tests/unit/test_local_kernel_execution.py",
        ],
        "focused_test_command": "py -3 -m pytest tests/unit/test_local_kernel_execution.py -q",
    },
    "verification": {
        "recommended_test_targets": [
            "tests/unit/test_local_kernel_execution.py",
        ],
        "focused_test_command": "py -3 -m pytest tests/unit/test_local_kernel_execution.py -q",
    },
    "local-skill-extension": {
        "recommended_test_targets": [
            "tests/unit/test_local_skill_index.py",
            "tests/unit/test_local_kernel_planning.py",
        ],
        "focused_test_command": (
            "py -3 -m pytest "
            "tests/unit/test_local_skill_index.py "
            "tests/unit/test_local_kernel_planning.py -q"
        ),
    },
}


def _load_boundary_payload(repo_root: Path) -> dict[str, object]:
    payload = json.loads((repo_root / "config" / "kernel-boundary-demotion-matrix.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("kernel boundary payload must be a JSON object")
    return payload


def locate_iteration_entry(*, repo_root: Path, change_kind: str) -> dict[str, object]:
    normalized_change_kind = str(change_kind).strip()
    capability = CHANGE_KIND_TO_CAPABILITY.get(normalized_change_kind)
    if capability is None:
        raise ValueError(f"unsupported change kind {change_kind!r}")

    payload = _load_boundary_payload(repo_root.resolve())
    boundaries = payload.get("capability_boundaries", [])
    if not isinstance(boundaries, list):
        raise ValueError("kernel boundary payload must contain capability_boundaries list")

    for raw_entry in boundaries:
        if not isinstance(raw_entry, dict):
            continue
        if str(raw_entry.get("capability") or "") != capability:
            continue
        primary_entry_file = str(raw_entry.get("primary_entry_file") or "").strip()
        if not primary_entry_file:
            raise ValueError(f"capability {capability!r} does not declare a primary entry file")
        verification_hint = CHANGE_KIND_TO_VERIFICATION.get(normalized_change_kind) or {}
        return {
            "change_kind": normalized_change_kind,
            "capability": capability,
            "primary_entry_file": primary_entry_file,
            "authority_layer": str(raw_entry.get("authority_layer") or ""),
            "steady_state_contract": str(raw_entry.get("steady_state_contract") or ""),
            "demoted_layers": list(raw_entry.get("demoted_layers") or []),
            "recommended_test_targets": list(verification_hint.get("recommended_test_targets") or []),
            "focused_test_command": str(verification_hint.get("focused_test_command") or "").strip(),
        }

    raise ValueError(f"capability {capability!r} not found in boundary map")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--change-kind", required=True, choices=tuple(CHANGE_KIND_TO_CAPABILITY))
    args = parser.parse_args(argv)

    payload = locate_iteration_entry(
        repo_root=Path(args.repo_root),
        change_kind=args.change_kind,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
