#!/usr/bin/env python3
"""Repository-local entry point for PaperSpine × PaperFigure integration."""

from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paperspine_figure_integration.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
