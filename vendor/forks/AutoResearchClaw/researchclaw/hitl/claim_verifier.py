"""Claim verifier: inline fact-checking for research outputs.

Extracts factual claims from LLM-generated text and cross-references
them against collected literature (Stage 6 knowledge cards) to detect:
- Ungrounded claims (not supported by any collected paper)
- Fabricated citations (non-existent papers)
- Numerical claims without evidence (made-up statistics)

Inspired by SAFE (Search-Augmented Factuality Evaluator) and FActScore.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Claim:
    """A factual claim extracted from text."""

    text: str
    claim_type: str = "factual"  # factual | numerical | citation | methodological
    source_line: int = 0
    grounded: bool | None = None  # None = not checked
    evidence: str = ""
    confidence: float = 0.0  # 0-1 how confident in the grounding

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "claim_type": self.claim_type,
            "source_line": self.source_line,
            "grounded": self.grounded,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }


@dataclass
class VerificationReport:
    """Report from claim verification."""

    total_claims: int = 0
    grounded_claims: int = 0
    ungrounded_claims: int = 0
    unchecked_claims: int = 0
    claims: list[Claim] = field(default_factory=list)
    score: float = 1.0  # 0-1, fraction of grounded claims

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_claims": self.total_claims,
            "grounded_claims": self.grounded_claims,
            "ungrounded_claims": self.ungrounded_claims,
            "unchecked_claims": self.unchecked_claims,
            "score": round(self.score, 3),
            "claims": [c.to_dict() for c in self.claims],
        }


class ClaimVerifier:
    """Extract and verify factual claims in research text.

    Verification is done by:
    1. Extracting claims using pattern matching (fast, no LLM needed)
    2. Cross-referencing against knowledge cards from literature
    3. Checking numerical claims against experiment results
    4. Optionally using LLM for deeper verification
    """

    def __init__(self, run_dir: Path, llm_client: Any = None) -> None:
        self.run_dir = run_dir
        self.llm = llm_client
        self._knowledge_base: list[str] = []
        self._load_knowledge_base()

    def verify_text(self, text: str) -> VerificationReport:
        """Verify all claims in a text.

        Args:
            text: The text to verify (hypothesis, paper draft, etc).

        Returns:
            VerificationReport with all claims and their verification status.
        """
        claims = self.extract_claims(text)
        for claim in claims:
            self._verify_claim(claim)

        grounded = sum(1 for c in claims if c.grounded is True)
        ungrounded = sum(1 for c in claims if c.grounded is False)
        unchecked = sum(1 for c in claims if c.grounded is None)
        total = len(claims)

        return VerificationReport(
            total_claims=total,
            grounded_claims=grounded,
            ungrounded_claims=ungrounded,
            unchecked_claims=unchecked,
            claims=claims,
            score=grounded / total if total > 0 else 1.0,
        )

    def extract_claims(self, text: str) -> list[Claim]:
        """Extract factual claims from text using pattern matching.

        Identifies:
        - Citation claims: "[Author, Year]", "(Author et al., Year)"
        - Numerical claims: "achieves 95% accuracy", "improves by 3.2%"
        - Comparative claims: "outperforms", "surpasses", "better than"
        - Existence claims: "X has been shown to", "studies have found"
        """
        claims: list[Claim] = []
        lines = text.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Citation claims — handles: Smith, 2024 | Smith et al., 2024
            # Also handles hyphenated (Smith-Jones) and initials (Smith, J.)
            _author_pat = r'[A-Z][\w\-\.]+'
            _citation_pat = (
                rf'({_author_pat}(?:\s+(?:et\s+al\.?|and\s+{_author_pat}))?'
                r'(?:,?\s*(?:[A-Z]\.?\s*)?(?:,\s*)?\d{4}))'
            )
            for match in re.finditer(
                rf'\[{_citation_pat}\]', stripped
            ):
                claims.append(Claim(
                    text=match.group(0),
                    claim_type="citation",
                    source_line=i,
                ))

            # Parenthetical citations
            for match in re.finditer(
                rf'\({_citation_pat}\)', stripped
            ):
                claims.append(Claim(
                    text=match.group(0),
                    claim_type="citation",
                    source_line=i,
                ))

            # Numerical claims with percentages
            for match in re.finditer(
                r'(?:achieve[sd]?|improve[sd]?|reach(?:es|ed)?|obtain[sed]?|report[sed]?)\s+'
                r'(?:an?\s+)?(?:accuracy|F1|precision|recall|score|AUC|BLEU|ROUGE)\s+'
                r'(?:of\s+)?(\d+\.?\d*)\s*%?',
                stripped, re.IGNORECASE,
            ):
                claims.append(Claim(
                    text=match.group(0),
                    claim_type="numerical",
                    source_line=i,
                ))

            # Improvement claims
            for match in re.finditer(
                r'(?:improve[sd]?|reduc(?:es?|ed)|increas(?:es?|ed))\s+(?:by\s+)?'
                r'(\d+\.?\d*)\s*%',
                stripped, re.IGNORECASE,
            ):
                claims.append(Claim(
                    text=match.group(0),
                    claim_type="numerical",
                    source_line=i,
                ))

            # Comparative claims
            for match in re.finditer(
                r'(?:outperform[sed]*|surpass(?:es|ed)?|superior\s+to|'
                r'better\s+than|state[- ]of[- ]the[- ]art|SOTA)',
                stripped, re.IGNORECASE,
            ):
                claims.append(Claim(
                    text=match.group(0),
                    claim_type="factual",
                    source_line=i,
                ))

            # Existence/attribution claims
            for match in re.finditer(
                r'(?:has\s+been\s+shown|studies\s+have\s+(?:found|shown|demonstrated)|'
                r'it\s+is\s+well[- ]known|previous\s+work\s+(?:has|shows))',
                stripped, re.IGNORECASE,
            ):
                # Get the surrounding sentence
                sentence_start = max(0, stripped.rfind(".", 0, match.start()) + 1)
                sentence_end = stripped.find(".", match.end())
                if sentence_end == -1:
                    sentence_end = len(stripped)
                claims.append(Claim(
                    text=stripped[sentence_start:sentence_end].strip(),
                    claim_type="factual",
                    source_line=i,
                ))

        return claims

    def _verify_claim(self, claim: Claim) -> None:
        """Verify a single claim against the knowledge base."""

        if claim.claim_type == "citation":
            self._verify_citation(claim)
        elif claim.claim_type == "numerical":
            self._verify_numerical(claim)
        elif claim.claim_type == "factual":
            self._verify_factual(claim)

    def _verify_citation(self, claim: Claim) -> None:
        """Check if a citation refers to a real paper in our literature."""
        # Extract author name and year
        match = re.search(r'([A-Z][a-z]+)', claim.text)
        year_match = re.search(r'(\d{4})', claim.text)

        if match:
            author = match.group(1).lower()
            year = year_match.group(1) if year_match else ""

            # Search knowledge base
            for kb_entry in self._knowledge_base:
                kb_lower = kb_entry.lower()
                if author in kb_lower:
                    if not year or year in kb_entry:
                        claim.grounded = True
                        claim.evidence = kb_entry[:100]
                        claim.confidence = 0.8
                        return

            claim.grounded = False
            claim.confidence = 0.6
            claim.evidence = "Citation not found in collected literature"

    def _verify_numerical(self, claim: Claim) -> None:
        """Check numerical claims against experiment results."""
        # Try to find the number in experiment data
        exp_summary = self.run_dir / "stage-14" / "experiment_summary.json"
        if exp_summary.exists():
            try:
                data = json.loads(exp_summary.read_text(encoding="utf-8"))
                data_str = json.dumps(data)
                # Extract the number from the claim
                numbers = re.findall(r'\d+\.?\d*', claim.text)
                for num_str in numbers:
                    if num_str in data_str:
                        claim.grounded = True
                        claim.evidence = f"Number {num_str} found in experiment data"
                        claim.confidence = 0.9
                        return
            except (json.JSONDecodeError, OSError):
                pass

        # Can't verify — mark as unchecked
        claim.grounded = None
        claim.confidence = 0.3

    def _verify_factual(self, claim: Claim) -> None:
        """Verify a factual claim against the knowledge base."""
        # Simple keyword overlap check
        claim_words = set(claim.text.lower().split())
        claim_words -= {"the", "a", "an", "is", "are", "was", "were", "has",
                        "have", "been", "to", "of", "in", "that", "it", "and",
                        "or", "for", "on", "with", "this", "by"}

        if not claim_words:
            claim.grounded = None
            return

        best_overlap = 0.0
        best_evidence = ""

        for kb_entry in self._knowledge_base:
            kb_words = set(kb_entry.lower().split())
            overlap = len(claim_words & kb_words) / len(claim_words) if claim_words else 0
            if overlap > best_overlap:
                best_overlap = overlap
                best_evidence = kb_entry[:100]

        if best_overlap > 0.4:
            claim.grounded = True
            claim.evidence = best_evidence
            claim.confidence = min(best_overlap, 0.9)
        elif best_overlap > 0.2:
            claim.grounded = None  # Uncertain
            claim.confidence = best_overlap
        else:
            claim.grounded = False
            claim.confidence = 0.5
            claim.evidence = "No supporting evidence found in literature"

    def _load_knowledge_base(self) -> None:
        """Load knowledge cards and literature data for verification."""
        # Load knowledge cards from Stage 6
        cards_dir = None
        for candidate in sorted(self.run_dir.glob("stage-06*/cards")):
            if candidate.is_dir():
                cards_dir = candidate
                break

        if cards_dir:
            for card_file in sorted(cards_dir.glob("*.md"))[:50]:
                try:
                    self._knowledge_base.append(
                        card_file.read_text(encoding="utf-8")[:2000]
                    )
                except (OSError, UnicodeDecodeError):
                    pass

        # Load shortlist from Stage 5
        shortlist = None
        for candidate in sorted(self.run_dir.glob("stage-05*/shortlist.jsonl")):
            shortlist = candidate
            break

        if shortlist and shortlist.exists():
            try:
                for line in shortlist.read_text(encoding="utf-8").strip().split("\n"):
                    if line.strip():
                        try:
                            paper = json.loads(line)
                            entry = f"{paper.get('title', '')} {paper.get('abstract', '')}"
                            if entry.strip():
                                self._knowledge_base.append(entry[:1000])
                        except json.JSONDecodeError:
                            pass
            except OSError:
                pass

    def save_report(self, report: VerificationReport, path: Path | None = None) -> Path:
        """Save verification report to disk."""
        if path is None:
            hitl_dir = self.run_dir / "hitl"
            hitl_dir.mkdir(parents=True, exist_ok=True)
            path = hitl_dir / "claim_verification.json"
        path.write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )
        return path
