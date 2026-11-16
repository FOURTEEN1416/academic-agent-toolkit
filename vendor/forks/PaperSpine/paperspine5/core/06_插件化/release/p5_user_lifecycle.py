#!/usr/bin/env python3
"""PaperSpine v1 P5 local install, launch, upgrade, migration, and rollback.

Program versions and the bundled Python runtime are immutable.  Mutable paper
state lives under ``profile/data`` so changing the active version cannot move,
replace, or delete tasks, SQLite, decisions, reviews, materials, or downloads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class P5LifecycleError(RuntimeError):
    pass


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(_json_bytes(value)); stream.flush(); os.fsync(stream.fileno())
        os.replace(raw, path)
    finally:
        if os.path.exists(raw): os.unlink(raw)


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big")); digest.update(relative)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def _copytree(source: Path, target: Path) -> None:
    if target.exists(): raise P5LifecycleError(f"immutable target already exists: {target}")
    shutil.copytree(source, target, copy_function=shutil.copy2)


def build_release(source_root: str | Path, runtime_seed: str | Path,
                  dependency_overlay: str | Path, output: str | Path,
                  *, version: str, hardlink_runtime: bool = False) -> dict[str, Any]:
    """Build an unpacked, hash-bound release with a relocatable Windows runtime."""
    source = Path(source_root).resolve(); seed = Path(runtime_seed).resolve()
    overlay = Path(dependency_overlay).resolve(); target = Path(output).resolve()
    if target.exists(): raise P5LifecycleError(f"release output already exists: {target}")
    app = target / "app"; runtime = target / "runtime"
    (app / "03_联合开发" / "src").mkdir(parents=True)
    shutil.copytree(source / "03_联合开发" / "src" / "paperspine_figure_integration",
                    app / "03_联合开发" / "src" / "paperspine_figure_integration")
    shutil.copytree(source / "03_联合开发" / "contracts", app / "03_联合开发" / "contracts")
    # The P1--P4 compatibility kernel is part of the integration package.  Keep
    # an explicit core root for its public constructor without copying the
    # repository-only PaperSpine Skill tree into this business runtime.
    (app / "01_PaperSpine4").mkdir(parents=True)
    (app / "launch.py").write_text(
        "from pathlib import Path\n"
        "import runpy,sys\n"
        "root=Path(__file__).resolve().parent\n"
        "sys.path.insert(0,str(root/'03_联合开发'/'src'))\n"
        "runpy.run_module('paperspine_figure_integration.p2_facades',run_name='__main__')\n",
        encoding="utf-8",
    )
    runtime.mkdir(parents=True)
    copy_runtime = os.link if hardlink_runtime else shutil.copy2
    for name in ("python.exe", "pythonw.exe", "python312.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
        if (seed / name).is_file(): copy_runtime(seed / name, runtime / name)
    if not (runtime / "python.exe").is_file(): raise P5LifecycleError("runtime seed has no python.exe")
    shutil.copytree(seed / "DLLs", runtime / "DLLs", copy_function=copy_runtime)
    (runtime / "Lib").mkdir()
    for item in (seed / "Lib").iterdir():
        if item.name != "site-packages":
            shutil.copytree(item, runtime / "Lib" / item.name, copy_function=copy_runtime) if item.is_dir() else copy_runtime(item, runtime / "Lib" / item.name)
    shutil.copytree(overlay, runtime / "Lib" / "site-packages", copy_function=copy_runtime)
    probe = subprocess.run([runtime / "python.exe", "-B", "-c", "import mcp,jsonschema,sqlite3"],
                           cwd=target, capture_output=True, text=True, timeout=60)
    if probe.returncode: raise P5LifecycleError(f"bundled runtime probe failed: {probe.stderr.strip()}")
    manifest = {"contract": "paperspine5.p5-release", "schema_version": "1.0", "version": version,
                "app_sha256": _tree_hash(app), "runtime_sha256": _tree_hash(runtime)}
    _write_json(target / "release.json", manifest)
    return manifest


class P5Lifecycle:
    def __init__(self, profile: str | Path):
        self.profile = Path(profile).resolve(); self.versions = self.profile / "versions"
        self.runtimes = self.profile / "runtimes"; self.data = self.profile / "data"
        self.current_file = self.profile / "current.json"; self.history = self.profile / "history"

    def _release(self, release: Path) -> dict[str, Any]:
        manifest = json.loads((release / "release.json").read_text(encoding="utf-8"))
        if manifest.get("contract") != "paperspine5.p5-release": raise P5LifecycleError("not a P5 release")
        if _tree_hash(release / "app") != manifest["app_sha256"]: raise P5LifecycleError("app bytes differ")
        if _tree_hash(release / "runtime") != manifest["runtime_sha256"]: raise P5LifecycleError("runtime bytes differ")
        return manifest

    def _migrate(self, legacy: Path | None) -> list[str]:
        self.data.mkdir(parents=True, exist_ok=True)
        if legacy is None or not legacy.exists(): return []
        migrated: list[str] = []
        for item in legacy.iterdir():
            target = self.data / item.name
            if target.exists():
                if item.is_file() and hashlib.sha256(item.read_bytes()).digest() == hashlib.sha256(target.read_bytes()).digest(): continue
                raise P5LifecycleError(f"legacy migration collision: {item.name}")
            shutil.copytree(item, target) if item.is_dir() else shutil.copy2(item, target)
            migrated.append(item.name)
        return migrated

    def _pointer(self) -> dict[str, Any]:
        if not self.current_file.is_file(): raise P5LifecycleError("PaperSpine is not installed")
        return json.loads(self.current_file.read_text(encoding="utf-8"))

    def paths(self) -> dict[str, Path]:
        pointer = self._pointer()
        return {"python": self.runtimes / pointer["runtime_sha256"] / "python.exe",
                "app": self.versions / pointer["version"] / "app", "data": self.data}

    def launch_command(self, mode: str, *, principal: str, session: str = "", port: int = 0) -> list[str]:
        paths = self.paths(); app = paths["app"]; data = paths["data"]
        command = [str(paths["python"]), "-B", str(app / "launch.py"), mode,
                   "--user-data-root", str(data / "tasks"), "--core-root", str(app / "01_PaperSpine4"),
                   "--domain-database", str(data / "domain" / "events.sqlite3"),
                   "--contracts-root", str(app / "03_联合开发" / "contracts"), "--principal-id", principal]
        if session: command += ["--session-id", session]
        if mode == "business-http": command += ["--port", str(port)]
        return command

    @staticmethod
    def _runtime_env(runtime: Path) -> dict[str, str]:
        # Deliberately do not inherit PATH/PYTHONPATH/PYTHONHOME.  SystemRoot is
        # required by Windows process creation; all Python bytes come from the
        # installed content-addressed runtime.
        env = {"PATH": str(runtime), "PYTHONHOME": str(runtime),
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
        if os.environ.get("SystemRoot"): env["SystemRoot"] = os.environ["SystemRoot"]
        return env

    def _probe_target(self, pointer: dict[str, Any]) -> None:
        python = self.runtimes / pointer["runtime_sha256"] / "python.exe"
        app = self.versions / pointer["version"] / "app"
        probe_root = self.profile / ".probe" / pointer["version"]
        if probe_root.exists(): shutil.rmtree(probe_root)
        command = [str(python), "-B", str(app / "launch.py"), "business-http",
                   "--user-data-root", str(probe_root / "tasks"),
                   "--core-root", str(app / "01_PaperSpine4"),
                   "--domain-database", str(probe_root / "domain" / "events.sqlite3"),
                   "--contracts-root", str(app / "03_联合开发" / "contracts"),
                   "--principal-id", "p5-startup-probe", "--session-id", "p5-probe", "--port", "0"]
        process = subprocess.Popen(command, cwd=app, env=self._runtime_env(python.parent),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            line = process.stdout.readline().strip() if process.stdout else ""
            if not line: raise P5LifecycleError("target startup emitted no ready record")
            port = int(json.loads(line)["port"])
            from urllib.request import urlopen
            with urlopen(f"http://127.0.0.1:{port}/api/v1/capabilities", timeout=10) as response:
                if response.status != 200: raise P5LifecycleError("target startup HTTP probe failed")
        except Exception as exc:
            stderr = process.stderr.read() if process.stderr else ""
            raise P5LifecycleError(f"target startup probe failed: {exc}; {stderr[-1000:]}") from exc
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
            if probe_root.exists(): shutil.rmtree(probe_root)

    def _activate(self, release: Path, *, legacy: Path | None, inject_failure: str | None) -> dict[str, Any]:
        manifest = self._release(release); version = manifest["version"]
        self.versions.mkdir(parents=True, exist_ok=True); self.runtimes.mkdir(parents=True, exist_ok=True)
        version_target = self.versions / version; runtime_target = self.runtimes / manifest["runtime_sha256"]
        if not runtime_target.exists(): _copytree(release / "runtime", runtime_target)
        if not version_target.exists():
            version_target.mkdir(); _copytree(release / "app", version_target / "app")
            _write_json(version_target / "release.json", manifest)
        migrated = self._migrate(legacy)
        previous = json.loads(self.current_file.read_text(encoding="utf-8")) if self.current_file.exists() else None
        if inject_failure == "before_activate":
            return {"status": "rolled_back", "version": previous and previous["version"],
                    "requested_target_applied": False, "data_preserved": True, "migrated": migrated}
        pointer = {"version": version, "app_sha256": manifest["app_sha256"],
                   "runtime_sha256": manifest["runtime_sha256"]}
        try:
            self._probe_target(pointer)
        except Exception:
            # Placement is immutable and harmless; the active pointer remains
            # exactly unchanged, which is the automatic rollback boundary.
            raise
        if previous:
            self.history.mkdir(parents=True, exist_ok=True)
            _write_json(self.history / f"before-{version}.json", previous)
        _write_json(self.current_file, pointer)
        return {"status": "committed", "version": version, "requested_target_applied": True,
                "data_preserved": True, "migrated": migrated}

    def install(self, release: str | Path, *, legacy: str | Path | None = None) -> dict[str, Any]:
        if self.current_file.exists(): raise P5LifecycleError("already installed; use upgrade")
        return self._activate(Path(release).resolve(), legacy=Path(legacy).resolve() if legacy else None,
                              inject_failure=None)

    def upgrade(self, release: str | Path, *, inject_failure: str | None = None) -> dict[str, Any]:
        self._pointer()
        return self._activate(Path(release).resolve(), legacy=None, inject_failure=inject_failure)

    def rollback(self) -> dict[str, Any]:
        current = self._pointer(); candidates = sorted(self.history.glob("before-*.json"), key=lambda p: p.stat().st_mtime_ns)
        if not candidates: raise P5LifecycleError("no rollback point")
        previous = json.loads(candidates[-1].read_text(encoding="utf-8"))
        if not (self.versions / previous["version"] / "app").is_dir(): raise P5LifecycleError("rollback app missing")
        if not (self.runtimes / previous["runtime_sha256"] / "python.exe").is_file(): raise P5LifecycleError("rollback runtime missing")
        _write_json(self.current_file, previous)
        return {"status": "committed", "version": previous["version"], "replaced": current["version"],
                "rollback_performed": True, "data_preserved": True}


def main() -> int:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-release"); build.add_argument("--source-root", required=True); build.add_argument("--runtime-seed", required=True); build.add_argument("--dependency-overlay", required=True); build.add_argument("--output", required=True); build.add_argument("--version", required=True); build.add_argument("--hardlink-runtime", action="store_true", help="fast same-volume staging; archive/copy remains portable")
    for name in ("install", "upgrade"):
        cmd = sub.add_parser(name); cmd.add_argument("--profile", required=True); cmd.add_argument("--release", required=True)
        if name == "install": cmd.add_argument("--legacy")
        else: cmd.add_argument("--inject-failure", choices=("before_activate",))
    rollback = sub.add_parser("rollback"); rollback.add_argument("--profile", required=True)
    args = parser.parse_args()
    if args.command == "build-release": result = build_release(args.source_root, args.runtime_seed, args.dependency_overlay, args.output, version=args.version, hardlink_runtime=args.hardlink_runtime)
    else:
        manager = P5Lifecycle(args.profile)
        result = manager.install(args.release, legacy=args.legacy) if args.command == "install" else manager.upgrade(args.release, inject_failure=args.inject_failure) if args.command == "upgrade" else manager.rollback()
    print(json.dumps(result, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
