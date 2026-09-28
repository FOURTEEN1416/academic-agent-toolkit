from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repo_ships_pack_manifest_contract() -> None:
    manifest_path = REPO_ROOT / "config" / "pack-manifest.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))

    assert isinstance(manifest.get("packs"), list)
    assert manifest["packs"]
