#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


sys.dont_write_bytecode = True
CORE_SRC = Path(__file__).resolve().parents[2] / "packages" / "verification-core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from vgo_verify.proof_publication import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
