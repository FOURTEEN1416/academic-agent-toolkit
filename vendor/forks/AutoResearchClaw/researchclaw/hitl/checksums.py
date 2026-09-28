"""Reproducibility checksums: SHA256 manifest for stage artifacts.

Every stage output gets a content hash to ensure:
- Artifacts have not been corrupted
- Changes can be tracked precisely
- Reproducibility can be verified
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def compute_sha256(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest(stage_dir: Path) -> dict[str, str]:
    """Generate a SHA256 manifest for all files in a stage directory.

    Args:
        stage_dir: Path to stage-NN directory.

    Returns:
        Dict mapping filename -> SHA256 hex digest.
    """
    manifest: dict[str, str] = {}
    if not stage_dir.is_dir():
        return manifest

    for f in sorted(stage_dir.rglob("*")):
        if f.is_file() and f.name != "manifest.json":
            rel = str(f.relative_to(stage_dir))
            try:
                manifest[rel] = compute_sha256(f)
            except OSError:
                manifest[rel] = "ERROR"

    return manifest


def write_manifest(stage_dir: Path) -> Path:
    """Write manifest.json to a stage directory.

    Returns:
        Path to the manifest file.
    """
    manifest = generate_manifest(stage_dir)
    path = stage_dir / "manifest.json"
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return path


def verify_manifest(stage_dir: Path) -> list[str]:
    """Verify stage artifacts against their manifest.

    Returns:
        List of error messages (empty if all OK).
    """
    manifest_path = stage_dir / "manifest.json"
    if not manifest_path.exists():
        return ["No manifest.json found"]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"Cannot read manifest: {exc}"]

    errors: list[str] = []
    for filename, expected_hash in manifest.items():
        fpath = stage_dir / filename
        if not fpath.exists():
            errors.append(f"Missing: {filename}")
            continue
        if expected_hash == "ERROR":
            continue
        actual_hash = compute_sha256(fpath)
        if actual_hash != expected_hash:
            errors.append(
                f"Changed: {filename} "
                f"(expected {expected_hash[:12]}..., "
                f"got {actual_hash[:12]}...)"
            )

    return errors


def write_run_manifest(run_dir: Path) -> dict[str, Any]:
    """Write manifests for all stage directories in a run.

    Returns:
        Summary dict: stage_num -> {file_count, verified}.
    """
    summary: dict[str, Any] = {}
    for stage_dir in sorted(run_dir.glob("stage-*")):
        if not stage_dir.is_dir():
            continue
        stage_name = stage_dir.name
        manifest = generate_manifest(stage_dir)
        if manifest:
            write_manifest(stage_dir)
            summary[stage_name] = {
                "file_count": len(manifest),
                "verified": True,
            }
    return summary
