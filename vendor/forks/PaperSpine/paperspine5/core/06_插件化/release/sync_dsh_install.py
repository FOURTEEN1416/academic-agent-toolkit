#!/usr/bin/env python3
"""Update already-installed DSH PaperSpine5 bundles from the canonical checkout.

Repository maintenance helper that lives next to ``suite_release.py`` and
``dsh_release.py``. It rebuilds ONE complete suite from the canonical project
source, projects the native DSH bundle from it, extracts that bundle into a
unique temporary build folder, and hands the same extracted bundle to the
existing ``install_bundle.py --target <stable path> --no-link`` once per
selected target.

Guarantees kept deliberately small and explicit:

* No recognized installed target means skip; nothing is created.
* An explicit ``--target`` must already be a recognized ``dsh-paperspine5``
  package, so no arbitrary directory is written.
* The existing installer is reused unchanged, including its backup and
  rollback behavior; previous bundle backups are preserved.
* ``--no-link`` keeps DSH profile links, routes, credentials and user data
  untouched.
* A build or install failure raises :class:`DshSyncError`; this module never
  records success on its own.

Standalone use (DSH-only update, other hosts untouched)::

    python -B sync_dsh_install.py --source-root <PaperSpine5 checkout>
"""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Callable

sys.dont_write_bytecode = True

PACKAGE_NAME = "dsh-paperspine5"
DEFAULT_RELEASES_ROOT = Path.home() / ".paperspine5" / "releases"
BACKUP_MARKERS = (".backup-", ".staging-")
INSTALLER_NAME = "install_bundle.py"


class DshSyncError(RuntimeError):
    """A DSH synchronization step failed; the caller must treat sync as failed."""


def _is_backup_name(name: str) -> bool:
    return any(marker in name for marker in BACKUP_MARKERS)


def _has_link_component(path: Path) -> bool:
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            return True
    return False


def is_recognized_dsh_target(target: str | Path) -> bool:
    """Return True only for an existing ``dsh-paperspine5`` package directory."""
    path = Path(target).expanduser().absolute()
    if _has_link_component(path) or not path.is_dir() or _is_backup_name(path.name):
        return False
    manifest = path / "package.json"
    if _has_link_component(manifest) or not manifest.is_file():
        return False
    try:
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(metadata, dict) and metadata.get("name") == PACKAGE_NAME


def discover_dsh_targets(releases_root: str | Path = DEFAULT_RELEASES_ROOT) -> list[Path]:
    """Find recognized ``<releases>/*/dsh-paperspine5`` installs, never backups."""
    root = Path(releases_root).expanduser()
    if _has_link_component(root.absolute()):
        raise DshSyncError(f"DSH releases root contains a link/reparse point: {root}")
    if not root.is_dir():
        return []
    targets: list[Path] = []
    for release in sorted(root.iterdir(), key=lambda item: item.name):
        if not release.is_dir() or _is_backup_name(release.name):
            continue
        candidate = release / PACKAGE_NAME
        if _is_backup_name(candidate.name) or not is_recognized_dsh_target(candidate):
            continue
        targets.append(candidate.resolve())
    return targets


def _resolve_builder(name: str, override: Callable | None) -> Callable:
    if override is not None:
        return override
    if name == "build_bundle":
        from suite_release import build_bundle
        return build_bundle
    from dsh_release import build_dsh_bundle
    return build_dsh_bundle


def build_bundles(
    source_root: str | Path,
    work_dir: Path,
    *,
    build_bundle: Callable | None = None,
    build_dsh_bundle: Callable | None = None,
) -> tuple[Path, Path]:
    """Rebuild one suite and its DSH projection inside ``work_dir``."""
    suite_zip = Path(work_dir) / "paperspine5-suite.zip"
    dsh_zip = Path(work_dir) / "paperspine5-dsh.zip"
    try:
        builder = _resolve_builder("build_bundle", build_bundle)
        projector = _resolve_builder("build_dsh_bundle", build_dsh_bundle)
        builder(str(source_root), str(suite_zip))
        projector(str(suite_zip), str(dsh_zip))
    except Exception as exc:  # noqa: BLE001 - surface every builder failure
        raise DshSyncError(f"DSH bundle build failed: {exc}") from exc
    return suite_zip, dsh_zip


def _unsafe_archive_path(name: str) -> bool:
    normalized = name.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    return normalized.startswith("/") or ".." in parts or ":" in normalized


def extract_dsh_bundle(dsh_zip: str | Path, destination: str | Path) -> Path:
    """Extract the built DSH bundle into a fresh, unique destination."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(dsh_zip) as archive:
            for info in archive.infolist():
                if _unsafe_archive_path(info.filename):
                    raise DshSyncError(f"DSH bundle contains an unsafe path: {info.filename}")
            archive.extractall(destination)
    except DshSyncError:
        raise
    except Exception as exc:  # noqa: BLE001 - bad zip or IO failure
        raise DshSyncError(f"DSH bundle extraction failed: {exc}") from exc
    if not (destination / INSTALLER_NAME).is_file():
        raise DshSyncError(f"DSH bundle has no {INSTALLER_NAME}: {destination}")
    return destination


def installer_argv(bundle_root: str | Path, target: str | Path, *, python: str | Path | None = None) -> list[str]:
    """Build the existing installer command; ``--no-link`` keeps profiles intact."""
    interpreter = str(python or sys.executable)
    return [
        interpreter,
        "-B",
        "-X",
        "utf8",
        str(Path(bundle_root) / INSTALLER_NAME),
        "--target",
        str(target),
        "--no-link",
    ]


def install_target(
    bundle_root: str | Path,
    target: str | Path,
    *,
    run: Callable | None = None,
    python: str | Path | None = None,
) -> list[str]:
    """Run the reused installer once for ``target`` and propagate any failure."""
    run = run or subprocess.run
    argv = installer_argv(bundle_root, target, python=python)
    try:
        run(argv, check=True)
    except Exception as exc:  # noqa: BLE001 - installer rollback already ran
        raise DshSyncError(f"DSH install failed for {target}: {exc}") from exc
    return argv


def _make_work_dir(output_dir: str | Path | None) -> Path:
    """Create a fresh, uniquely named build folder with inheritable permissions.

    ``tempfile.mkdtemp`` is avoided on purpose: it applies a ``0o700`` ACL that
    a restricted host token can no longer write inside.
    """
    base = Path(output_dir).expanduser().resolve() if output_dir is not None else Path(tempfile.gettempdir())
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DshSyncError(
            f"cannot use build directory {base}: {exc}; pass --output-dir with a writable path"
        ) from exc
    for _ in range(100):
        candidate = base / f"paperspine5-dsh-sync-{uuid.uuid4().hex[:12]}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
        except OSError as exc:
            raise DshSyncError(f"cannot create a build folder under {base}: {exc}") from exc
    raise DshSyncError(f"cannot allocate a unique build folder under {base}")


def sync_installed_targets(
    source_root: str | Path,
    *,
    target: str | Path | None = None,
    releases_root: str | Path | None = None,
    output_dir: str | Path | None = None,
    build_bundle: Callable | None = None,
    build_dsh_bundle: Callable | None = None,
    run: Callable | None = None,
    python: str | Path | None = None,
    keep_build: bool | None = None,
) -> dict:
    """Rebuild once and update every selected recognized DSH target.

    Returns ``{"status": "SKIPPED"}`` when no target is installed, otherwise
    ``{"status": "PASS", "targets": [...]}``. Raises :class:`DshSyncError` on
    any build or install failure.
    """
    source_root = Path(source_root).expanduser().resolve()
    if not source_root.is_dir():
        raise DshSyncError(f"canonical source root is missing: {source_root}")

    if target is not None:
        explicit = Path(target).expanduser().absolute()
        if not is_recognized_dsh_target(explicit):
            raise DshSyncError(
                f"explicit DSH target is not a recognized {PACKAGE_NAME} package: {explicit}"
            )
        targets = [explicit.resolve()]
    else:
        root = Path(releases_root).expanduser() if releases_root is not None else DEFAULT_RELEASES_ROOT
        targets = discover_dsh_targets(root)
        if not targets:
            return {
                "status": "SKIPPED",
                "reason": f"no recognized installed {PACKAGE_NAME} target",
                "targets": [],
                "build_dir": None,
            }

    work_dir = _make_work_dir(output_dir)
    if keep_build is None:
        keep_build = output_dir is not None
    try:
        suite_zip, dsh_zip = build_bundles(
            source_root,
            work_dir,
            build_bundle=build_bundle,
            build_dsh_bundle=build_dsh_bundle,
        )
        bundle_root = extract_dsh_bundle(dsh_zip, work_dir / "bundle")
        fresh_adapter = bundle_root / "adapter.json"
        fresh_platform = json.loads(fresh_adapter.read_text(encoding="utf-8")).get("platform") if fresh_adapter.is_file() else None
        for item in targets:
            metadata = item / "adapter.json"
            old_platform = json.loads(metadata.read_text(encoding="utf-8")).get("platform") if metadata.is_file() else None
            if old_platform and fresh_platform and old_platform != fresh_platform:
                raise DshSyncError(f"refusing platform change at {item}: {old_platform} -> {fresh_platform}")
        installed: list[str] = []
        for item in targets:
            install_target(bundle_root, item, run=run, python=python)
            installed.append(str(item))
        result = {"status": "PASS", "targets": installed, "build_dir": None}
        if keep_build:
            result["build_dir"] = str(work_dir)
            result["suite"] = str(suite_zip)
            result["bundle"] = str(dsh_zip)
        return result
    finally:
        if not keep_build:
            expected_parent = Path(output_dir).expanduser().resolve() if output_dir is not None else Path(tempfile.gettempdir()).resolve()
            resolved = work_dir.resolve()
            if resolved.parent == expected_parent and resolved.name.startswith("paperspine5-dsh-sync-") and not _has_link_component(work_dir):
                shutil.rmtree(resolved, ignore_errors=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild and update installed DSH PaperSpine5 bundles from a canonical checkout."
    )
    parser.add_argument("--source-root", type=Path, required=True,
                        help="Canonical PaperSpine5 checkout used to build the suite.")
    parser.add_argument("--target", type=Path, default=None,
                        help="Update exactly this recognized dsh-paperspine5 install.")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Keep the temporary build under this directory.")
    parser.add_argument("--releases-root", type=Path, default=None,
                        help="Override the releases root used for discovery.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = sync_installed_targets(
            args.source_root,
            target=args.target,
            releases_root=args.releases_root,
            output_dir=args.output_dir,
        )
    except DshSyncError as exc:
        print(f"DSH sync failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
