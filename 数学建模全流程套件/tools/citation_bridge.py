#!/usr/bin/env python3
"""Stable citation-check bridge with manifest-backed outputs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .bridge_common import finalize_step_manifest, print_result, python_dependency_versions, relpath, safe_path, safe_workspace, write_json
except ImportError:
    from bridge_common import finalize_step_manifest, print_result, python_dependency_versions, relpath, safe_path, safe_workspace, write_json

try:
    from .citation_checker import check_bibtex, check_markdown_refs
except ImportError:
    from citation_checker import check_bibtex, check_markdown_refs


def check_citations(workspace: Path, input_path: Path) -> dict:
    content = input_path.read_text(encoding="utf-8", errors="ignore")
    if input_path.suffix.lower() == ".bib" or ("@" in content and "title" in content):
        mode = "bibtex"
        issues = check_bibtex(content)
    else:
        mode = "markdown"
        issues = check_markdown_refs(content)
    errors = [item for item in issues if item.get("severity") == "error"]
    warnings = [item for item in issues if item.get("severity") == "warning"]
    result_path = workspace / "citation_bridge_result.json"
    payload = {
        "ok": not errors,
        "mode": mode,
        "input": relpath(workspace, input_path),
        "total": len(issues),
        "errors": len(errors),
        "warnings": len(warnings),
        "issues": issues,
        "stepManifest": "STEP_MANIFEST.json",
    }
    write_json(result_path, payload)
    manifest_info = finalize_step_manifest(
        workspace,
        "citation-bridge",
        {"mode": mode},
        [input_path],
        [result_path],
        "citation_checker local",
        [{"command": ["python", "tools/citation_bridge.py", "--input", relpath(workspace, input_path)], "exitCode": 0 if payload["ok"] else 1}],
        python_dependency_versions([]),
    )
    payload["manifest"] = manifest_info
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Check citations through a stable bridge")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    workspace = safe_workspace(args.workspace)
    input_path = safe_path(workspace, args.input)
    return print_result(check_citations(workspace, input_path))


if __name__ == "__main__":
    sys.exit(main())
