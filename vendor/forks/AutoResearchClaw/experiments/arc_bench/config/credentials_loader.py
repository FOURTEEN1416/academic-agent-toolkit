"""Tiny credentials loader for ARC-Bench scripts.

Loads ``experiments/arc_bench/config/.env.local`` (gitignored) and
``credentials.example.env`` (committed defaults), exporting them into
``os.environ`` if not already set.  Real values in ``.env.local`` always
win over the example template.

Usage at the top of any bench script:

    from experiments.arc_bench.config.credentials_loader import load_credentials
    load_credentials()
"""

from __future__ import annotations

import os
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent
_LOCAL = _CONFIG_DIR / ".env.local"
_EXAMPLE = _CONFIG_DIR / "credentials.example.env"


def _parse(env_file: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not env_file.is_file():
        return out
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def load_credentials(*, override: bool = False) -> dict[str, str]:
    """Load .env.local then example, set into ``os.environ``.

    Parameters
    ----------
    override:
        If False (default), pre-existing env vars win.  If True, file values
        clobber the existing process environment.

    Returns
    -------
    The merged credential dict (post-merge values, with example placeholders
    replaced by .env.local entries).
    """
    merged = _parse(_EXAMPLE)
    merged.update(_parse(_LOCAL))
    for k, v in merged.items():
        if v.startswith("REPLACE-ME") or v == "":
            continue
        if override or k not in os.environ:
            os.environ[k] = v
    return merged


__all__ = ["load_credentials"]
