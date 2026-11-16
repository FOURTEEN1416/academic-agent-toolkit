from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "scripts" / "paperspine_update.py"
# V4: the published suite is a single orchestrator skill per host.
SUITE_SKILLS = [
    "paper-spine",
]


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_repo(root: Path, version: str, *, broken: bool = False) -> Path:
    """Build a fake V4 single-skill PaperSpine repo for the updater.

    The layout mirrors exactly what the rewritten ``validate_repo`` demands:
    root installers + READMEs + manifest, the ``paper-spine`` skill published
    under ``dist/{claude,codex,openclaw}/skills`` and
    ``dist/hermes/skills/academic-writing``, and the Claude/Codex entry points.
    When ``broken`` is set, one genuinely-required file (the Hermes SKILL.md)
    is omitted so ``validate_repo`` must reject the package.
    """
    manifest = {
        "version": version,
        "channel": "main",
        "repository": "https://github.com/WUBING2023/PaperSpine",
        "manifest_url": "https://raw.githubusercontent.com/WUBING2023/PaperSpine/main/dist/paperspine_version.json",
        "archive_url": "https://github.com/WUBING2023/PaperSpine/archive/refs/heads/main.zip",
    }
    write_json(root / "dist" / "paperspine_version.json", manifest)
    write_json(root / ".claude-plugin" / "plugin.json", {"name": "paper-spine", "version": version})
    write_json(root / ".claude-plugin" / "marketplace.json", {"plugins": [{"name": "paper-spine"}]})
    (root / "install.ps1").write_text("# installer\n", encoding="utf-8")
    (root / "install.sh").write_text("#!/bin/bash\n# installer\n", encoding="utf-8")
    (root / "README.md").write_text("# PaperSpine\n", encoding="utf-8")
    (root / "README.en.md").write_text("# PaperSpine\n", encoding="utf-8")

    # Claude slash-command and Codex prompt entry points.
    (root / "dist" / "claude" / "commands").mkdir(parents=True)
    (root / "dist" / "claude" / "commands" / "paperspine.md").write_text(
        "---\ndescription: paperspine\n---\n", encoding="utf-8")
    (root / "dist" / "codex" / "prompts").mkdir(parents=True)
    (root / "dist" / "codex" / "prompts" / "paperspine.md").write_text(
        "---\ndescription: paperspine\n---\n", encoding="utf-8")

    # The single orchestrator skill, published once per agent host.
    for host in ("claude", "codex", "openclaw"):
        for skill in SUITE_SKILLS:
            skill_dir = root / "dist" / host / "skills" / skill
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {skill}\ndescription: {skill}\n---\n",
                encoding="utf-8",
            )

    # Hermes nests the skill under the academic-writing namespace. The broken
    # archive omits this required file to exercise validate_repo's rejection.
    if not broken:
        for skill in SUITE_SKILLS:
            hermes_dir = root / "dist" / "hermes" / "skills" / "academic-writing" / skill
            hermes_dir.mkdir(parents=True)
            (hermes_dir / "SKILL.md").write_text(
                f"---\nname: {skill}\ndescription: {skill}\n---\n",
                encoding="utf-8",
            )
    return root


def zip_repo(repo_root: Path, archive_path: Path) -> Path:
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in repo_root.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(repo_root.parent))
    return archive_path


class PaperSpineUpdateScriptTests(unittest.TestCase):
    def run_updater(self, base: Path, archive: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "PAPERSPINE_CODEX_SKILLS_DIR": str(base / "codex" / "skills"),
                "PAPERSPINE_CODEX_PROMPTS_DIR": str(base / "codex" / "prompts"),
                "PAPERSPINE_CLAUDE_SKILLS_DIR": str(base / "claude" / "skills"),
                "PAPERSPINE_CLAUDE_COMMANDS_DIR": str(base / "claude" / "commands"),
                "PAPERSPINE_OPENCLAW_SKILLS_DIR": str(base / "openclaw" / "skills"),
                "PAPERSPINE_HERMES_SKILLS_DIR": str(base / "hermes" / "skills"),
            }
        )
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-archive",
                str(archive),
                "--config-home",
                str(base / "config"),
                *extra,
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_already_latest_check_only_does_not_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = create_repo(base / "PaperSpine-main", "2.0.0-rc.3")
            archive = zip_repo(repo, base / "paperspine.zip")
            write_json(base / "config" / "install_state.json", {"installed_version": "2.0.0-rc.3"})
            result = self.run_updater(base, archive, "--check-only")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("already latest", result.stdout)
            self.assertFalse((base / "codex" / "skills" / "paper-spine" / "SKILL.md").exists())

    def test_updates_from_local_archive_and_preserves_global_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = create_repo(base / "PaperSpine-main", "2.0.0-rc.3")
            archive = zip_repo(repo, base / "paperspine.zip")
            write_json(base / "config" / "install_state.json", {"installed_version": "2.0.0-rc.2"})
            config = {"ui_language": "zh"}
            write_json(base / "config" / "config.json", config)
            legacy = base / "codex" / "skills" / "paper-spine-update" / "SKILL.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("legacy updater\n", encoding="utf-8")
            result = self.run_updater(base, archive, "--yes")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Reload or restart", result.stdout)
            self.assertTrue((base / "codex" / "skills" / "paper-spine" / "SKILL.md").exists())
            self.assertTrue((base / "codex" / "prompts" / "paperspine.md").exists())
            self.assertTrue((base / "claude" / "skills" / "paper-spine" / "SKILL.md").exists())
            self.assertTrue((base / "claude" / "commands" / "paperspine.md").exists())
            self.assertTrue((base / "openclaw" / "skills" / "paper-spine" / "SKILL.md").exists())
            self.assertTrue(
                (
                    base
                    / "hermes"
                    / "skills"
                    / "academic-writing"
                    / "paper-spine"
                    / "SKILL.md"
                ).exists()
            )
            self.assertFalse(legacy.exists())
            self.assertEqual(json.loads((base / "config" / "config.json").read_text(encoding="utf-8")), config)
            state = json.loads((base / "config" / "install_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["installed_version"], "2.0.0-rc.3")
            self.assertEqual(state["targets"], ["codex", "claude", "openclaw", "hermes"])

    def test_broken_archive_fails_without_overwriting_existing_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = create_repo(base / "PaperSpine-main", "2.0.0-rc.3", broken=True)
            archive = zip_repo(repo, base / "paperspine.zip")
            write_json(base / "config" / "install_state.json", {"installed_version": "2.0.0-rc.2"})
            existing = base / "codex" / "skills" / "paper-spine" / "SKILL.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("old install\n", encoding="utf-8")
            result = self.run_updater(base, archive, "--yes")
            self.assertEqual(result.returncode, 1)
            self.assertIn("incomplete", result.stderr)
            self.assertEqual(existing.read_text(encoding="utf-8"), "old install\n")

    def test_check_only_with_update_available_returns_two_and_does_not_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = create_repo(base / "PaperSpine-main", "2.0.0")
            archive = zip_repo(repo, base / "paperspine.zip")
            write_json(base / "config" / "install_state.json", {"installed_version": "2.0.0-rc.2"})
            result = self.run_updater(base, archive, "--check-only")
            self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
            self.assertIn("update available", result.stdout)
            self.assertFalse((base / "codex" / "skills" / "paper-spine" / "SKILL.md").exists())

    def test_final_version_compares_higher_than_rc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = create_repo(base / "PaperSpine-main", "2.0.0")
            archive = zip_repo(repo, base / "paperspine.zip")
            write_json(base / "config" / "install_state.json", {"installed_version": "2.0.0-rc.9"})
            result = self.run_updater(base, archive, "--yes")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            state = json.loads((base / "config" / "install_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["installed_version"], "2.0.0")

    def test_auto_update_is_opt_in_and_disabled_preflight_does_not_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = create_repo(base / "PaperSpine-main", "2.0.0")
            archive = zip_repo(repo, base / "paperspine.zip")
            write_json(base / "config" / "install_state.json", {"installed_version": "1.0.0"})
            result = self.run_updater(base, archive, "--auto")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("disabled", result.stdout)
            self.assertFalse((base / "codex" / "skills" / "paper-spine").exists())

    def test_enabled_auto_update_runs_once_and_records_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = create_repo(base / "PaperSpine-main", "2.0.0")
            archive = zip_repo(repo, base / "paperspine.zip")
            write_json(base / "config" / "install_state.json", {"installed_version": "1.0.0"})

            enabled = self.run_updater(
                base,
                archive,
                "--enable-auto-update",
                "--interval-hours",
                "24",
            )
            self.assertEqual(enabled.returncode, 0, enabled.stderr + enabled.stdout)
            result = self.run_updater(base, archive, "--auto")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("updated to 2.0.0", result.stdout)

            policy = json.loads((base / "config" / "update_policy.json").read_text(encoding="utf-8"))
            self.assertTrue(policy["auto_update"])
            self.assertEqual(policy["interval_hours"], 24)
            self.assertEqual(policy["last_result"], "updated_or_current")
            self.assertIsNotNone(policy["last_checked_at"])

            second = self.run_updater(base, archive, "--auto")
            self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
            self.assertIn("not due", second.stdout)

    def test_auto_update_can_be_disabled_and_status_is_network_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = create_repo(base / "PaperSpine-main", "2.0.0")
            archive = zip_repo(repo, base / "paperspine.zip")
            enabled = self.run_updater(base, archive, "--enable-auto-update")
            self.assertEqual(enabled.returncode, 0, enabled.stderr + enabled.stdout)
            disabled = self.run_updater(base, archive, "--disable-auto-update")
            self.assertEqual(disabled.returncode, 0, disabled.stderr + disabled.stdout)
            status = self.run_updater(base, archive, "--auto-status")
            self.assertEqual(status.returncode, 0, status.stderr + status.stdout)
            self.assertIn("automatic updates: disabled", status.stdout)


class ValidateRepoTests(unittest.TestCase):
    def _import_updater(self):
        sys.path.insert(0, str(ROOT / "src" / "scripts"))
        import paperspine_update  # noqa: PLC0415

        return paperspine_update

    def test_validate_repo_accepts_actual_repository(self) -> None:
        """Guards against validate_repo drifting from the real dist layout (issue #6)."""
        updater = self._import_updater()
        manifest = updater.validate_repo(ROOT)
        self.assertIn("version", manifest)
        expected = json.loads((ROOT / "dist" / "paperspine_version.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], expected["version"])

    def test_semver_prerelease_precedence_supports_shadow_releases(self) -> None:
        updater = self._import_updater()
        ordered = (
            "0.4.0-alpha.1",
            "0.4.0-alpha.2",
            "0.4.0-beta.1",
            "0.4.0-rc.1",
            "0.4.0",
        )
        for lower, higher in zip(ordered[:-1], ordered[1:], strict=True):
            self.assertLess(updater.compare_versions(lower, higher), 0)
            self.assertGreater(updater.compare_versions(higher, lower), 0)

    def test_semver_build_metadata_does_not_change_precedence(self) -> None:
        updater = self._import_updater()
        self.assertEqual(
            updater.compare_versions("0.4.0-alpha.1+build.7", "0.4.0-alpha.1+build.9"),
            0,
        )

    def test_semver_rejects_numeric_prerelease_leading_zero(self) -> None:
        updater = self._import_updater()
        with self.assertRaises(updater.UpdateError):
            updater.version_key("0.4.0-alpha.01")

    def test_validate_repo_warns_but_accepts_missing_optional(self) -> None:
        # Issue #13 forward-compat: a doc/installer renamed or dropped in a newer
        # package must NOT abort the upgrade — validate_repo warns and returns.
        updater = self._import_updater()
        with tempfile.TemporaryDirectory() as tmp:
            root = create_repo(Path(tmp) / "PaperSpine-main", "9.9.9")
            (root / "README.en.md").unlink()
            (root / "install.ps1").unlink()
            manifest = updater.validate_repo(root)
            self.assertEqual(manifest["version"], "9.9.9")

    def test_validate_repo_rejects_missing_core(self) -> None:
        # Core payload (the skill the updater installs) is still hard-required.
        updater = self._import_updater()
        with tempfile.TemporaryDirectory() as tmp:
            root = create_repo(Path(tmp) / "PaperSpine-main", "9.9.9")
            (root / "dist" / "claude" / "skills" / "paper-spine" / "SKILL.md").unlink()
            with self.assertRaises(updater.UpdateError):
                updater.validate_repo(root)

    def test_update_reference_explains_suite_preflight_and_legacy_bridge(self) -> None:
        doc = (ROOT / "src" / "skill" / "references" / "update.md").read_text(encoding="utf-8")
        self.assertIn("--preflight", doc)
        self.assertIn("paperspine-updater/1", doc)
        self.assertIn("separate version sequences", doc)
        self.assertIn("macOS arm64", doc)
        self.assertNotIn("full-suite update is currently Windows x64 only", doc)

    def test_orchestrator_and_host_entries_share_suite_preflight(self) -> None:
        skill = (ROOT / "src" / "skill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--preflight --yes", skill)
        for path in ("src/adapters/claude/commands/paperspine.md", "src/adapters/codex/prompts/paperspine.md"):
            entry = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn("--preflight --yes", entry)
            self.assertNotIn("without an update\npreflight", entry)

    def test_main_skill_frontmatter_does_not_claim_verified_end_to_end_delivery(self) -> None:
        skill = (ROOT / "src" / "skill" / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = skill.split("---", 2)[1]
        self.assertNotIn("end to end", frontmatter)
        self.assertNotIn("producing verified", frontmatter)
        self.assertIn("Blocks unsupported readiness", frontmatter)

    def test_resolve_claude_settings_dir_honors_env_override(self) -> None:
        """The overrides cleanup must never touch the real ~/.claude."""
        updater = self._import_updater()
        with tempfile.TemporaryDirectory() as tmp:
            override = Path(tmp) / "fake" / ".claude" / "skills"
            old = os.environ.get("PAPERSPINE_CLAUDE_SKILLS_DIR")
            os.environ["PAPERSPINE_CLAUDE_SKILLS_DIR"] = str(override)
            try:
                resolved = updater.resolve_claude_settings_dir()
            finally:
                if old is None:
                    os.environ.pop("PAPERSPINE_CLAUDE_SKILLS_DIR", None)
                else:
                    os.environ["PAPERSPINE_CLAUDE_SKILLS_DIR"] = old
            self.assertEqual(resolved, override.parent)
            self.assertNotEqual(resolved, Path.home() / ".claude")

    def test_host_install_rolls_back_if_a_later_entry_fails(self) -> None:
        updater = self._import_updater()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = create_repo(base / "PaperSpine-main", "9.9.9")
            skills = base / "installed" / "codex" / "skills"
            prompts = base / "installed" / "codex" / "prompts"
            existing_skill = skills / "paper-spine" / "SKILL.md"
            existing_prompt = prompts / "paperspine.md"
            existing_skill.parent.mkdir(parents=True)
            existing_prompt.parent.mkdir(parents=True)
            existing_skill.write_text("old skill\n", encoding="utf-8")
            existing_prompt.write_text("old prompt\n", encoding="utf-8")

            env = {
                "PAPERSPINE_CODEX_SKILLS_DIR": str(skills),
                "PAPERSPINE_CODEX_PROMPTS_DIR": str(prompts),
            }
            with mock.patch.dict(os.environ, env), mock.patch.object(
                updater,
                "copy_file",
                side_effect=OSError("simulated prompt write failure"),
            ):
                with self.assertRaises(updater.UpdateError):
                    updater.install_target(repo, "codex")

            self.assertEqual(existing_skill.read_text(encoding="utf-8"), "old skill\n")
            self.assertEqual(existing_prompt.read_text(encoding="utf-8"), "old prompt\n")


if __name__ == "__main__":
    unittest.main()
