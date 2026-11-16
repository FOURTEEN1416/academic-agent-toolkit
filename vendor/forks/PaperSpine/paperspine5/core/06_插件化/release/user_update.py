"""Independent update transactions for local Codex plugins and standalone Skills.

The W7 lifecycle in :mod:`lifecycle` is an explicit-profile acceptance harness.
This module can project a verified suite bundle to either real local Codex
authoring surface without editing marketplace metadata.  A manager is bound to
exactly one surface.  Plugin and standalone Skill state, receipts, mutations,
activation, and rollback are never combined.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import marshal
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import types
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

try:  # Installed bundle and direct-script use.
    from .suite_release import (
        PRODUCT_ID,
        ReleaseError,
        _verify_installed_bundle_with_runtime_residue,
        _recognize_legacy_installed_prestate,
        canonical_json_bytes,
        extract_verified_bundle,
        sha256_file,
        verify_bundle,
    )
except ImportError:  # pragma: no cover - exercised by CLI script mode.
    from suite_release import (  # type: ignore
        PRODUCT_ID,
        ReleaseError,
        _verify_installed_bundle_with_runtime_residue,
        _recognize_legacy_installed_prestate,
        canonical_json_bytes,
        extract_verified_bundle,
        sha256_file,
        verify_bundle,
    )


UPDATE_FEED_CONTRACT = "paperspine5.update-feed"
UPDATE_FEED_SCHEMA_VERSION = "1.0"
USER_UPDATE_RECEIPT_SCHEMA_VERSION = "1.0"
USER_UPDATE_STATE_SCHEMA_VERSION = "1.0"
PLUGIN_ACTIVATION_JOURNAL_CONTRACT = "paperspine5.plugin-activation-journal"
PLUGIN_ACTIVATION_JOURNAL_SCHEMA_VERSION = "1.0"
INSTALL_KINDS = frozenset({"plugin", "skill"})
PLUGIN_NAME = "paperspine5"
STANDALONE_SKILL_NAME = "paper-spine"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_FEED_BYTES = 1024 * 1024
MAX_BUNDLE_BYTES = 512 * 1024 * 1024
DISCOVERY_ARCHIVE_DIRECTORY = "skill-discovery-archive"
PLUGIN_CACHE_RECONCILIATION_CONTRACT = (
    "paperspine5.plugin-cache-reconciliation-receipt"
)
PLUGIN_CACHE_RECONCILIATION_SCHEMA_VERSION = "1.0"
PLUGIN_PRESTATE_VALIDATION_CONTRACT = (
    "paperspine5.plugin-installed-prestate-validation"
)
PLUGIN_PRESTATE_VALIDATION_SCHEMA_VERSION = "1.0"
SKILL_MANAGED_SUITE_RECONCILIATION_CONTRACT = (
    "paperspine5.skill-managed-suite-reconciliation-receipt"
)
SKILL_MANAGED_SUITE_RECONCILIATION_SCHEMA_VERSION = "1.0"
SKILL_MANAGED_SUITE_PRESTATE_VALIDATION_CONTRACT = (
    "paperspine5.skill-managed-suite-prestate-validation"
)
SKILL_MANAGED_SUITE_PRESTATE_VALIDATION_SCHEMA_VERSION = "1.0"
RUNTIME_PYC_NAME = re.compile(
    r"^(?P<stem>.+)\.(?P<tag>[A-Za-z0-9_]+-\d+)(?:\.opt-(?P<opt>\d+))?\.pyc$"
)


class UserUpdateError(RuntimeError):
    """A user update request is unsafe, ambiguous, or invalid."""


@dataclass(frozen=True)
class Installation:
    kind: str
    target_root: Path
    marketplace_path: Path | None = None
    marketplace_name: str | None = None


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


CommandRunner = Callable[[list[str]], CommandResult]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_id(value: str, field: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise UserUpdateError(f"{field} must be a safe non-empty identifier")
    return value


def _request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _self_hash(payload: dict[str, Any], field: str = "self_sha256") -> str:
    subject = dict(payload)
    subject.pop(field, None)
    return sha256_bytes(canonical_json_bytes(subject))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UserUpdateError(f"JSON is unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise UserUpdateError(f"JSON root must be an object: {path}")
    return payload


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical_json_bytes(payload))
    os.replace(temporary, path)


def _is_link_or_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(callable(is_junction) and is_junction())


def _assert_plain_contained_path(root: Path, target: Path, label: str) -> None:
    root_absolute = root.absolute()
    target_absolute = target.absolute()
    try:
        relative = target_absolute.relative_to(root_absolute)
    except ValueError as exc:
        raise UserUpdateError(f"{label} escaped its controlled root") from exc
    if relative.is_absolute() or ".." in relative.parts:
        raise UserUpdateError(f"{label} contains parent traversal")
    if not root_absolute.exists() or _is_link_or_junction(root_absolute):
        raise UserUpdateError(f"{label} root is missing or a reparse point")
    resolved_root = root_absolute.resolve()
    current = root_absolute
    candidates = [root_absolute]
    for part in relative.parts:
        current = current / part
        candidates.append(current)
    for candidate in candidates:
        if not candidate.exists():
            continue
        if _is_link_or_junction(candidate):
            raise UserUpdateError(f"{label} contains a link or junction: {candidate}")
        try:
            candidate.resolve().relative_to(resolved_root)
        except ValueError as exc:
            raise UserUpdateError(f"{label} resolved outside its controlled root") from exc


def _safe_target(path: str | Path, field: str) -> Path:
    target = Path(path).resolve()
    if target == Path(target.anchor):
        raise UserUpdateError(f"{field} cannot be a filesystem root")
    if target.exists() and _is_link_or_junction(target):
        raise UserUpdateError(f"{field} cannot be a link, junction, or reparse point")
    return target


def _default_runner(command: list[str]) -> CommandResult:
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _download(url: str, destination: Path, *, limit: int) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise UserUpdateError("remote update sources must use HTTPS")
    request = Request(url, headers={"User-Agent": "PaperSpine5-Updater/1.0"})
    written = 0
    with urlopen(request, timeout=30) as response, destination.open("wb") as output:
        while chunk := response.read(min(1024 * 1024, limit - written + 1)):
            written += len(chunk)
            if written > limit:
                raise UserUpdateError(f"download exceeds the {limit}-byte safety limit")
            output.write(chunk)


def _feed_bundle_reference(
    feed_source: str,
    feed: dict[str, Any],
    *,
    install_kind: str,
) -> tuple[str, int, str]:
    if feed.get("contract") != UPDATE_FEED_CONTRACT or feed.get("schema_version") != UPDATE_FEED_SCHEMA_VERSION:
        raise UserUpdateError("update feed contract/version is unsupported")
    if feed.get("status") != "PASS":
        raise UserUpdateError("update feed is not published as PASS")
    if feed.get("product_id") != PRODUCT_ID:
        raise UserUpdateError("update feed belongs to a different product")
    if feed.get("install_kind") != install_kind:
        raise UserUpdateError(
            f"update feed is for {feed.get('install_kind')!r}, not {install_kind!r}"
        )
    bundle = feed.get("bundle")
    if not isinstance(bundle, dict):
        raise UserUpdateError("update feed bundle record is missing")
    reference = bundle.get("url")
    size = bundle.get("bytes")
    digest = bundle.get("sha256")
    if not isinstance(reference, str) or not reference.strip():
        raise UserUpdateError("update feed bundle URL/path is missing")
    if not isinstance(size, int) or size < 1 or size > MAX_BUNDLE_BYTES:
        raise UserUpdateError("update feed bundle byte count is invalid")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise UserUpdateError("update feed bundle SHA-256 is invalid")
    if urlparse(feed_source).scheme == "https":
        resolved = urljoin(feed_source, reference)
        if urlparse(resolved).scheme != "https":
            raise UserUpdateError("remote feed resolved a non-HTTPS bundle")
        return resolved, size, digest
    feed_path = Path(feed_source).resolve()
    candidate = Path(reference)
    resolved_path = candidate.resolve() if candidate.is_absolute() else (feed_path.parent / candidate).resolve()
    return str(resolved_path), size, digest


def resolve_candidate(
    source: str | Path,
    *,
    install_kind: str,
) -> tuple[Path, dict[str, Any], Callable[[], None]]:
    """Resolve a local bundle or hash-bound local/HTTPS update feed."""
    raw = str(source)
    parsed = urlparse(raw)
    temporary_root: Path | None = None

    def cleanup() -> None:
        if temporary_root is not None:
            shutil.rmtree(temporary_root, ignore_errors=True)

    try:
        if parsed.scheme == "https":
            temporary_root = Path(tempfile.mkdtemp(prefix="paperspine5-update-"))
            feed_path = temporary_root / "feed.json"
            _download(raw, feed_path, limit=MAX_FEED_BYTES)
            feed = _read_json(feed_path)
            bundle_reference, expected_size, expected_sha = _feed_bundle_reference(
                raw, feed, install_kind=install_kind
            )
            bundle_path = temporary_root / "candidate.zip"
            _download(bundle_reference, bundle_path, limit=expected_size)
        else:
            path = Path(raw).resolve()
            if not path.is_file():
                raise UserUpdateError(f"update source does not exist: {path}")
            if path.suffix.lower() == ".zip":
                verification = verify_bundle(path)
                return path, verification, cleanup
            feed = _read_json(path)
            bundle_reference, expected_size, expected_sha = _feed_bundle_reference(
                str(path), feed, install_kind=install_kind
            )
            if urlparse(bundle_reference).scheme == "https":
                temporary_root = Path(tempfile.mkdtemp(prefix="paperspine5-update-"))
                bundle_path = temporary_root / "candidate.zip"
                _download(bundle_reference, bundle_path, limit=expected_size)
            else:
                bundle_path = Path(bundle_reference).resolve()
                if not bundle_path.is_file():
                    raise UserUpdateError(f"feed bundle does not exist: {bundle_path}")
        actual_size = bundle_path.stat().st_size
        actual_sha = sha256_file(bundle_path)
        if actual_size != expected_size or actual_sha != expected_sha:
            raise UserUpdateError(
                f"feed bundle bytes/hash mismatch: expected {expected_size}/{expected_sha}, "
                f"got {actual_size}/{actual_sha}"
            )
        verification = verify_bundle(bundle_path)
        feed_build = feed.get("build_id")
        if feed_build != verification.get("build_id"):
            raise UserUpdateError("update feed build ID differs from the verified bundle")
        return bundle_path, verification, cleanup
    except Exception:
        cleanup()
        raise


def make_update_feed(
    bundle: str | Path,
    output: str | Path,
    *,
    install_kind: str,
    bundle_url: str | None = None,
) -> dict[str, Any]:
    if install_kind not in INSTALL_KINDS:
        raise UserUpdateError("install_kind must be plugin or skill")
    bundle_path = Path(bundle).resolve()
    verification = verify_bundle(bundle_path)
    output_path = Path(output).resolve()
    reference = bundle_url or os.path.relpath(bundle_path, output_path.parent).replace("\\", "/")
    if urlparse(reference).scheme and urlparse(reference).scheme != "https":
        raise UserUpdateError("published bundle URLs must use HTTPS")
    payload = {
        "contract": UPDATE_FEED_CONTRACT,
        "schema_version": UPDATE_FEED_SCHEMA_VERSION,
        "status": "PASS",
        "product_id": PRODUCT_ID,
        "product_version": verification["product_version"],
        "channel": verification["channel"],
        "build_id": verification["build_id"],
        "bundle": {
            "url": reference,
            "bytes": bundle_path.stat().st_size,
            "sha256": sha256_file(bundle_path),
        },
        "install_kind": install_kind,
        "requires_new_session": True,
        "external_action_authorized": False,
    }
    _write_atomic(output_path, payload)
    return payload


def _marketplace_installation(path: Path, *, require_existing: bool) -> tuple[Installation | None, list[dict[str, Any]]]:
    if not path.is_file():
        return None, []
    try:
        payload = _read_json(path)
    except UserUpdateError as exc:
        return None, [{"code": "MARKETPLACE_INVALID", "message": str(exc), "path": str(path)}]
    name = payload.get("name")
    if not isinstance(name, str) or not SAFE_ID.fullmatch(name):
        return None, [{"code": "MARKETPLACE_NAME_INVALID", "path": str(path)}]
    entries = [item for item in payload.get("plugins", []) if isinstance(item, dict) and item.get("name") == PLUGIN_NAME]
    if len(entries) != 1:
        if not entries:
            return None, []
        return None, [{"code": "MARKETPLACE_PLUGIN_AMBIGUOUS", "count": len(entries), "path": str(path)}]
    source = entries[0].get("source")
    if not isinstance(source, dict) or source.get("source") != "local" or not isinstance(source.get("path"), str):
        return None, [{"code": "PLUGIN_SOURCE_NOT_LOCAL", "path": str(path)}]
    try:
        marketplace_root = path.parents[2]
    except IndexError:
        return None, [{"code": "MARKETPLACE_PATH_INVALID", "path": str(path)}]
    target = _safe_target(marketplace_root / source["path"], "plugin target")
    if require_existing and not target.is_dir():
        return None, []
    if target.is_dir():
        manifest = target / ".codex-plugin" / "plugin.json"
        if not manifest.is_file():
            return None, [{"code": "PLUGIN_MANIFEST_MISSING", "target_root": str(target)}]
        try:
            if _read_json(manifest).get("name") != PLUGIN_NAME:
                return None, [{"code": "PLUGIN_NAME_MISMATCH", "target_root": str(target)}]
        except UserUpdateError as exc:
            return None, [{"code": "PLUGIN_MANIFEST_INVALID", "message": str(exc)}]
    return Installation("plugin", target, path.resolve(), name), []


def detect_installations(
    install_kind: str,
    *,
    marketplace_path: str | Path | None = None,
    skill_root: str | Path | None = None,
    home: str | Path | None = None,
) -> tuple[list[Installation], list[dict[str, Any]]]:
    if install_kind not in INSTALL_KINDS:
        raise UserUpdateError("install_kind must be plugin or skill")
    home_root = Path(home).resolve() if home is not None else Path.home().resolve()
    found: list[Installation] = []
    blockers: list[dict[str, Any]] = []
    if install_kind == "plugin":
        selected_marketplace = (
            Path(marketplace_path).resolve()
            if marketplace_path is not None
            else home_root / ".agents" / "plugins" / "marketplace.json"
        )
        item, issues = _marketplace_installation(selected_marketplace, require_existing=True)
        blockers.extend(issues)
        if item is not None:
            found.append(item)
    if install_kind == "skill":
        candidates: list[Path] = []
        if skill_root is not None:
            candidates.append(Path(skill_root).resolve())
        else:
            candidates.extend(
                [
                    home_root / ".agents" / "skills" / STANDALONE_SKILL_NAME,
                    home_root / ".codex" / "skills" / STANDALONE_SKILL_NAME,
                ]
            )
            codex_home = os.environ.get("CODEX_HOME")
            if codex_home:
                candidates.append(Path(codex_home).resolve() / "skills" / STANDALONE_SKILL_NAME)
        seen: set[Path] = set()
        for candidate in candidates:
            target = _safe_target(candidate, "skill target")
            if target in seen or not (target / "SKILL.md").is_file():
                continue
            seen.add(target)
            found.append(Installation("skill", target))
        if len(found) > 1:
            blockers.append(
                {
                    "code": "SKILL_INSTALLATION_AMBIGUOUS",
                    "targets": [str(item.target_root) for item in found],
                }
            )
            found = []
    found.sort(key=lambda item: (item.kind, str(item.target_root).lower()))
    return found, blockers


def _installed_identity(item: Installation) -> dict[str, Any]:
    if item.kind == "plugin":
        try:
            verification = verify_bundle(item.target_root)
        except (ReleaseError, OSError):
            manifest_path = item.target_root / ".codex-plugin" / "plugin.json"
            manifest = _read_json(manifest_path) if manifest_path.is_file() else {}
            return {"build_id": None, "version": manifest.get("version"), "integrity": "unverified"}
        return {
            "build_id": verification["build_id"],
            "version": verification["product_version"],
            "manifest_version": _plugin_manifest_version(item.target_root),
            "content_index_sha256": verification["content_index_sha256"],
            "integrity": "verified",
            "current_prestate_recognized": True,
            "candidate_eligible": True,
            "legacy_discovery_violation": None,
        }
    pointer_path = item.target_root / "references" / "installed-suite.json"
    if not pointer_path.is_file():
        return {"build_id": None, "version": None, "integrity": "unverified"}
    try:
        pointer = _read_json(pointer_path)
        suite_root = Path(str(pointer["suite_root"])).resolve()
        verification = verify_bundle(suite_root)
    except (KeyError, OSError, ReleaseError, UserUpdateError, ValueError):
        return {"build_id": None, "version": None, "integrity": "invalid"}
    if pointer.get("build_id") != verification.get("build_id"):
        return {"build_id": None, "version": None, "integrity": "invalid"}
    return {
        "build_id": verification["build_id"],
        "version": verification["product_version"],
        "content_index_sha256": verification["content_index_sha256"],
        "integrity": "verified",
        "suite_root": str(suite_root),
        "current_prestate_recognized": True,
        "candidate_eligible": True,
        "legacy_discovery_violation": None,
    }


def _copytree(source: Path, destination: Path) -> None:
    if destination.exists():
        raise UserUpdateError(f"transaction staging path already exists: {destination}")
    shutil.copytree(source, destination)


def _backup_root(control_root: Path, target: Path) -> Path:
    digest = hashlib.sha256(str(target.resolve()).encode("utf-8")).hexdigest()[:20]
    root = (control_root / "backups" / digest).resolve()
    try:
        root.relative_to(control_root.resolve())
    except ValueError as exc:  # pragma: no cover - digest path is construction-safe.
        raise UserUpdateError("backup root escaped the update control root") from exc
    return root


def _plugin_manifest_version(root: Path) -> str | None:
    manifest = root / ".codex-plugin" / "plugin.json"
    if not manifest.is_file():
        return None
    try:
        value = _read_json(manifest).get("version")
    except UserUpdateError:
        return None
    return value if isinstance(value, str) and value else None


def _tree_identity(root: Path) -> dict[str, Any]:
    if not root.is_dir() or _is_link_or_junction(root):
        raise UserUpdateError(f"tree identity requires a plain directory: {root}")
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if _is_link_or_junction(path):
            raise UserUpdateError(f"tree identity contains a link or junction: {path}")
        if not path.is_file():
            continue
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "file_count": len(files),
        "total_bytes": sum(int(item["size_bytes"]) for item in files),
        "tree_sha256": hashlib.sha256(canonical_json_bytes(files)).hexdigest(),
    }


def _recognize_direct_embedded_skill_prestate(skill_root: Path) -> dict[str, Any]:
    """Recognize the pre-pointer standalone projection built by sync_local_installs.

    Older standalone installs were a self-contained ``paper-spine`` tree whose
    bundled Product core lived under ``_paperspine5``.  They predate the managed
    ``installed-suite.json`` pointer, so they cannot expose a suite build id.
    Recognition is intentionally narrower than merely finding that directory:

    * the embedded identity contract and all fixed surface fields must match;
    * its compact content index is recomputed from every embedded byte;
    * every outer agent/reference/script byte must mirror its embedded authority;
    * the outer Skill must be the canonical ``paper-spine`` discovery name; and
    * links, foreign top-level entries, missing peers, and drift fail closed.

    The returned identity remains candidate-ineligible.  Upgrade therefore
    records and backs up the exact legacy tree before projecting a verified
    managed suite; it never re-labels this tree as a historical suite build.
    """

    skill_root = _safe_target(skill_root, "direct embedded Skill prestate")
    tree = _tree_identity(skill_root)
    allowed_top_level = {
        "SKILL.md",
        "_paperspine5",
        "agents",
        "references",
        "scripts",
    }
    observed_top_level = {path.name for path in skill_root.iterdir()}
    foreign_top_level = sorted(observed_top_level - allowed_top_level)
    if foreign_top_level:
        raise UserUpdateError(
            "direct embedded Skill contains foreign top-level entries: "
            + ", ".join(foreign_top_level)
        )

    skill_path = skill_root / "SKILL.md"
    embedded_root = skill_root / "_paperspine5"
    identity_path = embedded_root / "EMBEDDED-WEB-IDENTITY.json"
    if not skill_path.is_file() or not embedded_root.is_dir() or not identity_path.is_file():
        raise UserUpdateError("direct embedded Skill structure is incomplete")
    skill_text = skill_path.read_text(encoding="utf-8")
    frontmatter = re.match(r"\A---\s*\n(?P<body>.*?)\n---(?:\s*\n|\Z)", skill_text, re.DOTALL)
    if frontmatter is None or re.search(
        rf"(?m)^name:\s*{re.escape(STANDALONE_SKILL_NAME)}\s*$",
        frontmatter.group("body"),
    ) is None:
        raise UserUpdateError("direct embedded Skill discovery name is not paper-spine")

    identity = _read_json(identity_path)
    expected_fixed = {
        "contract": "paperspine5.embedded-web-core",
        "schema_version": "1.0",
        "channel": "development",
        "source_authority": "shared-workspace-allowlist",
        "frontend": "web",
        "terminal_frontend": False,
    }
    for key, expected in expected_fixed.items():
        if identity.get(key) != expected:
            raise UserUpdateError(
                f"direct embedded Skill identity field {key!r} is unsupported"
            )
    product_version = identity.get("product_version")
    expected_index = identity.get("content_index_sha256")
    expected_count = identity.get("content_file_count")
    if not isinstance(product_version, str) or not product_version:
        raise UserUpdateError("direct embedded Skill product version is incomplete")
    if not isinstance(expected_index, str) or not SHA256.fullmatch(expected_index):
        raise UserUpdateError("direct embedded Skill content index is incomplete")
    if not isinstance(expected_count, int) or isinstance(expected_count, bool) or expected_count < 1:
        raise UserUpdateError("direct embedded Skill content file count is invalid")

    indexed: list[dict[str, Any]] = []
    for path in sorted(embedded_root.rglob("*"), key=lambda item: item.as_posix()):
        if _is_link_or_junction(path):
            raise UserUpdateError(
                f"direct embedded Skill contains a link or junction: {path}"
            )
        if not path.is_file() or path == identity_path:
            continue
        indexed.append(
            {
                "path": path.relative_to(embedded_root).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    observed_index = hashlib.sha256(
        json.dumps(
            indexed,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if len(indexed) != expected_count or observed_index != expected_index:
        raise UserUpdateError("direct embedded Skill content index does not match its bytes")

    required_outer = {
        "agents/openai.yaml",
        "references/update.md",
        "scripts/paperspine5_web.py",
    }
    observed_outer: set[str] = set()
    for path in sorted(skill_root.rglob("*"), key=lambda item: item.as_posix()):
        if path == skill_path or embedded_root in path.parents or not path.is_file():
            continue
        relative = path.relative_to(skill_root).as_posix()
        observed_outer.add(relative)
        parts = relative.split("/", 1)
        if len(parts) != 2 or parts[0] not in {"agents", "references", "scripts"}:
            raise UserUpdateError(
                f"direct embedded Skill outer file is unsupported: {relative}"
            )
        if parts[0] == "scripts":
            peer = embedded_root / "01_PaperSpine4" / "src" / "scripts" / parts[1]
        else:
            peer = (
                embedded_root
                / "01_PaperSpine4"
                / "src"
                / "skill"
                / parts[0]
                / parts[1]
            )
        if not peer.is_file() or sha256_file(path) != sha256_file(peer):
            raise UserUpdateError(
                f"direct embedded Skill outer byte does not match embedded authority: {relative}"
            )
    missing_outer = sorted(required_outer - observed_outer)
    if missing_outer:
        raise UserUpdateError(
            "direct embedded Skill required outer files are missing: "
            + ", ".join(missing_outer)
        )

    return {
        "build_id": None,
        "product_version": product_version,
        "content_index_sha256": expected_index,
        "embedded_identity_sha256": sha256_file(identity_path),
        "embedded_content_file_count": expected_count,
        "source_tree": tree,
    }


def _code_constant_semantics(
    value: Any,
    *,
    active: set[int] | None = None,
    depth: int = 0,
) -> dict[str, Any]:
    if depth > 256:
        raise ValueError("CodeType constant nesting exceeds the safe limit")
    active = set() if active is None else active
    if value is None:
        return {"type": "none"}
    if value is Ellipsis:
        return {"type": "ellipsis"}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float64", "bits": struct.pack(">d", value).hex()}
    if isinstance(value, complex):
        return {
            "type": "complex128",
            "real_bits": struct.pack(">d", value.real).hex(),
            "imag_bits": struct.pack(">d", value.imag).hex(),
        }
    if isinstance(value, str):
        return {"type": "str", "value": value}
    if isinstance(value, bytes):
        return {"type": "bytes", "hex": value.hex()}
    if isinstance(value, tuple):
        identity = id(value)
        if identity in active:
            raise ValueError("cyclic tuple in CodeType constants")
        active.add(identity)
        try:
            return {
                "type": "tuple",
                "items": [
                    _code_constant_semantics(
                        item,
                        active=active,
                        depth=depth + 1,
                    )
                    for item in value
                ],
            }
        finally:
            active.remove(identity)
    if isinstance(value, frozenset):
        identity = id(value)
        if identity in active:
            raise ValueError("cyclic frozenset in CodeType constants")
        active.add(identity)
        try:
            items = [
                _code_constant_semantics(
                    item,
                    active=active,
                    depth=depth + 1,
                )
                for item in value
            ]
            items.sort(key=canonical_json_bytes)
            return {"type": "frozenset", "items": items}
        finally:
            active.remove(identity)
    if isinstance(value, types.CodeType):
        return {
            "type": "code",
            "value": _code_semantics(
                value,
                active=active,
                depth=depth + 1,
            ),
        }
    raise ValueError(f"unsupported CodeType constant: {type(value).__name__}")


def _code_semantics(
    code: types.CodeType,
    *,
    active: set[int] | None = None,
    depth: int = 0,
) -> dict[str, Any]:
    if not isinstance(code, types.CodeType):
        raise ValueError("runtime pyc payload is not a CodeType")
    if depth > 256:
        raise ValueError("CodeType nesting exceeds the safe limit")
    active = set() if active is None else active
    identity = id(code)
    if identity in active:
        raise ValueError("cyclic nested CodeType")
    active.add(identity)
    try:
        return {
            "co_argcount": code.co_argcount,
            "co_posonlyargcount": code.co_posonlyargcount,
            "co_kwonlyargcount": code.co_kwonlyargcount,
            "co_nlocals": code.co_nlocals,
            "co_stacksize": code.co_stacksize,
            "co_flags": code.co_flags,
            "co_code": code.co_code.hex(),
            "co_consts": [
                _code_constant_semantics(
                    item,
                    active=active,
                    depth=depth + 1,
                )
                for item in code.co_consts
            ],
            "co_names": list(code.co_names),
            "co_varnames": list(code.co_varnames),
            "co_filename": code.co_filename,
            "co_name": code.co_name,
            "co_qualname": code.co_qualname,
            "co_firstlineno": code.co_firstlineno,
            "co_linetable": code.co_linetable.hex(),
            "co_exceptiontable": code.co_exceptiontable.hex(),
            "co_freevars": list(code.co_freevars),
            "co_cellvars": list(code.co_cellvars),
        }
    finally:
        active.remove(identity)


def _normalize_code_filenames(
    semantics: dict[str, Any], source_relative: str
) -> None:
    expected_suffix = "/" + source_relative.replace("\\", "/")
    filename = str(semantics.get("co_filename", "")).replace("\\", "/")
    if filename != source_relative and not filename.endswith(expected_suffix):
        raise ValueError("runtime pyc code filename is not source-bound")
    semantics["co_filename"] = f"<managed-source>/{source_relative}"
    for constant in semantics.get("co_consts", []):
        if isinstance(constant, dict) and constant.get("type") == "code":
            nested = constant.get("value")
            if not isinstance(nested, dict):
                raise ValueError("runtime pyc nested code semantics are invalid")
            _normalize_code_filenames(nested, source_relative)


def _code_semantic_fingerprint(
    code: types.CodeType, *, source_relative: str | None = None
) -> str:
    semantics = _code_semantics(code)
    if source_relative is not None:
        _normalize_code_filenames(semantics, source_relative)
    return hashlib.sha256(canonical_json_bytes(semantics)).hexdigest()


def _runtime_pyc_source(
    cache_root: Path,
    path: Path,
    source_files: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]] | None:
    try:
        relative = path.relative_to(cache_root)
    except ValueError:
        return None
    if relative.parent.name != "__pycache__" or path.suffix != ".pyc":
        return None
    match = RUNTIME_PYC_NAME.fullmatch(path.name)
    if match is None or match.group("tag") != str(sys.implementation.cache_tag):
        return None
    source_relative = (
        relative.parent.parent / f"{match.group('stem')}.py"
    ).as_posix()
    source = source_files.get(source_relative)
    if source is None:
        return None
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    if len(payload) < 16 or payload[:4] != importlib.util.MAGIC_NUMBER:
        return None
    flags = int.from_bytes(payload[4:8], "little")
    if flags not in {0, 1, 3}:
        return None
    if flags == 0:
        source_size = int.from_bytes(payload[12:16], "little")
        if source_size != int(source["size_bytes"]) % (2**32):
            return None
    cached_source = cache_root / Path(source_relative)
    try:
        _assert_plain_contained_path(cache_root, cached_source, "runtime pyc source")
        source_bytes = cached_source.read_bytes()
        if flags == 0:
            expected_header = (
                importlib.util.MAGIC_NUMBER
                + (0).to_bytes(4, "little")
                + (int(cached_source.stat().st_mtime) & 0xFFFFFFFF).to_bytes(
                    4, "little"
                )
                + (len(source_bytes) & 0xFFFFFFFF).to_bytes(4, "little")
            )
        else:
            expected_header = (
                importlib.util.MAGIC_NUMBER
                + flags.to_bytes(4, "little")
                + importlib.util.source_hash(source_bytes)
            )
        if payload[:16] != expected_header:
            return None
        optimize = int(match.group("opt") or 0)
        expected_code = compile(
            source_bytes,
            str(cached_source),
            "exec",
            dont_inherit=True,
            optimize=optimize,
        )
        marshalled = io.BytesIO(payload[16:])
        actual_code = marshal.load(marshalled)
        if not isinstance(actual_code, types.CodeType):
            return None
        if marshalled.tell() != len(payload) - 16:
            return None
        if _code_semantic_fingerprint(
            expected_code, source_relative=source_relative
        ) != _code_semantic_fingerprint(
            actual_code, source_relative=source_relative
        ):
            return None
    except (EOFError, OSError, SyntaxError, TypeError, ValueError):
        return None
    return source_relative, source


def _plugin_source_inventory(source_root: Path) -> dict[str, dict[str, Any]]:
    if not source_root.is_dir() or _is_link_or_junction(source_root):
        raise UserUpdateError("plugin source must be a plain directory")
    _assert_plain_contained_path(source_root, source_root, "plugin source")
    source_files: dict[str, dict[str, Any]] = {}
    for source in sorted(source_root.rglob("*"), key=lambda item: item.as_posix()):
        if _is_link_or_junction(source):
            raise UserUpdateError(f"plugin source contains a link or junction: {source}")
        if source.is_file():
            _assert_plain_contained_path(source_root, source, "plugin source")
            relative = source.relative_to(source_root).as_posix()
            source_files[relative] = {
                "path": relative,
                "size_bytes": source.stat().st_size,
                "sha256": sha256_file(source),
            }
    return source_files


def _classify_cache_against_plugin_source(
    source_root: Path,
    cache_root: Path,
    source_files: dict[str, dict[str, Any]],
    *,
    validation_mode: str,
) -> dict[str, Any]:
    base = {
        "source_root": str(source_root.resolve()),
        "cache_root": str(cache_root.resolve()),
        "validation_mode": validation_mode,
        "classification": "missing",
        "integrity": "invalid",
        "blocker_code": "PLUGIN_CACHE_MISSING",
        "indexed_bytes_exact": False,
        "runtime_residue": [],
        "foreign_entries": [],
        "missing_indexed": [],
        "changed_indexed": [],
    }
    if not cache_root.exists():
        return base
    if not cache_root.is_dir() or _is_link_or_junction(cache_root):
        return {
            **base,
            "classification": "foreign-drift",
            "blocker_code": "PLUGIN_CACHE_FOREIGN_DRIFT",
            "foreign_entries": [str(cache_root)],
        }
    try:
        _assert_plain_contained_path(cache_root, cache_root, "plugin cache")
    except UserUpdateError as exc:
        return {
            **base,
            "classification": "foreign-drift",
            "blocker_code": "PLUGIN_CACHE_FOREIGN_DRIFT",
            "foreign_entries": [{"path": str(cache_root), "reason": str(exc)}],
        }

    missing: list[str] = []
    changed: list[dict[str, Any]] = []
    for relative, expected in source_files.items():
        cached = cache_root / Path(relative)
        if not cached.exists():
            missing.append(relative)
            continue
        if not cached.is_file() or _is_link_or_junction(cached):
            changed.append({"path": relative, "reason": "not-a-plain-file"})
            continue
        observed_size = cached.stat().st_size
        observed_sha = sha256_file(cached)
        if (
            observed_size != expected["size_bytes"]
            or observed_sha != expected["sha256"]
        ):
            changed.append(
                {
                    "path": relative,
                    "expected_size_bytes": expected["size_bytes"],
                    "observed_size_bytes": observed_size,
                    "expected_sha256": expected["sha256"],
                    "observed_sha256": observed_sha,
                }
            )
    if missing or changed:
        return {
            **base,
            "classification": "indexed-drift",
            "blocker_code": "PLUGIN_CACHE_INDEXED_DRIFT",
            "missing_indexed": missing,
            "changed_indexed": changed,
        }

    residue: list[dict[str, Any]] = []
    foreign: list[dict[str, Any]] = []
    for cached in sorted(cache_root.rglob("*"), key=lambda item: item.as_posix()):
        try:
            _assert_plain_contained_path(cache_root, cached, "plugin cache entry")
        except UserUpdateError as exc:
            foreign.append(
                {
                    "path": cached.relative_to(cache_root).as_posix(),
                    "reason": str(exc),
                }
            )
            continue
        if not cached.is_file():
            continue
        relative = cached.relative_to(cache_root).as_posix()
        if relative in source_files:
            continue
        source_binding = _runtime_pyc_source(
            cache_root, cached, source_files
        )
        if source_binding is None:
            foreign.append({"path": relative, "reason": "unindexed-or-unbound"})
            continue
        source_relative, source = source_binding
        residue.append(
            {
                "path": relative,
                "size_bytes": cached.stat().st_size,
                "sha256": sha256_file(cached),
                "source_path": source_relative,
                "source_sha256": source["sha256"],
            }
        )
    if foreign:
        return {
            **base,
            "classification": "foreign-drift",
            "blocker_code": "PLUGIN_CACHE_FOREIGN_DRIFT",
            "indexed_bytes_exact": True,
            "runtime_residue": residue,
            "foreign_entries": foreign,
        }
    return {
        **base,
        "classification": "runtime-residue" if residue else "clean",
        "integrity": (
            "verified-with-runtime-residue" if residue else "verified"
        ),
        "blocker_code": None,
        "indexed_bytes_exact": True,
        "runtime_residue": residue,
    }


def _classify_plugin_cache(
    source_root: Path,
    cache_root: Path,
    *,
    expected_build_id: str,
    expected_content_index_sha256: str,
) -> dict[str, Any]:
    """Strict candidate/placed-suite cache classification.

    This path deliberately remains candidate-only.  Historical installed
    prestates use the separate recognizer below and can never become a
    candidate, a placement, or a post-activation PASS through this function.
    """

    source_verification = verify_bundle(source_root)
    if (
        source_verification.get("build_id") != expected_build_id
        or source_verification.get("content_index_sha256")
        != expected_content_index_sha256
    ):
        raise UserUpdateError("plugin source identity differs from the expected build")
    return _classify_cache_against_plugin_source(
        source_root,
        cache_root,
        _plugin_source_inventory(source_root),
        validation_mode="strict-candidate",
    )


def _runtime_residue_summary(files: list[dict[str, Any]]) -> dict[str, Any]:
    paths = sorted(str(entry["path"]) for entry in files)
    return {
        "file_count": len(files),
        "total_bytes": sum(int(entry["size_bytes"]) for entry in files),
        "path_digest_sha256": sha256_bytes(canonical_json_bytes(paths)),
    }


def _managed_suite_source_inventory(
    suite_root: Path,
    *,
    expected_build_id: str,
    expected_content_index_sha256: str,
) -> dict[str, dict[str, Any]]:
    """Read the manifest-indexed source inventory without accepting extras."""

    suite_root = _safe_target(suite_root, "managed Skill suite root")
    if not suite_root.is_dir() or _is_link_or_junction(suite_root):
        raise UserUpdateError("managed Skill suite root must be a plain directory")
    _assert_plain_contained_path(suite_root, suite_root, "managed Skill suite")
    manifest_path = suite_root / "suite-manifest.json"
    manifest = _read_json(manifest_path)
    suite = manifest.get("suite")
    content = manifest.get("content")
    if (
        manifest.get("contract") != "paperspine5.suite-manifest"
        or manifest.get("schema_version") != "1.0"
        or not isinstance(suite, dict)
        or suite.get("product_id") != PRODUCT_ID
        or suite.get("build_id") != expected_build_id
        or not isinstance(content, dict)
        or content.get("index_sha256") != expected_content_index_sha256
        or not isinstance(content.get("files"), list)
    ):
        raise UserUpdateError(
            "managed Skill suite manifest differs from its installed pointer"
        )
    source_files: dict[str, dict[str, Any]] = {}
    for record in content["files"]:
        if not isinstance(record, dict):
            raise UserUpdateError("managed Skill suite manifest record is invalid")
        raw = str(record.get("path", ""))
        pure = PurePosixPath(raw)
        size = record.get("size_bytes")
        digest = str(record.get("sha256", ""))
        if (
            not raw
            or raw != pure.as_posix()
            or pure.is_absolute()
            or ".." in pure.parts
            or "\\" in raw
            or raw == "suite-manifest.json"
            or raw in source_files
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not SHA256.fullmatch(digest)
        ):
            raise UserUpdateError(
                f"managed Skill suite manifest path/record is unsafe: {raw}"
            )
        source_files[raw] = {
            "path": raw,
            "size_bytes": size,
            "sha256": digest,
        }
    source_files["suite-manifest.json"] = {
        "path": "suite-manifest.json",
        "size_bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
    }
    return source_files


def _classify_managed_skill_suite(
    suite_root: Path,
    *,
    expected_build_id: str,
    expected_content_index_sha256: str,
) -> dict[str, Any]:
    """Classify one pointer-bound managed suite plus exact source-bound pyc."""

    base = {
        "source_root": str(suite_root.resolve()),
        "cache_root": str(suite_root.resolve()),
        "validation_mode": "managed-skill-suite",
        "classification": "foreign-drift",
        "integrity": "invalid",
        "blocker_code": "SKILL_MANAGED_SUITE_FOREIGN_DRIFT",
        "indexed_bytes_exact": False,
        "runtime_residue": [],
        "foreign_entries": [],
        "missing_indexed": [],
        "changed_indexed": [],
        "runtime_residue_summary": _runtime_residue_summary([]),
    }
    try:
        source_files = _managed_suite_source_inventory(
            suite_root,
            expected_build_id=expected_build_id,
            expected_content_index_sha256=expected_content_index_sha256,
        )
        classified = _classify_cache_against_plugin_source(
            suite_root,
            suite_root,
            source_files,
            validation_mode="managed-skill-suite",
        )
        blocker_map = {
            "PLUGIN_CACHE_MISSING": "SKILL_MANAGED_SUITE_MISSING",
            "PLUGIN_CACHE_INDEXED_DRIFT": "SKILL_MANAGED_SUITE_INDEXED_DRIFT",
            "PLUGIN_CACHE_FOREIGN_DRIFT": "SKILL_MANAGED_SUITE_FOREIGN_DRIFT",
        }
        classified["blocker_code"] = blocker_map.get(
            str(classified.get("blocker_code")), classified.get("blocker_code")
        )
        residue = [dict(entry) for entry in classified.get("runtime_residue", [])]
        classified["runtime_residue_summary"] = _runtime_residue_summary(residue)
        if classified.get("classification") not in {"clean", "runtime-residue"}:
            return {**base, **classified}
        verification = _verify_installed_bundle_with_runtime_residue(
            suite_root,
            runtime_residue=residue,
        )
        if (
            verification.get("build_id") != expected_build_id
            or verification.get("content_index_sha256")
            != expected_content_index_sha256
        ):
            raise UserUpdateError(
                "managed Skill suite verification differs from installed pointer"
            )
        return {
            **base,
            **classified,
            "verification": verification,
            "candidate_verified": verification.get(
                "current_candidate_runtime_markers_verified"
            )
            is True
            and verification.get("current_candidate_residue_contracts_verified")
            is True
            and verification.get("current_candidate_required_resources_verified")
            is True,
            "candidate_eligible": True,
        }
    except (KeyError, OSError, ReleaseError, UserUpdateError, ValueError) as exc:
        return {
            **base,
            "foreign_entries": [
                {"path": str(suite_root), "reason": str(exc)}
            ],
        }


def _classify_legacy_installed_prestate_cache(
    source_root: Path,
    cache_root: Path,
    *,
    expected_build_id: str,
    expected_content_index_sha256: str,
) -> dict[str, Any]:
    """Read one exact recorded legacy installed prestate plus bound pyc only."""

    recognition = _recognize_legacy_installed_prestate(
        source_root,
        expected_build_id=expected_build_id,
        expected_content_index_sha256=expected_content_index_sha256,
    )
    classified = _classify_cache_against_plugin_source(
        source_root,
        cache_root,
        _plugin_source_inventory(source_root),
        validation_mode="recorded-legacy-installed",
    )
    return {
        **classified,
        "legacy_recognition": recognition,
        "candidate_verified": False,
        "candidate_eligible": False,
    }


def _command_phase_record(
    phase: str, command: list[str], result: CommandResult
) -> dict[str, Any]:
    parsed: Any = None
    parse_error: str | None = None
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            parse_error = str(exc)
    return {
        "phase": phase,
        "kind": "command",
        "status": "passed" if result.returncode == 0 and parse_error is None else "failed",
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "result_json": parsed,
        "json_parse_error": parse_error,
        "recorded_at": _now(),
    }


def _installed_plugin_from_list(payload: Any, selector: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("installed"), list):
        return None
    matches = [
        item
        for item in payload["installed"]
        if isinstance(item, dict) and item.get("pluginId") == selector
    ]
    return matches[0] if len(matches) == 1 else None


def _remove_controlled(path: Path, allowed_parent: Path) -> None:
    try:
        path.resolve().relative_to(allowed_parent.resolve())
    except ValueError as exc:
        raise UserUpdateError(f"refusing to remove path outside transaction boundary: {path}") from exc
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _load_discovery_migration() -> Any:
    """Load the canonical PaperSpine migration source from workspace/bundle."""
    here = Path(__file__).resolve()
    relative = Path("01_PaperSpine4") / "src" / "scripts" / "skill_discovery_migration.py"
    candidates = [here.parents[1] / relative, here.parents[2] / relative]
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        raise UserUpdateError(
            "verified suite is missing the canonical Skill discovery migration module"
        )
    spec = importlib.util.spec_from_file_location("paperspine_skill_discovery_migration", source)
    if spec is None or spec.loader is None:
        raise UserUpdateError("Skill discovery migration module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _discovery_operation_id(install_kind: str, operation_id: str, phase: str) -> str:
    digest = hashlib.sha256(
        f"{install_kind}\0{operation_id}\0{phase}".encode("utf-8")
    ).hexdigest()[:32]
    return f"suite-{phase}-{digest}"


def _discovery_link(receipt: dict[str, Any], receipt_path: Path) -> dict[str, Any]:
    return {
        "contract": receipt.get("contract"),
        "schema_version": receipt.get("schema_version"),
        "operation": receipt.get("operation"),
        "operation_id": receipt.get("operation_id"),
        "status": receipt.get("status"),
        "receipt_path": str(receipt_path.resolve()),
        "receipt_sha256": receipt.get("receipt_sha256"),
        "item_count": len(receipt.get("items", [])),
        "external_action_authorized": False,
    }


class UserUpdateManager:
    def __init__(
        self,
        install_kind: str,
        control_root: str | Path,
        *,
        command_runner: CommandRunner | None = None,
        codex_command: str = "codex",
        home: str | Path | None = None,
    ) -> None:
        if install_kind not in INSTALL_KINDS:
            raise UserUpdateError("install_kind must be plugin or skill")
        self.install_kind = install_kind
        self.control_root = _safe_target(control_root, "control_root")
        self.command_runner = command_runner or _default_runner
        self.codex_command = codex_command
        self.home = Path(home).resolve() if home is not None else Path.home().resolve()
        for discovery_root in (
            self.home / ".agents" / "skills",
            self.home / ".codex" / "skills",
        ):
            try:
                self.control_root.relative_to(discovery_root.resolve())
            except ValueError:
                continue
            raise UserUpdateError("control_root must stay outside Skill discovery roots")
        self.state_path = self.control_root / "user-update-state.json"
        self.receipts = self.control_root / "receipts"
        self.staging = self.control_root / "staging"
        self.installs = self.control_root / "installs"
        self.transactions = self.control_root / "transactions"
        self.cache_reconciliations = (
            self.control_root / "plugin-cache-reconciliations"
        )
        self.skill_managed_suite_reconciliations = (
            self.control_root / "skill-managed-suite-reconciliations"
        )
        self.discovery_archive = self.home / ".paperspine5" / DISCOVERY_ARCHIVE_DIRECTORY
        if home is not None:
            self.codex_home = self.home / ".codex"
        else:
            self.codex_home = Path(
                os.environ.get("CODEX_HOME", self.home / ".codex")
            ).resolve()

    def _discovery_roots(self) -> dict[str, Path]:
        return {
            "agents": self.home / ".agents" / "skills",
            "codex": self.home / ".codex" / "skills",
        }

    def _cache_reconciliation_root(
        self, operation_id: str, *, item_kind: str = "plugin"
    ) -> Path:
        parent = (
            self.cache_reconciliations
            if item_kind == "plugin"
            else self.skill_managed_suite_reconciliations
        )
        return parent / _safe_id(operation_id, "operation_id")

    @staticmethod
    def _reconciliation_contracts(item_kind: str) -> tuple[str, str, str]:
        if item_kind == "plugin":
            return (
                PLUGIN_CACHE_RECONCILIATION_CONTRACT,
                PLUGIN_PRESTATE_VALIDATION_CONTRACT,
                "paperspine5.plugin-cache-reconciliation-restore-receipt",
            )
        if item_kind == "skill":
            return (
                SKILL_MANAGED_SUITE_RECONCILIATION_CONTRACT,
                SKILL_MANAGED_SUITE_PRESTATE_VALIDATION_CONTRACT,
                "paperspine5.skill-managed-suite-reconciliation-restore-receipt",
            )
        raise UserUpdateError("runtime residue surface must be plugin or skill")

    def _validate_cache_reconciliation_receipt(
        self, receipt_path: Path, *, item_kind: str = "plugin"
    ) -> dict[str, Any]:
        receipt_contract, validation_contract, _ = self._reconciliation_contracts(
            item_kind
        )
        _assert_plain_contained_path(
            receipt_path.parent, receipt_path, "plugin cache reconciliation receipt"
        )
        receipt = _read_json(receipt_path)
        if (
            receipt.get("contract") != receipt_contract
            or receipt.get("schema_version")
            != PLUGIN_CACHE_RECONCILIATION_SCHEMA_VERSION
            or receipt.get("status") != "committed"
            or receipt.get("external_action_authorized") is not False
            or receipt.get("self_sha256") != _self_hash(receipt)
        ):
            raise UserUpdateError("plugin cache reconciliation receipt is invalid")
        source_validation = receipt.get("source_validation")
        if not isinstance(source_validation, dict) or (
            source_validation.get("contract") != validation_contract
            or source_validation.get("schema_version")
            != PLUGIN_PRESTATE_VALIDATION_SCHEMA_VERSION
            or source_validation.get("mode")
            not in (
                {"strict-candidate", "recorded-legacy-installed"}
                if item_kind == "plugin"
                else {"managed-suite"}
            )
            or source_validation.get("external_action_authorized") is not False
            or source_validation.get("self_sha256")
            != _self_hash(source_validation)
        ):
            raise UserUpdateError(
                "plugin cache reconciliation source validation is invalid"
            )
        mode = source_validation["mode"]
        if (
            source_validation.get("build_id") != receipt.get("source_build_id")
            or source_validation.get("content_index_sha256")
            != receipt.get("source_content_index_sha256")
            or Path(str(source_validation.get("target_root", ""))).resolve()
            != Path(str(receipt.get("source_root", ""))).resolve()
            or (
                mode == "strict-candidate"
                and (
                    source_validation.get("candidate_verified") is not True
                    or source_validation.get("candidate_eligible") is not True
                )
            )
            or (
                mode == "recorded-legacy-installed"
                and (
                    source_validation.get("candidate_verified") is not False
                    or source_validation.get("candidate_eligible") is not False
                    or (
                        source_validation.get("legacy_recognition") or {}
                    ).get("legacy_discovery_violation", {}).get("code")
                    != "LEGACY_WORKSPACE_SKILL_PRESENT"
                )
            )
            or (
                mode == "managed-suite"
                and (
                    not isinstance(
                        source_validation.get("candidate_verified"), bool
                    )
                    or source_validation.get("candidate_eligible") is not True
                )
            )
        ):
            raise UserUpdateError(
                "plugin cache reconciliation source validation binding drifted"
            )
        files = receipt.get("files")
        if not isinstance(files, list) or not files:
            raise UserUpdateError("runtime residue reconciliation files are invalid")
        summary = _runtime_residue_summary(files)
        summary_present = any(key in receipt for key in summary)
        if (item_kind == "skill" or summary_present) and any(
            receipt.get(key) != value for key, value in summary.items()
        ):
            raise UserUpdateError(
                "runtime residue reconciliation summary binding drifted"
            )
        if item_kind == "skill" and (
            Path(str(receipt.get("cache_root", ""))).resolve()
            != Path(str(receipt.get("source_root", ""))).resolve()
            or files != source_validation.get("runtime_residue")
            or summary != source_validation.get("runtime_residue_summary")
        ):
            raise UserUpdateError(
                "managed Skill suite residue receipt binding drifted"
            )
        root = receipt_path.parent
        payload_root = root / "payload"
        for item in receipt.get("files", []):
            relative = Path(str(item.get("path", "")))
            archived = (payload_root / relative).absolute()
            _assert_plain_contained_path(
                root, archived, "plugin cache reconciliation payload"
            )
            if (
                not archived.is_file()
                or _is_link_or_junction(archived)
                or archived.stat().st_size != item.get("size_bytes")
                or sha256_file(archived) != item.get("sha256")
            ):
                raise UserUpdateError(
                    "plugin cache reconciliation payload hash mismatch"
                )
        return receipt

    def _archive_plugin_cache_residue(
        self,
        operation_id: str,
        item: Installation,
        cache: dict[str, Any],
        *,
        prestate_identity: dict[str, Any],
        fault_at: str | None = None,
    ) -> dict[str, Any]:
        files = cache.get("runtime_residue")
        if cache.get("classification") != "runtime-residue" or not isinstance(
            files, list
        ):
            raise UserUpdateError(
                "plugin cache reconciliation requires typed runtime residue"
            )
        receipt_contract, _, _ = self._reconciliation_contracts(item.kind)
        cache_root = Path(str(cache.get("cache_root", ""))).absolute()
        source_root = (
            item.target_root.absolute()
            if item.kind == "plugin"
            else cache_root
        )
        source_validation = self._prestate_validation_link(item, prestate_identity)
        expected_build_id = str(prestate_identity.get("build_id", ""))
        expected_content_index_sha256 = str(
            prestate_identity.get("content_index_sha256", "")
        )
        root = self._cache_reconciliation_root(
            operation_id, item_kind=item.kind
        )
        owner_path = root / "owner.json"
        journal_path = root / "journal.json"
        receipt_path = root / "receipt.json"
        payload_root = root / "payload"
        if receipt_path.is_file():
            receipt = self._validate_cache_reconciliation_receipt(
                receipt_path, item_kind=item.kind
            )
            if (
                receipt.get("operation_id") != operation_id
                or receipt.get("source_validation") != source_validation
            ):
                raise UserUpdateError("plugin cache reconciliation replay drift")
            return {
                "contract": receipt["contract"],
                "schema_version": receipt["schema_version"],
                "operation_id": operation_id,
                "status": "committed",
                "receipt_path": str(receipt_path.resolve()),
                "receipt_sha256": sha256_file(receipt_path),
                "self_sha256": receipt["self_sha256"],
                "file_count": len(receipt["files"]),
                "total_bytes": sum(
                    int(entry["size_bytes"]) for entry in receipt["files"]
                ),
                "path_digest_sha256": _runtime_residue_summary(
                    receipt["files"]
                )["path_digest_sha256"],
                "external_action_authorized": False,
            }
        expected_files = sorted(
            [dict(entry) for entry in files], key=lambda entry: entry["path"]
        )
        for entry in expected_files:
            relative = Path(str(entry.get("path", "")))
            if relative.is_absolute() or ".." in relative.parts:
                raise UserUpdateError(
                    "plugin cache residue path contains traversal"
                )
        request = {
            "operation_id": operation_id,
            "cache_root": str(cache_root),
            "source_root": str(source_root),
            "source_build_id": expected_build_id,
            "source_content_index_sha256": expected_content_index_sha256,
            "source_validation": source_validation,
            "files": expected_files,
        }
        request_sha = _request_hash(request)
        if not root.exists():
            fresh = self._classify_prestate_cache(
                item,
                prestate_identity,
                cache_state="initial",
                require_current_state=True,
            )
            fresh_files = sorted(
                [dict(entry) for entry in fresh.get("runtime_residue", [])],
                key=lambda entry: entry["path"],
            )
            if (
                fresh.get("classification") != "runtime-residue"
                or fresh_files != expected_files
            ):
                raise UserUpdateError(
                    "runtime residue prestate drifted before archival"
                )
        if root.exists():
            if not owner_path.is_file() or not journal_path.is_file():
                raise UserUpdateError(
                    "plugin cache reconciliation root is foreign or incomplete"
                )
            owner = _read_json(owner_path)
            journal = _read_json(journal_path)
            if (
                owner.get("operation_id") != operation_id
                or owner.get("request_sha256") != request_sha
                or owner.get("self_sha256") != _self_hash(owner)
                or journal.get("request_sha256") != request_sha
            ):
                raise UserUpdateError(
                    "plugin cache reconciliation owner/request collision"
                )
        else:
            root.parent.mkdir(parents=True, exist_ok=True)
            root.mkdir(exist_ok=False)
            _assert_plain_contained_path(
                root, root, "plugin cache reconciliation root"
            )
            owner = {
                "contract": (
                    "paperspine5.plugin-cache-reconciliation-owner"
                    if item.kind == "plugin"
                    else "paperspine5.skill-managed-suite-reconciliation-owner"
                ),
                "schema_version": "1.0",
                "operation_id": operation_id,
                "request_sha256": request_sha,
                "created_at": _now(),
                "external_action_authorized": False,
            }
            owner["self_sha256"] = _self_hash(owner)
            _write_atomic(owner_path, owner)
            journal = {
                "contract": (
                    "paperspine5.plugin-cache-reconciliation-journal"
                    if item.kind == "plugin"
                    else "paperspine5.skill-managed-suite-reconciliation-journal"
                ),
                "schema_version": "1.0",
                "operation_id": operation_id,
                "request_sha256": request_sha,
                "status": "prepared",
                "completed_paths": [],
                "updated_at": _now(),
                "external_action_authorized": False,
            }
            _write_atomic(journal_path, journal)
        completed = set(str(path) for path in journal.get("completed_paths", []))
        for index, entry in enumerate(expected_files):
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise UserUpdateError(
                    "plugin cache residue path contains traversal"
                )
            source = (cache_root / relative).absolute()
            destination = (payload_root / relative).absolute()
            _assert_plain_contained_path(
                cache_root, source, "plugin cache runtime residue"
            )
            _assert_plain_contained_path(
                root, destination, "plugin cache reconciliation payload"
            )
            source_exact = bool(
                source.is_file()
                and not _is_link_or_junction(source)
                and source.stat().st_size == entry["size_bytes"]
                and sha256_file(source) == entry["sha256"]
            )
            destination_exact = bool(
                destination.is_file()
                and not _is_link_or_junction(destination)
                and destination.stat().st_size == entry["size_bytes"]
                and sha256_file(destination) == entry["sha256"]
            )
            if destination.exists() and not destination_exact:
                raise UserUpdateError(
                    "plugin cache reconciliation archive contains foreign bytes"
                )
            if not destination_exact:
                if not source_exact:
                    raise UserUpdateError(
                        "plugin cache runtime residue changed before archival"
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                _assert_plain_contained_path(
                    root,
                    destination.parent,
                    "plugin cache reconciliation payload parent",
                )
                stage = destination.with_name(f".{destination.name}.owned-stage")
                _assert_plain_contained_path(
                    root, stage, "plugin cache reconciliation owned stage"
                )
                if stage.exists():
                    if (
                        not stage.is_file()
                        or _is_link_or_junction(stage)
                        or stage.stat().st_size != entry["size_bytes"]
                        or sha256_file(stage) != entry["sha256"]
                    ):
                        raise UserUpdateError(
                            "plugin cache reconciliation stage contains foreign bytes"
                        )
                else:
                    shutil.copy2(source, stage)
                if fault_at == f"after_residue_stage_{index}":
                    raise OSError("injected failure after runtime residue stage")
                os.replace(stage, destination)
                destination_exact = True
            if source.exists():
                if not source_exact:
                    raise UserUpdateError(
                        "plugin cache runtime residue drifted during archival"
                    )
                source.unlink()
            if fault_at == f"after_residue_remove_{index}":
                raise OSError("injected failure after runtime residue isolation")
            completed.add(entry["path"])
            journal["completed_paths"] = sorted(completed)
            journal["updated_at"] = _now()
            _write_atomic(journal_path, journal)
        strict = self._classify_prestate_cache(
            item,
            prestate_identity,
            cache_state="reconciled",
            require_current_state=True,
        )
        if strict.get("classification") != "clean":
            raise UserUpdateError(
                "plugin cache is not strict after runtime residue reconciliation"
            )
        journal["status"] = "committed"
        journal["updated_at"] = _now()
        _write_atomic(journal_path, journal)
        receipt = {
            "contract": receipt_contract,
            "schema_version": PLUGIN_CACHE_RECONCILIATION_SCHEMA_VERSION,
            "operation_id": operation_id,
            "request_sha256": request_sha,
            "status": "committed",
            "created_at": owner["created_at"],
            "source_root": str(source_root),
            "cache_root": str(cache_root),
            "source_build_id": expected_build_id,
            "source_content_index_sha256": expected_content_index_sha256,
            "source_validation": source_validation,
            "files": expected_files,
            **_runtime_residue_summary(expected_files),
            "post_cache_classification": "clean",
            "external_action_authorized": False,
        }
        receipt["self_sha256"] = _self_hash(receipt)
        _write_atomic(receipt_path, receipt)
        return {
            "contract": receipt["contract"],
            "schema_version": receipt["schema_version"],
            "operation_id": operation_id,
            "status": "committed",
            "receipt_path": str(receipt_path.resolve()),
            "receipt_sha256": sha256_file(receipt_path),
            "self_sha256": receipt["self_sha256"],
            "file_count": len(expected_files),
            "total_bytes": sum(int(entry["size_bytes"]) for entry in expected_files),
            "path_digest_sha256": _runtime_residue_summary(expected_files)[
                "path_digest_sha256"
            ],
            "external_action_authorized": False,
        }

    def _restore_plugin_cache_residue(
        self,
        link: dict[str, Any],
        item: Installation,
        *,
        restore_operation_id: str,
        prestate_identity: dict[str, Any],
        require_current_state: bool,
    ) -> dict[str, Any]:
        _, _, restore_contract = self._reconciliation_contracts(item.kind)
        receipt_path = Path(str(link.get("receipt_path", ""))).absolute()
        if (
            not receipt_path.is_file()
            or sha256_file(receipt_path) != link.get("receipt_sha256")
        ):
            raise UserUpdateError(
                "plugin cache reconciliation link hash mismatch"
            )
        receipt = self._validate_cache_reconciliation_receipt(
            receipt_path, item_kind=item.kind
        )
        source_validation = self._prestate_validation_link(item, prestate_identity)
        expected_build_id = str(prestate_identity.get("build_id", ""))
        expected_content_index_sha256 = str(
            prestate_identity.get("content_index_sha256", "")
        )
        if (
            receipt.get("source_build_id") != expected_build_id
            or receipt.get("source_content_index_sha256")
            != expected_content_index_sha256
            or receipt.get("source_validation") != source_validation
        ):
            raise UserUpdateError(
                "plugin cache reconciliation receipt targets another build"
            )
        cache_root = Path(receipt["cache_root"]).absolute()
        already_restored = False
        try:
            clean = self._classify_prestate_cache(
                item,
                prestate_identity,
                cache_state="reconciled",
                require_current_state=require_current_state,
            )
        except UserUpdateError as reconciled_error:
            try:
                clean = self._classify_prestate_cache(
                    item,
                    prestate_identity,
                    cache_state="initial",
                    require_current_state=require_current_state,
                )
                already_restored = True
            except UserUpdateError:
                raise reconciled_error
        if clean.get("classification") not in {"clean", "runtime-residue"}:
            details = (
                clean.get("foreign_entries")
                or clean.get("changed_indexed")
                or clean.get("missing_indexed")
                or clean.get("blocker_code")
            )
            raise UserUpdateError(
                "plugin cache cannot receive archived runtime residue: "
                f"{details}"
            )
        payload_root = receipt_path.parent / "payload"
        for entry in receipt["files"]:
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise UserUpdateError(
                    "runtime residue restore path contains traversal"
                )
            archived = (payload_root / relative).absolute()
            destination = (cache_root / relative).absolute()
            _assert_plain_contained_path(
                receipt_path.parent,
                archived,
                "archived runtime residue",
            )
            _assert_plain_contained_path(
                cache_root, destination, "runtime residue restore destination"
            )
            if not archived.is_file() or sha256_file(archived) != entry["sha256"]:
                raise UserUpdateError("archived runtime residue hash mismatch")
            if destination.exists():
                if (
                    not destination.is_file()
                    or _is_link_or_junction(destination)
                    or destination.stat().st_size != entry["size_bytes"]
                    or sha256_file(destination) != entry["sha256"]
                ):
                    raise UserUpdateError(
                        "runtime residue restore would overwrite foreign bytes"
                    )
                continue
            if already_restored:
                raise UserUpdateError(
                    "runtime residue restore prestate is incomplete after validation"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            _assert_plain_contained_path(
                cache_root,
                destination.parent,
                "runtime residue restore parent",
            )
            stage = destination.with_name(f".{destination.name}.restore-stage")
            _assert_plain_contained_path(
                cache_root, stage, "runtime residue restore owned stage"
            )
            if stage.exists():
                raise UserUpdateError("runtime residue restore stage collision")
            shutil.copy2(archived, stage)
            if sha256_file(stage) != entry["sha256"]:
                raise UserUpdateError("runtime residue restore stage hash mismatch")
            os.replace(stage, destination)
        restored = self._classify_prestate_cache(
            item,
            prestate_identity,
            cache_state="initial",
            require_current_state=require_current_state,
        )
        if restored.get("classification") != "runtime-residue":
            raise UserUpdateError("runtime residue restore did not reproduce prestate")
        restore_path = receipt_path.parent / f"restore-{_safe_id(restore_operation_id, 'operation_id')}.json"
        restore = {
            "contract": restore_contract,
            "schema_version": "1.0",
            "operation_id": restore_operation_id,
            "source_receipt_path": str(receipt_path.resolve()),
            "source_receipt_sha256": sha256_file(receipt_path),
            "status": "committed",
            "file_count": len(receipt["files"]),
            "total_bytes": sum(
                int(entry["size_bytes"]) for entry in receipt["files"]
            ),
            "path_digest_sha256": _runtime_residue_summary(receipt["files"])[
                "path_digest_sha256"
            ],
            "cache_root": str(cache_root),
            "restored_classification": "runtime-residue",
            "source_validation_mode": source_validation["mode"],
            "source_validation_sha256": source_validation["self_sha256"],
            "created_at": _now(),
            "external_action_authorized": False,
        }
        restore["self_sha256"] = _self_hash(restore)
        if restore_path.exists():
            existing = _read_json(restore_path)
            if existing != restore:
                raise UserUpdateError("runtime residue restore receipt collision")
        else:
            _write_atomic(restore_path, restore)
        return {
            "contract": restore["contract"],
            "schema_version": restore["schema_version"],
            "operation_id": restore_operation_id,
            "status": "committed",
            "receipt_path": str(restore_path.resolve()),
            "receipt_sha256": sha256_file(restore_path),
            "self_sha256": restore["self_sha256"],
            "file_count": len(receipt["files"]),
            "total_bytes": restore["total_bytes"],
            "path_digest_sha256": restore["path_digest_sha256"],
            "external_action_authorized": False,
        }

    def _plugin_selector(self, item: Installation) -> str:
        if item.kind != "plugin" or not item.marketplace_name:
            raise UserUpdateError("plugin installation has no marketplace identity")
        return f"{PLUGIN_NAME}@{item.marketplace_name}"

    def _recorded_active_identity(self, item: Installation) -> dict[str, str]:
        matches = [
            entry
            for entry in self._state().get("active_installations", [])
            if isinstance(entry, dict)
            and entry.get("kind") == item.kind
            and Path(str(entry.get("target_root", ""))).resolve()
            == item.target_root.resolve()
        ]
        if len(matches) != 1:
            raise UserUpdateError(
                "legacy installed prestate requires one exact active state record"
            )
        build_id = str(matches[0].get("build_id", ""))
        content_index = str(matches[0].get("content_index_sha256", ""))
        if not SAFE_ID.fullmatch(build_id) or not SHA256.fullmatch(content_index):
            raise UserUpdateError(
                "legacy installed prestate state identity is incomplete"
            )
        return {"build_id": build_id, "content_index_sha256": content_index}

    def _legacy_prestate_validation_descriptor(
        self,
        item: Installation,
        *,
        recorded: dict[str, str],
        version: str,
        observed: dict[str, Any],
        source_recognition: dict[str, Any],
        cache: dict[str, Any],
    ) -> dict[str, Any]:
        observed_plugin = observed.get("observed") or {}
        observed_source = observed_plugin.get("source") or {}
        descriptor = {
            "contract": PLUGIN_PRESTATE_VALIDATION_CONTRACT,
            "schema_version": PLUGIN_PRESTATE_VALIDATION_SCHEMA_VERSION,
            "mode": "recorded-legacy-installed",
            "build_id": recorded["build_id"],
            "content_index_sha256": recorded["content_index_sha256"],
            "manifest_version": version,
            "target_root": str(item.target_root.resolve()),
            "cache_root": str(Path(str(cache["cache_root"])).resolve()),
            "source_tree": _tree_identity(item.target_root),
            "initial_cache_tree": _tree_identity(
                Path(str(cache["cache_root"])).resolve()
            ),
            "initial_cache_classification": cache["classification"],
            "runtime_residue": sorted(
                [dict(entry) for entry in cache.get("runtime_residue", [])],
                key=lambda entry: entry["path"],
            ),
            "state_binding": {
                "kind": item.kind,
                "target_root": str(item.target_root.resolve()),
                "build_id": recorded["build_id"],
                "content_index_sha256": recorded["content_index_sha256"],
            },
            "cli_binding": {
                "plugin_id": self._plugin_selector(item),
                "version": observed_plugin.get("version"),
                "installed": observed_plugin.get("installed"),
                "enabled": observed_plugin.get("enabled"),
                "source": {
                    "source": observed_source.get("source"),
                    "path": str(Path(str(observed_source.get("path", ""))).resolve()),
                },
            },
            "legacy_recognition": source_recognition,
            "candidate_verified": False,
            "candidate_eligible": False,
            "external_action_authorized": False,
        }
        descriptor["self_sha256"] = _self_hash(descriptor)
        return descriptor

    def _validate_legacy_prestate_descriptor(
        self,
        item: Installation,
        identity: dict[str, Any],
        *,
        cache_state: str,
        require_current_state: bool,
    ) -> dict[str, Any]:
        if cache_state not in {"initial", "reconciled"}:
            raise UserUpdateError("legacy prestate cache state is invalid")
        descriptor = identity.get("prestate_validation")
        if not isinstance(descriptor, dict) or (
            descriptor.get("contract") != PLUGIN_PRESTATE_VALIDATION_CONTRACT
            or descriptor.get("schema_version")
            != PLUGIN_PRESTATE_VALIDATION_SCHEMA_VERSION
            or descriptor.get("mode") != "recorded-legacy-installed"
            or descriptor.get("external_action_authorized") is not False
            or descriptor.get("self_sha256") != _self_hash(descriptor)
        ):
            raise UserUpdateError(
                "legacy installed prestate validation descriptor is invalid"
            )
        expected_build = str(identity.get("build_id", ""))
        expected_index = str(identity.get("content_index_sha256", ""))
        if (
            identity.get("candidate_verified") is not False
            or identity.get("candidate_eligible") is not False
            or (identity.get("legacy_discovery_violation") or {}).get("code")
            != "LEGACY_WORKSPACE_SKILL_PRESENT"
            or descriptor.get("candidate_verified") is not False
            or descriptor.get("candidate_eligible") is not False
            or descriptor.get("build_id") != expected_build
            or descriptor.get("content_index_sha256") != expected_index
            or descriptor.get("manifest_version")
            != _plugin_manifest_version(item.target_root)
            or Path(str(descriptor.get("target_root", ""))).resolve()
            != item.target_root.resolve()
        ):
            raise UserUpdateError(
                "legacy installed prestate validation binding drifted"
            )
        if require_current_state:
            recorded = self._recorded_active_identity(item)
            if descriptor.get("state_binding") != {
                "kind": item.kind,
                "target_root": str(item.target_root.resolve()),
                "build_id": recorded["build_id"],
                "content_index_sha256": recorded["content_index_sha256"],
            }:
                raise UserUpdateError(
                    "legacy installed prestate state binding drifted"
                )
        recognition = _recognize_legacy_installed_prestate(
            item.target_root,
            expected_build_id=expected_build,
            expected_content_index_sha256=expected_index,
        )
        if recognition != descriptor.get("legacy_recognition"):
            raise UserUpdateError(
                "legacy installed prestate source recognition drifted"
            )
        if _tree_identity(item.target_root) != descriptor.get("source_tree"):
            raise UserUpdateError("legacy installed prestate source tree drifted")
        cache_root = Path(str(descriptor.get("cache_root", ""))).resolve()
        classified = _classify_legacy_installed_prestate_cache(
            item.target_root,
            cache_root,
            expected_build_id=expected_build,
            expected_content_index_sha256=expected_index,
        )
        if cache_state == "initial":
            if (
                classified.get("classification")
                != descriptor.get("initial_cache_classification")
                or sorted(
                    [dict(entry) for entry in classified.get("runtime_residue", [])],
                    key=lambda entry: entry["path"],
                )
                != descriptor.get("runtime_residue")
                or _tree_identity(cache_root)
                != descriptor.get("initial_cache_tree")
            ):
                raise UserUpdateError(
                    "legacy installed prestate initial cache binding drifted"
                )
        elif (
            classified.get("classification") != "clean"
            or _tree_identity(cache_root) != descriptor.get("source_tree")
        ):
            raise UserUpdateError(
                "legacy installed prestate reconciled cache is not exact"
            )
        return classified

    def _managed_skill_prestate_validation_descriptor(
        self,
        item: Installation,
        *,
        suite_root: Path,
        build_id: str,
        content_index_sha256: str,
        managed_suite: dict[str, Any],
    ) -> dict[str, Any]:
        residue = sorted(
            [dict(entry) for entry in managed_suite.get("runtime_residue", [])],
            key=lambda entry: entry["path"],
        )
        descriptor = {
            "contract": SKILL_MANAGED_SUITE_PRESTATE_VALIDATION_CONTRACT,
            "schema_version": SKILL_MANAGED_SUITE_PRESTATE_VALIDATION_SCHEMA_VERSION,
            "mode": "managed-suite",
            "build_id": build_id,
            "content_index_sha256": content_index_sha256,
            "target_root": str(suite_root.resolve()),
            "projection_root": str(item.target_root.resolve()),
            "projection_tree": _tree_identity(item.target_root),
            "initial_suite_tree": _tree_identity(suite_root),
            "initial_classification": managed_suite["classification"],
            "runtime_residue": residue,
            "runtime_residue_summary": _runtime_residue_summary(residue),
            "candidate_verified": managed_suite.get("candidate_verified") is True,
            "candidate_eligible": True,
            "external_action_authorized": False,
        }
        descriptor["self_sha256"] = _self_hash(descriptor)
        return descriptor

    def _validate_managed_skill_prestate_descriptor(
        self,
        item: Installation,
        identity: dict[str, Any],
        *,
        cache_state: str,
        require_current_state: bool,
    ) -> dict[str, Any]:
        if cache_state not in {"initial", "reconciled"}:
            raise UserUpdateError("managed Skill residue state is invalid")
        descriptor = identity.get("prestate_validation")
        if not isinstance(descriptor, dict) or (
            descriptor.get("contract")
            != SKILL_MANAGED_SUITE_PRESTATE_VALIDATION_CONTRACT
            or descriptor.get("schema_version")
            != SKILL_MANAGED_SUITE_PRESTATE_VALIDATION_SCHEMA_VERSION
            or descriptor.get("mode") != "managed-suite"
            or not isinstance(descriptor.get("candidate_verified"), bool)
            or descriptor.get("candidate_eligible") is not True
            or descriptor.get("external_action_authorized") is not False
            or descriptor.get("self_sha256") != _self_hash(descriptor)
        ):
            raise UserUpdateError(
                "managed Skill suite prestate validation descriptor is invalid"
            )
        expected_build = str(identity.get("build_id", ""))
        expected_index = str(identity.get("content_index_sha256", ""))
        suite_root = Path(str(descriptor.get("target_root", ""))).resolve()
        if (
            not SAFE_ID.fullmatch(expected_build)
            or not SHA256.fullmatch(expected_index)
            or descriptor.get("build_id") != expected_build
            or descriptor.get("content_index_sha256") != expected_index
            or descriptor.get("candidate_verified")
            != (identity.get("candidate_verified") is True)
            or Path(str(identity.get("suite_root", ""))).resolve() != suite_root
        ):
            raise UserUpdateError(
                "managed Skill suite prestate validation binding drifted"
            )
        pointer_path = item.target_root / "references" / "installed-suite.json"
        if require_current_state and (
            Path(str(descriptor.get("projection_root", ""))).resolve()
            != item.target_root.resolve()
            or _tree_identity(item.target_root) != descriptor.get("projection_tree")
        ):
            raise UserUpdateError("managed Skill projection binding drifted")
        if require_current_state or pointer_path.is_file():
            pointer = _read_json(pointer_path)
            if (
                pointer.get("contract") != "paperspine5.installed-suite-pointer"
                or pointer.get("schema_version") != "1.0"
                or pointer.get("product_id") != PRODUCT_ID
                or pointer.get("build_id") != expected_build
                or pointer.get("content_index_sha256") != expected_index
                or Path(str(pointer.get("suite_root", ""))).resolve() != suite_root
            ):
                raise UserUpdateError("managed Skill installed pointer drifted")
        classified = _classify_managed_skill_suite(
            suite_root,
            expected_build_id=expected_build,
            expected_content_index_sha256=expected_index,
        )
        if cache_state == "initial":
            residue = sorted(
                [dict(entry) for entry in classified.get("runtime_residue", [])],
                key=lambda entry: entry["path"],
            )
            if (
                classified.get("classification")
                != descriptor.get("initial_classification")
                or residue != descriptor.get("runtime_residue")
                or _runtime_residue_summary(residue)
                != descriptor.get("runtime_residue_summary")
                or _tree_identity(suite_root)
                != descriptor.get("initial_suite_tree")
            ):
                raise UserUpdateError(
                    "managed Skill suite initial residue binding drifted"
                )
        elif classified.get("classification") != "clean":
            raise UserUpdateError(
                "managed Skill suite is not clean after residue reconciliation"
            )
        return classified

    def _prestate_validation_link(
        self, item: Installation, identity: dict[str, Any]
    ) -> dict[str, Any]:
        if item.kind == "skill":
            descriptor = identity.get("prestate_validation")
            if not isinstance(descriptor, dict):
                raise UserUpdateError(
                    "managed Skill suite has no validation descriptor"
                )
            return dict(descriptor)
        if identity.get("candidate_eligible") is False:
            descriptor = identity.get("prestate_validation")
            if not isinstance(descriptor, dict):
                raise UserUpdateError(
                    "legacy installed prestate has no validation descriptor"
                )
            return dict(descriptor)
        link = {
            "contract": PLUGIN_PRESTATE_VALIDATION_CONTRACT,
            "schema_version": PLUGIN_PRESTATE_VALIDATION_SCHEMA_VERSION,
            "mode": "strict-candidate",
            "build_id": str(identity.get("build_id", "")),
            "content_index_sha256": str(
                identity.get("content_index_sha256", "")
            ),
            "manifest_version": str(identity.get("manifest_version", "")),
            "target_root": str(item.target_root.resolve()),
            "source_tree": _tree_identity(item.target_root),
            "candidate_verified": True,
            "candidate_eligible": True,
            "external_action_authorized": False,
        }
        link["self_sha256"] = _self_hash(link)
        return link

    def _classify_prestate_cache(
        self,
        item: Installation,
        identity: dict[str, Any],
        *,
        cache_state: str,
        require_current_state: bool,
    ) -> dict[str, Any]:
        if item.kind == "skill":
            return self._validate_managed_skill_prestate_descriptor(
                item,
                identity,
                cache_state=cache_state,
                require_current_state=require_current_state,
            )
        if identity.get("candidate_eligible") is False:
            return self._validate_legacy_prestate_descriptor(
                item,
                identity,
                cache_state=cache_state,
                require_current_state=require_current_state,
            )
        expected_build = str(identity.get("build_id", ""))
        expected_index = str(identity.get("content_index_sha256", ""))
        version = str(identity.get("manifest_version", ""))
        if not expected_build or not SHA256.fullmatch(expected_index) or not version:
            raise UserUpdateError("strict plugin prestate identity is incomplete")
        cache_root = self._plugin_cache_observation(item, version)["cache_root"]
        return _classify_plugin_cache(
            item.target_root,
            Path(str(cache_root)).resolve(),
            expected_build_id=expected_build,
            expected_content_index_sha256=expected_index,
        )

    def _current_skill_prestate_identity(
        self, item: Installation
    ) -> dict[str, Any]:
        pointer_path = item.target_root / "references" / "installed-suite.json"
        if not pointer_path.is_file():
            try:
                recognition = _recognize_direct_embedded_skill_prestate(
                    item.target_root
                )
                return {
                    "build_id": None,
                    "version": recognition["product_version"],
                    "content_index_sha256": recognition[
                        "content_index_sha256"
                    ],
                    "integrity": "direct-embedded-prestate-recognized",
                    "current_prestate_recognized": True,
                    "candidate_verified": False,
                    "candidate_eligible": False,
                    "legacy_discovery_violation": None,
                    "prestate_binding": {
                        "mode": "direct-embedded-standalone",
                        "embedded_identity": str(
                            (
                                item.target_root
                                / "_paperspine5"
                                / "EMBEDDED-WEB-IDENTITY.json"
                            ).resolve()
                        ),
                        "embedded_identity_sha256": recognition[
                            "embedded_identity_sha256"
                        ],
                        "content_index_sha256": recognition[
                            "content_index_sha256"
                        ],
                        "content_file_count": recognition[
                            "embedded_content_file_count"
                        ],
                        "source_tree": recognition["source_tree"],
                    },
                }
            except (KeyError, OSError, UserUpdateError, ValueError) as exc:
                return {
                    "build_id": None,
                    "version": None,
                    "integrity": "invalid",
                    "current_prestate_recognized": False,
                    "candidate_verified": False,
                    "candidate_eligible": False,
                    "legacy_discovery_violation": {
                        "code": "LEGACY_PRESTATE_UNRECOGNIZED",
                        "message": str(exc),
                    },
                }
        managed_suite: dict[str, Any] | None = None
        try:
            pointer = _read_json(pointer_path)
            if (
                pointer.get("contract")
                != "paperspine5.installed-suite-pointer"
                or pointer.get("schema_version") != "1.0"
                or pointer.get("product_id") != PRODUCT_ID
            ):
                raise UserUpdateError("managed Skill pointer contract is unsupported")
            build_id = str(pointer.get("build_id", ""))
            content_index = str(pointer.get("content_index_sha256", ""))
            suite_root = Path(str(pointer.get("suite_root", ""))).resolve()
            if not SAFE_ID.fullmatch(build_id) or not SHA256.fullmatch(content_index):
                raise UserUpdateError("managed Skill pointer identity is incomplete")
            managed_suite = _classify_managed_skill_suite(
                suite_root,
                expected_build_id=build_id,
                expected_content_index_sha256=content_index,
            )
            if managed_suite.get("classification") in {"clean", "runtime-residue"}:
                verification = managed_suite["verification"]
                identity = {
                    "build_id": build_id,
                    "version": verification["product_version"],
                    "content_index_sha256": content_index,
                    "integrity": managed_suite["integrity"],
                    "suite_root": str(suite_root),
                    "current_prestate_recognized": True,
                    "candidate_verified": managed_suite.get(
                        "candidate_verified"
                    )
                    is True,
                    "candidate_eligible": True,
                    "legacy_discovery_violation": None,
                    "managed_suite": managed_suite,
                    "cache": managed_suite,
                    "prestate_blocker_code": None,
                    "prestate_binding": {
                        "installed_suite_pointer": str(pointer_path.resolve()),
                        "build_id": build_id,
                        "content_index_sha256": content_index,
                    },
                }
                identity["prestate_validation"] = (
                    self._managed_skill_prestate_validation_descriptor(
                        item,
                        suite_root=suite_root,
                        build_id=build_id,
                        content_index_sha256=content_index,
                        managed_suite=managed_suite,
                    )
                )
                return identity

            # Retain the narrow historical two-Skill recognizer when there are
            # no unclassified extra bytes.  It never becomes candidate-eligible.
            recognition = _recognize_legacy_installed_prestate(
                suite_root,
                expected_build_id=build_id,
                expected_content_index_sha256=content_index,
            )
            return {
                "build_id": recognition["build_id"],
                "version": recognition["product_version"],
                "content_index_sha256": recognition["content_index_sha256"],
                "integrity": "legacy-prestate-recognized",
                "suite_root": str(suite_root),
                "current_prestate_recognized": True,
                "candidate_verified": False,
                "candidate_eligible": False,
                "legacy_discovery_violation": recognition[
                    "legacy_discovery_violation"
                ],
                "prestate_binding": {
                    "installed_suite_pointer": str(pointer_path.resolve()),
                    "build_id": build_id,
                    "content_index_sha256": content_index,
                },
            }
        except (KeyError, OSError, ReleaseError, UserUpdateError, ValueError) as exc:
            blocker_code = (
                managed_suite.get("blocker_code")
                if isinstance(managed_suite, dict)
                else "SKILL_MANAGED_SUITE_FOREIGN_DRIFT"
            )
            return {
                "build_id": None,
                "version": None,
                "integrity": "invalid",
                "current_prestate_recognized": False,
                "candidate_verified": False,
                "candidate_eligible": False,
                "managed_suite": managed_suite,
                "cache": managed_suite,
                "prestate_blocker_code": blocker_code,
                "legacy_discovery_violation": {
                    "code": "LEGACY_PRESTATE_UNRECOGNIZED",
                    "message": str(exc),
                },
            }

    def _current_prestate_identity(self, item: Installation) -> dict[str, Any]:
        if item.kind == "skill":
            return self._current_skill_prestate_identity(item)
        strict = _installed_identity(item)
        if strict.get("integrity") == "verified":
            if item.kind == "plugin":
                version = strict.get("manifest_version")
                if not isinstance(version, str) or not version:
                    return {
                        **strict,
                        "integrity": "invalid",
                        "current_prestate_recognized": False,
                        "candidate_eligible": False,
                        "cache": {
                            "classification": "foreign-drift",
                            "blocker_code": "PLUGIN_CACHE_FOREIGN_DRIFT",
                        },
                    }
                observed = self._observe_plugin(
                    "recognize_current_prestate",
                    item,
                    version,
                    expected_build_id=str(strict["build_id"]),
                    expected_content_index_sha256=str(
                        strict["content_index_sha256"]
                    ),
                )
                cache = dict(observed["cache"])
                classification = cache.get("classification")
                recognized = bool(
                    observed.get("identity_matches")
                    and classification in {"clean", "runtime-residue"}
                )
                return {
                    **strict,
                    "integrity": cache.get("integrity", "invalid"),
                    "current_prestate_recognized": recognized,
                    "candidate_eligible": recognized,
                    "cache": cache,
                    "active_plugin": {
                        "status": observed.get("status"),
                        "identity_matches": observed.get("identity_matches"),
                        "observed": observed.get("observed"),
                    },
                    "prestate_blocker_code": (
                        None
                        if recognized
                        else cache.get("blocker_code")
                        or "PLUGIN_ACTIVE_IDENTITY_DRIFT"
                    ),
                }
            return strict
        try:
            if item.kind == "plugin":
                recorded = self._recorded_active_identity(item)
                version = _plugin_manifest_version(item.target_root)
                if version is None or not version.endswith(
                    f"+codex.{recorded['build_id']}"
                ):
                    raise UserUpdateError(
                        "legacy plugin manifest does not match recorded active build"
                    )
                observed = self._observe_plugin(
                    "recognize_legacy_prestate",
                    item,
                    version,
                )
                observed_source = (observed.get("observed") or {}).get("source") or {}
                source_path = observed_source.get("path")
                if (
                    observed.get("status") != "passed"
                    or observed_source.get("source") != "local"
                    or not isinstance(source_path, str)
                    or Path(source_path).resolve() != item.target_root.resolve()
                ):
                    raise UserUpdateError(
                        "legacy plugin prestate is not the exact active CLI installation"
                    )
                source_recognition = _recognize_legacy_installed_prestate(
                    item.target_root,
                    expected_build_id=recorded["build_id"],
                    expected_content_index_sha256=recorded[
                        "content_index_sha256"
                    ],
                )
                cache_root = Path(observed["cache"]["cache_root"]).resolve()
                cache = _classify_legacy_installed_prestate_cache(
                    item.target_root,
                    cache_root,
                    expected_build_id=recorded["build_id"],
                    expected_content_index_sha256=recorded[
                        "content_index_sha256"
                    ],
                )
                if cache.get("classification") not in {
                    "clean",
                    "runtime-residue",
                }:
                    raise UserUpdateError(
                        "legacy plugin cache is not an exact recorded prestate: "
                        f"{cache.get('blocker_code')}"
                    )
                descriptor = self._legacy_prestate_validation_descriptor(
                    item,
                    recorded=recorded,
                    version=version,
                    observed=observed,
                    source_recognition=source_recognition,
                    cache=cache,
                )
                return {
                    "build_id": source_recognition["build_id"],
                    "version": source_recognition["product_version"],
                    "manifest_version": version,
                    "content_index_sha256": source_recognition[
                        "content_index_sha256"
                    ],
                    "integrity": (
                        "legacy-prestate-recognized-with-runtime-residue"
                        if cache.get("classification") == "runtime-residue"
                        else "legacy-prestate-recognized"
                    ),
                    "current_prestate_recognized": True,
                    "candidate_verified": False,
                    "candidate_eligible": False,
                    "legacy_discovery_violation": source_recognition[
                        "legacy_discovery_violation"
                    ],
                    "cache": cache,
                    "active_plugin": {
                        "status": observed.get("status"),
                        "identity_matches": observed.get("identity_matches"),
                        "observed": observed.get("observed"),
                    },
                    "prestate_validation": descriptor,
                    "prestate_binding": {
                        "state": recorded,
                        "cli_version": version,
                        "source_tree": descriptor["source_tree"],
                        "cache_tree": descriptor["initial_cache_tree"],
                        "cache_classification": cache["classification"],
                        "cache_recognition": cache["legacy_recognition"]["status"],
                    },
                }

            pointer_path = item.target_root / "references" / "installed-suite.json"
            if not pointer_path.is_file():
                recognition = _recognize_direct_embedded_skill_prestate(
                    item.target_root
                )
                return {
                    "build_id": None,
                    "version": recognition["product_version"],
                    "content_index_sha256": recognition[
                        "content_index_sha256"
                    ],
                    "integrity": "direct-embedded-prestate-recognized",
                    "current_prestate_recognized": True,
                    "candidate_verified": False,
                    "candidate_eligible": False,
                    "legacy_discovery_violation": None,
                    "prestate_binding": {
                        "mode": "direct-embedded-standalone",
                        "embedded_identity": str(
                            (
                                item.target_root
                                / "_paperspine5"
                                / "EMBEDDED-WEB-IDENTITY.json"
                            ).resolve()
                        ),
                        "embedded_identity_sha256": recognition[
                            "embedded_identity_sha256"
                        ],
                        "content_index_sha256": recognition[
                            "content_index_sha256"
                        ],
                        "content_file_count": recognition[
                            "embedded_content_file_count"
                        ],
                        "source_tree": recognition["source_tree"],
                    },
                }
            pointer = _read_json(pointer_path)
            if (
                pointer.get("contract")
                != "paperspine5.installed-suite-pointer"
                or pointer.get("product_id") != PRODUCT_ID
            ):
                raise UserUpdateError("legacy Skill pointer contract is unsupported")
            build_id = str(pointer.get("build_id", ""))
            content_index = str(pointer.get("content_index_sha256", ""))
            suite_root = Path(str(pointer.get("suite_root", ""))).resolve()
            if not SAFE_ID.fullmatch(build_id) or not SHA256.fullmatch(content_index):
                raise UserUpdateError("legacy Skill pointer identity is incomplete")
            recognition = _recognize_legacy_installed_prestate(
                suite_root,
                expected_build_id=build_id,
                expected_content_index_sha256=content_index,
            )
            return {
                "build_id": recognition["build_id"],
                "version": recognition["product_version"],
                "content_index_sha256": recognition["content_index_sha256"],
                "integrity": "legacy-prestate-recognized",
                "suite_root": str(suite_root),
                "current_prestate_recognized": True,
                "candidate_verified": False,
                "candidate_eligible": False,
                "legacy_discovery_violation": recognition[
                    "legacy_discovery_violation"
                ],
                "prestate_binding": {
                    "installed_suite_pointer": str(pointer_path.resolve()),
                    "build_id": build_id,
                    "content_index_sha256": content_index,
                },
            }
        except (KeyError, OSError, ReleaseError, UserUpdateError, ValueError) as exc:
            return {
                **strict,
                "current_prestate_recognized": False,
                "candidate_verified": False,
                "candidate_eligible": False,
                "legacy_discovery_violation": {
                    "code": "LEGACY_PRESTATE_UNRECOGNIZED",
                    "message": str(exc),
                },
            }

    def _plugin_command(
        self,
        phase: str,
        item: Installation,
        action: str,
    ) -> dict[str, Any]:
        selector = self._plugin_selector(item)
        if action == "list":
            command = [
                self.codex_command,
                "plugin",
                "list",
                "--marketplace",
                str(item.marketplace_name),
                "--json",
            ]
        elif action in {"add", "remove"}:
            command = [
                self.codex_command,
                "plugin",
                action,
                selector,
                "--json",
            ]
        else:  # pragma: no cover - internal construction only.
            raise UserUpdateError(f"unsupported plugin action: {action}")
        return _command_phase_record(phase, command, self.command_runner(command))

    def _plugin_cache_observation(
        self,
        item: Installation,
        expected_version: str,
        *,
        expected_build_id: str | None = None,
        expected_content_index_sha256: str | None = None,
    ) -> dict[str, Any]:
        if (
            not expected_version
            or Path(expected_version).name != expected_version
            or any(separator in expected_version for separator in ("/", "\\"))
        ):
            raise UserUpdateError("plugin version cannot identify a cache directory")
        cache_parent = (
            self.codex_home
            / "plugins"
            / "cache"
            / str(item.marketplace_name)
            / PLUGIN_NAME
        ).resolve()
        cache_root = cache_parent / expected_version
        try:
            cache_root.absolute().relative_to(cache_parent)
        except ValueError as exc:  # pragma: no cover - guarded by the version check.
            raise UserUpdateError("plugin cache path escaped its product cache root") from exc
        observed_version = _plugin_manifest_version(cache_root) if cache_root.is_dir() else None
        observation: dict[str, Any] = {
            "cache_root": str(cache_root),
            "exists": cache_root.is_dir(),
            "manifest_version": observed_version,
            "expected_version": expected_version,
            "manifest_matches": observed_version == expected_version,
            "build_id": None,
            "content_index_sha256": None,
            "exact_suite_matches": expected_build_id is None,
            "classification": "unchecked",
            "integrity": "unverified",
            "blocker_code": None,
            "runtime_residue": [],
        }
        if expected_build_id is not None and cache_root.is_dir():
            try:
                classification = _classify_plugin_cache(
                    item.target_root,
                    cache_root,
                    expected_build_id=expected_build_id,
                    expected_content_index_sha256=str(
                        expected_content_index_sha256
                    ),
                )
            except (OSError, ReleaseError, UserUpdateError) as exc:
                classification = {
                    "classification": "foreign-drift",
                    "integrity": "invalid",
                    "blocker_code": "PLUGIN_CACHE_FOREIGN_DRIFT",
                    "indexed_bytes_exact": False,
                    "runtime_residue": [],
                    "foreign_entries": [
                        {"path": str(cache_root), "reason": str(exc)}
                    ],
                }
            observation.update(classification)
            if classification.get("indexed_bytes_exact"):
                observation["build_id"] = expected_build_id
                observation["content_index_sha256"] = (
                    expected_content_index_sha256
                )
            observation["exact_suite_matches"] = (
                classification.get("classification") == "clean"
            )
        elif expected_build_id is not None:
            observation.update(
                {
                    "classification": "missing",
                    "integrity": "invalid",
                    "blocker_code": "PLUGIN_CACHE_MISSING",
                    "indexed_bytes_exact": False,
                }
            )
        else:
            observation["classification"] = (
                "unverified-present" if cache_root.is_dir() else "missing"
            )
        observation["matches"] = bool(
            observation["manifest_matches"] and observation["exact_suite_matches"]
        )
        return observation

    def _observe_plugin(
        self,
        phase: str,
        item: Installation,
        expected_version: str,
        *,
        expected_build_id: str | None = None,
        expected_content_index_sha256: str | None = None,
    ) -> dict[str, Any]:
        record = self._plugin_command(phase, item, "list")
        selector = self._plugin_selector(item)
        observed = _installed_plugin_from_list(record.get("result_json"), selector)
        record["expected"] = {
            "plugin_id": selector,
            "version": expected_version,
            "installed": True,
            "enabled": True,
            "source": {"source": "local", "path": str(item.target_root)},
        }
        record["observed"] = observed
        observed_source = (
            observed.get("source") if isinstance(observed, dict) else None
        )
        source_matches = bool(
            isinstance(observed_source, dict)
            and observed_source.get("source") == "local"
            and isinstance(observed_source.get("path"), str)
            and Path(str(observed_source["path"])).resolve()
            == item.target_root.resolve()
        )
        record["source_matches"] = source_matches
        record["identity_matches"] = bool(
            record["returncode"] == 0
            and record.get("json_parse_error") is None
            and observed is not None
            and observed.get("version") == expected_version
            and observed.get("installed") is True
            and observed.get("enabled") is True
            and source_matches
        )
        record["cache"] = self._plugin_cache_observation(
            item,
            expected_version,
            expected_build_id=expected_build_id,
            expected_content_index_sha256=expected_content_index_sha256,
        )
        if (
            record["identity_matches"]
            and record["cache"].get("classification") == "runtime-residue"
        ):
            record["status"] = "warning"
            record["warning"] = (
                "active cache contains only hash-bound runtime bytecode residue"
            )
        else:
            record["status"] = (
                "passed"
                if record["identity_matches"] and record["cache"]["matches"]
                else "failed"
            )
        return record

    def _observe_plugin_prestate(
        self,
        phase: str,
        item: Installation,
        identity: dict[str, Any],
        *,
        cache_state: str,
        require_current_state: bool,
    ) -> dict[str, Any]:
        """Observe only a prestate carrying its internally derived validation mode."""

        version = str(identity.get("manifest_version", ""))
        if identity.get("candidate_eligible") is not False:
            return self._observe_plugin(
                phase,
                item,
                version,
                expected_build_id=str(identity.get("build_id", "")),
                expected_content_index_sha256=str(
                    identity.get("content_index_sha256", "")
                ),
            )

        record = self._observe_plugin(phase, item, version)
        observed_record = record.get("observed")
        observed = observed_record or {}
        observed_source = observed.get("source") or {}
        descriptor = identity.get("prestate_validation") or {}
        cli_binding = {
            "plugin_id": self._plugin_selector(item),
            "version": observed.get("version"),
            "installed": observed.get("installed"),
            "enabled": observed.get("enabled"),
            "source": {
                "source": observed_source.get("source"),
                "path": (
                    str(Path(str(observed_source.get("path", ""))).resolve())
                    if observed_source.get("path")
                    else ""
                ),
            },
        }
        try:
            cache = self._classify_prestate_cache(
                item,
                identity,
                cache_state=cache_state,
                require_current_state=require_current_state,
            )
        except UserUpdateError as exc:
            raw_cache = record.get("cache") or {}
            if (
                observed_record is None
                and raw_cache.get("classification") == "missing"
            ):
                record["prestate_validation"] = self._prestate_validation_link(
                    item, identity
                )
                record["prestate_validation_mode"] = "recorded-legacy-installed"
                record["prestate_validation_error"] = str(exc)
                record["identity_matches"] = False
                record["status"] = "failed"
                return record
            raise
        record["cache"] = cache
        record["prestate_validation"] = self._prestate_validation_link(item, identity)
        record["prestate_validation_mode"] = "recorded-legacy-installed"
        record["identity_matches"] = bool(
            record.get("identity_matches")
            and cli_binding == descriptor.get("cli_binding")
        )
        classification = cache.get("classification")
        if record["identity_matches"] and classification == "runtime-residue":
            record["status"] = "warning"
            record["warning"] = (
                "active legacy prestate cache contains only hash-bound runtime "
                "bytecode residue"
            )
        else:
            record["status"] = (
                "passed"
                if record["identity_matches"] and classification == "clean"
                else "failed"
            )
        return record

    def _observe_plugin_absent(
        self, phase: str, item: Installation
    ) -> dict[str, Any]:
        record = self._plugin_command(phase, item, "list")
        selector = self._plugin_selector(item)
        observed = _installed_plugin_from_list(record.get("result_json"), selector)
        record["expected"] = {"plugin_id": selector, "installed": False}
        record["observed"] = observed
        record["identity_matches"] = bool(
            record["returncode"] == 0
            and record.get("json_parse_error") is None
            and observed is None
        )
        record["status"] = "passed" if record["identity_matches"] else "failed"
        return record

    def _write_activation_journal(self, journal: dict[str, Any]) -> Path:
        path = self.transactions / f"{journal['operation_id']}.json"
        journal["updated_at"] = _now()
        _write_atomic(path, journal)
        return path

    def _activation_journal_link(
        self, journal: dict[str, Any], path: Path
    ) -> dict[str, Any]:
        return {
            "contract": journal["contract"],
            "schema_version": journal["schema_version"],
            "operation_id": journal["operation_id"],
            "status": journal["status"],
            "journal_path": str(path.resolve()),
            "journal_sha256": sha256_file(path),
            "phase_count": len(journal.get("phases", [])),
        }

    def _migrate_discovery_conflicts(
        self, operation_id: str
    ) -> tuple[dict[str, Any], Path]:
        module = _load_discovery_migration()
        migration_id = _discovery_operation_id(
            self.install_kind, operation_id, "discovery-migrate"
        )
        receipt = module.migrate_discovery_conflicts(
            self._discovery_roots(),
            self.discovery_archive,
            operation_id=migration_id,
        )
        receipt_path = self.discovery_archive / "receipts" / f"{migration_id}.json"
        if receipt.get("status") not in {"committed", "noop"}:
            raise UserUpdateError(
                f"Skill discovery migration failed: {receipt.get('blockers')}"
            )
        return receipt, receipt_path

    def _restore_discovery_conflicts(
        self,
        migration_receipt_path: Path,
        operation_id: str,
        *,
        phase: str,
    ) -> tuple[dict[str, Any], Path]:
        module = _load_discovery_migration()
        restore_id = _discovery_operation_id(self.install_kind, operation_id, phase)
        receipt = module.restore_discovery_migration(
            migration_receipt_path,
            operation_id=restore_id,
        )
        receipt_path = self.discovery_archive / "receipts" / f"{restore_id}.json"
        if receipt.get("status") != "committed":
            raise UserUpdateError(
                f"Skill discovery restore failed: {receipt.get('blockers')}"
            )
        return receipt, receipt_path

    def _state(self) -> dict[str, Any]:
        contract = f"paperspine5.{self.install_kind}-update-state"
        if not self.state_path.is_file():
            return {
                "contract": contract,
                "schema_version": USER_UPDATE_STATE_SCHEMA_VERSION,
                "product_id": PRODUCT_ID,
                "install_kind": self.install_kind,
                "active_installations": [],
                "history": [],
            }
        payload = _read_json(self.state_path)
        if (
            payload.get("contract") != contract
            or payload.get("schema_version") != USER_UPDATE_STATE_SCHEMA_VERSION
            or payload.get("product_id") != PRODUCT_ID
            or payload.get("install_kind") != self.install_kind
        ):
            raise UserUpdateError(
                "surface update state contract/version/product/install-kind is unsupported"
            )
        return payload

    def _receipt_path(self, operation_id: str) -> Path:
        return self.receipts / f"{_safe_id(operation_id, 'operation_id')}.json"

    def _replay(self, operation_id: str, request_sha: str) -> dict[str, Any] | None:
        path = self._receipt_path(operation_id)
        if not path.is_file():
            return None
        receipt = _read_json(path)
        if receipt.get("request_sha256") != request_sha:
            raise UserUpdateError("operation_id was already used for a different user update request")
        return {**receipt, "replayed": True}

    def _save_receipt(self, receipt: dict[str, Any]) -> dict[str, Any]:
        _write_atomic(self._receipt_path(receipt["operation_id"]), receipt)
        return receipt

    def _base_receipt(
        self,
        operation: str,
        operation_id: str,
        request_sha: str,
        *,
        status: str,
        candidate: dict[str, Any] | None,
        installations: Iterable[Installation],
    ) -> dict[str, Any]:
        return {
            "contract": f"paperspine5.{self.install_kind}-update-receipt",
            "schema_version": USER_UPDATE_RECEIPT_SCHEMA_VERSION,
            "install_kind": self.install_kind,
            "operation": operation,
            "operation_id": operation_id,
            "request_sha256": request_sha,
            "status": status,
            "created_at": _now(),
            "candidate_build_id": candidate.get("build_id") if candidate else None,
            "installations": [
                {"kind": item.kind, "target_root": str(item.target_root)} for item in installations
            ],
            "blockers": [],
            "warnings": [],
            "rollback_performed": False,
            "requested_target_applied": False,
            "compensation_performed": False,
            "current_installation_restored": False,
            "retryable": False,
            "requires_new_session": False,
            "external_action_authorized": False,
        }

    def check(
        self,
        source: str | Path,
        *,
        marketplace_path: str | Path | None = None,
        skill_root: str | Path | None = None,
    ) -> dict[str, Any]:
        bundle, candidate, cleanup = resolve_candidate(
            source, install_kind=self.install_kind
        )
        del bundle
        try:
            installations, blockers = detect_installations(
                self.install_kind,
                marketplace_path=marketplace_path,
                skill_root=skill_root,
                home=self.home,
            )
            items = []
            warnings: list[dict[str, Any]] = []
            for item in installations:
                current = self._current_prestate_identity(item)
                items.append(
                    {
                        "kind": item.kind,
                        "target_root": str(item.target_root),
                        "current": current,
                        "candidate_build_id": candidate["build_id"],
                        "update_available": (
                            current.get("build_id") != candidate["build_id"]
                            or current.get("candidate_eligible") is False
                        ),
                    }
                )
                if current.get("current_prestate_recognized") is not True:
                    specific = current.get("prestate_blocker_code")
                    if isinstance(specific, str) and specific:
                        blockers.append(
                            {
                                "code": specific,
                                "kind": item.kind,
                                "target_root": str(item.target_root),
                                "cache": current.get("cache"),
                            }
                        )
                    blockers.append(
                        {
                            "code": "CURRENT_PRESTATE_UNRECOGNIZED",
                            "kind": item.kind,
                            "target_root": str(item.target_root),
                        }
                    )
                elif (
                    item.kind == "plugin"
                    and (current.get("cache") or {}).get("classification")
                    == "runtime-residue"
                ):
                    warnings.append(
                        {
                            "code": "PLUGIN_CACHE_RUNTIME_RESIDUE",
                            "kind": "plugin",
                            "target_root": str(item.target_root),
                            "cache_root": (current.get("cache") or {}).get(
                                "cache_root"
                            ),
                            "file_count": len(
                                (current.get("cache") or {}).get(
                                    "runtime_residue", []
                                )
                            ),
                            **_runtime_residue_summary(
                                (current.get("cache") or {}).get(
                                    "runtime_residue", []
                                )
                            ),
                        }
                    )
                elif (
                    item.kind == "skill"
                    and (current.get("managed_suite") or {}).get(
                        "classification"
                    )
                    == "runtime-residue"
                ):
                    summary = (current.get("managed_suite") or {}).get(
                        "runtime_residue_summary", {}
                    )
                    warnings.append(
                        {
                            "code": "SKILL_MANAGED_SUITE_RUNTIME_RESIDUE",
                            "kind": "skill",
                            "target_root": str(item.target_root),
                            "suite_root": current.get("suite_root"),
                            "file_count": summary.get("file_count"),
                            "total_bytes": summary.get("total_bytes"),
                            "path_digest_sha256": summary.get(
                                "path_digest_sha256"
                            ),
                        }
                    )
            if not installations:
                blockers.append(
                    {"code": "INSTALLATION_NOT_FOUND", "install_kind": self.install_kind}
                )
            return {
                "contract": f"paperspine5.{self.install_kind}-update-check",
                "schema_version": "1.0",
                "install_kind": self.install_kind,
                "status": "PASS" if not blockers else "BLOCKED",
                "candidate": {
                    "product_version": candidate["product_version"],
                    "channel": candidate["channel"],
                    "build_id": candidate["build_id"],
                    "content_index_sha256": candidate["content_index_sha256"],
                    "candidate_verified": True,
                },
                "installations": items,
                "update_available": any(item["update_available"] for item in items),
                "blockers": blockers,
                "warnings": warnings,
                "requires_confirmation": any(item["update_available"] for item in items),
                "external_action_authorized": False,
            }
        finally:
            cleanup()

    def upgrade(
        self,
        source: str | Path,
        *,
        operation_id: str,
        confirmed: bool,
        marketplace_path: str | Path | None = None,
        skill_root: str | Path | None = None,
        fault_at: str | None = None,
    ) -> dict[str, Any]:
        operation_id = _safe_id(operation_id, "operation_id")
        request = {
            "operation": "upgrade",
            "operation_id": operation_id,
            "source": str(source),
            "install_kind": self.install_kind,
            "marketplace_path": str(marketplace_path) if marketplace_path else None,
            "skill_root": str(skill_root) if skill_root else None,
            "confirmed": confirmed,
        }
        request_sha = _request_hash(request)
        replay = self._replay(operation_id, request_sha)
        if replay is not None:
            return replay
        bundle, candidate, cleanup = resolve_candidate(
            source, install_kind=self.install_kind
        )
        installations: list[Installation] = []
        placements: list[dict[str, Any]] = []
        activation_results: list[dict[str, Any]] = []
        activation_phases: list[dict[str, Any]] = []
        activation_journal: dict[str, Any] | None = None
        activation_journal_path: Path | None = None
        plugin_item: Installation | None = None
        previous_plugin_version: str | None = None
        candidate_plugin_version: str | None = None
        preflight_plugin_cache: dict[str, Any] | None = None
        preflight_runtime_residue: dict[str, Any] | None = None
        cache_reconciliation: dict[str, Any] | None = None
        cache_reconciliation_restore: dict[str, Any] | None = None
        previous_plugin_identity: dict[str, Any] | None = None
        previous_residue_identity: dict[str, Any] | None = None
        residue_item: Installation | None = None
        deactivation_attempted = False
        deactivation_succeeded = False
        candidate_activation_attempted = False
        discovery_migration: dict[str, Any] | None = None
        discovery_migration_path: Path | None = None
        discovery_restore: dict[str, Any] | None = None
        transaction_root = self.staging / operation_id
        try:
            installations, blockers = detect_installations(
                self.install_kind,
                marketplace_path=marketplace_path,
                skill_root=skill_root,
                home=self.home,
            )
            receipt = self._base_receipt(
                "upgrade", operation_id, request_sha, status="blocked", candidate=candidate, installations=installations
            )
            if blockers:
                receipt["blockers"] = blockers
                return self._save_receipt(receipt)
            if not installations:
                receipt["blockers"] = [
                    {"code": "INSTALLATION_NOT_FOUND", "install_kind": self.install_kind}
                ]
                return self._save_receipt(receipt)
            if not confirmed:
                receipt["blockers"] = [{"code": "USER_CONFIRMATION_REQUIRED"}]
                return self._save_receipt(receipt)
            current_items = [
                {
                    "installation": item,
                    "identity": self._current_prestate_identity(item),
                }
                for item in installations
            ]
            unrecognized = [
                item
                for item in current_items
                if item["identity"].get("current_prestate_recognized") is not True
            ]
            if unrecognized:
                prestate_blockers: list[dict[str, Any]] = []
                for current in unrecognized:
                    identity = current["identity"]
                    item = current["installation"]
                    specific = identity.get("prestate_blocker_code")
                    if isinstance(specific, str) and specific:
                        prestate_blockers.append(
                            {
                                "code": specific,
                                "kind": item.kind,
                                "target_root": str(item.target_root),
                                "cache": identity.get("cache"),
                            }
                        )
                    prestate_blockers.append(
                        {
                            "code": "CURRENT_PRESTATE_UNRECOGNIZED",
                            "kind": item.kind,
                            "target_root": str(item.target_root),
                        }
                    )
                receipt["blockers"] = prestate_blockers
                return self._save_receipt(receipt)
            if all(
                item["identity"].get("build_id") == candidate["build_id"]
                and item["identity"].get("candidate_eligible") is not False
                for item in current_items
            ):
                receipt["status"] = "noop"
                receipt["requested_target_applied"] = True
                receipt["warnings"] = [{"code": "ALREADY_CURRENT", "build_id": candidate["build_id"]}]
                return self._save_receipt(receipt)

            self.control_root.mkdir(parents=True, exist_ok=True)
            if transaction_root.exists():
                raise UserUpdateError(f"transaction staging already exists: {transaction_root}")
            extracted = transaction_root / "bundle"
            extract_verified_bundle(bundle, extracted)

            def record_activation_phase(phase_record: dict[str, Any]) -> None:
                nonlocal activation_journal_path
                activation_phases.append(phase_record)
                if activation_journal is not None:
                    activation_journal["phases"] = activation_phases
                    activation_journal_path = self._write_activation_journal(
                        activation_journal
                    )

            plugin_installations = [
                item for item in installations if item.kind == "plugin"
            ]
            if plugin_installations:
                if len(plugin_installations) != 1:
                    raise UserUpdateError("plugin update must resolve exactly one installation")
                plugin_item = plugin_installations[0]
                previous_plugin_version = _plugin_manifest_version(
                    plugin_item.target_root
                )
                candidate_plugin_version = _plugin_manifest_version(extracted)
                if previous_plugin_version is None or candidate_plugin_version is None:
                    raise UserUpdateError("plugin source/candidate version is unreadable")
                previous_plugin_identity = next(
                    current["identity"]
                    for current in current_items
                    if current["installation"] is plugin_item
                )
                activation_journal = {
                    "contract": PLUGIN_ACTIVATION_JOURNAL_CONTRACT,
                    "schema_version": PLUGIN_ACTIVATION_JOURNAL_SCHEMA_VERSION,
                    "operation_id": operation_id,
                    "install_kind": "plugin",
                    "status": "in_progress",
                    "created_at": _now(),
                    "updated_at": _now(),
                    "selector": self._plugin_selector(plugin_item),
                    "target_root": str(plugin_item.target_root),
                    "previous_version": previous_plugin_version,
                    "candidate_version": candidate_plugin_version,
                    "candidate_build_id": candidate["build_id"],
                    "phases": activation_phases,
                    "external_action_authorized": False,
                }
                preflight = self._observe_plugin_prestate(
                    "preflight_identity",
                    plugin_item,
                    previous_plugin_identity,
                    cache_state="initial",
                    require_current_state=True,
                )
                preflight_plugin_cache = dict(preflight["cache"])
                preflight_runtime_residue = preflight_plugin_cache
                previous_residue_identity = previous_plugin_identity
                residue_item = plugin_item
                record_activation_phase(preflight)
                if not preflight["identity_matches"]:
                    raise UserUpdateError("Codex plugin preflight identity does not match the current source")
                if preflight["cache"].get("classification") == "runtime-residue":
                    cache_reconciliation = self._archive_plugin_cache_residue(
                        operation_id,
                        plugin_item,
                        preflight["cache"],
                        prestate_identity=previous_plugin_identity,
                        fault_at=fault_at,
                    )
                    receipt["cache_reconciliation"] = cache_reconciliation
                    record_activation_phase(
                        {
                            **cache_reconciliation,
                            "phase": "reconcile_runtime_bytecode_residue",
                            "kind": "filesystem",
                            "status": "passed",
                            "recorded_at": _now(),
                        }
                    )
                    strict_preflight = self._observe_plugin_prestate(
                        "verify_strict_cache_before_deactivate",
                        plugin_item,
                        previous_plugin_identity,
                        cache_state="reconciled",
                        require_current_state=True,
                    )
                    record_activation_phase(strict_preflight)
                    if strict_preflight["status"] != "passed":
                        raise UserUpdateError(
                            "plugin cache is not strict after runtime residue reconciliation"
                        )
                elif preflight["status"] != "passed":
                    raise UserUpdateError(
                        "Codex plugin cache contains missing, changed, or foreign bytes"
                    )

            skill_residue_items = [
                current
                for current in current_items
                if current["installation"].kind == "skill"
                and (current["identity"].get("managed_suite") or {}).get(
                    "classification"
                )
                == "runtime-residue"
            ]
            if skill_residue_items:
                if len(skill_residue_items) != 1 or residue_item is not None:
                    raise UserUpdateError(
                        "runtime residue update must resolve exactly one installation"
                    )
                selected_skill = skill_residue_items[0]
                residue_item = selected_skill["installation"]
                previous_residue_identity = selected_skill["identity"]
                preflight_runtime_residue = dict(
                    previous_residue_identity["managed_suite"]
                )
                cache_reconciliation = self._archive_plugin_cache_residue(
                    operation_id,
                    residue_item,
                    preflight_runtime_residue,
                    prestate_identity=previous_residue_identity,
                    fault_at=fault_at,
                )
                receipt["cache_reconciliation"] = cache_reconciliation

            discovery_receipt, discovery_migration_path = self._migrate_discovery_conflicts(
                operation_id
            )
            discovery_migration = _discovery_link(
                discovery_receipt, discovery_migration_path
            )
            receipt["discovery_migration"] = discovery_migration
            if fault_at == "after_discovery_migration":
                raise OSError("injected failure after Skill discovery migration")

            if plugin_item is not None:
                deactivation_attempted = True
                deactivated = self._plugin_command(
                    "deactivate_previous", plugin_item, "remove"
                )
                record_activation_phase(deactivated)
                if deactivated["status"] != "passed":
                    raise UserUpdateError("Codex plugin deactivation failed")
                deactivation_succeeded = True
                absent = self._observe_plugin_absent(
                    "verify_previous_deactivated", plugin_item
                )
                record_activation_phase(absent)
                if absent["status"] != "passed":
                    raise UserUpdateError("Codex plugin remained active after remove")

            managed_install = self.installs / candidate["build_id"]
            if any(item.kind == "skill" for item in installations):
                if managed_install.exists():
                    installed_candidate = verify_bundle(managed_install)
                    if (
                        installed_candidate.get("build_id")
                        != candidate["build_id"]
                        or installed_candidate.get("content_index_sha256")
                        != candidate["content_index_sha256"]
                    ):
                        raise UserUpdateError(
                            "existing managed Skill candidate identity drifted"
                        )
                else:
                    managed_stage = self.installs / f".{candidate['build_id']}.{operation_id}.stage"
                    self.installs.mkdir(parents=True, exist_ok=True)
                    _copytree(extracted, managed_stage)
                    verify_bundle(managed_stage)
                    os.replace(managed_stage, managed_install)

            for current in current_items:
                item = current["installation"]
                target = item.target_root
                target.parent.mkdir(parents=True, exist_ok=True)
                stage_digest = hashlib.sha256(str(target).encode("utf-8")).hexdigest()[:20]
                stage = transaction_root / "placements" / stage_digest
                if item.kind == "plugin":
                    _copytree(extracted, stage)
                    verify_bundle(stage)
                else:
                    projection = extracted / "standalone" / STANDALONE_SKILL_NAME
                    if not (projection / "SKILL.md").is_file():
                        raise UserUpdateError("candidate does not contain the standalone Skill projection")
                    _copytree(projection, stage)
                    _write_atomic(
                        stage / "references" / "installed-suite.json",
                        {
                            "contract": "paperspine5.installed-suite-pointer",
                            "schema_version": "1.0",
                            "product_id": PRODUCT_ID,
                            "build_id": candidate["build_id"],
                            "content_index_sha256": candidate["content_index_sha256"],
                            "suite_root": str(managed_install.resolve()),
                        },
                    )
                backup_directory = _backup_root(self.control_root, target)
                backup_directory.mkdir(parents=True, exist_ok=True)
                previous_id = current["identity"].get("build_id") or "unverified"
                backup = backup_directory / f"{target.name}-{previous_id}-{operation_id}"
                if backup.exists():
                    raise UserUpdateError(f"backup path already exists: {backup}")
                previous_tree = _tree_identity(target) if target.is_dir() else None
                candidate_tree = _tree_identity(stage)
                placement_record = {
                    "kind": item.kind,
                    "target_root": str(target),
                    "backup_root": None,
                    "previous": current["identity"],
                    "previous_tree": previous_tree,
                    "candidate_tree": candidate_tree,
                    "marketplace_name": item.marketplace_name,
                    "cache_reconciliation": (
                        cache_reconciliation if item is residue_item else None
                    ),
                    "previous_moved": False,
                    "candidate_placed": False,
                }
                if target.exists():
                    os.replace(target, backup)
                    placement_record["backup_root"] = str(backup)
                    placement_record["previous_moved"] = True
                placements.append(placement_record)
                os.replace(stage, target)
                placement_record["candidate_placed"] = True
                if item.kind == "plugin":
                    record_activation_phase(
                        {
                            "phase": "place_candidate_source",
                            "kind": "filesystem",
                            "status": "passed",
                            "target_root": str(target),
                            "backup_root": str(backup) if backup.exists() else None,
                            "candidate_build_id": candidate["build_id"],
                            "previous_tree": previous_tree,
                            "candidate_tree": candidate_tree,
                            "recorded_at": _now(),
                        }
                    )
                if fault_at == f"after_{item.kind}_placement":
                    raise OSError(f"injected failure after {item.kind} placement")

            for item in installations:
                if item.kind != "plugin":
                    continue
                candidate_activation_attempted = True
                activated = self._plugin_command(
                    "activate_candidate", item, "add"
                )
                activation_results.append(activated)
                record_activation_phase(activated)
                if activated["status"] != "passed":
                    raise UserUpdateError("Codex plugin reinstall failed")
                verified_activation = self._observe_plugin(
                    "verify_candidate_activation",
                    item,
                    str(candidate_plugin_version),
                    expected_build_id=candidate["build_id"],
                    expected_content_index_sha256=candidate[
                        "content_index_sha256"
                    ],
                )
                record_activation_phase(verified_activation)
                if verified_activation["status"] != "passed":
                    raise UserUpdateError(
                        "Codex plugin activation/cache identity differs from candidate"
                    )
            if fault_at == "after_activation":
                raise OSError("injected failure after activation")

            state = self._state()
            state["active_installations"] = [
                {
                    "kind": item.kind,
                    "target_root": str(item.target_root),
                    "build_id": candidate["build_id"],
                    "content_index_sha256": candidate["content_index_sha256"],
                }
                for item in installations
            ]
            state.setdefault("history", []).append(
                {
                    "operation_id": operation_id,
                    "created_at": _now(),
                    "candidate_build_id": candidate["build_id"],
                    "placements": placements,
                    "discovery_migration": discovery_migration,
                    "rolled_back": False,
                }
            )
            if activation_journal is not None:
                activation_journal["status"] = "committed"
                activation_journal_path = self._write_activation_journal(
                    activation_journal
                )
            _write_atomic(self.state_path, state)
            receipt.update(
                {
                    "status": "committed",
                    "requested_target_applied": True,
                    "placements": placements,
                    "activation": activation_results,
                    "activation_phases": activation_phases,
                    "activation_journal": (
                        self._activation_journal_link(
                            activation_journal, activation_journal_path
                        )
                        if activation_journal is not None
                        and activation_journal_path is not None
                        else None
                    ),
                    "cache_reconciliation": cache_reconciliation,
                    "requires_new_session": True,
                    "next_action": "Start a new Codex task; restart Codex if the new build is not discovered.",
                }
            )
            return self._save_receipt(receipt)
        except Exception as exc:
            rollback_errors: list[str] = []
            if (
                cache_reconciliation is None
                and residue_item is not None
                and previous_residue_identity is not None
                and preflight_runtime_residue is not None
                and preflight_runtime_residue.get("classification")
                == "runtime-residue"
            ):
                try:
                    cache_reconciliation = self._archive_plugin_cache_residue(
                        operation_id,
                        residue_item,
                        preflight_runtime_residue,
                        prestate_identity=previous_residue_identity,
                    )
                except Exception as recovery_exc:
                    rollback_errors.append(
                        f"runtime residue reconciliation recovery failed: {recovery_exc}"
                    )
            source_restored = not placements
            previous_activation_restored = not deactivation_attempted
            previous_cache_usable: bool | None = (
                preflight_runtime_residue.get("classification")
                in {"clean", "runtime-residue"}
                if preflight_runtime_residue is not None
                else None
            )
            discovery_restored = not (
                discovery_migration is not None
                and discovery_migration.get("status") == "committed"
            )
            if plugin_item is not None and candidate_activation_attempted:
                try:
                    candidate_absent = self._observe_plugin_absent(
                        "rollback_observe_candidate_absent", plugin_item
                    )
                    record_activation_phase(candidate_absent)
                    if candidate_absent["status"] != "passed":
                        removed_candidate = self._plugin_command(
                            "rollback_deactivate_candidate", plugin_item, "remove"
                        )
                        record_activation_phase(removed_candidate)
                        if removed_candidate["status"] != "passed":
                            rollback_errors.append(
                                "candidate plugin could not be deactivated during rollback"
                            )
                        candidate_absent = self._observe_plugin_absent(
                            "rollback_verify_candidate_deactivated", plugin_item
                        )
                        record_activation_phase(candidate_absent)
                        if candidate_absent["status"] != "passed":
                            rollback_errors.append(
                                "candidate plugin remained active during rollback"
                            )
                except Exception as restore_exc:
                    rollback_errors.append(str(restore_exc))
            for placement in reversed(placements):
                target = Path(placement["target_root"])
                backup_value = placement.get("backup_root")
                backup = Path(backup_value) if backup_value else None
                try:
                    if target.exists():
                        quarantine = (
                            self.control_root
                            / "failed-placements"
                            / hashlib.sha256(
                                f"{target}\0{operation_id}".encode("utf-8")
                            ).hexdigest()[:20]
                        )
                        quarantine.parent.mkdir(parents=True, exist_ok=True)
                        if quarantine.exists():
                            _remove_controlled(quarantine, self.control_root)
                        os.replace(target, quarantine)
                        _remove_controlled(quarantine, self.control_root)
                    if backup is not None and backup.exists():
                        os.replace(backup, target)
                    observed_tree = _tree_identity(target) if target.is_dir() else None
                    tree_matches = observed_tree == placement.get("previous_tree")
                    if not tree_matches:
                        raise UserUpdateError(
                            "restored source tree differs from its preflight identity"
                        )
                    if placement.get("kind") == "plugin":
                        record_activation_phase(
                            {
                                "phase": "rollback_restore_previous_source",
                                "kind": "filesystem",
                                "status": "passed",
                                "target_root": str(target),
                                "observed_tree": observed_tree,
                                "expected_tree": placement.get("previous_tree"),
                                "tree_matches": tree_matches,
                                "recorded_at": _now(),
                            }
                        )
                    source_restored = True
                except Exception as restore_exc:  # pragma: no cover - hard to force portably.
                    rollback_errors.append(str(restore_exc))
            if (
                plugin_item is not None
                and deactivation_attempted
                and previous_plugin_version is not None
            ):
                try:
                    observed_previous = self._observe_plugin_prestate(
                        "rollback_observe_previous",
                        plugin_item,
                        previous_plugin_identity,
                        cache_state=(
                            "reconciled"
                            if cache_reconciliation is not None
                            else "initial"
                        ),
                        require_current_state=True,
                    )
                    record_activation_phase(observed_previous)
                    if observed_previous["status"] == "passed":
                        previous_activation_restored = True
                        previous_cache_usable = True
                    else:
                        previous_absent = self._observe_plugin_absent(
                            "rollback_observe_previous_absent", plugin_item
                        )
                        record_activation_phase(previous_absent)
                        if previous_absent["status"] != "passed":
                            removed_residue = self._plugin_command(
                                "rollback_deactivate_residue", plugin_item, "remove"
                            )
                            record_activation_phase(removed_residue)
                            if removed_residue["status"] != "passed":
                                raise UserUpdateError(
                                    "residual plugin could not be deactivated before previous restore"
                                )
                            previous_absent = self._observe_plugin_absent(
                                "rollback_verify_residue_deactivated", plugin_item
                            )
                            record_activation_phase(previous_absent)
                            if previous_absent["status"] != "passed":
                                raise UserUpdateError(
                                    "residual plugin remained active before previous restore"
                                )
                        reactivated = self._plugin_command(
                            "rollback_reactivate_previous", plugin_item, "add"
                        )
                        record_activation_phase(reactivated)
                        if reactivated["status"] != "passed":
                            raise UserUpdateError(
                                "previous plugin source could not be reactivated"
                            )
                        verified_previous = self._observe_plugin_prestate(
                            "rollback_verify_previous",
                            plugin_item,
                            previous_plugin_identity,
                            cache_state=(
                                "reconciled"
                                if cache_reconciliation is not None
                                else "initial"
                            ),
                            require_current_state=True,
                        )
                        record_activation_phase(verified_previous)
                        previous_activation_restored = (
                            verified_previous["status"] in {"passed", "warning"}
                        )
                        previous_cache_usable = bool(
                            verified_previous.get("identity_matches")
                            and verified_previous["cache"].get("classification")
                            in {"clean", "runtime-residue"}
                        )
                        if not previous_activation_restored:
                            raise UserUpdateError(
                                "previous plugin activation/cache identity was not restored"
                            )
                    if (
                        previous_activation_restored
                        and cache_reconciliation is not None
                        and previous_plugin_identity is not None
                    ):
                        cache_reconciliation_restore = (
                            self._restore_plugin_cache_residue(
                                cache_reconciliation,
                                plugin_item,
                                restore_operation_id=operation_id,
                                prestate_identity=previous_plugin_identity,
                                require_current_state=True,
                            )
                        )
                        previous_cache_usable = True
                        record_activation_phase(
                            {
                                **cache_reconciliation_restore,
                                "phase": "rollback_restore_runtime_bytecode_residue",
                                "kind": "filesystem",
                                "status": "passed",
                                "recorded_at": _now(),
                            }
                        )
                except Exception as restore_exc:
                    rollback_errors.append(str(restore_exc))
            if (
                residue_item is not None
                and residue_item.kind == "skill"
                and previous_residue_identity is not None
                and cache_reconciliation is not None
                and cache_reconciliation_restore is None
                and source_restored
            ):
                try:
                    cache_reconciliation_restore = (
                        self._restore_plugin_cache_residue(
                            cache_reconciliation,
                            residue_item,
                            restore_operation_id=operation_id,
                            prestate_identity=previous_residue_identity,
                            require_current_state=True,
                        )
                    )
                    previous_cache_usable = True
                except Exception as restore_exc:
                    rollback_errors.append(str(restore_exc))
            if (
                plugin_item is not None
                and previous_plugin_identity is not None
                and cache_reconciliation is not None
                and cache_reconciliation_restore is None
                and source_restored
                and previous_activation_restored
            ):
                try:
                    cache_reconciliation_restore = (
                        self._restore_plugin_cache_residue(
                            cache_reconciliation,
                            plugin_item,
                            restore_operation_id=operation_id,
                            prestate_identity=previous_plugin_identity,
                            require_current_state=True,
                        )
                    )
                    previous_cache_usable = True
                    record_activation_phase(
                        {
                            **cache_reconciliation_restore,
                            "phase": "rollback_restore_runtime_bytecode_residue",
                            "kind": "filesystem",
                            "status": "passed",
                            "recorded_at": _now(),
                        }
                    )
                except Exception as restore_exc:
                    rollback_errors.append(str(restore_exc))
            if (
                discovery_migration is not None
                and discovery_migration.get("status") == "committed"
                and discovery_migration_path is not None
            ):
                try:
                    restored, restored_path = self._restore_discovery_conflicts(
                        discovery_migration_path,
                        operation_id,
                        phase="discovery-auto-restore",
                    )
                    discovery_restore = _discovery_link(restored, restored_path)
                    discovery_restored = True
                except Exception as restore_exc:
                    rollback_errors.append(str(restore_exc))
            mutation_started = bool(
                deactivation_succeeded
                or placements
                or cache_reconciliation is not None
                or (
                    discovery_migration is not None
                    and discovery_migration.get("status") == "committed"
                )
            )
            final_status = (
                "rollback_failed"
                if rollback_errors
                else "rolled_back"
                if mutation_started
                else "blocked"
            )
            if activation_journal is not None:
                activation_journal["status"] = final_status
                activation_journal["recovery"] = {
                    "source_restored": source_restored,
                    "previous_activation_restored": previous_activation_restored,
                    "previous_cache_usable": previous_cache_usable,
                    "discovery_restored": discovery_restored,
                    "errors": rollback_errors,
                }
                activation_journal_path = self._write_activation_journal(
                    activation_journal
                )
            receipt = self._base_receipt(
                "upgrade",
                operation_id,
                request_sha,
                status=final_status,
                candidate=candidate,
                installations=installations,
            )
            receipt.update(
                {
                    "placements": placements,
                    "activation": activation_results,
                    "activation_phases": activation_phases,
                    "activation_journal": (
                        self._activation_journal_link(
                            activation_journal, activation_journal_path
                        )
                        if activation_journal is not None
                        and activation_journal_path is not None
                        else None
                    ),
                    "discovery_migration": discovery_migration,
                    "discovery_restore": discovery_restore,
                    "cache_reconciliation": cache_reconciliation,
                    "cache_reconciliation_restore": cache_reconciliation_restore,
                    "rollback_performed": bool(
                        mutation_started and not rollback_errors
                    ),
                    "requested_target_applied": False,
                    "compensation_performed": bool(mutation_started),
                    "current_installation_restored": bool(
                        source_restored
                        and previous_activation_restored
                        and (
                            cache_reconciliation is None
                            or cache_reconciliation_restore is not None
                        )
                        and discovery_restored
                    ),
                    "retryable": not rollback_errors,
                    "recovery": {
                        "source_restored": source_restored,
                        "previous_activation_restored": previous_activation_restored,
                        "previous_cache_usable": previous_cache_usable,
                        "cache_reconciliation_restored": bool(
                            cache_reconciliation is None
                            or cache_reconciliation_restore is not None
                        ),
                        "discovery_restored": discovery_restored,
                    },
                    "blockers": [
                        {
                            "code": (
                                "UPGRADE_FAILED"
                                if mutation_started
                                else "UPGRADE_PREFLIGHT_FAILED"
                            ),
                            "message": str(exc),
                        },
                        *(
                            [{"code": "UPGRADE_ROLLBACK_FAILED", "messages": rollback_errors}]
                            if rollback_errors
                            else []
                        ),
                    ],
                }
            )
            return self._save_receipt(receipt)
        finally:
            if transaction_root.exists():
                _remove_controlled(transaction_root, self.staging)
            cleanup()

    def _rollback_plugin_transaction(
        self,
        *,
        operation_id: str,
        request_sha: str,
        selected: dict[str, Any],
        state: dict[str, Any],
        receipt: dict[str, Any],
        fault_at: str | None,
    ) -> dict[str, Any]:
        placements = [
            item
            for item in selected.get("placements", [])
            if isinstance(item, dict) and item.get("kind") == "plugin"
        ]
        if len(placements) != 1:
            receipt["blockers"] = [
                {"code": "ROLLBACK_PLUGIN_PLACEMENT_AMBIGUOUS", "count": len(placements)}
            ]
            return self._save_receipt(receipt)
        placement = placements[0]
        target = _safe_target(placement["target_root"], "rollback target")
        backup_value = placement.get("backup_root")
        if not backup_value:
            receipt["blockers"] = [
                {"code": "ROLLBACK_BACKUP_MISSING", "target_root": str(target)}
            ]
            return self._save_receipt(receipt)
        backup = _safe_target(backup_value, "rollback backup")
        if not backup.is_dir():
            receipt["blockers"] = [
                {"code": "ROLLBACK_BACKUP_MISSING", "path": str(backup)}
            ]
            return self._save_receipt(receipt)
        item = Installation(
            "plugin",
            target,
            marketplace_name=str(placement.get("marketplace_name") or ""),
        )
        current_version = _plugin_manifest_version(target)
        previous_version = _plugin_manifest_version(backup)
        if current_version is None or previous_version is None:
            receipt["blockers"] = [
                {"code": "ROLLBACK_PLUGIN_VERSION_UNREADABLE"}
            ]
            return self._save_receipt(receipt)
        expected_previous = placement.get("previous") or {}
        expected_previous_tree = placement.get("previous_tree")
        try:
            observed_previous_tree = _tree_identity(backup)
            if observed_previous_tree != expected_previous_tree:
                raise UserUpdateError("rollback backup tree differs from recorded prestate")
            expected_previous_build = str(expected_previous.get("build_id", ""))
            expected_previous_index = str(
                expected_previous.get("content_index_sha256", "")
            )
            if (
                expected_previous.get("candidate_eligible") is False
                and (expected_previous.get("legacy_discovery_violation") or {}).get(
                    "code"
                )
                == "LEGACY_WORKSPACE_SKILL_PRESENT"
            ):
                _recognize_legacy_installed_prestate(
                    backup,
                    expected_build_id=expected_previous_build,
                    expected_content_index_sha256=expected_previous_index,
                )
            else:
                previous_verification = verify_bundle(backup)
                if (
                    previous_verification.get("build_id")
                    != expected_previous_build
                    or previous_verification.get("content_index_sha256")
                    != expected_previous_index
                ):
                    raise UserUpdateError(
                        "rollback backup identity differs from recorded prestate"
                    )
        except (OSError, ReleaseError, UserUpdateError) as exc:
            receipt["blockers"] = [
                {
                    "code": "ROLLBACK_PRESTATE_INVALID",
                    "message": str(exc),
                    "path": str(backup),
                }
            ]
            return self._save_receipt(receipt)
        try:
            current_verification = verify_bundle(target)
        except (OSError, ReleaseError) as exc:
            receipt["blockers"] = [
                {"code": "ROLLBACK_CURRENT_BUNDLE_INVALID", "message": str(exc)}
            ]
            return self._save_receipt(receipt)
        current_backup = _backup_root(
            self.control_root, target
        ) / f"{target.name}-rollback-current-{operation_id}"
        if current_backup.exists():
            receipt["blockers"] = [
                {"code": "ROLLBACK_CURRENT_BACKUP_EXISTS", "path": str(current_backup)}
            ]
            return self._save_receipt(receipt)

        phases: list[dict[str, Any]] = []
        journal = {
            "contract": PLUGIN_ACTIVATION_JOURNAL_CONTRACT,
            "schema_version": PLUGIN_ACTIVATION_JOURNAL_SCHEMA_VERSION,
            "operation_id": operation_id,
            "install_kind": "plugin",
            "status": "in_progress",
            "created_at": _now(),
            "updated_at": _now(),
            "selector": self._plugin_selector(item),
            "target_root": str(target),
            "previous_version": current_version,
            "candidate_version": previous_version,
            "candidate_build_id": (placement.get("previous") or {}).get("build_id"),
            "phases": phases,
            "external_action_authorized": False,
        }
        journal_path: Path | None = None

        def record(phase: dict[str, Any]) -> None:
            nonlocal journal_path
            phases.append(phase)
            journal["phases"] = phases
            journal_path = self._write_activation_journal(journal)

        source_move_started = False
        deactivation_succeeded = False
        old_activation_attempted = False
        cache_reconciliation = placement.get("cache_reconciliation")
        cache_reconciliation_restore: dict[str, Any] | None = None
        discovery_restore: dict[str, Any] | None = None
        discovery_migration = selected.get("discovery_migration")
        try:
            preflight = self._observe_plugin(
                "rollback_preflight_current",
                item,
                current_version,
                expected_build_id=current_verification["build_id"],
                expected_content_index_sha256=current_verification[
                    "content_index_sha256"
                ],
            )
            record(preflight)
            if preflight["status"] != "passed":
                raise UserUpdateError("rollback preflight activation/cache identity mismatch")
            removed = self._plugin_command(
                "rollback_deactivate_current", item, "remove"
            )
            record(removed)
            if removed["status"] != "passed":
                raise UserUpdateError("rollback could not deactivate the current plugin")
            deactivation_succeeded = True
            absent = self._observe_plugin_absent(
                "rollback_verify_current_deactivated", item
            )
            record(absent)
            if absent["status"] != "passed":
                raise UserUpdateError("current plugin remained active during rollback")
            os.replace(target, current_backup)
            source_move_started = True
            os.replace(backup, target)
            restored_tree = _tree_identity(target)
            expected_tree = placement.get("previous_tree")
            source_matches = restored_tree == expected_tree
            record(
                {
                    "phase": "rollback_place_previous_source",
                    "kind": "filesystem",
                    "status": "passed" if source_matches else "failed",
                    "target_root": str(target),
                    "current_backup": str(current_backup),
                    "observed_tree": restored_tree,
                    "expected_tree": expected_tree,
                    "tree_matches": source_matches,
                    "recorded_at": _now(),
                }
            )
            if not source_matches:
                raise UserUpdateError("rollback previous source hash mismatch")
            old_activation_attempted = True
            activated_old = self._plugin_command(
                "rollback_activate_previous", item, "add"
            )
            record(activated_old)
            if activated_old["status"] != "passed":
                raise UserUpdateError("rollback could not activate the previous plugin")
            verified_old = self._observe_plugin_prestate(
                "rollback_verify_previous_activation",
                item,
                expected_previous,
                cache_state=(
                    "reconciled"
                    if isinstance(cache_reconciliation, dict)
                    else "initial"
                ),
                require_current_state=False,
            )
            record(verified_old)
            if verified_old["status"] != "passed":
                raise UserUpdateError(
                    "rollback previous activation/cache identity mismatch"
                )
            if isinstance(cache_reconciliation, dict):
                cache_reconciliation_restore = self._restore_plugin_cache_residue(
                    cache_reconciliation,
                    item,
                    restore_operation_id=operation_id,
                    prestate_identity=expected_previous,
                    require_current_state=False,
                )
                record(
                    {
                        **cache_reconciliation_restore,
                        "phase": "rollback_restore_runtime_bytecode_residue",
                        "kind": "filesystem",
                        "status": "passed",
                        "recorded_at": _now(),
                    }
                )
            final_previous = self._observe_plugin_prestate(
                "rollback_verify_previous_final_prestate",
                item,
                expected_previous,
                cache_state="initial",
                require_current_state=False,
            )
            record(final_previous)
            if final_previous["status"] not in {"passed", "warning"}:
                raise UserUpdateError(
                    "rollback final previous source/cache/CLI identity mismatch"
                )
            if fault_at == "after_previous_activation":
                raise OSError("injected failure after previous plugin activation")
            if (
                isinstance(discovery_migration, dict)
                and discovery_migration.get("status") == "committed"
            ):
                migration_path = _safe_target(
                    discovery_migration["receipt_path"],
                    "Skill discovery migration receipt",
                )
                restored, restored_path = self._restore_discovery_conflicts(
                    migration_path,
                    operation_id,
                    phase="discovery-explicit-restore",
                )
                discovery_restore = _discovery_link(restored, restored_path)
            selected["rolled_back"] = True
            selected["rollback_operation_id"] = operation_id
            selected["discovery_restore"] = discovery_restore
            state["active_installations"] = [
                {
                    "kind": "plugin",
                    "target_root": str(target),
                    "build_id": (placement.get("previous") or {}).get("build_id"),
                    "content_index_sha256": (placement.get("previous") or {}).get(
                        "content_index_sha256"
                    ),
                }
            ]
            journal["status"] = "committed"
            journal_path = self._write_activation_journal(journal)
            _write_atomic(self.state_path, state)
            receipt.update(
                {
                    "status": "committed",
                    "rollback_performed": True,
                    "requested_target_applied": True,
                    "compensation_performed": False,
                    "current_installation_restored": False,
                    "retryable": False,
                    "rolled_back_operation_id": selected.get("operation_id"),
                    "discovery_migration": discovery_migration,
                    "discovery_restore": discovery_restore,
                    "activation_phases": phases,
                    "activation_journal": self._activation_journal_link(
                        journal, journal_path
                    ),
                    "cache_reconciliation": cache_reconciliation,
                    "cache_reconciliation_restore": cache_reconciliation_restore,
                    "requires_new_session": True,
                    "next_action": "Start a new Codex task; restart Codex if the restored build is not discovered.",
                }
            )
            return self._save_receipt(receipt)
        except Exception as exc:
            restore_errors: list[str] = []
            current_source_restored = not source_move_started
            current_activation_restored = not deactivation_succeeded
            if old_activation_attempted:
                try:
                    old_absent = self._observe_plugin_absent(
                        "rollback_failure_observe_previous_absent", item
                    )
                    record(old_absent)
                    if old_absent["status"] != "passed":
                        removed_old = self._plugin_command(
                            "rollback_failure_deactivate_previous", item, "remove"
                        )
                        record(removed_old)
                        if removed_old["status"] != "passed":
                            restore_errors.append(
                                "failed rollback could not deactivate previous plugin"
                            )
                        old_absent = self._observe_plugin_absent(
                            "rollback_failure_verify_previous_deactivated", item
                        )
                        record(old_absent)
                        if old_absent["status"] != "passed":
                            restore_errors.append(
                                "previous plugin remained active after failed rollback"
                            )
                except Exception as restore_exc:
                    restore_errors.append(str(restore_exc))
            if source_move_started:
                try:
                    if target.exists():
                        os.replace(target, backup)
                    if current_backup.exists():
                        os.replace(current_backup, target)
                    candidate_tree = _tree_identity(target)
                    tree_matches = candidate_tree == placement.get("candidate_tree")
                    record(
                        {
                            "phase": "rollback_failure_restore_current_source",
                            "kind": "filesystem",
                            "status": "passed" if tree_matches else "failed",
                            "target_root": str(target),
                            "observed_tree": candidate_tree,
                            "expected_tree": placement.get("candidate_tree"),
                            "tree_matches": tree_matches,
                            "recorded_at": _now(),
                        }
                    )
                    if not tree_matches:
                        restore_errors.append(
                            "failed rollback restored source hash mismatch"
                        )
                    else:
                        current_source_restored = True
                except Exception as restore_exc:
                    restore_errors.append(str(restore_exc))
            if deactivation_succeeded:
                try:
                    observed_current = self._observe_plugin(
                        "rollback_failure_observe_current",
                        item,
                        current_version,
                        expected_build_id=current_verification["build_id"],
                        expected_content_index_sha256=current_verification[
                            "content_index_sha256"
                        ],
                    )
                    record(observed_current)
                    if observed_current["status"] == "passed":
                        current_activation_restored = True
                    else:
                        current_absent = self._observe_plugin_absent(
                            "rollback_failure_observe_current_absent", item
                        )
                        record(current_absent)
                        if current_absent["status"] != "passed":
                            removed_residue = self._plugin_command(
                                "rollback_failure_deactivate_residue", item, "remove"
                            )
                            record(removed_residue)
                            if removed_residue["status"] != "passed":
                                raise UserUpdateError(
                                    "failed rollback could not deactivate residual plugin"
                                )
                            current_absent = self._observe_plugin_absent(
                                "rollback_failure_verify_residue_deactivated", item
                            )
                            record(current_absent)
                            if current_absent["status"] != "passed":
                                raise UserUpdateError(
                                    "residual plugin remained active before current restore"
                                )
                        reactivated_current = self._plugin_command(
                            "rollback_failure_reactivate_current", item, "add"
                        )
                        record(reactivated_current)
                        if reactivated_current["status"] != "passed":
                            raise UserUpdateError(
                                "failed rollback could not reactivate current plugin"
                            )
                        verified_current = self._observe_plugin(
                            "rollback_failure_verify_current",
                            item,
                            current_version,
                            expected_build_id=current_verification["build_id"],
                            expected_content_index_sha256=current_verification[
                                "content_index_sha256"
                            ],
                        )
                        record(verified_current)
                        current_activation_restored = (
                            verified_current["status"] == "passed"
                        )
                        if not current_activation_restored:
                            raise UserUpdateError(
                                "failed rollback current activation/cache identity mismatch"
                            )
                except Exception as restore_exc:
                    restore_errors.append(str(restore_exc))
            mutation_started = bool(deactivation_succeeded or source_move_started)
            final_status = "rollback_failed" if mutation_started or restore_errors else "blocked"
            journal["status"] = final_status
            journal["recovery"] = {
                "current_source_restored": current_source_restored,
                "current_activation_restored": current_activation_restored,
                "errors": restore_errors,
            }
            journal_path = self._write_activation_journal(journal)
            receipt.update(
                {
                    "status": final_status,
                    "rollback_performed": False,
                    "requested_target_applied": False,
                    "compensation_performed": bool(mutation_started),
                    "current_installation_restored": bool(
                        current_source_restored and current_activation_restored
                    ),
                    "retryable": not restore_errors,
                    "activation_phases": phases,
                    "activation_journal": self._activation_journal_link(
                        journal, journal_path
                    ),
                    "blockers": [
                        {"code": "ROLLBACK_FAILED", "message": str(exc)},
                        *(
                            [
                                {
                                    "code": "ROLLBACK_RESTORE_FAILED",
                                    "messages": restore_errors,
                                }
                            ]
                            if restore_errors
                            else []
                        ),
                    ],
                    "next_action": (
                        "Retry rollback with a new operation_id after reviewing the failed rollback receipt."
                        if not restore_errors
                        else "Do not retry automatically; inspect the activation journal and restore blockers."
                    ),
                }
            )
            return self._save_receipt(receipt)

    def rollback(
        self,
        *,
        operation_id: str,
        confirmed: bool,
        fault_at: str | None = None,
    ) -> dict[str, Any]:
        operation_id = _safe_id(operation_id, "operation_id")
        request = {"operation": "rollback", "operation_id": operation_id, "confirmed": confirmed}
        request_sha = _request_hash(request)
        replay = self._replay(operation_id, request_sha)
        if replay is not None:
            return replay
        state = self._state()
        history = [item for item in state.get("history", []) if isinstance(item, dict) and not item.get("rolled_back")]
        receipt = self._base_receipt(
            "rollback", operation_id, request_sha, status="blocked", candidate=None, installations=[]
        )
        if not confirmed:
            receipt["blockers"] = [{"code": "USER_CONFIRMATION_REQUIRED"}]
            return self._save_receipt(receipt)
        if not history:
            receipt["blockers"] = [{"code": "ROLLBACK_TARGET_MISSING"}]
            return self._save_receipt(receipt)
        selected = history[-1]
        placements = selected.get("placements", [])
        if any(
            isinstance(item, dict) and item.get("kind") == "plugin"
            for item in placements
        ):
            return self._rollback_plugin_transaction(
                operation_id=operation_id,
                request_sha=request_sha,
                selected=selected,
                state=state,
                receipt=receipt,
                fault_at=fault_at,
            )
        discovery_migration = selected.get("discovery_migration")
        discovery_restore: dict[str, Any] | None = None
        cache_reconciliation_restore: dict[str, Any] | None = None
        swapped: list[dict[str, Path]] = []
        try:
            for placement in reversed(placements):
                target = _safe_target(placement["target_root"], "rollback target")
                backup_value = placement.get("backup_root")
                if not backup_value:
                    raise UserUpdateError(f"rollback backup is unavailable for {target}")
                backup = _safe_target(backup_value, "rollback backup")
                if not backup.is_dir():
                    raise UserUpdateError(f"rollback backup is missing: {backup}")
                if _tree_identity(target) != placement.get("candidate_tree"):
                    raise UserUpdateError(
                        f"rollback current target differs from recorded candidate: {target}"
                    )
                if _tree_identity(backup) != placement.get("previous_tree"):
                    raise UserUpdateError(
                        f"rollback backup differs from recorded prestate: {backup}"
                    )
                previous = placement.get("previous") or {}
                previous_identity = self._current_prestate_identity(
                    Installation(str(placement.get("kind")), backup)
                )
                if (
                    previous_identity.get("current_prestate_recognized") is not True
                    or previous_identity.get("build_id") != previous.get("build_id")
                    or previous_identity.get("content_index_sha256")
                    != previous.get("content_index_sha256")
                ):
                    raise UserUpdateError(
                        f"rollback backup identity differs from recorded prestate: {backup}"
                    )
                current_backup = _backup_root(
                    self.control_root, target
                ) / f"{target.name}-rollback-current-{operation_id}"
                if current_backup.exists():
                    raise UserUpdateError(f"rollback current backup already exists: {current_backup}")
                os.replace(target, current_backup)
                swapped.append({"target": target, "old_backup": backup, "current_backup": current_backup})
                os.replace(backup, target)
                if placement.get("kind") == "plugin":
                    marketplace = placement.get("marketplace_name")
                    result = self.command_runner(
                        [self.codex_command, "plugin", "add", f"{PLUGIN_NAME}@{marketplace}"]
                    )
                    if result.returncode != 0:
                        raise UserUpdateError("Codex plugin reactivation failed during rollback")
                cache_reconciliation = placement.get("cache_reconciliation")
                if (
                    placement.get("kind") == "skill"
                    and isinstance(cache_reconciliation, dict)
                ):
                    cache_reconciliation_restore = (
                        self._restore_plugin_cache_residue(
                            cache_reconciliation,
                            Installation("skill", target),
                            restore_operation_id=operation_id,
                            prestate_identity=previous,
                            require_current_state=True,
                        )
                    )
                    final_previous = self._current_prestate_identity(
                        Installation("skill", target)
                    )
                    if (
                        final_previous.get("current_prestate_recognized") is not True
                        or final_previous.get("build_id") != previous.get("build_id")
                        or final_previous.get("content_index_sha256")
                        != previous.get("content_index_sha256")
                        or (final_previous.get("managed_suite") or {}).get(
                            "classification"
                        )
                        != "runtime-residue"
                    ):
                        raise UserUpdateError(
                            "rollback did not restore the managed Skill suite residue prestate"
                        )
            if (
                isinstance(discovery_migration, dict)
                and discovery_migration.get("status") == "committed"
            ):
                migration_path = _safe_target(
                    discovery_migration["receipt_path"],
                    "Skill discovery migration receipt",
                )
                restored, restored_path = self._restore_discovery_conflicts(
                    migration_path,
                    operation_id,
                    phase="discovery-explicit-restore",
                )
                discovery_restore = _discovery_link(restored, restored_path)
            selected["rolled_back"] = True
            selected["rollback_operation_id"] = operation_id
            selected["discovery_restore"] = discovery_restore
            state["active_installations"] = [
                {
                    "kind": placement["kind"],
                    "target_root": placement["target_root"],
                    "build_id": (placement.get("previous") or {}).get("build_id"),
                    "content_index_sha256": (placement.get("previous") or {}).get("content_index_sha256"),
                }
                for placement in placements
            ]
            _write_atomic(self.state_path, state)
            receipt.update(
                {
                    "status": "committed",
                    "rollback_performed": True,
                    "requested_target_applied": True,
                    "compensation_performed": False,
                    "current_installation_restored": False,
                    "retryable": False,
                    "rolled_back_operation_id": selected.get("operation_id"),
                    "discovery_migration": discovery_migration,
                    "discovery_restore": discovery_restore,
                    "cache_reconciliation_restore": cache_reconciliation_restore,
                    "requires_new_session": True,
                    "next_action": "Start a new Codex task; restart Codex if the restored build is not discovered.",
                }
            )
            return self._save_receipt(receipt)
        except Exception as exc:
            restore_errors: list[str] = []
            for item in reversed(swapped):
                try:
                    if item["target"].exists():
                        os.replace(item["target"], item["old_backup"])
                    if item["current_backup"].exists():
                        os.replace(item["current_backup"], item["target"])
                except Exception as restore_exc:  # pragma: no cover
                    restore_errors.append(str(restore_exc))
            receipt.update(
                {
                    "status": "rollback_failed" if swapped or restore_errors else "blocked",
                    "rollback_performed": False,
                    "requested_target_applied": False,
                    "compensation_performed": bool(swapped),
                    "current_installation_restored": bool(
                        not restore_errors
                    ),
                    "retryable": not restore_errors,
                    "blockers": [
                        {"code": "ROLLBACK_FAILED", "message": str(exc)},
                        *(
                            [{"code": "ROLLBACK_RESTORE_FAILED", "messages": restore_errors}]
                            if restore_errors
                            else []
                        ),
                    ],
                    "next_action": (
                        "Retry rollback with a new operation_id after reviewing the failed rollback receipt."
                        if not restore_errors
                        else "Do not retry automatically; inspect rollback restore blockers."
                    ),
                }
            )
            return self._save_receipt(receipt)
