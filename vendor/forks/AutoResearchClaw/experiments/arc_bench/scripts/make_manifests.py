#!/usr/bin/env python3
"""LLM-backed generator for ARC-Bench topic manifests + rubrics.

Reads ``topics.yaml`` entries and — for each ID not yet materialised under
``manifests/<Txx>.yaml`` — asks the LLM to emit BOTH a P01-style YAML
manifest AND a PaperBench-compatible JSON rubric. The generator uses
``manifests/T01.yaml`` + ``rubrics/T01.json`` as the few-shot exemplar so
downstream scripts (``prepare_run.py``, ``run_bench.py``, ``judge.py``)
can consume the output without format drift.

Design rules enforced by the prompt:
  * CPU-friendly (sklearn / numpy / scipy / statsmodels / networkx only).
  * Wall-clock budget per run ≤ 15 min on one core.
  * Exactly 3 measurable hypotheses (H1/H2/H3).
  * Rubric has one code / one exec / one results group, 7–10 total leaves.
  * Every leaf has ``task_category`` ∈ {Code Development, Code Execution,
    Result Analysis} and a ``finegrained_task_category`` picked from
    PaperBench's taxonomy.

The script is re-runnable — already-present manifests are skipped unless
``--force`` is passed.
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
MANIFEST_DIR = ROOT / "config" / "manifests"
RUBRIC_DIR = ROOT / "config" / "rubrics"

sys.path.insert(0, str(REPO_ROOT))
from researchclaw.llm.client import LLMClient, LLMConfig  # noqa: E402


PROMPT_TEMPLATE = """You are designing an ARC-Bench topic — a CPU-friendly
machine-learning research prompt that an autonomous agent will implement
and evaluate in under 15 minutes on a single core using only
numpy / scipy / sklearn / statsmodels / networkx. The topic will feed a
ResearchClaw pipeline that picks up at stage 10 (code generation).

For the topic below, produce BOTH a YAML manifest AND a JSON rubric. The
formats match the provided exemplars EXACTLY: field names, nesting, and
rubric shape must be identical. Deviation breaks downstream parsing.

## Rules

1. Manifest.hypotheses: produce EXACTLY 3 measurable hypotheses (H1/H2/H3).
   Each must be a concrete, quantitative claim that a rubric can check
   (e.g. "method A achieves X > Y on at least 2 of 3 datasets"). Avoid
   vague prose like "works well" or "is competitive".
2. Manifest.experiment_design: include 3-5 conditions, 2-4 metrics, 2-3
   datasets (all from sklearn.datasets or trivially synthesisable —
   NEVER require downloads), 1-2 baselines, and compute_requirements
   with gpu_required=false + estimated_wall_clock_sec ≤ 900.
3. Manifest.synthesis: 3-6 paragraphs framing the research QUESTION
   (not a paper to reproduce). End with an italicised one-line
   research question.
4. Rubric: produce a single root node with 3 internal children —
   ``<tid>-code`` (weight 2), ``<tid>-exec`` (weight 2), ``<tid>-results``
   (weight 3) — each with 2-4 leaves. Total leaves: 7-10.
5. Every LEAF has ``task_category`` in the set {{"Code Development",
   "Code Execution", "Result Analysis"}} and a ``finegrained_task_category``
   picked from: "Method Implementation", "Experimental Setup",
   "Dataset and Model Acquisition", "Evaluation, Metrics & Benchmarking",
   "Logging, Analysis & Presentation", "Hyperparameter Tuning".
6. Every INTERNAL node (root, code, exec, results) has
   ``task_category: null`` and ``finegrained_task_category: null`` and a
   non-empty ``sub_tasks`` array. Leaves have ``sub_tasks: []``.
7. One of the results leaves must be a writeup leaf requiring a
   prose summary ≥ 200 words that states per-hypothesis verdicts and
   limitations.

## Output format (strict JSON, no prose outside)

{{
  "manifest_yaml": "<full YAML as a string, exactly in the exemplar shape>",
  "rubric_json":   {{<the rubric object>}}
}}

## EXEMPLAR — manifest (for topic T01)
```yaml
{exemplar_manifest}
```

## EXEMPLAR — rubric (for topic T01)
```json
{exemplar_rubric}
```

## TARGET TOPIC
id: {topic_id}
topic: {topic_str}
domains: {domains}
metric_key: {metric_key}
metric_direction: {metric_direction}

Emit the JSON object and NOTHING ELSE.
"""


def _extract_json(blob: str) -> dict[str, Any]:
    text = blob.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        if start < 0:
            raise ValueError(f"no JSON object in output: {blob[:300]}")
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


def _load_topics() -> list[dict[str, Any]]:
    data = yaml.safe_load((ROOT / "config" / "topics.yaml").read_text(encoding="utf-8"))
    return data.get("topics", [])


def _load_exemplars() -> tuple[str, str]:
    manifest_path = MANIFEST_DIR / "T01.yaml"
    rubric_path = RUBRIC_DIR / "T01.json"
    if not manifest_path.is_file() or not rubric_path.is_file():
        raise SystemExit(
            "T01 exemplar missing — write manifests/T01.yaml and "
            "rubrics/T01.json first."
        )
    manifest_yaml = manifest_path.read_text(encoding="utf-8")
    rubric_json = rubric_path.read_text(encoding="utf-8")
    return manifest_yaml, rubric_json


def _call_llm(prompt: str) -> dict[str, Any]:
    cfg = LLMConfig(
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        primary_model=os.environ.get("OPENAI_MODEL", "gpt-5.3-codex"),
        fallback_models=[os.environ.get("OPENAI_SMALL_FAST_MODEL", "gpt-4o")],
        max_tokens=8000,
        timeout_sec=600,
    )
    client = LLMClient(cfg)
    resp = client.chat(
        messages=[{"role": "user", "content": prompt}],
        json_mode=True,
        max_tokens=8000,
    )
    return _extract_json(resp.content)


def _validate_manifest(payload: dict[str, Any], topic_id: str) -> None:
    if payload.get("id") != topic_id:
        raise ValueError(f"manifest.id={payload.get('id')} != {topic_id}")
    hs = payload.get("hypotheses") or []
    if len(hs) != 3:
        raise ValueError(f"expected 3 hypotheses, got {len(hs)}")
    design = payload.get("experiment_design") or {}
    if not design.get("conditions") or not design.get("metrics") \
       or not design.get("datasets"):
        raise ValueError("experiment_design missing conditions/metrics/datasets")


def _validate_rubric(rubric: dict[str, Any], topic_id: str) -> None:
    tid = topic_id.lower()
    if rubric.get("id") != f"{tid}-root":
        raise ValueError(f"rubric root id is {rubric.get('id')} (expected {tid}-root)")
    children = {c["id"]: c for c in rubric.get("sub_tasks", [])}
    for key in (f"{tid}-code", f"{tid}-exec", f"{tid}-results"):
        if key not in children:
            raise ValueError(f"rubric missing child {key}")
    # Count leaves
    leaves = 0

    def _walk(node: dict[str, Any]) -> None:
        nonlocal leaves
        sub = node.get("sub_tasks") or []
        if not sub:
            leaves += 1
            if node.get("task_category") not in (
                "Code Development", "Code Execution", "Result Analysis"
            ):
                raise ValueError(
                    f"leaf {node.get('id')} has invalid "
                    f"task_category={node.get('task_category')}"
                )
            return
        for c in sub:
            _walk(c)

    _walk(rubric)
    if leaves < 7 or leaves > 12:
        raise ValueError(f"rubric has {leaves} leaves (expected 7-12)")


def generate_one(topic: dict[str, Any], exemplar_manifest: str,
                 exemplar_rubric: str, *, dry_run: bool) -> tuple[Path, Path] | None:
    topic_id = topic["id"]
    manifest_out = MANIFEST_DIR / f"{topic_id}.yaml"
    rubric_out = RUBRIC_DIR / f"{topic_id}.json"

    prompt = PROMPT_TEMPLATE.format(
        exemplar_manifest=exemplar_manifest,
        exemplar_rubric=exemplar_rubric,
        topic_id=topic_id,
        topic_str=topic["topic"],
        domains=json.dumps(topic.get("domains", [])),
        metric_key=topic.get("metric_key", "primary_metric"),
        metric_direction=topic.get("metric_direction", "maximize"),
    )

    print(f"  [{topic_id}] prompting LLM (≈{len(prompt)} chars)")
    if dry_run:
        print(f"  [{topic_id}] (dry-run; would generate {manifest_out.name})")
        return None

    payload = _call_llm(prompt)
    manifest_yaml_text = payload.get("manifest_yaml", "")
    rubric_obj = payload.get("rubric_json", {})
    if not manifest_yaml_text or not isinstance(rubric_obj, dict):
        raise SystemExit(f"[{topic_id}] LLM returned malformed payload")

    # Parse + validate
    manifest_obj = yaml.safe_load(manifest_yaml_text)
    _validate_manifest(manifest_obj, topic_id)
    _validate_rubric(rubric_obj, topic_id)

    manifest_out.write_text(manifest_yaml_text.rstrip() + "\n", encoding="utf-8")
    rubric_out.write_text(
        json.dumps(rubric_obj, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"  [{topic_id}] wrote {manifest_out.name} + {rubric_out.name}")
    return manifest_out, rubric_out


def main() -> int:
    ap = argparse.ArgumentParser(description="Bulk-generate ARC-Bench manifests + rubrics")
    ap.add_argument("--topic", help="single topic id (default: all missing)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing manifests")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    MANIFEST_DIR.mkdir(exist_ok=True)
    RUBRIC_DIR.mkdir(exist_ok=True)

    exemplar_manifest, exemplar_rubric = _load_exemplars()

    topics = _load_topics()
    if args.topic:
        topics = [t for t in topics if t["id"] == args.topic]
        if not topics:
            raise SystemExit(f"topic not in topics.yaml: {args.topic}")

    for topic in topics:
        tid = topic["id"]
        mpath = MANIFEST_DIR / f"{tid}.yaml"
        rpath = RUBRIC_DIR / f"{tid}.json"
        if mpath.is_file() and rpath.is_file() and not args.force:
            print(f"  [{tid}] already present — skipping (use --force to overwrite)")
            continue
        try:
            generate_one(topic, exemplar_manifest, exemplar_rubric,
                         dry_run=args.dry_run)
        except Exception as exc:  # noqa: BLE001
            print(f"  [{tid}] ERROR: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
