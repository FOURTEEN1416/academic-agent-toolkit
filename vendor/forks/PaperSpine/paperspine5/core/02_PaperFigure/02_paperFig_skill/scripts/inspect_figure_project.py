#!/usr/bin/env python3
"""Inventory figures, plotting sources, and data-read evidence in a project."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import re


SOURCE_EXTS = {".py", ".r", ".m", ".jl", ".ipynb"}
FIGURE_EXTS = {".pdf", ".png", ".svg", ".eps", ".tif", ".tiff"}
DATA_EXTS = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".npy", ".npz", ".parquet"}
SKIP_PARTS = {".git", "__pycache__", "node_modules", ".venv", "venv"}

READ_PATTERNS = [
    re.compile(r"""(?:read_csv|read_excel|read_table|read_parquet|np\.load|numpy\.load)\s*\(\s*[rRuUbBfF]*["']([^"']+)["']"""),
    re.compile(r"""open\s*\(\s*[rRuUbBfF]*["']([^"']+\.(?:csv|tsv|json|npy|npz|xlsx|xls|parquet))["']""", re.I),
]
WRITE_PATTERNS = [
    re.compile(r"""(?:savefig|write_image|write_html)\s*\(\s*[rRuUbBfF]*["']([^"']+)["']"""),
]


def should_skip(path: Path) -> bool:
    return any(part.lower() in SKIP_PARTS for part in path.parts)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1", errors="ignore")


def normalize_stem(path: Path) -> str:
    stem = path.stem.lower()
    for prefix in ("deep_", "plot_", "make_", "build_", "gen_", "_gen_", "_src_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", stem)


def inspect(root: Path) -> dict:
    files = [p for p in root.rglob("*") if p.is_file() and not should_skip(p.relative_to(root))]
    figures = sorted(p for p in files if p.suffix.lower() in FIGURE_EXTS)
    data_files = sorted(p for p in files if p.suffix.lower() in DATA_EXTS)
    sources = sorted(p for p in files if p.suffix.lower() in SOURCE_EXTS)

    source_records = []
    mentioned_outputs: dict[str, list[Path]] = defaultdict(list)
    for source in sources:
        text = read_text(source) if source.suffix.lower() != ".ipynb" else read_text(source)
        reads = []
        writes = []
        for pattern in READ_PATTERNS:
            reads.extend(pattern.findall(text))
        for pattern in WRITE_PATTERNS:
            writes.extend(pattern.findall(text))
        for output in writes:
            mentioned_outputs[Path(output).name.lower()].append(source)
        source_records.append({"path": source, "reads": sorted(set(reads)), "writes": sorted(set(writes))})

    by_stem: dict[str, list[Path]] = defaultdict(list)
    for source in sources:
        by_stem[normalize_stem(source)].append(source)

    mappings = []
    for figure in figures:
        candidates = list(mentioned_outputs.get(figure.name.lower(), []))
        fstem = normalize_stem(figure)
        if fstem in by_stem:
            candidates.extend(by_stem[fstem])
        # Partial stem evidence is useful for paired A/B or v2/v3 files.
        if not candidates and len(fstem) >= 5:
            for sstem, paths in by_stem.items():
                if fstem in sstem or sstem in fstem:
                    candidates.extend(paths)
        seen = set()
        unique = []
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                unique.append(candidate)
        mappings.append((figure, unique))

    return {
        "figures": figures,
        "data_files": data_files,
        "sources": source_records,
        "mappings": mappings,
    }


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def render_markdown(result: dict, root: Path) -> str:
    lines = [
        "# Figure project source map",
        "",
        f"- Project root: `{root}`",
        f"- Figures: {len(result['figures'])}",
        f"- Plotting sources: {len(result['sources'])}",
        f"- Local data files: {len(result['data_files'])}",
        "",
        "## Figure-to-code candidates",
        "",
        "| Figure | Candidate plotting source | Status |",
        "|---|---|---|",
    ]
    for figure, candidates in result["mappings"]:
        candidate_text = "<br>".join(f"`{rel(p, root)}`" for p in candidates) or "unresolved"
        status = "candidate" if candidates else "unresolved"
        lines.append(f"| `{rel(figure, root)}` | {candidate_text} | {status} |")

    lines.extend(
        [
            "",
            "## Data-read and output-path evidence",
            "",
            "| Source | Data reads | Figure writes |",
            "|---|---|---|",
        ]
    )
    for record in result["sources"]:
        reads = "<br>".join(f"`{p}`" for p in record["reads"]) or "-"
        writes = "<br>".join(f"`{p}`" for p in record["writes"]) or "-"
        lines.append(f"| `{rel(record['path'], root)}` | {reads} | {writes} |")

    lines.extend(["", "## Local data files", ""])
    if result["data_files"]:
        lines.extend(f"- `{rel(path, root)}`" for path in result["data_files"])
    else:
        lines.append("- None discovered inside the project root. Inspect absolute paths in the source table.")
    lines.extend(
        [
            "",
            "## Verification note",
            "",
            "This report records filename and code evidence. Visually verify the selected mapping before redraw.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Project root not found: {root}")
    result = inspect(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(result, root), encoding="utf-8")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

