#!/usr/bin/env python3
"""Native smoke of the original updater, current Skill, bundled runtime and Web."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
OLD_HASHES = {
    "windows-amd64": "5fd48b5baba22483bcffdc6078e6ab9aac2ab0d03a0a9214dc17df801ad544d5",
    "linux-x86_64": "d348bc8fe541edcfc95e105519770ba3e56e7243bc3f705771462bc11a23fb95",
    "macos-arm64": "9aedfd5d95b7210e4cb174f69773a5e9d3c3d55528189c6b67cbdece064c660c",
    "macos-x86_64": "a03fdd843aa7761728c6aa525e61a0379644d5335add5261723ee1f0f9c6dff7",
}
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-suite", type=Path, required=True)
    parser.add_argument("--new-suite", type=Path, required=True)
    parser.add_argument("--platform", choices=OLD_HASHES, required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / "website/downloads/manifest.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    result = {"status": "RUNNING", "platform": args.platform, "commands": []}
    launched, owned_pid = None, None

    def run(label, *argv):
        command = list(map(str, argv))
        completed = subprocess.run(command, cwd=work, env=ENV, capture_output=True,
                                   text=True, encoding="utf-8", timeout=240)
        (work / (label + ".stdout.txt")).write_text(completed.stdout, encoding="utf-8")
        (work / (label + ".stderr.txt")).write_text(completed.stderr, encoding="utf-8")
        result["commands"].append({"label": label, "argv": command, "returncode": completed.returncode})
        assert completed.returncode == 0, f"{label}: {completed.stderr or completed.stdout}"
        return json.loads(completed.stdout)

    def http(path=""):
        with urllib.request.urlopen(launched["address"] + path, timeout=10) as response:
            assert response.status == 200
            assert response.headers.get("X-PaperSpine-Instance") == launched["instance_id"]
            return response.read().decode("utf-8")

    try:
        manifest = read(args.manifest)
        artifact, = [item for item in manifest["artifacts"] if item.get("platform") == args.platform
                     and item["kind"].startswith("suite")]
        assert args.new_suite.name == artifact["file"]
        assert args.new_suite.stat().st_size == artifact["bytes"]
        assert digest(args.new_suite) == artifact["sha256"]
        assert digest(args.old_suite) == OLD_HASHES[args.platform]
        skill, control, data = work / "host/skills/paper-spine", work / "control", work / "data"
        data.mkdir()
        for name in ("task.json", "config.json"):
            (data / name).write_bytes(("Existing isolated user " + name + "\n").encode())
        protected = {name: digest(data / name) for name in ("task.json", "config.json")}
        old_entry = work / "old-stable-updater.py"
        with zipfile.ZipFile(args.old_suite) as archive:
            old_entry.write_bytes(archive.read("release/stable_updater.py"))
            for name in archive.namelist():
                if name.startswith("standalone/paper-spine/") and not name.endswith("/"):
                    relative = PurePosixPath(name).relative_to("standalone/paper-spine")
                    assert not relative.is_absolute() and ".." not in relative.parts
                    path = skill.joinpath(*relative.parts)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(name))
        channel = work / "channel.json"
        write(channel, {"protocol": "paperspine-updater/1", "product": "paperspine", "bundle": {
            "url": str(args.new_suite.resolve()), "sha256": artifact["sha256"],
            "product_version": manifest["version"], "build_id": artifact["build_id"], "platform": args.platform}})
        applied = run("old-apply", sys.executable, "-B", old_entry, "apply", "--source", channel,
                      "--skill-root", skill, "--control-root", control, "--data-root", data, "--yes")
        assert applied["status"] == "committed"
        wrapper = skill / "scripts/paperspine_update.py"
        for label in ("preflight-self-refresh", "preflight-current"):
            checked = run(label, sys.executable, "-B", wrapper, "--preflight", "--source", channel,
                          "--skill-root", skill, "--control-root", control, "--config-home", work / "config")
            assert checked["status"] == "up_to_date"
            assert checked["bootstrap_updated"] is (label == "preflight-self-refresh")
        pointer = read(skill / "references/installed-suite.json")
        suite = Path(pointer["suite_root"])
        assert pointer["build_id"] == artifact["build_id"]
        assert (control / "paperspine_update.py").read_bytes() == (suite / "release/stable_updater.py").read_bytes()
        runtime = suite / read(suite / "suite-manifest.json")["runtime"]["python_executable"]
        web, profile = skill / "scripts/paperspine5_web.py", work / "profile"
        launched = run("web-launch", runtime, "-B", web, "launch", "--no-open", "--profile-root", profile)
        assert launched["status"] == "READY" and launched["reused"] is False
        assert Path(launched["profile_root"]).resolve() == profile and not launched["browser_opened"]
        starting = read(profile / ".paperspine5-web/public-starting.json")
        assert starting["process_id"] == launched["process_id"]
        assert starting["binding"] == launched["binding"] and Path(starting["binding"]["project_root"]) == suite
        page = http()
        owned_pid = launched["process_id"]  # Fresh launch + same binding + live instance header prove ownership.
        assert '<dialog id="save-toast"' in page and 'id="task-material-issues"' in page
        assert "task-material-issues" in http("product.js")
        tool = run("host-material-tools", runtime, "-B", web, "host", "tools", "--profile-root", profile,
                   "--tool", "paperspine_authorize_materials")
        assert tool["name"] == "paperspine_authorize_materials"
        schema = json.dumps(tool["inputSchema"])
        assert '"include_paths"' in schema and '"replace"' in schema
        assert {name: digest(data / name) for name in protected} == protected
        result.update(status="PASS", version=manifest["version"], build_id=pointer["build_id"],
                      archive_sha256=artifact["sha256"], user_data_unchanged=protected,
                      bootstrap_updated=True, bundled_runtime_started=True, http_ui_and_tools="PASS")
    except Exception as exc:
        result.update(status="FAIL", error=str(exc))
    finally:
        if owned_pid is not None:
            try:
                http()  # Never terminate a stale PID whose service instance has changed.
                os.kill(owned_pid, signal.SIGTERM)
                result["stopped_owned_pid"] = owned_pid
            except ProcessLookupError:
                result["owned_service_already_stopped"] = True
            except Exception as exc:
                result.update(status="FAIL", cleanup_error=str(exc))
        write(work / "verification.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
