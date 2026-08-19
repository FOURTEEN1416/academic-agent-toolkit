#!/usr/bin/env python3
"""Stable visual-check bridge for TikZ, draw.io, and data figures."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .bridge_common import finalize_step_manifest, print_result, python_dependency_versions, relpath, run_command, safe_path, safe_workspace, write_json
except ImportError:
    from bridge_common import finalize_step_manifest, print_result, python_dependency_versions, relpath, run_command, safe_path, safe_workspace, write_json


TOOLS_DIR = Path(__file__).resolve().parent
BACKENDS = {
    "tikz": TOOLS_DIR / "tikz_vision_check.py",
    "drawio": TOOLS_DIR / "drawio_vision_check.py",
    "data-fig": TOOLS_DIR / "data_fig_vision_check.py",
}


def run_visual_check(workspace: Path, image_path: Path, backend: str, review: bool) -> dict:
    if backend not in BACKENDS:
        raise ValueError(f"unsupported visual backend: {backend}")
    script = BACKENDS[backend]
    command = [sys.executable, str(script), str(image_path)]
    if backend == "tikz" and review:
        command.append("--review")
    result = run_command(command, cwd=workspace, timeout=180)
    status = "pass" if result["exitCode"] == 0 else ("unavailable" if result["exitCode"] == 2 else "fail")
    result_path = workspace / "visual_bridge_result.json"
    payload = {
        "ok": status == "pass",
        "status": status,
        "backend": backend,
        "image": relpath(workspace, image_path),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "reviewMode": review,
        "stepManifest": "STEP_MANIFEST.json",
    }
    write_json(result_path, payload)
    manifest_info = finalize_step_manifest(
        workspace,
        "visual-bridge",
        {"backend": backend, "review": review},
        [image_path],
        [result_path],
        f"{backend} visual checker",
        [{"command": result["command"], "cwd": result["cwd"], "exitCode": result["exitCode"]}],
        python_dependency_versions(["PIL"]),
    )
    payload["manifest"] = manifest_info
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run visual checks through a stable bridge")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--backend", default="tikz", choices=sorted(BACKENDS))
    parser.add_argument("--review", action="store_true")
    args = parser.parse_args()
    workspace = safe_workspace(args.workspace)
    image_path = safe_path(workspace, args.image)
    return print_result(run_visual_check(workspace, image_path, args.backend, args.review))


if __name__ == "__main__":
    sys.exit(main())
