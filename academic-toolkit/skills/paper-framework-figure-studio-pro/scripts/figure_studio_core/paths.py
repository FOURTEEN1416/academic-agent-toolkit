"""Project-run path safety and JSON/file helpers."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import DEFAULT_ROOT, SAFE_PROJECT_RE, STATE_RELATIVE_PATH
from .errors import StateError

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def normalize_project_id(project_id: str | None) -> str:
    if not project_id:
        project_id = "project-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if not SAFE_PROJECT_RE.fullmatch(project_id):
        raise StateError(
            "project_id must start with an alphanumeric character and contain only "
            "letters, digits, dot, underscore, or hyphen"
        )
    if project_id in {".", ".."}:
        raise StateError("project_id cannot be . or ..")
    return project_id

def resolve_root(root: str, allow_custom_root: bool) -> Path:
    root_path = Path(root).expanduser()
    if root_path.name != DEFAULT_ROOT and not allow_custom_root:
        raise StateError(f"custom root '{root}' requires --allow-custom-root; default root is {DEFAULT_ROOT}")
    return root_path.resolve()

def normalize_relative_path(relative: str | Path) -> str:
    rel = Path(str(relative).replace("\\", "/"))
    if rel.is_absolute() or rel.drive or rel.root:
        raise StateError(f"absolute paths are not allowed: {relative}")
    if not rel.parts or any(part in {"..", ""} for part in rel.parts):
        raise StateError(f"path traversal is not allowed: {relative}")
    return "/".join(rel.parts)

def safe_join(base: Path, relative: str | Path) -> Path:
    rel_text = normalize_relative_path(relative)
    candidate = (base / Path(rel_text)).resolve()
    base_resolved = base.resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise StateError(f"path escapes project run directory: {relative}") from exc
    return candidate

def generated_path_to_relative(run_dir: Path, source: str, require_exists: bool) -> str | None:
    src = Path(source).expanduser()
    if src.is_absolute() or src.drive or src.root:
        if require_exists and not src.exists():
            raise StateError(f"generated image path does not exist: {source}")
        try:
            return normalize_relative_path(src.resolve().relative_to(run_dir.resolve()))
        except ValueError:
            return None
    rel_path = normalize_relative_path(source)
    abs_path = safe_join(run_dir, rel_path)
    if require_exists and not abs_path.exists():
        raise StateError(f"generated image path does not exist under project run: {source}")
    return rel_path

def project_dir(args: Any) -> Path:
    project_id = normalize_project_id(args.project_id)
    root = resolve_root(args.root, getattr(args, "allow_custom_root", False))
    candidate = (root / project_id).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise StateError("resolved project directory escapes root") from exc
    return candidate

def state_file(run_dir: Path) -> Path:
    return safe_join(run_dir, STATE_RELATIVE_PATH)

def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)

def load_state(run_dir: Path) -> dict[str, Any]:
    path = state_file(run_dir)
    if not path.exists():
        raise StateError(f"state file does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))
