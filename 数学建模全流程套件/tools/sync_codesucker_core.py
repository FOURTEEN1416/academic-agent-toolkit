#!/usr/bin/env python3
"""Audited sync helper: reports the exact upstream ref; it never runs implicitly."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="https://github.com/fanbuz/codesucker")
    parser.add_argument("--ref", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.repo != "https://github.com/fanbuz/codesucker":
        raise SystemExit("only the approved upstream repository may be synchronized")
    payload = {"ok": args.dry_run, "repo": args.repo, "ref": args.ref, "action": "manual vendored sync required"}
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if args.dry_run else 2


if __name__ == "__main__":
    raise SystemExit(main())
