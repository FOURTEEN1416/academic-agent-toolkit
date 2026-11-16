"""Prepare a relocatable POSIX Python runtime from a pinned standalone archive."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def portable_archive_filter(member: tarfile.TarInfo, destination: str) -> tarfile.TarInfo | None:
    parts = PurePosixPath(member.name).parts
    # The upstream stripped runtime contains a very large terminfo alias forest,
    # including cyclic aliases that Python's safe tar filter correctly rejects.
    # PaperSpine does not consume this private terminfo database and POSIX hosts
    # already provide one, so omit it rather than weakening safe extraction.
    if parts[:3] == ("python", "share", "terminfo"):
        return None
    return tarfile.data_filter(member, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--interpreter-archive", type=Path, required=True)
    parser.add_argument("--base-suite", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if sha256(args.interpreter_archive) != lock["interpreter"]["sha256"]:
        raise SystemExit("portable interpreter SHA-256 mismatch")
    if args.destination.exists():
        raise SystemExit("portable runtime destination must not exist")
    args.destination.mkdir(parents=True)
    with tarfile.open(args.interpreter_archive, "r:gz") as archive:
        archive.extractall(args.destination, filter=portable_archive_filter)
    python_root = args.destination / "python"
    python = python_root / "bin" / "python3"
    if not python.is_file():
        raise SystemExit("portable runtime has no python/bin/python3")
    # python-build-standalone publishes python3 as a relative symlink.  The
    # suite ZIP intentionally stores a single stable launcher path, so turn
    # that symlink into the real executable before pruning the other bin files.
    if python.is_symlink():
        resolved = python.resolve(strict=True)
        materialized = python.with_name(".paperspine-python3")
        shutil.copy2(resolved, materialized)
        python.unlink()
        materialized.replace(python)
    python.chmod(0o755)
    subprocess.run([str(python), "-I", "-m", "ensurepip", "--upgrade"], check=True)
    packages = [
        requirement for requirement in lock["packages"]
        if not requirement.lower().startswith(("mcp==", "mcp-types==", "pywin32=="))
    ]
    with tempfile.TemporaryDirectory(prefix="paperspine-posix-requirements-") as temporary:
        requirements = Path(temporary) / "requirements.txt"
        requirements.write_text("\n".join(packages) + "\n", encoding="utf-8")
        subprocess.run([
            str(python), "-I", "-m", "pip", "install", "--disable-pip-version-check",
            "--no-compile", "--only-binary=:all:", "-r", str(requirements),
        ], check=True)
    site = subprocess.check_output([
        str(python), "-I", "-c", "import site; print(site.getsitepackages()[0])"
    ], text=True).strip()
    site_packages = Path(site)
    prefixes = (
        "runtime_vendor/windows-py312/mcp/",
        "runtime_vendor/windows-py312/mcp_types/",
        "runtime_vendor/windows-py312/mcp-0.0.1.dev1+d060b36.dist-info/",
        "runtime_vendor/windows-py312/mcp_types-0.0.1.dev1+d060b36.dist-info/",
    )
    with zipfile.ZipFile(args.base_suite) as archive:
        matched = 0
        for info in archive.infolist():
            prefix = next((item for item in prefixes if info.filename.startswith(item)), None)
            if prefix is None or info.is_dir():
                continue
            relative = info.filename[len("runtime_vendor/windows-py312/"):]
            target = site_packages / Path(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
            matched += 1
    if matched < 10:
        raise SystemExit("base suite did not provide the pinned MCP v2 packages")
    for path in sorted(python_root.rglob("*"), reverse=True):
        if path.is_file() and (path.suffix in {".pyc", ".pyo"} or path.name == "direct_url.json"):
            path.unlink()
        elif path.is_dir() and path.name == "__pycache__":
            shutil.rmtree(path)
    bin_dir = python_root / "bin"
    for item in bin_dir.iterdir():
        if item.name not in {"python3"}:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    result = subprocess.run([
        str(python), "-I", "-B", "-X", "utf8", "-c",
        "import json,importlib.metadata as m; print(json.dumps({'python':m.version('mcp'),'pydantic':m.version('pydantic')}))",
    ], check=True, capture_output=True, text=True)
    print(json.dumps({"status": "PASS", "platform": lock["platform"], "probe": json.loads(result.stdout)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
