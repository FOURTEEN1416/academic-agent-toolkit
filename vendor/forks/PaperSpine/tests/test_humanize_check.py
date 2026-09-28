"""Tests for humanize_check.py."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "scripts"))
from humanize_check import HumanizeCheckResult, check_matrix, count_connectors, to_markdown


class HumanizeCheckTests(unittest.TestCase):
    def _make_out_dir(self, **files: str) -> Path:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "paper_spine_config.json").write_text('{"output_language": "zh"}', encoding="utf-8")
        (tmp / "final_paper").mkdir()
        for name, content in files.items():
            (tmp / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp / name).write_text(content, encoding="utf-8")
        return tmp

    def test_missing_matrix(self) -> None:
        out = self._make_out_dir()
        result = check_matrix(out / "humanize_matrix.md", "", "zh")
        self.assertFalse(result.ok)
        self.assertIn("not found", result.findings[0])

    def test_low_coverage(self) -> None:
        out = self._make_out_dir(**{
            "humanize_matrix.md": (
                "| Row ID | Manuscript Unit | AI Pattern Found | Detection Dim | Severity | Applied Change | Expected Effect | Teaching Note |\n"
                "|---|---|---|---|---|---|---|---|\n"
                "| 1 | P1 | uniform length | sentence structure | High | varied | lower | why |\n"
            ),
            "final_paper/main.tex": "par one." + "x " * 80 + "\n\npar two." + "y " * 80 + "\n\npar three." + "z " * 80,
        })
        result = check_matrix(out / "humanize_matrix.md", (out / "final_paper/main.tex").read_text(), "zh")
        self.assertTrue(any("Coverage" in f for f in result.findings))

    def test_missing_dimensions(self) -> None:
        out = self._make_out_dir(**{
            "humanize_matrix.md": (
                "| Row ID | Unit | AI Pattern Found | Detection Dim | Severity | Applied Change | Expected Effect | Teaching Note |\n"
                "|---|---|---|---|---|---|---|---|\n"
                "| 1 | P1 | uniform | sentence structure | High | varied | lower | why |\n"
            ),
        })
        result = check_matrix(out / "humanize_matrix.md", "", "zh")
        self.assertTrue(any("not covered" in f for f in result.findings))

    def test_count_connectors_zh(self) -> None:
        cnt = count_connectors("首先，此外，综上所述，", "zh")
        self.assertGreaterEqual(cnt, 2)

    def test_to_markdown(self) -> None:
        result = HumanizeCheckResult("test.md", True)
        result.matrix_rows = 5
        result.manuscript_paragraphs = 10
        md = to_markdown(result)
        self.assertIn("PASS", md)

    def test_json_output(self) -> None:
        import json
        result = HumanizeCheckResult("test.md", False)
        result.findings = ["gap"]
        output = json.dumps({"ok": result.ok, "findings": result.findings})
        data = json.loads(output)
        self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()
