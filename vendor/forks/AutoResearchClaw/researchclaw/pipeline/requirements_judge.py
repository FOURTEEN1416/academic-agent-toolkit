"""LLM requirements-judge — proceed/reject gate for agent-based experiments.

Agent-based experiment modes (``collider_agent``, ``biology_agent``) run an
end-to-end Claude Code session that produces a canonical ``results.json`` at
the workspace root.  The pipeline then needs to decide whether the run met
the **research requirements** (not just numeric thresholds) before passing
to paper-writing.

This module provides that decision via an LLM:

    judge_requirements(requirements, summary, agent_results, llm)
        → {verdict: "proceed" | "reject" | "partial",
           per_requirement: [{id, met, evidence, missing}, ...],
           delta_feedback: <text suitable for inclusion in a rerun prompt>}

The judge is intentionally separate from the existing
``assess_experiment_quality`` (numeric thresholds, condition counts) because
agent runs may produce many conditions and figures yet still fail the actual
research question — and conversely a sparse run may answer the question
faithfully.

Verdict semantics
-----------------
* ``proceed`` — every ``must_pass`` requirement is met.  Optional
  requirements may be unmet but that does not block paper-writing.
* ``reject`` — at least one ``must_pass`` requirement is unmet.  Caller
  should write a ``REPAIR_PROMPT.md`` and trigger a stage-12 rerun (subject
  to retry budget).
* ``partial`` — every ``must_pass`` requirement is met but some optional
  ones are not.  Caller proceeds to paper-writing with a flag.

Requirement schema (manifest)
-----------------------------
::

    requirements:
      - id: req_wt_growth                       # string identifier
        type: numeric | discussion | artifact   # advisory; LLM ignores type if unsure
        description: "results.json metrics.wt_growth_observed_1_per_h must be within ±15% of 0.736"
        must_pass: true                          # if true, unmet → reject
"""

from __future__ import annotations

import json
import logging
from typing import Any

from researchclaw.llm.client import LLMClient

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "You are a strict research auditor. You read the requirements that a study "
    "MUST satisfy, then audit the post-run experiment summary and the agent's "
    "canonical results.json against each requirement. You quote concrete evidence "
    "and only mark a requirement as met when there is direct, unambiguous support "
    "in the data. You do not invent facts. You are terse and precise."
)


def _build_user_prompt(
    requirements: list[dict[str, Any]],
    experiment_summary: dict[str, Any],
    agent_results: dict[str, Any],
) -> str:
    summary_excerpt = json.dumps(experiment_summary, indent=2, default=str)[:9000]
    results_excerpt = json.dumps(agent_results, indent=2, default=str)[:7000]
    requirements_json = json.dumps(requirements, indent=2)
    return (
        "REQUIREMENTS to verify (JSON list of objects):\n"
        f"{requirements_json}\n\n"
        "EXPERIMENT_SUMMARY (post-run, built by stage-14):\n"
        f"```json\n{summary_excerpt}\n```\n\n"
        "AGENT_RESULTS (results.json written by the agent at workspace root):\n"
        f"```json\n{results_excerpt}\n```\n\n"
        "TASK\n"
        "----\n"
        "For each requirement, decide whether it is MET based ONLY on the data above.\n"
        "Cite the concrete value or text you used as evidence (max 200 chars per cite).\n"
        "When a must_pass requirement is unmet, write what is missing — concrete enough "
        "that an agent could fix it in a follow-up run.\n\n"
        "Then produce a single overall verdict:\n"
        "  * \"proceed\"  — every must_pass requirement is met (any optional may fail)\n"
        "  * \"reject\"   — at least one must_pass requirement is unmet\n"
        "  * \"partial\"  — all must_pass met but ≥1 optional unmet\n\n"
        "Finally produce delta_feedback: a short bulleted list of the must_pass items still "
        "failing, phrased as instructions to the agent for a rerun (e.g. \"Compute X for "
        "condition Y; report it under metrics.X\").  Empty string if nothing is failing.\n\n"
        "OUTPUT — return ONLY a single JSON object, no prose, no fences:\n"
        '{\n'
        '  "per_requirement": [\n'
        '    {"id": "<req-id>", "must_pass": <bool>, "met": <bool>, "evidence": "...", "missing": "..."},\n'
        '    ...\n'
        '  ],\n'
        '  "verdict": "proceed" | "reject" | "partial",\n'
        '  "delta_feedback": "..."\n'
        '}\n'
    )


def _parse_verdict_response(text: str) -> dict[str, Any]:
    """Pull the JSON object out of an LLM response, tolerant of fences."""
    text = text.strip()
    # Strip ```json ... ``` fences if present
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: find first { … last }
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError(f"requirements judge returned non-object: {type(data).__name__}")
    return data


def _normalize_verdict(parsed: dict[str, Any], requirements: list[dict[str, Any]]) -> dict[str, Any]:
    """Coerce a parsed LLM response into the canonical verdict shape and
    sanity-check that it agrees with must_pass flags."""
    per_req_raw = parsed.get("per_requirement") or []
    by_id = {str(r.get("id", f"req_{i}")): r for i, r in enumerate(requirements)}
    per_req: list[dict[str, Any]] = []
    for item in per_req_raw:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("id", ""))
        spec = by_id.get(rid, {})
        per_req.append({
            "id": rid or "(unnamed)",
            "must_pass": bool(item.get("must_pass", spec.get("must_pass", False))),
            "met": bool(item.get("met", False)),
            "evidence": str(item.get("evidence") or "")[:400],
            "missing": str(item.get("missing") or "")[:600],
        })

    # Recompute verdict from per_requirement so the LLM can't hand us an
    # inconsistent envelope (claims proceed while flagging must_pass=met=false).
    must_unmet = [r for r in per_req if r["must_pass"] and not r["met"]]
    optional_unmet = [r for r in per_req if not r["must_pass"] and not r["met"]]
    if must_unmet:
        verdict = "reject"
    elif optional_unmet:
        verdict = "partial"
    else:
        verdict = "proceed"

    delta_feedback = str(parsed.get("delta_feedback") or "").strip()
    if verdict == "reject" and not delta_feedback:
        # Synthesize a fallback bullet list so the rerun prompt isn't empty.
        delta_feedback = "\n".join(
            f"- ({r['id']}) {r['missing'] or 'requirement not met — check the requirement description'}"
            for r in must_unmet
        )

    return {
        "verdict": verdict,
        "per_requirement": per_req,
        "delta_feedback": delta_feedback,
        "raw_verdict": parsed.get("verdict"),  # what the LLM said before normalization
    }


def judge_requirements(
    requirements: list[dict[str, Any]],
    experiment_summary: dict[str, Any],
    agent_results: dict[str, Any],
    llm: LLMClient,
    *,
    max_tokens: int = 2000,
) -> dict[str, Any]:
    """Audit the run against the manifest requirements via LLM.

    Returns the verdict dict (see module docstring).  Never raises on a
    well-formed LLM response; on parser failure, returns a conservative
    "reject"-with-error verdict so the caller can decide what to do.
    """
    if not requirements:
        return {
            "verdict": "proceed",
            "per_requirement": [],
            "delta_feedback": "",
            "raw_verdict": None,
            "skipped": "no requirements declared",
        }

    sys_p = _SYSTEM_PROMPT
    user_p = _build_user_prompt(requirements, experiment_summary, agent_results)

    try:
        resp = llm.chat(
            messages=[{"role": "user", "content": user_p}],
            system=sys_p,
            json_mode=True,
            max_tokens=max_tokens,
        )
        text = resp.content if hasattr(resp, "content") else str(resp)
        parsed = _parse_verdict_response(text)
        verdict = _normalize_verdict(parsed, requirements)
        logger.info(
            "Requirements judge: verdict=%s, %d/%d must_pass met",
            verdict["verdict"],
            sum(1 for r in verdict["per_requirement"] if r["must_pass"] and r["met"]),
            sum(1 for r in verdict["per_requirement"] if r["must_pass"]),
        )
        return verdict
    except Exception as exc:  # noqa: BLE001
        logger.warning("Requirements judge failed: %s — defaulting to reject", exc)
        return {
            "verdict": "reject",
            "per_requirement": [
                {"id": r.get("id", f"req_{i}"), "must_pass": bool(r.get("must_pass")),
                 "met": False, "evidence": "",
                 "missing": "(judge LLM call failed — assume unmet)"}
                for i, r in enumerate(requirements)
            ],
            "delta_feedback": (
                "The requirements judge could not be evaluated. Please re-run the "
                "experiment ensuring results.json contains numeric values for every "
                "metric named in the requirements list, and that hypotheses h1..h3 "
                "each have an explicit supported flag with details."
            ),
            "raw_verdict": None,
            "error": str(exc),
        }
