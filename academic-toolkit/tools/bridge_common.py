#!/usr/bin/env python3
"""Shared helpers for Phase 1 stable bridge tools."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.step_manifest import validate_manifest, write_manifest


def safe_workspace(path: str | Path) -> Path:
    workspace = Path(path).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def safe_path(workspace: Path, path: str | Path) -> Path:
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
    try:
        resolved.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError(f"path is outside workspace: {path}") from exc
    return resolved


def relpath(workspace: Path, path: str | Path) -> str:
    return Path(path).resolve().relative_to(workspace.resolve()).as_posix()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run_command(command: list[str], cwd: Path, timeout: int = 600) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "exitCode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def command_version(command: str | Path, args: list[str] | None = None) -> str:
    try:
        result = run_command([str(command), *(args or ["--version"])], cwd=PROJECT_ROOT, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "unavailable"
    text = (result.get("stdout") or result.get("stderr") or "").strip().splitlines()
    return text[0].strip() if text else "unknown"


def python_dependency_versions(names: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {"python": sys.version.split()[0]}
    for name in names:
        try:
            module = __import__(name)
            versions[name] = str(getattr(module, "__version__", "installed"))
        except Exception:
            versions[name] = "unavailable"
    return versions


def finalize_step_manifest(
    workspace: Path,
    step_name: str,
    config: dict[str, Any],
    inputs: list[Path],
    outputs: list[Path],
    backend: str,
    commands: list[dict[str, Any]],
    dependencies: dict[str, str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest_path = write_manifest(
        workspace=workspace,
        step_name=step_name,
        config=config,
        inputs=inputs,
        outputs=outputs,
        backend=backend,
        commands=commands,
        dependencies=dependencies,
        extra=extra,
    )
    validation = validate_manifest(workspace, manifest_path)
    return {"path": relpath(workspace, manifest_path), "validation": validation}


def print_result(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if payload.get("ok") else 1


def env_snapshot(keys: list[str]) -> dict[str, bool]:
    return {key: bool(os.environ.get(key)) for key in keys}
