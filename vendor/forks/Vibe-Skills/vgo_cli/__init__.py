from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_PACKAGE_DIR = REPO_ROOT / "apps" / "vgo-cli" / "src" / "vgo_cli"

if not REAL_PACKAGE_DIR.is_dir():
    raise ModuleNotFoundError(f"missing vgo_cli package directory: {REAL_PACKAGE_DIR}")

for source_root in sorted(path for path in (REPO_ROOT / "packages").glob("*/src") if path.is_dir()):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

real_package_dir_text = str(REAL_PACKAGE_DIR)
if real_package_dir_text not in __path__:
    __path__.insert(0, real_package_dir_text)
