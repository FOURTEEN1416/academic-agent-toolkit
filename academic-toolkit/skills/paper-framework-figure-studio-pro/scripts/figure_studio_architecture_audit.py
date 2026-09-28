#!/usr/bin/env python3
"""Lightweight architecture audit for paper-framework-figure-studio-pro v3.2.15f."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "3.2.15f"

REQUIRED_FILES = [
    "SKILL.md",
    "VERSION",
    "metadata.json",
    "references/contribution-type-visual-priority-policy-v3215e.md",
    "references/s2-s5-image-only-terminal-orchestration-policy-v3215.md",
    "references/candidate-artifact-id-coherence-policy-v3215.md",
    "references/strict-source-grounded-modular-prompt-contract-policy-v3215a.md",
    "references/layout-density-mainline-balance-policy-v3215f.md",
    "references/style-combination-selection-and-human-palette-policy-v3215d.md",
    "references/preferred-first-round-carryover-policy-v3215b.md",
    "references/restore-repair-or-redo-policy-v3215b.md",
    "references/s0-semantic-precision-and-role-variation-lock-policy-v3215f.md",
    "scripts/figure_studio_s0_precision_guard.py",
    "scripts/figure_studio_layout_density_guard.py",
    "scripts/figure_studio_core/constants.py",
    "scripts/figure_studio_core/identity.py",
]

ACTIVE_TEXT_FILES = [
    "SKILL.md",
    "metadata.json",
    "templates/project-state-template.json",
    "templates/prompt-template.md",
    "templates/figure-brief-template.md",
]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8-sig")


def main() -> int:
    findings: list[dict[str, str]] = []
    version = (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()
    if version != EXPECTED_VERSION:
        findings.append({"level": "ERROR", "message": f"VERSION is {version}, expected {EXPECTED_VERSION}"})

    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            findings.append({"level": "ERROR", "message": f"missing required file: {rel}"})

    skill = read("SKILL.md")
    required_skill_phrases = [
        "v3.2.15f",
        "style-combination-selection-and-human-palette-policy-v3215d.md",
        "no-false-relay-data-flow-policy-v3215d.md",
        "public-stage-human-wait-barrier-policy-v3215d.md",
        "C01-C04",
        "F01-F02",
        "palette_anti_ai_artifact_rules",
        "human_aesthetic_rationale",
        "up to five cycles",
        "contribution-type visual priority",
        "data_flow_overdominance",
        "false_relay_data_flow_audit",
        "layout-density-mainline-balance-policy-v3215f.md",
        "layout_information_density_plan",
        "canvas_area_budget",
        "context_inset_budget",
        "mainline_center_of_gravity_gate",
        "hard runtime human wait barrier",
        "never exceed two second-round S5 schemes",
        "prompt-index `candidate_id` is the source of truth",
        "s0-semantic-precision-contract.json",
        "forbidden_misimplementation_locks",
        "Do not turn a shared-role marker contract into duplicated full workflows",
    ]
    for phrase in required_skill_phrases:
        if phrase not in skill:
            findings.append({"level": "ERROR", "message": f"SKILL.md missing required v3.2.15f phrase: {phrase}"})

    forbidden_active_terms = [
        "C01-" + "C" + "08",
        "F01-" + "F" + "06",
        "F" + "07" + "/" + "F" + "08",
        "default " + "six",
        "eight-" + "scheme cap",
        "max-" + "eight",
        "3.2.15" + "c workflow",
    ]
    for rel in ACTIVE_TEXT_FILES:
        path = ROOT / rel
        if not path.exists():
            findings.append({"level": "ERROR", "message": f"missing active text file: {rel}"})
            continue
        text = read(rel)
        for term in forbidden_active_terms:
            if term in text:
                findings.append({"level": "ERROR", "message": f"{rel} contains obsolete term: {term}"})
        if "paper-framework-figure-studio-pro-v3" in text or "skill.zip" in text:
            findings.append({"level": "ERROR", "message": f"{rel} contains user-facing archive-specific skill wording"})

    meta = json.loads(read("metadata.json"))
    if meta.get("version") != EXPECTED_VERSION:
        findings.append({"level": "ERROR", "message": f"metadata version must be {EXPECTED_VERSION}"})
    if meta.get("terminal_step") != "S5-CANDIDATE-IMAGE":
        findings.append({"level": "ERROR", "message": "metadata terminal_step must be S5-CANDIDATE-IMAGE"})
    counts = meta.get("candidate_count_policy", {})
    if counts.get("s1_selected_s2_candidate_count") != 4 or counts.get("s5_image_count") != 2:
        findings.append({"level": "ERROR", "message": "metadata candidate_count_policy must enforce S2=4 and S5=2"})
    s0_precision = meta.get("s0_semantic_precision_policy", {})
    if s0_precision.get("policy_id") != "s0-semantic-precision-and-role-variation-lock-v3215f":
        findings.append({"level": "ERROR", "message": "metadata must expose s0_semantic_precision_policy v3.2.15f"})

    layout_density = meta.get("layout_density_policy", {})
    if layout_density.get("policy_id") != "layout-density-mainline-balance-v3215f":
        findings.append({"level": "ERROR", "message": "metadata must expose layout_density_policy v3.2.15f"})
    required_layout = {
        "layout_information_density_plan",
        "canvas_area_budget",
        "context_inset_budget",
        "mainline_center_of_gravity_gate",
        "layout_density_audit",
    }
    if not required_layout.issubset(set(layout_density.get("required_records", []))):
        findings.append({"level": "ERROR", "message": "metadata layout_density_policy missing required prompt records"})
    prompt_required = set(meta.get("prompt_audit_policy", {}).get("required_records", []))
    if not required_layout.issubset(prompt_required):
        findings.append({"level": "ERROR", "message": "metadata prompt_audit_policy missing layout-density required records"})

    required_s0 = {
        "ambiguous_directive_normalization",
        "actor_or_condition_variation_matrix",
        "role_visual_realization_contract",
        "process_instance_budget",
        "forbidden_misimplementation_locks",
        "downstream_s1_s4_carry_forward",
    }
    if not required_s0.issubset(set(s0_precision.get("required_report_fields", []))):
        findings.append({"level": "ERROR", "message": "metadata s0_semantic_precision_policy missing required report fields"})

    print(json.dumps({"version": version, "finding_count": len(findings), "findings": findings}, indent=2, ensure_ascii=False))
    return 1 if any(f["level"] == "ERROR" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
