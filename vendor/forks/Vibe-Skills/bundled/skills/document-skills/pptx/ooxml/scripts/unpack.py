#!/usr/bin/env python3
"""Thin wrapper that dispatches to the sibling document-skills OOXML unpacker."""

import sys
from pathlib import Path


def main() -> None:
    shared_script = (
        Path(__file__).resolve().parents[3] / "docx" / "ooxml" / "scripts" / "unpack.py"
    )
    sys.path.insert(0, str(shared_script.parent))
    globals_dict = {"__name__": "__main__", "__file__": str(shared_script)}
    exec(compile(shared_script.read_text(encoding="utf-8"), str(shared_script), "exec"), globals_dict)


if __name__ == "__main__":
    main()
