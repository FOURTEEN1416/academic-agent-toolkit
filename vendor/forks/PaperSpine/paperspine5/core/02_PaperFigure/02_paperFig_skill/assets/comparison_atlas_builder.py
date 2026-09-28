#!/usr/bin/env python3
"""Config-driven public-reference-above/project-redraw-below PDF builder.

Project page builders implement:
    build(subfigure, rng, array_store, page_config)
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle
import numpy as np
from PIL import Image


NAVY = "#2c578b"

mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 7.2,
    "axes.titlesize": 8.2,
    "axes.labelsize": 6.8,
    "xtick.labelsize": 5.8,
    "ytick.labelsize": 5.8,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def load_builder(spec: str):
    module_name, function_name = spec.split(":", 1)
    return getattr(importlib.import_module(module_name), function_name)


def banner(fig, title: str) -> None:
    fig.add_artist(Rectangle((0, 0.948), 1, 0.052,
                             transform=fig.transFigure, color=NAVY, zorder=30))
    fig.text(0.026, 0.973, title, color="white", fontsize=15.5,
             fontweight="bold", va="center", zorder=31)
    fig.text(0.975, 0.973, "PUBLIC REFERENCES ABOVE  |  PROJECT FIGURE BELOW",
             color="white", fontsize=7.3, fontweight="bold",
             ha="right", va="center", zorder=31)


def reference_row(subfig, references: list[dict]) -> None:
    axes = np.atleast_1d(subfig.subplots(1, len(references)))
    subfig.subplots_adjust(left=0.035, right=0.985, bottom=0.03,
                           top=0.82, wspace=0.05)
    subfig.suptitle("PUBLIC REFERENCE FIGURES", y=0.91,
                    color="#a02b22", fontsize=9.5, fontweight="bold")
    for index, (ax, reference) in enumerate(zip(axes, references), start=1):
        ax.imshow(Image.open(reference["path"]).convert("RGB"))
        ax.axis("off")
        ax.set_title(reference.get("citation", f"Reference {index}"), loc="left",
                     color="#3f4a52", fontsize=7.0, fontweight="bold", pad=4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    project_root = Path(config["project_root"]).resolve()
    sys.path.insert(0, str(project_root))

    output_pdf = Path(config["output_pdf"])
    output_arrays = Path(config["output_arrays"])
    preview_dir = Path(config.get("preview_dir", output_pdf.parent / "preview"))
    for directory in (output_pdf.parent, output_arrays.parent, preview_dir):
        directory.mkdir(parents=True, exist_ok=True)

    seed = int(config.get("layout_seed", 20260802))
    store: dict[str, np.ndarray] = {}
    with PdfPages(output_pdf) as pdf:
        for page_number, page in enumerate(config["pages"], start=1):
            fig = plt.figure(figsize=tuple(config.get("page_size", [12.4, 15.8])),
                             dpi=150)
            banner(fig, page["title"])
            top, bottom = fig.subfigures(2, 1,
                                         height_ratios=[0.34, 0.66], hspace=0.035)
            reference_row(top, page["references"])
            load_builder(page["builder"])(
                bottom, np.random.default_rng(seed + page_number), store, page
            )
            fig.text(0.5, 0.012,
                     page.get("footer", "Project figure generated from verified code and data."),
                     ha="center", fontsize=6.4, color="#67727a")
            pdf.savefig(fig)
            fig.savefig(preview_dir / f"page-{page_number}.png", dpi=120)
            plt.close(fig)

    store["layout_seed"] = np.asarray([seed], dtype=np.int64)
    np.savez_compressed(output_arrays, **store)
    print(output_pdf.resolve())
    print(output_arrays.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

