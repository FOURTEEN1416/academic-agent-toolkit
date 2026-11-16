"""Use Windows extended paths for already-authorized local file I/O."""
from __future__ import annotations

import os
from pathlib import Path


def native_path(path: str | Path) -> Path:
    """Keep the logical path for receipts; prefix only the path used for I/O.

    Callers must validate containment and reparse points before using a path.
    This does not grant access or normalize untrusted relative paths.
    """
    value = Path(path)
    if os.name != "nt" or not value.is_absolute():
        return value
    raw = str(value)
    if raw.startswith("\\\\?\\"):
        return value
    if raw.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + raw[2:])
    return Path("\\\\?\\" + raw)
