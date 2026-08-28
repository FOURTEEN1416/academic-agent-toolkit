#!/usr/bin/env python3
"""Stable optimization/statistical solver bridge with manifest-backed outputs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .bridge_common import finalize_step_manifest, print_result, python_dependency_versions, relpath, safe_path, safe_workspace, write_json
except ImportError:
    from bridge_common import finalize_step_manifest, print_result, python_dependency_versions, relpath, safe_path, safe_workspace, write_json


def run_solver(workspace: Path, config_path: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    solver = str(config.get("solver", "scipy-linprog"))
    result_path = workspace / "solver_bridge_result.json"
    dependencies = python_dependency_versions(["numpy", "scipy"])
    ok = False
    payload: dict = {"solver": solver, "config": relpath(workspace, config_path), "dependencies": dependencies,
                    "stepManifest": "STEP_MANIFEST.json"}
    if solver == "scipy-linprog":
        try:
            from scipy.optimize import linprog
            c = config.get("c")
            if not isinstance(c, list) or not c:
                raise ValueError("config.c must be a non-empty list")
            res = linprog(
                c,
                A_ub=config.get("A_ub"),
                b_ub=config.get("b_ub"),
                A_eq=config.get("A_eq"),
                b_eq=config.get("b_eq"),
                bounds=config.get("bounds"),
                method=config.get("method", "highs"),
            )
            ok = bool(res.success)
            payload.update({
                "ok": ok,
                "status": int(res.status),
                "message": str(res.message),
                "objective": float(res.fun) if res.fun is not None else None,
                "x": [float(v) for v in res.x] if res.x is not None else [],
            })
        except Exception as exc:
            payload.update({"ok": False, "error": str(exc)})
    else:
        payload.update({"ok": False, "error": f"unsupported solver: {solver}"})
    write_json(result_path, payload)
    manifest_info = finalize_step_manifest(
        workspace,
        "solver-bridge",
        config,
        [config_path],
        [result_path],
        f"{solver} via scipy {dependencies.get('scipy', 'unavailable')}",
        [{"command": ["python", "tools/solver_bridge.py", "--config", relpath(workspace, config_path)], "exitCode": 0 if ok else 1}],
        dependencies,
    )
    payload["manifest"] = manifest_info
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a solver through a stable bridge")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    workspace = safe_workspace(args.workspace)
    config_path = safe_path(workspace, args.config)
    return print_result(run_solver(workspace, config_path))


if __name__ == "__main__":
    sys.exit(main())
