#!/usr/bin/env python3
"""Generate the single-skill PaperSpine dist and install it into local hosts.

V4 architecture: ONE `paper-spine` skill. Source of truth is `src/`:
  src/skill/{SKILL.md, references/, agents/}   shared skill core
  src/scripts/*.py|*.sh|*.ps1                   shared scripts
  src/adapters/{claude,codex,hermes}/...        per-host adapters

dist/ is generated (committed, CI-guarded):
  dist/claude/skills/paper-spine/      dist/codex/skills/paper-spine/
  dist/openclaw/skills/paper-spine/    dist/hermes/skills/academic-writing/paper-spine/
  dist/claude/commands/paperspine.md   dist/codex/prompts/paperspine.md
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_SKILL = ROOT / "src" / "skill"
SRC_SCRIPTS = ROOT / "src" / "scripts"
SRC_ADAPTERS = ROOT / "src" / "adapters"
DIST = ROOT / "dist"
VERSION_MANIFEST = DIST / "paperspine_version.json"

SKILL_NAME = "paper-spine"
HERMES_CATEGORY = "academic-writing"
# Legacy 12-skill worker dirs to remove on install (issue #7: cc switch mixed files).
LEGACY_SKILLS = (
    "paper-spine-ui", "paper-spine-intake", "paper-spine-research", "paper-spine-citation",
    "paper-spine-rewrite", "paper-spine-build", "paper-spine-latex", "paper-spine-audit",
    "paper-spine-translate", "paper-spine-humanize", "paper-spine-update",
)


def parse_args() -> argparse.Namespace:
    home = Path.home()
    p = argparse.ArgumentParser(description="Generate and install single-skill PaperSpine.")
    p.add_argument("--dist-only", action="store_true", help="Only regenerate dist/ from src/. No install.")
    p.add_argument("--clean-legacy", action="store_true", help="Remove legacy 12-skill worker dirs from installs.")
    p.add_argument("--claude-skills-dir", type=Path, default=home / ".claude" / "skills")
    p.add_argument("--claude-commands-dir", type=Path, default=home / ".claude" / "commands")
    p.add_argument("--codex-skills-dir", type=Path, default=home / ".codex" / "skills")
    p.add_argument("--codex-prompts-dir", type=Path, default=home / ".codex" / "prompts")
    p.add_argument("--openclaw-skills-dir", type=Path, default=home / ".openclaw" / "skills")
    p.add_argument("--hermes-skills-dir", type=Path, default=home / "AppData" / "Local" / "hermes" / "skills")
    p.add_argument("--config-home", type=Path, default=home / ".paperspine")
    p.add_argument("--desktop-root", type=Path, default=home / "Desktop" / "PaperSpine")
    return p.parse_args()


def copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"))


# Build/install-only scripts that must NOT ship inside an installed skill
# (they assume the repo's src/ layout and would crash from a dist copy).
BUILD_ONLY_SCRIPTS = frozenset({"sync_local_installs.py"})


def copy_scripts(dest_scripts: Path) -> None:
    dest_scripts.mkdir(parents=True, exist_ok=True)
    for f in list(SRC_SCRIPTS.glob("*.py")) + list(SRC_SCRIPTS.glob("*.sh")) + list(SRC_SCRIPTS.glob("*.ps1")):
        if f.name in BUILD_ONLY_SCRIPTS:
            continue
        shutil.copy2(f, dest_scripts / f.name)


def hermes_frontmatter() -> str:
    """Build the Hermes SKILL.md frontmatter block from the adapter overlay."""
    raw = (SRC_ADAPTERS / "hermes" / "frontmatter.yaml").read_text(encoding="utf-8")
    lines = [ln for ln in raw.splitlines() if not ln.lstrip().startswith("#")]
    body = "\n".join(lines).strip("\n")
    return f"---\n{body}\n---\n"


def shared_skill_body() -> str:
    """Return the shared SKILL.md content WITHOUT its YAML frontmatter block."""
    text = (SRC_SKILL / "SKILL.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[nl + 1:] if nl != -1 else ""
    return text


def build_skill_tree(dest: Path, *, hermes: bool = False) -> None:
    """Materialize one paper-spine skill folder at dest."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if hermes:
        (dest / "SKILL.md").write_text(
            hermes_frontmatter() + shared_skill_body(), encoding="utf-8", newline="\n"
        )
    else:
        shutil.copy2(SRC_SKILL / "SKILL.md", dest / "SKILL.md")
    copy_tree(SRC_SKILL / "references", dest / "references")
    copy_tree(SRC_SKILL / "agents", dest / "agents")
    copy_scripts(dest / "scripts")


def build_dist() -> None:
    """Regenerate the whole dist/ tree from src/ (idempotent)."""
    for host in ("claude", "codex", "openclaw"):
        build_skill_tree(DIST / host / "skills" / SKILL_NAME)
    build_skill_tree(DIST / "hermes" / "skills" / HERMES_CATEGORY / SKILL_NAME, hermes=True)
    # adapters
    cc = DIST / "claude" / "commands"
    cc.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_ADAPTERS / "claude" / "commands" / "paperspine.md", cc / "paperspine.md")
    cp = DIST / "codex" / "prompts"
    cp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_ADAPTERS / "codex" / "prompts" / "paperspine.md", cp / "paperspine.md")
    sync_version_from_canonical()
    print(f"Dist regenerated from src/: {DIST}")


def sync_version_from_canonical() -> None:
    version = json.loads(VERSION_MANIFEST.read_text(encoding="utf-8"))["version"]
    for rel, is_marketplace in ((".claude-plugin/plugin.json", False), (".claude-plugin/marketplace.json", True)):
        path = ROOT / rel
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if is_marketplace:
            for plugin in data.get("plugins", []):
                plugin["version"] = version
        else:
            data["version"] = version
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    try:
        shutil.rmtree(path) if path.is_dir() else path.unlink()
    except PermissionError as exc:
        print(f"Warning: skipped locked path: {path} ({exc})", file=sys.stderr)


def clean_legacy(args: argparse.Namespace) -> None:
    for skills_dir in (args.claude_skills_dir, args.codex_skills_dir, args.openclaw_skills_dir):
        for name in LEGACY_SKILLS:
            remove_path(skills_dir / name)
        for name in ("PaperSpine", "PaperSpineV2"):
            remove_path(skills_dir / name)


def install(args: argparse.Namespace) -> None:
    for src_host, dest in (
        (DIST / "claude" / "skills" / SKILL_NAME, args.claude_skills_dir / SKILL_NAME),
        (DIST / "codex" / "skills" / SKILL_NAME, args.codex_skills_dir / SKILL_NAME),
        (DIST / "openclaw" / "skills" / SKILL_NAME, args.openclaw_skills_dir / SKILL_NAME),
        (DIST / "hermes" / "skills" / HERMES_CATEGORY / SKILL_NAME,
         args.hermes_skills_dir / HERMES_CATEGORY / SKILL_NAME),
    ):
        if src_host.exists():
            copy_tree(src_host, dest)
    args.claude_commands_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DIST / "claude" / "commands" / "paperspine.md", args.claude_commands_dir / "paperspine.md")
    args.codex_prompts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DIST / "codex" / "prompts" / "paperspine.md", args.codex_prompts_dir / "paperspine.md")


def write_install_state(args: argparse.Namespace) -> None:
    manifest = json.loads(VERSION_MANIFEST.read_text(encoding="utf-8"))
    args.config_home.mkdir(parents=True, exist_ok=True)
    state = {
        "installed_version": manifest["version"],
        "installed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {k: manifest.get(k) for k in ("repository", "channel", "manifest_url", "archive_url")},
        "targets": ["claude", "codex", "openclaw", "hermes"],
        "preserved_config_path": str(args.config_home / "config.json"),
    }
    (args.config_home / "install_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    build_dist()
    if args.dist_only:
        return 0
    if args.clean_legacy:
        clean_legacy(args)
    install(args)
    write_install_state(args)
    print("PaperSpine V4 single-skill sync complete.")
    print(f"  Claude:   {args.claude_skills_dir / SKILL_NAME}")
    print(f"  Codex:    {args.codex_skills_dir / SKILL_NAME}  (+ /paperspine prompt)")
    print(f"  OpenClaw: {args.openclaw_skills_dir / SKILL_NAME}")
    print(f"  Hermes:   {args.hermes_skills_dir / HERMES_CATEGORY / SKILL_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
