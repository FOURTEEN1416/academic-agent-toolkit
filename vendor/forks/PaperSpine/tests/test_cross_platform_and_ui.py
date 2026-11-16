from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

try:
    from .test_suite_hardening import PRODUCT_CORE, prepare_isolated_build
except ImportError:  # unittest discovery imports modules without the package prefix.
    from test_suite_hardening import PRODUCT_CORE, prepare_isolated_build

ROOT = Path(__file__).resolve().parents[1]
TEST_TEMP_ROOT = ROOT.parent / "90_临时工作" / "test-temp"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


@contextmanager
def test_workspace(prefix: str):
    """Use inherited ACLs; tempfile's 0700 ACL is unusable on some mapped drives."""
    path = TEST_TEMP_ROOT / f"{prefix}{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

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
        with test_workspace("codex-entry-") as base:
            repository = prepare_isolated_build(base)
            codex = base / "codex" / "skills"
            # Simulate the concrete dirty-profile roots from PS-GAP-001.  The
            # installer must preserve their bytes outside discovery, not delete
            # or rewrite the legacy Skill content.
            conflicts = {
                "paperFig": b"---\nname: paperFig\n---\nlegacy figure bytes\n",
                "paper-spine.pre-fixture": b"---\nname: paper-spine\n---\nbackup bytes\n",
            }
            for name, payload in conflicts.items():
                root = codex / name
                root.mkdir(parents=True)
                (root / "SKILL.md").write_bytes(payload)
            old_canonical = codex / SKILL_NAME
            (old_canonical / "_paperspine5" / "01_PaperSpine4" / "src" / "skill").mkdir(parents=True)
            nested_spine_bytes = b"---\nname: paper-spine\n---\nold nested entry\n"
            (
                old_canonical / "_paperspine5" / "01_PaperSpine4" / "src" / "skill" / "SKILL.md"
            ).write_bytes(nested_spine_bytes)
            old_paperfig = old_canonical / "_paperspine5" / "02_PaperFigure" / "02_paperFig_skill"
            old_paperfig.mkdir(parents=True)
            nested_paperfig_bytes = b"---\nname: paperFig\n---\nold embedded legacy bytes\n"
            (old_paperfig / "SKILL.md").write_bytes(nested_paperfig_bytes)
            result = subprocess.run(
                [
                    sys.executable, "-X", "utf8", "src/scripts/sync_local_installs.py", "--clean-legacy",
                    "--paperspine5-root", str(repository.parent), "--skip-dsh",
                    "--desktop-root", str(base / "desktop"),
                    "--codex-skills-dir", str(base / "codex" / "skills"),
                    "--codex-prompts-dir", str(base / "codex" / "prompts"),
                    "--claude-skills-dir", str(base / "claude" / "skills"),
                    "--claude-commands-dir", str(base / "claude" / "commands"),
                    "--openclaw-skills-dir", str(base / "openclaw" / "skills"),
                    "--hermes-skills-dir", str(base / "hermes" / "skills"),
                    "--config-home", str(base / "config"),
                ],
                cwd=repository, text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            # dist/codex/skills must contain exactly one 'paper-spine' folder, nothing else.
            dist_codex = ROOT / "dist" / "codex" / "skills"
            dist_skill_dirs = sorted(p.name for p in dist_codex.iterdir() if p.is_dir())
            self.assertEqual(dist_skill_dirs, [SKILL_NAME], f"dist codex skills: {dist_skill_dirs}")

            # The installed Codex skills dir also has exactly one paper-spine.
            ps_dirs = [p for p in codex.iterdir() if p.is_dir() and p.name == SKILL_NAME]
            self.assertEqual(len(ps_dirs), 1, "expected exactly one paper-spine directory")
            installed = [p.name for p in codex.iterdir() if p.is_dir()]
            self.assertEqual(installed, [SKILL_NAME], f"Codex must install ONLY paper-spine: {installed}")
            self.assertTrue((codex / SKILL_NAME / "SKILL.md").exists())
            self.assertTrue(
                (codex / SKILL_NAME / "_paperspine5" / "EMBEDDED-WEB-IDENTITY.json").exists(),
                "standalone install must carry the shared Product Web core",
            )
            embedded = codex / SKILL_NAME / "_paperspine5"
            authority_relative = Path(
                "01_PaperSpine4/src/skill/references/figure-reference-mapping.md"
            )
            self.assertEqual(
                (embedded / authority_relative).read_bytes(),
                (PRODUCT_CORE / authority_relative).read_bytes(),
                "direct-embedded runtime must preserve the authority-table source bytes",
            )
            identity = json.loads(
                (embedded / "EMBEDDED-WEB-IDENTITY.json").read_text(encoding="utf-8")
            )
            content_index = [
                {
                    "path": path.relative_to(embedded).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "size_bytes": path.stat().st_size,
                }
                for path in sorted(embedded.rglob("*"), key=lambda item: item.as_posix())
                if path.is_file() and path.name != "EMBEDDED-WEB-IDENTITY.json"
            ]
            self.assertIn(authority_relative.as_posix(), {item["path"] for item in content_index})
            self.assertEqual(identity["content_file_count"], len(content_index))
            self.assertEqual(
                identity["content_index_sha256"],
                hashlib.sha256(
                    json.dumps(
                        content_index,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
            )
            self.assertEqual(
                frontmatter_value(codex / SKILL_NAME / "SKILL.md", "name"), SKILL_NAME
            )
            recursively_embedded = sorted(
                path.relative_to(codex / SKILL_NAME).as_posix()
                for path in (codex / SKILL_NAME).rglob("SKILL.md")
            )
            self.assertEqual(
                recursively_embedded,
                ["SKILL.md"],
                f"canonical install embeds discoverable nested Skills: {recursively_embedded}",
            )

            discovered = []
            for skill_md in codex.rglob("SKILL.md"):
                try:
                    discovered.append((frontmatter_value(skill_md, "name"), skill_md))
                except AssertionError:
                    continue
            self.assertEqual(
                [name for name, _ in discovered if name == "paper-spine"],
                ["paper-spine"],
                discovered,
            )
            self.assertEqual([item for item in discovered if item[0] == "paperFig"], [])

            receipts = list((base / "config" / "skill-discovery-archive" / "receipts").glob("*.json"))
            self.assertEqual(len(receipts), 1)
            receipt = __import__("json").loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "committed", receipt)
            archived = {
                item["source_relative_path"]: Path(item["target"])
                for item in receipt["items"]
            }
            for name, payload in conflicts.items():
                self.assertEqual((archived[name] / "SKILL.md").read_bytes(), payload)
            nested_spine_relative = (
                "paper-spine/_paperspine5/01_PaperSpine4/src/skill/SKILL.md"
            )
            nested_paperfig_relative = (
                "paper-spine/_paperspine5/02_PaperFigure/02_paperFig_skill"
            )
            self.assertEqual(archived[nested_spine_relative].read_bytes(), nested_spine_bytes)
            self.assertEqual(
                (archived[nested_paperfig_relative] / "SKILL.md").read_bytes(),
                nested_paperfig_bytes,
            )

            # The /paperspine slash command must install as a Codex prompt.
            self.assertTrue((base / "codex" / "prompts" / "paperspine.md").exists())

            # No legacy/backup discovery roots may remain in the active profile.
            for legacy in LEGACY_SKILLS + ("PaperSpine", "PaperSpineV2", "paperFig", "paper-spine.pre-fixture"):
                self.assertFalse((codex / legacy).exists(), f"legacy {legacy} should not install")

    def test_paper_spine_ships_in_every_host(self) -> None:
        skill_roots = {
            host: ROOT / "dist" / host / "skills" / SKILL_NAME
            for host in ("claude", "codex", "openclaw")
        }
        skill_roots["hermes"] = (
            ROOT / "dist" / "hermes" / "skills" / HERMES_CATEGORY / SKILL_NAME
        )
        authority_relative = Path(
            "01_PaperSpine4/src/skill/references/figure-reference-mapping.md"
        )
        source_authority = (PRODUCT_CORE / authority_relative).read_bytes()
        for host, skill_root in skill_roots.items():
            self.assertTrue(skill_root.joinpath("SKILL.md").exists(), f"{host}:{SKILL_NAME} must ship")
            embedded = skill_root / "_paperspine5"
            if embedded.is_dir():
                self.assertEqual(
                    (embedded / authority_relative).read_bytes(),
                    source_authority,
                    f"{host} direct-embedded authority table must equal source bytes",
                )
            else:
                # The public repository commits the lightweight Skill; suite CI
                # validates the platform payload. Source and bootstrap still ship.
                self.assertEqual(PRODUCT_CORE, ROOT / "paperspine5" / "core")
                self.assertEqual(
                    (ROOT / "src/skill/references/figure-reference-mapping.md").read_bytes(),
                    source_authority,
                )
                self.assertTrue((skill_root / "scripts/paperspine5_web.py").is_file())
                self.assertTrue((skill_root / "scripts/paperspine_stable_update.py").is_file())


class UiRoutingTests(unittest.TestCase):
    """Guarantee #1b: intake stays Web-first/in-host; CLI remains explicit fallback."""

    def test_native_embedded_method_without_historical_table(self) -> None:
        sys.path.insert(0, str(ROOT / "src/scripts"))
        import sync_local_installs
        original = Path.read_bytes
        def without_history(path):
            if path.name == "PAPERSPINE_VERA_FIGURE_MAPPING.md":
                raise FileNotFoundError("historical table is not installed")
            return original(path)
        with test_workspace("native-method-embed-") as temporary, patch.object(Path, "read_bytes", without_history):
            repository = prepare_isolated_build(temporary)
            sync_local_installs.embed_product_web(temporary / "skill", repository.parent)
            bundle = temporary / "skill/_paperspine5"
            relative = sync_local_installs.FIGURE_AUTHORITY_TABLE_RELATIVE
            self.assertEqual((PRODUCT_CORE / relative).read_bytes(), (bundle / relative).read_bytes())
            self.assertFalse((bundle / "03_联合开发/PAPERSPINE_VERA_FIGURE_MAPPING.md").exists())

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

    def test_codex_prompt_uses_the_installed_host_launcher(self) -> None:
        prompt = ROOT / "src" / "adapters" / "codex" / "prompts" / "paperspine.md"
        text = prompt.read_text(encoding="utf-8")
        self.assertIn("Read the installed `paper-spine` Skill", text)
        self.assertIn("scripts/paperspine5_web.py launch --no-open", text)
        self.assertIn("references/product-v1-workflow.md", text)
        self.assertNotIn("paper-spine-ui", text)
        self.assertNotIn("-File scripts/launch_paperspine_ui.ps1", text)

    def test_intake_reference_uses_absolute_single_skill_launcher(self) -> None:
        intake = ROOT / "src" / "skill" / "references" / "interactive-intake.md"
        text = intake.read_text(encoding="utf-8")
        self.assertIn(ABS_PS1_LAUNCHER, text)
        self.assertNotIn("paper-spine-ui", text)
        self.assertNotIn("paper-spine-intake", text)
        self.assertNotIn("-File scripts/launch_paperspine_ui.ps1", text)

    def test_codex_paperspine_slash_command_routes_to_current_skill(self) -> None:
        prompt = ROOT / "dist" / "codex" / "prompts" / "paperspine.md"
        self.assertTrue(prompt.exists(), "Codex /paperspine custom prompt must ship")
        text = prompt.read_text(encoding="utf-8")
        self.assertIn("Read the installed `paper-spine` Skill", text)
        self.assertIn("description:", text)
        self.assertIn("scripts/paperspine_update.py --preflight --yes", text)
        self.assertIn("scripts/paperspine5_web.py launch --no-open", text)
        self.assertIn("same task", text)
        self.assertIn("read the actual saved configuration", text)
        self.assertNotIn("-File scripts/launch_paperspine_ui.ps1", text)
        self.assertNotIn("require_escalated", text)
        self.assertNotIn("FIRST tool action", text)

    def test_orchestrator_routes_missing_configuration_through_current_host(self) -> None:
        orch = (ROOT / "dist" / "claude" / "skills" / SKILL_NAME / "SKILL.md").read_text(
            encoding="utf-8"
        ).lower()
        for token in (
            "configuration is missing",
            "current host agent",
            "scripts/paperspine_update.py --preflight --yes",
            "launch --no-open",
            "host tools",
            "web does not launch another writer",
            "same task",
        ):
            self.assertIn(token, orch, f"orchestrator must describe host-first intake ({token})")
        self.assertNotIn("first tool action", orch)
        self.assertNotIn("command-line wizard is an explicit compatibility fallback", orch)

    def test_no_adapter_requires_terminal_as_first_action(self) -> None:
        for path in (
            ROOT / "src" / "adapters" / "codex" / "prompts" / "paperspine.md",
            ROOT / "src" / "adapters" / "claude" / "commands" / "paperspine.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("FIRST tool action", text, str(path))
            self.assertNotIn("require_escalated", text, str(path))
        skill = (ROOT / "src/skill/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("FIRST tool action", skill)
        if "require_escalated" in skill:
            self.assertIn("as required by the host", skill)


class CrossPlatformLauncherTests(unittest.TestCase):
    """Guarantee #2: Windows, macOS, and Linux are all supported."""

    def test_ui_launchers_exist_for_all_platforms(self) -> None:
        self.assertTrue((ROOT / "src" / "scripts" / "launch_paperspine_ui.ps1").exists(), "Windows launcher")
        self.assertTrue((ROOT / "src" / "scripts" / "launch_paperspine_ui.sh").exists(), "macOS/Linux launcher")

    def test_shell_launcher_uses_the_web_adapter_without_terminal_emulators(self) -> None:
        sh = (ROOT / "src" / "scripts" / "launch_paperspine_ui.sh").read_text(encoding="utf-8")
        self.assertIn("python3", sh)
        self.assertIn("paperspine5_web.py", sh)
        for terminal in ("osascript", "gnome-terminal", "konsole", "xterm"):
            self.assertNotIn(terminal, sh)

    def test_powershell_launcher_forces_python_utf8_and_has_no_tui(self) -> None:
        ps = (ROOT / "src" / "scripts" / "launch_paperspine_ui.ps1").read_text(encoding="utf-8")
        self.assertIn("PYTHONUTF8", ps)
        self.assertIn("paperspine5_web.py", ps)
        self.assertNotIn("--keyboard-ui", ps)
        self.assertNotIn("Start-Process", ps)

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
