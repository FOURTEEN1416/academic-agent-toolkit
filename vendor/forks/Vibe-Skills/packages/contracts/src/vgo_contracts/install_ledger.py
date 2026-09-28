from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def _is_safe_skill_name(value: str) -> bool:
    text = value.strip()
    if not text or text in {'.', '..'}:
        return False
    return '/' not in text and '\\' not in text and ':' not in text


def _normalize_relpath(value: object) -> str | None:
    text = str(value).replace('\\', '/').strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return None
    normalized = path.as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized or normalized == '.':
        return None
    parts = [part for part in Path(normalized).parts if part not in {'', '.'}]
    if any(part == '..' for part in parts):
        return None
    return '/'.join(parts)


def _validate_skill_names(values: list[str], *, field_name: str) -> None:
    bad = [name for name in values if not _is_safe_skill_name(str(name))]
    if bad:
        raise ValueError(f'invalid {field_name}: {bad}')


def _validate_relpaths(values: list[str], *, field_name: str) -> None:
    bad = [value for value in values if _normalize_relpath(value) is None]
    if bad:
        raise ValueError(f'invalid {field_name}: {bad}')


def _validate_path_values(values: list[str], *, field_name: str) -> None:
    bad = [value for value in values if not str(value).strip() or '\x00' in str(value)]
    if bad:
        raise ValueError(f'invalid {field_name}: {bad}')


def _validate_config_rollbacks(values: list[dict[str, object]]) -> None:
    bad: list[object] = []
    for entry in values:
        if not isinstance(entry, dict):
            bad.append(entry)
            continue
        path = entry.get('path')
        if _normalize_relpath(path) is None or '\x00' in str(path):
            bad.append(entry)
    if bad:
        raise ValueError(f'invalid config_rollbacks: {bad}')


@dataclass(slots=True)
class InstallLedger:
    managed_skill_names: list[str] = field(default_factory=list)
    runtime_roots: list[str] = field(default_factory=list)
    compatibility_roots: list[str] = field(default_factory=list)
    sidecar_roots: list[str] = field(default_factory=list)
    config_rollbacks: list[dict[str, object]] = field(default_factory=list)
    legacy_cleanup_candidates: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate_skill_names(self.managed_skill_names, field_name='managed skill names')
        _validate_relpaths(self.runtime_roots, field_name='runtime_roots')
        _validate_relpaths(self.compatibility_roots, field_name='compatibility_roots')
        _validate_relpaths(self.sidecar_roots, field_name='sidecar_roots')
        _validate_config_rollbacks(self.config_rollbacks)
        _validate_relpaths(self.legacy_cleanup_candidates, field_name='legacy_cleanup_candidates')
