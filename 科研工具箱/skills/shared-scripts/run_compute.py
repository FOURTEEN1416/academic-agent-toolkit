"""Run a workspace Python entry point with explicit paths, even in embedded Python.

No source rewriting, shell evaluation, directory guessing or global ._pth edits.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import runpy
import sys
import tokenize


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--cwd", choices=("workspace", "script"), default="workspace")
    parser.add_argument("--check", action="store_true", help="Check syntax/import locations without executing the script")
    parser.add_argument("--check-import", action="append", default=[])
    parser.add_argument("script")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    options = parser.parse_args(argv)
    root = options.workspace.resolve(strict=True)
    script = (root / options.script).resolve(strict=True)
    if not script.is_relative_to(root) or not script.is_file() or script.suffix.lower() != ".py":
        parser.error("entry point must be a Python file inside this workspace")
    paths = [script.parent, root / "code", root / "_utils", root]
    if any(not p.resolve().is_relative_to(root) for p in paths):
        parser.error("runtime import directory escapes workspace")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace", line_buffering=True)
    old_path, old_argv, old_cwd = sys.path[:], sys.argv[:], Path.cwd()
    try:
        sys.path[:0] = list(dict.fromkeys(str(p.resolve()) for p in paths))
        os.chdir(script.parent if options.cwd == "script" else root)
        with tokenize.open(script) as handle:
            compile(handle.read(), str(script), "exec")
        for name in options.check_import:
            if not name.isidentifier() or importlib.util.find_spec(name) is None:
                parser.error(f"module not found: {name}")
        if options.check:
            print("COMPUTE_PREFLIGHT_OK")
            return 0
        args = options.args[1:] if options.args[:1] == ["--"] else options.args
        sys.argv = [str(script), *args]
        runpy.run_path(str(script), run_name="__main__")
        return 0
    finally:
        sys.path[:], sys.argv[:] = old_path, old_argv
        os.chdir(old_cwd)


if __name__ == "__main__":
    raise SystemExit(main())
