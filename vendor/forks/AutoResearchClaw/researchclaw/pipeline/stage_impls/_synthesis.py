"""Stages 7-8: Synthesis and hypothesis generation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from researchclaw.adapters import AdapterBundle
from researchclaw.config import RCConfig
from researchclaw.llm import build_panel_llms, build_reviewer_llm
from researchclaw.llm.client import LLMClient
from researchclaw.pipeline.debate import run_debate
from researchclaw.pipeline._helpers import (
    StageResult,
    _default_hypotheses,
    _get_evolution_overlay,
    _multi_perspective_generate,
    _parse_jsonl_rows,
    _read_prior_artifact,
    _synthesize_perspectives,
    _utcnow_iso,
)
from researchclaw.pipeline.stages import Stage, StageStatus
from researchclaw.prompts import PromptManager, _render

logger = logging.getLogger(__name__)


def _execute_synthesis(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    cards_path = _read_prior_artifact(run_dir, "cards/") or ""
    cards_context = ""
    if cards_path:
        snippets: list[str] = []
        for path in sorted(Path(cards_path).glob("*.md"))[:24]:
            snippets.append(path.read_text(encoding="utf-8"))
        cards_context = "\n\n".join(snippets)

    if llm is not None:
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "synthesis")
        sp = _pm.for_stage(
            "synthesis",
            evolution_overlay=_overlay,
            topic=config.research.topic,
            cards_context=cards_context,
            domain_context="",
        )
        resp = llm.chat(
            [{"role": "user", "content": sp.user}],
            system=sp.system,
            max_tokens=sp.max_tokens or 8192,
        )
        synthesis_md = resp.content
    else:
        synthesis_md = f"""# Synthesis

## Cluster Overview
- Cluster A: Representation methods
- Cluster B: Training strategies
- Cluster C: Evaluation robustness

## Gap 1
Limited consistency across benchmark protocols.

## Gap 2
Under-reported failure behavior under distribution shift.

## Prioritized Opportunities
1. Unified experimental protocol
2. Robustness-aware evaluation suite

## Generated
{_utcnow_iso()}
"""
    (stage_dir / "synthesis.md").write_text(synthesis_md, encoding="utf-8")
    return StageResult(
        stage=Stage.SYNTHESIS,
        status=StageStatus.DONE,
        artifacts=("synthesis.md",),
        evidence_refs=("stage-07/synthesis.md",),
    )


def _execute_hypothesis_gen(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    synthesis = _read_prior_artifact(run_dir, "synthesis.md") or ""

    if llm is not None:
        _pm = prompts or PromptManager()
        # Debate roles come from the PromptManager's active bank
        # (ML bank -> innovator/pragmatist/contrarian,
        #  HEP bank -> theorist/phenomenologist/experimentalist).
        _active_roles = _pm.debate_roles_hypothesis()

        perspectives_dir = stage_dir / "perspectives"
        variables = {"topic": config.research.topic, "synthesis": synthesis}
        if config.llm.tournament_enabled and config.llm.tournament_candidates >= 2:
            # --- Best-of-N tournament: generate N candidate hypothesis sets
            # from diverse stances, then an independent judge picks the winner.
            from researchclaw.pipeline.tournament import (
                effective_candidates,
                run_tournament,
            )

            _gens = build_panel_llms(config) or [llm]
            _judge = build_reviewer_llm(config) or llm
            _roles = list(_active_roles.values()) or [
                {
                    "system": "You are a research scientist.",
                    "user": (
                        "Propose 2-4 falsifiable hypotheses for:\n{topic}"
                        "\n\n{synthesis}"
                    ),
                }
            ]
            _n = effective_candidates(config.llm.tournament_candidates)
            _cps = [
                (
                    _render(_roles[i % len(_roles)]["system"], variables),
                    _render(_roles[i % len(_roles)]["user"], variables),
                )
                for i in range(_n)
            ]
            hypotheses_md, _ = run_tournament(
                _gens,
                _judge,
                _cps,
                rank_prompt="tournament_rank",
                out_dir=stage_dir / "tournament",
                prompts=_pm,
                author_model=getattr(llm.config, "primary_model", ""),
                label="hypset",
            )
        else:
            _panel = build_panel_llms(config)
            if _panel:
                # --- Multi-model debate: distinct models argue per role,
                # rebuttal round(s), then an independent judge ranks and the
                # stronger model synthesizes the final text. ---
                _judge = build_reviewer_llm(config) or llm
                try:
                    hypotheses_md, _ = run_debate(
                        _panel,
                        _judge,
                        _active_roles,
                        variables,
                        rounds=config.llm.debate_rounds,
                        synth_prompt="hypothesis_synthesize",
                        out_dir=perspectives_dir,
                        prompts=_pm,
                        author_model=getattr(llm.config, "primary_model", ""),
                        synthesizer=llm,
                    )
                except Exception:  # noqa: BLE001 — never block on debate
                    logger.warning(
                        "Multi-model debate failed; using default hypotheses",
                        exc_info=True,
                    )
                    hypotheses_md = _default_hypotheses(config.research.topic)
            else:
                # --- Legacy multi-perspective (single model, no judge) ---
                perspectives = _multi_perspective_generate(
                    llm, _active_roles, variables, perspectives_dir
                )
                # BUG-S2: If all debate perspectives failed, fall back to defaults
                # instead of sending empty context to the LLM (pure hallucination).
                if not perspectives:
                    logger.warning(
                        "All debate perspectives failed; using default hypotheses"
                    )
                    hypotheses_md = _default_hypotheses(config.research.topic)
                else:
                    # --- Synthesize into final hypotheses ---
                    hypotheses_md = _synthesize_perspectives(
                        llm, perspectives, "hypothesis_synthesize", _pm
                    )
    else:
        hypotheses_md = _default_hypotheses(config.research.topic)
    # --- HITL: Read human guidance if available ---
    guidance_file = stage_dir / "hitl_guidance.md"
    if guidance_file.exists():
        try:
            guidance = guidance_file.read_text(encoding="utf-8").strip()
            if guidance and llm is not None:
                logger.info("Applying HITL guidance to hypotheses")
                resp = llm.chat(
                    [{"role": "user", "content": (
                        f"Refine the following hypotheses based on this human guidance.\n\n"
                        f"## Current Hypotheses\n{hypotheses_md}\n\n"
                        f"## Human Guidance\n{guidance}\n\n"
                        f"Produce improved hypotheses that incorporate the guidance."
                    )}],
                    max_tokens=4096,
                )
                hypotheses_md = resp.content
        except Exception:
            logger.debug("HITL guidance application failed (non-blocking)")

    # --- HITL: Idea Workshop data persistence ---
    try:
        from researchclaw.hitl.workshops.idea import IdeaWorkshop

        workshop = IdeaWorkshop(run_dir, llm_client=llm)
        workshop.candidates = [
            type("IC", (), {"title": "Generated Hypothesis", "description": hypotheses_md[:500],
                            "to_dict": lambda self: {"title": self.title, "description": self.description},
                            "human_approved": False, "baselines": [], "keywords": [],
                            "novelty_notes": "", "feasibility_notes": "", "impact_notes": "",
                            "score": 0.0})()
        ]
        workshop.save()
    except Exception:
        pass

    (stage_dir / "hypotheses.md").write_text(hypotheses_md, encoding="utf-8")

    # --- Novelty check (non-blocking) ---
    novelty_artifacts: tuple[str, ...] = ()
    try:
        from researchclaw.literature.novelty import check_novelty  # noqa: PLC0415

        candidates_text = _read_prior_artifact(run_dir, "candidates.jsonl") or ""
        papers_seen = _parse_jsonl_rows(candidates_text) if candidates_text else []
        novelty_report = check_novelty(
            topic=config.research.topic,
            hypotheses_text=hypotheses_md,
            papers_already_seen=papers_seen,
            s2_api_key=getattr(config.llm, "s2_api_key", ""),
        )
        (stage_dir / "novelty_report.json").write_text(
            json.dumps(novelty_report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        novelty_artifacts = ("novelty_report.json",)
        logger.info(
            "Novelty check: score=%.3f  assessment=%s  recommendation=%s",
            novelty_report["novelty_score"],
            novelty_report["assessment"],
            novelty_report["recommendation"],
        )
    except Exception:  # noqa: BLE001
        logger.warning("Novelty check failed (non-blocking)", exc_info=True)

    return StageResult(
        stage=Stage.HYPOTHESIS_GEN,
        status=StageStatus.DONE,
        artifacts=("hypotheses.md",) + novelty_artifacts,
        evidence_refs=("stage-08/hypotheses.md",),
    )
