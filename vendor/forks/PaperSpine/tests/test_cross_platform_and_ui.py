from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKILL_NAME = "paper-spine"
HERMES_CATEGORY = "academic-writing"

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

# The absolute installed launcher path that intake docs MUST reference (single skill).
ABS_PS1_LAUNCHER = r"$env:USERPROFILE\.codex\skills\paper-spine\scripts\launch_paperspine_ui.ps1"


def all_skill_docs() -> list[Path]:
    docs = list((ROOT / "dist").rglob("SKILL.md"))
    docs += list((ROOT / "dist").rglob("interactive-intake.md"))
    docs += list((ROOT / "dist").rglob("paperspine.md"))
    return docs


def frontmatter_value(skill_md: Path, field: str) -> str:
    for line in skill_md.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{field}:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"{skill_md}: missing frontmatter '{field}'")


class CodexSingleEntryTests(unittest.TestCase):
    """Guarantee #1: Codex sees exactly ONE 'paper-spine' skill (single-skill V4)."""

    def test_codex_install_exposes_single_paper_spine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = subprocess.run(
                [
                    sys.executable, "src/scripts/sync_local_installs.py", "--clean-legacy",
                    "--desktop-root", str(base / "desktop"),
                    "--codex-skills-dir", str(base / "codex" / "skills"),
                    "--codex-prompts-dir", str(base / "codex" / "prompts"),
                    "--claude-skills-dir", str(base / "claude" / "skills"),
                    "--claude-commands-dir", str(base / "claude" / "commands"),
                    "--openclaw-skills-dir", str(base / "openclaw" / "skills"),
                    "--hermes-skills-dir", str(base / "hermes" / "skills"),
                    "--config-home", str(base / "config"),
                ],
                cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            # dist/codex/skills must contain exactly one 'paper-spine' folder, nothing else.
            dist_codex = ROOT / "dist" / "codex" / "skills"
            dist_skill_dirs = sorted(p.name for p in dist_codex.iterdir() if p.is_dir())
            self.assertEqual(dist_skill_dirs, [SKILL_NAME], f"dist codex skills: {dist_skill_dirs}")

            # The installed Codex skills dir also has exactly one paper-spine.
            codex = base / "codex" / "skills"
            ps_dirs = [p for p in codex.iterdir() if p.is_dir() and p.name == SKILL_NAME]
            self.assertEqual(len(ps_dirs), 1, "expected exactly one paper-spine directory")
            installed = [p.name for p in codex.iterdir() if p.is_dir()]
            self.assertEqual(installed, [SKILL_NAME], f"Codex must install ONLY paper-spine: {installed}")
            self.assertTrue((codex / SKILL_NAME / "SKILL.md").exists())
            self.assertEqual(
                frontmatter_value(codex / SKILL_NAME / "SKILL.md", "name"), SKILL_NAME
            )

            # The /paperspine slash command must install as a Codex prompt.
            self.assertTrue((base / "codex" / "prompts" / "paperspine.md").exists())

            # No legacy worker dirs or old monolith dirs may remain.
            for legacy in LEGACY_SKILLS + ("PaperSpine", "PaperSpineV2"):
                self.assertFalse((codex / legacy).exists(), f"legacy {legacy} should not install")

    def test_paper_spine_ships_in_every_host(self) -> None:
        for host in ("claude", "codex", "openclaw"):
            self.assertTrue(
                (ROOT / "dist" / host / "skills" / SKILL_NAME / "SKILL.md").exists(),
                f"{host}:{SKILL_NAME} must ship",
            )
        self.assertTrue(
            (ROOT / "dist" / "hermes" / "skills" / HERMES_CATEGORY / SKILL_NAME / "SKILL.md").exists(),
            "hermes academic-writing/paper-spine must ship",
        )


class UiAutoLaunchTests(unittest.TestCase):
    """Guarantee #1b: the UI launches by ABSOLUTE single-skill install path, automatically."""

    def test_no_relative_launcher_invocation_in_docs(self) -> None:
        bad: list[str] = []
        for doc in all_skill_docs():
            text = doc.read_text(encoding="utf-8")
            if "-File scripts/launch_paperspine_ui.ps1" in text or "python scripts/intake_wizard.py" in text:
                bad.append(str(doc.relative_to(ROOT)))
        self.assertEqual(bad, [], "docs must invoke the launcher by absolute install path")

    def test_no_legacy_worker_launcher_paths_in_docs(self) -> None:
        """Single-skill: launcher lives under paper-spine/, never paper-spine-ui/ or -intake/."""
        bad: list[str] = []
        for doc in all_skill_docs():
            text = doc.read_text(encoding="utf-8")
            if "paper-spine-ui" in text or "paper-spine-intake" in text:
                bad.append(str(doc.relative_to(ROOT)))
        self.assertEqual(bad, [], "no doc may point at the retired worker skill folders")

    def test_codex_prompt_references_absolute_single_skill_launcher(self) -> None:
        prompt = ROOT / "src" / "adapters" / "codex" / "prompts" / "paperspine.md"
        text = prompt.read_text(encoding="utf-8")
        self.assertIn(ABS_PS1_LAUNCHER, text)
        self.assertNotIn("paper-spine-ui", text)
        self.assertNotIn("-File scripts/launch_paperspine_ui.ps1", text)

    def test_intake_reference_uses_absolute_single_skill_launcher(self) -> None:
        intake = ROOT / "src" / "skill" / "references" / "interactive-intake.md"
        text = intake.read_text(encoding="utf-8")
        self.assertIn(ABS_PS1_LAUNCHER, text)
        self.assertNotIn("paper-spine-ui", text)
        self.assertNotIn("paper-spine-intake", text)
        self.assertNotIn("-File scripts/launch_paperspine_ui.ps1", text)

    def test_codex_paperspine_slash_command_exists_and_routes_to_orchestrator(self) -> None:
        prompt = ROOT / "dist" / "codex" / "prompts" / "paperspine.md"
        self.assertTrue(prompt.exists(), "Codex /paperspine custom prompt must ship")
        text = prompt.read_text(encoding="utf-8")
        self.assertIn("$paper-spine", text)  # routes to the orchestrator skill
        self.assertIn("description:", text)  # valid custom-prompt frontmatter
        self.assertNotIn("-File scripts/launch_paperspine_ui.ps1", text)  # absolute path only
        self.assertIn(r"$env:USERPROFILE\.codex\skills", text)
        # Hard execution constraint: launch UI first, with escalation.
        self.assertIn("require_escalated", text)
        self.assertIn("FIRST tool action", text)

    def test_orchestrator_auto_launches_ui_when_config_missing(self) -> None:
        orch = (ROOT / "dist" / "claude" / "skills" / SKILL_NAME / "SKILL.md").read_text(
            encoding="utf-8"
        ).lower()
        for token in ("configuration is missing", "launch", "intake", "automatically"):
            self.assertIn(token, orch, f"orchestrator must describe auto-launch ({token})")
        # Codex hard constraint: launch UI as the first action, with escalation.
        self.assertIn("require_escalated", orch)
        self.assertIn("first tool", orch)


class CrossPlatformLauncherTests(unittest.TestCase):
    """Guarantee #2: Windows, macOS, and Linux are all supported."""

    def test_ui_launchers_exist_for_all_platforms(self) -> None:
        self.assertTrue((ROOT / "src" / "scripts" / "launch_paperspine_ui.ps1").exists(), "Windows launcher")
        self.assertTrue((ROOT / "src" / "scripts" / "launch_paperspine_ui.sh").exists(), "macOS/Linux launcher")

    def test_shell_launcher_supports_macos_and_linux(self) -> None:
        sh = (ROOT / "src" / "scripts" / "launch_paperspine_ui.sh").read_text(encoding="utf-8")
        self.assertIn("Darwin", sh)
        self.assertIn("osascript", sh)
        self.assertIn("Linux", sh)
        self.assertTrue(
            any(term in sh for term in ("gnome-terminal", "konsole", "xterm")),
            "shell launcher must support at least one Linux terminal emulator",
        )

    def test_powershell_launcher_forces_utf8(self) -> None:
        ps = (ROOT / "src" / "scripts" / "launch_paperspine_ui.ps1").read_text(encoding="utf-8")
        self.assertIn("chcp 65001", ps)
        self.assertIn("UTF8", ps)

    def test_intake_wizard_handles_windows_and_posix(self) -> None:
        wiz = (ROOT / "src" / "scripts" / "intake_wizard.py").read_text(encoding="utf-8")
        self.assertIn("msvcrt", wiz, "Windows key input")
        self.assertIn("termios", wiz, "POSIX key input")
        self.assertIn("tty", wiz, "POSIX raw mode")
        self.assertIn("ENABLE_VIRTUAL_TERMINAL_PROCESSING", wiz, "Windows ANSI enabling")
        self.assertIn("chcp 65001", wiz, "Windows UTF-8 codepage")


class OrchestratorDiscoverabilityTests(unittest.TestCase):
    """The single skill must be intent-discoverable (no anti-trigger description)."""

    def test_orchestrator_description_is_trigger_rich(self) -> None:
        desc = frontmatter_value(
            ROOT / "dist" / "claude" / "skills" / SKILL_NAME / "SKILL.md", "description"
        )
        low = desc.lower()
        self.assertNotIn("internal orchestrator", low)
        self.assertNotIn("users should use /paperspine", low)
        self.assertTrue(
            any(verb in low for verb in ("write", "rewrite", "build")),
            "orchestrator description needs an action verb so hosts surface it",
        )
        self.assertIn("paper", low)
        self.assertLessEqual(len(desc), 200)

    def test_orchestrator_not_marked_internal_step(self) -> None:
        desc = frontmatter_value(
            ROOT / "dist" / "claude" / "skills" / SKILL_NAME / "SKILL.md", "description"
        )
        self.assertNotIn("internal /paperspine step", desc.lower())


class HermesFrontmatterTests(unittest.TestCase):
    """Single-skill V4: Hermes ships paper-spine under the academic-writing category."""

    def test_hermes_skill_has_academic_writing_frontmatter(self) -> None:
        skill_md = (
            ROOT / "dist" / "hermes" / "skills" / HERMES_CATEGORY / SKILL_NAME / "SKILL.md"
        )
        self.assertTrue(skill_md.exists(), "Hermes paper-spine SKILL.md must ship")
        self.assertEqual(frontmatter_value(skill_md, "name"), SKILL_NAME)
        self.assertEqual(frontmatter_value(skill_md, "category"), HERMES_CATEGORY)
        title = frontmatter_value(skill_md, "title")
        self.assertIn("PaperSpine", title)
        # 'triggers:' opens a YAML list; its bullet items must follow.
        text = skill_md.read_text(encoding="utf-8")
        self.assertIn("triggers:", text)
        self.assertRegex(text, r"triggers:\s*\n\s*-\s+\S")

    def test_hermes_body_matches_other_hosts(self) -> None:
        """Hermes overlays frontmatter only; the orchestrator body is shared."""
        hermes = (
            ROOT / "dist" / "hermes" / "skills" / HERMES_CATEGORY / SKILL_NAME / "SKILL.md"
        ).read_text(encoding="utf-8")
        claude = (
            ROOT / "dist" / "claude" / "skills" / SKILL_NAME / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("# PaperSpine Orchestrator", hermes)
        body_marker = "# PaperSpine Orchestrator"
        self.assertEqual(
            hermes[hermes.index(body_marker):],
            claude[claude.index(body_marker):],
            "Hermes body must equal the shared orchestrator body",
        )


if __name__ == "__main__":
    unittest.main()
