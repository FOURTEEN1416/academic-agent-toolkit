"""Convert a verified Windows source suite into a platform-specific POSIX suite."""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

import suite_release as core


def rewrite_packaged_runtime(raw: bytes, *, build_id: str) -> bytes:
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise core.ReleaseError("runtime is not UTF-8") from exc
    # Match only the assignment; leave its LF/CRLF terminator byte-for-byte intact.
    pattern = r'(?m)^PRODUCT_BUILD_ID = "[^"\r\n]+"(?=\r?$)'
    rewritten, count = re.subn(pattern, lambda _: f'PRODUCT_BUILD_ID = "{build_id}"', text)
    if count != 1:
        raise core.ReleaseError("runtime build identity anchor is missing or ambiguous")
    return rewritten.encode()


def runtime_payload(runtime_root: Path) -> dict[str, bytes]:
    payload: dict[str, bytes] = {}
    for path in sorted(runtime_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir():
            continue
        relative = path.relative_to(runtime_root).as_posix()
        if "__pycache__" in PurePosixPath(relative).parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if relative.startswith("bin/") and relative != "bin/python3":
            continue
        content = path.resolve().read_bytes() if path.is_symlink() else path.read_bytes()
        payload[f"runtime_vendor/python/{relative}"] = content
    if "runtime_vendor/python/bin/python3" not in payload:
        raise core.ReleaseError("portable runtime has no python/bin/python3")
    return payload


def refresh_canonical_skill(payload: dict[str, bytes], source_root: Path) -> None:
    """Replace both Skill projections, including deletions, from current source."""
    sources = {"01_PaperSpine4/src/skill", "01_PaperSpine4/src/scripts"}
    rules = [rule for rule in core.TREE_RULES if rule.source in sources]
    fresh = dict(item for rule in rules for item in core._iter_tree(source_root, rule))
    prefixes = tuple(rule.destination.rstrip("/") + "/" for rule in rules)
    # Explicit projections (for example the stable updater) may originate outside
    # the Skill trees, but would otherwise be removed by the prefix replacement.
    for rule in core.FILE_RULES:
        if not rule.destination.startswith(prefixes):
            continue
        source = source_root / rule.source
        if not source.is_file():
            raise core.ReleaseError(f"allowlisted source file is missing: {rule.source}")
        if core._is_link_or_junction(source):
            raise core.ReleaseError(f"allowlisted source file is a link/reparse point: {rule.source}")
        destination = core._safe_archive_path(rule.destination)
        if destination in fresh:
            raise core.ReleaseError(f"duplicate allowlist destination: {destination}")
        fresh[destination] = source.read_bytes()
    # Collect first: an unreadable source must not leave a partly updated payload.
    for relative in list(payload):
        if relative.startswith(prefixes):
            del payload[relative]
    payload.update(fresh)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-suite", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dsh-output", type=Path, help="also build the native DSH bundle")
    parser.add_argument("--variant", default="release")
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("platform") not in {"linux-x86_64", "macos-arm64", "macos-x86_64"}:
        raise core.ReleaseError("unsupported portable suite platform")
    core.verify_bundle(args.base_suite.resolve())
    files, _ = core._read_bundle(args.base_suite.resolve())
    payload = {
        path: content for path, content in files.items()
        if path != "suite-manifest.json"
        and not path.startswith("runtime_vendor/windows-py312/")
        and path not in {"runtime_vendor/requirements.lock.json", "paperspine.cmd", "release/stable-update.cmd"}
    }
    source_root = Path(__file__).resolve().parents[2]
    refresh_canonical_skill(payload, source_root)
    replacements = {
        "release/suite_release.py": source_root / "06_插件化/release/suite_release.py",
        "release/product_runtime.py": source_root / "06_插件化/release/product_runtime.py",
        "release/product_probe.py": source_root / "06_插件化/release/product_probe.py",
        "paperspine": source_root / "06_插件化/release/paperspine",
        "release/stable-update": source_root / "06_插件化/release/stable-update",
    }
    for relative, source in replacements.items():
        payload[relative] = source.read_bytes()
    # Use the same adapter source for every platform, including older base suites.
    from dsh_release import ADAPTER_FILES, build_dsh_bundle
    for relative in ADAPTER_FILES:
        payload["adapters/dsh/" + relative] = (
            source_root / "06_插件化/dsh/paperspine5" / relative
        ).read_bytes()
    for relative in ("dsh_release.py", "release_cli.py"):
        payload["release/" + relative] = (source_root / "06_插件化/release" / relative).read_bytes()
    payload.update(runtime_payload(args.runtime_root))
    payload["runtime_vendor/requirements.lock.json"] = core.canonical_json_bytes(lock)
    payload["PORTABLE-VARIANT.txt"] = f"{args.variant}\n".encode()
    source_digest = core._tree_digest(payload)
    build_id = f"w7p-{lock['platform']}-{source_digest[:12]}"
    payload[".codex-plugin/plugin.json"] = core._rewrite_plugin_manifest(
        payload[".codex-plugin/plugin.json"], build_id=build_id
    )
    payload["06_插件化/runtime/paperspine5_runtime.py"] = rewrite_packaged_runtime(
        payload["06_插件化/runtime/paperspine5_runtime.py"], build_id=build_id
    )
    payload["RELEASE-CANDIDATE.md"] = (
        "# PaperSpine5 portable suite\n\n"
        f"Platform `{lock['platform']}`, build `{build_id}`, variant `{args.variant}`. "
        "External manuscript submission remains unauthorized.\n"
    ).encode()
    for path, content in payload.items():
        core._assert_no_absolute_local_paths(path, content)
    manifest = core.build_manifest(payload, source_digest=source_digest, build_id=build_id)
    manifest["suite"]["platform"] = lock["platform"]
    manifest["runtime"] = {
        "platform": lock["platform"],
        "python_executable": lock["python_executable"],
        "executable_paths": ["paperspine", "release/stable-update", lock["python_executable"]],
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    archive_files = {"suite-manifest.json": core.canonical_json_bytes(manifest), **payload}
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        executable = set(manifest["runtime"]["executable_paths"])
        for relative in sorted(archive_files):
            info = zipfile.ZipInfo(relative, date_time=core.FIXED_ZIP_TIME)
            info.create_system = 3
            mode = 0o755 if relative in executable or relative.endswith((".sh", ".ps1")) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, archive_files[relative], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    os.replace(temporary, output)
    verified = core.verify_bundle(output)
    if args.dsh_output:
        build_dsh_bundle(output, args.dsh_output)
    print(json.dumps({
        "status": verified["status"], "platform": verified["platform"],
        "build_id": verified["build_id"], "archive_sha256": verified["archive_sha256"],
        "bytes": output.stat().st_size,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
