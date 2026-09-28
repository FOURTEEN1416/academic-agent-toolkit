#!/usr/bin/env python3
"""Mathematical Proof Structure Validator."""

import re
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class ProofAnalysis:
    has_hypothesis: bool = False
    has_proof_body: bool = False
    has_conclusion: bool = False
    proof_type: str = "unknown"
    valid_structure: bool = False


PROOF_TYPES = {
    "direct": ["assume", "therefore", "thus", "hence", "qed"],
    "contradiction": ["assume", "contradiction", "absurd", "impossible"],
    "induction": ["base case", "inductive hypothesis", "inductive step"],
    "contrapositive": ["contrapositive", "suppose not", "implies"]
}


def validate_proof(text: str) -> dict:
    """Validate mathematical proof structure."""
    analysis = ProofAnalysis()
    text_lower = text.lower()

    # Check for hypothesis
    if any(kw in text_lower for kw in ["given", "assume", "let", "suppose"]):
        analysis.has_hypothesis = True

    # Check for proof body indicators
    if any(kw in text_lower for kw in ["because", "since", "by", "from"]):
        analysis.has_proof_body = True

    # Check for conclusion
    if any(kw in text_lower for kw in ["therefore", "thus", "hence", "qed", "∎"]):
        analysis.has_conclusion = True

    # Detect proof type
    for ptype, keywords in PROOF_TYPES.items():
        if any(kw in text_lower for kw in keywords):
            analysis.proof_type = ptype
            break

    analysis.valid_structure = all([
        analysis.has_hypothesis,
        analysis.has_proof_body,
        analysis.has_conclusion
    ])

    return {
        "has_hypothesis": analysis.has_hypothesis,
        "has_proof_body": analysis.has_proof_body,
        "has_conclusion": analysis.has_conclusion,
        "proof_type": analysis.proof_type,
        "valid_structure": analysis.valid_structure,
        "score": sum([analysis.has_hypothesis, analysis.has_proof_body, analysis.has_conclusion]) / 3 * 100
    }


def main():
    import sys
    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text()
    else:
        text = sys.stdin.read()
    print(json.dumps(validate_proof(text), indent=2))


if __name__ == "__main__":
    main()
