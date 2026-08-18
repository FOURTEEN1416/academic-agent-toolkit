#!/usr/bin/env python3
"""Asset-inventory adapter for source-materials metadata-only scans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.codesucker_bridge import run_source_materials


def inventory_code_project(project_root: Path, workspace: Path, title: str = "资产源码 V1.0") -> dict[str, Any]:
    manifest = run_source_materials(
        {
            "root": str(project_root.resolve()),
            "title": title,
            "extensions": ["py", "ts", "tsx", "js", "java", "go", "rs"],
            "excludes": [".git", "node_modules", "dist", "build", "__pycache__", "*.lock"],
            "sourceMode": "inventory",
        },
        workspace,
    )
    return {
        "manifest": "source-materials/SOURCE_MATERIALS_MANIFEST.json",
        "backend": manifest["backend"],
        "coreVersion": manifest["coreVersion"],
        "rulesVersion": manifest["rulesVersion"],
        "files": len(json.loads((workspace / "source-materials" / "files.json").read_text(encoding="utf-8")).get("files", [])),
        "auditWarnings": [item for item in manifest.get("audit", []) if item.get("status") == "warn"],
    }
