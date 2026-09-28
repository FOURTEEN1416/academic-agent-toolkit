from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_CORE_SRC = REPO_ROOT / 'packages' / 'installer-core' / 'src'
CONTRACTS_SRC = REPO_ROOT / 'packages' / 'contracts' / 'src'
for src in (INSTALLER_CORE_SRC, CONTRACTS_SRC):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

from vgo_installer.materializer import install_opencode_guidance_payload


def test_install_opencode_guidance_payload_requires_example_scaffold(tmp_path: Path) -> None:
    repo_root = tmp_path / 'repo'
    (repo_root / 'config' / 'opencode' / 'commands').mkdir(parents=True)
    (repo_root / 'config' / 'opencode' / 'agents').mkdir(parents=True)
    target_root = tmp_path / 'target'
    target_root.mkdir()

    with pytest.raises(FileNotFoundError, match='opencode.json.example'):
        install_opencode_guidance_payload(
            repo_root,
            target_root,
            copy_tree_fn=lambda _src, _dst: None,
            copy_file_fn=lambda _src, _dst: None,
        )
