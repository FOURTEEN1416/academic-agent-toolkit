"""Project the native DSH adapter from an already verified platform suite."""
from __future__ import annotations

import json
import os
import stat
import zipfile
from pathlib import Path

try:
    from . import suite_release as core
except ImportError:
    import suite_release as core

ADAPTER_PREFIX = "adapters/dsh/"
ADAPTER_FILES = (
    "package.json", "adapter.json", "cordis.patch.yml", "configure_dsh.py",
    "install_bundle.py", "install.ps1", "install.sh", "README.md", "INSTALL.md",
    "scripts/paperspine5_mcp.py",
)


def build_dsh_bundle(suite: str | Path, output: str | Path) -> dict:
    verified = core.verify_bundle(suite)
    files, _ = core._read_bundle(Path(suite).resolve())
    manifest = json.loads(files["suite-manifest.json"])
    payload = {"core/" + path: content for path, content in files.items()}
    for relative in ADAPTER_FILES:
        source = ADAPTER_PREFIX + relative
        if source not in files:
            raise core.ReleaseError("suite has no current DSH adapter: " + source)
        payload[relative] = files[source]
    if "__PAPERSPINE5_PACKAGE_ROOT__" not in payload["cordis.patch.yml"].decode("utf-8"):
        raise core.ReleaseError("DSH adapter is already bound to an installation")
    for relative in ("package.json", "adapter.json"):
        metadata = json.loads(payload[relative])
        metadata["version"] = manifest["suite"]["product_version"]
        if relative == "adapter.json":
            metadata.update(build_id=verified["build_id"], platform=verified["platform"])
        payload[relative] = core.canonical_json_bytes(metadata)
    payload["DSH-BUILD.json"] = core.canonical_json_bytes({
        "suite_build_id": verified["build_id"], "platform": verified["platform"],
        "suite_archive_sha256": verified["archive_sha256"],
    })
    target = Path(output).resolve()
    if target == Path(suite).resolve() or target.exists():
        raise core.ReleaseError("DSH output already exists or is the source; use a new candidate path")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    executable = {"core/" + p for p in manifest["runtime"].get("executable_paths", [])}
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path, content in sorted(payload.items()):
                info = zipfile.ZipInfo(path, date_time=core.FIXED_ZIP_TIME)
                info.create_system = 3
                mode = 0o755 if path in executable or path.endswith((".sh", ".ps1")) else 0o644
                info.external_attr = (stat.S_IFREG | mode) << 16
                archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    receipt = {"status": "PASS", "platform": verified["platform"],
               "build_id": verified["build_id"], "archive_sha256": core.sha256_file(target),
               "bytes": target.stat().st_size, "files": len(payload)}
    target.with_suffix(target.suffix + ".receipt.json").write_bytes(core.canonical_json_bytes(receipt))
    return receipt
