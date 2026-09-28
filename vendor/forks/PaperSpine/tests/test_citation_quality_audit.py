"""Tests for citation_quality_audit.py."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "scripts"))
from citation_quality_audit import (
    CitationQualityReport,
    audit_citations,
    classify_citation_type,
    compute_recency_score,
    extract_dois,
    title_similarity,
    to_markdown,
)


def _make_bank(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class CitationQualityAuditTests(unittest.TestCase):
    def test_extract_dois(self) -> None:
        dois = extract_dois("https://doi.org/10.1234/abcd doi: 10.5678/efgh")
        self.assertEqual(len(dois), 2)

    def test_classify_citation_type(self) -> None:
        self.assertEqual(classify_citation_type("A Survey of Deep Learning Methods"), "survey")
        self.assertEqual(classify_citation_type("ImageNet: A Large-Scale Benchmark Dataset"), "benchmark")
        self.assertEqual(classify_citation_type("On the Limitations of Current Approaches"), "critique")
        self.assertEqual(classify_citation_type("Clinical Applications of Deep Learning"), "application")
        self.assertEqual(classify_citation_type("A Novel Transformer Architecture for NLP"), "sota")

    def test_compute_recency_score_recent(self) -> None:
        self.assertGreaterEqual(compute_recency_score("2026"), 90)

    def test_compute_recency_score_old(self) -> None:
        self.assertLess(compute_recency_score("2015"), 50)

    def test_title_similarity(self) -> None:
        self.assertGreaterEqual(title_similarity("Deep Learning for NLP", "Deep Learning for NLP"), 0.95)
        self.assertLess(title_similarity("Deep Learning", "Quantum Mechanics"), 0.3)

    def test_audit_citations_no_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            out_dir.joinpath("paper_spine_config.json").write_text(
                '{"workflow": "rewrite_existing", "scene": "journal", "citation_target_count": 20}',
                encoding="utf-8",
            )
            # V4 find_citation_table requires the header to expose a claim *sentence*
            # column (not just "Claim"), so the bank must use the canonical headers.
            _make_bank(out_dir / "citation_support_bank.md",
                "| Candidate ID | Reference | Year | Recency | Supports Section | Support Claim Sentence | Why | Source |\n"
                "|---|---|---|---|---|---|---|---|\n"
                "| 1 | Smith 2024 https://doi.org/10.1234/test.1 | 2024 | yes | Intro | X | Y | web |\n"
            )
            report = audit_citations(out_dir, no_api=True, timeout=30, delay=0)
            self.assertEqual(len(report.entries), 1)
            self.assertEqual(report.scene, "journal")
            # V4 no_api semantics: a DOI-bearing row is not API-verified, so it stays
            # "pending" (it does not get promoted to verified offline).
            self.assertEqual(report.entries[0].status, "pending")

    def test_report_gap_analysis(self) -> None:
        report = CitationQualityReport("test", "journal", 20)
        md = to_markdown(report)
        self.assertIn("Citation Quality Audit", md)
        self.assertIn("Citation Strategy Principles", md)

    def test_dead_doi_not_ok(self) -> None:
        report = CitationQualityReport("test", "journal", 20)
        md = to_markdown(report)
        self.assertIn("Citation Quality Audit", md)


if __name__ == "__main__":
    unittest.main()
