from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "update-reference-tocs.py"
SPEC = importlib.util.spec_from_file_location("update_reference_tocs", SCRIPT)
assert SPEC and SPEC.loader
TOCS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TOCS
SPEC.loader.exec_module(TOCS)


class GithubAnchorTests(unittest.TestCase):
    def test_spaces_around_a_hyphen_are_not_collapsed(self) -> None:
        self.assertEqual(TOCS.github_anchor("Input - Output", {}), "input---output")

    def test_removed_punctuation_leaves_adjacent_hyphens(self) -> None:
        self.assertEqual(TOCS.github_anchor("A & B", {}), "a--b")

    def test_plain_heading_and_duplicates(self) -> None:
        seen: dict[str, int] = {}
        self.assertEqual(TOCS.github_anchor("Grounding checks", seen), "grounding-checks")
        self.assertEqual(TOCS.github_anchor("Grounding checks", seen), "grounding-checks-1")

    def test_code_and_links_are_cleaned_first(self) -> None:
        self.assertEqual(TOCS.github_anchor("Use `x` and [docs](http://a.b)", {}), "use-x-and-docs")


class FencedHeadingTests(unittest.TestCase):
    def test_hash_lines_inside_code_fences_are_not_headings(self) -> None:
        body = "\n".join(f"line {i}" for i in range(110))
        text = "# Title\n\n## Real\n\n```bash\n## install\n```\n\n" + body + "\n\n## Also real\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.md"
            path.write_text(text, encoding="utf-8")
            self.assertTrue(TOCS.add_contents(path))
            out = path.read_text(encoding="utf-8")
        self.assertIn("[Real](#real)", out)
        self.assertIn("[Also real](#also-real)", out)
        self.assertNotIn("[install]", out)


if __name__ == "__main__":
    unittest.main()
