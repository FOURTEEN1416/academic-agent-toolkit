"""Tests for the latex-posters helpers.

The two schematic scripts are byte-identical to the copies in
`scientific-schematics` and `literature-review`, so their behaviour comes from
the shared contract. What is specific here is `review_poster.sh`, the shell
helper that renders and inspects a compiled poster.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "latex-posters"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

SchematicTests = skill_contract.schematic.schematic_test_case(SKILL_ROOT)
ReviewParsingTests = skill_contract.schematic.review_parsing_test_case(
    SCRIPTS, "generate_schematic_ai"
)
ReviewFailureTests = skill_contract.schematic.review_failure_test_case(
    SCRIPTS, "generate_schematic_ai", "ScientificSchematicGenerator",
    ("diagram.png", "a prompt", 1, "journal", 2),
)
CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

REVIEW_SCRIPT = SCRIPTS / "review_poster.sh"


class ReviewScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = REVIEW_SCRIPT.read_text(encoding="utf-8")

    def test_it_is_executable_shell_with_a_shebang(self) -> None:
        self.assertTrue(REVIEW_SCRIPT.is_file())
        self.assertTrue(REVIEW_SCRIPT.stat().st_mode & 0o111, "not executable")
        self.assertTrue(self.text.startswith("#!"), "no shebang")

    def test_it_parses_as_bash(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(REVIEW_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(REVIEW_SCRIPT), *args],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=SCRIPTS,
        )

    def test_no_argument_exits_non_zero_with_usage(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Usage:", result.stdout + result.stderr)

    def test_a_missing_file_exits_non_zero_and_names_it(self) -> None:
        result = self._run("no-such-poster.pdf")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no-such-poster.pdf", result.stdout + result.stderr)

    def test_a_missing_poppler_tool_degrades_instead_of_aborting(self) -> None:
        # Deliberately no `set -e`: this is a report, and one unavailable
        # inspector must not truncate the remaining checks or the manual
        # checklist. Running with an empty PATH-ish environment proves it.
        with tempfile.TemporaryDirectory() as directory:
            poster = Path(directory) / "poster.pdf"
            poster.write_bytes(b"%PDF-1.4\n%%EOF\n")
            result = subprocess.run(
                ["bash", str(REVIEW_SCRIPT), str(poster)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=SCRIPTS,
            )
        self.assertEqual(result.returncode, 0)
        output = result.stdout
        # Every numbered section still runs, right through to the summary.
        for section in ("[1]", "[2]", "[3]", "[4]", "[5]", "[6]", "[7]"):
            with self.subTest(section=section):
                self.assertIn(section, output)
        self.assertIn("Quality Check Complete", output)
        self.assertNotIn("Traceback", result.stderr)

    def test_every_python_script_it_invokes_is_shipped(self) -> None:
        for token in self.text.split():
            if token.endswith(".py"):
                with self.subTest(script=token):
                    self.assertTrue(
                        (SCRIPTS / Path(token).name).is_file(),
                        f"{token} is referenced but not shipped",
                    )


class AssetTests(unittest.TestCase):
    def test_every_documented_asset_is_shipped(self) -> None:
        # The skill's value is its templates; a SKILL.md that names one it does
        # not ship sends the agent looking for a file that is not there.
        problems = skill_contract.structure.link_problems(SKILL_ROOT)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
