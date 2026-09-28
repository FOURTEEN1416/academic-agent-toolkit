"""Tests for structured_review.py."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "scripts"))
from structured_review import (
    StructuredReviewReport,
    extract_sections,
    generate_structured_review,
    to_markdown,
    validate_review,
)


def _mktemp_tex(content: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=".tex")
    os.write(fd, content.encode("utf-8"))
    os.close(fd)
    return Path(name)


def _make_out_dir(**files: str) -> Path:
    tmp = Path(tempfile.mkdtemp())
    (tmp / "final_paper").mkdir()
    for name, content in files.items():
        p = tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp


class StructuredReviewTests(unittest.TestCase):
    def test_extract_sections_from_tex(self) -> None:
        tex = (
            r"\section{Introduction}\n"
            "This is the introduction with enough words to pass the minimum word count threshold set at eight words or more.\n"
            r"\section{Methods}\n"
            "The methods section describes experiments performed during this study in sufficient detail for readers.\n"
        )
        path = _mktemp_tex(tex)
        try:
            sections = extract_sections(path)
            self.assertGreaterEqual(len(sections), 2)
        finally:
            path.unlink(missing_ok=True)

    def test_generate_review_includes_three_reviewers(self) -> None:
        tex = r"\section{Test}\nEnough text here to pass the minimum paragraph word count threshold.\n"
        manuscript = _mktemp_tex(tex)
        out_dir = _make_out_dir(
            **{
                "writing_rationale_matrix.md": (
                    "| Row ID | Unit | Motivation | Evidence |\n"
                    "|---|---|---|---|\n"
                    "| 1 | Framework | motivation text here enough detail | evidence |\n"
                    "| 2 | Method unit | method design with enough detail for review | evidence |\n"
                ),
                "evidence_bank.md": "# Evidence\n\n" + "x " * 200,
                "paper_spine_config.json": '{"workflow": "rewrite_existing"}',
            }
        )
        try:
            report = generate_structured_review(out_dir, manuscript)
            reviewer_roles = [r.role for r in report.reviewers]
            self.assertIn("methods", reviewer_roles)
            self.assertIn("contribution", reviewer_roles)
            self.assertIn("clarity", reviewer_roles)
        finally:
            manuscript.unlink(missing_ok=True)

    def test_validate_review_incomplete(self) -> None:
        fd, name = tempfile.mkstemp(suffix=".md")
        os.write(fd, b"# Review\n\n[LLM: fill this in]\n")
        os.close(fd)
        try:
            result = validate_review(Path(name))
            self.assertFalse(result["ok"])
        finally:
            Path(name).unlink(missing_ok=True)

    def test_validate_review_complete(self) -> None:
        text = (
            "Methods & Reproducibility Reviewer\nfindings here\n"
            "Contribution & Novelty Reviewer\nfindings here\n"
            "Structure & Clarity Reviewer\nfindings here\n"
            "Editor Synthesis\nfindings here\n"
            "supported by evidence\n"
        )
        fd, name = tempfile.mkstemp(suffix=".md")
        os.write(fd, text.encode("utf-8"))
        os.close(fd)
        try:
            result = validate_review(Path(name))
            self.assertTrue(result["ok"], msg=str(result.get("findings", [])))
        finally:
            Path(name).unlink(missing_ok=True)

    def test_validate_missing_file(self) -> None:
        result = validate_review(Path("nonexistent.md"))
        self.assertFalse(result["ok"])

    def test_dispatch_generates_three_prompt_files(self) -> None:
        tex = r"\section{Test}\nEnough text here to pass the minimum paragraph word count threshold for testing.\n"
        manuscript = _mktemp_tex(tex)
        out_dir = _make_out_dir(**{
            "paper_spine_config.json": '{"workflow": "rewrite_existing"}',
        })
        try:
            from structured_review import dispatch_review
            result = dispatch_review(out_dir, manuscript)
            self.assertEqual(result["status"], "dispatched")
            prompts_dir = out_dir / "review_prompts"
            self.assertTrue((prompts_dir / "methods_reviewer.md").exists())
            self.assertTrue((prompts_dir / "contribution_reviewer.md").exists())
            self.assertTrue((prompts_dir / "clarity_reviewer.md").exists())
            self.assertTrue((prompts_dir / "dispatch.md").exists())
            # Each prompt should NOT reference the other reviewer role names
            role_labels = {
                "methods_reviewer.md": "Contribution",
                "contribution_reviewer.md": "Methods",
                "clarity_reviewer.md": "Contribution",
            }
            for role_file, forbidden_label in role_labels.items():
                text = (prompts_dir / role_file).read_text(encoding="utf-8")
                self.assertNotIn(f"{forbidden_label} Reviewer", text,
                                 f"{role_file} should not reference {forbidden_label} Reviewer")
        finally:
            manuscript.unlink(missing_ok=True)
            import shutil
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_validate_independence_detects_similarity(self) -> None:
        fd, name = tempfile.mkstemp()
        os.close(fd)
        review_dir = Path(name)
        review_dir.unlink(missing_ok=True)
        review_dir.mkdir()
        try:
            text_a = "The methods section is well described. The contribution is clearly stated. " * 20
            text_b = "The methods section is well described. The contribution is clearly stated. " * 20  # nearly identical
            text_c = "The paper structure is logical and clear. Transitions are smooth throughout. " * 20
            (review_dir / "methods_reviewer.md").write_text(text_a, encoding="utf-8")
            (review_dir / "contribution_reviewer.md").write_text(text_b, encoding="utf-8")
            (review_dir / "clarity_reviewer.md").write_text(text_c, encoding="utf-8")
            from structured_review import validate_independence
            result = validate_independence(review_dir)
            self.assertFalse(result["ok"])  # should detect high similarity between a and b
            self.assertIn("independence_score", result)
        finally:
            import shutil
            shutil.rmtree(review_dir, ignore_errors=True)

    def test_validate_independence_clean(self) -> None:
        fd, name = tempfile.mkstemp()
        os.close(fd)
        review_dir = Path(name)
        review_dir.unlink(missing_ok=True)
        review_dir.mkdir()
        try:
            (review_dir / "methods_reviewer.md").write_text("Methods analysis. " * 30, encoding="utf-8")
            (review_dir / "contribution_reviewer.md").write_text("Contribution analysis. " * 30, encoding="utf-8")
            (review_dir / "clarity_reviewer.md").write_text("Clarity analysis. " * 30, encoding="utf-8")
            from structured_review import validate_independence
            result = validate_independence(review_dir)
            # Different texts should pass independence check
            self.assertTrue(result["independence_score"] > 0.5)
        finally:
            import shutil
            shutil.rmtree(review_dir, ignore_errors=True)

    def test_to_markdown_includes_all_sections(self) -> None:
        from structured_review import EditorSynthesis
        report = StructuredReviewReport("test.tex", sections=[], total_findings=0)
        report.editor = EditorSynthesis(overall_score=80, recommendation="Accept")
        md = to_markdown(report)
        self.assertIn("Structured Peer Review", md)
        self.assertIn("Editor Synthesis", md)


if __name__ == "__main__":
    unittest.main()
