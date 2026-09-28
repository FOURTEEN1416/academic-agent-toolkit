#!/usr/bin/env python3
"""Response-time cumulative checkpoint zip gate.

This helper is intentionally paper-neutral. Before a workflow text reply is
presented, use it to verify that at least one checkpoint zip for the active or
just-completed stage is a usable cumulative restore mirror. If no such zip is
valid, the script can invoke the generic cumulative repair helper. When project
state is missing, it can only build a conservative reconstruction bundle from
available files and must report that conversation/state reconstruction is still
required.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

META_NAMES = {
    "checkpoint-manifest.json",
    "checkpoint-cumulative-integrity.json",
    "checkpoint-integrity-audit.json",
}
DEFAULT_ROOTS = ["state", "inputs", "outputs"]
EXCLUDE_DIRS = {"checkpoints", "__pycache__"}
EXCLUDE_SUFFIXES = {".pyc"}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_rel(value: str | Path) -> str:
    rel = Path(value).as_posix().lstrip("/")
    parts: list[str] = []
    for part in rel.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            raise ValueError(f"unsafe relative path: {value!r}")
        parts.append(part)
    return "/".join(parts)


def unique(rows: Iterable[str]) -> list[str]:
    result: list[str] = []
    for row in rows:
        try:
            rel = norm_rel(row)
        except ValueError:
            continue
        if rel and rel not in result:
            result.append(rel)
    return result


def read_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json_member(zf: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        return json.loads(zf.read(name).decode("utf-8"))
    except Exception:
        return {}


def status_ok(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    values = {
        str(payload.get("status", "")).upper(),
        str(payload.get("checkpoint_status", "")),
        str(payload.get("restore_status", "")),
        str(payload.get("checkpoint_integrity_status", "")),
        str(payload.get("final_verdict", "")),
        str(payload.get("post_write_validation_status", "")).upper(),
    }
    return bool({"PASS", "complete_restore_ready"}.intersection(values))


def discover_stage(state: dict[str, Any], explicit_stage: str | None) -> str | None:
    if explicit_stage:
        return explicit_stage
    for key in ("current_step", "active_stage", "last_completed_stage"):
        value = state.get(key)
        if isinstance(value, str) and value:
            return value
    plan = state.get("workflow_plan")
    if isinstance(plan, list):
        completed = [row.get("step") for row in plan if isinstance(row, dict) and row.get("status") == "completed"]
        if completed:
            return str(completed[-1])
        for row in plan:
            if isinstance(row, dict) and row.get("step"):
                return str(row["step"])
    return None


def stage_roots_from_state(run_dir: Path, state: dict[str, Any], stage: str | None) -> list[str]:
    roots = ["state", "inputs"]
    plan = state.get("workflow_plan")
    if isinstance(plan, list):
        for row in plan:
            if not isinstance(row, dict):
                continue
            out = row.get("output_dir")
            if isinstance(out, str) and out:
                roots.append(out)
            if stage and row.get("step") == stage:
                break
    else:
        roots.append("outputs")

    # Include prompt-index roots prepared by the active text stage for future image stages.
    outputs = run_dir / "outputs"
    if outputs.is_dir() and stage:
        for path in outputs.rglob("prompt-index.json"):
            try:
                data = read_json_file(path)
            except Exception:
                continue
            if data.get("prepared_by_stage") == stage:
                try:
                    roots.append(norm_rel(path.parent.relative_to(run_dir)))
                except ValueError:
                    continue
    return unique(roots)


def rel_is_under(rel: str, roots: list[str]) -> bool:
    rel = norm_rel(rel)
    if any(part in EXCLUDE_DIRS for part in rel.split("/")):
        return False
    if Path(rel).suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    return any(rel == root or rel.startswith(root + "/") for root in roots)


def collect_existing_files(run_dir: Path, roots: list[str]) -> list[str]:
    files: set[str] = set()
    for root in roots:
        root_path = run_dir / root
        if root_path.is_file():
            files.add(norm_rel(root))
            continue
        if not root_path.exists():
            continue
        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = norm_rel(path.relative_to(run_dir))
            except ValueError:
                continue
            if rel_is_under(rel, roots):
                files.add(rel)
    return sorted(files)


def candidate_zips(run_dir: Path, stage: str | None) -> list[Path]:
    candidates: list[Path] = []
    if stage:
        stage_dir = run_dir / "checkpoints" / stage
        if stage_dir.is_dir():
            candidates.extend(stage_dir.glob("*.zip"))
    checkpoints = run_dir / "checkpoints"
    if checkpoints.is_dir():
        candidates.extend(checkpoints.rglob("*.zip"))
    dedup = sorted({p.resolve() for p in candidates if p.is_file()}, key=lambda p: p.stat().st_mtime, reverse=True)
    return dedup


def validate_zip(zip_path: Path, required_files: list[str], roots: list[str]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "zip_path": str(zip_path),
        "status": "FAIL",
        "usable_as_cumulative_response_checkpoint": False,
        "included_roots_expected": roots,
        "required_existing_asset_count": len(required_files),
    }
    try:
        with zipfile.ZipFile(zip_path) as zf:
            members = set(zf.namelist())
            row["member_count"] = len(members)
            missing_meta = sorted(META_NAMES - members)
            row["metadata_present"] = {name: name in members for name in sorted(META_NAMES)}
            manifest = read_json_member(zf, "checkpoint-manifest.json") if "checkpoint-manifest.json" in members else {}
            integrity = read_json_member(zf, "checkpoint-cumulative-integrity.json") if "checkpoint-cumulative-integrity.json" in members else {}
            audit = read_json_member(zf, "checkpoint-integrity-audit.json") if "checkpoint-integrity-audit.json" in members else {}
            missing_assets = [rel for rel in required_files if rel not in members]
            manifest_scope = str(manifest.get("checkpoint_scope", "")) if isinstance(manifest, dict) else ""
            manifest_roots = [norm_rel(root) for root in manifest.get("included_roots", [])] if isinstance(manifest, dict) else []
            missing_manifest_roots = [root for root in roots if root not in manifest_roots]
            failures = []
            if missing_meta:
                failures.append({"category": "missing_metadata", "members": missing_meta})
            if "cumulative" not in manifest_scope.lower():
                failures.append({"category": "manifest_not_cumulative", "checkpoint_scope": manifest_scope})
            if integrity and not status_ok(integrity):
                failures.append({"category": "integrity_status_not_passed"})
            if audit and not status_ok(audit):
                failures.append({"category": "audit_status_not_passed"})
            if missing_manifest_roots:
                failures.append({"category": "manifest_missing_expected_roots", "roots": missing_manifest_roots})
            if missing_assets:
                failures.append({"category": "missing_required_existing_assets", "count": len(missing_assets), "first_30": missing_assets[:30]})
            row.update(
                {
                    "checkpoint_scope": manifest_scope,
                    "missing_metadata": missing_meta,
                    "missing_required_asset_count": len(missing_assets),
                    "missing_required_asset_first_30": missing_assets[:30],
                    "embedded_integrity_status": integrity.get("checkpoint_integrity_status") or integrity.get("status"),
                    "embedded_audit_status": audit.get("final_verdict") or audit.get("checkpoint_integrity_status") or audit.get("status"),
                    "failures": failures,
                }
            )
            if not failures:
                row["status"] = "PASS"
                row["usable_as_cumulative_response_checkpoint"] = True
    except zipfile.BadZipFile:
        row["failures"] = [{"category": "bad_zip_file"}]
    except Exception as exc:  # pragma: no cover - defensive CLI behavior
        row["failures"] = [{"category": "zip_validation_error", "message": str(exc)}]
    return row


def latest_sequence_for_fallback(run_dir: Path) -> int:
    target = run_dir / "checkpoints" / "RESPONSE-CHECKPOINT-GATE"
    nums: list[int] = []
    if target.is_dir():
        for path in target.glob("response-reconstruction-*.zip"):
            match = re.search(r"response-reconstruction-(\d+)", path.name)
            if match:
                nums.append(int(match.group(1)))
    return max(nums or [0]) + 1


def build_fallback_reconstruction_zip(
    run_dir: Path,
    roots: list[str],
    required_files: list[str],
    stage: str | None,
    conversation_reconstruction_md: Path | None,
) -> Path:
    sequence = latest_sequence_for_fallback(run_dir)
    zip_path = run_dir / "checkpoints" / "RESPONSE-CHECKPOINT-GATE" / f"response-reconstruction-{sequence:04d}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    created = now()
    manifest = {
        "schema_version": 1,
        "stage": stage,
        "created_at": created,
        "checkpoint_type": "response-time-conversation-reconstruction-fallback",
        "checkpoint_scope": "cumulative_from_available_roots_with_conversation_reconstruction_required",
        "included_roots": roots,
        "required_existing_asset_count": len(required_files),
        "checkpoint_status": "conversation_reconstruction_required",
        "restore_status": "not_restore_ready_until_state_and_missing_assets_are_reconstructed",
        "instruction": "This fallback zip contains available state/input/output files. It is not a complete restore-ready checkpoint unless a human/assistant reconstructs missing state from conversation history and reruns the normal checkpoint guard.",
    }
    integrity = {
        "schema_version": 1,
        "stage": stage,
        "created_at": created,
        "checkpoint_integrity_status": "conversation_reconstruction_required",
        "required_existing_asset_count": len(required_files),
        "missing_asset_count": 0,
        "required_action": "reconstruct missing state/manifests from conversation history, restore any generated rasters, then rerun the response checkpoint zip gate",
    }
    audit = {
        "schema_version": 1,
        "stage": stage,
        "created_at": created,
        "final_verdict": "conversation_reconstruction_required",
        "available_roots_zipped": roots,
        "conversation_reconstruction_note_included": bool(conversation_reconstruction_md and conversation_reconstruction_md.is_file()),
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("checkpoint-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        zf.writestr("checkpoint-cumulative-integrity.json", json.dumps(integrity, ensure_ascii=False, indent=2) + "\n")
        zf.writestr("checkpoint-integrity-audit.json", json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
        if conversation_reconstruction_md and conversation_reconstruction_md.is_file():
            zf.write(conversation_reconstruction_md, "outputs/_conversation-reconstruction/conversation-reconstruction.md")
        for rel in required_files:
            path = run_dir / rel
            if path.is_file():
                zf.write(path, rel)
    return zip_path


def run_repair_helper(run_dir: Path, stage: str, report_path: Path) -> dict[str, Any]:
    helper = Path(__file__).with_name("figure_studio_cumulative_checkpoint_repair.py")
    cmd = [sys.executable, str(helper), "--run-dir", str(run_dir), "--stage", stage, "--repair", "--report", str(report_path)]
    completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    payload: dict[str, Any] = {
        "command": [Path(cmd[0]).name, *cmd[1:]],
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }
    if report_path.is_file():
        try:
            payload["repair_report"] = read_json_file(report_path)
        except Exception:
            pass
    return payload


def resolve_report_path(run_dir: Path, report_arg: str | None) -> Path:
    if report_arg:
        p = Path(report_arg)
        return p if p.is_absolute() else run_dir / p
    return run_dir / "outputs" / "_checkpoint-gates" / "response-checkpoint-zip-gate-report.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Project run directory that contains state/, outputs/, and checkpoints/.")
    parser.add_argument("--stage", help="Active or just-completed public stage. If omitted, the script derives it from state/project-state.json.")
    parser.add_argument("--build-if-missing", action="store_true", help="Attempt generic checkpoint repair if no valid cumulative checkpoint zip exists.")
    parser.add_argument("--conversation-reconstruction-md", help="Optional markdown note reconstructed from conversation history; included only in fallback bundles.")
    parser.add_argument("--report", help="Output JSON report path, relative to run-dir unless absolute.")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit non-zero when no usable cumulative checkpoint zip is available after repair attempts.")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    report_path = resolve_report_path(run_dir, args.report)
    state_path = run_dir / "state" / "project-state.json"
    state: dict[str, Any] = {}
    state_read_error: str | None = None
    if state_path.is_file():
        try:
            state = read_json_file(state_path)
        except Exception as exc:
            state_read_error = str(exc)
    stage = discover_stage(state, args.stage)
    roots = stage_roots_from_state(run_dir, state, stage) if state else DEFAULT_ROOTS
    roots = unique(roots)
    required_files = collect_existing_files(run_dir, roots)

    report: dict[str, Any] = {
        "schema_version": 1,
        "gate": "response_checkpoint_zip_gate",
        "created_at": now(),
        "run_dir": str(run_dir),
        "stage": stage,
        "state_path": str(state_path),
        "state_loaded": bool(state),
        "state_read_error": state_read_error,
        "included_roots_expected": roots,
        "required_existing_asset_count": len(required_files),
        "build_if_missing": bool(args.build_if_missing),
    }

    candidates = candidate_zips(run_dir, stage)
    validations = [validate_zip(path, required_files, roots) for path in candidates]
    usable = [row for row in validations if row.get("usable_as_cumulative_response_checkpoint")]
    report["candidate_zip_count_before_repair"] = len(candidates)
    report["zip_validations_before_repair"] = validations[:20]

    repair_report: dict[str, Any] | None = None
    fallback_zip: Path | None = None
    if not usable and args.build_if_missing:
        if stage and state_path.is_file():
            repair_path = report_path.with_name(report_path.stem + ".generic-repair.json")
            repair_report = run_repair_helper(run_dir, stage, repair_path)
            report["generic_repair_attempt"] = repair_report
        else:
            conversation_md = Path(args.conversation_reconstruction_md).resolve() if args.conversation_reconstruction_md else None
            fallback_zip = build_fallback_reconstruction_zip(run_dir, roots, required_files, stage, conversation_md)
            report["fallback_reconstruction_zip_created"] = str(fallback_zip)
            report["fallback_reason"] = "missing_or_unreadable_project_state_or_stage"
        candidates = candidate_zips(run_dir, stage)
        validations = [validate_zip(path, required_files, roots) for path in candidates]
        usable = [row for row in validations if row.get("usable_as_cumulative_response_checkpoint")]
        report["candidate_zip_count_after_repair"] = len(candidates)
        report["zip_validations_after_repair"] = validations[:20]

    if usable:
        best = usable[0]
        report["status"] = "PASS"
        report["checkpoint_status"] = "complete_restore_ready"
        report["usable_checkpoint_zip"] = best.get("zip_path")
        report["user_facing_checkpoint_link_allowed"] = True
        exit_code = 0
    else:
        report["status"] = "FAIL"
        report["checkpoint_status"] = "not_restore_ready"
        report["user_facing_checkpoint_link_allowed"] = False
        report["required_action"] = (
            "rebuild from cumulative roots and rerun the gate; if source files or generated rasters are absent, "
            "reconstruct text state from conversation history and redo the producing image/text stage as needed"
        )
        exit_code = 2 if args.fail_on_error else 0

    write_json_file(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
