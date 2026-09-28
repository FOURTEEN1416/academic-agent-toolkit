from __future__ import annotations

from pathlib import Path
from typing import Mapping


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _is_absolute_target_root(value: str) -> bool:
    if value.startswith("/") or value.startswith("\\"):
        return True
    return len(value) >= 3 and value[1] == ":" and value[2] in {"/", "\\"}


def _looks_windows_path(value: str) -> bool:
    if "\\" in value:
        return True
    return len(value) >= 2 and value[1] == ":"


def _join_target_root_text(home: str, relative: str) -> str:
    home_text = _clean_text(home)
    rel_text = _clean_text(relative)
    if not home_text:
        raise ValueError("home is required for relative target root")
    separator = "\\" if _looks_windows_path(home_text) else "/"
    cleaned_home = home_text.rstrip("/\\")
    cleaned_rel = rel_text.replace("\\", "/").strip("/")
    return cleaned_home + separator + cleaned_rel.replace("/", separator)


def resolve_target_root_text(
    *,
    default_target_root: object,
    default_target_root_env: object = "",
    env: Mapping[str, str] | None = None,
    home: object | None = None,
    descriptor_id: object = "adapter",
) -> str:
    env_map = env or {}
    env_name = _clean_text(default_target_root_env)
    if env_name:
        env_value = _clean_text(env_map.get(env_name, ""))
        if env_value:
            return env_value

    rel = _clean_text(default_target_root)
    if not rel:
        raise ValueError(f"missing default target root for {_clean_text(descriptor_id) or 'adapter'}")
    if _is_absolute_target_root(rel):
        return rel

    home_text = _clean_text(home) if home is not None else str(Path.home())
    return _join_target_root_text(home_text, rel)
