#!/usr/bin/env python3
"""Check and update local PaperSpine installs.

The updater is deliberately self-contained and standard-library only so it can
run from Codex, Claude Code, OpenClaw, or a plain terminal.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST_URL = (
    "https://raw.githubusercontent.com/WUBING2023/PaperSpine/main/dist/paperspine_version.json"
)
# Stage 5a: archive_url points to a fixed tag so users never pull in-flight main.
DEFAULT_ARCHIVE_URL = "https://github.com/WUBING2023/PaperSpine/archive/refs/tags/v4.0.0.zip"
CONFIG_HOME_ENV = "PAPERSPINE_CONFIG_HOME"
VERSION_FILE = "paperspine_version.json"
INSTALL_STATE_FILE = "install_state.json"
UPDATE_POLICY_FILE = "update_policy.json"
UPDATE_POLICY_SCHEMA = "1.0"
DEFAULT_AUTO_UPDATE_INTERVAL_HOURS = 24

# Stage 2a: published suite is a single orchestrator skill.
SUITE_SKILLS = (
    "paper-spine",
)


class UpdateError(RuntimeError):
    """Raised for expected updater failures."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check and update local PaperSpine installs.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true", help="Only check whether an update is available.")
    mode.add_argument(
        "--auto",
        action="store_true",
        help="Run the opt-in, interval-limited automatic update preflight.",
    )
    mode.add_argument(
        "--enable-auto-update",
        action="store_true",
        help="Enable automatic updates for later PaperSpine launches.",
    )
    mode.add_argument(
        "--disable-auto-update",
        action="store_true",
        help="Disable automatic updates.",
    )
    mode.add_argument(
        "--auto-status",
        action="store_true",
        help="Show automatic-update policy and last check result without using the network.",
    )
    parser.add_argument(
        "--target",
        choices=("all", "codex", "claude", "openclaw", "hermes"),
        default="all",
        help="Install target to update. Default: all.",
    )
    parser.add_argument(
        "--config-home",
        type=Path,
        default=None,
        help="Override the PaperSpine global config directory. Default: ~/.paperspine.",
    )
    parser.add_argument(
        "--repo-archive",
        default=None,
        help="Optional repo zip, repo directory, or URL. Tests can pass a local zip.",
    )
    parser.add_argument("--yes", action="store_true", help="Update without interactive confirmation.")
    parser.add_argument(
        "--interval-hours",
        type=int,
        default=None,
        help="Automatic-update interval (1-168 hours). Used with --enable-auto-update.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --auto, bypass the interval once; automatic updates must still be enabled.",
    )
    args = parser.parse_args()
    if args.interval_hours is not None and not 1 <= args.interval_hours <= 168:
        parser.error("--interval-hours must be between 1 and 168.")
    if args.interval_hours is not None and not args.enable_auto_update:
        parser.error("--interval-hours requires --enable-auto-update.")
    if args.force and not args.auto:
        parser.error("--force requires --auto.")
    return args


def config_home(args: argparse.Namespace) -> Path:
    if args.config_home is not None:
        return args.config_home
    env_value = os.environ.get(CONFIG_HOME_ENV)
    if env_value:
        return Path(env_value)
    return Path.home() / ".paperspine"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise UpdateError(f"JSON root must be an object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def default_update_policy() -> dict[str, Any]:
    return {
        "schema_version": UPDATE_POLICY_SCHEMA,
        "auto_update": False,
        "interval_hours": DEFAULT_AUTO_UPDATE_INTERVAL_HOURS,
        "target": "all",
        "last_checked_at": None,
        "last_result": "never_checked",
        "last_error": None,
    }


def load_update_policy(config_dir: Path) -> dict[str, Any]:
    path = config_dir / UPDATE_POLICY_FILE
    if not path.exists():
        return default_update_policy()
    try:
        stored = read_json(path)
    except (OSError, json.JSONDecodeError, UpdateError) as exc:
        raise UpdateError(f"Invalid automatic-update policy: {path} ({exc})") from exc
    policy = default_update_policy()
    policy.update(stored)
    if policy.get("schema_version") != UPDATE_POLICY_SCHEMA:
        raise UpdateError(
            f"Unsupported automatic-update policy schema: {policy.get('schema_version')}"
        )
    interval = policy.get("interval_hours")
    if not isinstance(interval, int) or not 1 <= interval <= 168:
        raise UpdateError("Automatic-update interval must be an integer between 1 and 168 hours.")
    if policy.get("target") not in {"all", "codex", "claude", "openclaw", "hermes"}:
        raise UpdateError(f"Unsupported automatic-update target: {policy.get('target')}")
    if not isinstance(policy.get("auto_update"), bool):
        raise UpdateError("Automatic-update policy auto_update must be true or false.")
    return policy


def save_update_policy(config_dir: Path, policy: dict[str, Any]) -> None:
    write_json(config_dir / UPDATE_POLICY_FILE, policy)


def auto_update_due(policy: dict[str, Any], *, now: datetime | None = None) -> bool:
    last_checked = policy.get("last_checked_at")
    if not last_checked:
        return True
    try:
        checked_at = datetime.fromisoformat(str(last_checked).replace("Z", "+00:00"))
    except ValueError as exc:
        raise UpdateError(f"Invalid last_checked_at in automatic-update policy: {last_checked}") from exc
    if checked_at.tzinfo is None:
        raise UpdateError("Automatic-update policy last_checked_at must include a timezone.")
    current_time = now or utc_now()
    return current_time >= checked_at + timedelta(hours=int(policy["interval_hours"]))


def describe_update_policy(policy: dict[str, Any]) -> str:
    state = "enabled" if policy["auto_update"] else "disabled"
    return (
        f"PaperSpine automatic updates: {state}; interval={policy['interval_hours']}h; "
        f"target={policy['target']}; last_checked={policy.get('last_checked_at') or 'never'}; "
        f"last_result={policy.get('last_result') or 'unknown'}"
    )


def version_key(version: str) -> tuple[int, int, int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?", version.strip())
    if not match:
        raise UpdateError(f"Unsupported PaperSpine version: {version}")
    major, minor, patch = (int(match.group(i)) for i in range(1, 4))
    rc = match.group(4)
    if rc is None:
        return (major, minor, patch, 1, 0)
    return (major, minor, patch, 0, int(rc))


def compare_versions(left: str, right: str) -> int:
    left_key = version_key(left)
    right_key = version_key(right)
    if left_key == right_key:
        return 0
    return -1 if left_key < right_key else 1


def find_local_version_file() -> Path | None:
    script_path = Path(__file__).resolve()
    candidates: list[Path] = []
    for parent in script_path.parents:
        candidates.append(parent / VERSION_FILE)
        candidates.append(parent / "dist" / VERSION_FILE)
    for path in candidates:
        if path.exists():
            return path
    return None


def local_version(config_dir: Path) -> str:
    state_path = config_dir / INSTALL_STATE_FILE
    if state_path.exists():
        state = read_json(state_path)
        version = state.get("installed_version")
        if isinstance(version, str) and version:
            return version
    version_path = find_local_version_file()
    if version_path is not None:
        data = read_json(version_path)
        version = data.get("version")
        if isinstance(version, str) and version:
            return version
    return "0.0.0"


def load_manifest_from_url(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise UpdateError(f"Unable to fetch PaperSpine manifest: {url} ({exc})") from exc
    data = json.loads(body)
    if not isinstance(data, dict):
        raise UpdateError("Remote manifest JSON root must be an object.")
    return data


def extract_zip(zip_path: Path, temp_dir: Path) -> Path:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(temp_dir)
    except zipfile.BadZipFile as exc:
        raise UpdateError(f"Invalid PaperSpine archive: {zip_path}") from exc
    return find_repo_root(temp_dir)


def download_archive(url: str, temp_dir: Path) -> Path:
    archive_path = temp_dir / "paperspine-update.zip"
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            archive_path.write_bytes(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise UpdateError(f"Unable to download PaperSpine archive: {url} ({exc})") from exc
    return extract_zip(archive_path, temp_dir / "extracted")


def find_repo_root(base: Path) -> Path:
    candidates = [base]
    candidates.extend(path for path in base.iterdir() if path.is_dir())
    for candidate in candidates:
        if (candidate / "dist" / VERSION_FILE).exists() and (candidate / "install.ps1").exists():
            return candidate
    raise UpdateError(f"Unable to locate PaperSpine repository root in: {base}")


def repo_root_from_archive(repo_archive: str | None, manifest: dict[str, Any], temp_dir: Path) -> Path:
    archive_value = repo_archive or str(manifest.get("archive_url") or DEFAULT_ARCHIVE_URL)
    archive_path = Path(archive_value)
    if archive_path.exists():
        if archive_path.is_dir():
            return archive_path
        return extract_zip(archive_path, temp_dir / "extracted")
    if archive_value.startswith("file://"):
        file_path = Path(urllib.request.url2pathname(archive_value.removeprefix("file://")))
        if file_path.is_dir():
            return file_path
        return extract_zip(file_path, temp_dir / "extracted")
    return download_archive(archive_value, temp_dir)


def manifest_from_archive(repo_archive: str) -> dict[str, Any]:
    archive_path = Path(repo_archive)
    with tempfile.TemporaryDirectory(prefix="paperspine-manifest-") as tmp:
        temp_dir = Path(tmp)
        if archive_path.exists() and archive_path.is_dir():
            root = archive_path
        elif archive_path.exists():
            root = extract_zip(archive_path, temp_dir / "extracted")
        elif repo_archive.startswith("file://"):
            file_path = Path(urllib.request.url2pathname(repo_archive.removeprefix("file://")))
            root = file_path if file_path.is_dir() else extract_zip(file_path, temp_dir / "extracted")
        else:
            raise UpdateError("--repo-archive must be a local path when used for manifest discovery.")
        return read_json(root / "dist" / VERSION_FILE)


def latest_manifest(args: argparse.Namespace) -> dict[str, Any]:
    if args.repo_archive:
        return manifest_from_archive(args.repo_archive)
    return load_manifest_from_url(DEFAULT_MANIFEST_URL)


def validate_repo(root: Path) -> dict[str, Any]:
    """Validate a downloaded V4 single-skill PaperSpine package.

    Stage V4 / issues #13 + #6: the suite is a single ``paper-spine``
    orchestrator skill published per host.

    Forward-compatibility (issue #13): only *core* payload — the version
    manifest, the per-host skill, and the command/prompt entry points the
    updater actually installs — is required, and a missing core file aborts.
    Docs and root installers (``README*``, ``install.*``) are *optional*: a
    missing optional file only warns, so a stale updater no longer rejects a
    newer package that renamed or dropped a doc (the exact failure in #13, e.g.
    ``README.zh-CN.md``). Legacy artifacts removed across versions
    (``paper-spine.md``, ``paperspine-legacy.md``, ``dist/codex/paper-spine/SKILL.md``)
    are never required.
    """
    # Core payload: without these the package cannot be installed — fatal.
    core: list[str] = ["dist/paperspine_version.json"]
    for skill in SUITE_SKILLS:
        core.append(f"dist/claude/skills/{skill}/SKILL.md")
        core.append(f"dist/codex/skills/{skill}/SKILL.md")
        core.append(f"dist/openclaw/skills/{skill}/SKILL.md")
        # Hermes nests the skill under the academic-writing namespace.
        core.append(f"dist/hermes/skills/academic-writing/{skill}/SKILL.md")
    # Slash-command / prompt entry points for Claude and Codex.
    core.append("dist/claude/commands/paperspine.md")
    core.append("dist/codex/prompts/paperspine.md")

    # Optional: docs + root installers. These churn across versions, so a
    # missing one must never abort an upgrade — warn and continue.
    optional: list[str] = ["install.ps1", "install.sh", "README.md", "README.en.md"]

    missing_core = [rel for rel in core if not (root / rel).exists()]
    if missing_core:
        raise UpdateError(
            "Downloaded PaperSpine package is incomplete (missing core files):\n"
            + "\n".join(missing_core[:20])
        )
    missing_optional = [rel for rel in optional if not (root / rel).exists()]
    if missing_optional:
        print(
            "PaperSpine update: optional files absent (continuing anyway): "
            + ", ".join(missing_optional),
            file=sys.stderr,
        )
    return read_json(root / "dist" / VERSION_FILE)


def replace_tree(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".{dest.name}.paperspine-update-tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(src, tmp, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"))
    if dest.exists():
        shutil.rmtree(dest)
    tmp.rename(dest)


def copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".{dest.name}.paperspine-update-tmp"
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(src, tmp)
    tmp.replace(dest)


def target_paths(target: str) -> dict[str, Path]:
    home = Path.home()
    paths = {
        "codex_skills": Path(
            os.environ.get("PAPERSPINE_CODEX_SKILLS_DIR", home / ".codex" / "skills")
        ),
        "codex_prompts": Path(
            os.environ.get("PAPERSPINE_CODEX_PROMPTS_DIR", home / ".codex" / "prompts")
        ),
        "claude_skills": Path(os.environ.get("PAPERSPINE_CLAUDE_SKILLS_DIR", home / ".claude" / "skills")),
        "claude_commands": Path(os.environ.get("PAPERSPINE_CLAUDE_COMMANDS_DIR", home / ".claude" / "commands")),
        "openclaw_skills": Path(
            os.environ.get("PAPERSPINE_OPENCLAW_SKILLS_DIR", home / ".openclaw" / "skills")
        ),
        "hermes_skills": Path(
            os.environ.get(
                "PAPERSPINE_HERMES_SKILLS_DIR",
                home / "AppData" / "Local" / "hermes" / "skills",
            )
        ),
    }
    if target == "codex":
        return {key: paths[key] for key in ("codex_skills", "codex_prompts")}
    if target == "claude":
        return {"claude_skills": paths["claude_skills"], "claude_commands": paths["claude_commands"]}
    if target == "openclaw":
        return {"openclaw_skills": paths["openclaw_skills"]}
    if target == "hermes":
        return {"hermes_skills": paths["hermes_skills"]}
    return paths


def target_names(target: str) -> list[str]:
    if target == "all":
        return ["codex", "claude", "openclaw", "hermes"]
    return [target]


def stale_skill_entries(skills_root: Path) -> list[tuple[None, Path]]:
    if not skills_root.exists():
        return []
    return [
        (None, path)
        for path in skills_root.iterdir()
        if path.is_dir() and path.name.startswith("paper-spine") and path.name != "paper-spine"
    ]


def installation_entries(root: Path, target: str) -> list[tuple[Path | None, Path]]:
    paths = target_paths(target)
    entries: list[tuple[Path | None, Path]] = []
    if "codex_skills" in paths:
        entries.extend(
            [
                (
                    root / "dist" / "codex" / "skills" / "paper-spine",
                    paths["codex_skills"] / "paper-spine",
                ),
                (
                    root / "dist" / "codex" / "prompts" / "paperspine.md",
                    paths["codex_prompts"] / "paperspine.md",
                ),
            ]
        )
        entries.extend(stale_skill_entries(paths["codex_skills"]))
    if "claude_skills" in paths:
        entries.extend(
            [
                (
                    root / "dist" / "claude" / "skills" / "paper-spine",
                    paths["claude_skills"] / "paper-spine",
                ),
                (
                    root / "dist" / "claude" / "commands" / "paperspine.md",
                    paths["claude_commands"] / "paperspine.md",
                ),
            ]
        )
        entries.extend(stale_skill_entries(paths["claude_skills"]))
        if paths["claude_commands"].exists():
            entries.extend(
                (None, path)
                for path in paths["claude_commands"].glob("paperspine*.md")
                if path.name != "paperspine.md"
            )
    if "openclaw_skills" in paths:
        entries.append(
            (
                root / "dist" / "openclaw" / "skills" / "paper-spine",
                paths["openclaw_skills"] / "paper-spine",
            )
        )
        entries.extend(stale_skill_entries(paths["openclaw_skills"]))
    if "hermes_skills" in paths:
        entries.append(
            (
                root / "dist" / "hermes" / "skills" / "academic-writing" / "paper-spine",
                paths["hermes_skills"] / "academic-writing" / "paper-spine",
            )
        )
        entries.extend(
            stale_skill_entries(paths["hermes_skills"] / "academic-writing")
        )
    return entries


def restore_installation(backups: list[tuple[Path, Path | None]]) -> None:
    for dest, backup in reversed(backups):
        if dest.exists():
            shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
        if backup is None:
            continue
        if backup.is_dir():
            shutil.copytree(backup, dest)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, dest)


def install_target(root: Path, target: str) -> list[str]:
    entries = installation_entries(root, target)
    with tempfile.TemporaryDirectory(prefix="paperspine-rollback-") as tmp:
        backup_root = Path(tmp)
        backups: list[tuple[Path, Path | None]] = []
        try:
            for index, (_, dest) in enumerate(entries):
                if not dest.exists():
                    backups.append((dest, None))
                    continue
                backup = backup_root / str(index)
                if dest.is_dir():
                    shutil.copytree(dest, backup)
                else:
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, backup)
                backups.append((dest, backup))
        except OSError as exc:
            raise UpdateError(f"Unable to prepare update rollback data: {exc}") from exc
        try:
            for source, dest in entries:
                if source is None:
                    shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
                elif source.is_dir():
                    replace_tree(source, dest)
                else:
                    copy_file(source, dest)
        except OSError as exc:
            try:
                restore_installation(backups)
            except OSError as rollback_exc:
                raise UpdateError(
                    f"Installation failed ({exc}); rollback also failed ({rollback_exc})."
                ) from rollback_exc
            raise UpdateError(f"Installation failed and was rolled back: {exc}") from exc
    return target_names(target)


def resolve_claude_settings_dir() -> Path:
    """Resolve the Claude settings directory, honoring the install-dir override.

    This must follow PAPERSPINE_CLAUDE_SKILLS_DIR so that callers (and tests)
    that redirect installs away from the real home never mutate the developer's
    actual ~/.claude/settings.json.
    """
    skills_dir = Path(
        os.environ.get("PAPERSPINE_CLAUDE_SKILLS_DIR", Path.home() / ".claude" / "skills")
    )
    return skills_dir.parent


def sync_skill_overrides(claude_settings_dir: Path) -> None:
    """Remove stale PaperSpine skillOverrides. All skills are now visible."""
    settings_path = claude_settings_dir / "settings.json"
    if not settings_path.exists():
        return
    try:
        existing = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    overrides = existing.get("skillOverrides", {})
    if isinstance(overrides, list):
        return
    stale = [k for k in overrides if k.startswith("paper-spine")]
    if not stale:
        return
    for skill in stale:
        del overrides[skill]
    if not overrides:
        existing.pop("skillOverrides", None)
    else:
        existing["skillOverrides"] = overrides
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_install_state(config_dir: Path, manifest: dict[str, Any], targets: list[str]) -> None:
    state = {
        "installed_version": manifest["version"],
        "installed_at": iso_utc(utc_now()),
        "source": {
            "repository": manifest.get("repository"),
            "channel": manifest.get("channel"),
            "manifest_url": manifest.get("manifest_url", DEFAULT_MANIFEST_URL),
            "archive_url": manifest.get("archive_url", DEFAULT_ARCHIVE_URL),
        },
        "targets": targets,
        "preserved_config_path": str(config_dir / "config.json"),
    }
    write_json(config_dir / INSTALL_STATE_FILE, state)


def confirm_update(current: str, latest: str, args: argparse.Namespace) -> bool:
    if args.yes or args.auto:
        return True
    if not sys.stdin.isatty():
        raise UpdateError("Update available but --yes was not provided in a non-interactive session.")
    answer = input(f"Update PaperSpine from {current} to {latest}? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def run_update(args: argparse.Namespace) -> int:
    config_dir = config_home(args)
    current = local_version(config_dir)
    manifest = latest_manifest(args)
    latest = str(manifest.get("version") or "")
    if not latest:
        raise UpdateError("Latest manifest does not contain a version.")

    comparison = compare_versions(current, latest)
    if comparison >= 0:
        print(f"PaperSpine is already latest: {current}")
        if comparison == 0 and not args.check_only:
            write_install_state(config_dir, manifest, target_names(args.target))
            if "claude" in target_names(args.target):
                sync_skill_overrides(resolve_claude_settings_dir())
        return 0

    print(f"PaperSpine update available: {current} -> {latest}")
    if args.check_only:
        return 2
    if not confirm_update(current, latest, args):
        print("PaperSpine update cancelled.")
        return 0

    with tempfile.TemporaryDirectory(prefix="paperspine-update-") as tmp:
        root = repo_root_from_archive(args.repo_archive, manifest, Path(tmp))
        package_manifest = validate_repo(root)
        package_version = str(package_manifest.get("version") or "")
        if compare_versions(package_version, latest) != 0:
            raise UpdateError(f"Archive version {package_version} does not match manifest version {latest}.")
        installed = install_target(root, args.target)
        if "claude" in installed:
            sync_skill_overrides(resolve_claude_settings_dir())
        write_install_state(config_dir, package_manifest, installed)
    print(f"PaperSpine updated to {latest}: {', '.join(installed)}")
    print(f"Global config preserved: {config_dir / 'config.json'}")
    print("Reload or restart the host before starting or resuming a PaperSpine workflow.")
    return 0


def configure_auto_update(args: argparse.Namespace) -> int:
    config_dir = config_home(args)
    policy = load_update_policy(config_dir)
    if args.enable_auto_update:
        policy["auto_update"] = True
        policy["interval_hours"] = args.interval_hours or policy["interval_hours"]
        policy["target"] = args.target
        policy["last_result"] = "enabled_waiting_for_preflight"
        policy["last_error"] = None
        save_update_policy(config_dir, policy)
        print(describe_update_policy(policy))
        return 0
    if args.disable_auto_update:
        policy["auto_update"] = False
        policy["last_result"] = "disabled_by_user"
        policy["last_error"] = None
        save_update_policy(config_dir, policy)
        print(describe_update_policy(policy))
        return 0
    print(describe_update_policy(policy))
    if policy.get("last_error"):
        print(f"Last automatic-update error: {policy['last_error']}")
    return 0


def run_auto_update(args: argparse.Namespace) -> int:
    config_dir = config_home(args)
    policy = load_update_policy(config_dir)
    if not policy["auto_update"]:
        print("PaperSpine automatic updates are disabled.")
        return 0
    if not args.force and not auto_update_due(policy):
        print(describe_update_policy(policy))
        print("PaperSpine automatic update check is not due.")
        return 0

    args.target = str(policy["target"])
    checked_at = utc_now()
    try:
        result = run_update(args)
    except UpdateError as exc:
        policy["last_checked_at"] = iso_utc(checked_at)
        policy["last_result"] = "error"
        policy["last_error"] = str(exc)
        save_update_policy(config_dir, policy)
        raise
    policy["last_checked_at"] = iso_utc(checked_at)
    policy["last_result"] = "updated_or_current"
    policy["last_error"] = None
    save_update_policy(config_dir, policy)
    return result


def run(args: argparse.Namespace) -> int:
    if args.enable_auto_update or args.disable_auto_update or args.auto_status:
        return configure_auto_update(args)
    if args.auto:
        return run_auto_update(args)
    return run_update(args)


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except UpdateError as exc:
        print(f"PaperSpine update failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
