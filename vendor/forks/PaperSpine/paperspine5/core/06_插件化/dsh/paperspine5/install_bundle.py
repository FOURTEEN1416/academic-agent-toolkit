"""Install one DSH bundle at a stable path; preserve the prior copy on failure."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def dsh_command(explicit: str = "") -> list[str]:
    candidate = explicit or os.environ.get("DSH_BIN") or shutil.which("dsh")
    if not candidate:
        raise RuntimeError("Installed DSH not found. Set DSH_BIN or pass --dsh-bin; no download is performed.")
    path = Path(candidate).expanduser().resolve()
    if path.suffix.lower() in {".cmd", ".bat", ".ps1"}:
        path = path.parent / "node_modules/@deepseek-ai/dsh/lib/bin.js"
    if not path.is_file():
        raise RuntimeError("DSH entrypoint does not exist: " + str(path))
    if path.suffix.lower() in {".js", ".mjs", ".cjs"}:
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node.js is required by the installed DSH.")
        return [node, str(path)]
    return [str(path)]


def run(argv: list[str], cwd: Path) -> None:
    subprocess.run(argv, cwd=cwd, check=True, timeout=120)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="web")
    parser.add_argument("--target", type=Path)
    parser.add_argument("--no-link", action="store_true")
    parser.add_argument("--dsh-bin", default="")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.profile):
        parser.error("profile must be a simple DSH profile name")
    source = Path(__file__).resolve().parent
    adapter = json.loads((source / "adapter.json").read_text(encoding="utf-8"))
    target = (args.target or Path.home() / ".paperspine5/releases" / adapter["version"] / "dsh-paperspine5").expanduser().resolve()
    if target == source or source in target.parents or target in source.parents:
        raise RuntimeError("Install target must be separate from the source bundle and its ancestors.")
    if target.exists() and not (target / "package.json").is_file():
        raise RuntimeError("Target is not a recognized DSH bundle; choose an empty directory.")
    if target.exists():
        previous = json.loads((target / "package.json").read_text(encoding="utf-8"))
        if previous.get("name") != "dsh-paperspine5":
            raise RuntimeError("Target belongs to another package.")
    cli = [] if args.no_link else dsh_command(args.dsh_bin)
    core = source / "core"
    if (core / "suite-manifest.json").is_file():
        sys.path.insert(0, str(core / "release"))
        from suite_release import verify_bundle
        verify_bundle(core)
    elif adapter.get("build_id"):
        raise RuntimeError("Packaged DSH bundle is missing its verified core suite.")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + ".staging-" + uuid.uuid4().hex[:12])
    backup = target.with_name(target.name + ".backup-" + uuid.uuid4().hex[:12])
    # copy only the bundle, excluding caches created by a user's inspection.
    shutil.copytree(source, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
    python = sys.executable
    configure = [python, "-B", str(staging / "configure_dsh.py"), "--project-root", str(source)]
    run(configure, staging)
    bound = json.loads((staging / "adapter.json").read_text(encoding="utf-8"))
    run([bound["command"], "-B", str(staging / "scripts/paperspine5_mcp.py"), "health"], staging)
    had_previous = target.exists()
    if had_previous:
        target.rename(backup)
    try:
        staging.rename(target)
        # The embedded interpreter moved with the bundle. Bootstrap at its new path.
        if Path(python).is_relative_to(source):
            python = str(target / Path(python).relative_to(source))
        run([python, "-B", str(target / "configure_dsh.py"), "--project-root", str(source)], target)
        if cli:
            run(cli + ["plugin", "--profile", args.profile, "add", str(target)], target)
    except BaseException:
        if target.exists():
            target.rename(staging)
        if had_previous:
            backup.rename(target)
        raise
    print(json.dumps({"status": "CONFIGURED" if args.no_link else "LINKED", "target": str(target),
                      "profile": args.profile, "backup": str(backup) if had_previous else None}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
