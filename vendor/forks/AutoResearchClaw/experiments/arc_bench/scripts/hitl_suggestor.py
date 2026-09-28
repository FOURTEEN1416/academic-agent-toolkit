#!/usr/bin/env python3
"""Generate scripted HITL interventions from rc_full runs.

For each topic with an rc_full result under ``results/rc_full/<Txx>/<run>/``:
  1. Load the submission (README, claims.json, metrics.json).
  2. Load the local judge_result (which leaves scored 0 / 0.5).
  3. Load the stage-14 analysis from the archived full_run.
  4. Make ONE LLM call: "You are a senior ML advisor. The full-auto run
     produced X. The rubric leaves (A, B, C) scored low. Write a JSON
     interventions file keyed by pipeline stage id (5, 8, 9, 14) that
     would plausibly fix those gaps on a co-pilot re-run."
  5. Write ``interventions/<Txx>.json`` matching the HITL ablation format.

This is the *model-evolve* step. Copilot gains measured against these
auto-generated suggestions show whether autoclaw can iterate on its own
failures, not whether hand-tuned expert advice helps.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent.parent
RESULTS_DIR = ROOT / "results"
LOG_DIR = ROOT / "log"
INTERVENTIONS_DIR = ROOT / "interventions"

sys.path.insert(0, str(REPO_ROOT))
from researchclaw.llm.client import LLMClient, LLMConfig  # noqa: E402

PROMPT_TEMPLATE = """You are a senior ML research advisor writing scripted
co-pilot interventions for a second autoclaw run on the ARC-Bench topic below.
The first run was full-auto; a local rubric scored it and flagged specific
weak leaves. Your job: produce a JSON interventions file whose guidance,
applied at specific pipeline stages, would plausibly fix the flagged gaps.

Do not invent experimental results. Only prescribe actions: literature to
seek, hypotheses to refine, metrics to add, ablation checks to enforce,
analysis to demand, limitations to acknowledge. Guidance must be concrete
and actionable within a CPU-only sklearn/numpy experiment.

IMPORTANT — only TWO stage IDs are valid for ARC-Bench co-pilot pauses
(the bench runs stages 10..14 and the co-pilot harness only pauses AFTER
stages 10 and 13). Output exactly these two keys:

  10 — CODE_GENERATION (post-stage). Guidance applied here is read by
       stages 11 (resource_planning), 12 (experiment_run), 13
       (iterative_refine), and 14 (result_analysis). Use this slot for:
         * code-quality directives (variant wiring fingerprints, ablation
           integrity assertions, condition hashing)
         * dataset / seeding requirements (>=5 seeds, paired splits)
         * required metrics + statistical-test scaffolding
         * ablation-check assertions to fail-fast on zero-variance results
  13 — ITERATIVE_REFINE (post-stage). Guidance here is read by stage 14
       (result_analysis). Use this slot for:
         * post-experiment analysis checklist (calibration, reliability
           diagrams, paired tests, multiplicity correction)
         * ceiling / zero-variance diagnostics
         * narrative re-framing (e.g. shift from accuracy → calibration
           when accuracy is saturated)
         * limitations the writeup must acknowledge

Do NOT emit keys other than "10" and "13". Each guidance must be 200-700
words, concrete, and tied to the specific weak leaves in the judge result.

Output format (strict JSON, no prose outside):
{{
  "topic_id": "<TXX>",
  "topic": "<verbatim topic string>",
  "expert_profile": "<one-phrase advisor identity, e.g. 'ML calibration specialist'>",
  "interventions": {{
    "<stage_id>": {{
      "action": "inject",
      "message": "<1-2 sentence high-level directive>",
      "guidance": "<multi-bullet concrete actions, newline-separated>"
    }},
    ...
  }}
}}

--- TOPIC MANIFEST ---
{manifest_yaml}

--- RC_FULL LOCAL JUDGE RESULT ---
{judge_json}

--- SUBMISSION README ---
{readme}

--- SUBMISSION CLAIMS ---
{claims_json}

--- METRICS ---
{metrics_json}

--- STAGE-14 ANALYSIS (if available) ---
{stage14_analysis}
"""


def _read(path: Path, cap: int = 8000) -> str:
    if not path.is_file():
        return "(not available)"
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return "(read error)"
    if len(text) > cap:
        return text[:cap] + "\n...[truncated]"
    return text


def _latest_run(mode: str, topic_id: str) -> Path | None:
    base = RESULTS_DIR / mode / topic_id
    if not base.is_dir():
        return None
    runs = sorted(base.iterdir())
    return runs[-1] if runs else None


def _extract_json(blob: str) -> dict[str, Any]:
    text = blob.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        if start < 0:
            raise ValueError(f"no JSON object in LLM output: {blob[:300]}")
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    text = text[start:i + 1]
                    break
    return json.loads(text)


def call_llm(prompt: str) -> dict[str, Any]:
    cfg = LLMConfig(
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        primary_model=os.environ.get("OPENAI_MODEL", "gpt-5.3-codex"),
        fallback_models=[os.environ.get("OPENAI_SMALL_FAST_MODEL", "gpt-4o")],
        wire_api=os.environ.get("OPENAI_WIRE_API", "responses"),
        max_tokens=6000,
        timeout_sec=300,
    )
    client = LLMClient(cfg)
    resp = client.chat(
        messages=[{"role": "user", "content": prompt}],
        json_mode=True,
        max_tokens=6000,
    )
    return _extract_json(resp.content)


def suggest_one(topic_id: str, *, dry_run: bool = False) -> Path | None:
    run = _latest_run("rc_full", topic_id)
    if run is None:
        print(f"  [{topic_id}] no rc_full run found — skipping")
        return None
    manifest_path = ROOT / "manifests" / f"{topic_id}.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest_yaml = yaml.dump(manifest, sort_keys=False, allow_unicode=True)[:4000]
    submission = run / "submission"
    judge_path = run / "judge_result.json"
    archive = LOG_DIR / "rc_full" / topic_id
    stage14 = ""
    if archive.is_dir():
        latest_archive = sorted(archive.iterdir())[-1] if any(archive.iterdir()) else None
        if latest_archive is not None:
            stage14 = _read(latest_archive / "full_run" / "stage-14" / "analysis.md")

    prompt = PROMPT_TEMPLATE.format(
        manifest_yaml=manifest_yaml,
        judge_json=_read(judge_path, cap=4000),
        readme=_read(submission / "README.md", cap=6000),
        claims_json=_read(submission / "claims.json", cap=4000),
        metrics_json=_read(submission / "results" / "metrics.json", cap=4000),
        stage14_analysis=stage14,
    )
    print(f"  [{topic_id}] prompting LLM (≈{len(prompt)} chars)")

    if dry_run:
        print(f"  [{topic_id}] (dry-run; no LLM call)")
        return None

    interventions = call_llm(prompt)

    # Validate stage keys: only 10 and 13 are useful in ARC-Bench co-pilot.
    raw = interventions.get("interventions", {}) or {}
    filtered: dict[str, Any] = {}
    dropped: list[str] = []
    for k, v in raw.items():
        if str(k) in {"10", "13"}:
            filtered[str(k)] = v
        else:
            dropped.append(str(k))
    interventions["interventions"] = filtered
    if dropped:
        print(f"  [{topic_id}] dropped non-{{10,13}} keys: {dropped}")
    if set(filtered.keys()) != {"10", "13"}:
        print(
            f"  [{topic_id}] WARNING: expected both stages 10 and 13, "
            f"got {sorted(filtered.keys())}"
        )

    INTERVENTIONS_DIR.mkdir(exist_ok=True)
    out_path = INTERVENTIONS_DIR / f"{topic_id}.json"
    out_path.write_text(
        json.dumps(interventions, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    n = len(interventions.get("interventions", {}))
    print(f"  [{topic_id}] wrote {out_path} ({n} intervention stages)")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Derive HITL suggestions from rc_full runs")
    ap.add_argument("--topic", help="single topic, e.g. T01")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.all:
        topic_ids = sorted(p.stem for p in (ROOT / "manifests").glob("T*.yaml"))
    elif args.topic:
        topic_ids = [args.topic]
    else:
        ap.error("--topic or --all required")

    for tid in topic_ids:
        suggest_one(tid, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
