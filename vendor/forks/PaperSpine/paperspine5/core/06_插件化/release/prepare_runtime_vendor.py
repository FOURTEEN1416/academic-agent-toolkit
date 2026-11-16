"""Regenerate vendor bytes from a pinned interpreter ZIP and an offline wheelhouse.

Developer build tool only. The destination must not exist; never mutates an
installed profile or silently fetches packages from the network.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interpreter-zip", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads((Path(__file__).resolve().parents[1] / "runtime_vendor/requirements.lock.json").read_text(encoding="utf-8"))
    if args.destination.exists():
        raise SystemExit("Destination must be a new directory")
    if hashlib.sha256(args.interpreter_zip.read_bytes()).hexdigest() != lock["interpreter"]["sha256"]:
        raise SystemExit("Interpreter archive does not match requirements.lock.json")
    args.destination.mkdir(parents=True)
    with zipfile.ZipFile(args.interpreter_zip) as archive:
        for name in archive.namelist():
            target = (args.destination / name).resolve()
            if not target.is_relative_to(args.destination.resolve()):
                raise SystemExit("Unsafe interpreter archive path")
        archive.extractall(args.destination)
    with tempfile.TemporaryDirectory(prefix="paperspine-vendor-build-") as temporary:
        requirements = Path(temporary) / "requirements.txt"
        requirements.write_text("\n".join(lock["packages"]) + "\n", encoding="utf-8")
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
            "--no-compile", "--only-binary=:all:", "--find-links", str(args.wheelhouse.resolve()),
            "--target", str(args.destination.resolve()), "-r", str(requirements)], check=True)
    for direct_url in args.destination.glob("*.dist-info/direct_url.json"):
        direct_url.unlink()
    print("Vendor bytes generated; build and run test_product_runtime before acceptance.")


if __name__ == "__main__":
    main()
