"""Tests for contribution_check.py (Contribution-First gate)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "scripts" / "contribution_check.py"


VALID_CONTRIBUTION = """# Confirmed Contribution

## Core Contribution

| Field | Content |
|---|---|
| Main contribution statement | We show that sparse routing recovers dense accuracy at one third the inference cost on benchmark X. |
| Contribution type | new method |
| One-sentence reviewer payoff | Practitioners can halve serving cost without retraining or accuracy loss. |

## Why This Contribution Is Needed

| Field | Content |
|---|---|
| Field problem | Large models are too expensive to serve at interactive latency in production settings. |
| Specific gap | No prior router preserves dense accuracy below half the FLOPs on this benchmark family. |
| Concrete challenge | Routing decisions are discrete and non-differentiable, so gradients cannot tune them directly. |
| Why prior work leaves it unresolved | Soft-mixture baselines keep all experts active and therefore never realize the compute savings. |

## How This Paper Responds

| Field | Content |
|---|---|
| Design response | A straight-through gating estimator lets us learn hard routes end to end without auxiliary losses. |
| Evidence required | Matched-accuracy comparison versus dense and soft-mixture baselines plus an ablation of the estimator. |
| Evidence available | Table 2 matched-accuracy results and Table 3 ablation across three seeds support the claim. |
| Evidence missing | None remaining for the core claim; cross-domain transfer is explicitly out of scope here. |

## Claim Boundary

| Field | Content |
|---|---|
| Strong claims allowed | Inference-cost reduction at matched accuracy on benchmark X is fully supported by Table 2. |
| Claims to soften or avoid | Generalization to unseen domains is only suggested, not proven, and is hedged accordingly. |
| Novelty risk | A reviewer may cite prior straight-through routers; we differentiate on the auxiliary-loss-free design. |
| Significance risk | A reviewer may call the setting narrow; we answer with the production-cost stakes in Section 1. |
"""


def _write_dir(text: str | None) -> Path:
    tmp = Path(tempfile.mkdtemp())
    if text is not None:
        (tmp / "confirmed_contribution.md").write_text(text, encoding="utf-8")
    return tmp


def _run(out_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(out_dir), "--markdown"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class ContributionCheckTests(unittest.TestCase):
    def test_filled_fixture_passes(self) -> None:
        out = _write_dir(VALID_CONTRIBUTION)
        res = _run(out)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("Status: PASS", res.stdout)

    def test_missing_file_fails(self) -> None:
        out = _write_dir(None)
        res = _run(out)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("does not exist", res.stdout)

    def test_missing_section_fails(self) -> None:
        # Drop the entire "Claim Boundary" section.
        trimmed = VALID_CONTRIBUTION.split("## Claim Boundary")[0]
        out = _write_dir(trimmed)
        res = _run(out)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("Claim Boundary", res.stdout)

    def test_placeholder_field_fails(self) -> None:
        # Replace a filled cell with a TODO placeholder.
        broken = VALID_CONTRIBUTION.replace(
            "| Design response | A straight-through gating estimator lets us learn hard routes end to end without auxiliary losses. |",
            "| Design response | TODO |",
        )
        out = _write_dir(broken)
        res = _run(out)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("design response", res.stdout.lower())

    def test_empty_cell_fails(self) -> None:
        broken = VALID_CONTRIBUTION.replace(
            "| Specific gap | No prior router preserves dense accuracy below half the FLOPs on this benchmark family. |",
            "| Specific gap |  |",
        )
        out = _write_dir(broken)
        res = _run(out)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
