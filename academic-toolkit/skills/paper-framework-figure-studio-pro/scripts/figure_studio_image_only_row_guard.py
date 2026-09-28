#!/usr/bin/env python3
"""Guard S2/S5 image-only row-atomic generation and completion.

This validator is paper-neutral. It checks that an image-only stage is executed
as a prompt-index queue where each selected/non-skipped row receives exactly one
independent image-generation call and one registered raster at that same row's
`target_image_path`. It prevents a single orphan raster, contact sheet, montage,
or broad all-candidate image from satisfying a multi-row prompt-index.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[0]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from figure_studio_core.constants import STEP_OUTPUT_DIRS, SUBSTAGE_STEPS, TARGET_RASTER_IMAGE_EXTS  # noqa: E402
from figure_studio_core.errors import StateError  # noqa: E402
from figure_studio_core.identity import default_prompt_index_path, load_prompt_index  # noqa: E402
from figure_studio_core.paths import normalize_relative_path, safe_join, utc_now  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class Finding:
    level: str
    code: str
    candidate_id: str
    path: str
    message: str


def load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def active_rows(index: dict[str, Any]) -> list[dict[str, Any]]:
    rows = index.get("candidates") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("selected", True) is False:
            continue
        if row.get("skip", False) is True:
            continue
        status = str(row.get("status") or "").upper()
        if status in {"SKIP", "SKIPPED", "INTENTIONALLY_SKIPPED"}:
            continue
        out.append(row)
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def queue_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sibling_ids = [str(row.get("candidate_id")) for row in rows]
    queue: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        cid = str(row.get("candidate_id"))
        queue.append(
            {
                "ordinal": ordinal,
                "candidate_id": cid,
                "prompt_path": row.get("prompt_path"),
                "target_image_path": row.get("target_image_path"),
                "reference_image_paths": row.get("reference_image_paths", []),
                "image_call_policy": "row_atomic: exactly one image-generation call for this candidate only",
                "active_scope": {
                    "candidate_id": cid,
                    "prompt_path": row.get("prompt_path"),
                    "target_image_path": row.get("target_image_path"),
                },
                "forbidden_scope": {
                    "sibling_candidate_ids": [sid for sid in sibling_ids if sid != cid],
                    "multi_row_composite": True,
                    "contact_sheet_or_montage": True,
                    "single_call_satisfying_multiple_rows": True,
                },
            }
        )
    return queue


def preflight_checks(run_dir: Path, rows: list[dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    if not rows:
        findings.append(Finding("ERROR", "NO_ACTIVE_ROWS", "<index>", "", "prompt-index has no selected/non-skipped rows"))
        return findings
    for row in rows:
        cid = str(row.get("candidate_id"))
        prompt_rel = str(row.get("prompt_path") or "")
        target_rel = str(row.get("target_image_path") or "")
        if not prompt_rel:
            findings.append(Finding("ERROR", "MISSING_PROMPT_PATH", cid, "", "row lacks prompt_path"))
        elif not safe_join(run_dir, prompt_rel).is_file():
            findings.append(Finding("ERROR", "PROMPT_FILE_MISSING", cid, prompt_rel, "prompt_path file does not exist"))
        if not target_rel:
            findings.append(Finding("ERROR", "MISSING_TARGET_IMAGE_PATH", cid, "", "row lacks target_image_path"))
        elif Path(target_rel).suffix.lower() not in TARGET_RASTER_IMAGE_EXTS:
            findings.append(Finding("ERROR", "NON_RASTER_TARGET", cid, target_rel, "target_image_path must be PNG/JPG/JPEG/WebP"))
    return findings


def postflight_checks(run_dir: Path, stage: str, rows: list[dict[str, Any]], *, require_state_provenance: bool) -> list[Finding]:
    findings: list[Finding] = []
    target_set = {normalize_relative_path(str(row.get("target_image_path"))) for row in rows if row.get("target_image_path")}
    hashes: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        cid = str(row.get("candidate_id"))
        target_rel = normalize_relative_path(str(row.get("target_image_path") or ""))
        target_path = safe_join(run_dir, target_rel) if target_rel else run_dir / "<missing>"
        if not target_rel:
            findings.append(Finding("ERROR", "MISSING_TARGET_IMAGE_PATH", cid, "", "row lacks target_image_path"))
            continue
        if not target_path.is_file():
            findings.append(Finding("ERROR", "TARGET_IMAGE_MISSING", cid, target_rel, "no registered raster exists at this row's target_image_path"))
            continue
        digest = sha256_file(target_path)
        hashes.setdefault(digest, []).append((cid, target_rel))

    for digest, entries in hashes.items():
        if len(entries) > 1:
            ids = ", ".join(cid for cid, _ in entries)
            paths = ", ".join(path for _, path in entries)
            findings.append(
                Finding(
                    "ERROR",
                    "DUPLICATE_RASTER_BYTES_ACROSS_ROWS",
                    ids,
                    paths,
                    "multiple prompt-index rows point to byte-identical images; do not reuse one generated raster for different candidate IDs",
                )
            )

    state = load_json_if_exists(safe_join(run_dir, "state/project-state.json")) or {}
    registry_key = "s2_sketches" if stage == "S2-SKETCH-EXPLORE" else "s5_candidates"
    registry = state.get("candidate_run_registry", {}).get(registry_key, {}) if isinstance(state, dict) else {}
    for row in rows:
        cid = str(row.get("candidate_id"))
        target_rel = normalize_relative_path(str(row.get("target_image_path") or ""))
        reg = registry.get(cid) if isinstance(registry, dict) else None
        if not isinstance(reg, dict):
            finding = Finding("ERROR" if require_state_provenance else "WARN", "REGISTRY_ROW_MISSING", cid, target_rel, "candidate registry has no row for this target image")
            findings.append(finding)
            continue
        active = normalize_relative_path(str(reg.get("active_image_path") or "")) if reg.get("active_image_path") else ""
        if active != target_rel:
            findings.append(Finding("ERROR", "REGISTRY_TARGET_MISMATCH", cid, target_rel, f"registry active_image_path does not match target_image_path: {active}"))
        status = str(reg.get("status") or "").upper()
        if status in {"", "PENDING", "MISSING", "PENDING_IMAGE_GENERATION"}:
            findings.append(Finding("ERROR" if require_state_provenance else "WARN", "REGISTRY_STATUS_INCOMPLETE", cid, target_rel, f"registry status is not image-complete: {status or '<empty>'}"))

    if isinstance(state, dict):
        pending = [normalize_relative_path(p) for p in state.get("generated_image_default_locations_to_register", []) or [] if isinstance(p, str)]
        orphan_pending = [p for p in pending if p not in target_set]
        if orphan_pending:
            findings.append(
                Finding(
                    "ERROR",
                    "ORPHAN_GENERATED_RASTERS_PENDING_REGISTRATION",
                    "<stage>",
                    ", ".join(orphan_pending),
                    "generated rasters remain outside prompt-index target_image_path registration; S2/S5 is incomplete",
                )
            )
        for event in state.get("image_generation_events", []) or []:
            if not isinstance(event, dict) or event.get("step") != stage:
                continue
            generated = event.get("generated_paths") or []
            if len(generated) > 1:
                findings.append(
                    Finding(
                        "ERROR",
                        "MULTI_ROW_IMAGE_EVENT",
                        "<event>",
                        str(event.get("event_id") or ""),
                        "row-atomic policy requires one generated raster per image-generation event/call for S2/S5",
                    )
                )
            outputs = event.get("candidate_outputs") or {}
            if isinstance(outputs, dict) and len(outputs) > 1:
                findings.append(
                    Finding(
                        "ERROR",
                        "MULTI_CANDIDATE_EVENT_OUTPUTS",
                        "<event>",
                        str(event.get("event_id") or ""),
                        "one image-generation event must not bind multiple candidate_ids; split into one event/call per row",
                    )
                )
            if event.get("canonical_copy_status") == "pending_explicit_copy":
                findings.append(
                    Finding(
                        "ERROR",
                        "PENDING_CANONICAL_COPY",
                        "<event>",
                        str(event.get("event_id") or ""),
                        "image-generation event exists but raster has not been mirrored to the prompt-index target_image_path",
                    )
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", default=".", help="Project run root containing state/ and outputs/")
    parser.add_argument("--stage", required=True, choices=sorted(SUBSTAGE_STEPS))
    parser.add_argument("--prompt-index", help="Project-run-relative prompt-index.json; defaults to the stage canonical path")
    parser.add_argument("--mode", required=True, choices=["preflight", "postflight"])
    parser.add_argument("--write-queue", nargs="?", const="__DEFAULT__", help="Write row-atomic image-call queue JSON, defaulting under the stage output root")
    parser.add_argument("--json-output", help="Write guard report JSON")
    parser.add_argument("--require-state-provenance", action="store_true", help="Treat missing/incomplete candidate registry rows as errors")
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    prompt_index_rel = args.prompt_index or default_prompt_index_path(args.stage)
    prompt_index = load_prompt_index(run_dir, prompt_index_rel, stage=args.stage, require_prompt_files=args.mode == "preflight")
    rows = active_rows(prompt_index)
    queue = queue_from_rows(rows)

    if args.mode == "preflight":
        findings = preflight_checks(run_dir, rows)
    else:
        findings = postflight_checks(run_dir, args.stage, rows, require_state_provenance=args.require_state_provenance)

    if args.write_queue:
        queue_rel = f"{STEP_OUTPUT_DIRS[args.stage]}/image-call-queue.json" if args.write_queue == "__DEFAULT__" else normalize_relative_path(args.write_queue)
        queue_path = safe_join(run_dir, queue_rel)
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        queue_payload = {
            "schema_version": 1,
            "stage": args.stage,
            "prompt_index_path": prompt_index.get("prompt_index_path") or prompt_index_rel,
            "created_at": utc_now(),
            "row_atomic_generation_required": True,
            "required_image_call_count": len(queue),
            "completion_rule": "all selected/non-skipped rows must have a registered raster at their own target_image_path; orphan rasters do not count",
            "queue": queue,
        }
        queue_path.write_text(json.dumps(queue_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    error_count = sum(1 for f in findings if f.level == "ERROR")
    warn_count = sum(1 for f in findings if f.level == "WARN")
    payload = {
        "schema_version": 1,
        "stage": args.stage,
        "mode": args.mode,
        "prompt_index_path": prompt_index.get("prompt_index_path") or prompt_index_rel,
        "active_row_count": len(rows),
        "required_image_call_count": len(rows),
        "row_atomic_generation_required": True,
        "completion_status": "PASS" if error_count == 0 else "FAIL",
        "error_count": error_count,
        "warn_count": warn_count,
        "findings": [asdict(f) for f in findings],
        "checked_at": utc_now(),
    }
    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.fail_on_error and error_count:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StateError as exc:
        print(json.dumps({"completion_status": "FAIL", "error_count": 1, "findings": [{"level": "ERROR", "code": "STATE_ERROR", "candidate_id": "<guard>", "path": "", "message": str(exc)}]}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(2)
