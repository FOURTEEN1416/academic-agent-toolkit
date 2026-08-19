#!/usr/bin/env python3
"""Stable LaTeX compilation bridge with manifest-backed outputs."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    from .bridge_common import command_version, finalize_step_manifest, print_result, relpath, run_command, safe_path, safe_workspace, write_json
except ImportError:
    from bridge_common import command_version, finalize_step_manifest, print_result, relpath, run_command, safe_path, safe_workspace, write_json


def _find_engine(engine: str) -> str | None:
    return shutil.which(engine)


def compile_latex(workspace: Path, tex: Path, engine: str, runs: int, timeout: int) -> dict:
    pdf = tex.with_suffix(".pdf")
    log = workspace / "latex_bridge.log"
    commands = []
    ok = True
    messages = []
    executable = _find_engine(engine)
    if not executable:
        result = {
            "ok": False,
            "error": f"LaTeX engine unavailable: {engine}",
            "engine": engine,
            "pdf": relpath(workspace, pdf) if pdf.exists() else "",
            "stepManifest": "STEP_MANIFEST.json",
        }
        write_json(workspace / "latex_bridge_result.json", result)
        manifest_info = finalize_step_manifest(
            workspace,
            "latex-bridge",
            {"engine": engine, "runs": runs, "timeout": timeout},
            [tex],
            [workspace / "latex_bridge_result.json"],
            f"{engine} unavailable",
            [],
            {},
        )
        result["manifest"] = manifest_info
        return result
    for _ in range(max(1, runs)):
        command = [executable, "-interaction=nonstopmode", "-halt-on-error", tex.name]
        command_result = run_command(command, cwd=tex.parent, timeout=timeout)
        commands.append({k: v for k, v in command_result.items() if k in ("command", "cwd", "exitCode")})
        messages.append(command_result.get("stdout", ""))
        messages.append(command_result.get("stderr", ""))
        if command_result["exitCode"] != 0:
            ok = False
            break
    log.write_text("\n".join(messages), encoding="utf-8")
    result = {
        "ok": ok and pdf.is_file(),
        "engine": engine,
        "engineVersion": command_version(executable, ["--version"]),
        "tex": relpath(workspace, tex),
        "pdf": relpath(workspace, pdf) if pdf.exists() else "",
        "log": relpath(workspace, log),
        "runs": len(commands),
        "stepManifest": "STEP_MANIFEST.json",
    }
    result_path = workspace / "latex_bridge_result.json"
    write_json(result_path, result)
    manifest_info = finalize_step_manifest(
        workspace,
        "latex-bridge",
        {"engine": engine, "runs": runs, "timeout": timeout},
        [tex],
        [result_path, log] + ([pdf] if pdf.exists() else []),
        f"{engine} {result['engineVersion']}",
        commands,
        {"latex_engine": result["engineVersion"]},
    )
    result["manifest"] = manifest_info
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile LaTeX through a stable bridge")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--tex", required=True)
    parser.add_argument("--engine", default="xelatex", choices=["xelatex", "pdflatex", "lualatex"])
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    workspace = safe_workspace(args.workspace)
    tex = safe_path(workspace, args.tex)
    return print_result(compile_latex(workspace, tex, args.engine, args.runs, args.timeout))


if __name__ == "__main__":
    sys.exit(main())
