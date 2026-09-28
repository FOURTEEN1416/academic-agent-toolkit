from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


RUNTIME_ROOT_REQUIRED_MARKERS = (
    "SKILL.md",
    "config/version-governance.json",
    "config/adapter-registry.json",
    "apps/vgo-cli/src/vgo_cli/main.py",
)


@dataclass(frozen=True, slots=True)
class EntryRootDecision:
    repo_root: Path
    original_repo_root: Path
    working_dir_candidate: Path | None
    reason_code: str
    auto_corrected: bool


class EntryRootGuardError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        original_repo_root: Path,
        candidates: tuple[Path, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.original_repo_root = original_repo_root
        self.candidates = candidates


def _normalize_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return Path(text).resolve()


def _looks_like_runtime_root(path: Path) -> bool:
    return all((path / marker).exists() for marker in RUNTIME_ROOT_REQUIRED_MARKERS)


def _looks_like_workspace_root(path: Path) -> bool:
    if _looks_like_runtime_root(path):
        return False
    if (path / ".git").exists():
        return True
    return any((path / name).exists() for name in ("README.md", "pyproject.toml", "package.json", "src"))


def _script_anchor_runtime_root(script_anchor: Path | None) -> Path | None:
    current = script_anchor.resolve() if script_anchor is not None else None
    while current is not None:
        if current.is_file():
            current = current.parent
            continue
        if _looks_like_runtime_root(current):
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def resolve_entry_repo_root(
    repo_root: str | Path,
    *,
    script_anchor: str | Path | None = None,
    installed_runtime_roots: tuple[str | Path, ...] = (),
) -> EntryRootDecision:
    original_repo_root = _normalize_path(repo_root)
    if original_repo_root is None:
        raise EntryRootGuardError(
            "missing_repo_root",
            "repo_root was empty; pass the real Vibe runtime root instead of a workspace path.",
            original_repo_root=Path.cwd(),
        )

    if _looks_like_runtime_root(original_repo_root):
        return EntryRootDecision(
            repo_root=original_repo_root,
            original_repo_root=original_repo_root,
            working_dir_candidate=None,
            reason_code="repo_root_ok",
            auto_corrected=False,
        )

    candidates: list[Path] = []
    anchor_candidate = _script_anchor_runtime_root(_normalize_path(script_anchor))
    if anchor_candidate is not None:
        candidates.append(anchor_candidate)

    for value in installed_runtime_roots:
        candidate = _normalize_path(value)
        if candidate is not None and _looks_like_runtime_root(candidate) and candidate not in candidates:
            candidates.append(candidate)

    if len(candidates) == 1 and _looks_like_workspace_root(original_repo_root):
        return EntryRootDecision(
            repo_root=candidates[0],
            original_repo_root=original_repo_root,
            working_dir_candidate=original_repo_root,
            reason_code="root_role_mismatch_autocorrected",
            auto_corrected=True,
        )

    if len(candidates) == 1:
        raise EntryRootGuardError(
            "runtime_incomplete",
            (
                "The provided repo_root does not look like a Vibe runtime root. "
                f"A candidate runtime root was found at '{candidates[0]}', but the provided path "
                "did not look like a workspace path, so auto-correction was skipped."
            ),
            original_repo_root=original_repo_root,
            candidates=tuple(candidates),
        )

    if len(candidates) > 1:
        raise EntryRootGuardError(
            "ambiguous_runtime_root",
            "Detected multiple candidate Vibe runtime roots; refusing to guess.",
            original_repo_root=original_repo_root,
            candidates=tuple(candidates),
        )

    raise EntryRootGuardError(
        "runtime_incomplete",
        "The provided repo_root does not look like a Vibe runtime root, and no trusted runtime root could be recovered.",
        original_repo_root=original_repo_root,
    )
