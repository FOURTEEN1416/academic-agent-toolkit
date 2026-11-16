#!/usr/bin/env python3
"""Move obsolete Skill roots out of automatic discovery without deleting history.

The migration is intentionally separate from PaperSpine content updates.  It
only moves known immediate children of declared Skill discovery roots, records
every file hash, verifies the destination bytes, and rolls back on any failure.
The receipt can later be used for an explicit, equally verified restore.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTRACT = "paperspine.skill-discovery-migration-receipt"
PREVIEW_CONTRACT = "paperspine.skill-discovery-migration-preview"
SCHEMA_VERSION = "1.0"
CANONICAL_SKILL = "paper-spine"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
LEGACY_EXACT_NAMES = frozenset(
    {
        "PaperSpine",
        "PaperSpineV2",
        ".paperspine5-update-backups",
        "paperFig",
        "paperspine5-workspace",
        "paper-spine-ui",
        "paper-spine-intake",
        "paper-spine-research",
        "paper-spine-citation",
        "paper-spine-rewrite",
        "paper-spine-build",
        "paper-spine-latex",
        "paper-spine-audit",
        "paper-spine-translate",
        "paper-spine-humanize",
        "paper-spine-update",
    }
)
LEGACY_NAME_PATTERNS = (
    re.compile(r"^paper-spine\.pre-.+$"),
    re.compile(r"^paper-spine\.backup-.+$"),
)


class DiscoveryMigrationError(RuntimeError):
    """A discovery migration or restore request is unsafe or cannot verify."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _safe_operation_id(value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise DiscoveryMigrationError("operation_id must be a safe non-empty identifier")
    return value


def _is_link_or_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(callable(is_junction) and is_junction())


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory(root: Path) -> dict[str, Any]:
    if not root.exists() or _is_link_or_junction(root):
        raise DiscoveryMigrationError(f"Skill conflict is missing or linked: {root}")
    files: list[dict[str, Any]] = []
    paths = [root] if root.is_file() else sorted(
        root.rglob("*"), key=lambda item: item.as_posix().lower()
    )
    if not root.is_file() and not root.is_dir():
        raise DiscoveryMigrationError(f"Skill conflict is not a regular file/directory: {root}")
    for path in paths:
        if _is_link_or_junction(path):
            raise DiscoveryMigrationError(f"Skill conflict contains a link or junction: {path}")
        if not path.is_file():
            continue
        relative = path.name if root.is_file() else path.relative_to(root).as_posix()
        files.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    tree_sha256 = hashlib.sha256(_canonical_bytes(files)).hexdigest()
    return {
        "files": files,
        "file_count": len(files),
        "total_bytes": sum(int(item["size_bytes"]) for item in files),
        "tree_sha256": tree_sha256,
    }


def _matches_conflict(name: str) -> bool:
    return name in LEGACY_EXACT_NAMES or any(pattern.fullmatch(name) for pattern in LEGACY_NAME_PATTERNS)


def _frontmatter_name(skill_md: Path) -> str | None:
    try:
        text = skill_md.read_text(encoding="utf-8-sig", errors="strict")
    except (OSError, UnicodeError):
        return None
    for line in text.splitlines()[:40]:
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return None


def discover_conflicts(skills_roots: dict[str, Path]) -> list[tuple[str, Path]]:
    conflicts: list[tuple[str, Path]] = []
    for host, raw_root in sorted(skills_roots.items()):
        root = raw_root.resolve()
        if not root.exists():
            continue
        if not root.is_dir() or _is_link_or_junction(root):
            raise DiscoveryMigrationError(f"Skill discovery root is not a plain directory: {root}")
        for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
            if child.name == CANONICAL_SKILL:
                continue
            if _matches_conflict(child.name) and child.exists():
                conflicts.append((host, child))
        canonical = root / CANONICAL_SKILL
        if canonical.is_dir() and not _is_link_or_junction(canonical):
            nested_candidates: set[Path] = set()
            for path in sorted(canonical.rglob("*"), key=lambda item: item.as_posix().lower()):
                if _is_link_or_junction(path):
                    raise DiscoveryMigrationError(
                        f"canonical Skill contains a link or junction: {path}"
                    )
                if not path.is_file() or path.name != "SKILL.md":
                    continue
                if path.parent == canonical:
                    continue
                nested_name = _frontmatter_name(path)
                if nested_name == "paperFig":
                    nested_candidates.add(path.parent)
                elif nested_name == CANONICAL_SKILL:
                    nested_candidates.add(path)
            for candidate in sorted(nested_candidates, key=lambda item: item.as_posix().lower()):
                if any(candidate != parent and _is_within(candidate, parent) for parent in nested_candidates):
                    continue
                conflicts.append((host, candidate))
    return conflicts


def _validate_roots(skills_roots: dict[str, Path], archive_root: Path) -> dict[str, Path]:
    if not skills_roots:
        raise DiscoveryMigrationError("at least one Skill discovery root is required")
    normalized: dict[str, Path] = {}
    for host, raw_root in skills_roots.items():
        if not SAFE_ID.fullmatch(host):
            raise DiscoveryMigrationError(f"unsafe host label: {host!r}")
        root = raw_root.resolve()
        if root == Path(root.anchor):
            raise DiscoveryMigrationError("Skill discovery root cannot be a filesystem root")
        normalized[host] = root
    archive = archive_root.resolve()
    if archive == Path(archive.anchor):
        raise DiscoveryMigrationError("archive_root cannot be a filesystem root")
    for root in normalized.values():
        if _is_within(archive, root) or _is_within(root, archive):
            raise DiscoveryMigrationError("archive_root and Skill discovery roots must not overlap")
    return normalized


def _receipt_path(archive_root: Path, operation_id: str) -> Path:
    return archive_root / "receipts" / f"{operation_id}.json"


def _prepare_items(
    roots: dict[str, Path], archive: Path, operation_id: str
) -> list[dict[str, Any]]:
    conflicts = discover_conflicts(roots)
    history_root = archive / "history" / operation_id
    prepared: list[dict[str, Any]] = []
    for host, source in conflicts:
        source_absolute = source.absolute()
        try:
            source_relative = source_absolute.relative_to(roots[host].absolute())
        except ValueError as exc:
            raise DiscoveryMigrationError(
                f"conflict escaped its Skill discovery root: {source}"
            ) from exc
        if not source_relative.parts or source_relative.parts[0] == "..":
            raise DiscoveryMigrationError(f"unsafe Skill conflict path: {source}")
        if len(source_relative.parts) > 1 and source_relative.parts[0] != CANONICAL_SKILL:
            raise DiscoveryMigrationError(
                f"nested conflict must be contained by the canonical Skill: {source}"
            )
        inventory = _inventory(source)
        target = history_root / host / source_relative
        prepared.append(
            {
                "host": host,
                "source": str(source.resolve()),
                "target": str(target.resolve()),
                "name": source.name,
                "source_relative_path": source_relative.as_posix(),
                **inventory,
            }
        )
    return prepared


def preview_discovery_migration(
    skills_roots: dict[str, Path],
    archive_root: Path,
    *,
    operation_id: str,
) -> dict[str, Any]:
    """Return the exact typed inventory a migration would use without writing."""

    operation_id = _safe_operation_id(operation_id)
    roots = _validate_roots(skills_roots, archive_root)
    archive = archive_root.resolve()
    request = {
        "operation": "migrate",
        "operation_id": operation_id,
        "canonical_skill": CANONICAL_SKILL,
        "skills_roots": {host: str(root) for host, root in sorted(roots.items())},
        "archive_root": str(archive),
    }
    prepared = _prepare_items(roots, archive, operation_id)
    return {
        "contract": PREVIEW_CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "operation": "preview",
        "operation_id": operation_id,
        "request_sha256": _payload_hash(request),
        "created_at": _now(),
        "canonical_skill": CANONICAL_SKILL,
        "skills_roots": request["skills_roots"],
        "archive_root": str(archive),
        "status": "ready" if prepared else "noop",
        "item_count": len(prepared),
        "file_count": sum(int(item["file_count"]) for item in prepared),
        "total_bytes": sum(int(item["total_bytes"]) for item in prepared),
        "items": prepared,
        "mutation_performed": False,
        "external_action_authorized": False,
    }


def _write_receipt(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    unsigned = {key: value for key, value in payload.items() if key != "receipt_sha256"}
    payload = {**unsigned, "receipt_sha256": _payload_hash(unsigned)}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(_canonical_bytes(payload))
    os.replace(temporary, path)
    return payload


def _read_receipt(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiscoveryMigrationError(f"migration receipt is unreadable: {path}") from exc
    if not isinstance(payload, dict) or payload.get("contract") != CONTRACT:
        raise DiscoveryMigrationError("migration receipt contract is unsupported")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise DiscoveryMigrationError("migration receipt version is unsupported")
    expected = payload.get("receipt_sha256")
    unsigned = {key: value for key, value in payload.items() if key != "receipt_sha256"}
    if expected != _payload_hash(unsigned):
        raise DiscoveryMigrationError("migration receipt hash mismatch")
    return payload


def migrate_discovery_conflicts(
    skills_roots: dict[str, Path],
    archive_root: Path,
    *,
    operation_id: str,
    fault_after_moves: int | None = None,
) -> dict[str, Any]:
    operation_id = _safe_operation_id(operation_id)
    roots = _validate_roots(skills_roots, archive_root)
    archive = archive_root.resolve()
    request = {
        "operation": "migrate",
        "operation_id": operation_id,
        "canonical_skill": CANONICAL_SKILL,
        "skills_roots": {host: str(root) for host, root in sorted(roots.items())},
        "archive_root": str(archive),
    }
    request_sha256 = _payload_hash(request)
    receipt_path = _receipt_path(archive, operation_id)
    if receipt_path.is_file():
        existing = _read_receipt(receipt_path)
        if existing.get("request_sha256") != request_sha256:
            raise DiscoveryMigrationError("operation_id was already used for a different request")
        return {**existing, "replayed": True}

    prepared = _prepare_items(roots, archive, operation_id)

    base = {
        "contract": CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "operation": "migrate",
        "operation_id": operation_id,
        "request_sha256": request_sha256,
        "created_at": _now(),
        "canonical_skill": CANONICAL_SKILL,
        "skills_roots": request["skills_roots"],
        "archive_root": str(archive),
        "status": "noop" if not prepared else "blocked",
        "items": prepared,
        "blockers": [],
        "rollback_performed": False,
        "restores_receipt": None,
        "external_action_authorized": False,
    }
    if not prepared:
        return _write_receipt(receipt_path, base)

    moved: list[dict[str, Any]] = []
    try:
        for item in prepared:
            source = Path(item["source"])
            target = Path(item["target"])
            if target.exists():
                raise DiscoveryMigrationError(f"archive target already exists: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            moved.append(item)
            observed = _inventory(target)
            if observed["tree_sha256"] != item["tree_sha256"] or observed["files"] != item["files"]:
                raise DiscoveryMigrationError(f"post-migration hash mismatch: {target}")
            if fault_after_moves is not None and len(moved) >= fault_after_moves:
                raise OSError("injected discovery migration failure")
        return _write_receipt(receipt_path, {**base, "status": "committed"})
    except Exception as exc:
        rollback_errors: list[str] = []
        for item in reversed(moved):
            source = Path(item["source"])
            target = Path(item["target"])
            try:
                if source.exists():
                    raise DiscoveryMigrationError(f"rollback source already exists: {source}")
                os.replace(target, source)
                if _inventory(source)["tree_sha256"] != item["tree_sha256"]:
                    raise DiscoveryMigrationError(f"rollback hash mismatch: {source}")
            except Exception as rollback_exc:  # pragma: no cover - platform failure path.
                rollback_errors.append(str(rollback_exc))
        return _write_receipt(
            receipt_path,
            {
                **base,
                "status": "rollback_failed" if rollback_errors else "rolled_back",
                "rollback_performed": not rollback_errors,
                "blockers": [
                    {"code": "DISCOVERY_MIGRATION_FAILED", "message": str(exc)},
                    *(
                        [{"code": "DISCOVERY_MIGRATION_ROLLBACK_FAILED", "messages": rollback_errors}]
                        if rollback_errors
                        else []
                    ),
                ],
            },
        )


def restore_discovery_migration(
    migration_receipt_path: Path,
    *,
    operation_id: str,
) -> dict[str, Any]:
    operation_id = _safe_operation_id(operation_id)
    migration_path = migration_receipt_path.resolve()
    migration = _read_receipt(migration_path)
    if migration.get("operation") != "migrate" or migration.get("status") != "committed":
        raise DiscoveryMigrationError("only a committed migration receipt can be restored")
    archive = Path(str(migration["archive_root"])).resolve()
    request = {
        "operation": "restore",
        "operation_id": operation_id,
        "migration_receipt": str(migration_path),
        "migration_receipt_sha256": migration["receipt_sha256"],
    }
    request_sha256 = _payload_hash(request)
    receipt_path = _receipt_path(archive, operation_id)
    if receipt_path.is_file():
        existing = _read_receipt(receipt_path)
        if existing.get("request_sha256") != request_sha256:
            raise DiscoveryMigrationError("operation_id was already used for a different request")
        return {**existing, "replayed": True}

    items = list(migration.get("items", []))
    base = {
        "contract": CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "operation": "restore",
        "operation_id": operation_id,
        "request_sha256": request_sha256,
        "created_at": _now(),
        "canonical_skill": CANONICAL_SKILL,
        "skills_roots": migration.get("skills_roots", {}),
        "archive_root": str(archive),
        "status": "blocked",
        "items": items,
        "blockers": [],
        "rollback_performed": False,
        "restores_receipt": str(migration_path),
        "external_action_authorized": False,
    }
    for item in items:
        source = Path(str(item["source"]))
        target = Path(str(item["target"]))
        if source.exists():
            return _write_receipt(
                receipt_path,
                {**base, "blockers": [{"code": "RESTORE_SOURCE_EXISTS", "path": str(source)}]},
            )
        observed = _inventory(target)
        if observed["tree_sha256"] != item["tree_sha256"] or observed["files"] != item["files"]:
            return _write_receipt(
                receipt_path,
                {**base, "blockers": [{"code": "RESTORE_ARCHIVE_HASH_MISMATCH", "path": str(target)}]},
            )

    restored: list[dict[str, Any]] = []
    try:
        for item in reversed(items):
            source = Path(str(item["source"]))
            target = Path(str(item["target"]))
            source.parent.mkdir(parents=True, exist_ok=True)
            os.replace(target, source)
            restored.append(item)
            if _inventory(source)["tree_sha256"] != item["tree_sha256"]:
                raise DiscoveryMigrationError(f"restored source hash mismatch: {source}")
        return _write_receipt(receipt_path, {**base, "status": "committed"})
    except Exception as exc:
        rollback_errors: list[str] = []
        for item in reversed(restored):
            source = Path(str(item["source"]))
            target = Path(str(item["target"]))
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, target)
                if _inventory(target)["tree_sha256"] != item["tree_sha256"]:
                    raise DiscoveryMigrationError(f"restore rollback hash mismatch: {target}")
            except Exception as rollback_exc:  # pragma: no cover
                rollback_errors.append(str(rollback_exc))
        return _write_receipt(
            receipt_path,
            {
                **base,
                "status": "rollback_failed" if rollback_errors else "rolled_back",
                "rollback_performed": not rollback_errors,
                "blockers": [
                    {"code": "DISCOVERY_RESTORE_FAILED", "message": str(exc)},
                    *(
                        [{"code": "DISCOVERY_RESTORE_ROLLBACK_FAILED", "messages": rollback_errors}]
                        if rollback_errors
                        else []
                    ),
                ],
            },
        )


def _parse_roots(values: Iterable[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise DiscoveryMigrationError("--skills-root must be HOST=PATH")
        host, raw_path = value.split("=", 1)
        if host in roots:
            raise DiscoveryMigrationError(f"duplicate Skill-root host: {host}")
        roots[host] = Path(raw_path)
    return roots


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive or restore duplicate Skill discovery roots.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    preview = subparsers.add_parser("preview")
    preview.add_argument("--skills-root", action="append", required=True, metavar="HOST=PATH")
    preview.add_argument("--archive-root", type=Path, required=True)
    preview.add_argument("--operation-id", required=True)
    migrate = subparsers.add_parser("migrate")
    migrate.add_argument("--skills-root", action="append", required=True, metavar="HOST=PATH")
    migrate.add_argument("--archive-root", type=Path, required=True)
    migrate.add_argument("--operation-id", required=True)
    restore = subparsers.add_parser("restore")
    restore.add_argument("--receipt", type=Path, required=True)
    restore.add_argument("--operation-id", required=True)
    args = parser.parse_args()
    try:
        if args.command == "preview":
            result = preview_discovery_migration(
                _parse_roots(args.skills_root),
                args.archive_root,
                operation_id=args.operation_id,
            )
        elif args.command == "migrate":
            result = migrate_discovery_conflicts(
                _parse_roots(args.skills_root),
                args.archive_root,
                operation_id=args.operation_id,
            )
        else:
            result = restore_discovery_migration(args.receipt, operation_id=args.operation_id)
    except DiscoveryMigrationError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"ready", "committed", "noop"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
