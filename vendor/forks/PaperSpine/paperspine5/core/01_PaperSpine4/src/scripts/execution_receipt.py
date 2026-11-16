#!/usr/bin/env python3
"""Record and verify hash-bound receipts for expensive PaperSpine operations.

The receipt is intentionally generic: a renderer, citation audit, conversion,
or other deterministic operation can be reused only when its operation name,
tool identity, complete input snapshot, and complete output snapshot are exact.
It never turns a computational cache hit into scientific or visual readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTRACT = "paperspine.execution-receipt"
SCHEMA_VERSION = "1.0"
REUSABLE = 0
MISS = 3
ERROR = 2


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_path(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if resolved.is_symlink():
        raise ValueError(f"links are not valid receipt inputs or outputs: {resolved}")
    if resolved.is_file():
        return {
            "path": str(resolved),
            "kind": "file",
            "size_bytes": resolved.stat().st_size,
            "sha256": sha256_file(resolved),
        }
    if not resolved.is_dir():
        raise FileNotFoundError(str(resolved))

    members: list[dict[str, Any]] = []
    for member in sorted(resolved.rglob("*"), key=lambda item: item.relative_to(resolved).as_posix()):
        if member.is_symlink():
            raise ValueError(f"links are not valid receipt members: {member}")
        if not member.is_file():
            continue
        members.append(
            {
                "path": member.relative_to(resolved).as_posix(),
                "size_bytes": member.stat().st_size,
                "sha256": sha256_file(member),
            }
        )
    canonical = json.dumps(members, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "path": str(resolved),
        "kind": "directory",
        "file_count": len(members),
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "members": members,
    }


def snapshot_many(paths: list[Path]) -> list[dict[str, Any]]:
    if not paths:
        raise ValueError("at least one path is required")
    resolved = [path.expanduser().resolve() for path in paths]
    if len({str(path).casefold() for path in resolved}) != len(resolved):
        raise ValueError("duplicate paths are not allowed")
    return [snapshot_path(path) for path in resolved]


def build_receipt(
    operation: str,
    tool_identity: str,
    inputs: list[Path],
    outputs: list[Path],
) -> dict[str, Any]:
    if not operation.strip() or not tool_identity.strip():
        raise ValueError("operation and tool identity must be non-empty")
    return {
        "contract": CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "operation": operation.strip(),
        "tool_identity": tool_identity.strip(),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "inputs": snapshot_many(inputs),
        "outputs": snapshot_many(outputs),
        "scientific_readiness_inferred": False,
        "visual_readiness_inferred": False,
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def verify_receipt(
    receipt_path: Path,
    operation: str,
    tool_identity: str,
    inputs: list[Path],
    outputs: list[Path],
) -> tuple[bool, list[str]]:
    findings: list[str] = []
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return False, ["receipt does not exist"]
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"receipt is unreadable: {exc}"]
    if not isinstance(receipt, dict):
        return False, ["receipt must be a JSON object"]
    if receipt.get("contract") != CONTRACT or receipt.get("schema_version") != SCHEMA_VERSION:
        findings.append("receipt contract or schema version differs")
    if receipt.get("operation") != operation.strip():
        findings.append("operation differs")
    if receipt.get("tool_identity") != tool_identity.strip():
        findings.append("tool identity differs")
    try:
        current_inputs = snapshot_many(inputs)
        current_outputs = snapshot_many(outputs)
    except (FileNotFoundError, OSError, ValueError) as exc:
        findings.append(f"current snapshot is incomplete: {exc}")
        return False, findings
    if receipt.get("inputs") != current_inputs:
        findings.append("input snapshot differs")
    if receipt.get("outputs") != current_outputs:
        findings.append("output snapshot differs")
    return not findings, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record or verify an exact hash-bound PaperSpine execution receipt."
    )
    parser.add_argument("action", choices=("record", "check"))
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--tool", dest="tool_identity", required=True)
    parser.add_argument("--input", dest="inputs", type=Path, action="append", required=True)
    parser.add_argument("--output", dest="outputs", type=Path, action="append", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.action == "record":
            payload = build_receipt(args.operation, args.tool_identity, args.inputs, args.outputs)
            atomic_write_json(args.receipt, payload)
            result = {"status": "RECORDED", "reusable": True, "receipt": str(args.receipt.resolve())}
            code = REUSABLE
        else:
            reusable, findings = verify_receipt(
                args.receipt,
                args.operation,
                args.tool_identity,
                args.inputs,
                args.outputs,
            )
            result = {
                "status": "REUSABLE" if reusable else "MISS",
                "reusable": reusable,
                "receipt": str(args.receipt.resolve()),
                "findings": findings,
            }
            code = REUSABLE if reusable else MISS
    except (FileNotFoundError, OSError, ValueError) as exc:
        result = {"status": "ERROR", "reusable": False, "error": str(exc)}
        code = ERROR
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["status"])
        for finding in result.get("findings", []):
            print(f"- {finding}")
        if result.get("error"):
            print(f"- {result['error']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
