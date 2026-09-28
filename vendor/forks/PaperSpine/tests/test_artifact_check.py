from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMMON_ARTIFACTS = [
    "paper_spine_config.json",
    "paper_spine_config.md",
    "source_map.md",
    "reference_materials/source_index.md",
    "research_dossier.md",
    "exemplar_learning_dossier.md",
    "style_profile.md",
    "sota_gap_map.md",
    "motivation_options_after_research.md",
    "citation_support_bank.md",
    "confirmed_contribution.md",
    "confirmed_motivation.md",
    "section_blueprints.md",
    "writing_rationale_matrix.md",
    "latex_report.md",
    "final_artifact_manifest.md",
]
BUILD_ARTIFACTS = [
    "source_inventory.md",
    "evidence_bank.md",
    "figure_asset_map.md",
    "claim_register.md",
]
REWRITE_ARTIFACTS = [
    "original_logic_map.md",
    "evidence_bank.md",
    "rewrite_matrix.md",
    "logic_transfer_audit.md",
]
TRANSLATION_COMMON = [
    "translation_zh/manifest.md",
    "translation_zh/translation_coverage.md",
    "translation_zh/paper_spine_config.zh.md",
    "translation_zh/source_map.zh.md",
    "translation_zh/reference_materials/source_index.zh.md",
    "translation_zh/research_dossier.zh.md",
    "translation_zh/exemplar_learning_dossier.zh.md",
    "translation_zh/style_profile.zh.md",
    "translation_zh/sota_gap_map.zh.md",
    "translation_zh/motivation_options_after_research.zh.md",
    "translation_zh/citation_support_bank.zh.md",
    "translation_zh/confirmed_motivation.zh.md",
    "translation_zh/section_blueprints.zh.md",
    "translation_zh/writing_rationale_matrix.zh.md",
    "translation_zh/final_structure.zh.md",
    "translation_zh/final_paper.zh.md",
    "translation_zh/full_paper_translation.zh.md",
    "translation_zh/latex_report.zh.md",
    "translation_zh/final_artifact_manifest.zh.md",
    "translation_zh/artifact_check.zh.md",
]
TRANSLATION_BUILD = [
    "translation_zh/source_inventory.zh.md",
    "translation_zh/evidence_bank.zh.md",
    "translation_zh/figure_asset_map.zh.md",
    "translation_zh/claim_register.zh.md",
]
TRANSLATION_REWRITE = [
    "translation_zh/original_logic_map.zh.md",
    "translation_zh/rewrite_matrix.zh.md",
    "translation_zh/logic_transfer_audit.zh.md",
]

VALID_RATIONALE_MATRIX = """# Writing Rationale Matrix

| Row ID | Manuscript Unit | Current Problem or Planned Function | Motivation Link | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Change/Text Move | Final Text Check |
|---|---|---|---|---|---|---|---|---|
| R0 | Whole-work framework and throughline | Establish the whole-work structure before drafting any section, so the document is not an append-only polish pass. | The confirmed motivation becomes the spine: every later unit must narrow, operationalize, test, or bound the same contribution rather than introduce parallel claims. | The reference/SOTA pattern learned is a problem-gap-design-evidence-limitation arc: strong examples first define what existing work cannot explain, then make the method choices look necessary, then let results answer the opening gap. | The target scene expects a visible architecture of claims, not isolated section summaries; journal, report, and competition norms all reward a line of reasoning that can be traced from opening problem to final implication. | Evidence anchors are source_map.md, evidence_bank.md, confirmed_motivation.md, and the available figures/tables/citations; no external reference contributes new user results. | Reframe the whole paper around motivation, method choice, evidence sequence, and bounded implication; sequence sections so each planned text move prepares the next one and creates front/back echo. | PASS: framework row controls all later rows, each section can point back to this throughline, and no final claim lacks an evidence anchor. |
| R1 | Executive summary or abstract opening move | State the problem and why the task matters before naming the method, because tool-first openings make the motivation look incidental. | The motivation is narrowed into a reader-facing problem statement that explains why the contribution is needed. | Reference examples use an unresolved task difficulty before method naming, so the abstract reads as an argument rather than an advertisement. | The target venue expects a concise contribution summary with problem, gap, method, evidence, and implication in a small space. | Anchors are confirmed_motivation.md, research_dossier.md, and headline user result claims. | Rewrite the opening as problem-gap-method-evidence, then place numbers only after the reader knows what question they answer. | PASS: final abstract opens with the problem, names evidence, and does not introduce unsupported claims. |
| R2 | Background or problem-restatement unit | Convert broad context into the specific gap the work addresses, instead of accumulating general background. | The motivation controls which background facts remain: only facts that make the central gap visible should stay. | SOTA gap mapping teaches the move of comparing prior limitations before presenting the new angle, avoiding empty novelty language. | The target scene expects the gap before design details, especially for journal and competition readers who need to see why the method exists. | Anchors are sota_gap_map.md, exemplar_learning_dossier.md, and citation keys already available to the manuscript. | Replace generic background with a staged setup: domain importance, unresolved limitation, consequence, and transition to the proposed contribution. | PASS: the gap appears before solution details and cites evidence or references. |
| R3 | Motivation-confirmation paragraph or problem thesis | Make the controlling motivation explicit after the gap, so the paper has one primary contribution rather than several equal slogans. | This row preserves the confirmed motivation as the central spine and prevents secondary method details from competing with it. | Strong reference papers often use a thesis paragraph that turns the literature gap into a testable writing contract for the rest of the paper. | The target scene norm is that readers should know what evidence the paper owes them before entering methods or models. | Anchors are confirmed_motivation.md, motivation_options_after_research.md, and the claim register or original logic map. | Add or rewrite a thesis paragraph that states the primary contribution, subordinates enabling design choices, and previews the evidence sequence. | PASS: later Results and Discussion can be checked against this thesis paragraph. |
| R4 | Method, model, or solution-design unit | Explain why this design is needed, not only what it does, because recipe-style methods do not prove relevance to the motivation. | The method operationalizes the motivation by turning the gap into concrete design choices. | Reference/SOTA examples justify design choices against alternatives and separate necessary mechanisms from implementation detail. | The target scene expects reproducible logic plus rationale, not only architecture labels. | Anchors are claim_register.md or original_logic_map.md, user figures, equations, data descriptions, and method citations. | Place rationale next to each major technical choice: need, choice, alternative, expected effect, and evidence that later evaluates it. | PASS: method unit contains why-this-design logic and does not overclaim beyond available evidence. |
| R5 | Evidence, result, or validation unit | Turn numbers and figures into an argument about the main claim instead of reporting metrics as a list. | Results support the motivation only when each number is interpreted as evidence for the central problem. | Strong examples interpret results immediately after reporting them and connect result order to the promised evidence sequence. | The target scene expects evidence-to-claim continuity and clear independent validation or robustness logic where available. | Anchors are evidence_bank.md, figure_asset_map.md, result tables, dataset descriptions, and cited baselines. | Rewrite result paragraphs as evidence, interpretation, comparison, and limitation; move unsupported claims out or soften them. | PASS: every result claim has a nearby evidence anchor and a stated relevance to the motivation. |
| R6 | Figure, table, heading, or caption unit | Treat visual and heading text as argument-bearing units, not decoration or formatting cleanup. | Captions and headings should help the reader follow how each evidence block supports the motivation. | Reference examples use captions to define the comparison, the measure, and the intended inference without forcing readers to infer the claim alone. | Target venues expect figures/tables to be independently interpretable and consistently labeled. | Anchors are figure_asset_map.md, source_inventory.md, final_paper/main.tex labels, and user-supplied images or tables. | Rewrite headings/captions to state what is being compared, why it matters, and what evidence is safe to infer. | PASS: each caption has a claim boundary and matches the surrounding paragraph. |
| R7 | Limitation, discussion, or recommendation unit | Close by returning to what the evidence does and does not prove, preventing the motivation from becoming an unsupported overclaim. | The motivation is bounded by the evidence, so the final implication is credible rather than inflated. | Reference papers often end by narrowing claims, naming remaining limits, and explaining practical or scientific meaning. | The target scene expects explicit limitations, transferability boundaries, or recommendations depending on journal/report/competition context. | Anchors are claim_register.md, logic_transfer_audit.md, validation evidence, and any missing or weak evidence noted during audit. | Add a bounded conclusion that restates the contribution, names limits, and points to the next step without inventing new data. | PASS: conclusion returns to motivation, cites evidence boundaries, and avoids unverified claims. |
"""

INVALID_RATIONALE_MATRIX = """# Writing Rationale Matrix

| Row ID | Manuscript Unit | Current Problem or Planned Function | Motivation Link | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Change/Text Move | Final Text Check |
|---|---|---|---|---|---|---|---|---|
| R0 | Abstract | improve clarity | x | x | x | x | polish wording | x |
"""


def valid_citation_bank(count: int = 60) -> str:
    lines = [
        "# Citation Support Bank",
        "",
        "| Candidate ID | Reference/BibTeX | Year | Recency | Supports Section | Support Claim Sentence | Why This Paper Fits | Source | Source Channel |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for index in range(1, count + 1):
        year = 2023 + (index % 4)
        lines.append(
            f"| C{index:03d} | @article{{ref{index}, title={{Reference {index}}}, year={{{year}}}, doi={{10.0000/ref{index}}}}} | {year} | recent | Introduction/Discussion | "
            f"Recent work {index} supports the manuscript sentence that related studies motivate this problem and justify a bounded claim. | "
            f"It is a same-field, adjacent, foundational, benchmark, or application reference that can support one specific literature statement. | REF{index:03d} | local |"
        )
    lines.append("")
    return "\n".join(lines)


def run_check(output_dir: Path, workflow: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        "src/scripts/artifact_check.py",
        str(output_dir),
        "--workflow",
        workflow,
        "--markdown",
    ]
    args.extend(extra_args)
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_artifact(output: Path, name: str, content: str = "x") -> None:
    path = output / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_artifacts(output: Path, names: list[str], config: dict[str, object]) -> None:
    for name in names:
        if name == "paper_spine_config.json":
            write_artifact(output, name, json.dumps(config))
        elif name == "writing_rationale_matrix.md":
            write_artifact(output, name, VALID_RATIONALE_MATRIX)
        elif name == "citation_support_bank.md":
            target = int(config.get("citation_target_count", 20)) if isinstance(config, dict) else 20
            write_artifact(output, name, valid_citation_bank(target * 3))
        elif name == "translation_zh/citation_support_bank.zh.md":
            target = int(config.get("citation_target_count", 20)) if isinstance(config, dict) else 20
            write_artifact(output, name, valid_citation_bank(target * 3))
        else:
            write_artifact(output, name)


def write_final_tex(output: Path, *, pdf: bool = False, docx: bool = False) -> None:
    final_paper = output / "final_paper"
    final_paper.mkdir(parents=True, exist_ok=True)
    (final_paper / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}x\\end{document}",
        encoding="utf-8",
    )
    if pdf:
        (final_paper / "paper.pdf").write_bytes(b"%PDF-1.4\n% test fixture\n")
    if docx:
        (final_paper / "paper.docx").write_bytes(b"PK\x03\x04 test fixture")


class ArtifactCheckTests(unittest.TestCase):
    def test_write_option_creates_markdown_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    "src/scripts/artifact_check.py",
                    str(output),
                    "--workflow",
                    "rewrite_existing",
                    "--markdown",
                    "--write",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            report = output / "artifact_check.md"
            self.assertTrue(report.exists())
            self.assertIn("Status: FAIL", report.read_text(encoding="utf-8"))

    def test_rewrite_missing_artifacts_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            write_artifact(
                output,
                "paper_spine_config.json",
                json.dumps({"workflow": "rewrite_existing", "tier": "flash"}),
            )
            result = run_check(output, "rewrite_existing")
            self.assertEqual(result.returncode, 1)
            self.assertIn("FAIL", result.stdout)
            self.assertIn("confirmed_motivation.md", result.stdout)
            self.assertIn("writing_rationale_matrix.md", result.stdout)
            self.assertIn("reference_materials/source_index.md", result.stdout)

    def test_build_complete_minimal_artifacts_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            config = {"workflow": "build_from_materials", "tier": "pro", "word_output": "none"}
            write_artifacts(output, COMMON_ARTIFACTS + BUILD_ARTIFACTS, config)
            write_final_tex(output, pdf=True)
            result = run_check(output, "build_from_materials", "--pdf-policy", "always")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("PASS", result.stdout)

    def test_build_without_final_latex_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            config = {"workflow": "build_from_materials", "tier": "flash"}
            write_artifacts(output, COMMON_ARTIFACTS + BUILD_ARTIFACTS, config)
            result = run_check(output, "build_from_materials", "--pdf-policy", "always")
            self.assertEqual(result.returncode, 1)
            self.assertIn("final_paper/main.tex", result.stdout)
            self.assertIn("final_paper/paper.pdf", result.stdout)

    def test_build_without_pdf_can_pass_when_pdf_policy_never(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            config = {"workflow": "build_from_materials", "tier": "flash", "word_output": "none"}
            write_artifacts(output, COMMON_ARTIFACTS + BUILD_ARTIFACTS, config)
            write_final_tex(output)
            result = run_check(output, "build_from_materials", "--pdf-policy", "never")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_rationale_matrix_content_is_checked_for_both_workflows(self) -> None:
        for workflow, workflow_artifacts in (
            ("build_from_materials", BUILD_ARTIFACTS),
            ("rewrite_existing", REWRITE_ARTIFACTS),
        ):
            with self.subTest(workflow=workflow):
                with tempfile.TemporaryDirectory() as tmp:
                    output = Path(tmp)
                    config = {"workflow": workflow, "tier": "flash"}
                    write_artifacts(output, COMMON_ARTIFACTS + workflow_artifacts, config)
                    write_artifact(output, "writing_rationale_matrix.md", INVALID_RATIONALE_MATRIX)
                    write_final_tex(output)
                    result = run_check(output, workflow, "--pdf-policy", "never")
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("Content Issues", result.stdout)
                    self.assertIn("first data row", result.stdout)
                    self.assertIn("generic or empty", result.stdout)

    def test_citation_support_bank_requires_three_x_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            config = {
                "workflow": "rewrite_existing",
                "tier": "flash",
                "citation_target_count": 20,
            }
            write_artifacts(output, COMMON_ARTIFACTS + REWRITE_ARTIFACTS, config)
            write_artifact(output, "citation_support_bank.md", valid_citation_bank(10))
            write_final_tex(output)
            result = run_check(output, "rewrite_existing", "--pdf-policy", "never")
            self.assertEqual(result.returncode, 1)
            self.assertIn("citation_support_bank.md", result.stdout)
            self.assertIn("fewer than 60", result.stdout)

    def test_requested_word_output_requires_docx_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            config = {
                "workflow": "build_from_materials",
                "tier": "flash",
                "word_output": "docx",
            }
            write_artifacts(output, COMMON_ARTIFACTS + BUILD_ARTIFACTS, config)
            write_final_tex(output)
            result = run_check(output, "build_from_materials", "--pdf-policy", "never")
            self.assertEqual(result.returncode, 1)
            self.assertIn("final_paper/paper.docx", result.stdout)
            self.assertIn("word_report.md", result.stdout)

    def test_english_translation_package_requires_all_common_and_build_translations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            config = {
                "workflow": "build_from_materials",
                "tier": "flash",
                "output_language": "en",
                "translation_package": "zh",
                "word_output": "none",
            }
            write_artifacts(output, COMMON_ARTIFACTS + BUILD_ARTIFACTS, config)
            write_final_tex(output)
            result = run_check(output, "build_from_materials", "--pdf-policy", "never")
            self.assertEqual(result.returncode, 1)
            self.assertIn("translation_zh/research_dossier.zh.md", result.stdout)
            self.assertIn("translation_zh/source_map.zh.md", result.stdout)
            self.assertIn("translation_zh/source_inventory.zh.md", result.stdout)
            write_artifacts(output, TRANSLATION_COMMON + TRANSLATION_BUILD, config)
            write_artifact(output, "translation_zh/translation_coverage.md", "\n".join(TRANSLATION_COMMON + TRANSLATION_BUILD))
            write_artifact(output, "translation_zh/writing_rationale_matrix.zh.md", VALID_RATIONALE_MATRIX)
            result = run_check(output, "build_from_materials", "--pdf-policy", "never")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_english_translation_package_requires_rewrite_specific_translations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            config = {
                "workflow": "rewrite_existing",
                "tier": "pro",
                "output_language": "en",
                "translation_package": "zh",
                "word_output": "none",
            }
            write_artifacts(output, COMMON_ARTIFACTS + REWRITE_ARTIFACTS, config)
            write_artifacts(output, TRANSLATION_COMMON, config)
            write_final_tex(output)
            result = run_check(output, "rewrite_existing", "--pdf-policy", "never")
            self.assertEqual(result.returncode, 1)
            self.assertIn("translation_zh/original_logic_map.zh.md", result.stdout)
            write_artifacts(output, TRANSLATION_REWRITE, config)
            write_artifact(output, "translation_zh/translation_coverage.md", "\n".join(TRANSLATION_COMMON + TRANSLATION_REWRITE))
            write_artifact(output, "translation_zh/writing_rationale_matrix.zh.md", VALID_RATIONALE_MATRIX)
            result = run_check(output, "rewrite_existing", "--pdf-policy", "never")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_translation_package_rejects_partial_large_matrix_translation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            config = {
                "workflow": "rewrite_existing",
                "tier": "pro",
                "output_language": "en",
                "translation_package": "zh",
            }
            write_artifacts(output, COMMON_ARTIFACTS + REWRITE_ARTIFACTS, config)
            write_artifacts(output, TRANSLATION_COMMON + TRANSLATION_REWRITE, config)
            write_artifact(output, "translation_zh/translation_coverage.md", "\n".join(TRANSLATION_COMMON + TRANSLATION_REWRITE))
            write_artifact(output, "translation_zh/writing_rationale_matrix.zh.md", "| 单元 | 翻译 |\n|---|---|\n| 摘要 | 部分翻译 |\n")
            write_final_tex(output)
            result = run_check(output, "rewrite_existing", "--pdf-policy", "never")
            self.assertEqual(result.returncode, 1)
            self.assertIn("writing_rationale_matrix.zh.md", result.stdout)


if __name__ == "__main__":
    unittest.main()

