from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# V4: a single 'paper-spine' skill replaces B's 12-skill flat suite.
# These are the four host copies of the one skill's SKILL.md.
SKILL_COPIES = [
    ROOT / "src" / "skill" / "SKILL.md",
    ROOT / "dist" / "claude" / "skills" / "paper-spine" / "SKILL.md",
    ROOT / "dist" / "codex" / "skills" / "paper-spine" / "SKILL.md",
    ROOT / "dist" / "openclaw" / "skills" / "paper-spine" / "SKILL.md",
    ROOT / "dist" / "hermes" / "skills" / "academic-writing" / "paper-spine" / "SKILL.md",
]


class SkillStructureTests(unittest.TestCase):
    def test_required_project_files_exist(self) -> None:
        required = [
            "README.md",
            "README.en.md",
            "LICENSE",
            ".gitignore",
            "install.ps1",
            "install.sh",
            ".claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            # Single-skill source layout.
            "src/skill/SKILL.md",
            "src/skill/agents/openai.yaml",
            "src/skill/references/task-genre-research.md",
            "src/skill/references/version-requirements.md",
            "src/skill/references/orchestrator-branch-map.md",
            "src/skill/references/local-reference-ingestion.md",
            "src/skill/references/citation-support-bank.md",
            "src/skill/references/writing-rationale-matrix.md",
            # Single-source scripts (B carry-overs).
            "src/scripts/latex_guard.py",
            "src/scripts/revision_audit.py",
            "src/scripts/style_metrics.py",
            "src/scripts/intake_wizard.py",
            "src/scripts/material_inventory.py",
            "src/scripts/artifact_check.py",
            "src/scripts/reference_inventory.py",
            "src/scripts/citation_bank_check.py",
            "src/scripts/word_guard.py",
            "src/scripts/sync_local_installs.py",
            "src/scripts/paperspine_update.py",
            "src/scripts/_paper_spine_utils.py",
            "src/scripts/integrity_audit.py",
            "src/scripts/citation_quality_audit.py",
            "src/scripts/structured_review.py",
            "src/scripts/translate_guard.py",
            "src/scripts/humanize_check.py",
            # New V4 stage scripts.
            "src/scripts/progress_check.py",
            "src/scripts/submission_check.py",
            "src/scripts/respond_check.py",
            "src/scripts/citation_verification_en.py",
            "src/scripts/contribution_check.py",
            "src/scripts/results_validation_check.py",
            "src/scripts/reviewer_audit_check.py",
            # Versioned distribution metadata + the four host copies.
            "dist/paperspine_version.json",
            "dist/claude/skills/paper-spine/SKILL.md",
            "dist/codex/skills/paper-spine/SKILL.md",
            "dist/codex/prompts/paperspine.md",
            "dist/openclaw/skills/paper-spine/SKILL.md",
            "dist/hermes/skills/academic-writing/paper-spine/SKILL.md",
            "dist/claude/commands/paperspine.md",
        ]
        missing = [path for path in required if not (ROOT / path).exists()]
        self.assertEqual(missing, [])

    def test_references_directory_has_enough_playbooks(self) -> None:
        refs = list((ROOT / "src" / "skill" / "references").glob("*.md"))
        self.assertGreater(len(refs), 30)

    def test_version_is_4_0_0(self) -> None:
        import json

        data = json.loads((ROOT / "dist" / "paperspine_version.json").read_text(encoding="utf-8"))
        self.assertEqual(data["version"], "4.0.0")

        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["version"], "4.0.0")

    def test_root_skill_is_absent_to_avoid_duplicate_codex_discovery(self) -> None:
        self.assertFalse((ROOT / "SKILL.md").exists())

    def test_single_skill_distribution_layout(self) -> None:
        # All host copies present; no legacy worker dirs remain anywhere.
        for path in SKILL_COPIES:
            self.assertTrue(path.exists(), f"missing skill copy: {path}")

        legacy_workers = [
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
        ]
        offenders: list[str] = []
        for skills_root in ROOT.glob("dist/*/skills"):
            for worker in legacy_workers:
                if (skills_root / worker).exists():
                    offenders.append(str((skills_root / worker).relative_to(ROOT)))
        # Hermes nests under an extra category directory.
        for worker in legacy_workers:
            nested = ROOT / "dist" / "hermes" / "skills" / "academic-writing" / worker
            if nested.exists():
                offenders.append(str(nested.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_readme_language_switch_and_content_parity(self) -> None:
        english = (ROOT / "README.en.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.md").read_text(encoding="utf-8")

        for text in (english, chinese):
            self.assertIn("[English](README.en.md)", text)
            self.assertIn("[中文](README.md)", text)
            for fragment in [
                "dist/codex/skills",
                "dist/claude/skills",
                "dist/claude/commands",
                "dist/openclaw/skills",
                "install.ps1",
                "install.sh",
                "paper-spine",
                "writing_rationale_matrix",
                "citation_support_bank",
                "translation_package",
                "artifact_check.py",
                "reference_inventory.py",
                "citation_bank_check.py",
                "latex_guard.py",
                "word_guard.py",
            ]:
                self.assertIn(fragment, text)

        english_sections = [line for line in english.splitlines() if line.startswith("## ")]
        chinese_sections = [line for line in chinese.splitlines() if line.startswith("## ")]
        self.assertEqual(len(english_sections), len(chinese_sections))

    def test_no_temporary_artifact_directories(self) -> None:
        tmp_dirs = [path.name for path in ROOT.glob("tmp_*_artifacts") if path.is_dir()]
        self.assertEqual(tmp_dirs, [])

    def test_no_obvious_local_private_paths_in_reusable_files(self) -> None:
        reusable_suffixes = {".md", ".py", ".yaml", ".yml", ".txt", ".json"}
        blocked_fragments = [
            "C:" + "\\Users\\",
            "/Users/",
            "file:" + "///",
            "Bio" + "informatics",
            "M:" + "\\" + "R" + "BP" + "\\",
            "paper" + "_v",
            "oup-" + "authoring",
        ]
        offenders: list[str] = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in reusable_suffixes:
                continue
            if path.name == "test_skill_structure.py":
                continue
            if path.name in ("CLAUDE.md", "AGENTS.md"):
                continue
            if ".git" in path.parts:
                continue
            if "paper_rewriting_output" in path.parts:
                continue
            if "paper-spine-promo-video" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for fragment in blocked_fragments:
                if fragment in text:
                    offenders.append(str(path.relative_to(ROOT)))
                    break
        self.assertEqual(offenders, [])

    def test_no_control_char_corruption_in_text_files(self) -> None:
        # Guards against escaping bugs that mangle backslash content while
        # authoring SKILL.md/references (e.g. "\r"->CR, "\a"->BEL), which silently
        # corrupts LaTeX command guidance like \ref/\autoref. Scans src/ + dist/.
        text_suffixes = {".md", ".py", ".sh", ".ps1", ".json", ".yaml", ".yml", ".toml"}
        control_chars = ("\a", "\b", "\f", "\v")
        offenders: list[str] = []
        for base in ("src", "dist"):
            for path in (ROOT / base).rglob("*"):
                if not path.is_file() or path.suffix.lower() not in text_suffixes:
                    continue
                if "__pycache__" in path.parts:
                    continue
                if ".git" in path.parts or "paper_rewriting_output" in path.parts:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                if any(ch in text for ch in control_chars):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_skill_metadata_files_have_no_utf8_bom(self) -> None:
        offenders = []
        for path in SKILL_COPIES:
            data = path.read_bytes()
            if data.startswith(b"\xef\xbb\xbf"):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_frontmatter_description_is_portable(self) -> None:
        # The single paper-spine SKILL.md (claude copy and its siblings) must keep
        # a portable description <= 200 chars.
        offenders: list[str] = []
        for path in SKILL_COPIES:
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            description = next(line for line in lines if line.startswith("description: "))
            value = description.removeprefix("description: ").strip()
            if len(value) > 200:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
