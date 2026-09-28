from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_SRC = REPO_ROOT / 'apps' / 'vgo-cli' / 'src'
if str(CLI_SRC) not in sys.path:
    sys.path.insert(0, str(CLI_SRC))

from vgo_cli.upgrade_state import (
    is_upstream_cache_stale,
    load_upgrade_status,
    merge_upgrade_status,
    save_upgrade_status,
    upgrade_status_path,
)


def test_save_upgrade_status_creates_sidecar_on_first_write(tmp_path: Path) -> None:
    target_root = tmp_path / 'target'
    payload = {'host_id': 'codex', 'installed_version': '3.0.1'}

    save_upgrade_status(target_root, payload)

    assert upgrade_status_path(target_root).exists()
    assert load_upgrade_status(target_root) == payload


def test_is_upstream_cache_stale_respects_24_hour_boundary() -> None:
    now = datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc)
    fresh = {'remote_latest_checked_at': '2026-04-08T12:00:00Z'}
    stale = {'remote_latest_checked_at': '2026-04-08T11:59:59Z'}

    assert is_upstream_cache_stale({}, now=now) is True
    assert is_upstream_cache_stale(fresh, now=now) is False
    assert is_upstream_cache_stale(stale, now=now) is True


def test_merge_upgrade_status_preserves_cached_remote_fields_when_updating_installed_state(tmp_path: Path) -> None:
    target_root = tmp_path / 'target'
    existing = {
        'host_id': 'codex',
        'target_root': str(target_root.resolve()),
        'repo_remote': 'https://github.com/foryourhealth111-pixel/Vibe-Skills.git',
        'repo_default_branch': 'main',
        'installed_version': '3.0.0',
        'installed_commit': 'oldcommit',
        'installed_recorded_at': '2026-04-08T00:00:00Z',
        'remote_latest_commit': 'newcommit',
        'remote_latest_version': '3.0.1',
        'remote_latest_checked_at': '2026-04-09T00:00:00Z',
        'update_available': True,
    }

    merged = merge_upgrade_status(
        existing,
        installed={
            'host_id': 'codex',
            'target_root': target_root,
            'repo_remote': 'https://github.com/foryourhealth111-pixel/Vibe-Skills.git',
            'repo_default_branch': 'main',
            'installed_version': '3.0.1',
            'installed_commit': 'newcommit',
            'installed_recorded_at': datetime(2026, 4, 9, 8, 30, tzinfo=timezone.utc),
        },
    )

    assert merged['remote_latest_commit'] == 'newcommit'
    assert merged['remote_latest_version'] == '3.0.1'
    assert merged['remote_latest_checked_at'] == '2026-04-09T00:00:00Z'
    assert merged['installed_version'] == '3.0.1'
    assert merged['installed_commit'] == 'newcommit'
    assert merged['installed_recorded_at'] == '2026-04-09T08:30:00Z'
    assert merged['update_available'] is False
