#!/usr/bin/env python3
"""Scan paper_rewriting_output/ and report the first incomplete stage.

Self-contained, standard library only. It does not modify files except when
--write is used to produce progress.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paper_spine_utils import figure_work_required, literature_scope, review_policy
from author_voice_check import validate_author_voice
from evidence_grounded_review import validate_file as validate_evidence_review_file
from structured_review import validate_review


@dataclass
class StageDef:
    key: str
    label: str
    required: list[str]
    config_dependent: bool = False
    workflow: str | None = None


STAGE_PLAYBOOK: dict[str, str | None] = {
    "intake": "intake",
    "research": "research",
    "citation": "citation",
    "semantic_confirmation": "semantic-confirmation",
    "planning": "rewrite",
    "build_from_materials": "build",
    "rewrite_existing": "rewrite",
    "drafting": "rewrite",
    "author_voice_restoration": "humanize",
    "integrity_audit": "audit",
    "latex": "latex",
    "word": "latex",
    "translation": "translate",
    "submission": "submission",
    "final_audit": "audit",
}


# `motivation_confirmation` was the V4 public gate name. Keep it as a CLI
# compatibility alias, but expose the contribution-governed semantic contract
# as the canonical state everywhere else.
STAGE_ALIASES: dict[str, str] = {
    "motivation_confirmation": "semantic_confirmation",
}


STAGES: list[StageDef] = [
    StageDef("intake", "Intake / Configuration", [
        "paper_spine_config.json",
        "paper_spine_config.md",
    ]),
    StageDef("research", "Research", [
        "source_map.md",
        "reference_materials/source_index.md",
        "research_dossier.md",
        "exemplar_learning_dossier.md",
        "style_profile.md",
        "sota_gap_map.md",
        "contribution_options_after_research.md",
        "motivation_options_after_research.md",
    ]),
    StageDef("citation", "Citation Support Bank", [
        "citation_support_bank.md",
    ]),
    StageDef("semantic_confirmation", "Semantic Confirmation (Contribution + Motivation)", [
        "confirmed_contribution.md",
        "confirmed_motivation.md",
    ]),
    StageDef("planning", "Planning / Rationale Matrix", [
        "section_blueprints.md",
        "writing_rationale_matrix.md",
        "scientific_evidence_ledger.json",
    ]),
    StageDef("build_from_materials", "Build From Materials", [
        "source_inventory.md",
        "evidence_bank.md",
        "figure_asset_map.md",
        "claim_register.md",
    ], workflow="build_from_materials"),
    StageDef("rewrite_existing", "Rewrite Existing", [
        "original_logic_map.md",
        "evidence_bank.md",
        "rewrite_matrix.md",
        "logic_transfer_audit.md",
    ], workflow="rewrite_existing"),
    StageDef("drafting", "Drafting / Writing", [
        "final_paper/main.tex",
    ]),
    StageDef("author_voice_restoration", "Authorial Voice Restoration", [
        "author_voice_profile.json",
        "author_voice_revision.json",
        "author_voice_receipt.json",
        "author_voice_report.md",
    ], config_dependent=True),
    StageDef("integrity_audit", "Integrity Audit", [
        "artifact_check.md",
        "integrity_audit.md",
        "structured_review.md",
        "evidence_review.json",
        "evidence_review_check.md",
        "reviewer_audit.md",
    ]),
    StageDef("latex", "LaTeX / PDF", [
        "latex_report.md",
        "final_artifact_manifest.md",
        "visual_audit_manifest.json",
        "visual_readiness_check.md",
        "publication_surface_check.md",
    ]),
    StageDef("word", "Word Output", [
        "final_paper/paper.docx",
        "word_report.md",
    ], config_dependent=True),
    StageDef("translation", "Translation Package", [
        "translation_zh/manifest.md",
        "translation_zh/translation_coverage.md",
        "translation_zh/full_paper_translation.zh.md",
    ], config_dependent=True),
    StageDef("submission", "Submission Package", [
        "submission_package/submission_check.md",
    ], config_dependent=True),
    StageDef("final_audit", "Final Audit", [
        "artifact_check.md",
        "citation_bank_check.md",
        "citation_quality_audit.md",
        "final_artifact_manifest.md",
        "scientific_evidence_check.md",
        "visual_readiness_check.md",
        "publication_surface_check.md",
        "submission_metadata.json",
        "metadata_readiness_check.md",
        "usage_ledger.jsonl",
        "token_budget_by_stage.md",
    ]),
]


WEB_RUNNER_STAGES: list[tuple[str, str]] = [
    ("web_intake", "J1-J3 / Web Intake and Configuration"),
    ("awaiting_research", "J4 / Direction and Target Research"),
    ("awaiting_contribution", "J5 / Contribution Boundary"),
    ("awaiting_claim_graph", "J6 / Claim-Evidence Graph"),
    ("awaiting_figure_intent", "J7 / Figure Intent"),
    ("awaiting_canonical", "J8 / Canonical Manuscript"),
    ("awaiting_review", "J9 / Independent Review"),
    ("awaiting_package", "J10 / Target Adaptation and Author Close"),
    ("target_package_ready", "J11 / Local Delivery"),
]


MISPLACED_RELATIVE_PATHS = (
    "final_paper",
    "writing_rationale_matrix.md",
    "section_blueprints.md",
    "citation_support_bank.md",
    "research_dossier.md",
    "final_artifact_manifest.md",
    "word_report.md",
    "translation_zh",
    "citation_bank_check.md",
    "citation_quality_audit.md",
    "humanize_check.md",
)


@dataclass
class StageStatus:
    key: str
    label: str
    status: str = "PENDING"
    required_artifacts: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)


@dataclass
class ProgressResult:
    output_dir: str
    next_stage: str = "intake"
    next_action: str = ""
    is_complete: bool = False
    stages: list[StageStatus] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    misplaced_artifacts: list[str] = field(default_factory=list)
    readiness: dict[str, bool] = field(default_factory=dict)
    interaction: dict[str, object] = field(default_factory=dict)
    figure_quality: dict[str, object] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan PaperSpine output and report the next incomplete stage."
    )
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write progress.md to the output directory")
    parser.add_argument(
        "--gate",
        choices=[s.key for s in STAGES] + list(STAGE_ALIASES) + [
            "web_runner_validation", "product_web", "local_delivery"
        ],
        help="Check only a specific stage: exit 0 if complete, 1 otherwise.",
    )
    parser.add_argument(
        "--require",
        action="store_true",
        help="With --gate: treat config-dependent stages as required.",
    )
    return parser.parse_args()


def _read_config(out_dir: Path) -> dict:
    config_path = out_dir / "paper_spine_config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            return {}
    return {}


def _artifact_exists(out_dir: Path, rel: str) -> bool:
    return (out_dir / rel).exists()


def _report_contains_fail_blocked(out_dir: Path, rel_path: str) -> bool:
    """Check if a report markdown file exists and contains FAIL or BLOCKED indicators."""
    filepath = out_dir / rel_path
    if not filepath.is_file():
        return False
    try:
        content = filepath.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, UnicodeError):
        try:
            content = filepath.read_text(encoding="utf-16")
        except Exception:
            return False
    except Exception:
        return False
    if re.search(r'Status:\s*(FAIL|BLOCKED)', content, re.IGNORECASE):
        return True
    if re.search(r'(?:Result|Conclusion|Overall|Outcome):\s*(FAIL|BLOCKED)', content, re.IGNORECASE):
        return True
    return False


def _run_script(scripts_dir: Path, script_name: str, args: list[str]) -> tuple[int, str, str]:
    """Run a sibling PaperSpine script, return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(scripts_dir / script_name)] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def _run_final_audit_gate(output_dir: Path, config: dict) -> tuple[bool, str, list[str]]:
    """Actually execute the audit scripts and return pass/fail based on real exit codes."""
    scripts_dir = Path(__file__).resolve().parent
    failures: list[str] = []

    # 1. artifact_check.py
    rc, _stdout, _stderr = _run_script(
        scripts_dir, "artifact_check.py", [str(output_dir), "--markdown", "--write"]
    )
    if rc != 0:
        failures.append(f"artifact_check.py exit {rc}")

    # 2. citation_bank_check.py - reads citation_target_count from config
    try:
        target_count = int(config.get("citation_target_count", 20))
    except (ValueError, TypeError):
        target_count = 20
    citation_path = str(output_dir / "citation_support_bank.md")
    citation_scope = literature_scope(config)
    rc, _stdout, _stderr = _run_script(
        scripts_dir, "citation_bank_check.py",
        [
            citation_path, "--target-count", str(target_count),
            "--scope", citation_scope, "--markdown", "--write",
        ],
    )
    if rc != 0:
        failures.append(f"citation_bank_check.py exit {rc}")

    # 3. integrity_audit.py
    rc, _stdout, _stderr = _run_script(
        scripts_dir, "integrity_audit.py", [str(output_dir), "--markdown", "--write"]
    )
    if rc != 0:
        failures.append(f"integrity_audit.py exit {rc}")

    # The review file must contain real editorial judgment, not the generated
    # brief or unfilled reviewer placeholders.
    review_result = validate_review(output_dir / "structured_review.md")
    if not review_result["ok"]:
        failures.append("structured_review.md incomplete")

    # 4. citation_quality_audit.py
    citation_quality_args = [str(output_dir), "--write"]
    if review_policy(config) == "balanced" and citation_scope == "closed_corpus":
        citation_quality_args.extend([
            "--no-api", "--min-score", "0", "--max-error-ratio", "1.0",
            "--max-pending-ratio", "1.0",
        ])
    rc, _stdout, _stderr = _run_script(
        scripts_dir, "citation_quality_audit.py", citation_quality_args
    )
    if rc != 0:
        failures.append(f"citation_quality_audit.py exit {rc}")

    # 5. word_guard.py - conditional on word output config
    if word_requested(config):
        word_checks: list[tuple[str, str]] = []
        if primary_word_requested(config):
            word_checks.append(("final_paper/paper.docx", "word_report.md"))
        if chinese_word_requested(config):
            word_checks.append(("final_paper/paper.zh.docx", "word_report.zh.md"))

        for docx_rel, report_rel in word_checks:
            docx_path = output_dir / docx_rel
            report_path = output_dir / report_rel
            tex_path = output_dir / "final_paper" / "main.tex"
            args = [str(docx_path), "--markdown", "--output", str(report_path)]
            if tex_path.exists():
                args.extend(["--tex", str(tex_path)])
            rc, _stdout, _stderr = _run_script(scripts_dir, "word_guard.py", args)
            if rc != 0:
                failures.append(f"word_guard.py ({docx_rel}) exit {rc}")

    # 6. Body-level guards (V4): citation linkage + section economy. These read
    #    the manuscript itself, so they only run once main.tex exists; if it is
    #    missing the artifact/drafting gates already fail.
    tex_path = output_dir / "final_paper" / "main.tex"
    if tex_path.exists():
        lg_args = [str(tex_path), "--markdown"]
        bib_path = output_dir / "final_paper" / "references.bib"
        if bib_path.exists():
            lg_args.extend(["--bib", str(bib_path)])
        rc, _stdout, _stderr = _run_script(scripts_dir, "latex_guard.py", lg_args)
        if rc != 0:
            failures.append(f"latex_guard.py exit {rc}")
        try:
            max_sections = int(config.get("max_sections", 6))
        except (ValueError, TypeError):
            max_sections = 6
        rc, _stdout, _stderr = _run_script(
            scripts_dir, "section_economy_check.py",
            [
                str(tex_path), "--max-sections", str(max_sections), "--markdown",
                *(["--enforce"] if review_policy(config) == "strict" else []),
            ],
        )
        if rc != 0:
            failures.append(f"section_economy_check.py exit {rc}")

    # Authorial Voice Restoration runs after the claim/evidence snapshot and
    # reader-facing draft are frozen, but before independent editorial review.
    # Pattern diagnostics are advisory; stale hashes or semantic drift block.
    if author_voice_requested(config):
        rc, _stdout, _stderr = _run_script(
            scripts_dir,
            "author_voice_check.py",
            [str(output_dir), "--markdown", "--write"],
        )
        if rc != 0:
            failures.append(f"author_voice_check.py exit {rc}")

    # 7. Contribution-first / reviewer-aware methodology gates (V4).
    methodology_scripts = ["contribution_check.py"]
    if review_policy(config) == "strict":
        methodology_scripts.append("reviewer_audit_check.py")
    for script in methodology_scripts:
        rc, _stdout, _stderr = _run_script(scripts_dir, script, [str(output_dir), "--markdown", "--write"])
        if rc != 0:
            failures.append(f"{script} exit {rc}")
    if review_policy(config) == "strict":
        evidence_contract = output_dir / "evidence_review.json"
        evidence_args = ["validate", str(evidence_contract)]
        manuscript = output_dir / "final_paper" / "main.tex"
        if manuscript.is_file():
            evidence_args.extend(["--manuscript", str(manuscript)])
        evidence_args.extend(["--markdown", "--write"])
        rc, _stdout, _stderr = _run_script(
            scripts_dir, "evidence_grounded_review.py", evidence_args
        )
        if rc != 0:
            failures.append(f"evidence_grounded_review.py exit {rc}")
    # Results-as-Validation applies only to evidence-bearing scenes.
    if str(config.get("scene") or "").lower() in ("journal", "conference", "competition"):
        rc, _stdout, _stderr = _run_script(
            scripts_dir, "results_validation_check.py", [str(output_dir), "--markdown", "--write"]
        )
        if rc != 0:
            failures.append(f"results_validation_check.py exit {rc}")

        rc, _stdout, _stderr = _run_script(
            scripts_dir, "scientific_evidence_check.py", [str(output_dir), "--phase", "final", "--markdown", "--write"]
        )
        if rc != 0:
            failures.append(f"scientific_evidence_check.py exit {rc}")

    if figure_work_required(output_dir, config):
        rc, _stdout, _stderr = _run_script(
            scripts_dir, "figure_story_check.py",
            [str(output_dir), "--phase", "final", "--markdown", "--write"],
        )
        if rc != 0:
            failures.append(f"figure_story_check.py exit {rc}")

    # Existing-asset selection is a hash-bound decision, not a one-time note.
    # If either side exists, require the request/receipt pair and recompute it
    # against current files so an older figure or mutated data file cannot keep
    # a stale PASS through final audit.
    asset_request = output_dir / "asset_selection_request.json"
    asset_receipt = output_dir / "asset_selection_receipt.json"
    if asset_request.exists() or asset_receipt.exists():
        if not asset_request.is_file() or not asset_receipt.is_file():
            failures.append("asset selection request/receipt pair incomplete")
        else:
            rc, _stdout, _stderr = _run_script(
                scripts_dir,
                "asset_selection.py",
                [str(asset_request), "--verify-receipt", str(asset_receipt), "--json"],
            )
            if rc != 0:
                failures.append(f"asset_selection.py receipt verification exit {rc}")

    # 8. Reader-visible and delivery-state gates. Visual review is deliberately
    #    separate from TeX source checks: it binds receipts to rendered pages
    #    and figure assets by hash.
    for script in (
        "visual_readiness_check.py",
        "publication_surface_check.py",
        "metadata_readiness_check.py",
        "usage_ledger.py",
    ):
        rc, _stdout, _stderr = _run_script(
            scripts_dir, script, [str(output_dir), "--markdown", "--write"]
        )
        if rc != 0:
            failures.append(f"{script} exit {rc}")

    if failures:
        return False, (
            f"GATE FAILED: Final Audit - {len(failures)} script(s) failed: {', '.join(failures)}"
        ), failures

    return True, "GATE PASSED: Final Audit - all scripts passed.", []


def _recalc_first_pending(stages: list[StageStatus]) -> StageStatus | None:
    for stage in stages:
        if stage.status in ("PENDING", "BLOCKED"):
            return stage
    return None


def workflow_from_config(config: dict) -> str:
    workflow = str(config.get("workflow") or "rewrite_existing")
    return "build_from_materials" if workflow == "build_from_materials" else "rewrite_existing"


def evidence_bearing_scene(config: dict) -> bool:
    return str(config.get("scene") or "").strip().lower() in {
        "journal", "conference", "competition"
    }


def author_voice_requested(config: dict) -> bool:
    """Return whether the evidence-bound voice-restoration lane is enabled.

    ``humanize_tier`` remains a compatibility input, but no longer selects an
    AI-detector optimization target.
    """
    explicit = config.get("author_voice_restoration")
    if isinstance(explicit, dict):
        explicit = explicit.get("enabled", True)
    if explicit is not None:
        if explicit is False:
            return False
        return str(explicit).strip().lower() not in {"none", "off", "false", "no", "0", "disabled"}
    legacy = str(config.get("humanize_tier") or "none").strip().lower()
    return legacy in {"light", "medium", "heavy"}


def word_requested(config: dict) -> bool:
    if "word_output" not in config:
        return True
    value = config.get("word_output")
    if value is False:
        return False
    return str(value).strip().lower() not in {"none", "false", "no", "0"}


def translation_requested(config: dict) -> bool:
    return str(config.get("translation_package") or "none").strip().lower() == "zh"


def chinese_word_requested(config: dict) -> bool:
    output_language = str(config.get("output_language") or "").strip().lower()
    return word_requested(config) and (output_language == "zh" or translation_requested(config))


def primary_word_requested(config: dict) -> bool:
    output_language = str(config.get("output_language") or "").strip().lower()
    return word_requested(config) and output_language != "zh"


def submission_requested(output_dir: Path, config: dict) -> bool:
    return (output_dir / "submission_package").exists() or bool(config.get("submission_requested"))


def required_artifacts_for_stage(
    stage: StageDef, config: dict, require: bool = False, output_dir: Path | None = None
) -> list[str]:
    required = list(stage.required)
    if review_policy(config) == "balanced":
        if stage.key == "planning":
            required = [item for item in required if item != "writing_rationale_matrix.md"]
        if stage.key == "integrity_audit":
            required = [
                item for item in required
                if item not in {
                    "reviewer_audit.md",
                    "evidence_review.json",
                    "evidence_review_check.md",
                }
            ]
    if stage.key == "planning" and not evidence_bearing_scene(config):
        required = [item for item in required if item != "scientific_evidence_ledger.json"]
    if stage.key == "final_audit" and not evidence_bearing_scene(config):
        required = [item for item in required if item != "scientific_evidence_check.md"]
    if stage.key == "planning" and evidence_bearing_scene(config):
        required.append("results_validation.md")
    figure_active = output_dir is not None and figure_work_required(output_dir, config)
    if stage.key == "planning" and figure_active:
        required.append("figure_requests.json")
    if stage.key == "final_audit" and figure_active:
        required.append("figure_story_check.md")
    if stage.key == "final_audit" and author_voice_requested(config):
        required.extend([
            "author_voice_profile.json",
            "author_voice_revision.json",
            "author_voice_receipt.json",
            "author_voice_report.md",
        ])
    if stage.key == "word":
        if require:
            # --require forces the Word gate even when word_output is none:
            # the standard pair must exist (or the zh pair when output_language=zh).
            output_language = str(config.get("output_language") or "").strip().lower()
            if output_language == "zh":
                required = ["final_paper/paper.zh.docx", "word_report.zh.md"]
            else:
                required = ["final_paper/paper.docx", "word_report.md"]
                if chinese_word_requested(config):
                    required.extend(["final_paper/paper.zh.docx", "word_report.zh.md"])
        else:
            if not primary_word_requested(config):
                required = []
            if chinese_word_requested(config):
                required.extend(["final_paper/paper.zh.docx", "word_report.zh.md"])
    return required


def detect_misplaced_artifacts(output_dir: Path) -> list[str]:
    parent = output_dir.parent
    misplaced: list[str] = []
    for rel in MISPLACED_RELATIVE_PATHS:
        if (parent / rel).exists() and not (output_dir / rel).exists():
            misplaced.append(rel)
    nested = output_dir / "paper_rewriting_output"
    if nested.is_dir():
        misplaced.append(
            "paper_rewriting_output/ (nested: artifacts written one level too deep - "
            "move contents up into the outer paper_rewriting_output/ and remove the inner one)"
        )
    if (parent / "final_paper").is_dir() and (output_dir / "final_paper").is_dir():
        if "final_paper" not in misplaced:
            misplaced.append(
                "final_paper (sibling: exists both in parent and inside paper_rewriting_output - "
                "remove the parent-level copy and keep only the one under paper_rewriting_output/)"
            )
    return misplaced


def stage_applies(stage: StageDef, output_dir: Path, config: dict, require: bool = False) -> bool:
    if stage.workflow and stage.workflow != workflow_from_config(config):
        return False
    if not stage.config_dependent:
        return True
    if require:
        return True
    if stage.key == "word":
        return word_requested(config)
    if stage.key == "translation":
        return translation_requested(config)
    if stage.key == "submission":
        return submission_requested(output_dir, config)
    if stage.key == "author_voice_restoration":
        return author_voice_requested(config)
    return True


def stage_skip_message(stage: StageDef) -> str:
    if stage.workflow:
        return "Stage not applicable for this workflow."
    if stage.key == "word":
        return "Word output explicitly disabled; gate passes (opt-out)."
    if stage.key == "translation":
        return "Translation not requested; gate passes (opt-out)."
    if stage.key == "submission":
        return "Submission not requested; gate passes (opt-out)."
    if stage.key == "author_voice_restoration":
        return "Authorial Voice Restoration explicitly disabled; gate passes (opt-out)."
    return "Stage not applicable."


def _product_web_progress(output_dir: Path) -> ProgressResult | None:
    """Verify a Product Web task instead of misreading it as legacy output.

    Product Web stores its authority in ``task_record.json`` plus hash-bound
    Runner artifacts, not in the V4 flat-file names.  This projection does not
    manufacture compatibility files.  It verifies the actual task record,
    readiness verdict, package manifest, source snapshot, and deterministic ZIP
    before reporting J11 complete.
    """

    record_path = output_dir / "task_record.json"
    if not record_path.is_file():
        return None
    result = ProgressResult(str(output_dir))

    def fail(message: str) -> ProgressResult:
        result.next_stage = "web_runner_validation"
        result.next_action = "Repair or resume the Product Web task; do not create legacy placeholder artifacts."
        result.is_complete = False
        result.readiness = {
            "scientific_content_ready": False,
            "visual_ready": False,
            "citation_verified": False,
            "metadata_ready": False,
            "artifact_portable": False,
        }
        result.findings.append(message)
        return result

    try:
        task = json.loads(record_path.read_text(encoding="utf-8"))
        if not isinstance(task, dict) or task.get("contract") != "paperspine5.task-record":
            return fail("Product Web task_record.json contract is invalid.")
        state = task.get("state")
        runner = state.get("runner") if isinstance(state, dict) else None
        if not isinstance(runner, dict) or runner.get("contract") != "paperspine5.runner-state":
            return fail("Product Web Runner state is missing or invalid.")
        interaction = runner.get("interaction")
        if isinstance(interaction, dict):
            result.interaction = {
                "mode": interaction.get("mode"),
                "requested_scope": interaction.get("requested_scope"),
                "grant_status": interaction.get("grant_status"),
                "grant_id": interaction.get("grant_id"),
                "grant_sha256": interaction.get("grant_sha256"),
                "decision_classes": list(interaction.get("decision_classes", [])),
                "decision_receipts": list(interaction.get("decision_receipts", [])),
                "external_action_authorized": False,
            }
        academic_base = runner.get("academic_base_artifacts")
        if isinstance(academic_base, dict):
            corrections = sorted(
                artifact_id
                for artifact_id in academic_base
                if str(artifact_id).startswith("figure-correction.")
            )
            legibility = sorted(
                artifact_id
                for artifact_id in academic_base
                if str(artifact_id).startswith("target-size-legibility.")
            )
            result.figure_quality = {
                "contract": "paperspine5.figure-quality-projection",
                "contract_version": "1.0",
                "correction_receipts": corrections,
                "target_size_legibility_receipts": legibility,
                "status": "PASS" if legibility else "not_evaluated",
                "external_action_authorized": False,
            }
        current = str(runner.get("stage") or "web_intake")
        stage_keys = [key for key, _label in WEB_RUNNER_STAGES]
        current_index = stage_keys.index(current) if current in stage_keys else 0
        ready_stage = current == "target_package_ready"
        for index, (key, label) in enumerate(WEB_RUNNER_STAGES):
            stage = StageStatus(key=key, label=label)
            if ready_stage or index < current_index:
                stage.status = "DONE"
            else:
                stage.status = "PENDING"
                if index == current_index:
                    stage.missing_artifacts = [f"Runner stage is {current}"]
            result.stages.append(stage)

        if not ready_stage:
            result.next_stage = current
            next_actions = runner.get("next_actions")
            result.next_action = (
                str(next_actions[0])
                if isinstance(next_actions, list) and next_actions
                else f"Resume the Product Web task from Runner stage '{current}'."
            )
            result.readiness = {
                "scientific_content_ready": False,
                "visual_ready": False,
                "citation_verified": False,
                "metadata_ready": False,
                "artifact_portable": False,
            }
            result.findings.append(
                f"Product Web task is active at {current}; legacy flat-file intake is not required."
            )
            return result

        run_root = Path(str(task.get("run_root") or "")).resolve()
        workspace_root = Path(str(task.get("workspace_root") or "")).resolve()
        if not run_root.is_dir() or not workspace_root.is_dir():
            return fail("Product Web run/workspace root is missing.")

        def load_pointer(pointer: object, label: str) -> dict:
            if not isinstance(pointer, dict):
                raise ValueError(f"{label} pointer is missing")
            raw_path = pointer.get("path")
            if not isinstance(raw_path, str) or not raw_path:
                raise ValueError(f"{label} pointer path is missing")
            path = (run_root / raw_path).resolve()
            try:
                path.relative_to(run_root)
            except ValueError as exc:
                raise ValueError(f"{label} pointer escapes the run root") from exc
            encoded = path.read_bytes()
            if (
                hashlib.sha256(encoded).hexdigest() != pointer.get("sha256")
                or len(encoded) != pointer.get("size_bytes")
            ):
                raise ValueError(f"{label} pointer bytes changed")
            value = json.loads(encoded.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError(f"{label} pointer is not an object")
            return value

        artifacts = runner.get("academic_artifacts")
        bases = runner.get("academic_base_artifacts")
        if not isinstance(artifacts, dict) or not isinstance(bases, dict):
            return fail("Product Web academic artifact ledgers are missing.")
        required_artifacts = {
            "claim_evidence",
            "publication.manuscript-head",
            "publication.readiness",
            "publication.review-closure",
            "publication.target-package",
            "surface_pdf",
            "surface_word",
            "target_authority",
        }
        missing_artifacts = sorted(required_artifacts - set(artifacts))
        if missing_artifacts:
            return fail(
                "Product Web completion is missing Runner artifacts: "
                + ", ".join(missing_artifacts)
            )

        readiness = load_pointer(artifacts["publication.readiness"], "readiness")
        requested_scope = str(readiness.get("requested_scope") or "")
        if requested_scope == "submission_package":
            submission_artifacts = {"author_close", "target_obligations"}
            missing_submission = sorted(submission_artifacts - set(artifacts))
            if missing_submission:
                return fail(
                    "Product Web submission scope is missing Runner artifacts: "
                    + ", ".join(missing_submission)
                )
        package = load_pointer(artifacts["publication.target-package"], "target package")
        descriptor = load_pointer(bases.get("bundle_archive"), "bundle archive")
        material_ledger = load_pointer(runner.get("material_inventory"), "material ledger")
        run_contract = load_pointer(runner.get("run_contract"), "run contract")
        if (
            readiness.get("contract") != "paperspine5.readiness-verdict"
            or requested_scope not in {"manuscript", "local_delivery", "submission_package"}
            or readiness.get("is_complete_for_requested_scope") is not True
            or readiness.get("manuscript_ready") is not True
            or readiness.get("delivery_ready") is not True
            or readiness.get("external_action_authorized") is not False
        ):
            return fail("Product Web readiness verdict is not complete for the requested local scope.")
        layer_blockers = readiness.get("blockers_by_layer")
        if (
            not isinstance(layer_blockers, dict)
            or layer_blockers.get(requested_scope) != []
        ):
            return fail("Product Web requested-scope blocker register is not empty.")
        if (
            package.get("contract") != "paperspine5.target-package-manifest"
            or package.get("status") != "PASS"
            or package.get("external_action_authorized") is not False
        ):
            return fail("Product Web target package manifest is not PASS.")
        if (
            descriptor.get("contract") != "paperspine5.local-package-archive"
            or descriptor.get("local_only") is not True
            or descriptor.get("external_action_authorized") is not False
        ):
            return fail("Product Web bundle descriptor is not a local-only archive.")
        archive_path = (workspace_root / str(descriptor.get("path") or "")).resolve()
        try:
            archive_path.relative_to(workspace_root)
        except ValueError as exc:
            raise ValueError("bundle archive escapes the task workspace") from exc
        archive_bytes = archive_path.read_bytes()
        if (
            hashlib.sha256(archive_bytes).hexdigest() != descriptor.get("sha256")
            or len(archive_bytes) != descriptor.get("size_bytes")
        ):
            return fail("Product Web bundle archive bytes changed.")
        entries = descriptor.get("entries")
        if not isinstance(entries, list) or not entries:
            return fail("Product Web bundle descriptor entries are missing.")
        entry_map = {
            str(entry.get("archive_path")): entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("archive_path")
        }
        if len(entry_map) != len(entries):
            return fail("Product Web bundle descriptor contains duplicate/invalid entries.")
        with zipfile.ZipFile(archive_path, "r") as bundle:
            if bundle.testzip() is not None or set(bundle.namelist()) != set(entry_map):
                return fail("Product Web bundle archive failed CRC or member verification.")
            for name, entry in entry_map.items():
                encoded = bundle.read(name)
                if (
                    hashlib.sha256(encoded).hexdigest() != entry.get("sha256")
                    or len(encoded) != entry.get("size_bytes")
                ):
                    return fail(f"Product Web bundle member changed: {name}")
        if material_ledger.get("snapshot_sha256") != run_contract.get("material_snapshot_sha256"):
            return fail("Product Web material ledger and run contract snapshots differ.")
        unresolved = [
            issue
            for issue in runner.get("issues", [])
            if isinstance(issue, dict) and issue.get("status") != "resolved"
        ]
        if (
            task.get("status") != "completed"
            or runner.get("external_action_authorized") is not False
            or unresolved
            or runner.get("next_actions") not in ([], None)
        ):
            return fail("Product Web task has unresolved work or external authorization.")

        result.next_stage = "complete"
        result.next_action = (
            "Product Web J11 local delivery is complete and hash-verified; "
            "external upload/submission remains unauthorized."
        )
        result.is_complete = True
        result.readiness = {
            "manuscript_ready": True,
            "delivery_ready": True,
            "submission_ready": readiness.get("submission_ready") is True,
            "external_action_authorized": False,
        }
        result.findings.append(
            "Product Web authority verified at target_package_ready: requested scope complete, deterministic local ZIP valid, "
            f"submission_ready={readiness.get('submission_ready') is True}, external action locked."
        )
        return result
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, zipfile.BadZipFile) as exc:
        return fail(f"Product Web verification failed: {exc}")


def gate_check(output_dir: Path, stage_key: str, require: bool = False) -> tuple[bool, str, list[str]]:
    web_result = _product_web_progress(output_dir)
    if web_result is not None:
        # Product Web has its own J1-J11 state machine. A completed local
        # delivery is not evidence that an arbitrary legacy stage gate passed;
        # only the explicit Web validation gate may consume this projection.
        web_gates = {"web_runner_validation", "product_web", "local_delivery"}
        if stage_key not in web_gates:
            return False, (
                f"GATE NOT APPLICABLE: Product Web task is governed by its Runner stages; "
                f"legacy stage '{stage_key}' cannot be satisfied by J11 delivery. "
                "Use --gate web_runner_validation or resume the Web task."
            ), ["product_web_legacy_stage_not_substituted"]
        if web_result.is_complete:
            return True, (
                "GATE PASSED: Product Web Runner verified J11 local delivery; "
                "the explicit Web validation gate is covered by the current READY verdict."
            ), []
        return False, (
            f"GATE FAILED: Product Web task is at {web_result.next_stage}. "
            "Resume it in the Web workspace; do not create legacy placeholder files."
        ), list(web_result.findings)
    config = _read_config(output_dir)
    stage_key = STAGE_ALIASES.get(stage_key, stage_key)
    stage_def = next((s for s in STAGES if s.key == stage_key), None)
    if stage_def is None:
        return False, f"Unknown stage: {stage_key}", []
    if not stage_applies(stage_def, output_dir, config, require=require):
        return True, stage_skip_message(stage_def), []

    if stage_key == "final_audit":
        return _run_final_audit_gate(output_dir, config)

    required = required_artifacts_for_stage(stage_def, config, require=require, output_dir=output_dir)
    missing = [art for art in required if not _artifact_exists(output_dir, art)]
    if missing:
        return False, (
            f"GATE FAILED: {stage_def.label} - missing: {', '.join(missing)}. "
            "Return to this stage and produce the missing artifacts before continuing."
        ), missing

    # Methodology checks run at their owning upstream stages. Final audit still
    # re-runs them, but it must never be the first place a weak semantic contract,
    # unmapped Results plan, or missing reviewer audit is discovered.
    scripts_dir = Path(__file__).resolve().parent
    if stage_key in {"semantic_confirmation", "planning"}:
        rc, _stdout, _stderr = _run_script(
            scripts_dir, "contribution_check.py", [str(output_dir), "--markdown", "--write"]
        )
        if rc != 0:
            return False, (
                f"GATE FAILED: {stage_def.label} - contribution_check.py exit {rc}. "
                "Return to semantic confirmation and repair the contribution contract."
            ), ["contribution_check.py"]

    if stage_key == "planning" and evidence_bearing_scene(config):
        rc, _stdout, _stderr = _run_script(
            scripts_dir, "results_validation_check.py", [str(output_dir), "--markdown", "--write"]
        )
        if rc != 0:
            return False, (
                f"GATE FAILED: {stage_def.label} - results_validation_check.py exit {rc}. "
                "Map every major Results unit to a contribution promise before drafting."
            ), ["results_validation_check.py"]

        rc, _stdout, _stderr = _run_script(
            scripts_dir, "scientific_evidence_check.py",
            [str(output_dir), "--phase", "planning", "--markdown", "--write"],
        )
        if rc != 0:
            return False, (
                f"GATE FAILED: {stage_def.label} - scientific_evidence_check.py exit {rc}. "
                "Separate and link sources, claims, numeric facts, methods, outcomes, and results before drafting."
            ), ["scientific_evidence_check.py"]

    if stage_key == "planning" and figure_work_required(output_dir, config):
        rc, _stdout, _stderr = _run_script(
            scripts_dir, "figure_story_check.py",
            [str(output_dir), "--phase", "planning", "--markdown", "--write"],
        )
        if rc != 0:
            return False, (
                f"GATE FAILED: {stage_def.label} - figure_story_check.py exit {rc}. "
                "Define each figure's question, main claim, hero panel, panel jobs, evidence anchors, "
                "claim boundary, and Results unit before drafting."
            ), ["figure_story_check.py"]

    if stage_key == "author_voice_restoration":
        result = validate_author_voice(output_dir)
        if not result.ok:
            return False, (
                "GATE FAILED: Authorial Voice Restoration - semantic invariants, "
                "provenance, independent audit, or author confirmation are incomplete."
            ), [f"{item.code}: {item.message}" for item in result.hard_findings]

    # FAIL/BLOCKED content checks (mirrors check_progress post-processing)
    if stage_key == "integrity_audit" and _report_contains_fail_blocked(output_dir, "integrity_audit.md"):
        return False, (
            f"GATE FAILED: {stage_def.label} - integrity_audit.md reports FAIL/BLOCKED. "
            "Resolve the audit findings and re-run before continuing."
        ), ["integrity_audit.md: FAIL/BLOCKED"]

    if stage_key == "integrity_audit" and _report_contains_fail_blocked(output_dir, "artifact_check.md"):
        return False, (
            f"GATE FAILED: {stage_def.label} - artifact_check.md reports FAIL/BLOCKED. "
            "Re-run audit before continuing."
        ), ["artifact_check.md: FAIL/BLOCKED"]

    if stage_key == "integrity_audit":
        if author_voice_requested(config):
            voice_result = validate_author_voice(output_dir)
            if not voice_result.ok:
                return False, (
                    "GATE FAILED: Integrity Audit - Authorial Voice Restoration receipt "
                    "is missing, stale, or blocked."
                ), [f"{item.code}: {item.message}" for item in voice_result.hard_findings]
        review_result = validate_review(output_dir / "structured_review.md")
        if not review_result["ok"]:
            return False, (
                f"GATE FAILED: {stage_def.label} - structured_review.md is still a brief "
                "or lacks a completed editor synthesis. Read and revise the manuscript, "
                "then set Review status: PASS."
            ), review_result["findings"]

    if stage_key == "integrity_audit" and review_policy(config) == "strict":
        evidence_contract = output_dir / "evidence_review.json"
        manuscript = output_dir / "final_paper" / "main.tex"
        evidence_result = validate_evidence_review_file(
            evidence_contract,
            manuscript if manuscript.is_file() else None,
        )
        if not evidence_result.ok:
            return False, (
                f"GATE FAILED: {stage_def.label} - evidence_review.json is not "
                "grounded in the current manuscript or has invalid tool/literature receipts."
            ), evidence_result.errors
        rc, _stdout, _stderr = _run_script(
            scripts_dir, "reviewer_audit_check.py", [str(output_dir), "--markdown", "--write"]
        )
        if rc != 0:
            return False, (
                f"GATE FAILED: {stage_def.label} - reviewer_audit_check.py exit {rc}. "
                "Build the reviewer audit from structured review findings before LaTeX assembly."
            ), ["reviewer_audit_check.py"]

    if stage_key == "citation":
        try:
            target_count = int(config.get("citation_target_count", 20))
        except (ValueError, TypeError):
            target_count = 20
        rc, _stdout, _stderr = _run_script(
            scripts_dir,
            "citation_bank_check.py",
            [
                str(output_dir / "citation_support_bank.md"),
                "--target-count", str(target_count),
                "--scope", literature_scope(config),
                "--markdown", "--write",
            ],
        )
        if rc != 0:
            return False, (
                f"GATE FAILED: {stage_def.label} - citation_bank_check.py exit {rc}. "
                "Source coverage and recency are counted by unique bibliographic source, not repeated claim-use rows."
            ), ["citation_bank_check.py"]

    if stage_key == "word" and _report_contains_fail_blocked(output_dir, "word_report.md"):
        return False, (
            f"GATE FAILED: {stage_def.label} - word_report.md reports FAIL/BLOCKED. "
            "Re-run word stage before continuing."
        ), ["word_report.md: FAIL/BLOCKED"]

    if stage_key == "word" and _report_contains_fail_blocked(output_dir, "word_report.zh.md"):
        return False, (
            f"GATE FAILED: {stage_def.label} - word_report.zh.md reports FAIL/BLOCKED. "
            "Re-run Chinese Word stage before continuing."
        ), ["word_report.zh.md: FAIL/BLOCKED"]

    if stage_key == "latex" and _report_contains_fail_blocked(output_dir, "latex_report.md"):
        paper_pdf_missing = not _artifact_exists(output_dir, "final_paper/paper.pdf")
        paper_docx_missing = primary_word_requested(config) and not _artifact_exists(output_dir, "final_paper/paper.docx")
        zh_docx_missing = chinese_word_requested(config) and not _artifact_exists(output_dir, "final_paper/paper.zh.docx")
        if paper_pdf_missing or paper_docx_missing or zh_docx_missing:
            return False, (
                f"GATE FAILED: {stage_def.label} - latex_report.md reports FAIL/BLOCKED "
                "with missing outputs. Re-run latex before continuing."
            ), ["latex_report.md: FAIL/BLOCKED"]

    if stage_key == "latex":
        for script in ("publication_surface_check.py", "visual_readiness_check.py"):
            rc, _stdout, _stderr = _run_script(
                scripts_dir, script, [str(output_dir), "--markdown", "--write"]
            )
            if rc != 0:
                return False, (
                    f"GATE FAILED: {stage_def.label} - {script} exit {rc}. "
                    "Return to final assembly, re-render, inspect, and resolve reader-visible defects."
                ), [script]

    return True, f"GATE PASSED: {stage_def.label} - all required artifacts present.", []


def _next_action_for_stage(stage: StageStatus, config: dict, misplaced: list[str]) -> str:
    prefix = ""
    if misplaced:
        prefix = (
            "Misplaced artifacts detected in the wrong directory; rebuild or move them into "
            "paper_rewriting_output before declaring completion. "
        )
    if stage.status == "BLOCKED":
        return prefix + f"Stage '{stage.label}' is BLOCKED. User confirmation required before continuing."

    playbook = STAGE_PLAYBOOK.get(stage.key)
    if stage.key == "semantic_confirmation":
        playbook = "semantic-confirmation"
    elif stage.key in {"planning", "drafting"}:
        playbook = "build" if workflow_from_config(config) == "build_from_materials" else "rewrite"
    if playbook:
        return (
            prefix
            + f"Resume from stage '{stage.label}'. Missing artifacts: {', '.join(stage.missing_artifacts)}. "
            + f"Read references/{playbook}.md for instructions."
        )
    return prefix + f"Resume from stage '{stage.label}'. Missing artifacts: {', '.join(stage.missing_artifacts)}."


def check_progress(output_dir: Path) -> ProgressResult:
    web_result = _product_web_progress(output_dir)
    if web_result is not None:
        return web_result
    result = ProgressResult(str(output_dir))

    if not output_dir.exists():
        result.next_stage = "intake"
        result.next_action = "Output directory does not exist. Start from intake to create paper_spine_config.json."
        result.findings.append("Output directory not found - begin from intake.")
        return result

    config = _read_config(output_dir)
    result.misplaced_artifacts = detect_misplaced_artifacts(output_dir)

    first_pending: StageStatus | None = None
    for stage_def in STAGES:
        stage = StageStatus(
            key=stage_def.key,
            label=stage_def.label,
            required_artifacts=required_artifacts_for_stage(stage_def, config, output_dir=output_dir),
        )

        if not stage_applies(stage_def, output_dir, config):
            stage.status = "SKIPPED" if stage_def.workflow else "OPTIONAL"
            result.stages.append(stage)
            continue

        missing = [art for art in stage.required_artifacts if not _artifact_exists(output_dir, art)]
        stage.missing_artifacts = missing
        if not missing:
            stage.status = "DONE"
        elif stage_def.key == "semantic_confirmation" and (
            _artifact_exists(output_dir, "contribution_options_after_research.md")
            or _artifact_exists(output_dir, "motivation_options_after_research.md")
        ):
            stage.status = "BLOCKED"
        else:
            stage.status = "PENDING"

        if first_pending is None and stage.status in {"PENDING", "BLOCKED"}:
            first_pending = stage
        result.stages.append(stage)

    # Post-process report content for FAIL/BLOCKED indicators
    artifact_check_fail = _report_contains_fail_blocked(output_dir, "artifact_check.md")
    citation_bank_check_fail = _report_contains_fail_blocked(output_dir, "citation_bank_check.md")
    citation_quality_audit_fail = _report_contains_fail_blocked(output_dir, "citation_quality_audit.md")
    word_report_fail = _report_contains_fail_blocked(output_dir, "word_report.md")
    zh_word_report_fail = _report_contains_fail_blocked(output_dir, "word_report.zh.md")
    latex_report_fail = _report_contains_fail_blocked(output_dir, "latex_report.md")
    contribution_check_fail = _report_contains_fail_blocked(output_dir, "contribution_check.md")
    results_validation_check_fail = _report_contains_fail_blocked(output_dir, "results_validation_check.md")
    reviewer_audit_check_fail = _report_contains_fail_blocked(output_dir, "reviewer_audit_check.md")
    evidence_review_check_fail = _report_contains_fail_blocked(output_dir, "evidence_review_check.md")
    author_voice_report_fail = _report_contains_fail_blocked(output_dir, "author_voice_report.md")
    scientific_evidence_check_fail = _report_contains_fail_blocked(output_dir, "scientific_evidence_check.md")
    visual_readiness_check_fail = _report_contains_fail_blocked(output_dir, "visual_readiness_check.md")
    publication_surface_check_fail = _report_contains_fail_blocked(output_dir, "publication_surface_check.md")
    metadata_readiness_check_fail = _report_contains_fail_blocked(output_dir, "metadata_readiness_check.md")
    structured_review_result = validate_review(output_dir / "structured_review.md")
    structured_review_fail = not structured_review_result["ok"]

    if author_voice_report_fail and author_voice_requested(config):
        for stage in result.stages:
            if stage.key in ("author_voice_restoration", "integrity_audit", "final_audit") and stage.status == "DONE":
                stage.status = "PENDING"
                stage.missing_artifacts = [
                    "author_voice_report.md reports BLOCKED - restore semantic invariants and re-confirm the current revision"
                ]
        result.findings.append(
            "author_voice_report.md reports BLOCKED - independent review cannot begin on this revision"
        )

    if structured_review_fail:
        for stage in result.stages:
            if stage.key in ("integrity_audit", "final_audit") and stage.status == "DONE":
                stage.status = "PENDING"
                stage.missing_artifacts = [
                    "structured_review.md needs a completed editor synthesis"
                ]
        result.findings.extend(structured_review_result["findings"])

    if contribution_check_fail:
        for stage in result.stages:
            if stage.key in ("semantic_confirmation", "planning", "final_audit") and stage.status == "DONE":
                stage.status = "PENDING"
                stage.missing_artifacts = [
                    "contribution_check.md reports FAIL/BLOCKED - semantic contract must be repaired"
                ]
        result.findings.append(
            "contribution_check.md reports FAIL/BLOCKED - semantic confirmation must be re-run"
        )

    if results_validation_check_fail:
        for stage in result.stages:
            if stage.key in ("planning", "final_audit") and stage.status == "DONE":
                stage.status = "PENDING"
                stage.missing_artifacts = [
                    "results_validation_check.md reports FAIL/BLOCKED - Results plan must be repaired"
                ]
        result.findings.append(
            "results_validation_check.md reports FAIL/BLOCKED - planning must be re-run"
        )

    if reviewer_audit_check_fail and review_policy(config) == "strict":
        for stage in result.stages:
            if stage.key in ("integrity_audit", "final_audit") and stage.status == "DONE":
                stage.status = "PENDING"
                stage.missing_artifacts = [
                    "reviewer_audit_check.md reports FAIL/BLOCKED - reviewer audit must be repaired"
                ]
        result.findings.append(
            "reviewer_audit_check.md reports FAIL/BLOCKED - integrity audit must be re-run"
        )

    if evidence_review_check_fail and review_policy(config) == "strict":
        for stage in result.stages:
            if stage.key in ("integrity_audit", "final_audit") and stage.status == "DONE":
                stage.status = "PENDING"
                stage.missing_artifacts = [
                    "evidence_review_check.md reports FAIL/BLOCKED - grounded review must be repaired"
                ]
        result.findings.append(
            "evidence_review_check.md reports FAIL/BLOCKED - integrity audit must be re-run"
        )

    if artifact_check_fail:
        for stage in result.stages:
            if stage.key in ("integrity_audit", "final_audit"):
                if stage.status == "DONE":
                    stage.status = "PENDING"
                    stage.missing_artifacts = [
                        "artifact_check.md reports FAIL/BLOCKED - audit must be re-run"
                    ]
        result.findings.append(
            "artifact_check.md reports FAIL/BLOCKED - integrity/final audit must be re-run"
        )

    if citation_bank_check_fail:
        for stage in result.stages:
            if stage.key in ("citation", "final_audit") and stage.status == "DONE":
                stage.status = "PENDING"
                stage.missing_artifacts = [
                    "citation_bank_check.md reports FAIL/BLOCKED - citation bank must be re-run"
                ]
        result.findings.append(
            "citation_bank_check.md reports FAIL/BLOCKED - citation support bank must be re-run"
        )

    if citation_quality_audit_fail:
        for stage in result.stages:
            if stage.key == "final_audit" and stage.status == "DONE":
                stage.status = "PENDING"
                stage.missing_artifacts = [
                    "citation_quality_audit.md reports FAIL/BLOCKED - citation quality audit must be re-run"
                ]
        result.findings.append(
            "citation_quality_audit.md reports FAIL/BLOCKED - citation quality audit must be re-run"
        )

    if word_report_fail:
        for stage in result.stages:
            if stage.key == "word" and stage.status == "DONE":
                stage.status = "PENDING"
                stage.missing_artifacts = [
                    "word_report.md reports FAIL/BLOCKED - word must be re-run"
                ]
        result.findings.append(
            "word_report.md reports FAIL/BLOCKED - word stage must be re-run"
        )

    if zh_word_report_fail:
        for stage in result.stages:
            if stage.key == "word" and stage.status == "DONE":
                stage.status = "PENDING"
                stage.missing_artifacts = [
                    "word_report.zh.md reports FAIL/BLOCKED - Chinese Word must be re-run"
                ]
        result.findings.append(
            "word_report.zh.md reports FAIL/BLOCKED - Chinese Word stage must be re-run"
        )

    if latex_report_fail:
        paper_pdf_missing = not _artifact_exists(output_dir, "final_paper/paper.pdf")
        paper_docx_missing = primary_word_requested(config) and not _artifact_exists(output_dir, "final_paper/paper.docx")
        zh_docx_missing = chinese_word_requested(config) and not _artifact_exists(output_dir, "final_paper/paper.zh.docx")
        if paper_pdf_missing or paper_docx_missing or zh_docx_missing:
            for stage in result.stages:
                if stage.key == "latex" and stage.status == "DONE":
                    stage.status = "PENDING"
                    stage.missing_artifacts = [
                        "latex_report.md reports FAIL/BLOCKED with missing output - latex must be re-run"
                    ]
            result.findings.append(
                "latex_report.md reports FAIL/BLOCKED with missing outputs - latex must be re-run"
            )

    new_gate_failures = {
        "scientific_evidence_check.md": scientific_evidence_check_fail,
        "visual_readiness_check.md": visual_readiness_check_fail,
        "publication_surface_check.md": publication_surface_check_fail,
        "metadata_readiness_check.md": metadata_readiness_check_fail,
    }
    for report_name, failed in new_gate_failures.items():
        if not failed:
            continue
        for stage in result.stages:
            if stage.key == "final_audit" and stage.status == "DONE":
                stage.status = "PENDING"
                stage.missing_artifacts = [f"{report_name} reports FAIL/BLOCKED"]
        result.findings.append(f"{report_name} reports FAIL/BLOCKED - final audit must be re-run")

    def report_passes(name: str) -> bool:
        return (output_dir / name).is_file() and not _report_contains_fail_blocked(output_dir, name)

    result.readiness = {
        "scientific_content_ready": (
            report_passes("integrity_audit.md")
            and not structured_review_fail
            and (
                review_policy(config) == "balanced"
                or (
                    report_passes("evidence_review_check.md")
                    and report_passes("reviewer_audit_check.md")
                )
            )
            and report_passes("contribution_check.md")
            and (not evidence_bearing_scene(config) or (
                report_passes("results_validation_check.md")
                and report_passes("scientific_evidence_check.md")
            ))
        ),
        "visual_ready": report_passes("visual_readiness_check.md"),
        "citation_verified": report_passes("citation_bank_check.md") and report_passes("citation_quality_audit.md"),
        "metadata_ready": report_passes("metadata_readiness_check.md"),
        "artifact_portable": (
            (output_dir / "final_paper" / "paper.pdf").is_file()
            and report_passes("latex_report.md")
            and report_passes("publication_surface_check.md")
            and not result.misplaced_artifacts
        ),
    }

    # Recalculate first pending and completion after content checks
    first_pending = _recalc_first_pending(result.stages)

    if first_pending is None:
        result.next_stage = "complete"
        result.is_complete = True
        if result.misplaced_artifacts:
            result.next_action = (
                "Misplaced artifacts detected in the wrong directory; rebuild or move them into "
                "paper_rewriting_output before declaring completion."
            )
            result.is_complete = False
        elif all(result.readiness.values()):
            result.next_action = "All stages are complete. The paper is ready."
            result.findings.append("All stages complete - workflow finished.")
        else:
            result.next_stage = "final_audit"
            result.is_complete = False
            failed_dimensions = ", ".join(name for name, ready in result.readiness.items() if not ready)
            result.next_action = f"Final readiness dimensions are not complete: {failed_dimensions}. Re-run the owning gates."
    else:
        result.next_stage = first_pending.key
        result.is_complete = False
        result.next_action = _next_action_for_stage(first_pending, config, result.misplaced_artifacts)

    for stage in result.stages:
        if stage.status == "BLOCKED":
            result.findings.append(f"BLOCKED: {stage.label} - missing {stage.missing_artifacts}")
        elif stage.status == "PENDING" and stage.missing_artifacts:
            result.findings.append(f"PENDING: {stage.label} - missing {', '.join(stage.missing_artifacts)}")
    return result


def _status_icon(status: str) -> str:
    return {
        "DONE": "[DONE]",
        "PENDING": "[PENDING]",
        "BLOCKED": "[BLOCKED]",
        "OPTIONAL": "[OPTIONAL]",
        "SKIPPED": "[SKIPPED]",
    }.get(status, status)


def to_markdown(result: ProgressResult) -> str:
    next_label = "Complete" if result.is_complete else f"**{result.next_stage}**"
    lines = [
        "# PaperSpine Progress",
        "",
        f"- Output directory: `{result.output_dir}`",
        f"- Next stage: {next_label}",
        f"- Action: {result.next_action}",
        "",
        "## Stage Status",
        "",
        "| Stage | Status | Missing |",
        "|---|---|---|",
    ]
    for stage in result.stages:
        missing = ", ".join(stage.missing_artifacts) if stage.missing_artifacts else "-"
        lines.append(f"| {stage.label} | {_status_icon(stage.status)} | {missing} |")
    lines.append("")

    if result.interaction:
        interaction = result.interaction
        lines.extend(
            [
                "## Interaction Authority",
                "",
                f"- Mode: {interaction.get('mode') or 'unknown'}",
                f"- Requested scope: {interaction.get('requested_scope') or 'unknown'}",
                f"- Grant status: {interaction.get('grant_status') or 'unknown'}",
                f"- Grant ID: {interaction.get('grant_id') or '-'}",
                f"- Grant SHA-256: {interaction.get('grant_sha256') or '-'}",
                "- Decision classes: "
                + (", ".join(interaction.get("decision_classes", [])) or "-"),
                "- Decision receipts: "
                + (", ".join(interaction.get("decision_receipts", [])) or "-"),
                "- External action authorized: false",
                "",
            ]
        )

    if result.figure_quality:
        figure_quality = result.figure_quality
        lines.extend(
            [
                "## Figure Quality Evidence",
                "",
                f"- Status: {figure_quality.get('status') or 'unknown'}",
                "- Correction receipts: "
                + (
                    ", ".join(figure_quality.get("correction_receipts", []))
                    or "-"
                ),
                "- Target-size legibility receipts: "
                + (
                    ", ".join(
                        figure_quality.get(
                            "target_size_legibility_receipts", []
                        )
                    )
                    or "-"
                ),
                "- External action authorized: false",
                "",
            ]
        )

    if result.misplaced_artifacts:
        lines.extend(["## Misplaced Artifacts", ""])
        lines.extend(f"- `{rel}`" for rel in result.misplaced_artifacts)
        lines.append("")

    if result.readiness:
        lines.extend(["## Submission Readiness", "", "| Dimension | Ready |", "|---|---|"])
        for name, ready in result.readiness.items():
            lines.append(f"| {name} | {'PASS' if ready else 'BLOCKED'} |")
        lines.append("")

    if result.findings:
        lines.extend(["## Findings", ""])
        lines.extend(f"- {finding}" for finding in result.findings)
        lines.append("")
    return "\n".join(lines)


def to_json_dict(result: ProgressResult) -> dict:
    return {
        "output_dir": result.output_dir,
        "next_stage": result.next_stage,
        "next_action": result.next_action,
        "is_complete": result.is_complete,
        "misplaced_artifacts": result.misplaced_artifacts,
        "readiness": result.readiness,
        "interaction": result.interaction,
        "figure_quality": result.figure_quality,
        "stages": [
            {
                "key": stage.key,
                "label": stage.label,
                "status": stage.status,
                "missing": stage.missing_artifacts,
            }
            for stage in result.stages
        ],
        "findings": result.findings,
    }


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)

    if args.gate:
        passed, message, missing = gate_check(out_dir, args.gate, args.require)
        print(message)
        for item in missing:
            print(f"  - {item}")
        return 0 if passed else 1

    result = check_progress(out_dir)

    if args.json:
        print(json.dumps(to_json_dict(result), ensure_ascii=False, indent=2))
    elif args.markdown or not args.json:
        print(to_markdown(result))

    if args.write:
        report_path = out_dir / "progress.md"
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(to_markdown(result), encoding="utf-8")
        print(f"Wrote {report_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
