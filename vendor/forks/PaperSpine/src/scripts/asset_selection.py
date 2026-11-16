#!/usr/bin/env python3
"""Select the newest relevant project-local scientific asset with an audit receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
CONTRACT = "paperspine.asset-selection-request"
RECEIPT_CONTRACT = "paperspine.asset-selection-receipt"
ASSET_KINDS = {"data", "figure", "table", "code", "source", "other"}


@dataclass
class SelectionResult:
    request_path: str
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    receipt: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.findings

    def payload(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": "PASS" if self.ok else "BLOCKED",
            "request_path": self.request_path,
            "findings": list(dict.fromkeys(self.findings)),
            "warnings": list(dict.fromkeys(self.warnings)),
            "receipt": self.receipt,
        }


def _load_json(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"Cannot read selection request {path}: {exc}"
    if not isinstance(value, dict):
        return {}, "Selection request root must be an object."
    return value, None


def _resolve(base: Path, raw: object) -> Path:
    value = Path(str(raw))
    return (value if value.is_absolute() else base / value).resolve()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _inside(path: Path, roots: list[Path]) -> bool:
    return any(path == root or path.is_relative_to(root) for root in roots)


def _identity(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _path_key(path: str) -> tuple[str, str]:
    return os.path.normcase(path), path


def _mtime_iso(mtime_ns: int) -> str:
    return (
        datetime.fromtimestamp(mtime_ns / 1_000_000_000, timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def select_assets(request_path: str | Path) -> SelectionResult:
    path = Path(request_path).resolve()
    result = SelectionResult(str(path))
    request, error = _load_json(path)
    if error:
        result.findings.append(error)
        return result
    if request.get("contract") != CONTRACT:
        result.findings.append(f"contract must be {CONTRACT}.")
    if str(request.get("schema_version")) != SCHEMA_VERSION:
        result.findings.append(f"schema_version must be {SCHEMA_VERSION}.")

    project_root_raw = request.get("project_root")
    if not isinstance(project_root_raw, str) or not project_root_raw.strip():
        result.findings.append("project_root must be a non-empty path string.")
        return result
    project_root = _resolve(path.parent, project_root_raw)
    if not project_root.is_dir():
        result.findings.append(f"project_root does not exist: {project_root}")
        return result
    if not path.is_relative_to(project_root):
        result.findings.append(f"Selection request must stay inside project_root: {path}")

    roots_raw = request.get("allowed_roots")
    if not isinstance(roots_raw, list) or not roots_raw:
        result.findings.append("allowed_roots must list project/materials roots.")
        return result
    allowed_roots: list[Path] = []
    for index, raw in enumerate(roots_raw, start=1):
        root = _resolve(project_root, raw)
        if not root.is_relative_to(project_root):
            result.findings.append(f"allowed_roots[{index}] escapes project_root: {root}")
        elif not root.is_dir():
            result.findings.append(f"allowed_roots[{index}] does not exist: {root}")
        else:
            allowed_roots.append(root)
    if not allowed_roots:
        return result

    selections = request.get("selections")
    if not isinstance(selections, list) or not selections:
        result.findings.append("selections must contain at least one scientific asset identity.")
        return result

    seen_ids: set[str] = set()
    selection_receipts: list[dict[str, Any]] = []
    for selection_index, selection in enumerate(selections, start=1):
        label = f"selections[{selection_index}]"
        if not isinstance(selection, dict):
            result.findings.append(f"{label} must be an object.")
            continue
        selection_id = str(selection.get("id") or "").strip()
        identity = str(selection.get("scientific_identity") or "").strip()
        kind = str(selection.get("asset_kind") or "").strip().lower()
        if not selection_id:
            result.findings.append(f"{label}.id is required.")
        elif selection_id in seen_ids:
            result.findings.append(f"Duplicate selection id: {selection_id}")
        else:
            seen_ids.add(selection_id)
        if not identity:
            result.findings.append(f"{label}.scientific_identity is required.")
        if kind not in ASSET_KINDS:
            result.findings.append(f"{label}.asset_kind must be one of {sorted(ASSET_KINDS)}.")

        candidates = selection.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            result.findings.append(f"{label}.candidates must not be empty.")
            candidates = []
        candidate_receipts: list[dict[str, Any]] = []
        for candidate_index, candidate in enumerate(candidates, start=1):
            candidate_label = f"{label}.candidates[{candidate_index}]"
            if not isinstance(candidate, dict):
                result.findings.append(f"{candidate_label} must be an object.")
                continue
            raw_path = candidate.get("path")
            candidate_identity = str(candidate.get("scientific_identity") or "").strip()
            candidate_kind = str(candidate.get("asset_kind") or "").strip().lower()
            resolved = _resolve(project_root, raw_path) if raw_path else project_root / "<missing>"
            exclusion_reasons: list[str] = []
            if not raw_path:
                exclusion_reasons.append("missing_path")
            if not resolved.is_relative_to(project_root) or not _inside(resolved, allowed_roots):
                exclusion_reasons.append("outside_allowed_roots")
            if not resolved.is_file():
                exclusion_reasons.append("missing_file")
            if _identity(candidate_identity) != _identity(identity):
                exclusion_reasons.append("scientific_identity_mismatch")
            if candidate_kind != kind:
                exclusion_reasons.append("asset_kind_mismatch")
            record: dict[str, Any] = {
                "path": _relative(resolved, project_root),
                "scientific_identity": candidate_identity,
                "asset_kind": candidate_kind,
                "eligible": not exclusion_reasons,
                "exclusion_reasons": exclusion_reasons,
                "selected": False,
            }
            if resolved.is_file():
                stat = resolved.stat()
                record.update(
                    {
                        "mtime_ns": stat.st_mtime_ns,
                        "mtime_utc": _mtime_iso(stat.st_mtime_ns),
                        "size_bytes": stat.st_size,
                        "sha256": _sha256(resolved),
                    }
                )
            candidate_receipts.append(record)
            if "outside_allowed_roots" in exclusion_reasons:
                result.warnings.append(f"{candidate_label} was excluded because it is outside allowed_roots.")

        eligible = [item for item in candidate_receipts if item["eligible"]]
        eligible.sort(key=lambda item: (-int(item["mtime_ns"]), *_path_key(str(item["path"]))))
        explicit_raw = selection.get("explicit_selection")
        selected: dict[str, Any] | None = None
        reason = ""
        tie_break = "not_needed"
        if explicit_raw:
            explicit_path = _resolve(project_root, explicit_raw)
            matches = [
                item
                for item in candidate_receipts
                if _resolve(project_root, item["path"]) == explicit_path
            ]
            if not matches:
                result.findings.append(f"{label}.explicit_selection is not listed as a candidate: {explicit_raw}")
            elif not matches[0]["eligible"]:
                result.findings.append(
                    f"{label}.explicit_selection is ineligible: {matches[0]['exclusion_reasons']}"
                )
            else:
                selected = matches[0]
                reason = "explicit_user_selection_overrides_automatic_timestamp_ranking"
        elif eligible:
            selected = eligible[0]
            reason = "automatic_latest_relevant_candidate_by_mtime_ns"
            tied = [item for item in eligible if item["mtime_ns"] == selected["mtime_ns"]]
            if len(tied) > 1:
                tie_break = "mtime_ns_tie_resolved_by_lexical_project_relative_path"
                reason += "_with_lexical_path_tie_break"
        else:
            result.findings.append(f"{label} has no eligible candidate after identity, kind, and root checks.")
        if selected is not None:
            selected["selected"] = True

        selection_receipts.append(
            {
                "id": selection_id,
                "scientific_identity": identity,
                "asset_kind": kind,
                "explicit_selection": str(explicit_raw) if explicit_raw else None,
                "selected_path": selected["path"] if selected else None,
                "selection_reason": reason or "no_eligible_selection",
                "tie_break": tie_break,
                "ranking_policy": "eligible candidates sorted by descending mtime_ns, then lexical project-relative path",
                "candidates": candidate_receipts,
            }
        )

    result.receipt = {
        "contract": RECEIPT_CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "project_root": ".",
        "allowed_roots": [_relative(root, project_root) or "." for root in allowed_roots],
        "selection_policy": {
            "relevance_gate": "exact normalized scientific_identity and asset_kind match",
            "path_gate": "candidate must be a file inside project_root and one allowed_root",
            "precedence": ["explicit_user_selection", "newest_mtime_ns", "lexical_project_relative_path"],
        },
        "selections": selection_receipts,
    }
    return result


def verify_selection_receipt(
    request_path: str | Path,
    receipt_path: str | Path,
) -> SelectionResult:
    """Recompute selection from current files and reject any stale receipt."""
    current = select_assets(request_path)
    path = Path(receipt_path).resolve()
    try:
        stored = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        current.findings.append(f"Cannot read asset selection receipt {path}: {exc}")
        return current
    if not isinstance(stored, dict):
        current.findings.append("Asset selection receipt root must be an object.")
        return current
    if stored.get("status") != "PASS" or stored.get("ok") is not True:
        current.findings.append("Stored asset selection receipt is not PASS.")
    stored_receipt = stored.get("receipt")
    if not isinstance(stored_receipt, dict):
        current.findings.append("Stored asset selection receipt payload is missing.")
    elif stored_receipt != current.receipt:
        current.findings.append(
            "Asset selection receipt is stale: candidate identity, timestamp, size, hash, "
            "eligibility, or selected path differs from the current project files."
        )
    return current


def receipt_markdown(payload: dict[str, Any]) -> str:
    receipt = payload.get("receipt", {})
    lines = [
        "# Asset Selection Receipt",
        "",
        f"- Status: {payload.get('status')}",
        "- Policy: explicit selection; otherwise newest eligible mtime_ns; lexical path tie-break",
        "",
    ]
    for selection in receipt.get("selections", []):
        lines.extend(
            [
                f"## {selection.get('id')}",
                "",
                f"- Scientific identity: `{selection.get('scientific_identity')}`",
                f"- Selected: `{selection.get('selected_path')}`",
                f"- Reason: `{selection.get('selection_reason')}`",
                f"- Tie-break: `{selection.get('tie_break')}`",
                "",
                "| Candidate | mtime ns | Modified UTC | Eligible | Selected | Exclusion reasons |",
                "|---|---:|---|---|---|---|",
            ]
        )
        for candidate in selection.get("candidates", []):
            reasons = ", ".join(candidate.get("exclusion_reasons", [])) or "—"
            lines.append(
                f"| `{candidate.get('path')}` | {candidate.get('mtime_ns', '—')} | "
                f"{candidate.get('mtime_utc', '—')} | {candidate.get('eligible')} | "
                f"{candidate.get('selected')} | {reasons} |"
            )
        lines.append("")
    lines.extend(["## Findings", ""])
    findings = payload.get("findings", [])
    if findings:
        lines.extend(f"- {item}" for item in findings)
    else:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    warnings = payload.get("warnings", [])
    if warnings:
        lines.extend(f"- {item}" for item in warnings)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select newest relevant project-local scientific assets.")
    parser.add_argument("request", type=Path, help="asset_selection_request.json")
    parser.add_argument("--output-dir", type=Path, help="Write receipt JSON/Markdown here.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument(
        "--verify-receipt",
        type=Path,
        help="Recompute the request and compare it with an existing receipt JSON.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = (
        verify_selection_receipt(args.request, args.verify_receipt)
        if args.verify_receipt
        else select_assets(args.request)
    )
    if args.output_dir:
        output_dir = args.output_dir.resolve()
        request, error = _load_json(args.request.resolve())
        project_root = _resolve(args.request.resolve().parent, request.get("project_root")) if not error else None
        if project_root is None or not output_dir.is_relative_to(project_root):
            result.findings.append(f"output_dir must stay inside project_root: {output_dir}")
        else:
            payload = result.payload()
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "asset_selection_receipt.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            (output_dir / "asset_selection_receipt.md").write_text(
                receipt_markdown(payload), encoding="utf-8"
            )
    payload = result.payload()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(receipt_markdown(payload), end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
