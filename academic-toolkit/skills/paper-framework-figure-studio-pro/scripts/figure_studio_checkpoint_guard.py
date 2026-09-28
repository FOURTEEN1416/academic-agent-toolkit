#!/usr/bin/env python3
"""Generic cumulative checkpoint validator/rebuilder.

This script is deliberately paper-agnostic. It validates a checkpoint zip or
split-part union against files that already exist in a project run under the
cumulative included roots. It never assumes a project id, paper topic,
candidate id, image count, or fixed output filename.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Iterable

RASTER_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
EXCLUDED_PARTS = {"__pycache__"}
EXCLUDED_SUFFIXES = {".pyc"}


def normalize_rel(value: str | Path) -> str:
    rel = Path(value).as_posix().lstrip("/")
    parts: list[str] = []
    for part in rel.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            raise ValueError(f"unsafe relative path: {value!r}")
        parts.append(part)
    return "/".join(parts)


def should_include(rel: str, roots: Iterable[str]) -> bool:
    rel = normalize_rel(rel)
    if rel.startswith("checkpoints/"):
        return False
    if any(part in EXCLUDED_PARTS for part in rel.split("/")):
        return False
    if Path(rel).suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    norm_roots = [normalize_rel(root) for root in roots]
    return any(rel == root or rel.startswith(root + "/") for root in norm_roots)


def discover_output_roots_from_state(run_dir: Path, stage: str | None) -> list[str]:
    state_path = run_dir / "state" / "project-state.json"
    roots = ["state", "inputs"]
    if not state_path.is_file():
        roots.append("outputs")
        return unique(roots)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        roots.append("outputs")
        return unique(roots)
    plan = state.get("workflow_plan", [])
    if isinstance(plan, list):
        for row in plan:
            if not isinstance(row, dict):
                continue
            out = row.get("output_dir")
            if isinstance(out, str) and out:
                roots.append(normalize_rel(out))
            if stage and row.get("step") == stage:
                break
            if not stage and row.get("status") in {"current", "in_progress"}:
                break
    else:
        roots.append("outputs")
    return unique(roots)


def unique(rows: Iterable[str]) -> list[str]:
    result: list[str] = []
    for row in rows:
        try:
            rel = normalize_rel(row)
        except ValueError:
            continue
        if rel and rel not in result:
            result.append(rel)
    return result


def existing_required_assets(run_dir: Path, roots: list[str]) -> list[str]:
    assets: set[str] = set()
    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = normalize_rel(path.relative_to(run_dir))
        except ValueError:
            continue
        if should_include(rel, roots):
            assets.add(rel)
    return sorted(assets)


def zip_member_union(zip_paths: list[Path]) -> set[str]:
    members: set[str] = set()
    for path in zip_paths:
        if not path.is_file():
            continue
        with zipfile.ZipFile(path, "r") as archive:
            members.update(archive.namelist())
    return members


def read_checkpoint_manifest(zip_paths: list[Path]) -> dict:
    for path in zip_paths:
        if not path.is_file():
            continue
        with zipfile.ZipFile(path, "r") as archive:
            if "checkpoint-manifest.json" in archive.namelist():
                return json.loads(archive.read("checkpoint-manifest.json").decode("utf-8"))
    return {}


def read_checkpoint_integrity(zip_paths: list[Path]) -> dict:
    for path in zip_paths:
        if not path.is_file():
            continue
        with zipfile.ZipFile(path, "r") as archive:
            if "checkpoint-cumulative-integrity.json" in archive.namelist():
                return json.loads(archive.read("checkpoint-cumulative-integrity.json").decode("utf-8"))
    return {}




def read_checkpoint_integrity_audit(zip_paths: list[Path]) -> dict:
    for path in zip_paths:
        if not path.is_file():
            continue
        with zipfile.ZipFile(path, "r") as archive:
            if "checkpoint-integrity-audit.json" in archive.namelist():
                return json.loads(archive.read("checkpoint-integrity-audit.json").decode("utf-8"))
    return {}


def integrity_passes(report: dict) -> bool:
    if not isinstance(report, dict) or not report:
        return False
    status_values = {
        str(report.get("status", "")).upper(),
        str(report.get("checkpoint_integrity_status", "")),
        str(report.get("checkpoint_status", "")),
        str(report.get("restore_status", "")),
    }
    return "PASS" in status_values or "complete_restore_ready" in status_values


def validate(
    run_dir: Path,
    zip_paths: list[Path],
    roots: list[str],
    stage: str | None,
    attempt: int,
    *,
    require_integrity_status: bool = True,
) -> dict:
    required = existing_required_assets(run_dir, roots)
    members = zip_member_union(zip_paths)
    manifest = read_checkpoint_manifest(zip_paths)
    integrity = read_checkpoint_integrity(zip_paths)
    integrity_audit = read_checkpoint_integrity_audit(zip_paths)
    missing = [rel for rel in required if rel not in members]
    roots_with_files = []
    roots_without_members = []
    for root in roots:
        has_files = any(rel == root or rel.startswith(root + "/") for rel in required)
        if has_files:
            roots_with_files.append(root)
            if not any(member == root or member.startswith(root + "/") for member in members):
                roots_without_members.append(root)
    scope = str(manifest.get("checkpoint_scope", "")) if isinstance(manifest, dict) else ""
    manifest_ok = bool(manifest) and "cumulative" in scope.lower()
    manifest_roots = [normalize_rel(root) for root in manifest.get("included_roots", [])] if isinstance(manifest, dict) else []
    manifest_missing_roots = [root for root in roots if root not in manifest_roots]
    failures = []
    if not manifest:
        failures.append({"category": "missing_checkpoint_manifest", "member": "checkpoint-manifest.json"})
    elif not manifest_ok:
        failures.append({"category": "manifest_scope_not_cumulative", "checkpoint_scope": scope})
    if not integrity:
        failures.append({"category": "missing_checkpoint_cumulative_integrity", "member": "checkpoint-cumulative-integrity.json"})
    elif require_integrity_status and not integrity_passes(integrity):
        failures.append({
            "category": "checkpoint_cumulative_integrity_not_passed",
            "embedded_status": integrity.get("status"),
            "embedded_checkpoint_integrity_status": integrity.get("checkpoint_integrity_status"),
        })
    if not integrity_audit:
        failures.append({"category": "missing_checkpoint_integrity_audit", "member": "checkpoint-integrity-audit.json"})
    elif require_integrity_status and not integrity_passes(integrity_audit):
        failures.append({
            "category": "checkpoint_integrity_audit_not_passed",
            "embedded_status": integrity_audit.get("status"),
            "embedded_checkpoint_integrity_status": integrity_audit.get("checkpoint_integrity_status"),
        })
    failures.extend({"category": "manifest_missing_expected_root", "root": root} for root in manifest_missing_roots)
    failures.extend({"category": "missing_required_existing_asset", "relative_path": rel} for rel in missing)
    failures.extend({"category": "existing_root_without_archive_members", "root": root} for root in roots_without_members)
    return {
        "schema_version": 1,
        "guard": "generic_cumulative_checkpoint_guard",
        "stage": stage,
        "attempt": attempt,
        "status": "PASS" if not failures else "FAIL",
        "checkpoint_status": "complete_restore_ready" if not failures else "redo_required",
        "restore_status": "complete_restore_ready" if not failures else "not_restore_ready_redo_required",
        "redo_required": bool(failures),
        "user_facing_checkpoint_link_allowed": not bool(failures),
        "run_dir": str(run_dir),
        "zip_paths": [str(path) for path in zip_paths],
        "included_roots": roots,
        "required_existing_asset_count": len(required),
        "archive_member_count": len(members),
        "missing_required_existing_asset_count": len(missing),
        "roots_with_existing_files": roots_with_files,
        "roots_without_archive_members": roots_without_members,
        "manifest_present": bool(manifest),
        "integrity_report_present": bool(integrity),
        "integrity_audit_present": bool(integrity_audit),
        "integrity_report_status": integrity.get("status") if isinstance(integrity, dict) else None,
        "integrity_report_checkpoint_status": integrity.get("checkpoint_integrity_status") if isinstance(integrity, dict) else None,
        "integrity_report_required_for_response_link": require_integrity_status,
        "manifest_scope": scope,
        "manifest_included_roots": manifest_roots,
        "manifest_missing_expected_roots": manifest_missing_roots,
        "failures": failures,
        "non_hardcoding_statement": "Inventory is derived from run state, workflow plan, included roots, zip members, and existing files only.",
    }


def write_zip_from_inventory(run_dir: Path, out_zip: Path, roots: list[str], report: dict) -> None:
    manifest = {
        "schema_version": 2,
        "checkpoint_scope": "cumulative_from_workflow_start_to_current_stage_or_substage",
        "included_roots": roots,
        "checkpoint_status": "complete_restore_ready",
        "restore_status": "complete_restore_ready",
        "guard_report_embedded": "checkpoint-cumulative-integrity.json",
        "integrity_audit_embedded": "checkpoint-integrity-audit.json",
        "hardcoding_forbidden": "No project id, paper name, candidate id, image count, or fixed filename assumptions were used.",
    }
    embedded_report = dict(report) if isinstance(report, dict) else {"status": "UNKNOWN"}
    embedded_report.setdefault("checkpoint_integrity_status", "complete_restore_ready" if embedded_report.get("status") == "PASS" else embedded_report.get("status"))
    audit_report = {
        "schema_version": 1,
        "audit": "root_level_checkpoint_integrity_audit",
        "status": embedded_report.get("status"),
        "checkpoint_integrity_status": embedded_report.get("checkpoint_integrity_status"),
        "included_roots": roots,
        "required_existing_asset_count": embedded_report.get("required_existing_asset_count"),
        "missing_required_existing_asset_count": embedded_report.get("missing_required_existing_asset_count"),
        "non_hardcoding_statement": "Audit inventory was derived from roots/state/manifests/existing files; no paper or fixed candidate assumptions were used.",
    }
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("checkpoint-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("checkpoint-cumulative-integrity.json", json.dumps(embedded_report, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("checkpoint-integrity-audit.json", json.dumps(audit_report, ensure_ascii=False, indent=2) + "\n")
        seen = {"checkpoint-manifest.json", "checkpoint-cumulative-integrity.json", "checkpoint-integrity-audit.json"}
        for rel in existing_required_assets(run_dir, roots):
            if rel in seen:
                continue
            seen.add(rel)
            archive.write(run_dir / rel, rel)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Project run directory, not repository root.")
    parser.add_argument("--stage", help="Current public stage; used only to derive cumulative roots from state.")
    parser.add_argument("--zip", action="append", dest="zip_paths", default=[], help="Checkpoint zip or split part. Repeat for split checkpoints.")
    parser.add_argument("--included-root", action="append", default=[], help="Explicit cumulative root. Defaults to state/input/output roots from project state.")
    parser.add_argument("--report", help="Write validation report JSON here.")
    parser.add_argument("--report-out", help="Alias for --report.")
    parser.add_argument("--fail-on-error", action="store_true", help="Compatibility flag; this script exits nonzero on failure either way.")
    parser.add_argument("--rebuild-output-zip", help="If validation fails, rebuild a cumulative checkpoint zip here.")
    parser.add_argument("--max-attempts", type=int, default=3, help="Bounded validation/rebuild attempts.")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    roots = unique(args.included_root) if args.included_root else discover_output_roots_from_state(run_dir, args.stage)
    zip_paths = [(Path(p) if Path(p).is_absolute() else run_dir / p).resolve() for p in args.zip_paths]
    max_attempts = max(1, args.max_attempts)

    report = validate(run_dir, zip_paths, roots, args.stage, attempt=1, require_integrity_status=True)
    attempt = 1
    rebuilt_zip: Path | None = None
    while report["status"] != "PASS" and args.rebuild_output_zip and attempt < max_attempts:
        attempt += 1
        rebuilt_zip = (Path(args.rebuild_output_zip) if Path(args.rebuild_output_zip).is_absolute() else run_dir / args.rebuild_output_zip).resolve()
        write_zip_from_inventory(
            run_dir,
            rebuilt_zip,
            roots,
            {"status": "REBUILD_IN_PROGRESS", "source_failure_report": report},
        )
        # Validate asset/root completeness without requiring the provisional embedded
        # integrity report to have already certified itself. This avoids a circular
        # rebuild dependency while still requiring a final embedded PASS report.
        base_report = validate(run_dir, [rebuilt_zip], roots, args.stage, attempt=attempt, require_integrity_status=False)
        if base_report["status"] == "PASS":
            final_embedded_report = dict(base_report)
            final_embedded_report["status"] = "PASS"
            final_embedded_report["checkpoint_integrity_status"] = "complete_restore_ready"
            final_embedded_report["restore_status"] = "complete_restore_ready"
            final_embedded_report["final_attempt_count"] = attempt
            final_embedded_report["bounded_rebuild_attempt_limit"] = max_attempts
            write_zip_from_inventory(run_dir, rebuilt_zip, roots, final_embedded_report)
            report = validate(run_dir, [rebuilt_zip], roots, args.stage, attempt=attempt, require_integrity_status=True)
        else:
            report = base_report
        zip_paths = [rebuilt_zip]

    report["final_attempt_count"] = attempt
    report["bounded_rebuild_attempt_limit"] = max_attempts
    if report.get("status") != "PASS":
        report["redo_instruction"] = "Redo the earliest affected workflow step or image-output/prompt-preparation registration, then rebuild the cumulative checkpoint until this guard passes."
        report["not_a_restore_checkpoint"] = True
    if report.get("status") != "PASS":
        report["status"] = "REDO_REQUIRED"
        report["redo_required"] = True
        report["must_not_present_as_checkpoint"] = True
        report["next_required_action"] = (
            "Redo the producing stage/substage for the missing required assets, then rebuild and validate "
            "the cumulative checkpoint until PASS. Do not proceed or present this archive as recoverable."
        )
        report["failure_handling_policy"] = "repair_or_redo_required_no_final_incomplete_checkpoint_v3215b"
    report_path = args.report or args.report_out
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
