#!/usr/bin/env python3
"""Convert standard source-materials JSON into copyright draft code pages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_selection(workspace: Path) -> dict[str, Any]:
    path = workspace / "source-materials" / "selection.json"
    return json.loads(path.read_text(encoding="utf-8"))


def write_code_pages(workspace: Path, output: Path, title: str) -> int:
    """Write stable Markdown pages from the standard selection result."""
    selection = load_selection(workspace)
    pages = selection.get("pages", [])
    if not pages:
        raise ValueError("selection contains no pages")
    output.parent.mkdir(parents=True, exist_ok=True)
    chunks = [f"# {title} 源程序材料", "", "<!-- generated from source-materials/selection.json -->", ""]
    for index, page in enumerate(pages, 1):
        start = page.get("startFile") or "unknown"
        end = page.get("endFile") or start
        chunks.extend([
            f"## 第{index}页",
            "",
            f"<!-- source: {start} -> {end} -->",
            "```",
            *page.get("lines", []),
            "```",
            "",
        ])
    output.write_text("\n".join(chunks), encoding="utf-8")
    return len(pages)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()
    print(write_code_pages(Path(args.workspace), Path(args.output), args.title))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
