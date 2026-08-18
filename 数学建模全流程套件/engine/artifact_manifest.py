"""Declared artifact discovery and validation for quality gates."""

from __future__ import annotations

import hashlib
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Artifact:
    path: str
    size: int = 0
    sha256: str = ""
    exists: bool = False
    mime_type: str = ""


class ArtifactManifest:
    """Scan and validate only the files explicitly declared by a step."""

    @staticmethod
    def _path(workspace: Path, relative_path: str) -> Path | None:
        candidate = Path(relative_path)
        if not relative_path or candidate.is_absolute() or os.path.isabs(relative_path):
            return None
        root = workspace.resolve()
        resolved = (root / candidate).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            return None
        return resolved

    @staticmethod
    def _spec(entry: str | dict[str, Any]) -> tuple[str, str | None]:
        if isinstance(entry, str):
            return entry, None
        return str(entry.get("path", "")), entry.get("sha256")

    @classmethod
    def scan(cls, workspace: Path, declared_outputs: list[str | dict[str, Any]]) -> list[Artifact]:
        workspace = Path(workspace)
        artifacts = []
        for entry in declared_outputs:
            relative_path, _ = cls._spec(entry)
            path = cls._path(workspace, relative_path)
            if path is None or not path.exists():
                artifacts.append(Artifact(path=relative_path))
                continue
            digest = hashlib.sha256()
            size = 0
            if path.is_dir():
                files = sorted(item for item in path.rglob("*") if item.is_file())
                if not files:
                    artifacts.append(Artifact(path=relative_path))
                    continue
                for item in files:
                    rel = item.relative_to(path).as_posix().encode("utf-8")
                    digest.update(len(rel).to_bytes(8, "big"))
                    digest.update(rel)
                    with item.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            size += len(chunk)
                            digest.update(chunk)
                mime_type = "inode/directory"
            else:
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        size += len(chunk)
                        digest.update(chunk)
                mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            artifacts.append(
                Artifact(
                    path=relative_path,
                    size=size,
                    sha256=digest.hexdigest(),
                    exists=True,
                    mime_type=mime_type,
                )
            )
        return artifacts

    @classmethod
    def validate(
        cls, workspace: Path, declared_outputs: list[str | dict[str, Any]]
    ) -> dict[str, Any]:
        invalid = []
        missing = []
        artifacts = cls.scan(workspace, declared_outputs)
        for entry, artifact in zip(declared_outputs, artifacts):
            relative_path, expected_hash = cls._spec(entry)
            if cls._path(Path(workspace), relative_path) is None:
                invalid.append(relative_path)
            elif not artifact.exists:
                missing.append(relative_path)
            elif expected_hash and artifact.sha256.lower() != str(expected_hash).lower():
                invalid.append(relative_path)
        return {
            "ok": not missing and not invalid,
            "missing": missing,
            "invalid": invalid,
            "artifacts": artifacts,
        }
