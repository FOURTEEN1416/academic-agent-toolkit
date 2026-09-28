from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

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


def run_sync(*extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "src/scripts/sync_local_installs.py", *extra],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class SingleSkillDistTests(unittest.TestCase):
    def test_dist_exposes_exactly_one_paper_spine_skill_per_host(self) -> None:
        """V4 collapsed the 12-skill flat suite to a single `paper-spine` skill."""
        for host in PLAIN_HOSTS:
            skills_dir = ROOT / "dist" / host / "skills"
            present = sorted(p.name for p in skills_dir.iterdir() if p.is_dir())
            self.assertEqual(present, [SKILL_NAME], f"{host} should expose only {SKILL_NAME}")
            self.assertTrue((skills_dir / SKILL_NAME / "SKILL.md").exists())
            # None of the legacy worker dirs survive.
            for legacy in LEGACY_SKILLS:
                self.assertFalse((skills_dir / legacy).exists(), f"{host}:{legacy}")

        hermes = ROOT / "dist" / "hermes" / "skills" / HERMES_CATEGORY / SKILL_NAME
        self.assertTrue((hermes / "SKILL.md").exists())
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
                checked += 1
                if copy.read_bytes() != want:
                    out_of_sync.append(str(copy.relative_to(ROOT)))
        self.assertEqual(out_of_sync, [], f"dist copies out of sync with src: {out_of_sync}")
        self.assertGreater(checked, 0, "no dist copies discovered")


class DistOnlyIdempotencyTests(unittest.TestCase):
    def test_dist_only_regenerates_and_is_idempotent(self) -> None:
        """`--dist-only` regenerates dist/; a second run leaves file bytes unchanged."""
        first = run_sync("--dist-only")
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        after_first = snapshot_tree(ROOT / "dist")
        self.assertIn("claude/skills/paper-spine/SKILL.md", after_first)

        second = run_sync("--dist-only")
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
        after_second = snapshot_tree(ROOT / "dist")

        self.assertEqual(
            sorted(after_first), sorted(after_second), "dist file set changed across runs"
        )
        changed = [k for k in after_first if after_first[k] != after_second.get(k)]
        self.assertEqual(changed, [], f"dist bytes changed on a repeated --dist-only run: {changed}")


class SyncInstallTests(unittest.TestCase):
    def test_sync_installs_single_skill_to_all_hosts_and_cleans_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            claude_skills = base / "claude" / "skills"
            codex_skills = base / "codex" / "skills"
            openclaw_skills = base / "openclaw" / "skills"
            hermes_skills = base / "hermes" / "skills"
            claude_cmds = base / "claude" / "commands"
            codex_prompts = base / "codex" / "prompts"
            config_home = base / "config"

            # Plant a legacy worker dir that --clean-legacy must remove.
            planted = claude_skills / "paper-spine-research"
            planted.mkdir(parents=True)
            (planted / "SKILL.md").write_text("stale", encoding="utf-8")

            result = run_sync(
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
            self.assertEqual(state["installed_version"], "4.0.0")
            self.assertEqual(
                set(state["targets"]), {"claude", "codex", "openclaw", "hermes"}
            )
            # Legacy planted dir removed; no other legacy worker dirs present.
            self.assertFalse(planted.exists(), "--clean-legacy left a stale worker dir")
            for legacy in LEGACY_SKILLS:
                self.assertFalse((claude_skills / legacy).exists(), legacy)

    def test_installed_skill_matches_dist_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            claude_skills = base / "claude" / "skills"
            result = run_sync(
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
            dist = snapshot_tree(ROOT / "dist" / "claude" / "skills" / SKILL_NAME)
            self.assertEqual(installed, dist, "installed skill diverges from dist source")


class AdapterLauncherTests(unittest.TestCase):
    def test_claude_command_references_absolute_installed_launcher(self) -> None:
        text = read("dist/claude/commands/paperspine.md")
        self.assertIn("description: Start PaperSpine", text)
        # Resolves the launcher by its absolute installed path, then runs it.
        self.assertIn(
            r".claude\skills\paper-spine\scripts\launch_paperspine_ui.ps1", text
        )
        self.assertIn("$HOME/.claude/skills/paper-spine/scripts/launch_paperspine_ui.sh", text)
        self.assertIn("-File $launcher", text)
        # No relative `-File scripts/...` invocation (Codex/Claude run from project dir).
        self.assertNotRegex(text, r"-File\s+[\"']?\.?[\\/]?scripts[\\/]")
        self.assertIn("paper-spine` orchestrator", text)

    def test_codex_prompt_references_absolute_installed_launcher(self) -> None:
        text = read("dist/codex/prompts/paperspine.md")
        self.assertIn(
            r".codex\skills\paper-spine\scripts\launch_paperspine_ui.ps1", text
        )
        self.assertIn("$HOME/.codex/skills/paper-spine/scripts/launch_paperspine_ui.sh", text)
        self.assertIn("-File $launcher", text)
        self.assertNotRegex(text, r"-File\s+[\"']?\.?[\\/]?scripts[\\/]")
        # Explicitly documents resolving by absolute path because scripts/ is absent locally.
        self.assertIn("absolute installed path", text)


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
