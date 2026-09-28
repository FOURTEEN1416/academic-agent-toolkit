#!/usr/bin/env python3
"""Run AI-Scientist-v2 end-to-end on one ARC-Bench topic, then judge.

Pipeline:
  1. Build workshop .md from the topic manifest (title, keywords, abstract,
     hypotheses, condition list).
  2. Write a per-topic bfts_config.yaml that routes all agent roles through
     ``gpt-4o`` (a widely-available model on most proxies) and trims
     stage/step counts so one topic finishes in ~1-2h on CPU.
  3. Invoke ``ai_scientist/perform_ideation_temp_free.py`` — produces an
     ideas JSON.
  4. Invoke ``launch_scientist_bfts.py --skip_writeup --skip_review`` —
     runs BFTS and plot aggregation (no PDF/citation/review — our judge
     only reads claims + metrics, not the paper).
  5. Post-process the AIS-v2 experiment directory into an ARC-Bench
     ``submission/`` layout (README.md, claims.json, results/metrics.json).
  6. Invoke ``scripts/judge.py`` on the submission; write
     ``judge_result.json`` under ``results/ais_v2/<Txx>/<run_ts>/``.

Usage:
    python3 experiments/arc_bench/scripts/run_ais_v2.py --topic T01
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent.parent
AIS_REPO = ROOT / "baseline" / "external" / "AI-Scientist-v2"
VENV_PY = Path(
    os.environ.get(
        "ARC_AIS_V2_PYTHON",
        str(Path.home() / "arc_bench" / "ais_v2_venv" / "bin" / "python"),
    )
)

RESULTS_DIR = ROOT / "results" / "ais_v2"
LOG_DIR = ROOT / "results" / "legacy" / "log" / "ais_v2"

PROXY_URL = os.environ.get(
    "OPENAI_BASE_URL", "https://api.openai.com/v1"
)
PROXY_KEY = os.environ.get("OPENAI_API_KEY", "")
if not PROXY_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY env var is required; set it before invoking run_ais_v2.py"
    )
# Matches RC-FULL wire: gpt-5.3-codex via /v1/responses for autonomous code
# generation; gpt-4o via /v1/chat/completions for tool-calling / JSON modes
# (select_node, feedback function-calls, ideation, summarization).
CODE_MODEL = "gpt-5.3-codex"
CHAT_MODEL = "gpt-4o"


def build_workshop_md(manifest: dict) -> str:
    hyp_lines = [f"- {h['id']}: {h['statement']}" for h in manifest.get("hypotheses", [])]
    cond_lines = [f"- {c['name']}: {c.get('description','')}"
                  for c in manifest.get("experiment_design", {}).get("conditions", [])]
    metric_names = [m["name"] for m in
                    manifest.get("experiment_design", {}).get("metrics", [])]
    datasets = manifest.get("experiment_design", {}).get("datasets", [])
    return "\n".join([
        f"# Title",
        manifest.get("title", manifest.get("id", "ARC-Bench topic")),
        "",
        "## Keywords",
        "machine-learning, benchmark, cpu-only",
        "",
        "## TL;DR",
        manifest.get("experiment_design", {}).get(
            "research_question", "A CPU-scale ML empirical study."),
        "",
        "## Abstract",
        manifest.get("synthesis", "").strip()
        + "\n\nThe study must measure the following metrics: "
        + ", ".join(metric_names) + ".",
        "",
        "## Hypotheses",
        *hyp_lines,
        "",
        "## Proposed Conditions",
        *cond_lines,
        "",
        "## Datasets",
        *[f"- {d.get('name','?')} ({d.get('source','?')})" for d in datasets],
        "",
        "## Constraints",
        "- CPU-only, scikit-learn / numpy / pandas permitted; torch is installed",
        "  (CPU build) but deep models should stay small.",
        "- Wall-clock budget per experiment cell: 300 seconds.",
        "- Report at least 3 quantitative claims grounded in measured metrics.",
        "",
    ])


def write_bfts_config(dest: Path) -> None:
    cfg = {
        "data_dir": "data",
        "preprocess_data": False,
        "goal": None,
        "eval": None,
        "log_dir": "logs",
        "workspace_dir": "workspaces",
        "copy_data": True,
        "exp_name": "run",
        "exec": {"timeout": 300, "agent_file_name": "runfile.py",
                 "format_tb_ipython": False},
        "generate_report": True,
        "report": {"model": CHAT_MODEL, "temp": 1.0},
        "experiment": {"num_syn_datasets": 1},
        "debug": {"stage4": False},
        "agent": {
            "type": "parallel",
            "num_workers": 2,
            "stages": {"stage1_max_iters": 10, "stage2_max_iters": 4,
                       "stage3_max_iters": 4, "stage4_max_iters": 6},
            "steps": 3,
            "k_fold_validation": 1,
            "multi_seed_eval": {"num_seeds": 2},
            "expose_prediction": False,
            "data_preview": False,
            # Code role = pure-text generation → gpt-5.3-codex via /v1/responses
            "code": {"model": CODE_MODEL, "temp": 1.0, "max_tokens": 8000},
            # Tool-calling / JSON / feedback roles → gpt-4o via chat_completions
            "feedback": {"model": CHAT_MODEL, "temp": 0.5, "max_tokens": 4096},
            "vlm_feedback": {"model": CHAT_MODEL, "temp": 0.5, "max_tokens": None},
            "summary": {"model": CHAT_MODEL, "temp": 0.5},
            "select_node": {"model": CHAT_MODEL, "temp": 0.3},
            "search": {"max_debug_depth": 2, "debug_prob": 0.3, "num_drafts": 2},
        },
    }
    dest.write_text(yaml.safe_dump(cfg, sort_keys=False))


def _ais_env() -> dict:
    env = os.environ.copy()
    env.update({
        "OPENAI_BASE_URL": PROXY_URL,
        "OPENAI_API_KEY": PROXY_KEY,
        "CUDA_VISIBLE_DEVICES": "",
    })
    return env


def run_ideation(workshop_md: Path, log_path: Path, env: dict) -> Path:
    ideas_json = workshop_md.with_suffix(".json")
    cmd = [
        str(VENV_PY), "-u",
        "ai_scientist/perform_ideation_temp_free.py",
        "--workshop-file", str(workshop_md),
        "--model", CHAT_MODEL,
        "--max-num-generations", "2",
        "--num-reflections", "2",
    ]
    _stream(cmd, cwd=AIS_REPO, log_path=log_path, env=env)
    if not ideas_json.is_file():
        raise RuntimeError(f"ideation finished but no {ideas_json}")
    return ideas_json


def run_bfts(ideas_json: Path, log_path: Path, env: dict) -> Path:
    # Parallel-safe: identify the output dir by idea['Name'] rather than
    # snapshot-diff of AIS_REPO/experiments, which is racy when multiple
    # topics run concurrently (each BFTS creates its own
    # experiments/<date>_<Name>_attempt_0/ dir; snapshot-diff picks the
    # lexicographic max of ALL new dirs instead of the one *this* run made).
    ideas = json.loads(ideas_json.read_text(encoding="utf-8"))
    if not isinstance(ideas, list) or not ideas:
        raise RuntimeError(f"ideas file {ideas_json} is empty or not a list")
    idea_name = str(ideas[0].get("Name", "")).strip()
    if not idea_name:
        raise RuntimeError(f"ideas[0] in {ideas_json} has no 'Name'")
    cmd = [
        str(VENV_PY), "-u",
        "launch_scientist_bfts.py",
        "--load_ideas", str(ideas_json),
        "--model_writeup", CHAT_MODEL,
        "--model_writeup_small", CHAT_MODEL,
        "--model_citation", CHAT_MODEL,
        "--model_review", CHAT_MODEL,
        "--model_agg_plots", CHAT_MODEL,
        "--num_cite_rounds", "3",
        "--writeup-retries", "1",
        "--writeup-type", "icbinb",
        "--skip_writeup",
        "--skip_review",
        "--attempt_id", "0",
        "--idea_idx", "0",
    ]
    _stream(cmd, cwd=AIS_REPO, log_path=log_path, env=env)
    candidates = sorted((AIS_REPO / "experiments").glob(
        f"*_{idea_name}_attempt_0"))
    if not candidates:
        raise RuntimeError(
            f"BFTS finished but no experiments/*_{idea_name}_attempt_0 found")
    return candidates[-1]


def _stream(cmd, *, cwd: Path, log_path: Path, env: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[run_ais_v2] exec: {' '.join(cmd)}", flush=True)
    with open(log_path, "ab") as f:
        f.write(f"\n\n=== {' '.join(cmd)} ===\n".encode())
        p = subprocess.Popen(cmd, cwd=str(cwd), env=env,
                             stdout=f, stderr=subprocess.STDOUT)
        rc = p.wait()
    if rc != 0:
        raise RuntimeError(f"cmd failed rc={rc}: {' '.join(cmd)} — see {log_path}")


def _snapshot(path: Path) -> set[str]:
    if not path.is_dir():
        return set()
    return {p.name for p in path.iterdir() if p.is_dir()}


# Stopwords dropped when computing hypothesis↔evidence token overlap for
# verdict assignment. Leaves only technical/hypothesis-specific anchors.
_CLAIM_STOP = frozenset({
    "that", "this", "with", "from", "have", "been", "their", "these",
    "those", "will", "must", "over", "more", "less", "than", "most",
    "into", "also", "such", "same", "each", "only", "some", "both",
    "very", "many", "when", "which", "they", "them", "then", "here",
    "there", "mean", "means", "report", "reports", "show", "shows",
    "using", "across", "between", "are", "the", "and", "but", "for",
    # Domain boilerplate that would inflate overlap w/o discriminating
    # between hypotheses.
    "test", "train", "model", "models", "data", "dataset", "datasets",
    "metric", "metrics", "experiment", "experiments", "results",
    "result", "evaluation", "performance",
})


def _canonical_metric_keys(metric_name: str) -> list[str]:
    """Map AIS-v2 raw metric names to ARC-Bench canonical primary keys.

    The judge's ``_correctness_signal`` tries ``primary_key`` and
    ``primary_key.lower()`` against each condition's metrics dict. Manifest
    primary keys for ARC-Bench topics are short canonical strings like
    ``test_accuracy``, ``ece``, ``nll``, ``brier`` — but AIS-v2 emits
    verbose names like ``"test accuracy"`` and ``"test ECE"``. This mapper
    lets us emit both so either lookup hits.
    """
    mn = metric_name.lower().strip()
    out: list[str] = []
    if "test" not in mn:
        return out
    if "accuracy" in mn or mn.endswith(" acc") or " acc " in mn:
        out.append("test_accuracy")
    if "ece" in mn or "calibration error" in mn:
        out.append("ece")
    if "nll" in mn or "negative log" in mn:
        out.append("nll")
    if "brier" in mn:
        out.append("brier")
    if "loss" in mn and "ece" not in mn and "nll" not in mn:
        out.append("test_loss")
    if "f1" in mn:
        out.append("f1")
    if "auc" in mn or "roc" in mn:
        out.append("auc")
    if "rmse" in mn:
        out.append("rmse")
    if "mae" in mn:
        out.append("mae")
    return out


def _metrics_from_metric_value(metric_value: dict) -> dict[str, float]:
    """AIS-v2 ``metric.value.metric_names[]`` → flat ``{key: float}``.

    For each reported (metric_name, dataset) pair we emit
    ``"{dataset}__{metric_name}"`` for uniqueness + any matching canonical
    ARC-Bench keys (``test_accuracy``, ``ece``, ``nll``, ``brier``, …) so
    the judge's primary-metric lookup succeeds.
    """
    out: dict[str, float] = {}
    for m in (metric_value or {}).get("metric_names", []) or []:
        mn = str(m.get("metric_name", "")).strip()
        if not mn:
            continue
        canonical = _canonical_metric_keys(mn)
        for dp in m.get("data", []) or []:
            val = dp.get("final_value")
            if not isinstance(val, (int, float)):
                continue
            fval = float(val)
            ds = str(dp.get("dataset_name", "default"))
            raw_key = f"{ds}__{mn}"
            out[raw_key] = fval
            for ck in canonical:
                out.setdefault(ck, fval)
    return out


def _add_condition(condition_summaries: dict, name: str, entry: dict) -> None:
    if not isinstance(entry, dict):
        return
    metric_value = (entry.get("metric") or {}).get("value") or {}
    metrics = _metrics_from_metric_value(metric_value)
    if metrics:
        safe = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")[:80] or name
        condition_summaries[safe] = {"metrics": metrics}


_PAREN_RE = re.compile(r"\s*\(([^()]{1,80})\)\s*$")


def _safe_cond_key(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]+", "_", s).strip("_")
    return s[:80] or "cond"


def _pivot_per_condition_from_entry(entry: dict) -> dict[str, dict[str, float]]:
    """Extract per-condition metric dicts from an AIS-v2 ``best node`` / ablation entry.

    AIS-v2 commonly encodes the canonical "condition" as either:
      (a) a parenthesized suffix in ``metric_name`` — e.g. ``"relative RMSE
          degradation (DecisionTree)"`` where the paren tag *is* the condition.
      (b) a parenthesized suffix in ``dataset_name`` — e.g.
          ``"synthetic_outlier_knn (scaler = standard)"`` where the paren
          encodes ``key = value`` for the condition.

    The rubric-driven judge needs separate ``condition_summaries[<cond>]`` keys
    so it can check per-condition primary-metric coverage. Without this pivot
    the entire experiment collapses into a single "baseline" condition even
    when AIS-v2 actually ran all canonical variants.

    Returns ``{condition_name: {metric_key: float}}`` ready to merge into the
    top-level ``condition_summaries`` map.
    """
    mv = (entry.get("metric") or {}).get("value") or {}
    out: dict[str, dict[str, float]] = {}
    for m in mv.get("metric_names", []) or []:
        raw_mn = str(m.get("metric_name", "")).strip()
        if not raw_mn:
            continue
        # Strip trailing paren from metric_name → condition tag
        mn_cond = None
        clean_mn = raw_mn
        pm = _PAREN_RE.search(raw_mn)
        if pm:
            mn_cond = pm.group(1).strip()
            clean_mn = raw_mn[:pm.start()].strip()
        for dp in m.get("data", []) or []:
            val = dp.get("final_value")
            if not isinstance(val, (int, float)):
                continue
            fval = float(val)
            raw_ds = str(dp.get("dataset_name", "")).strip()
            ds_cond = None
            clean_ds = raw_ds
            pd = _PAREN_RE.search(raw_ds)
            if pd:
                ds_cond = pd.group(1).strip()
                clean_ds = raw_ds[:pd.start()].strip()
            # Determine condition name: prefer dataset-paren (usually the
            # axis of variation), fall back to metric-paren.
            cond = ds_cond or mn_cond
            if not cond:
                continue
            # If paren was "key = value" keep the value as the cond label
            if "=" in cond:
                cond = cond.split("=", 1)[1].strip() or cond
            cond_key = _safe_cond_key(cond)
            bucket = out.setdefault(cond_key, {})
            key_prefix = clean_ds or "default"
            metric_key = f"{key_prefix}__{clean_mn}".strip("_")
            bucket[metric_key] = fval
            for ck in _canonical_metric_keys(clean_mn):
                bucket.setdefault(ck, fval)
    return out


def _add_pivoted_conditions(condition_summaries: dict, entry: dict) -> int:
    """Merge per-condition pivot output into the running summaries map.

    Returns the number of canonical conditions added.
    """
    added = 0
    for cond, metrics in _pivot_per_condition_from_entry(entry).items():
        if not metrics:
            continue
        existing = condition_summaries.get(cond)
        if isinstance(existing, dict) and isinstance(existing.get("metrics"), dict):
            existing["metrics"].update(metrics)
        else:
            condition_summaries[cond] = {"metrics": metrics}
            added += 1
    return added


def _tokens(s: str) -> set[str]:
    toks = re.findall(r"[a-z][a-z0-9_]{3,}", s.lower())
    return {t for t in toks if t not in _CLAIM_STOP and len(t) >= 4}


def build_submission(ais_run_dir: Path, topic: dict, out_dir: Path) -> None:
    """Synthesize an ARC-Bench ``submission/`` + ``stage-*/`` layout.

    AIS-v2 writes its canonical output to
    ``<run>/logs/0-run/{baseline,ablation,research,draft}_summary.json``.
    ``baseline_summary`` / ``research_summary`` each contain a single
    "best node" with a ``metric.value.metric_names[]`` list.
    ``ablation_summary`` is a list of ablation nodes with the same
    metric schema + an ``ablation_name``. ``draft_summary`` carries the
    framework's own narrative (``Experiment_description``,
    ``Key_numerical_results``, …) which we use for (a) README writeup,
    (b) hypothesis↔evidence overlap for verdict assignment.

    The downstream judge pipeline (``judge.grade`` →
    ``paperbench_bridge.build_submission``) reads
    ``run_dir/stage-14/experiment_summary.json``, ``run_dir/stage-10/*.py``,
    ``run_dir/stage-13/*.py`` and ``submission/claims.json``. All four
    are materialized here in the schema those consumers expect.
    """
    sub = out_dir / "submission"
    (sub / "results").mkdir(parents=True, exist_ok=True)

    # 1. Harvest the four top-level summaries AIS-v2 emits
    run_logs = ais_run_dir / "logs" / "0-run"
    summaries: dict[str, object] = {}
    for name in ("baseline_summary", "ablation_summary",
                 "research_summary", "draft_summary"):
        p = run_logs / f"{name}.json"
        if not p.is_file():
            continue
        try:
            summaries[name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[run_ais_v2] WARN could not parse {p}: {exc}", flush=True)

    # 2. Flatten the summaries into condition_summaries
    condition_summaries: dict = {}

    baseline = summaries.get("baseline_summary")
    if isinstance(baseline, dict) and isinstance(baseline.get("best node"), dict):
        bn = baseline["best node"]
        # Pivot per-condition metrics out of parenthesized metric/dataset
        # suffixes FIRST so canonical conditions (DecisionTree, RandomForest,
        # scaler=standard, …) surface as top-level keys — without this pivot
        # AIS-v2's BFTS output collapses the whole experiment to a single
        # "baseline" condition and the rubric's per-condition leaves all fail.
        n_pivot = _add_pivoted_conditions(condition_summaries, bn)
        # Keep the aggregate "baseline" entry only if no pivot was produced;
        # otherwise its metrics are redundant noise that confuses the judge.
        if n_pivot == 0:
            _add_condition(condition_summaries, "baseline", bn)

    research = summaries.get("research_summary")
    if isinstance(research, dict) and isinstance(research.get("best node"), dict):
        rn = research["best node"]
        n_pivot_r = _add_pivoted_conditions(condition_summaries, rn)
        if n_pivot_r == 0:
            _add_condition(condition_summaries, "research_best", rn)

    ablations = summaries.get("ablation_summary")
    if isinstance(ablations, list):
        for i, entry in enumerate(ablations):
            if not isinstance(entry, dict):
                continue
            # Pivot the ablation entry too (its metric/dataset parens usually
            # encode the ablation axis levels, e.g. "scaler = robust").
            n_pivot_a = _add_pivoted_conditions(condition_summaries, entry)
            if n_pivot_a == 0:
                cond_name = entry.get("ablation_name") or f"ablation_{i:02d}"
                _add_condition(condition_summaries, str(cond_name), entry)

    # 3. Ablation warnings — zero-variance detection on canonical metrics
    ablation_warnings: list[str] = []
    if len(condition_summaries) == 0:
        ablation_warnings.append(
            "no condition summaries — BFTS produced no parseable metrics")
    else:
        for k in ("test_accuracy", "ece", "nll", "brier"):
            vals = [v["metrics"][k] for v in condition_summaries.values()
                    if isinstance(v["metrics"].get(k), (int, float))]
            if len(vals) >= 2 and (max(vals) - min(vals)) < 1e-9:
                ablation_warnings.append(f"zero variance on metric {k}")

    # 4. Write stage-14/experiment_summary.json in the judge-expected schema
    stage14 = out_dir / "stage-14"
    stage14.mkdir(parents=True, exist_ok=True)
    summary_payload: dict = {
        "condition_summaries": condition_summaries,
        "ablation_warnings": ablation_warnings,
        "source": "ai_scientist_v2",
        "ais_run_dir": str(ais_run_dir),
        "n_conditions": len(condition_summaries),
    }
    draft = summaries.get("draft_summary")
    if isinstance(draft, dict):
        summary_payload["draft_summary"] = draft
    (stage14 / "experiment_summary.json").write_text(
        json.dumps(summary_payload, indent=2), encoding="utf-8")

    # 5. README with the "## Agent-produced writeup" guard so
    #    paperbench_bridge.build_submission() won't overwrite it
    readme_parts = [
        f"# AIS-v2 autonomous run: {topic['title']}",
        "",
        "## Agent-produced writeup",
        "",
    ]
    if isinstance(draft, dict):
        for key, heading in (
            ("Experiment_description", "Experiment description"),
            ("Significance", "Significance"),
            ("Description", "Methodology"),
        ):
            if draft.get(key):
                readme_parts += [f"### {heading}", "",
                                 str(draft[key]).strip(), ""]
        knr = draft.get("Key_numerical_results") or []
        if knr:
            readme_parts += ["### Key numerical results", ""]
            for r in knr:
                if not isinstance(r, dict):
                    continue
                readme_parts.append(
                    f"- **{r.get('description', '?')}** → "
                    f"{r.get('result', '?')}. {r.get('analysis', '')}".strip())
            readme_parts.append("")
    idea_md = ais_run_dir / "idea.md"
    if idea_md.is_file():
        readme_parts += ["### Research idea", "",
                         idea_md.read_text(encoding="utf-8"), ""]
    (sub / "README.md").write_text("\n".join(readme_parts), encoding="utf-8")

    # 6. claims.json — evidence-based verdict.
    #    Assign "partially_supported" when the topic hypothesis and the
    #    framework's own narrative share ≥2 discriminating tokens AND at
    #    least one condition produced numeric results. Otherwise keep
    #    "inconclusive". This is honest: we never claim "supported"
    #    without the full statistical test the hypothesis requires,
    #    but we credit the framework for producing interpretable evidence.
    evidence_chunks: list[str] = []
    if isinstance(draft, dict):
        evidence_chunks.append(str(draft.get("Experiment_description", "")))
        evidence_chunks.append(str(draft.get("Significance", "")))
        evidence_chunks.append(str(draft.get("Description", "")))
        for r in draft.get("Key_numerical_results", []) or []:
            if isinstance(r, dict):
                evidence_chunks.append(str(r.get("description", "")))
                evidence_chunks.append(str(r.get("analysis", "")))
    for key in ("baseline_summary", "research_summary"):
        s = summaries.get(key)
        best = (s or {}).get("best node") if isinstance(s, dict) else None
        if isinstance(best, dict):
            evidence_chunks.append(str(best.get("vlm_feedback_summary", "")))
            evidence_chunks.append(str(best.get("analysis", "")))
    if isinstance(ablations, list):
        for entry in ablations:
            if isinstance(entry, dict):
                evidence_chunks.append(str(entry.get("ablation_name", "")))
                evidence_chunks.append(
                    str(entry.get("vlm_feedback_summary", "")))
    evidence_text = " ".join(evidence_chunks)
    evidence_tokens = _tokens(evidence_text)

    # A condition-name token pool — the hypothesis must mention something
    # concretely addressable by the framework's output (e.g., a specific
    # dropout variant, a specific dataset) for us to credit it as
    # "partially_supported". Pure-generic overlap ("model", "accuracy")
    # stays at "inconclusive".
    condition_tokens: set[str] = set()
    for cname in condition_summaries:
        condition_tokens |= _tokens(cname)
    if isinstance(draft, dict):
        # Draft often names the specific conditions (mc_dropout, spatial, …)
        condition_tokens |= _tokens(str(draft.get("Description", "")))

    claims: list[dict] = []
    for h in topic.get("hypotheses", []):
        stmt = str(h.get("statement", ""))
        stmt_tokens = _tokens(stmt)
        overlap = sorted(stmt_tokens & evidence_tokens)
        cond_overlap = sorted(stmt_tokens & condition_tokens)
        # partially_supported requires:
        #   (a) ≥3 evidence-overlap tokens (non-trivial thematic match), AND
        #   (b) ≥1 condition-overlap token (framework addressed *this*
        #       hypothesis concretely, not just the broader topic)
        #   (c) at least one condition in the experiment summary
        if condition_summaries and len(overlap) >= 3 and len(cond_overlap) >= 1:
            verdict = "partially_supported"
        else:
            verdict = "inconclusive"
        claims.append({
            "id": h["id"],
            "statement": stmt,
            "verdict": verdict,
            "evidence_overlap": overlap,
            "condition_overlap": cond_overlap,
            "support": {
                "source": "ais_v2_bfts",
                "evidence_tokens": len(overlap),
                "condition_tokens": len(cond_overlap),
                "n_conditions": len(condition_summaries),
            },
        })
    (sub / "claims.json").write_text(
        json.dumps({"claims": claims}, indent=2), encoding="utf-8")

    # 7. stage-10 / stage-13 code — paperbench_bridge copies from both
    stage10 = out_dir / "stage-10"
    stage10.mkdir(exist_ok=True)
    stage13 = out_dir / "stage-13"
    stage13.mkdir(exist_ok=True)

    def _best_code(s: object) -> str | None:
        if isinstance(s, dict) and isinstance(s.get("best node"), dict):
            c = s["best node"].get("code")
            if isinstance(c, str) and c.strip():
                return c
        return None

    baseline_code = _best_code(summaries.get("baseline_summary"))
    research_code = _best_code(summaries.get("research_summary"))

    if baseline_code:
        (stage10 / "experiment.py").write_text(baseline_code, encoding="utf-8")
    else:
        runfiles = sorted(ais_run_dir.rglob("runfile.py"))
        if runfiles:
            shutil.copy(runfiles[-1], stage10 / "experiment.py")
        else:
            (stage10 / "experiment.py").write_text(
                "# AIS-v2 produced no runfile.py — see ais_v2_artifacts/ for logs\n",
                encoding="utf-8")

    if research_code:
        (stage13 / "experiment_final.py").write_text(
            research_code, encoding="utf-8")
    elif baseline_code:
        (stage13 / "experiment_final.py").write_text(
            baseline_code, encoding="utf-8")

    # 8. Audit trail — carry workspaces/*.npy out (kept-out to stay small)
    audit = out_dir / "ais_v2_artifacts"
    if audit.exists():
        shutil.rmtree(audit)
    shutil.copytree(
        ais_run_dir, audit,
        ignore=shutil.ignore_patterns(
            "workspaces", "*.pdf", "*.npy", "experiment_data.npy"))


def run_judge(topic_id: str, out_dir: Path) -> Path:
    judge = ROOT / "scripts" / "judge.py"
    cmd = [sys.executable, str(judge),
           "--topic", topic_id,
           "--run-dir", str(out_dir),
           "--debug"]
    print(f"[run_ais_v2] judging: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)
    return out_dir / "judge_result.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    args = ap.parse_args()
    tid = args.topic

    manifest_path = ROOT / "manifests" / f"{tid}.yaml"
    if not manifest_path.is_file():
        raise SystemExit(f"no manifest: {manifest_path}")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS_DIR / tid / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / tid / f"{ts}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[run_ais_v2] topic={tid} out={out_dir} log={log_path}")

    # 1. Workshop markdown
    workshop_dir = AIS_REPO / "ai_scientist" / "ideas"
    workshop_md = workshop_dir / f"arc_{tid.lower()}.md"
    workshop_md.write_text(build_workshop_md(manifest), encoding="utf-8")

    # 2. bfts_config override
    write_bfts_config(AIS_REPO / "bfts_config.yaml")

    # 3. Run pipeline
    env = _ais_env()
    t0 = time.monotonic()
    try:
        ideas_json = run_ideation(workshop_md, log_path, env)
        ais_run_dir = run_bfts(ideas_json, log_path, env)
    except Exception as exc:
        (out_dir / "error.txt").write_text(
            f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        print(f"[run_ais_v2] FAILED: {exc}")
        return 2
    elapsed = time.monotonic() - t0

    # 4. Bridge + judge — wrap in try/except so a bridge or judge failure
    #    surfaces as an explicit error.txt instead of a silent exit. This
    #    preserves the BFTS run on disk even if post-processing fails, so
    #    we can re-bridge later without re-running the expensive LLM loop.
    topic_meta = {
        "id": tid,
        "title": manifest.get("title", tid),
        "hypotheses": manifest.get("hypotheses", []),
    }
    try:
        build_submission(ais_run_dir, topic_meta, out_dir)
        judge_json = run_judge(tid, out_dir)
    except Exception as exc:  # noqa: BLE001
        import traceback
        tb = traceback.format_exc()
        (out_dir / "error.txt").write_text(
            f"{type(exc).__name__}: {exc}\n\n{tb}\n"
            f"ais_run_dir: {ais_run_dir}\n", encoding="utf-8")
        print(f"[run_ais_v2] BRIDGE/JUDGE FAILED: {exc}", flush=True)
        print(tb, flush=True)
        return 3

    summary = {
        "topic": tid,
        "framework": "ais_v2",
        "started_at": ts,
        "elapsed_sec": round(elapsed, 1),
        "ais_run_dir": str(ais_run_dir),
        "judge_result": str(judge_json),
    }
    (out_dir / "experiment_meta.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[run_ais_v2] done in {elapsed:.0f}s → {judge_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
