#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


sys.dont_write_bytecode = True
CORE_SRC = Path(__file__).resolve().parents[2] / "packages" / "verification-core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from vgo_verify.test_baseline_audit import (  # noqa: E402
    PolicyError,
    build_artifact,
    build_collect_commands,
    build_run_layer_command,
    classify_node,
    load_policy,
    main,
    parse_collect_output,
    render_markdown,
    run_collect_commands,
    run_layer,
    scan_file_risks,
    select_layer_files,
    write_artifacts,
)

__all__ = [
    "PolicyError",
    "build_artifact",
    "build_collect_commands",
    "build_run_layer_command",
    "classify_node",
    "load_policy",
    "main",
    "parse_collect_output",
    "render_markdown",
    "run_collect_commands",
    "run_layer",
    "scan_file_risks",
    "select_layer_files",
    "write_artifacts",
]


if __name__ == "__main__":
    raise SystemExit(main())
