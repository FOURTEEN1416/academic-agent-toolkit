"""Read-only diagnostics for a PaperSpine updater successor chain.

This module deliberately does not install, rollback, or edit updater state.  It
turns a malformed history into a deterministic, reviewable recovery plan that
can then be executed through the official :class:`UserUpdateManager` one
operation at a time.  The installed-suite successor resolver remains the final
authority because this diagnostic does not verify bytes or receipts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _edges(state: dict[str, Any], install_kind: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(state.get("history", [])):
        if not isinstance(item, dict) or item.get("rolled_back") is True:
            continue
        placements = [
            placement
            for placement in item.get("placements", [])
            if isinstance(placement, dict) and placement.get("kind") == install_kind
        ]
        if len(placements) != 1:
            continue
        previous = placements[0].get("previous")
        previous_build = previous.get("build_id") if isinstance(previous, dict) else None
        candidate = item.get("candidate_build_id")
        if not isinstance(candidate, str) or not isinstance(previous_build, str):
            continue
        result.append(
            {
                "history_index": index,
                "operation_id": item.get("operation_id"),
                "source_build_id": previous_build,
                "target_build_id": candidate,
                "rolled_back": False,
            }
        )
    return result


def diagnose(
    control_root: str | Path,
    *,
    install_kind: str,
    source_build_id: str,
    target_build_id: str,
) -> dict[str, Any]:
    """Return a deterministic, read-only chain status and recovery plan."""

    control = Path(control_root).expanduser().resolve()
    state_path = control / "user-update-state.json"
    state = _read_json(state_path)
    active = state.get("active_installations")
    active_build = (
        active[0].get("build_id")
        if isinstance(active, list) and len(active) == 1 and isinstance(active[0], dict)
        else None
    )
    result: dict[str, Any] = {
        "contract": "paperspine5.authority-chain-diagnostic",
        "schema_version": "1.0",
        "install_kind": install_kind,
        "source_build_id": source_build_id,
        "target_build_id": target_build_id,
        "active_build_id": active_build,
        "external_action_authorized": False,
        "read_only": True,
        "status": "BLOCKED",
        "chain": [],
        "blockers": [],
        "rollback_operations": [],
    }
    if install_kind not in {"skill", "plugin"}:
        result["blockers"].append({"code": "INSTALL_KIND_INVALID"})
        return result
    if active_build != target_build_id:
        result["blockers"].append(
            {
                "code": "ACTIVE_TARGET_MISMATCH",
                "expected": target_build_id,
                "observed": active_build,
            }
        )
        return result

    edges = _edges(state, install_kind)
    cursor = target_build_id
    before_index = len(state.get("history", []))
    seen = {cursor}
    selected: list[dict[str, Any]] = []
    cycle_nodes: set[str] = set()
    while cursor != source_build_id:
        candidates = [
            edge
            for edge in edges
            if edge["target_build_id"] == cursor and edge["history_index"] < before_index
        ]
        if not candidates:
            result["blockers"].append(
                {"code": "NO_FORWARD_CHAIN", "unreached_source": source_build_id, "at": cursor}
            )
            break
        edge = max(candidates, key=lambda item: item["history_index"])
        previous = edge["source_build_id"]
        if previous in seen:
            cycle_nodes = set(seen)
            cycle_nodes.add(previous)
            result["blockers"].append(
                {
                    "code": "FORWARD_CHAIN_CYCLE",
                    "at": cursor,
                    "repeated": previous,
                    "cycle_nodes": sorted(cycle_nodes),
                }
            )
            break
        selected.append(edge)
        seen.add(previous)
        cursor = previous
        before_index = edge["history_index"]
    else:
        chain = list(reversed(selected))
        result["status"] = "PASS"
        result["chain"] = chain
        return result

    if cycle_nodes:
        # Do not propose rolling back an older, valid forward edge merely
        # because its endpoints happen to be members of the cycle.  Walk the
        # history from the requested source and locate the first operation
        # that reverses the currently established cursor (or otherwise
        # switches direction inside the cycle).  Only operations at and after
        # that corruption point are candidates, in newest-first order.  This
        # mirrors the official updater's latest-operation rollback discipline
        # while keeping the diagnostic read-only.
        cycle_start: int | None = None
        cursor = source_build_id
        visited_cursors: set[str] = {cursor}
        for edge in sorted(edges, key=lambda item: item["history_index"]):
            source = edge["source_build_id"]
            target = edge["target_build_id"]
            if source == cursor:
                if target in visited_cursors and target in cycle_nodes:
                    cycle_start = edge["history_index"]
                    break
                cursor = target
                visited_cursors.add(cursor)
                continue
            if (
                target == cursor
                and source in cycle_nodes
                and target in cycle_nodes
            ) or (
                cursor in cycle_nodes
                and source in cycle_nodes
                and target in cycle_nodes
                and source != cursor
            ):
                cycle_start = edge["history_index"]
                break
        if cycle_start is None:
            # A malformed branch may not expose a clean cursor reversal.  In
            # that case, fall back to the oldest selected cycle edge; this is
            # still finite and deterministic, and remains reviewable before
            # any official rollback is attempted.
            cycle_start = min(
                edge["history_index"]
                for edge in edges
                if edge["source_build_id"] in cycle_nodes
                and edge["target_build_id"] in cycle_nodes
            )
        result["rollback_operations"] = [
            edge["operation_id"]
            for edge in sorted(edges, key=lambda item: item["history_index"], reverse=True)
            if edge["history_index"] >= cycle_start
            if edge["target_build_id"] in cycle_nodes
            and edge["source_build_id"] in cycle_nodes
            and isinstance(edge.get("operation_id"), str)
        ]
    result["chain"] = list(reversed(selected))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only PaperSpine updater-chain diagnostic")
    parser.add_argument("--control-root", required=True)
    parser.add_argument("--install-kind", choices=("skill", "plugin"), required=True)
    parser.add_argument("--source-build-id", required=True)
    parser.add_argument("--target-build-id", required=True)
    args = parser.parse_args()
    try:
        payload = diagnose(
            args.control_root,
            install_kind=args.install_kind,
            source_build_id=args.source_build_id,
            target_build_id=args.target_build_id,
        )
    except Exception as exc:
        payload = {
            "contract": "paperspine5.authority-chain-diagnostic",
            "schema_version": "1.0",
            "status": "BLOCKED",
            "external_action_authorized": False,
            "read_only": True,
            "blockers": [{"code": "DIAGNOSTIC_INPUT_INVALID", "message": str(exc)}],
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
