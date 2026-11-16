"""V5 package adapter for the permanently supported updater/1 envelope.

Only this version-owned file knows the suite layout. The bootstrap executes it
after checking the release archive against the selected channel's SHA-256.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_release import verify_bundle
from stable_updater import PLATFORMS, current_platform



def restore_executables(suite: Path, verified: dict, *, posix: bool | None = None) -> None:
    """Repair modes lost by the original v1 bootstrap's zipfile extraction."""
    if not (os.name != "nt" if posix is None else posix):
        return
    root = suite.resolve()
    paths = []
    for relative in verified["manifest"]["runtime"]["executable_paths"]:
        if (not isinstance(relative, str) or PurePosixPath(relative).is_absolute()
                or "\\" in relative or ":" in relative
                or any(part in ("", ".", "..") for part in relative.split("/"))):
            raise ValueError("executable path must stay inside the verified suite")
        path = root / relative
        if (not path.is_file() or not path.resolve().is_relative_to(root)
                or any(item.is_symlink() for item in (path, *path.parents) if item != root and item.is_relative_to(root))):
            raise ValueError("executable path must be a real non-linked suite file")
        paths.append(path)
    for path in paths:
        path.chmod(stat.S_IMODE(path.stat().st_mode) | 0o111)


def handle(request: dict) -> dict:
    if request["protocol"] != "paperspine-updater/1":
        raise ValueError("unsupported updater protocol")
    suite = Path(request["bundle_root"])
    verified = verify_bundle(Path(request["bundle_archive"]))
    if PLATFORMS.get(verified["platform"]) != current_platform():
        raise ValueError("release bundle does not support this operating system and architecture")
    restore_executables(suite, verified)
    target = Path(request["prepared_root"])
    if request["action"] == "prepare":
        shutil.copytree(suite / "standalone" / "paper-spine", target)
        pointer = {
            "contract": "paperspine5.installed-suite-pointer",
            "schema_version": "1.0", "product_id": "paperspine5",
            "build_id": verified["build_id"],
            "product_version": verified["product_version"],
            "archive_sha256": verified["archive_sha256"],
            "platform": verified["platform"],
            "updater_entry": "release/stable_updater.py",
            "content_index_sha256": verified["content_index_sha256"],
            "suite_root": str(suite),
        }
        (target / "references" / "installed-suite.json").write_text(
            json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8")
    elif request["action"] != "probe":
        raise ValueError("unsupported adapter action")
    # Exercise the actual installed launcher without starting a paper/service.
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
    result = subprocess.run(
        [sys.executable, "-B", str(target / "scripts" / "paperspine5_web.py"), "--help"],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=45,
    )
    if result.returncode or "launch" not in result.stdout or "host" not in result.stdout:
        raise RuntimeError("installed Web/host launcher probe failed")
    return {"protocol": "paperspine-updater/1", "status": "PASS",
            "build_id": verified["build_id"], "product_version": verified["product_version"],
            "platform": verified["platform"], "probe": "real-launcher-help", "task_schema_migrated": False}


if __name__ == "__main__":
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    answer = handle(request)
    Path(sys.argv[2]).write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
