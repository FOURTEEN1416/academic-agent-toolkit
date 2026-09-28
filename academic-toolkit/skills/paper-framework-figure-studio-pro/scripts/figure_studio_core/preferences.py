"""Startup preference reference image registration."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
from typing import Any

from .constants import PREFERENCE_REFERENCE_ROOT, REFERENCE_IMAGE_EXTS
from .errors import StateError
from .paths import normalize_relative_path, safe_join, sha256_file, utc_now

def preference_reference_records(args: argparse.Namespace, run_dir: Path) -> list[dict[str, Any]]:
    output_dir_rel = normalize_relative_path(args.output_dir)
    output_dir = safe_join(run_dir, output_dir_rel)
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for offset, source in enumerate(args.source):
        src = Path(source).expanduser().resolve()
        if not src.exists() or not src.is_file():
            raise StateError(f"reference image source does not exist or is not a file: {source}")
        ext = src.suffix.lower()
        if ext not in REFERENCE_IMAGE_EXTS:
            allowed = ", ".join(sorted(REFERENCE_IMAGE_EXTS))
            raise StateError(f"unsupported reference image extension {ext}; allowed: {allowed}")
        index = args.start_index + offset
        reference_id = f"{args.reference_id_prefix}-{index:02d}"
        dest_rel = normalize_relative_path(Path(output_dir_rel) / f"{reference_id}{ext}")
        dest = safe_join(run_dir, dest_rel)
        if dest.exists() and not args.replace:
            raise StateError(f"reference image already exists; use --replace to overwrite: {dest_rel}")
        shutil.copy2(src, dest)
        now = utc_now()
        records.append(
            {
                "reference_id": reference_id,
                "relative_path": dest_rel,
                "summary": args.summary or f"User preference reference diagram {index:02d}",
                "tags": sorted(set((args.tag or []) + ["preference-reference", "startup"])),
                "status": "active",
                "analysis_status": "pending",
                "source_path_recording_status": "original_source_path_not_persisted",
                "created_at": now,
                "updated_at": now,
                "content_hash": sha256_file(dest),
                "source_user_request": args.source_user_request or "",
            }
        )
    return records
