from __future__ import annotations

import json
from pathlib import Path
import shutil


def seed_live_document_contract(
    workspace_root: Path,
    *,
    source_root: Path | None = None,
) -> None:
    """Seed the executable live contract into a temporary workspace fixture."""
    repository_root = source_root or Path(__file__).resolve().parents[2]
    config_root = workspace_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        repository_root / "config" / "live-document-contract.json",
        config_root / "live-document-contract.json",
    )


def seed_live_document_workspace(
    workspace_root: Path,
    *,
    source_root: Path | None = None,
) -> None:
    """Seed the contract and every registered live document into a fixture."""
    repository_root = source_root or Path(__file__).resolve().parents[2]
    seed_live_document_contract(workspace_root, source_root=repository_root)
    contract = json.loads(
        (repository_root / "config" / "live-document-contract.json").read_text(
            encoding="utf-8"
        )
    )
    for document in contract["documents"]:
        relative_path = Path(str(document["path"]))
        source_path = repository_root / relative_path
        destination = workspace_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
