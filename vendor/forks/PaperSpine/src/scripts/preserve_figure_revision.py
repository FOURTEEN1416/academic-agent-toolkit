#!/usr/bin/env python3
"""Preserve explicitly named figure work locally; never change task facts."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path


def preserve(paper_root: Path, revision: str, files: list[str]) -> dict:
    root = paper_root.resolve(strict=True)
    if not root.is_dir() or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", revision):
        raise ValueError("Use an existing paper directory and a simple revision name")
    if not files:
        raise ValueError("Name the actual files to preserve")
    archive = root / "figure-versions"
    if archive.resolve() != archive:
        raise ValueError("The revision directory must stay inside this paper")
    destination = archive / revision
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Preserved revision already exists: {destination}")
    inputs = []
    seen = set()
    for name in files:
        rel = Path(name)
        if rel.is_absolute() or rel.drive or ".." in rel.parts or not rel.parts:
            raise ValueError(f"Use a paper-relative file: {name}")
        source = (root / rel).resolve(strict=True)
        if not source.is_relative_to(root) or source.is_relative_to(archive.resolve()):
            raise ValueError(f"File is outside active paper work: {name}")
        if not source.is_file():
            raise ValueError(f"A named input is not a file: {name}")
        if rel == Path("revision-manifest.json"):
            raise ValueError("revision-manifest.json is reserved for archive metadata")
        if rel in seen:
            continue
        seen.add(rel)
        # Resolve for confinement, retain the named layout for relative references.
        inputs.append((source, rel))
    archive.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".preserving-", dir=archive))
    try:
        records = []
        for source, rel in inputs:
            content = source.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            target = staging / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise RuntimeError(f"Source changed during preservation: {rel}")
            records.append({"file": rel.as_posix(), "source_file": source.relative_to(root).as_posix(),
                            "bytes": len(content), "sha256": digest})
        # Check the whole input set again, not just each file immediately after
        # copying it. Callers still need stable inputs; this is not a writer lock.
        for (source, rel), record in zip(inputs, records, strict=True):
            if hashlib.sha256(source.read_bytes()).hexdigest() != record["sha256"]:
                raise RuntimeError(f"Input set changed during preservation: {rel}")
        manifest = {"revision": revision, "files": records}
        (staging / "revision-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        # rename refuses an occupied/non-empty revision; do not replace old work.
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Preserved revision already exists: {destination}")
        staging.rename(destination)
        return {"revision_directory": str(destination), **manifest}
    finally:
        if staging.exists() and staging.resolve().parent == archive.resolve():
            shutil.rmtree(staging)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-root", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--file", action="append", required=True, dest="files")
    args = parser.parse_args()
    print(json.dumps(preserve(args.paper_root, args.revision, args.files), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
