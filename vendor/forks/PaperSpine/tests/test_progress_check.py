"""Tests for progress_check.py gate logic (V4 fixed gate bugs)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "scripts" / "progress_check.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_contribution_check import VALID_CONTRIBUTION
from test_evidence_grounded_review import _contract as valid_evidence_review_contract
from test_figure_story_check import valid_request, write_request_with_plan
from test_readiness_gates import valid_evidence_ledger
from test_results_validation_check import GOOD_ROW, HEADER
from test_reviewer_audit_check import EDITORIAL, OBJECTION, VALUE_MAP, _doc

VALID_INTEGRATED_REVIEW = """# Integrated Editorial Review

- Review status: PASS

## Editor synthesis

The manuscript presents one coherent contribution and carries it through the evidence chain. Results explain why each analysis is needed, identify the decisive comparisons, and connect the figures without collapsing into captions. Discussion interprets the findings against prior work, alternatives, limitations, and implications. The ending completes the research arc, while the rendered figure order supports the reader's progression. Residual stylistic choices are advisory and do not conceal a claim, evidence, or usability defect.
"""

VALID_STRICT_REVIEW = """# Structured Peer Review

## Methods & Reproducibility Reviewer
Supported methods assessment with specific evidence.

## Contribution & Novelty Reviewer
Supported contribution assessment with specific evidence.

## Structure & Clarity Reviewer
Supported narrative assessment with specific evidence.

## Editor Synthesis
Supported synthesis and revision priority.
"""


def _mkdir(config: dict | None = None, files: dict | None = None) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "paper_rewriting_output"
    tmp.mkdir(parents=True)
    if config is not None:
        (tmp / "paper_spine_config.json").write_text(
            json.dumps(config), encoding="utf-8"
        )
    for name, content in (files or {}).items():
        p = tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp


def _gate(out_dir: Path, gate: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(out_dir), "--gate", gate, *extra],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _add_valid_author_voice_no_op(out: Path) -> None:
    original = out / "author_voice" / "original_manuscript.tex"
    revised = out / "final_paper" / "main.tex"
    authority = out / "scientific_evidence_ledger.json"
    original.parent.mkdir(parents=True, exist_ok=True)
    revised.parent.mkdir(parents=True, exist_ok=True)
    text = "RBPNet may be associated with X at 5 mg."
    original.write_text(text, encoding="utf-8")
    revised.write_text(text, encoding="utf-8")
    authority.write_text('{"claim":"C1","status":"verified"}\n', encoding="utf-8")

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    current = digest(revised)
    profile = {
        "contract": "paperspine.author-voice-profile",
        "schema_version": "1.0",
        "profile_id": "progress-fixture",
        "status": "unavailable",
        "output_language": "en",
        "authorized_sources": [],
        "protected_terms": ["RBPNet"],
        "first_person_policy": "not_profiled",
        "unavailable_reason": "No authorized author corpus in fixture.",
    }
    request = {
        "contract": "paperspine.author-voice-restoration",
        "schema_version": "1.0",
        "mode": "no_op",
        "rewriter_id": "writer",
        "output_language": "en",
        "original": {"path": "author_voice/original_manuscript.tex", "sha256": digest(original)},
        "revised": {"path": "final_paper/main.tex", "sha256": current},
        "authority_files": [{"purpose": "frozen_claim_evidence", "path": "scientific_evidence_ledger.json", "sha256": digest(authority)}],
        "protected_terms": ["RBPNet"],
        "changes": [],
        "semantic_audit": {
            "audit_method": "deterministic_identity",
            "reviewer_id": "deterministic-no-op",
            "independent_from_rewriter": True,
            "status": "pass",
            "original_sha256": current,
            "revised_sha256": current,
            "unsupported_new_claims": 0,
            "claim_strength_drift": 0,
            "causal_direction_changes": 0,
            "negation_changes": 0,
            "modality_uncertainty_changes": 0,
            "citation_meaning_changes": 0,
            "findings": [],
        },
        "author_confirmation": {"status": "confirmed", "confirmed_sha256": current, "confirmed_at": "2026-08-26T16:00:00+08:00"},
    }
    (out / "author_voice_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (out / "author_voice_revision.json").write_text(json.dumps(request), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "src" / "scripts" / "author_voice_check.py"), str(out), "--write", "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stdout + proc.stderr)


class ProgressGateTests(unittest.TestCase):
    def test_author_voice_gate_is_optional_when_disabled(self) -> None:
        out = _mkdir(config={"author_voice_restoration": "off", "word_output": "none"})
        res = _gate(out, "author_voice_restoration")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("disabled", res.stdout)

    def test_author_voice_gate_requires_auditable_receipts_when_enabled(self) -> None:
        out = _mkdir(config={"author_voice_restoration": "standard", "word_output": "none"})
        res = _gate(out, "author_voice_restoration")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("author_voice_profile.json", res.stdout)

    def test_author_voice_gate_accepts_clean_text_no_op(self) -> None:
        out = _mkdir(config={"author_voice_restoration": "standard", "word_output": "none"})
        _add_valid_author_voice_no_op(out)
        res = _gate(out, "author_voice_restoration")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("GATE PASSED", res.stdout)

    def test_integrity_gate_rechecks_author_voice_before_review(self) -> None:
        out = _mkdir(
            config={"author_voice_restoration": "standard", "word_output": "none", "review_policy": "balanced"},
            files={
                "artifact_check.md": "# Artifact Check\n\nStatus: PASS\n",
                "integrity_audit.md": "# Integrity Audit\n\nStatus: PASS\n",
                "structured_review.md": VALID_INTEGRATED_REVIEW,
            },
        )
        _add_valid_author_voice_no_op(out)
        (out / "final_paper" / "main.tex").write_text("RBPNet proves X at 5 mg.", encoding="utf-8")
        res = _gate(out, "integrity_audit")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("Authorial Voice Restoration", res.stdout)

    def test_semantic_confirmation_requires_contribution_and_motivation(self) -> None:
        out = _mkdir(
            config={"scene": "journal", "word_output": "none"},
            files={"confirmed_motivation.md": "# Confirmed Motivation\n\nUser confirmed."},
        )
        res = _gate(out, "semantic_confirmation")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("confirmed_contribution.md", res.stdout)

    def test_legacy_motivation_gate_alias_uses_semantic_contract(self) -> None:
        out = _mkdir(
            config={"scene": "journal", "word_output": "none"},
            files={"confirmed_motivation.md": "# Confirmed Motivation\n\nUser confirmed."},
        )
        res = _gate(out, "motivation_confirmation")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("confirmed_contribution.md", res.stdout)

    def test_planning_runs_results_validation_before_drafting(self) -> None:
        out = _mkdir(
            config={"scene": "journal", "word_output": "none"},
            files={
                "confirmed_contribution.md": VALID_CONTRIBUTION,
                "section_blueprints.md": "# Blueprints\n\nSubstantive plan.",
                "writing_rationale_matrix.md": "# Matrix\n\nSubstantive plan.",
                "results_validation.md": "# Results Validation\n\n" + HEADER,
                "scientific_evidence_ledger.json": json.dumps(valid_evidence_ledger(status="analysis_ready")),
            },
        )
        res = _gate(out, "planning")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("results_validation_check.py", res.stdout)

    def test_planning_passes_with_valid_semantics_and_results_map(self) -> None:
        out = _mkdir(
            config={"scene": "journal", "word_output": "none"},
            files={
                "confirmed_contribution.md": VALID_CONTRIBUTION,
                "section_blueprints.md": "# Blueprints\n\nSubstantive plan.",
                "writing_rationale_matrix.md": "# Matrix\n\nSubstantive plan.",
                "results_validation.md": "# Results Validation\n\n" + HEADER + GOOD_ROW,
                "scientific_evidence_ledger.json": json.dumps(valid_evidence_ledger(status="analysis_ready")),
            },
        )
        res = _gate(out, "planning")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_balanced_planning_does_not_require_rationale_matrix(self) -> None:
        out = _mkdir(
            config={"scene": "journal", "word_output": "none", "review_policy": "balanced"},
            files={
                "confirmed_contribution.md": VALID_CONTRIBUTION,
                "section_blueprints.md": "# Blueprints\n\nSubstantive plan.",
                "results_validation.md": "# Results Validation\n\n" + HEADER + GOOD_ROW,
                "scientific_evidence_ledger.json": json.dumps(valid_evidence_ledger(status="analysis_ready")),
            },
        )
        res = _gate(out, "planning")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_figure_active_planning_requires_complete_story_contract(self) -> None:
        out = _mkdir(
            config={
                "scene": "journal",
                "word_output": "none",
                "review_policy": "balanced",
                "figure_policy": "generate_or_redesign",
            },
            files={
                "confirmed_contribution.md": VALID_CONTRIBUTION,
                "section_blueprints.md": "# Blueprints\n\nSubstantive plan.",
                "results_validation.md": "# Results Validation\n\n" + HEADER + GOOD_ROW,
                "scientific_evidence_ledger.json": json.dumps(valid_evidence_ledger(status="analysis_ready")),
            },
        )
        res = _gate(out, "planning")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("figure_requests.json", res.stdout)

        write_request_with_plan(out, valid_request())
        res = _gate(out, "planning")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_strict_planning_requires_rationale_matrix(self) -> None:
        out = _mkdir(
            config={"scene": "journal", "word_output": "none", "review_policy": "strict"},
            files={
                "confirmed_contribution.md": VALID_CONTRIBUTION,
                "section_blueprints.md": "# Blueprints\n\nSubstantive plan.",
                "results_validation.md": "# Results Validation\n\n" + HEADER + GOOD_ROW,
                "scientific_evidence_ledger.json": json.dumps(valid_evidence_ledger(status="analysis_ready")),
            },
        )
        res = _gate(out, "planning")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("writing_rationale_matrix.md", res.stdout)

    def test_integrity_gate_requires_and_checks_reviewer_audit(self) -> None:
        out = _mkdir(
            config={"scene": "journal", "word_output": "none", "review_policy": "strict"},
            files={
                "artifact_check.md": "# Artifact Check\n\nStatus: PASS\n",
                "integrity_audit.md": "# Integrity Audit\n\nStatus: PASS\n",
                "structured_review.md": VALID_STRICT_REVIEW,
                "reviewer_audit.md": _doc(VALUE_MAP, OBJECTION, EDITORIAL),
            },
        )
        manuscript = out / "final_paper" / "main.tex"
        manuscript.parent.mkdir(parents=True, exist_ok=True)
        manuscript.write_text(
            "\\section{Methods}\nWe sample observations until convergence.\n",
            encoding="utf-8",
        )
        (out / "evidence_review.json").write_text(
            json.dumps(valid_evidence_review_contract(manuscript)), encoding="utf-8"
        )
        (out / "evidence_review_check.md").write_text(
            "# Evidence-Grounded Review Check\n\n- Status: PASS\n",
            encoding="utf-8",
        )
        res = _gate(out, "integrity_audit")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_word_require_with_word_output_none_fails(self) -> None:
        # The fixed bug: --gate word --require must NOT pass just because
        # word_output is disabled; --require forces the docx/report pair.
        out = _mkdir(config={"word_output": "none"})
        res = _gate(out, "word", "--require")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("GATE FAILED", res.stdout)
        self.assertIn("paper.docx", res.stdout)

    def test_word_none_without_require_passes_optout(self) -> None:
        # Without --require, word_output=none is a legitimate opt-out.
        out = _mkdir(config={"word_output": "none"})
        res = _gate(out, "word")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_integrity_audit_status_fail_fails(self) -> None:
        out = _mkdir(
            config={"word_output": "none"},
            files={
                "artifact_check.md": "# Artifact Check\n\nStatus: PASS\n",
                "integrity_audit.md": "# Integrity Audit\n\nStatus: FAIL\n",
                "structured_review.md": VALID_INTEGRATED_REVIEW,
                "reviewer_audit.md": _doc(VALUE_MAP, OBJECTION, EDITORIAL),
            },
        )
        res = _gate(out, "integrity_audit")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("FAIL/BLOCKED", res.stdout)

    def test_integrity_audit_healthy_passes(self) -> None:
        out = _mkdir(
            config={"word_output": "none"},
            files={
                "artifact_check.md": "# Artifact Check\n\nStatus: PASS\n",
                "integrity_audit.md": "# Integrity Audit\n\nStatus: PASS\n",
                "structured_review.md": VALID_INTEGRATED_REVIEW,
                "reviewer_audit.md": _doc(VALUE_MAP, OBJECTION, EDITORIAL),
            },
        )
        res = _gate(out, "integrity_audit")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("GATE PASSED", res.stdout)

    def test_balanced_integrity_allows_one_integrated_review(self) -> None:
        out = _mkdir(
            config={"word_output": "none", "review_policy": "balanced"},
            files={
                "artifact_check.md": "# Artifact Check\n\nStatus: PASS\n",
                "integrity_audit.md": "# Integrity Audit\n\nStatus: PASS\n",
                "structured_review.md": VALID_INTEGRATED_REVIEW,
            },
        )
        res = _gate(out, "integrity_audit")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_strict_integrity_requires_reviewer_audit(self) -> None:
        out = _mkdir(
            config={"word_output": "none", "review_policy": "strict"},
            files={
                "artifact_check.md": "# Artifact Check\n\nStatus: PASS\n",
                "integrity_audit.md": "# Integrity Audit\n\nStatus: PASS\n",
                "structured_review.md": VALID_STRICT_REVIEW,
            },
        )
        res = _gate(out, "integrity_audit")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("reviewer_audit.md", res.stdout)

    def test_balanced_integrity_rejects_unfinished_editorial_brief(self) -> None:
        out = _mkdir(
            config={"word_output": "none", "review_policy": "balanced"},
            files={
                "artifact_check.md": "# Artifact Check\n\nStatus: PASS\n",
                "integrity_audit.md": "# Integrity Audit\n\nStatus: PASS\n",
                "structured_review.md": (
                    "# Integrated Editorial Review\n\n"
                    "- Review status: PENDING_EDITORIAL_REVIEW\n\n"
                    "## Editor synthesis\n\nReplace this guidance with a real judgment."
                ),
            },
        )
        res = _gate(out, "integrity_audit")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("editor synthesis", res.stdout.lower())

    def test_final_audit_invokes_methodology_checks(self) -> None:
        # final_audit must drive contribution, reviewer, and (for journal scenes)
        # results-validation checks. With those artifacts absent, the gate fails
        # and names each failing script.
        out = _mkdir(config={"scene": "journal", "word_output": "none", "review_policy": "strict"})
        res = _gate(out, "final_audit")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("contribution_check.py", res.stdout)
        self.assertIn("reviewer_audit_check.py", res.stdout)
        self.assertIn("results_validation_check.py", res.stdout)

    def test_final_audit_skips_results_for_nonevidence_scene(self) -> None:
        # results_validation only applies to evidence-bearing scenes.
        out = _mkdir(config={"scene": "report", "word_output": "none"})
        res = _gate(out, "final_audit")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertNotIn("results_validation_check.py", res.stdout)
        self.assertIn("contribution_check.py", res.stdout)


class ProgressScanTests(unittest.TestCase):
    def _web_task(self) -> Path:
        root = Path(tempfile.mkdtemp()) / "task-web"
        run_root = root / "run"
        artifacts = run_root / "runner" / "artifacts"
        workspace = root / "workspace"
        artifacts.mkdir(parents=True)
        package_dir = workspace / "publication-package" / "revision-10"
        package_dir.mkdir(parents=True)
        archive = package_dir / "paperspine5-local-target-package.zip"
        members = {"README.md": b"local only\n", "manuscript/paper.pdf": b"%PDF-1.7\n"}
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, encoded in members.items():
                bundle.writestr(name, encoded)

        def store(name: str, value: dict) -> dict:
            encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
            path = artifacts / f"{name}.json"
            path.write_bytes(encoded)
            return {
                "path": path.relative_to(run_root).as_posix(),
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "size_bytes": len(encoded),
            }

        descriptor = {
            "contract": "paperspine5.local-package-archive",
            "local_only": True,
            "external_action_authorized": False,
            "path": archive.relative_to(workspace).as_posix(),
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "size_bytes": archive.stat().st_size,
            "entries": [
                {
                    "archive_path": name,
                    "sha256": hashlib.sha256(encoded).hexdigest(),
                    "size_bytes": len(encoded),
                }
                for name, encoded in members.items()
            ],
        }
        readiness = {
            "contract": "paperspine5.readiness-verdict",
            "ready": True,
            "overall_status": "ready",
            "blockers": [],
            "requested_scope": "local_delivery",
            "is_complete_for_requested_scope": True,
            "manuscript_ready": True,
            "delivery_ready": True,
            "blockers_by_layer": {"local_delivery": []},
            "external_action_authorized": False,
        }
        package = {
            "contract": "paperspine5.target-package-manifest",
            "status": "PASS",
            "external_action_authorized": False,
        }
        material = {"snapshot_sha256": "a" * 64}
        run_contract = {"material_snapshot_sha256": "a" * 64}
        common = store("common", {"ok": True})
        artifact_names = {
            "author_close", "claim_evidence", "publication.manuscript-head",
            "publication.review-closure", "surface_pdf", "surface_word",
            "target_authority", "target_obligations",
        }
        task = {
            "contract": "paperspine5.task-record",
            "status": "completed",
            "run_root": str(run_root),
            "workspace_root": str(workspace),
            "state": {"runner": {
                "contract": "paperspine5.runner-state",
                "stage": "target_package_ready",
                "external_action_authorized": False,
                "issues": [],
                "next_actions": [],
                "academic_artifacts": {
                    **{name: common for name in artifact_names},
                    "publication.readiness": store("readiness", readiness),
                    "publication.target-package": store("package", package),
                },
                "academic_base_artifacts": {"bundle_archive": store("bundle", descriptor)},
                "material_inventory": store("material", material),
                "run_contract": store("run-contract", run_contract),
            }},
        }
        (root / "task_record.json").write_text(json.dumps(task), encoding="utf-8")
        return root

    def test_product_web_task_uses_runner_authority_instead_of_legacy_files(self) -> None:
        out = self._web_task()
        res = subprocess.run(
            [sys.executable, str(SCRIPT), str(out), "--json"],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(0, res.returncode, res.stdout + res.stderr)
        data = json.loads(res.stdout)
        self.assertTrue(data["is_complete"])
        self.assertEqual("complete", data["next_stage"])
        self.assertIn("target_package_ready", data["findings"][0])

    def test_product_web_task_does_not_satisfy_legacy_stage_gate(self) -> None:
        out = self._web_task()
        res = _gate(out, "intake")
        self.assertEqual(1, res.returncode, res.stdout + res.stderr)
        self.assertIn("cannot be satisfied by J11 delivery", res.stdout)
        self.assertIn("product_web_legacy_stage_not_substituted", res.stdout)

    def test_product_web_validation_gate_accepts_completed_task(self) -> None:
        out = self._web_task()
        res = _gate(out, "web_runner_validation")
        self.assertEqual(0, res.returncode, res.stdout + res.stderr)
        self.assertIn("explicit Web validation gate", res.stdout)

    def test_product_web_task_fails_closed_when_archive_changes(self) -> None:
        out = self._web_task()
        archive = next((out / "workspace" / "publication-package").rglob("*.zip"))
        archive.write_bytes(b"tampered")
        res = subprocess.run(
            [sys.executable, str(SCRIPT), str(out), "--json"],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        data = json.loads(res.stdout)
        self.assertFalse(data["is_complete"])
        self.assertEqual("web_runner_validation", data["next_stage"])
        self.assertIn("archive bytes changed", " ".join(data["findings"]))

    def test_missing_output_dir_reports_intake(self) -> None:
        tmp = Path(tempfile.mkdtemp()) / "does_not_exist"
        res = subprocess.run(
            [sys.executable, str(SCRIPT), str(tmp), "--json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        data = json.loads(res.stdout)
        self.assertEqual(data["next_stage"], "intake")
        self.assertFalse(data["is_complete"])


if __name__ == "__main__":
    unittest.main()
