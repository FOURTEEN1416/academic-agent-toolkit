from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_TEMP_ROOT = ROOT.parent / "90_临时工作" / "test-temp"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
PRODUCT_CORE = ROOT / "paperspine5" / "core"
if not (PRODUCT_CORE / "03_联合开发" / "ui" / "product.html").is_file():
    PRODUCT_CORE = ROOT.parent

SKILL_NAME = "paper-spine"
HERMES_CATEGORY = "academic-writing"
# Hosts that receive a byte-identical single-source paper-spine skill tree.
PLAIN_HOSTS = ("claude", "codex", "openclaw")
# The 11 legacy worker dirs the V4 single-skill rewrite collapsed away.
LEGACY_SKILLS = (
    "paper-spine-ui",
    "paper-spine-intake",
    "paper-spine-research",
    "paper-spine-citation",
    "paper-spine-rewrite",
    "paper-spine-build",
    "paper-spine-latex",
    "paper-spine-audit",
    "paper-spine-translate",
    "paper-spine-humanize",
    "paper-spine-update",
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def strip_frontmatter(text: str) -> str:
    """Return SKILL.md body with the leading YAML frontmatter block removed."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[nl + 1:] if nl != -1 else ""
    return text


def snapshot_tree(root: Path) -> dict[str, bytes]:
    """Map every file under root to its bytes, keyed by POSIX relative path."""
    out: dict[str, bytes] = {}
    for f in sorted(root.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            out[f.relative_to(root).as_posix()] = f.read_bytes()
    return out


def prepare_isolated_build(base: Path) -> Path:
    """Exercise real copy/install code without changing the repository or user hosts.

    The runtime marker is deliberately not executable: native suite startup has
    separate platform CI. These tests verify source projection and installation.
    """
    product = base / "build-product"
    repository = product / "01_PaperSpine4"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    shutil.copytree(ROOT / "src", repository / "src", ignore=ignore)
    shutil.copytree(ROOT / ".claude-plugin", repository / ".claude-plugin", ignore=ignore)
    for relative in (
        "03_联合开发/src/paperspine_figure_integration",
        "03_联合开发/contracts",
        "03_联合开发/ui",
        "06_插件化/runtime",
        "02_PaperFigure/01_FigMirror引擎/src",
    ):
        shutil.copytree(PRODUCT_CORE / relative, product / relative, ignore=ignore)
    release = product / "06_插件化/release"
    release.mkdir(parents=True)
    shutil.copy2(PRODUCT_CORE / "06_插件化/release/stable_updater.py", release)
    vendor = product / "06_插件化/runtime_vendor/windows-py312"
    vendor.mkdir(parents=True)
    (vendor / "COPY-ONLY-TEST-FIXTURE.txt").write_text(
        "Not an interpreter; native runtime execution is tested by suite CI.\n",
        encoding="utf-8",
    )
    return repository


def run_sync(repository: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable, "-X", "utf8", "src/scripts/sync_local_installs.py",
            "--paperspine5-root", str(repository.parent), "--skip-dsh", *extra,
        ],
        cwd=repository,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


@contextmanager
def managed_test_workspace(prefix: str):
    """Use inherited ACLs; tempfile's 0700 ACL is unusable on some mapped drives."""
    path = TEST_TEMP_ROOT / f"{prefix}{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class SingleSkillDistTests(unittest.TestCase):
    def test_dist_exposes_exactly_one_paper_spine_skill_per_host(self) -> None:
        """V4 collapsed the 12-skill flat suite to a single `paper-spine` skill."""
        for host in PLAIN_HOSTS:
            skills_dir = ROOT / "dist" / host / "skills"
            present = sorted(p.name for p in skills_dir.iterdir() if p.is_dir())
            self.assertEqual(present, [SKILL_NAME], f"{host} should expose only {SKILL_NAME}")
            self.assertTrue((skills_dir / SKILL_NAME / "SKILL.md").exists())
            nested = sorted(
                path.relative_to(skills_dir / SKILL_NAME).as_posix()
                for path in (skills_dir / SKILL_NAME).rglob("SKILL.md")
            )
            self.assertEqual(nested, ["SKILL.md"], f"{host} embeds nested Skill entries")
            # None of the legacy worker dirs survive.
            for legacy in LEGACY_SKILLS:
                self.assertFalse((skills_dir / legacy).exists(), f"{host}:{legacy}")

        hermes = ROOT / "dist" / "hermes" / "skills" / HERMES_CATEGORY / SKILL_NAME
        self.assertTrue((hermes / "SKILL.md").exists())
        self.assertEqual(
            sorted(path.relative_to(hermes).as_posix() for path in hermes.rglob("SKILL.md")),
            ["SKILL.md"],
        )
        self.assertFalse((ROOT / "dist" / "hermes" / "skills" / SKILL_NAME).exists())

    def test_plain_host_skill_trees_are_byte_identical(self) -> None:
        """codex/openclaw must be byte-for-byte copies of the claude skill (single source)."""
        base = snapshot_tree(ROOT / "dist" / "claude" / "skills" / SKILL_NAME)
        self.assertIn("SKILL.md", base)
        self.assertTrue(any(k.startswith("scripts/") for k in base))
        self.assertTrue(any(k.startswith("references/") for k in base))
        for host in ("codex", "openclaw"):
            other = snapshot_tree(ROOT / "dist" / host / "skills" / SKILL_NAME)
            self.assertEqual(other, base, f"{host} skill tree diverges from claude")

    def test_hermes_skill_differs_only_by_frontmatter(self) -> None:
        """Hermes overlays its own frontmatter but ships the identical SKILL body and assets."""
        claude = snapshot_tree(ROOT / "dist" / "claude" / "skills" / SKILL_NAME)
        hermes = snapshot_tree(
            ROOT / "dist" / "hermes" / "skills" / HERMES_CATEGORY / SKILL_NAME
        )
        # Every non-SKILL file is byte-identical to the claude source.
        self.assertEqual(
            {k: v for k, v in hermes.items() if k != "SKILL.md"},
            {k: v for k, v in claude.items() if k != "SKILL.md"},
            "hermes assets diverge from single source",
        )
        # SKILL.md bytes differ (frontmatter), but the body is identical.
        self.assertNotEqual(hermes["SKILL.md"], claude["SKILL.md"])
        claude_text = claude["SKILL.md"].decode("utf-8")
        hermes_text = hermes["SKILL.md"].decode("utf-8")
        # Body content is identical; compare on normalized newlines because the sync
        # script writes the hermes SKILL.md via write_text (CRLF on Windows) while the
        # other hosts are copied byte-for-byte (LF). See regression note.
        self.assertEqual(
            strip_frontmatter(hermes_text).splitlines(),
            strip_frontmatter(claude_text).splitlines(),
        )
        # The hermes-only frontmatter fields are present.
        self.assertIn("category: academic-writing", hermes_text)
        self.assertIn("title:", hermes_text)
        self.assertNotIn("category:", claude_text.split("---", 2)[1])

    def test_dist_copies_match_src_source_of_truth(self) -> None:
        """Every dist copy of a src script/reference/agent matches src byte-for-byte."""
        src_skill = ROOT / "src" / "skill"
        sources = (
            list((ROOT / "src" / "scripts").glob("*.py"))
            + list((ROOT / "src" / "scripts").glob("*.sh"))
            + list((ROOT / "src" / "scripts").glob("*.ps1"))
            + list((src_skill / "references").glob("*.md"))
            + list((src_skill / "agents").glob("*"))
        )
        self.assertTrue(sources, "no source files discovered under src/")
        checked = 0
        out_of_sync: list[str] = []
        for src_file in sources:
            if not src_file.is_file():
                continue
            want = src_file.read_bytes()
            for copy in (ROOT / "dist").rglob(src_file.name):
                if not copy.is_file():
                    continue
                # Embedded Product Web sources are a second, mechanically copied
                # source tree.  This assertion covers the public standalone skill
                # surface only; embedded-core parity has its own identity checks.
                if "_paperspine5" in copy.parts:
                    continue
                checked += 1
                if copy.read_bytes() != want:
                    out_of_sync.append(str(copy.relative_to(ROOT)))
        self.assertEqual(out_of_sync, [], f"dist copies out of sync with src: {out_of_sync}")
        self.assertGreater(checked, 0, "no dist copies discovered")

    def test_embedded_product_core_excludes_hidden_development_trees(self) -> None:
        embedded = (
            ROOT
            / "dist"
            / "codex"
            / "skills"
            / SKILL_NAME
            / "_paperspine5"
        )
        offenders = [
            path.relative_to(embedded).as_posix()
            for path in embedded.rglob("*")
            if path.is_file()
            and any(part.startswith(".") for part in path.relative_to(embedded).parts)
        ]
        self.assertEqual(
            offenders,
            [],
            "embedded product core must not package test/probe/cache hidden trees",
        )


class DistOnlyIdempotencyTests(unittest.TestCase):
    def test_dist_only_regenerates_and_is_idempotent(self) -> None:
        """`--dist-only` regenerates dist/; a second run leaves file bytes unchanged."""
        with managed_test_workspace("dist-idempotency-") as base:
            repository = prepare_isolated_build(base)
            first = run_sync(repository, "--dist-only")
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            after_first = snapshot_tree(repository / "dist")
            self.assertIn("claude/skills/paper-spine/SKILL.md", after_first)

            second = run_sync(repository, "--dist-only")
            self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
            after_second = snapshot_tree(repository / "dist")

            self.assertEqual(
                sorted(after_first), sorted(after_second), "dist file set changed across runs"
            )
            changed = [k for k in after_first if after_first[k] != after_second.get(k)]
            self.assertEqual(changed, [], f"dist bytes changed on a repeated --dist-only run: {changed}")


class SyncInstallTests(unittest.TestCase):
    def test_sync_installs_single_skill_to_all_hosts_and_cleans_legacy(self) -> None:
        with managed_test_workspace("sync-hosts-") as base:
            repository = prepare_isolated_build(base)
            claude_skills = base / "claude" / "skills"
            codex_skills = base / "codex" / "skills"
            openclaw_skills = base / "openclaw" / "skills"
            hermes_skills = base / "hermes" / "skills"
            claude_cmds = base / "claude" / "commands"
            codex_prompts = base / "codex" / "prompts"
            config_home = base / "config"

            # Plant a legacy worker dir that --clean-legacy must archive without
            # changing a byte, then remove from automatic discovery.
            planted = claude_skills / "paper-spine-research"
            planted.mkdir(parents=True)
            planted_bytes = b"stale legacy bytes\x00\xff"
            (planted / "SKILL.md").write_bytes(planted_bytes)

            result = run_sync(
                repository,
                "--clean-legacy",
                "--claude-skills-dir", str(claude_skills),
                "--claude-commands-dir", str(claude_cmds),
                "--codex-skills-dir", str(codex_skills),
                "--codex-prompts-dir", str(codex_prompts),
                "--openclaw-skills-dir", str(openclaw_skills),
                "--hermes-skills-dir", str(hermes_skills),
                "--config-home", str(config_home),
                "--desktop-root", str(base / "desktop"),
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            # Exactly one paper-spine skill per plain host.
            self.assertTrue((claude_skills / SKILL_NAME / "SKILL.md").exists())
            self.assertTrue((codex_skills / SKILL_NAME / "SKILL.md").exists())
            self.assertTrue((openclaw_skills / SKILL_NAME / "SKILL.md").exists())
            identity = json.loads(
                (codex_skills / SKILL_NAME / "_paperspine5" / "EMBEDDED-WEB-IDENTITY.json")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(identity["frontend"], "web")
            self.assertFalse(identity["terminal_frontend"])
            # Hermes nests under the academic-writing category.
            self.assertTrue(
                (hermes_skills / HERMES_CATEGORY / SKILL_NAME / "SKILL.md").exists()
            )
            # Host adapters: claude command + codex prompt.
            self.assertTrue((claude_cmds / "paperspine.md").exists())
            self.assertTrue((codex_prompts / "paperspine.md").exists())
            # Install state recorded.
            self.assertTrue((config_home / "install_state.json").exists())
            state = json.loads((config_home / "install_state.json").read_text(encoding="utf-8"))
            canonical = json.loads((ROOT / "src/paperspine_version.json").read_text(encoding="utf-8"))
            self.assertEqual(state["installed_version"], canonical["version"])
            self.assertEqual(
                set(state["targets"]), {"claude", "codex", "openclaw", "hermes"}
            )
            # Legacy planted dir is outside discovery and recoverable from the
            # product-owned, hash-bound receipt.
            self.assertFalse(planted.exists(), "--clean-legacy left a stale discovery root")
            for legacy in LEGACY_SKILLS:
                self.assertFalse((claude_skills / legacy).exists(), legacy)
            receipts = list((config_home / "skill-discovery-archive" / "receipts").glob("*.json"))
            self.assertEqual(len(receipts), 1)
            receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "committed", receipt)
            planted_item = next(item for item in receipt["items"] if item["name"] == planted.name)
            self.assertEqual((Path(planted_item["target"]) / "SKILL.md").read_bytes(), planted_bytes)
            self.assertEqual(planted_item["file_count"], 1)

    def test_installed_skill_matches_dist_bytes(self) -> None:
        with managed_test_workspace("sync-bytes-") as base:
            repository = prepare_isolated_build(base)
            claude_skills = base / "claude" / "skills"
            result = run_sync(
                repository,
                "--claude-skills-dir", str(claude_skills),
                "--claude-commands-dir", str(base / "claude" / "commands"),
                "--codex-skills-dir", str(base / "codex" / "skills"),
                "--codex-prompts-dir", str(base / "codex" / "prompts"),
                "--openclaw-skills-dir", str(base / "openclaw" / "skills"),
                "--hermes-skills-dir", str(base / "hermes" / "skills"),
                "--config-home", str(base / "config"),
                "--desktop-root", str(base / "desktop"),
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            installed = snapshot_tree(claude_skills / SKILL_NAME)
            dist = snapshot_tree(repository / "dist" / "claude" / "skills" / SKILL_NAME)
            self.assertEqual(installed, dist, "installed skill diverges from dist source")


class AdapterLauncherTests(unittest.TestCase):
    def test_claude_command_uses_installed_skill_and_preserves_invocation(self) -> None:
        text = read("dist/claude/commands/paperspine.md")
        self.assertIn("description:", text)
        self.assertIn("$ARGUMENTS", text)
        self.assertIn("Read the installed `paper-spine` Skill", text)
        self.assertIn("scripts/paperspine5_web.py launch", text)
        self.assertIn("scripts/paperspine_update.py --preflight --yes", text)
        self.assertIn("read the actual saved configuration", text)
        self.assertIn("same task", text)
        self.assertNotRegex(text, r"""-File\s+["\']?\.?[\\/]?scripts[\\/]""")
        self.assertNotIn("require_escalated", text)
        self.assertNotIn("FIRST tool action", text)

    def test_codex_prompt_uses_installed_skill_and_preserves_invocation(self) -> None:
        text = read("dist/codex/prompts/paperspine.md")
        self.assertIn("$1", text)
        self.assertIn("Read the installed `paper-spine` Skill", text)
        self.assertIn("scripts/paperspine5_web.py launch --no-open", text)
        self.assertIn("scripts/paperspine_update.py --preflight --yes", text)
        self.assertIn("exact returned task URL once", text)
        self.assertIn("read the actual saved configuration", text)
        self.assertIn("same task", text)
        self.assertNotRegex(text, r"""-File\s+["\']?\.?[\\/]?scripts[\\/]""")
        self.assertNotIn("require_escalated", text)
        self.assertNotIn("FIRST tool action", text)


class RepoHygieneTests(unittest.TestCase):
    def test_no_top_level_skill_and_no_legacy_flat_roots(self) -> None:
        self.assertFalse((ROOT / "SKILL.md").exists())
        self.assertTrue((ROOT / "dist" / "claude" / "skills" / SKILL_NAME / "SKILL.md").exists())
        for legacy_root in ("codex", "skills", "commands", "scripts", "references"):
            self.assertFalse((ROOT / legacy_root).exists(), legacy_root)

    def test_gitignore_blocks_user_and_generated_artifacts(self) -> None:
        text = read(".gitignore")
        for fragment in ("paper_rewriting_output/", "tmp_*_artifacts/", "*.aux", "*.log", "*.docx", "*.pdf"):
            self.assertIn(fragment, text)


if __name__ == "__main__":
    unittest.main()
