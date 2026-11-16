#!/usr/bin/env python3
"""Stable, stdlib-only PaperSpine installer/update bootstrap (protocol v1).

Keep this entry outside versioned installations. New releases supply their own
adapter; never import an old installed application's updater. Channel metadata
is trusted release input, not a signature. A local ZIP requires an explicit hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import urlopen

PROTOCOL = "paperspine-updater/1"
LIMIT = 1024 * 1024 * 1024
CONTROL_FILES = ("paperspine_update.py", "settings.json")
PLATFORMS = {
    "windows-amd64": "windows-amd64", "windows-x86_64": "windows-amd64",
    "linux-x86_64": "linux-x86_64", "linux-amd64": "linux-x86_64",
    "macos-arm64": "macos-arm64", "darwin-arm64": "macos-arm64",
    "macos-x86_64": "macos-x86_64", "darwin-x86_64": "macos-x86_64",
}


def current_platform():
    system, machine = platform.system().lower(), platform.machine().lower()
    machine = {"amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
    key = {"windows": "windows", "linux": "linux", "darwin": "macos"}.get(system, system)
    key = PLATFORMS.get(f"{key}-{machine}")
    if key is None:
        raise ValueError(f"unsupported update platform: {system}/{machine}")
    return key


def select_bundle(channel):
    if channel.get("protocol") != PROTOCOL or channel.get("product") != "paperspine":
        raise ValueError("unsupported update channel")
    selected = current_platform()
    bundles = channel.get("bundles")
    if bundles is not None:
        if not isinstance(bundles, dict):
            raise ValueError("channel bundles must be a platform mapping")
        matches = [value for key, value in bundles.items() if PLATFORMS.get(key) == selected]
        if len(matches) != 1:
            raise ValueError(f"channel must provide exactly one bundle for {selected}")
        bundle = matches[0]
    else:
        bundle = channel.get("bundle")
        # The historical unlabelled v1 channel contained only the Windows suite.
        legacy_platform = (bundle or {}).get("platform", channel.get("platform", "windows-amd64"))
        if PLATFORMS.get(legacy_platform) != selected:
            raise ValueError(f"legacy channel does not provide a bundle for {selected}")
    if not isinstance(bundle, dict) or not isinstance(bundle.get("url"), str):
        raise ValueError("channel bundle must name its archive URL")
    if not re.fullmatch("[a-f0-9]{64}", str(bundle.get("sha256", ""))):
        raise ValueError("channel bundle must provide its SHA-256")
    labelled = bundle.get("platform")
    if labelled is not None and PLATFORMS.get(labelled) != selected:
        raise ValueError("channel bundle platform differs from its mapping")
    return {**bundle, "platform": selected,
            "build_id": bundle.get("build_id", channel.get("build_id")),
            "product_version": bundle.get("product_version", channel.get("product_version"))}


def bundle_reference(source, bundle):
    reference = bundle["url"]
    if reference.startswith("https://"):
        return reference
    if str(source).startswith("https://") or "://" in reference:
        raise ValueError("remote channels must name an absolute HTTPS bundle")
    return str(Path(source).resolve().parent / reference)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def plain(path):
    """Check lexical ancestors before resolve: do not follow junctions on cleanup."""
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise ValueError(f"linked path is not an install target: {item}")
    return path


def inventory(root):
    root = plain(root)
    if not root.exists():
        return None
    if not root.is_dir():
        raise ValueError("installation must be a directory")
    result = {}
    for path in sorted(root.rglob("*")):
        plain(path)
        if path.is_file():
            result[path.relative_to(root).as_posix()] = digest(path)
        elif not path.is_dir():
            raise ValueError("unsupported installation entry")
    return result


def remove_tree(path, parent):
    path, parent = plain(path), plain(parent)
    if path == parent or not path.is_relative_to(parent):
        raise ValueError("cleanup escaped its declared parent")
    inventory(path)
    if path.exists():
        shutil.rmtree(path)


def detect(skill_root):
    root = plain(skill_root)
    if root.name != "paper-spine":
        raise ValueError("select the canonical paper-spine Skill directory")
    if not root.exists():
        return {"kind": "fresh", "root": str(root)}
    skill = root / "SKILL.md"
    if not skill.is_file() or not re.search(
        r"(?m)^name:\s*['\"]?paper-spine['\"]?\s*$", skill.read_text(encoding="utf-8-sig")
    ):
        raise ValueError("existing directory is not a recognized PaperSpine Skill")
    pointer = root / "references" / "installed-suite.json"
    if pointer.is_file():
        info = read(pointer)
        if info.get("contract") != "paperspine5.installed-suite-pointer":
            raise ValueError("unrecognized installed suite pointer")
        result = {"kind": "managed-suite", "root": str(root)}
        for key in ("build_id", "product_version", "archive_sha256", "platform", "suite_root", "updater_entry"):
            if info.get(key) is not None:
                result[key] = info[key]
        # Older adapters wrote only build_id. Read data, never execute old code.
        if info.get("suite_root"):
            manifest = plain(info["suite_root"]) / "suite-manifest.json"
            if manifest.is_file():
                data = read(manifest)
                if data.get("suite", {}).get("build_id") == info.get("build_id"):
                    result.setdefault("product_version", data["suite"].get("product_version"))
        return result
    # V1--V4 distributions share this Skill name; never execute their code.
    markers = ["SKILL.md"]
    if (root / "scripts" / "paperspine_update.py").is_file():
        markers.append("scripts/paperspine_update.py")
    if (root / "_paperspine5").is_dir():
        markers.append("_paperspine5")
    return {"kind": "legacy-standalone", "compatible_legacy_family": "V1-V4",
            "root": str(root), "markers": markers, "task_schema_migrated": False}


@contextmanager
def lock(control):
    control.mkdir(parents=True, exist_ok=True)
    handle = (control / "update.lock").open("a+b")
    handle.seek(0)
    if handle.read(1) == b"":
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError("another updater is running") from None
    try:
        yield
    finally:
        handle.close()  # OS releases the lock even after a process crash.


def fetch(source, target, limit=LIMIT):
    if str(source).startswith("https://"):
        with urlopen(str(source), timeout=30) as response, Path(target).open("wb") as out:
            if urlparse(response.url).scheme != "https":
                raise ValueError("update source redirected away from HTTPS")
            count = 0
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > limit:
                    raise ValueError("update source exceeds size limit")
                out.write(block)
    else:
        if "://" in str(source):
            raise ValueError("update source must be a local file or HTTPS")
        if Path(source).stat().st_size > limit:
            raise ValueError("update source exceeds size limit")
        shutil.copyfile(source, target)


def candidate(source, expected, scratch):
    if not str(source).startswith("https://") and zipfile.is_zipfile(source) and not expected:
        raise ValueError("a direct release ZIP requires its SHA-256")
    scratch.mkdir(parents=True, exist_ok=True)
    downloaded = scratch / "source"
    fetch(source, downloaded)
    channel = None
    if not zipfile.is_zipfile(downloaded):
        channel = read(downloaded)
        bundle = select_bundle(channel)
        fetch(bundle_reference(source, bundle), scratch / "bundle.zip")
        expected = bundle["sha256"]
        downloaded = scratch / "bundle.zip"
    if not expected or not re.fullmatch("[a-f0-9]{64}", expected) or digest(downloaded) != expected:
        raise ValueError("release archive SHA-256 mismatch or missing hash")
    return downloaded, expected, channel



def check(source, *, sha256=None, skill_root, control_root):
    """Read a small channel and installed identity; never download its suite."""
    installation = detect(skill_root)
    if sha256 is not None:
        if not re.fullmatch("[a-f0-9]{64}", sha256):
            raise ValueError("a direct release ZIP requires its SHA-256")
        bundle = {"sha256": sha256, "url": str(source), "platform": current_platform()}
    else:
        with tempfile.TemporaryDirectory(prefix="paperspine-check-") as temporary:
            metadata = Path(temporary) / "channel.json"
            fetch(source, metadata, limit=2 * 1024 * 1024)
            if zipfile.is_zipfile(metadata):
                raise ValueError("a direct release ZIP requires its SHA-256")
            bundle = select_bundle(read(metadata))
            bundle_reference(source, bundle)  # Validate before reporting an available update.
    control = plain(control_root)
    journal_path = control / "transaction.json"
    if journal_path.is_file():
        journal = read(journal_path)
        if journal.get("status") not in ("committed", "rolled_back"):
            return {"status": "recovery_required", "installation": installation,
                    "candidate": bundle, "source": str(source), "update_available": False}
        if (journal.get("status") == "committed"
                and plain(journal["target"]) == plain(skill_root)
                and installation.get("build_id") == journal.get("candidate", {}).get("build_id")):
            installation.setdefault("archive_sha256", journal.get("archive_sha256"))
            installation.setdefault("product_version", journal.get("candidate", {}).get("product_version"))
    installed_hash = installation.get("archive_sha256")
    if installed_hash:
        same = installed_hash == bundle["sha256"]
    else:
        same = bool(bundle.get("build_id") and bundle.get("product_version")
                    and installation.get("build_id") == bundle["build_id"]
                    and installation.get("product_version") == bundle["product_version"])
    for key in ("build_id", "product_version"):
        if bundle.get(key) and installation.get(key) and bundle[key] != installation[key]:
            same = False
    if installation.get("platform") and PLATFORMS.get(installation["platform"]) != bundle["platform"]:
        same = False
    if installation.get("suite_root") and not plain(installation["suite_root"]).is_dir():
        same = False
    return {"status": "up_to_date" if same else "update_available",
            "installation": installation, "candidate": bundle, "source": str(source),
            "update_available": not same}


def auto(source, *, sha256=None, skill_root, control_root, data_roots=(), confirmed=False):
    target, control = plain(skill_root), plain(control_root)
    if control.is_relative_to(target.parent) or target.is_relative_to(control):
        raise ValueError("updater control must be outside Skill discovery and installation roots")
    if confirmed:
        with lock(plain(control_root)):
            _recover(plain(control_root))
    result = check(source, sha256=sha256, skill_root=skill_root, control_root=control_root)
    if result["status"] == "up_to_date" and confirmed:
        with lock(plain(control_root)):
            result["bootstrap_updated"] = _refresh_bootstrap(plain(control_root), plain(skill_root))
    if result["status"] != "update_available" or not confirmed:
        return result
    return apply(source, sha256=sha256, skill_root=skill_root, control_root=control_root,
                 data_roots=data_roots, confirmed=True,
                 expected_identity=result["candidate"]["sha256"])


def _control_inventory(control):
    result = {}
    for name in CONTROL_FILES:
        path = plain(control / name)
        if path.exists() and not path.is_file():
            raise ValueError("updater control entry must be a regular file")
        result[name] = digest(path) if path.exists() else None
    return result


def _replace_file(source, target):
    temporary = target.with_name(target.name + ".new")
    plain(temporary)
    with Path(source).open("rb") as incoming, temporary.open("wb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    os.replace(temporary, target)


def _validate_control_recovery(control, tx, journal):
    if "control_before" not in journal:
        return
    observed = _control_inventory(control)
    for name in CONTROL_FILES:
        before, after = journal["control_before"][name], journal["control_after"][name]
        if observed[name] not in (before, after):
            raise ValueError("updater settings or entry changed after update; retained without overwrite")
        if before is not None and digest(plain(tx / "control-before" / name)) != before:
            raise ValueError("updater control backup differs; retained without overwrite")


def _restore_control(control, tx, journal):
    if "control_before" not in journal:
        return  # Historical protocol-v1 journals did not snapshot control files.
    for name in CONTROL_FILES:
        target = plain(control / name)
        if journal["control_before"][name] is None:
            target.unlink(missing_ok=True)
        else:
            _replace_file(tx / "control-before" / name, target)
    if _control_inventory(control) != journal["control_before"]:
        raise RuntimeError("updater control rollback verification failed")



def _refresh_bootstrap(control, target):
    """Finish a legacy updater's handoff using its locally verified transaction."""
    settings_path, journal_path = control / "settings.json", control / "transaction.json"
    if not settings_path.is_file() or not journal_path.is_file():
        return False
    settings, journal = read(settings_path), read(journal_path)
    if (plain(settings.get("skill_root", control)) != target
            or journal.get("status") != "committed" or plain(journal["target"]) != target):
        return False
    pointer = target / "references" / "installed-suite.json"
    if not pointer.is_file():
        return False
    installed = read(pointer)
    tx = plain(journal["transaction_root"])
    if (tx.parent != control / "transactions" or installed.get("suite_root") is None
            or plain(installed["suite_root"]) != tx / "suite"
            or installed.get("build_id") != journal.get("candidate", {}).get("build_id")):
        raise ValueError("installed suite does not match its committed updater transaction")
    source = plain(tx / "suite" / "release" / "stable_updater.py")
    bootstrap = plain(control / "paperspine_update.py")
    if not source.is_file():
        return False
    if bootstrap.is_file() and digest(source) == digest(bootstrap):
        return False
    _validate_control_recovery(control, tx, journal)
    archive = plain(tx / "bundle.zip")
    expected = journal["archive_sha256"]
    if installed.get("archive_sha256") not in (None, expected) or digest(archive) != expected:
        raise ValueError("installed release archive differs; bootstrap retained")
    with zipfile.ZipFile(archive) as bundle:
        archived_bootstrap = bundle.read("release/stable_updater.py")
    if hashlib.sha256(archived_bootstrap).hexdigest() != digest(source):
        raise ValueError("installed bootstrap differs from its verified archive")
    # Add control snapshots only for old v1 journals, preserving their product backup.
    if "control_before" not in journal:
        journal["control_before"] = _control_inventory(control)
        for name, previous_hash in journal["control_before"].items():
            if previous_hash is not None:
                destination = tx / "control-before" / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(control / name, destination)
    journal["control_after"] = {**_control_inventory(control), "paperspine_update.py": digest(source)}
    journal["status"] = "updating_bootstrap"
    write(journal_path, journal)
    try:
        _replace_file(source, bootstrap)
        if _control_inventory(control) != journal["control_after"]:
            raise ValueError("bootstrap handoff verification failed")
        journal["status"] = "committed"
        write(journal_path, journal)
        write(tx / "receipt.json", journal)
    except Exception:
        _recover(control, explicit=True)
        raise
    return True


def extract(archive, target):
    target.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as bundle:
        seen, size = set(), 0
        for entry in bundle.infolist():
            name = entry.filename
            path = PurePosixPath(name)
            parts = name.rstrip("/").split("/")
            if (path.is_absolute() or any(p in ("", ".", "..") for p in parts)
                    or "\\" in name or ":" in name or name.casefold() in seen
                    or any(p.endswith((".", " ")) for p in parts)
                    or any(p.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL",
                        *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]} for p in parts)
                    or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError("unsafe or duplicate release archive path")
            seen.add(name.casefold())
            size += entry.file_size
            if size > 3 * LIMIT:
                raise ValueError("unpacked release exceeds limit")
        bundle.extractall(target)
        if os.name != "nt":
            for entry in bundle.infolist():
                mode = (entry.external_attr >> 16) & 0o777
                if mode and not entry.is_dir():
                    (target / entry.filename).chmod(mode)


def adapter_call(suite, prepared, action, tx):
    envelope = read(suite / "updater-protocol.json")
    if envelope.get("protocol") != PROTOCOL or envelope.get("product") != "paperspine":
        raise ValueError("release does not support the stable updater protocol")
    if tuple(envelope["python_min"]) > sys.version_info[:2]:
        raise ValueError("this release requires a newer Python; old installation preserved")
    adapter = plain(suite / envelope["adapter"])
    if not adapter.is_relative_to(suite) or not adapter.is_file():
        raise ValueError("adapter must be inside the verified archive")
    request, response = tx / f"{action}-request.json", tx / f"{action}-response.json"
    response.unlink(missing_ok=True)
    write(request, {"protocol": PROTOCOL, "action": action, "bundle_root": str(suite),
                    "bundle_archive": str(tx / "bundle.zip"), "prepared_root": str(prepared)})
    result = subprocess.run([sys.executable, "-B", str(adapter), str(request), str(response)],
                            cwd=suite, capture_output=True, timeout=180,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
    if result.returncode or not response.is_file():
        raise RuntimeError(f"release adapter {action} failed (exit {result.returncode})")
    reply = read(response)
    if reply.get("status") != "PASS" or reply.get("protocol") != PROTOCOL:
        raise ValueError("release adapter did not pass")
    return reply


def _recover(control, *, explicit=False):
    journal_path = control / "transaction.json"
    if not journal_path.exists():
        return {"status": "noop"}
    journal = read(journal_path)
    if journal["status"] == "rolled_back":
        return journal
    if journal["status"] == "committed" and not explicit:
        return journal
    target, backup = plain(journal["target"]), plain(journal["backup"])
    tx = plain(journal["transaction_root"])
    if tx.parent != control / "transactions" or backup != tx / "previous" or target.name != "paper-spine":
        raise ValueError("invalid recovery paths")
    if journal["before"] is not None and inventory(backup) != journal["before"]:
        raise ValueError("rollback backup differs; current installation retained")
    _validate_control_recovery(control, tx, journal)
    observed = inventory(target)
    if observed not in (None, journal["before"], journal["after"]):
        raise ValueError("installation changed after update; retained without overwrite")
    if journal["before"] is None:
        if observed is not None:
            remove_tree(target, target.parent)
    elif observed != journal["before"]:
        remove_tree(target, target.parent)
        shutil.copytree(backup, target)
    if inventory(target) != journal["before"]:
        raise RuntimeError("rollback verification failed")
    _restore_control(control, tx, journal)
    journal["status"] = "rolled_back"
    write(journal_path, journal)
    write(tx / "receipt.json", journal)
    return journal


def apply(source, *, sha256=None, skill_root, control_root, data_roots=(), confirmed=False,
          fault_at=None, expected_identity=None):
    target, control = plain(skill_root), plain(control_root)
    if control.is_relative_to(target.parent) or target.is_relative_to(control):
        raise ValueError("updater control must be outside Skill discovery and installation roots")
    if not confirmed:
        return {"status": "check", "installation": detect(target), "source": str(source)}
    with lock(control):
        _recover(control)
        prestate = detect(target)
        before = inventory(target)
        roots = [str(plain(p)) for p in data_roots]
        if any(not Path(p).exists() for p in roots):
            raise ValueError("explicit data root does not exist")
        if any(control.is_relative_to(Path(p)) or Path(p).is_relative_to(control) for p in roots):
            raise ValueError("user data root must be separate from updater control")
        operation = uuid.uuid4().hex
        tx = control / "transactions" / operation
        tx.mkdir(parents=True)
        with tempfile.TemporaryDirectory(prefix="paperspine-update-") as temporary:
            archive, identity, channel = candidate(source, sha256, Path(temporary))
            if expected_identity is not None and identity != expected_identity:
                raise ValueError("release channel changed during the update; check again")
            # Version-addressed storage is private to the bootstrap, never the data root.
            suite = tx / "suite"
            extract(archive, suite)
            shutil.copyfile(archive, tx / "bundle.zip")
        prepared, backup = tx / "prepared", tx / "previous"
        result = adapter_call(suite, prepared, "prepare", tx)
        if not (prepared / "SKILL.md").is_file():
            raise ValueError("candidate adapter omitted the Skill")
        release_platform = result.get("platform")
        manifest_path = suite / "suite-manifest.json"
        if release_platform is None and manifest_path.is_file():
            release_platform = read(manifest_path).get("runtime", {}).get("platform")
        if release_platform is not None and PLATFORMS.get(release_platform) != current_platform():
            raise ValueError("verified bundle platform differs from this computer")
        if channel:
            selected = select_bundle(channel)
            for key in ("build_id", "product_version"):
                if selected.get(key) and result.get(key) != selected[key]:
                    raise ValueError(f"verified bundle {key} differs from channel metadata")
            if result.get("platform") and PLATFORMS.get(result["platform"]) != selected["platform"]:
                raise ValueError("verified bundle platform differs from channel metadata")
        after = inventory(prepared)
        controls_before = _control_inventory(control)
        for name, previous_hash in controls_before.items():
            if previous_hash is not None:
                destination = tx / "control-before" / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(control / name, destination)
        control_new = tx / "control-new"
        control_new.mkdir()
        # Take the next bootstrap from the already hash-verified release, not __file__.
        next_bootstrap = plain(suite / "release" / "stable_updater.py")
        if not next_bootstrap.is_file():
            raise ValueError("verified release omitted its stable updater")
        shutil.copyfile(next_bootstrap, control_new / "paperspine_update.py")
        previous_settings = read(control / "settings.json") if controls_before["settings.json"] else {}
        write(control_new / "settings.json", {
            "protocol": PROTOCOL, "skill_root": str(target),
            "channel": str(source) if channel else previous_settings.get("channel"),
            "data_roots": roots,
        })
        controls_after = _control_inventory(control_new)
        if before is not None:
            shutil.copytree(target, backup)
            if inventory(backup) != before or inventory(target) != before:
                raise ValueError("old installation changed during snapshot; retry when idle")
        if fault_at == "before_switch":
            raise RuntimeError("injected before switch")
        stage = target.parent / (".paperspine-stage-" + operation)
        retired = target.parent / (".paperspine-retired-" + operation)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(prepared, stage)
        journal = {"protocol": PROTOCOL, "status": "switching", "operation_id": operation,
                   "transaction_root": str(tx), "target": str(target), "backup": str(backup),
                   "before": before, "after": after, "archive_sha256": identity,
                   "control_before": controls_before, "control_after": controls_after,
                   "previous": prestate, "candidate": result,
                   "retained_data_roots": roots, "legacy_files": str(backup) if before is not None else None,
                   "requires_host_reload": True, "task_schema_migrated": False}
        write(control / "transaction.json", journal)
        try:
            if inventory(target) != before:
                raise ValueError("installation changed before switch")
            if target.exists():
                os.replace(target, retired)
            if fault_at == "after_retire":
                raise RuntimeError("injected after retire")
            os.replace(stage, target)
            if fault_at == "after_switch":
                raise RuntimeError("injected after switch")
            adapter_call(suite, target, "probe", tx)
            if inventory(target) != after:
                raise ValueError("installed candidate changed during health check")
            if _control_inventory(control) != controls_before:
                raise ValueError("updater entry or settings changed before switch")
            for name in CONTROL_FILES:
                _replace_file(control_new / name, control / name)
                if fault_at == "after_bootstrap" and name == "paperspine_update.py":
                    raise RuntimeError("injected after bootstrap switch")
            if _control_inventory(control) != controls_after:
                raise ValueError("updater control verification failed")
            journal["status"] = "committed"
            write(control / "transaction.json", journal)
            write(tx / "receipt.json", journal)
            return journal
        except Exception:
            _recover(control, explicit=True)
            raise
        finally:
            # Both paths are exact operation-owned siblings, checked before removal.
            remove_tree(stage, target.parent)
            remove_tree(retired, target.parent)


def main():
    parser = argparse.ArgumentParser(description="PaperSpine stable installer and updater")
    parser.add_argument("command", choices=("detect", "check", "auto", "apply", "rollback", "recover"))
    parser.add_argument("--control-root", default=str(Path.home() / ".paperspine5" / "updater"))
    parser.add_argument("--skill-root")
    parser.add_argument("--source", help="trusted local ZIP or stable channel JSON/HTTPS URL")
    parser.add_argument("--sha256", help="required for a direct ZIP")
    parser.add_argument("--data-root", action="append", default=None)
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    control = plain(args.control_root)
    settings = read(control / "settings.json") if (control / "settings.json").is_file() else {}
    skill = args.skill_root or settings.get("skill_root") or str(
        Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills" / "paper-spine")
    if args.command == "detect":
        result = {"status": "PASS", "installation": detect(skill), "updater_protocol": PROTOCOL,
                  "data_roots": settings.get("data_roots", []), "channel": settings.get("channel")}
    elif args.command in ("rollback", "recover"):
        if not args.yes:
            raise ValueError("rollback/recovery requires the user's update authorization (--yes)")
        with lock(control):
            result = _recover(control, explicit=args.command == "rollback")
    else:
        source = args.source or settings.get("channel")
        if not source:
            raise ValueError("no release channel configured; supply the official channel or exact ZIP")
        if args.command == "check":
            result = check(source, sha256=args.sha256, skill_root=skill, control_root=control)
        else:
            operation = auto if args.command == "auto" else apply
            result = operation(source, sha256=args.sha256, skill_root=skill, control_root=control,
                               data_roots=args.data_root if args.data_root is not None else settings.get("data_roots", []),
                               confirmed=args.yes)
    # Receipts stay on disk; avoid flooding user output with file inventories.
    print(json.dumps({k: v for k, v in result.items() if k not in ("before", "after")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False))
        raise SystemExit(1)
