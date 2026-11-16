#!/usr/bin/env python3
"""Generate the single-skill PaperSpine dist and install it into local hosts.

V4 architecture: ONE `paper-spine` skill. Source of truth is `src/`:
  src/skill/{SKILL.md, references/, agents/}   shared skill core
  src/scripts/*.py|*.sh|*.ps1|*.lua             shared scripts
  src/adapters/{claude,codex,hermes}/...        per-host adapters

dist/ is generated (committed, CI-guarded):
  dist/claude/skills/paper-spine/      dist/codex/skills/paper-spine/
  dist/openclaw/skills/paper-spine/    dist/hermes/skills/academic-writing/paper-spine/
  dist/claude/commands/paperspine.md   dist/codex/prompts/paperspine.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from skill_discovery_migration import (
    migrate_discovery_conflicts,
    restore_discovery_migration,
)

ROOT = Path(__file__).resolve().parents[2]
SRC_SKILL = ROOT / "src" / "skill"
SRC_SCRIPTS = ROOT / "src" / "scripts"
SRC_ADAPTERS = ROOT / "src" / "adapters"
DIST = ROOT / "dist"
VERSION_MANIFEST = ROOT / "src" / "paperspine_version.json"
PRODUCT_WEB_BUNDLE = "_paperspine5"
FIGURE_AUTHORITY_TABLE_RELATIVE = Path(
    "01_PaperSpine4/src/skill/references/figure-reference-mapping.md"
)

SKILL_NAME = "paper-spine"
HERMES_CATEGORY = "academic-writing"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    home = Path.home()
    p = argparse.ArgumentParser(description="Generate and install single-skill PaperSpine.")
    p.add_argument("--dist-only", action="store_true", help="Only regenerate dist/ from src/. No install.")
    p.add_argument(
        "--skip-dsh",
        action="store_true",
        help="Do not update installed DSH (dsh-paperspine5) bundles.",
    )
    p.add_argument(
        "--dsh-target",
        type=Path,
        help="Update exactly this recognized dsh-paperspine5 install instead of discovering them.",
    )
    p.add_argument(
        "--dsh-releases-root",
        type=Path,
        help="Override the ~/.paperspine5/releases root used for DSH discovery.",
    )
    p.add_argument(
        "--dsh-output-dir",
        type=Path,
        help="Keep the temporary DSH rebuild under this directory (default: a system temp dir).",
    )
    p.add_argument(
        "--clean-legacy",
        action="store_true",
        help=(
            "Move legacy/backup Skill roots out of automatic discovery with a "
            "hash-bound, restorable receipt. No history is deleted."
        ),
    )
    p.add_argument("--claude-skills-dir", type=Path, default=home / ".claude" / "skills")
    p.add_argument("--claude-commands-dir", type=Path, default=home / ".claude" / "commands")
    p.add_argument("--codex-skills-dir", type=Path, default=home / ".codex" / "skills")
    p.add_argument("--codex-prompts-dir", type=Path, default=home / ".codex" / "prompts")
    p.add_argument("--openclaw-skills-dir", type=Path, default=home / ".openclaw" / "skills")
    p.add_argument("--hermes-skills-dir", type=Path, default=home / "AppData" / "Local" / "hermes" / "skills")
    p.add_argument("--config-home", type=Path, default=home / ".paperspine")
    p.add_argument("--desktop-root", type=Path, default=home / "Desktop" / "PaperSpine")
    p.add_argument(
        "--paperspine5-root",
        type=Path,
        help="PaperSpine5 workspace root used to embed the shared Kernel/Runner/Web core.",
    )
    return p.parse_args(argv)


def copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"))


# Build/install-only scripts that must NOT ship inside an installed skill
# (they assume the repo's src/ layout and would crash from a dist copy).
BUILD_ONLY_SCRIPTS = frozenset({"sync_local_installs.py"})


def copy_scripts(dest_scripts: Path) -> None:
    dest_scripts.mkdir(parents=True, exist_ok=True)
    for f in sorted(path for suffix in ("*.py", "*.sh", "*.ps1", "*.lua") for path in SRC_SCRIPTS.glob(suffix)):
        if f.name in BUILD_ONLY_SCRIPTS:
            continue
        shutil.copy2(f, dest_scripts / f.name)


def resolve_paperspine5_root(explicit: Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    if os.environ.get("PAPERSPINE5_PROJECT_ROOT"):
        candidates.append(Path(os.environ["PAPERSPINE5_PROJECT_ROOT"]))
    candidates.append(ROOT.parent)
    for candidate in candidates:
        root = candidate.expanduser().resolve()
        required = (
            root / "03_联合开发" / "src" / "paperspine_figure_integration" / "product_kernel.py",
            root / "03_联合开发" / "ui" / "product.html",
            root / FIGURE_AUTHORITY_TABLE_RELATIVE,
            root / "06_插件化" / "runtime" / "paperspine5_runtime.py",
        )
        if all(path.is_file() for path in required):
            return root
    raise RuntimeError(
        "PaperSpine5 shared Web core was not found. Set --paperspine5-root or "
        "PAPERSPINE5_PROJECT_ROOT; a terminal-only distribution is no longer built."
    )


def copy_filtered_tree(
    source: Path,
    destination: Path,
    *,
    suffixes: frozenset[str],
    excluded_names: frozenset[str] = frozenset(),
) -> None:
    if not source.is_dir():
        raise RuntimeError(f"PaperSpine5 bundle source is missing: {source}")
    for path in sorted(source.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(source)
        if any(
            part.startswith(".") or part == "__pycache__"
            for part in relative.parts
        ):
            continue
        if path.is_symlink():
            raise RuntimeError(f"PaperSpine5 bundle source cannot contain links: {path}")
        if not path.is_file() or path.name in excluded_names or path.suffix.lower() not in suffixes:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def copy_runtime_vendor(source: Path, destination: Path) -> None:
    """Ship the complete platform runtime required by the public MCP facade."""
    if not source.is_dir():
        raise RuntimeError(f"PaperSpine5 runtime vendor is missing: {source}")
    for path in sorted(source.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(source)
        if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
            continue
        if path.is_symlink():
            raise RuntimeError(f"PaperSpine5 runtime vendor cannot contain links: {path}")
        if not path.is_file():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def embed_product_web(dest: Path, product_root: Path) -> None:
    """Mechanically embed the shared Product core without duplicating its implementation."""
    bundle = dest / PRODUCT_WEB_BUNDLE
    if bundle.exists():
        shutil.rmtree(bundle)
    rules = (
        (
            product_root / "03_联合开发" / "src" / "paperspine_figure_integration",
            bundle / "03_联合开发" / "src" / "paperspine_figure_integration",
            frozenset({".py"}),
            frozenset(),
        ),
        (
            product_root / "03_联合开发" / "contracts",
            bundle / "03_联合开发" / "contracts",
            frozenset({".json"}),
            frozenset(),
        ),
        (
            product_root / "03_联合开发" / "ui",
            bundle / "03_联合开发" / "ui",
            frozenset({".css", ".html", ".js"}),
            frozenset(),
        ),
        (
            product_root / "06_插件化" / "runtime",
            bundle / "06_插件化" / "runtime",
            frozenset({".py", ".md"}),
            frozenset(
                {
                    "test_runtime.py",
                    "test_web_agent_runtime.py",
                    "test_material_profile.py",
                }
            ),
        ),
        (
            product_root / "01_PaperSpine4" / "src" / "skill",
            bundle / "01_PaperSpine4" / "src" / "skill",
            frozenset({".json", ".md", ".yaml", ".yml"}),
            frozenset({"SKILL.md"}),
        ),
        (
            product_root / "01_PaperSpine4" / "src" / "scripts",
            bundle / "01_PaperSpine4" / "src" / "scripts",
            frozenset({".py", ".ps1", ".sh", ".lua"}),
            BUILD_ONLY_SCRIPTS,
        ),
        (
            product_root / "02_PaperFigure" / "01_FigMirror引擎" / "src",
            bundle / "02_PaperFigure" / "01_FigMirror引擎" / "src",
            frozenset({".py"}),
            frozenset(),
        ),
    )
    for source, destination, suffixes, excluded_names in rules:
        copy_filtered_tree(
            source,
            destination,
            suffixes=suffixes,
            excluded_names=excluded_names,
        )
    copy_runtime_vendor(
        product_root / "06_插件化" / "runtime_vendor" / "windows-py312",
        bundle / "06_插件化" / "runtime_vendor" / "windows-py312",
    )
    # Preserve the dependency provenance next to the relocated platform tree.
    # Older source roots without lock metadata remain buildable.
    vendor_lock = product_root / "06_插件化" / "runtime_vendor" / "requirements.lock.json"
    if vendor_lock.is_symlink():
        raise RuntimeError(f"PaperSpine5 runtime lock cannot be a link: {vendor_lock}")
    if vendor_lock.is_file():
        shutil.copy2(vendor_lock, bundle / "06_插件化" / "runtime_vendor" / vendor_lock.name)
    authority_source = product_root / FIGURE_AUTHORITY_TABLE_RELATIVE
    if authority_source.is_symlink() or not authority_source.is_file():
        raise RuntimeError(
            f"PaperSpine5 authority table is missing or linked: {authority_source}"
        )
    authority_destination = bundle / FIGURE_AUTHORITY_TABLE_RELATIVE
    authority_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(authority_source, authority_destination)
    if authority_destination.read_bytes() != authority_source.read_bytes():
        raise RuntimeError("embedded Figure authority table bytes differ from source")
    content_index = [
        {
            "path": path.relative_to(bundle).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(bundle.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
    ]
    content_index_sha256 = hashlib.sha256(
        json.dumps(
            content_index,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    identity = {
        "contract": "paperspine5.embedded-web-core",
        "schema_version": "1.0",
        "product_version": "0.4.0-alpha.2",
        "channel": "development",
        "source_authority": "shared-workspace-allowlist",
        "content_index_sha256": content_index_sha256,
        "content_file_count": len(content_index),
        "frontend": "web",
        "terminal_frontend": False,
    }
    (bundle / "EMBEDDED-WEB-IDENTITY.json").write_text(
        json.dumps(identity, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


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


def build_skill_tree(dest: Path, *, product_root: Path, hermes: bool = False) -> None:
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
    # The bootstrap is a mechanical projection of the version-owned source.
    shutil.copy2(product_root / "06_插件化" / "release" / "stable_updater.py",
                 dest / "scripts" / "paperspine_stable_update.py")
    embed_product_web(dest, product_root)


def build_dist(product_root: Path) -> None:
    """Regenerate the whole dist/ tree from src/ (idempotent)."""
    for host in ("claude", "codex", "openclaw"):
        build_skill_tree(DIST / host / "skills" / SKILL_NAME, product_root=product_root)
    build_skill_tree(
        DIST / "hermes" / "skills" / HERMES_CATEGORY / SKILL_NAME,
        product_root=product_root,
        hermes=True,
    )
    # adapters
    cc = DIST / "claude" / "commands"
    cc.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_ADAPTERS / "claude" / "commands" / "paperspine.md", cc / "paperspine.md")
    cp = DIST / "codex" / "prompts"
    cp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_ADAPTERS / "codex" / "prompts" / "paperspine.md", cp / "paperspine.md")
    shutil.copy2(VERSION_MANIFEST, DIST / VERSION_MANIFEST.name)
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


def clean_legacy(args: argparse.Namespace) -> tuple[dict[str, object], Path]:
    """Archive discoverable conflicts through the reversible migration contract."""
    archive_root = (args.config_home / "skill-discovery-archive").resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    operation_id = f"sync-{timestamp}-{os.getpid()}"
    receipt = migrate_discovery_conflicts(
        {
            "claude": args.claude_skills_dir,
            "codex": args.codex_skills_dir,
            "openclaw": args.openclaw_skills_dir,
        },
        archive_root,
        operation_id=operation_id,
    )
    if receipt.get("status") not in {"committed", "noop"}:
        raise RuntimeError(f"Skill discovery migration failed: {receipt.get('blockers')}")
    receipt_path = archive_root / "receipts" / f"{operation_id}.json"
    return receipt, receipt_path


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


def load_dsh_sync():
    """Import the repository maintenance helper that owns DSH bundle updates."""
    try:
        import sync_dsh_install
    except ImportError:
        release_dir = ROOT.parent / "06_插件化" / "release"
        if release_dir.is_dir() and str(release_dir) not in sys.path:
            sys.path.insert(0, str(release_dir))
        import sync_dsh_install
    return sync_dsh_install


def sync_dsh(args: argparse.Namespace, product_root: Path, *, module=None) -> dict | None:
    """Update recognized installed DSH bundles from the canonical source.

    Runs after the other hosts are installed and before install state is
    written, so a build or install failure fails the whole sync instead of
    reporting success.
    """
    if getattr(args, "skip_dsh", False):
        return None
    module = module or load_dsh_sync()
    result = module.sync_installed_targets(
        product_root,
        target=getattr(args, "dsh_target", None),
        releases_root=getattr(args, "dsh_releases_root", None),
        output_dir=getattr(args, "dsh_output_dir", None),
    )
    if result.get("status") == "SKIPPED":
        print("  DSH:      no installed dsh-paperspine5 target; skipped.")
    else:
        for target in result.get("targets", []):
            print(f"  DSH:      {target}")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    product_root = resolve_paperspine5_root(args.paperspine5_root)
    build_dist(product_root)
    if args.dist_only:
        return 0
    migration_receipt: dict[str, object] | None = None
    migration_receipt_path: Path | None = None
    if args.clean_legacy:
        migration_receipt, migration_receipt_path = clean_legacy(args)
    try:
        install(args)
        sync_dsh(args, product_root)
        write_install_state(args)
    except Exception:
        if (
            migration_receipt is not None
            and migration_receipt.get("status") == "committed"
            and migration_receipt_path is not None
        ):
            restore_id = f"{migration_receipt['operation_id']}-auto-restore"
            restore = restore_discovery_migration(
                migration_receipt_path,
                operation_id=restore_id,
            )
            if restore.get("status") != "committed":
                print(
                    f"Warning: Skill discovery restore failed: {restore.get('blockers')}",
                    file=sys.stderr,
                )
        raise
    print("PaperSpine V4 single-skill sync complete.")
    print(f"  Claude:   {args.claude_skills_dir / SKILL_NAME}")
    print(f"  Codex:    {args.codex_skills_dir / SKILL_NAME}  (+ /paperspine prompt)")
    print(f"  OpenClaw: {args.openclaw_skills_dir / SKILL_NAME}")
    print(f"  Hermes:   {args.hermes_skills_dir / HERMES_CATEGORY / SKILL_NAME}")
    if migration_receipt_path is not None:
        print(f"  Discovery migration receipt: {migration_receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
