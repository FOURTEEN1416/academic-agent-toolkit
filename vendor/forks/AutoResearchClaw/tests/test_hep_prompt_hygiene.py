"""Phase-B hygiene tests for the HEP prompt bank.

Covers:

* **ML-leakage scanner** — every rendered HEP stage prompt must be free of
  the ML-venue vocabulary that motivated the refactor (broader impact,
  reproducibility checklist, seed variance, accuracy, …).
* **Parity contract** — ML and HEP banks expose the same stage keys,
  placeholders, JSON-mode flags and ``max_tokens`` budgets so call sites
  remain interchangeable.
* **Adapter surface** — the adapter layer has shed the HEP-only overlay
  methods and the HEP adapter returns empty blocks for the three
  YAML-driven hooks.
"""

from __future__ import annotations

import re

import pytest

from researchclaw.domains.detector import DomainProfile
from researchclaw.domains.adapters.hep_ph import HEPPhPromptAdapter
from researchclaw.domains.prompt_adapter import PromptAdapter, PromptBlocks
from researchclaw.prompts import PromptManager


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


# Per-stage placeholder bindings. Any placeholder referenced by a stage
# template that is NOT listed here falls back to an empty string so the
# scanner still sees the bare template text.
_STAGE_VARS = {
    "topic": "dark matter simplified model with scalar mediator",
    "domains": "hep-ph",
    "cards_context": "Previous work on Z' mediators...",
    "synthesis": "Synthesis placeholder body.",
    "hypotheses": "H1: scalar mediator excluded above 2 TeV.",
    "preamble": "Preamble text.",
    "dataset_guidance": "",
    "domain_context": "",
    "domain_design_context": "",
    "evidence": "",
    "constraints": "",
    "analysis": "Analysis body.",
    "decision": "Decide to proceed.",
    "outline": "Outline scaffold.",
    "draft": "Draft body.",
    "reviews": "Reviews body.",
    "feedback": "",
    "experiment_evidence": "Evidence body.",
    "context": "Context placeholder.",
    "plan": "Plan placeholder.",
    "report": "Report placeholder.",
    "refinement_summary": "Refinement summary body.",
    "section_label": "Model",
    "section_target": "800 words",
    "section_target_words": "800",
    "writing_structure": "",
    "academic_style_guide": "",
    "narrative_writing_rules": "",
    "anti_hedging_rules": "",
    "anti_repetition_rules": "",
    "topic_constraint": "Topic constraint block.",
    "venue_guidance": "",
    "hypothesis_feasibility": "",
    "time_budget_sec": "7200",
    "metric_key": "exclusion_95cl",
    "metric_direction": "maximize",
    "hardware_profile": "CPU only",
    "per_condition_budget_sec": "600",
    "available_tier1_datasets": "CIFAR-10 (ML only)",
    "results": "Result placeholder.",
    "exp_metrics_instruction": "",
    "citation_instruction": "",
    "extra_guidance": "",
    "compute_budget": "",
    "hp_reporting": "",
    "code_generation_hints": "",
    "result_analysis_hints": "",
    "experiment_design_context": "",
    "statistical_test_guidance": "",
    "output_format_guidance": "",
    "export_publish_guidance": "",
    "preferred_template": "",
    "venue_label": "JHEP",
    "blueprint": "",
    "metrics_block": "",
    "hint_block": "",
    "section_requirements": "",
    "export_template": "jhep",
    "existing_code": "",
    "failure_log": "",
}


_ML_LEAKAGE_TERMS = (
    r"\baccuracy\b",
    r"\bvalidation\s+loss\b",
    r"\btraining/validation\b",
    r"\bbroader\s+impact\b",
    r"\breproducibility\s+checklist\b",
    r"\bseed\s+variance\b",
    r"\bseed-averaged\b",
    r"\bmodel\s+card\b",
    r"\balgorithm\s+card\b",
    r"\bneurips\b",
    r"\bicml\b",
    r"\biclr\b",
    r"\bsocietal\s+impact\b",
    r"\bablation\s+study\b",
)

_ML_REGEX = re.compile("|".join(_ML_LEAKAGE_TERMS), re.IGNORECASE)


# Terms that mark an ML-vocabulary mention as a *negative* instruction
# ("do NOT include a Broader Impact section"). HEP prompts deliberately
# warn the LLM against ML-venue conventions, so those mentions are OK.
_NEGATION_MARKERS = (
    r"\bnot\b",
    r"\bno\b",
    r"\bavoid(?:s|ed|ing)?\b",
    r"\bdo\s+not\b",
    r"\bdon'?t\b",
    r"\binstead\s+of\b",
    r"\bwithout\b",
    r"\bremov\w*\b",
    r"\bstrip(?:s|ped|ping)?\b",
    r"\bsurviving\b",
    r"\bml[- ]venue\b",
    r"\bml[- ]style\b",
    r"\bml[- ]metric\b",
    r"\bml[- ]artefacts?\b",
    r"\bartefacts?\b",
    r"\bflag(?:s|ged|ging)?\b",
    r"\breplac\w*\b",
    r"\bforbid\w*\b",
    r"\bexcept\b",
    r"\bnever\b",
    r"\binherited\s+from\s+ML\b",
)

_NEG_REGEX = re.compile("|".join(_NEGATION_MARKERS), re.IGNORECASE)


def _is_negated_context(text: str, match: re.Match[str], window: int = 120) -> bool:
    """Return True when the match sits inside a negative instruction."""
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    return bool(_NEG_REGEX.search(text[start:end]))


# ---------------------------------------------------------------------------
# ML-leakage scanner
# ---------------------------------------------------------------------------


def _all_hep_texts() -> list[tuple[str, str]]:
    pm = PromptManager(domain="hep_ph")
    out: list[tuple[str, str]] = []
    for stage in pm.stage_names():
        rendered = pm.for_stage(stage, **_STAGE_VARS)
        out.append((f"{stage}:system", rendered.system))
        out.append((f"{stage}:user", rendered.user))
    for role, block in pm.debate_roles_hypothesis().items():
        out.append((f"hypothesis_role[{role}]:system", block.get("system", "")))
        out.append((f"hypothesis_role[{role}]:user", block.get("user", "")))
    for role, block in pm.debate_roles_analysis().items():
        out.append((f"analysis_role[{role}]:system", block.get("system", "")))
        out.append((f"analysis_role[{role}]:user", block.get("user", "")))
    return out


def test_hep_bank_has_no_ml_leakage() -> None:
    """Flag *positive* ML-vocabulary mentions in the HEP bank.

    Negative instructions ("do NOT include a Broader Impact section") are
    intentional anti-ML guards and are allowed.
    """
    offenders: list[tuple[str, str, str]] = []
    for label, text in _all_hep_texts():
        for match in _ML_REGEX.finditer(text):
            if _is_negated_context(text, match):
                continue
            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 40)
            offenders.append((label, match.group(0), text[start:end]))
    assert not offenders, (
        "HEP prompt bank contains *positive* ML-venue vocabulary:\n"
        + "\n".join(
            f"  - {label}: {hit!r}\n      ...{ctx!r}..."
            for label, hit, ctx in offenders
        )
    )


# ---------------------------------------------------------------------------
# Parity contract: ML vs HEP banks expose the same surface
# ---------------------------------------------------------------------------


def _stage_placeholders(pm: PromptManager, stage: str) -> set[str]:
    raw = pm.system(stage) + "\n" + pm._stages[stage]["user"]
    return set(re.findall(r"\{(\w+)\}", raw))


def test_hep_ml_stage_parity() -> None:
    pm_ml = PromptManager(domain="ml")
    pm_hep = PromptManager(domain="hep_ph")

    assert pm_ml.stage_names() == pm_hep.stage_names()

    for stage in pm_ml.stage_names():
        ml_ph = _stage_placeholders(pm_ml, stage)
        hep_ph = _stage_placeholders(pm_hep, stage)
        assert ml_ph == hep_ph, (
            f"Placeholder mismatch for stage {stage!r}:\n"
            f"  ML  only: {sorted(ml_ph - hep_ph)}\n"
            f"  HEP only: {sorted(hep_ph - ml_ph)}"
        )
        assert pm_ml.json_mode(stage) == pm_hep.json_mode(stage), stage
        assert pm_ml.max_tokens(stage) == pm_hep.max_tokens(stage), stage


def test_debate_role_names_are_domain_specific() -> None:
    pm_ml = PromptManager(domain="ml")
    pm_hep = PromptManager(domain="hep_ph")
    assert set(pm_ml.debate_roles_hypothesis().keys()) == {
        "innovator", "pragmatist", "contrarian",
    }
    assert set(pm_hep.debate_roles_hypothesis().keys()) == {
        "theorist", "phenomenologist", "experimentalist",
    }


# ---------------------------------------------------------------------------
# Adapter-surface invariants
# ---------------------------------------------------------------------------


def test_adapter_base_has_no_overlay_methods() -> None:
    methods = {m for m in dir(PromptAdapter) if m.startswith("get_")}
    assert "get_synthesis_blocks" not in methods
    assert "get_hypothesis_gen_blocks" not in methods
    assert "get_paper_writing_blocks" not in methods
    assert "get_peer_review_blocks" not in methods
    assert "get_paper_revision_blocks" not in methods
    assert "get_debate_roles" not in methods
    # Still-supported hooks:
    for m in (
        "get_code_generation_blocks",
        "get_experiment_design_blocks",
        "get_result_analysis_blocks",
        "get_export_publish_blocks",
        "get_blueprint_context",
        "get_condition_terminology",
    ):
        assert m in methods, m


def test_hep_adapter_is_yaml_only_overlay() -> None:
    hep_profile = DomainProfile(
        domain_id="hep_ph",
        parent_domain="hep_ph",
        display_name="HEP phenomenology",
        experiment_paradigm="simulation",
    )
    adapter = HEPPhPromptAdapter(hep_profile)
    for hook in (
        adapter.get_code_generation_blocks,
        adapter.get_experiment_design_blocks,
        adapter.get_result_analysis_blocks,
    ):
        blocks = hook({"topic": "dm"})
        assert isinstance(blocks, PromptBlocks)
        assert all(v == "" for v in blocks.__dict__.values() if isinstance(v, str))
    export = adapter.get_export_publish_blocks({"topic": "dm"})
    assert export.preferred_template == "jhep"


def test_prompt_blocks_has_shrunk_surface() -> None:
    fields = set(PromptBlocks.__dataclass_fields__.keys())
    forbidden = {
        "synthesis_domain_context",
        "hypothesis_feasibility",
        "paper_venue_guidance",
        "paper_section_structure",
        "paper_abstract_structure",
        "paper_writing_style",
        "peer_review_system",
        "peer_review_rubric",
        "paper_revision_system",
        "paper_revision_rules",
    }
    assert fields.isdisjoint(forbidden), (
        f"PromptBlocks still exposes removed overlay fields: {fields & forbidden}"
    )


# ---------------------------------------------------------------------------
# HEP debate roles vocabulary is present (sanity spot-check)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        "Lagrangian",
        "cross section",
        "95% CL",
        "JHEP",
        "natural units",
    ],
)
def test_hep_bank_vocabulary_present(token: str) -> None:
    pm = PromptManager(domain="hep_ph")
    joined = "\n".join(t for _, t in _all_hep_texts())
    assert token.lower() in joined.lower(), (
        f"Expected HEP vocabulary token {token!r} missing from bank output"
    )
