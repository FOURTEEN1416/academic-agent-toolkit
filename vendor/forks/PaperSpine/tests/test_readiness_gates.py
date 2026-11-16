from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "scripts"))

from citation_bank_check import validate as validate_citations
from metadata_readiness_check import validate as validate_metadata
from publication_surface_check import validate as validate_surface
from scientific_evidence_check import validate as validate_evidence
from usage_ledger import validate as validate_usage
from visual_readiness_check import PAGE_CHECKS, _probe_neutral_background, sha256
from visual_readiness_check import prepare as prepare_visual
from visual_readiness_check import validate as validate_visual


def valid_evidence_ledger(status: str = "manuscript_ready", result_state: str = "user_authoritative") -> dict:
    return {
        "schema_version": "1.0",
        "status": status,
        "records": {
            "sources": [{
                "id": "S001", "verification_state": "user_authoritative",
                "evidence_locator": "source.csv", "sha256": "abc",
            }],
            "claims": [{
                "id": "C001", "text": "Bounded claim", "boundary": "One dataset only",
                "source_ids": ["S001"], "result_ids": ["R001"], "used_in_final": True,
            }],
            "numeric_facts": [{
                "id": "N001", "value": "0.031", "unit": "absolute gain",
                "source_ids": ["S001"], "result_ids": ["R001"],
                "verification_state": "user_authoritative", "evidence_locator": "source.csv#2",
            }],
            "methods": [{
                "id": "M001", "name": "Matched comparison", "source_ids": ["S001"],
                "result_ids": ["R001"], "verification_state": "user_authoritative",
                "evidence_locator": "method.json",
            }],
            "outcomes": [{
                "id": "O001", "name": "Accuracy", "definition": "correct / total",
                "source_ids": ["S001"],
            }],
            "results": [{
                "id": "R001", "claim_ids": ["C001"], "numeric_fact_ids": ["N001"],
                "method_ids": ["M001"], "outcome_ids": ["O001"], "source_ids": ["S001"],
                "conditions": "standard split", "uncertainty": "no external validation",
                "verification_state": result_state, "evidence_locator": "source.csv#2",
            }],
        },
    }


class ScientificEvidenceTests(unittest.TestCase):
    def test_final_ledger_passes_when_links_and_states_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scientific_evidence_ledger.json"
            path.write_text(json.dumps(valid_evidence_ledger()), encoding="utf-8")
            result = validate_evidence(path, "final")
            self.assertTrue(result.ok, result.findings)

    def test_final_ledger_rejects_unverified_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scientific_evidence_ledger.json"
            path.write_text(json.dumps(valid_evidence_ledger(result_state="unverified")), encoding="utf-8")
            result = validate_evidence(path, "final")
            self.assertFalse(result.ok)
            self.assertTrue(any("unverified" in finding for finding in result.findings))


class CitationUniquenessTests(unittest.TestCase):
    def test_repeated_claim_uses_do_not_fill_unique_source_quota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "citation_support_bank.md"
            lines = [
                "| Candidate ID | Reference/BibTeX | Year | Recency | Supports Section | Support Claim Sentence | Why This Paper Fits | Source |",
                "|---|---|---|---|---|---|---|---|",
            ]
            for index in range(60):
                key = index % 15
                lines.append(
                    f"| C{index:03d} | @article{{same{key}, year={{2024}}, doi={{10.1000/same{key}}}}} | 2024 | recent | Introduction | "
                    "This paper supports one concrete sentence about the bounded literature context. | "
                    "It fits the same field and the exact claim use recorded here. | local |"
                )
            path.write_text("\n".join(lines), encoding="utf-8")
            result = validate_citations(path, 20, 3, 3, 0.8)
            self.assertFalse(result.ok)
            self.assertEqual(result.unique_source_count, 15)
            self.assertTrue(any("unique sources" in finding for finding in result.findings))

    def test_closed_corpus_accepts_real_local_pool_and_makes_recency_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "citation_support_bank.md"
            lines = [
                "| Candidate ID | Reference/BibTeX | Year | Recency | Supports Section | Support Claim Sentence | Why This Paper Fits | Source |",
                "|---|---|---|---|---|---|---|---|",
            ]
            for index in range(30):
                year = 2024 if index < 3 else 2018
                lines.append(
                    f"| C{index:03d} | @article{{local{index}, year={{{year}}}, doi={{10.1000/local{index}}}}} | {year} | local | Introduction | "
                    "This local paper supports one concrete sentence used by the evidence-bounded rewrite. | "
                    "It is part of the supplied bibliography and supports the exact local claim. | local |"
                )
            path.write_text("\n".join(lines), encoding="utf-8")
            result = validate_citations(path, 20, 3, 3, 0.8, "closed_corpus")
            self.assertTrue(result.ok, result.findings)
            self.assertEqual(result.required_candidates, 20)
            self.assertTrue(any("recency" in warning.lower() for warning in result.warnings or []))


class PublicationAndMetadataTests(unittest.TestCase):
    def test_publication_surface_rejects_inline_evidence_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            final = output / "final_paper"
            final.mkdir()
            (final / "main.tex").write_text("Result [claim:C001] [evidence:S001].", encoding="utf-8")
            result = validate_surface(output)
            self.assertFalse(result.ok)
            self.assertTrue(any("audit tag" in finding for finding in result.findings))

    def test_metadata_accepts_explicit_blinding_and_not_applicable_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "submission_metadata.json"
            fields = {}
            for name in (
                "title", "authors", "affiliations", "corresponding_author", "funding",
                "conflicts", "ethics", "data_availability", "code_availability",
                "author_contributions", "ai_use_disclosure",
            ):
                fields[name] = {"state": "provided", "value": f"value for {name}"}
            fields["authors"] = {"state": "blinded", "reason": "double-blind review"}
            fields["ethics"] = {"state": "not_applicable", "reason": "no human or animal subjects"}
            path.write_text(json.dumps({"fields": fields}), encoding="utf-8")
            self.assertTrue(validate_metadata(path).ok)


class UsageAndVisualTests(unittest.TestCase):
    def test_usage_ledger_accepts_explicit_unavailable_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "usage_ledger.jsonl"
            event = {
                "timestamp": "2026-08-22T12:00:00Z", "stage": "research", "role": "sota",
                "model": "host-managed", "reasoning_effort": "unknown",
                "usage_source": "telemetry_unavailable", "telemetry_note": "host returned no usage",
                "input_hashes": [], "output_artifacts": ["sota_gap_map.md"],
                "gate_result": "pass", "retry": 0,
            }
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            result = validate_usage(path)
            self.assertTrue(result.ok, result.findings)
            self.assertEqual(result.status, "UNAVAILABLE")

    def test_usage_ledger_validates_execution_reuse_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "usage_ledger.jsonl"
            event = {
                "timestamp": "2026-09-01T00:00:00Z",
                "stage": "latex",
                "role": "renderer",
                "model": "host-managed",
                "reasoning_effort": "unknown",
                "usage_source": "host",
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "reasoning_tokens": 0,
                "output_tokens": 0,
                "input_hashes": ["a" * 64],
                "output_artifacts": ["visual_audit/pages"],
                "gate_result": "pass",
                "retry": 0,
                "elapsed_ms": 42,
                "execution_reuse": "hit",
                "execution_receipt": "execution_receipts/pdf-render.json",
            }
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            self.assertTrue(validate_usage(path).ok)

            event.pop("execution_receipt")
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            result = validate_usage(path)
            self.assertFalse(result.ok)
            self.assertTrue(any("requires execution_receipt" in finding for finding in result.findings))

    def test_visual_receipt_is_hash_bound_and_conflicts_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            final = output / "final_paper"
            audit_pages = output / "visual_audit" / "pages"
            final.mkdir(parents=True)
            audit_pages.mkdir(parents=True)
            pdf = final / "paper.pdf"
            tex = final / "main.tex"
            render = audit_pages / "page-1.png"
            pdf.write_bytes(b"%PDF test")
            tex.write_text("\\documentclass{article}\\begin{document}No figures.\\end{document}", encoding="utf-8")
            render.write_bytes(b"PNG test")
            manifest = {
                "paper_pdf": "final_paper/paper.pdf",
                "paper_pdf_sha256": sha256(pdf),
                "main_tex_sha256": sha256(tex),
                "renderer": {"status": "pass", "box_probe_status": "pass"},
                "review": {"status": "pass", "reviewer": "blind visual agent", "reviewed_at": "2026-08-22T12:10:00Z"},
                "pages": [{
                    "page": 1, "render_path": "visual_audit/pages/page-1.png",
                    "render_sha256": sha256(render),
                    "checks": {name: {"status": "pass", "note": "inspected"} for name in PAGE_CHECKS},
                    "status": "pass", "issues": [],
                }],
                "figures": [],
                "unresolved_conflicts": ["Figure 2 visible method name conflicts with caption"],
            }
            (output / "visual_audit_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = validate_visual(output)
            self.assertFalse(result.ok)
            self.assertTrue(any("unresolved visual" in finding for finding in result.findings))

    def test_visual_prepare_reuses_exact_render_snapshot_without_erasing_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            final = output / "final_paper"
            pages = output / "visual_audit" / "pages"
            final.mkdir(parents=True)
            pages.mkdir(parents=True)
            pdf = final / "paper.pdf"
            tex = final / "main.tex"
            render = pages / "page-1.png"
            pdf.write_bytes(b"%PDF exact")
            tex.write_text("\\documentclass{article}\\begin{document}Exact.\\end{document}", encoding="utf-8")
            render.write_bytes(b"PNG exact")
            manifest = {
                "schema_version": "1.1",
                "paper_pdf": "final_paper/paper.pdf",
                "paper_pdf_sha256": sha256(pdf),
                "main_tex_sha256": sha256(tex),
                "figure_requests_sha256": "",
                "renderer": {"status": "pass", "dpi": 144, "box_probe_status": "pass"},
                "review": {"status": "pass", "reviewer": "visual reviewer", "reviewed_at": "2026-09-01T00:00:00Z"},
                "pages": [{
                    "page": 1,
                    "render_path": "visual_audit/pages/page-1.png",
                    "render_sha256": sha256(render),
                    "checks": {name: {"status": "pass", "note": "inspected"} for name in PAGE_CHECKS},
                    "status": "pass",
                    "issues": [],
                }],
                "figures": [],
                "unresolved_conflicts": [],
            }
            manifest_path = output / "visual_audit_manifest.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            before = manifest_path.read_bytes()

            with patch("visual_readiness_check._render_pdf") as renderer:
                reused_path, findings = prepare_visual(output, 144)

            renderer.assert_not_called()
            self.assertEqual(reused_path, manifest_path)
            self.assertEqual(findings, [])
            self.assertEqual(manifest_path.read_bytes(), before)
            self.assertTrue(validate_visual(output).ok)

    def test_visual_prepare_invalidates_when_bound_pdf_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            final = output / "final_paper"
            pages = output / "visual_audit" / "pages"
            final.mkdir(parents=True)
            pages.mkdir(parents=True)
            pdf = final / "paper.pdf"
            tex = final / "main.tex"
            render = pages / "page-1.png"
            pdf.write_bytes(b"%PDF old")
            tex.write_text("\\documentclass{article}\\begin{document}Old.\\end{document}", encoding="utf-8")
            render.write_bytes(b"PNG old")
            (output / "visual_audit_manifest.json").write_text(
                json.dumps({
                    "schema_version": "1.1",
                    "paper_pdf_sha256": sha256(pdf),
                    "main_tex_sha256": sha256(tex),
                    "figure_requests_sha256": "",
                    "renderer": {"dpi": 144},
                    "pages": [{"render_path": "visual_audit/pages/page-1.png", "render_sha256": sha256(render)}],
                    "figures": [],
                }),
                encoding="utf-8",
            )
            pdf.write_bytes(b"%PDF changed")

            def render_changed(_pdf: Path, prefix: Path, _dpi: int, single: bool = False):
                target = prefix.parent / f"{prefix.name}-1.png"
                target.write_bytes(b"PNG changed")
                return [target], ""

            with patch("visual_readiness_check._render_pdf", side_effect=render_changed) as renderer, patch(
                "visual_readiness_check.shutil.which", return_value=None
            ):
                _path, findings = prepare_visual(output, 144)

            renderer.assert_called_once()
            self.assertIn("pdfinfo not found", findings)
            rebuilt = json.loads((output / "visual_audit_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(rebuilt["paper_pdf_sha256"], sha256(pdf))
            self.assertEqual(rebuilt["review"]["status"], "pending")

    def test_background_probe_accepts_white_edges_with_semantic_color_inside(self) -> None:
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "figure.png"
            image = Image.new("RGBA", (240, 160), (255, 255, 255, 255))
            ImageDraw.Draw(image).rectangle((70, 50, 170, 110), fill=(0, 107, 96, 255))
            image.save(path)
            spec = {
                "canvas": {"region_id": "canvas", "bbox_normalized": [0, 0, 1, 1]},
                "axes": [{"region_id": "axis-A", "bbox_normalized": [0.2, 0.2, 0.6, 0.6]}],
                "panels": [{"region_id": "A", "bbox_normalized": [0.1, 0.1, 0.8, 0.8]}],
            }

            receipt = _probe_neutral_background(path, spec)

            self.assertEqual(receipt["status"], "PASS", receipt)
            self.assertTrue(all(region["status"] == "PASS" for region in receipt["regions"]))

    def test_background_probe_rejects_tinted_canvas_and_panel(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "figure.png"
            Image.new("RGB", (240, 160), (251, 250, 247)).save(path)
            spec = {
                "canvas": {"region_id": "canvas", "bbox_normalized": [0, 0, 1, 1]},
                "axes": [],
                "panels": [{"region_id": "A", "bbox_normalized": [0.1, 0.1, 0.8, 0.8]}],
            }

            receipt = _probe_neutral_background(path, spec)

            self.assertEqual(receipt["status"], "FAIL")
            self.assertTrue(any(region["status"] == "FAIL" for region in receipt["regions"]))


if __name__ == "__main__":
    unittest.main()
