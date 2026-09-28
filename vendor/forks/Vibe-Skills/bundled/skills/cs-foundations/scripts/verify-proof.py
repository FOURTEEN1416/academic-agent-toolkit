#!/usr/bin/env python3
"""
Mathematical Proof Verification Helper
Validates common proof patterns and checks logical consistency.
"""

import re
import sys
from typing import List, Tuple, Optional

class ProofVerifier:
    """Verifies structure and common patterns in mathematical proofs."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def verify_induction_proof(self, proof_text: str) -> Tuple[bool, List[str]]:
        """
        Verify that an induction proof has all required components.

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []

        # Check for base case
        if not re.search(r'base\s*case|n\s*=\s*[01]|initial\s*case', proof_text, re.I):
            issues.append("Missing base case")

        # Check for inductive hypothesis
        if not re.search(r'inductive\s*hypothesis|assume.*true|suppose.*holds', proof_text, re.I):
            issues.append("Missing inductive hypothesis")

        # Check for inductive step
        if not re.search(r'inductive\s*step|show.*n\+1|prove.*k\+1', proof_text, re.I):
            issues.append("Missing inductive step")

        # Check for conclusion
        if not re.search(r'therefore|thus|hence|QED|proven|by\s*induction', proof_text, re.I):
            issues.append("Missing conclusion statement")

        return len(issues) == 0, issues

    def verify_contradiction_proof(self, proof_text: str) -> Tuple[bool, List[str]]:
        """Verify proof by contradiction structure."""
        issues = []

        # Check for assumption
        if not re.search(r'assume|suppose|let.*false', proof_text, re.I):
            issues.append("Missing contradiction assumption")

        # Check for contradiction
        if not re.search(r'contradiction|impossible|cannot|absurd', proof_text, re.I):
            issues.append("Missing contradiction identification")

        return len(issues) == 0, issues

    def check_logical_symbols(self, text: str) -> List[str]:
        """Check for proper use of logical symbols."""
        warnings = []

        # Common symbol issues
        if '=>' in text and '→' not in text:
            warnings.append("Consider using → instead of =>")

        if 'AND' in text and '∧' not in text:
            warnings.append("Consider using ∧ for logical AND")

        if 'OR' in text and '∨' not in text:
            warnings.append("Consider using ∨ for logical OR")

        return warnings

    def verify_proof(self, proof_text: str, proof_type: str = 'auto') -> dict:
        """
        Main verification method.

        Args:
            proof_text: The proof to verify
            proof_type: 'induction', 'contradiction', 'direct', or 'auto'

        Returns:
            Dictionary with verification results
        """
        result = {
            'valid': True,
            'issues': [],
            'warnings': [],
            'proof_type': proof_type
        }

        # Auto-detect proof type
        if proof_type == 'auto':
            if re.search(r'induction|base\s*case', proof_text, re.I):
                proof_type = 'induction'
            elif re.search(r'contradiction|assume.*false', proof_text, re.I):
                proof_type = 'contradiction'
            else:
                proof_type = 'direct'
            result['proof_type'] = proof_type

        # Verify based on type
        if proof_type == 'induction':
            valid, issues = self.verify_induction_proof(proof_text)
            result['valid'] = valid
            result['issues'] = issues
        elif proof_type == 'contradiction':
            valid, issues = self.verify_contradiction_proof(proof_text)
            result['valid'] = valid
            result['issues'] = issues

        # Check logical symbols
        result['warnings'] = self.check_logical_symbols(proof_text)

        return result


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python verify-proof.py <proof_file> [proof_type]")
        print("proof_type: induction, contradiction, direct, auto (default)")
        sys.exit(1)

    proof_file = sys.argv[1]
    proof_type = sys.argv[2] if len(sys.argv) > 2 else 'auto'

    try:
        with open(proof_file, 'r') as f:
            proof_text = f.read()
    except FileNotFoundError:
        print(f"Error: File '{proof_file}' not found")
        sys.exit(1)

    verifier = ProofVerifier()
    result = verifier.verify_proof(proof_text, proof_type)

    print(f"\n=== Proof Verification Results ===")
    print(f"Detected Type: {result['proof_type']}")
    print(f"Valid: {'Yes' if result['valid'] else 'No'}")

    if result['issues']:
        print(f"\nIssues Found:")
        for issue in result['issues']:
            print(f"  - {issue}")

    if result['warnings']:
        print(f"\nWarnings:")
        for warning in result['warnings']:
            print(f"  - {warning}")

    if result['valid'] and not result['issues']:
        print("\n✓ Proof structure appears valid!")

    sys.exit(0 if result['valid'] else 1)


if __name__ == '__main__':
    main()
