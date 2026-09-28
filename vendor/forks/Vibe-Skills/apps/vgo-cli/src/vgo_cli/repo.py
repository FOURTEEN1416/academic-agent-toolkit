from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


CONTRACTS_SRC = Path(__file__).resolve().parents[4] / 'packages' / 'contracts' / 'src'
if str(CONTRACTS_SRC) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_SRC))

from vgo_contracts.installed_runtime_contract import default_installed_runtime_config, merge_installed_runtime_config

_GIT_CAPTURE_TIMEOUT_SECONDS = 5


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def load_governance(repo_root: Path) -> dict:
    return load_json(repo_root / 'config' / 'version-governance.json')


def _run_git_capture(repo_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ['git', '-C', str(repo_root), *args],
            capture_output=True,
            text=True,
            timeout=_GIT_CAPTURE_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ''
    if result.returncode != 0:
        return ''
    return result.stdout.strip()


def get_installed_runtime_config(repo_root: Path) -> dict[str, object]:
    return merge_installed_runtime_config(load_governance(repo_root), default_installed_runtime_config())


def get_local_release_metadata(repo_root: Path) -> dict[str, str]:
    release = load_governance(repo_root).get('release') or {}
    return {
        'version': str(release.get('version') or '').strip(),
        'updated': str(release.get('updated') or '').strip(),
        'channel': str(release.get('channel') or '').strip(),
    }


def get_official_self_repo_metadata(repo_root: Path) -> dict[str, str]:
    governance = load_governance(repo_root)
    source = governance.get('source_of_truth') or {}
    official_repo = source.get('official_self_repo') or {}
    canonical_root = str(official_repo.get('canonical_root') or source.get('canonical_root') or '.').strip() or '.'
    repo_url = str(official_repo.get('repo_url') or '').strip() or _run_git_capture(
        repo_root,
        'config',
        '--get',
        'remote.origin.url',
    )
    default_branch = str(official_repo.get('default_branch') or '').strip()
    if not default_branch:
        remote_head = _run_git_capture(repo_root, 'symbolic-ref', 'refs/remotes/origin/HEAD')
        default_branch = remote_head.rsplit('/', 1)[-1].strip() if remote_head else ''
    default_branch = default_branch or 'main'
    return {
        'repo_url': repo_url,
        'default_branch': default_branch,
        'canonical_root': canonical_root,
    }


def get_repo_head_commit(repo_root: Path) -> str:
    # Install metadata should degrade cleanly when git is unavailable.
    return _run_git_capture(repo_root, 'rev-parse', 'HEAD')


def resolve_canonical_repo_root(start_path: Path) -> Path | None:
    current = start_path.resolve()
    while True:
        if (current / '.git').exists() and (current / 'config' / 'version-governance.json').exists():
            return current
        if current.parent == current:
            return None
        current = current.parent
