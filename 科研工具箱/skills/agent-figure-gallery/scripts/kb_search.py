#!/usr/bin/env python3
"""Read-only search over the AgentFigureGallery reference KB.

Host-neutral. Resolves the KB root from (1) $AGENT_FIGURE_GALLERY_ROOT,
(2) $DRAWING_KB_ROOT, (3) the repo-local vendor source
vendor/forks/AgentFigureGallery derived from this script's location.
Never writes to the KB. If no root is found, prints a TOOL_GAP report
and exits 2 (no traceback).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PLOT_HINTS = [
    ("heatmap_matrix", ["heatmap", "matrix", "density"]),
    ("box_violin_distribution", ["box", "violin", "distribution"]),
    ("bar_chart", ["bar", "column"]),
    ("line_chart", ["line", "trend", "trajectory", "training curve"]),
    ("embedding_plot", ["umap", "tsne", "t-sne", "embedding"]),
    ("scatter_plot", ["scatter", "correlation", "pareto"]),
    ("spatial_map", ["spatial", "tissue"]),
    ("microscopy_panel", ["microscopy", "segmentation"]),
    ("benchmark_performance", ["benchmark", "performance", "accuracy"]),
    ("multi_panel_figure", ["multi-panel", "multipanel", "panel"]),
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def resolve_root() -> tuple[Path | None, list[str]]:
    checked: list[str] = []
    for key in ("AGENT_FIGURE_GALLERY_ROOT", "DRAWING_KB_ROOT"):
        value = os.environ.get(key)
        if value:
            p = Path(value).expanduser()
            checked.append(f"{key} -> {p}")
            if (p / "data" / "reference_candidate_index.json").exists():
                return p, checked
    vendored = repo_root() / "vendor" / "forks" / "AgentFigureGallery"
    checked.append(f"vendor fallback -> {vendored}")
    if (vendored / "data" / "reference_candidate_index.json").exists():
        return vendored, checked
    return None, checked


def infer_plot_type(task: str, explicit: str) -> str:
    if explicit:
        return explicit
    text = task.lower()
    for plot_type, words in PLOT_HINTS:
        if any(word in text for word in words):
            return plot_type
    return ""


def score(item: dict, terms: list[str]) -> float:
    hay = " ".join([
        str(item.get("plot_type", "")),
        " ".join(item.get("tags", [])),
        str(item.get("why_suggested", "")),
        str(item.get("source_repo", "")),
    ]).lower()
    return sum(1.0 for t in terms if t and t in hay) + 0.01 * float(item.get("quality_score") or 0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--task", default="", help="free-text plotting task")
    ap.add_argument("--plot-type", default="", help="explicit plot type filter")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    kb_root, checked = resolve_root()
    if kb_root is None:
        print("TOOL_GAP: AgentFigureGallery KB not found. Paths checked:")
        for line in checked:
            print(f"  - {line}")
        print("Fix: set AGENT_FIGURE_GALLERY_ROOT to a KB checkout, or restore")
        print("the repo-local vendor source at vendor/forks/AgentFigureGallery.")
        return 2
    index = json.loads((kb_root / "data" / "reference_candidate_index.json").read_text(encoding="utf-8"))
    candidates = index.get("candidates", [])
    plot_type = infer_plot_type(args.task, args.plot_type)
    terms = [w for w in (args.task + " " + plot_type).lower().replace("-", " ").split() if len(w) > 2]
    hits = [c for c in candidates if not plot_type or c.get("plot_type") == plot_type]
    hits.sort(key=lambda c: score(c, terms), reverse=True)
    hits = hits[: max(1, args.limit)]
    try:
        kb_display = kb_root.resolve().relative_to(repo_root().resolve())
    except ValueError:
        kb_display = kb_root.resolve()
    out = {
        "kb_root": str(kb_display),
        "index_source": f"{kb_display}/data/reference_candidate_index.json",
        "resolved_plot_type": plot_type or "any",
        "total_candidates": len(candidates),
        "results": [
            {
                "candidate_id": c.get("stable_candidate_id"),
                "plot_type": c.get("plot_type"),
                "source_repo": c.get("source_repo"),
                "quality_score": c.get("quality_score"),
                "preview_path": c.get("preview_path_rel"),
                "script_path": c.get("script_path_rel"),
                "why_suggested": c.get("why_suggested"),
            }
            for c in hits
        ],
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
