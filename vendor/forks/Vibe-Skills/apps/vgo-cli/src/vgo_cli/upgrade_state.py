from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any


UPGRADE_STATUS_RELPATH = Path('.vibeskills') / 'upgrade-status.json'
UPSTREAM_CACHE_TTL = timedelta(hours=24)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')


def _parse_timestamp(raw: object) -> datetime | None:
    text = str(raw or '').strip()
    if not text:
        return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def upgrade_status_path(target_root: Path) -> Path:
    return target_root / UPGRADE_STATUS_RELPATH


def load_upgrade_status(target_root: Path) -> dict[str, Any]:
    path = upgrade_status_path(target_root)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save_upgrade_status(target_root: Path, payload: dict[str, Any]) -> Path:
    path = upgrade_status_path(target_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return path


def is_upstream_cache_stale(status: dict[str, Any] | None, *, now: datetime | None = None) -> bool:
    effective_now = (now or _utc_now()).astimezone(timezone.utc)
    checked_at = _parse_timestamp((status or {}).get('remote_latest_checked_at'))
    if checked_at is None:
        return True
    return effective_now - checked_at > UPSTREAM_CACHE_TTL


def merge_upgrade_status(
    existing: dict[str, Any] | None = None,
    *,
    installed: dict[str, Any] | None = None,
    remote: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(existing or {})

    if installed:
        recorded_at = installed.get('installed_recorded_at')
        if isinstance(recorded_at, datetime):
            recorded_at_text = _to_utc_timestamp(recorded_at)
        else:
            recorded_at_text = _to_utc_timestamp(_parse_timestamp(recorded_at) or _utc_now())
        merged.update(
            {
                'host_id': str(installed.get('host_id') or merged.get('host_id') or '').strip(),
                'target_root': str(Path(installed.get('target_root') or merged.get('target_root') or '.').resolve()),
                'repo_remote': str(installed.get('repo_remote') or merged.get('repo_remote') or '').strip(),
                'repo_default_branch': str(installed.get('repo_default_branch') or merged.get('repo_default_branch') or '').strip(),
                'installed_version': str(installed.get('installed_version') or '').strip(),
                'installed_commit': str(installed.get('installed_commit') or '').strip(),
                'installed_recorded_at': recorded_at_text,
            }
        )

    if remote:
        checked_at = remote.get('remote_latest_checked_at')
        if isinstance(checked_at, datetime):
            checked_at_text = _to_utc_timestamp(checked_at)
        else:
            checked_at_text = _to_utc_timestamp(_parse_timestamp(checked_at) or _utc_now())
        merged.update(
            {
                'remote_latest_commit': str(remote.get('remote_latest_commit') or '').strip(),
                'remote_latest_version': str(remote.get('remote_latest_version') or '').strip(),
                'remote_latest_checked_at': checked_at_text,
            }
        )

    installed_commit = str(merged.get('installed_commit') or '').strip()
    remote_commit = str(merged.get('remote_latest_commit') or '').strip()
    installed_version = str(merged.get('installed_version') or '').strip()
    remote_version = str(merged.get('remote_latest_version') or '').strip()
    merged['update_available'] = bool(
        (remote_commit and installed_commit and remote_commit != installed_commit)
        or (remote_version and installed_version and remote_version != installed_version)
    )
    return merged
