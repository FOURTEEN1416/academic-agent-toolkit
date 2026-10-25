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
    # 工作区相对路径 -> 文件摘要；只有新目录回执携带此字段。
    members: dict[str, str] | None = None


class FingerprintSession:
    """Content fingerprints shared only inside one validation call, never across calls.

    Streaming reads bound memory. Metadata detects edits during validation; it is
    not used as proof of content equality on the next validation boundary.
    """

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).resolve()
        self._artifacts: dict[str, Artifact] = {}
        self._stats: dict[Path, tuple[int, int, int, int]] = {}

    @staticmethod
    def _stamp(path: Path) -> tuple[int, int, int, int]:
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino

    def fingerprint(self, value: str | Path) -> Artifact:
        self.assert_unchanged()
        raw = Path(value)
        path = raw if raw.is_absolute() else self.workspace / raw
        for ancestor in (path, *path.parents):
            if ancestor == self.workspace:
                break
            if ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction()):
                raise ValueError(f"linked artifact path is not allowed: {value}")
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(self.workspace).as_posix()
        except ValueError as exc:
            raise ValueError(f"artifact escapes workspace: {value}") from exc
        if relative in self._artifacts:
            self.assert_unchanged()
            return self._artifacts[relative]
        if not path.exists():
            return Artifact(relative)
        members = [path, *path.rglob("*")] if path.is_dir() else [path]
        for member in members:
            if member.is_symlink() or (hasattr(member, "is_junction") and member.is_junction()):
                raise ValueError(f"linked artifact member is not allowed: {member}")
            member = member.resolve()
            member.relative_to(self.workspace)
            stamp = self._stamp(member)
            if member in self._stats and self._stats[member] != stamp:
                raise ValueError(f"artifact changed during validation: {member}")
            self._stats.setdefault(member, stamp)
        files = sorted(p for p in members if p.is_file())
        if not files:
            return Artifact(relative)
        digest, size = hashlib.sha256(), 0
        is_directory = path.is_dir()
        leaves: dict[str, Artifact] = {}
        for item in files:
            if is_directory:
                rel = item.relative_to(path).as_posix().encode("utf-8")
                digest.update(len(rel).to_bytes(8, "big"))
                digest.update(rel)
            leaf_digest, leaf_size = hashlib.sha256(), 0
            with item.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
                    leaf_digest.update(chunk)
                    leaf_size += len(chunk)
            size += leaf_size
            leaf_path = item.resolve().relative_to(self.workspace).as_posix()
            leaves[leaf_path] = Artifact(leaf_path, leaf_size, leaf_digest.hexdigest(), True,
                mimetypes.guess_type(item.name)[0] or "application/octet-stream")
        self.assert_unchanged()
        mime = "inode/directory" if is_directory else leaves[relative].mime_type
        artifact = Artifact(relative, size, digest.hexdigest(), True, mime,
                            {p: a.sha256 for p, a in leaves.items()} if is_directory else None)
        # 父目录已读取真实字节，后续叶节点复用同次结果，不再读一遍。
        self._artifacts.update(leaves)
        self._artifacts[relative] = artifact
        return artifact

    def assert_unchanged(self) -> None:
        for path, stamp in self._stats.items():
            if not path.exists() or self._stamp(path) != stamp:
                raise ValueError(f"artifact changed during validation: {path}")


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
    def scan(cls, workspace: Path, declared_outputs: list[str | dict[str, Any]],
             session: FingerprintSession | None = None) -> list[Artifact]:
        workspace = Path(workspace)
        session = session or FingerprintSession(workspace)
        if session.workspace != workspace.resolve():
            raise ValueError("fingerprint session belongs to a different workspace")
        artifacts = []
        for entry in declared_outputs:
            relative_path, _ = cls._spec(entry)
            if cls._path(workspace, relative_path) is None:
                artifacts.append(Artifact(path=relative_path))
                continue
            try:
                artifact = session.fingerprint(relative_path)
                artifacts.append(Artifact(relative_path, artifact.size, artifact.sha256,
                                          artifact.exists, artifact.mime_type, artifact.members))
            except (OSError, ValueError):
                artifacts.append(Artifact(path=relative_path))
        return artifacts

    @classmethod
    def validate(
        cls, workspace: Path, declared_outputs: list[str | dict[str, Any]],
        session: FingerprintSession | None = None,
    ) -> dict[str, Any]:
        invalid = []
        missing = []
        artifacts = cls.scan(workspace, declared_outputs, session=session)
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

    @classmethod
    def validate_coverage(cls, workspace: Path, outputs: list[dict[str, Any]],
                          directories: list[dict[str, Any]],
                          session: FingerprintSession | None = None) -> dict[str, Any]:
        """Validate accepted leaf bytes plus closed directory membership."""
        session = session or FingerprintSession(workspace)
        invalid_directories = []
        for directory in directories:
            path = directory.get("path", "") if isinstance(directory, dict) else ""
            expected = directory.get("members") if isinstance(directory, dict) else None
            try:
                if cls._path(Path(workspace), path) is None or not isinstance(expected, list):
                    raise ValueError("invalid directory coverage")
                actual = session.fingerprint(path)
                canonical = lambda p: os.path.normcase(os.path.normpath(p)).replace("\\", "/")
                if (actual.members is None or
                        {canonical(p) for p in actual.members} != {canonical(p) for p in expected}):
                    raise ValueError("directory membership changed")
            except (OSError, ValueError, TypeError):
                invalid_directories.append(path)
        result = cls.validate(workspace, outputs, session=session)
        result["invalid"].extend(invalid_directories)
        result["ok"] = not result["missing"] and not result["invalid"]
        return result
