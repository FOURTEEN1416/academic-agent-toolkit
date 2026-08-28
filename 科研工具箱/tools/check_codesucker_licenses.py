#!/usr/bin/env python3
"""Verify vendored CodeSucker attribution files before source-materials use."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent / "codesucker-core"
REQUIRED = ("LICENSE", "NOTICE", "UPSTREAM.md", "package.json", "packages/core/package.json")


def main() -> int:
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    upstream = (ROOT / "UPSTREAM.md").read_text(encoding="utf-8") if not missing else ""
    ok = not missing and "Apache-2.0" in upstream and "Pinned commit:" in upstream
    print(json.dumps({"ok": ok, "missing": missing, "root": str(ROOT)}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
