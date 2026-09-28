# pyright: basic, reportMissingImports=false, reportUnusedCallResult=false
"""Tests for HITL claim verifier and dynamic summarizer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from researchclaw.hitl.claim_verifier import Claim, ClaimVerifier, VerificationReport


class TestClaimExtraction:
    def test_extract_citation_brackets(self) -> None:
        verifier = ClaimVerifier(Path("/tmp/fake"))
        verifier._knowledge_base = []
        text = "As shown by [Smith, 2024], transformers are effective."
        claims = verifier.extract_claims(text)
        citation_claims = [c for c in claims if c.claim_type == "citation"]
        assert len(citation_claims) >= 1
        assert "Smith" in citation_claims[0].text

    def test_extract_citation_parens(self) -> None:
        verifier = ClaimVerifier(Path("/tmp/fake"))
        verifier._knowledge_base = []
        text = "Previous work (Johnson et al., 2023) demonstrated this."
        claims = verifier.extract_claims(text)
        citation_claims = [c for c in claims if c.claim_type == "citation"]
        assert len(citation_claims) >= 1

    def test_extract_numerical_claims(self) -> None:
        verifier = ClaimVerifier(Path("/tmp/fake"))
        verifier._knowledge_base = []
        text = "Our method achieves accuracy of 95.3% on CIFAR-10."
        claims = verifier.extract_claims(text)
        numerical = [c for c in claims if c.claim_type == "numerical"]
        assert len(numerical) >= 1
        assert "95.3" in numerical[0].text

    def test_extract_improvement_claims(self) -> None:
        verifier = ClaimVerifier(Path("/tmp/fake"))
        verifier._knowledge_base = []
        text = "This improves by 3.2% over the baseline."
        claims = verifier.extract_claims(text)
        numerical = [c for c in claims if c.claim_type == "numerical"]
        assert len(numerical) >= 1

    def test_extract_comparative_claims(self) -> None:
        verifier = ClaimVerifier(Path("/tmp/fake"))
        verifier._knowledge_base = []
        text = "Our approach outperforms all existing methods."
        claims = verifier.extract_claims(text)
        assert len(claims) >= 1

    def test_extract_from_empty_text(self) -> None:
        verifier = ClaimVerifier(Path("/tmp/fake"))
        verifier._knowledge_base = []
        assert verifier.extract_claims("") == []
        assert verifier.extract_claims("# Header\n\n") == []

    def test_extract_existence_claims(self) -> None:
        verifier = ClaimVerifier(Path("/tmp/fake"))
        verifier._knowledge_base = []
        text = "It has been shown that dropout reduces overfitting."
        claims = verifier.extract_claims(text)
        factual = [c for c in claims if c.claim_type == "factual"]
        assert len(factual) >= 1


class TestClaimVerification:
    def test_verify_citation_grounded(self, tmp_path: Path) -> None:
        # Create knowledge base with a paper by Smith
        cards_dir = tmp_path / "stage-06" / "cards"
        cards_dir.mkdir(parents=True)
        (cards_dir / "paper1.md").write_text(
            "# Attention is All You Need\nAuthors: Smith et al., 2024\n"
            "Abstract: This paper introduces transformers."
        )

        verifier = ClaimVerifier(tmp_path)
        text = "As shown by [Smith, 2024], transformers work well."
        report = verifier.verify_text(text)

        citation_claims = [c for c in report.claims if c.claim_type == "citation"]
        assert len(citation_claims) >= 1
        assert citation_claims[0].grounded is True

    def test_verify_citation_ungrounded(self, tmp_path: Path) -> None:
        verifier = ClaimVerifier(tmp_path)
        verifier._knowledge_base = ["Paper by Johnson about NLP"]

        text = "According to [Nonexistent, 2024], quantum computing is fast."
        report = verifier.verify_text(text)

        citation_claims = [c for c in report.claims if c.claim_type == "citation"]
        if citation_claims:
            assert citation_claims[0].grounded is False

    def test_verify_numerical_with_experiment_data(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-14"
        stage_dir.mkdir()
        (stage_dir / "experiment_summary.json").write_text(
            json.dumps({"metrics_summary": {"accuracy": {"mean": 95.3}}})
        )

        verifier = ClaimVerifier(tmp_path)
        text = "Our method achieves accuracy of 95.3 on the benchmark."
        report = verifier.verify_text(text)

        numerical = [c for c in report.claims if c.claim_type == "numerical"]
        if numerical:
            assert numerical[0].grounded is True

    def test_full_verification_report(self, tmp_path: Path) -> None:
        verifier = ClaimVerifier(tmp_path)
        verifier._knowledge_base = [
            "Smith et al., 2024: Transformers for image classification"
        ]

        text = (
            "As shown by [Smith, 2024], transformers are effective.\n"
            "Our method improves by 5% over the baseline.\n"
            "It has been shown that data augmentation helps.\n"
        )
        report = verifier.verify_text(text)
        assert report.total_claims >= 2
        assert isinstance(report.score, float)

    def test_save_report(self, tmp_path: Path) -> None:
        verifier = ClaimVerifier(tmp_path)
        report = VerificationReport(
            total_claims=5, grounded_claims=3,
            ungrounded_claims=1, unchecked_claims=1, score=0.6,
        )
        path = verifier.save_report(report)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["total_claims"] == 5

    def test_load_shortlist_knowledge(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-05"
        stage_dir.mkdir()
        (stage_dir / "shortlist.jsonl").write_text(
            json.dumps({"title": "Paper A", "abstract": "About transformers"}) + "\n"
            + json.dumps({"title": "Paper B", "abstract": "About CNNs"}) + "\n"
        )

        verifier = ClaimVerifier(tmp_path)
        assert len(verifier._knowledge_base) >= 2


class TestVerificationReport:
    def test_to_dict(self) -> None:
        report = VerificationReport(
            total_claims=10, grounded_claims=7,
            ungrounded_claims=2, unchecked_claims=1,
            score=0.7,
            claims=[Claim(text="test", grounded=True)],
        )
        data = report.to_dict()
        assert data["total_claims"] == 10
        assert len(data["claims"]) == 1


class TestDynamicSummarizer:
    def test_stage_5_analysis(self, tmp_path: Path) -> None:
        from researchclaw.hitl.summarizer import _dynamic_stage_analysis

        stage_dir = tmp_path / "stage-05"
        stage_dir.mkdir()
        lines = [json.dumps({"title": f"Paper {i}"}) for i in range(3)]
        (stage_dir / "shortlist.jsonl").write_text("\n".join(lines))

        analysis = _dynamic_stage_analysis(5, tmp_path)
        assert any("3" in line for line in analysis)
        assert any("Low paper count" in line for line in analysis)

    def test_stage_8_with_novelty(self, tmp_path: Path) -> None:
        from researchclaw.hitl.summarizer import _dynamic_stage_analysis

        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("Hypothesis 1\nHypothesis 2")
        (stage_dir / "novelty_report.json").write_text(
            json.dumps({"novelty_score": 0.85, "assessment": "novel"})
        )

        analysis = _dynamic_stage_analysis(8, tmp_path)
        assert any("0.85" in line for line in analysis)

    def test_stage_17_draft_analysis(self, tmp_path: Path) -> None:
        from researchclaw.hitl.summarizer import _dynamic_stage_analysis

        stage_dir = tmp_path / "stage-17"
        stage_dir.mkdir()
        (stage_dir / "paper_draft.md").write_text(
            "## Introduction\n" + "word " * 1000 + "\n## Method\ntext\n## Experiments\n"
        )

        analysis = _dynamic_stage_analysis(17, tmp_path)
        assert any("words" in line for line in analysis)
        assert any("sections" in line for line in analysis)
