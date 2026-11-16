#!/usr/bin/env python3
"""Stage a verified full-suite Skill with a persistent installed-suite pointer."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_release import verify_bundle
from stable_update_adapter import handle


def stage_skill(archive: Path, installed: Path, prepared: Path) -> dict:
    candidate = verify_bundle(archive)
    active = verify_bundle(installed)
    for key in ("build_id", "content_index_sha256", "product_version", "platform"):
        if active[key] != candidate[key]:
            raise ValueError(f"installed suite differs from verified archive: {key}")
    if prepared.exists():
        raise ValueError("prepared Skill target must be absent")
    result = handle({"protocol": "paperspine-updater/1", "action": "prepare",
                     "bundle_archive": str(archive), "bundle_root": str(installed),
                     "prepared_root": str(prepared)})
    if result.get("status") != "PASS":
        raise RuntimeError("prepared Skill launcher probe failed")
    pointer = json.loads((prepared / "references" / "installed-suite.json").read_text(encoding="utf-8"))
    if pointer.get("suite_root") != str(installed) or pointer.get("build_id") != active["build_id"]:
        raise RuntimeError("prepared Skill pointer does not bind the installed suite")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--prepared-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage_skill(args.archive, args.installed_root, args.prepared_root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
