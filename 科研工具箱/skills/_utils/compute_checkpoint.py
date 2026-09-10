"""Atomic, version-bound per-case JSON checkpoints; never certifies mathematics.

Callers provide actual input/source dependencies and a deterministic validator.
The validator must return True after checking the saved solution, not rerun a solver.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import tempfile


def _json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe(root: Path, path: Path) -> Path:
    if not path.is_absolute():
        path = root / path
    if not path.resolve().is_relative_to(root):
        raise ValueError("checkpoint path escapes workspace")
    for item in [path, *path.parents]:
        if item == root:
            break
        if item.is_symlink() or (item.exists() and getattr(item.stat(), "st_file_attributes", 0)
                               & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
            raise ValueError("checkpoint dependencies/directories cannot be links")
    return path


class CaseCheckpoint:
    def __init__(self, workspace: Path, key: str, *, dependencies, parameters):
        self.root = Path(workspace).resolve(strict=True)
        if not isinstance(key, str) or not key.strip():
            raise ValueError("case key is required")
        self.key = key
        self.dependencies = sorted({_safe(self.root, Path(p)) for p in dependencies})
        if not self.dependencies:
            raise ValueError("input, solver and validation dependencies must be declared")
        # Freeze caller-owned parameters, including seed, tolerances and library versions.
        self.parameters = json.loads(_json(parameters))
        self.fingerprint = self._fingerprint()
        self.directory = _safe(self.root, self.root / ".mh" / "compute-checkpoints")
        self.path = self.directory / (hashlib.sha256(key.encode()).hexdigest() + ".json")

    def _fingerprint(self) -> str:
        sources = [(p.relative_to(self.root).as_posix(), _hash(_safe(self.root, p)))
                   for p in self.dependencies]
        return hashlib.sha256(_json([sources, self.parameters, platform.python_version()])).hexdigest()

    def load(self, validate):
        try:
            _safe(self.root, self.path)
            if self._fingerprint() != self.fingerprint:
                return None
            record = json.loads(self.path.read_text(encoding="utf-8"))
            if (record.get("schema") != 1 or record.get("state") != "validated"
                    or record.get("key") != self.key or record.get("fingerprint") != self.fingerprint):
                return None
            data = record["data"]
            if hashlib.sha256(_json(data)).hexdigest() != record["data_sha256"]:
                return None
            return data if validate(data) is True else None
        except (OSError, ValueError, TypeError, KeyError, AttributeError, AssertionError):
            return None

    def save(self, data, validate) -> None:
        # Validate a JSON round-trip of exactly the bytes that will be stored.
        payload = _json(data)
        stored = json.loads(payload)
        if validate(stored) is not True:
            raise ValueError("case validation did not pass")
        if self._fingerprint() != self.fingerprint:
            raise ValueError("dependencies changed during computation; checkpoint not committed")
        record = {"schema": 1, "state": "validated", "key": self.key,
                  "fingerprint": self.fingerprint, "data": stored,
                  "data_sha256": hashlib.sha256(payload).hexdigest()}
        _safe(self.root, self.path)
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, filename = tempfile.mkstemp(prefix=".case-", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(_json(record))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(filename, self.path)
        finally:
            Path(filename).unlink(missing_ok=True)
