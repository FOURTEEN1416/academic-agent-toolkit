#!/usr/bin/env python3
"""Scan paper_rewriting_output/ and report the first incomplete stage.

Self-contained, standard library only. It does not modify files except when
--write is used to produce progress.md.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


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
    "motivation_confirmation": None,
    "planning": "rewrite",
    "build_from_materials": "build",
    "rewrite_existing": "rewrite",
    "drafting": "rewrite",
    "integrity_audit": "audit",
    "latex": "latex",
    "word": "latex",
    "translation": "translate",
    "submission": "submission",
    "final_audit": "audit",
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
        "motivation_options_after_research.md",
    ]),
    StageDef("citation", "Citation Support Bank", [
        "citation_support_bank.md",
    ]),
    StageDef("motivation_confirmation", "Motivation Confirmation", [
        "confirmed_motivation.md",
    ]),
    StageDef("planning", "Planning / Rationale Matrix", [
        "section_blueprints.md",
        "writing_rationale_matrix.md",
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
    StageDef("integrity_audit", "Integrity Audit", [
        "artifact_check.md",
        "integrity_audit.md",
    ]),
    StageDef("latex", "LaTeX / PDF", [
        "latex_report.md",
        "final_artifact_manifest.md",
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
    ]),
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
        choices=[s.key for s in STAGES],
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
    rc, _stdout, _stderr = _run_script(
        scripts_dir, "citation_bank_check.py",
        [citation_path, "--target-count", str(target_count), "--markdown", "--write"],
    )
    if rc != 0:
        failures.append(f"citation_bank_check.py exit {rc}")

    # 3. integrity_audit.py
    rc, _stdout, _stderr = _run_script(
        scripts_dir, "integrity_audit.py", [str(output_dir), "--markdown", "--write"]
    )
    if rc != 0:
        failures.append(f"integrity_audit.py exit {rc}")

    # 4. citation_quality_audit.py
    rc, _stdout, _stderr = _run_script(
        scripts_dir, "citation_quality_audit.py", [str(output_dir), "--write"]
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
            [str(tex_path), "--max-sections", str(max_sections), "--markdown"],
        )
        if rc != 0:
            failures.append(f"section_economy_check.py exit {rc}")

    # 7. Contribution-first / reviewer-aware methodology gates (V4).
    for script in ("contribution_check.py", "reviewer_audit_check.py"):
        rc, _stdout, _stderr = _run_script(scripts_dir, script, [str(output_dir), "--markdown", "--write"])
        if rc != 0:
            failures.append(f"{script} exit {rc}")
    # Results-as-Validation applies only to evidence-bearing scenes.
    if str(config.get("scene") or "").lower() in ("journal", "conference", "competition"):
        rc, _stdout, _stderr = _run_script(
            scripts_dir, "results_validation_check.py", [str(output_dir), "--markdown", "--write"]
        )
        if rc != 0:
            failures.append(f"results_validation_check.py exit {rc}")

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


def required_artifacts_for_stage(stage: StageDef, config: dict, require: bool = False) -> list[str]:
    required = list(stage.required)
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
    return "Stage not applicable."


def gate_check(output_dir: Path, stage_key: str, require: bool = False) -> tuple[bool, str, list[str]]:
    config = _read_config(output_dir)
    stage_def = next((s for s in STAGES if s.key == stage_key), None)
    if stage_def is None:
        return False, f"Unknown stage: {stage_key}", []
    if not stage_applies(stage_def, output_dir, config, require=require):
        return True, stage_skip_message(stage_def), []

    if stage_key == "final_audit":
        return _run_final_audit_gate(output_dir, config)

    required = required_artifacts_for_stage(stage_def, config, require=require)
    missing = [art for art in required if not _artifact_exists(output_dir, art)]
    if missing:
        return False, (
            f"GATE FAILED: {stage_def.label} - missing: {', '.join(missing)}. "
            "Return to this stage and produce the missing artifacts before continuing."
        ), missing

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

    if stage_key == "citation" and _report_contains_fail_blocked(output_dir, "citation_bank_check.md"):
        return False, (
            f"GATE FAILED: {stage_def.label} - citation_bank_check.md reports FAIL/BLOCKED. "
            "Re-run citation bank before continuing."
        ), ["citation_bank_check.md: FAIL/BLOCKED"]

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
    if stage.key == "motivation_confirmation":
        playbook = "research"
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
            required_artifacts=required_artifacts_for_stage(stage_def, config),
        )

        if not stage_applies(stage_def, output_dir, config):
            stage.status = "SKIPPED" if stage_def.workflow else "OPTIONAL"
            result.stages.append(stage)
            continue

        missing = [art for art in stage.required_artifacts if not _artifact_exists(output_dir, art)]
        stage.missing_artifacts = missing
        if not missing:
            stage.status = "DONE"
        elif stage_def.key == "motivation_confirmation" and _artifact_exists(output_dir, "motivation_options_after_research.md"):
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
        else:
            result.next_action = "All stages are complete. The paper is ready."
            result.findings.append("All stages complete - workflow finished.")
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

    if result.misplaced_artifacts:
        lines.extend(["## Misplaced Artifacts", ""])
        lines.extend(f"- `{rel}`" for rel in result.misplaced_artifacts)
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
