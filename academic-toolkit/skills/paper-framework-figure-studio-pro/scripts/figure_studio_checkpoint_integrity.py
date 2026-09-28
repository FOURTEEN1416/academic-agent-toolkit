#!/usr/bin/env python3
"""Audit cumulative checkpoint integrity for paper-framework-figure-studio-pro.

Generic: discovers workflow order, included roots, previous complete checkpoint
payloads, and current archive members from state. It does not know anything
about a paper, project id, candidate ids, or image counts.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

# Allow running from the scripts directory without installation.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from figure_studio_core.constants import WORKFLOW_STEPS  # noqa: E402
from figure_studio_core.paths import normalize_relative_path  # noqa: E402
from figure_studio_core.substages import (  # noqa: E402
    CHECKPOINT_METADATA_MEMBERS,
    archive_member_set,
    checkpoint_included_roots,
    prior_checkpoint_payload_inventory,
    workflow_stage_index,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Project run directory")
    parser.add_argument("--state-file", default="state/project-state.json")
    parser.add_argument("--stage", required=True, choices=[step for step, _, _, _ in WORKFLOW_STEPS])
    parser.add_argument("--checkpoint-zip", action="append", required=True, help="Checkpoint zip path relative to run-dir or absolute; repeat for split parts")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    state = load_json(run_dir / args.state_file)
    included_roots = checkpoint_included_roots(args.stage)
    zip_paths: list[Path] = []
    current_zip_rels: set[str] = set()
    for value in args.checkpoint_zip:
        path = Path(value)
        if not path.is_absolute():
            path = run_dir / value
        path = path.resolve()
        zip_paths.append(path)
        try:
            current_zip_rels.add(normalize_relative_path(path.relative_to(run_dir)))
        except Exception:
            pass

    members = archive_member_set(zip_paths)
    prior_payload = prior_checkpoint_payload_inventory(
        run_dir=run_dir,
        state=state,
        stage=args.stage,
        included_roots=included_roots,
        current_zip_rels=current_zip_rels,
    )
    missing_prior = sorted(rel for rel in prior_payload if rel not in members)
    stage_list = [step for step, _, _, _ in WORKFLOW_STEPS[: workflow_stage_index(args.stage) + 1]]
    metadata_present = "checkpoint-integrity-audit.json" in members
    report = {
        "schema_version": 1,
        "audit_type": "standalone_cumulative_checkpoint_integrity_audit",
        "stage": args.stage,
        "checkpoint_stage_list": stage_list,
        "included_roots": included_roots,
        "zip_paths": [str(p) for p in zip_paths],
        "zip_member_count": len(members),
        "previous_complete_checkpoint_payload_count": len(prior_payload),
        "missing_previous_payload_count": len(missing_prior),
        "missing_previous_payload": missing_prior,
        "checkpoint_integrity_audit_member_present": metadata_present,
        "verdict": "PASS" if metadata_present and not missing_prior else "FAIL",
        "non_hardcoding_guard": "All expected prior payload paths are discovered from state checkpoint_bundles and workflow included roots, not from paper/project/candidate-specific names.",
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"verdict: {report['verdict']}")
        print(f"stage: {args.stage}")
        print(f"prior payload count: {len(prior_payload)}")
        print(f"missing prior payload count: {len(missing_prior)}")
        print(f"checkpoint-integrity-audit.json present: {metadata_present}")
        if missing_prior:
            print("missing prior payload:")
            for rel in missing_prior:
                print(f"  - {rel}")
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
