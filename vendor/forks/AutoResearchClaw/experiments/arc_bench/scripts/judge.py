#!/usr/bin/env python3
"""ARC-Bench judge — grades a submission against per-topic rubric.

Two backends:
  - ``llm`` (default): Two-round LLM judge that reads code, experiment
    summary and writeup artifacts then scores rubric leaves directly.
    Framework-agnostic: identical discovery for AutoResearchClaw and AIS-v2
    submissions (both produce the same ``submission/`` layout after
    ``build_submission`` runs).
  - ``local``: 4-boolean heuristic (has_code, has_results, has_writeup,
    claims_cover) plus a rubric-leaf keyword heuristic.  Kept for offline /
    CI use; invoke with ``--backend local``.

Intended to be called by ``run_bench.py`` with ``--run-dir <path>
--topic Txx``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import warnings
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent.parent

sys.path.insert(0, str(REPO_ROOT / "experiments" / "paper_replication" / "scripts"))
from paperbench_bridge import build_submission  # noqa: E402


# ---------------------------------------------------------------------------
# Manifest / rubric helpers
# ---------------------------------------------------------------------------

_PREFIX_MAP: dict[str, str] = {
    "ML": "ml",         # ML01-ML25 → config/ml/{manifests,rubrics}/
    "P":  "physics",    # P01-P10   → config/physics/...
    "B":  "biology",    # B01+      → config/biology/...
    "S":  "statistics", # S01+      → config/statistics/...
    "Q":  "quantum",    # Q01+      → config/quantum/...
}


def _resolve_topic_subdir(topic_id: str) -> str:
    """Mirror of prepare_run.py:_resolve_topic_subdir (longest-prefix match)."""
    tid = topic_id.upper()
    for prefix in sorted(_PREFIX_MAP, key=len, reverse=True):
        if tid.startswith(prefix):
            return _PREFIX_MAP[prefix]
    return ""


def _candidate_paths(topic_id: str, *, kind: str, ext: str) -> list[Path]:
    """Resolution order — domain-specific subdir first, then legacy roots.

    kind ∈ {"manifests", "rubrics"};  ext ∈ {"yaml", "json"}.
    Legacy fallbacks preserve backward compatibility with the original
    ``ROOT/manifests`` / ``ROOT/rubrics`` layout that pre-dated config/.
    """
    sub = _resolve_topic_subdir(topic_id)
    paths: list[Path] = []
    if sub:
        paths.append(ROOT / "config" / sub / kind / f"{topic_id}.{ext}")
    paths.append(ROOT / "config" / kind / f"{topic_id}.{ext}")
    paths.append(ROOT / kind / f"{topic_id}.{ext}")
    return paths


def load_manifest(topic_id: str) -> dict[str, Any]:
    for path in _candidate_paths(topic_id, kind="manifests", ext="yaml"):
        if path.is_file():
            return yaml.safe_load(path.read_text(encoding="utf-8"))
    raise SystemExit(
        f"manifest not found for {topic_id} — tried: "
        + ", ".join(str(p) for p in _candidate_paths(topic_id, kind="manifests", ext="yaml"))
    )


def load_rubric(topic_id: str) -> dict[str, Any]:
    for path in _candidate_paths(topic_id, kind="rubrics", ext="json"):
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    raise SystemExit(
        f"rubric not found for {topic_id} — tried: "
        + ", ".join(str(p) for p in _candidate_paths(topic_id, kind="rubrics", ext="json"))
    )


def _iter_leaves(node: dict[str, Any]):
    sub = node.get("sub_tasks") or []
    if not sub:
        yield node
        return
    for child in sub:
        yield from _iter_leaves(child)


# ---------------------------------------------------------------------------
# Artifact discovery (framework-agnostic)
# ---------------------------------------------------------------------------

def _find_primary_code(run_dir: Path) -> tuple[str | None, str]:
    """Return (code_text, label) for the best available experiment code.

    For multi-file packages the directory is concatenated with file headers.
    Returns (None, "") if nothing is found.

    Discovery order (first match wins):
      1. run_dir/stage-13/experiment_final/   — multi-file package (dir)
      2. run_dir/stage-13/experiment_final.py — flat single file
      3. run_dir/submission/code/stage-13/experiment_final/ — dir (trimmed runs)
      4. run_dir/submission/code/stage-13/experiment_final.py — flat
      5. run_dir/submission/code/stage-10/experiment/       — dir
      6. run_dir/stage-10/experiment.py                     — flat
    """

    def _concat_dir(d: Path, label: str) -> tuple[str, str]:
        parts = []
        for f in sorted(d.rglob("*.py")):
            if not f.is_file() or f.stat().st_size == 0:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore").strip()
                if text:
                    rel = f.relative_to(d)
                    parts.append(f"# === {rel} ===\n{text}")
            except OSError:
                pass
        return ("\n\n".join(parts), label) if parts else ("", label)

    # 1. stage-13/experiment_final/ directory (archive path or direct AIS layout)
    d = run_dir / "stage-13" / "experiment_final"
    if d.is_dir():
        text, lbl = _concat_dir(d, "stage-13/experiment_final/")
        if text:
            return text, lbl

    # 2. stage-13/experiment_final.py flat file (AIS-v2 / archive flat copy)
    p = run_dir / "stage-13" / "experiment_final.py"
    if p.is_file() and p.stat().st_size > 0:
        return p.read_text(encoding="utf-8", errors="ignore"), "stage-13/experiment_final.py"

    # 3. submission/code/stage-13/experiment_final/ directory (trimmed autoclaw, not redirected)
    d = run_dir / "submission" / "code" / "stage-13" / "experiment_final"
    if d.is_dir():
        text, lbl = _concat_dir(d, "submission/code/stage-13/experiment_final/")
        if text:
            return text, lbl

    # 4. submission/code/stage-13/experiment_final.py
    p = run_dir / "submission" / "code" / "stage-13" / "experiment_final.py"
    if p.is_file() and p.stat().st_size > 0:
        return p.read_text(encoding="utf-8", errors="ignore"), "submission/code/stage-13/experiment_final.py"

    # 5. submission/code/stage-10/experiment/ directory
    d = run_dir / "submission" / "code" / "stage-10" / "experiment"
    if d.is_dir():
        text, lbl = _concat_dir(d, "submission/code/stage-10/experiment/")
        if text:
            return text, lbl

    # 6. stage-10/experiment.py
    p = run_dir / "stage-10" / "experiment.py"
    if p.is_file() and p.stat().st_size > 0:
        return p.read_text(encoding="utf-8", errors="ignore"), "stage-10/experiment.py"

    return None, ""


def _find_experiment_summary(run_dir: Path) -> tuple[dict | None, str]:
    """Return (parsed JSON dict, relative_label) for experiment_summary.

    Discovery order:
      1. run_dir/stage-14/experiment_summary.json
      2. Any run_dir/stage-14*/experiment_summary.json  (glob)
      3. Embedded in run_dir/submission/results/metrics.json under key
         "stage-14/experiment_summary.json"
      4. Sidecar run_dir/submission/results/_experiment_summary_from_metrics.json
    """
    primary = run_dir / "stage-14" / "experiment_summary.json"
    if primary.is_file():
        try:
            return json.loads(primary.read_text(encoding="utf-8")), "stage-14/experiment_summary.json"
        except json.JSONDecodeError:
            pass

    globs = sorted(run_dir.glob("stage-14*/experiment_summary.json"))
    for g in globs:
        try:
            return json.loads(g.read_text(encoding="utf-8")), str(g.relative_to(run_dir))
        except json.JSONDecodeError:
            continue

    sub_metrics = run_dir / "submission" / "results" / "metrics.json"
    if sub_metrics.is_file():
        try:
            blob = json.loads(sub_metrics.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            blob = {}
        inner = blob.get("stage-14/experiment_summary.json") if isinstance(blob, dict) else None
        if isinstance(inner, dict) and inner:
            return inner, "submission/results/metrics.json[stage-14/experiment_summary.json]"

    sidecar = run_dir / "submission" / "results" / "_experiment_summary_from_metrics.json"
    if sidecar.is_file():
        try:
            return json.loads(sidecar.read_text(encoding="utf-8")), str(sidecar.relative_to(run_dir))
        except json.JSONDecodeError:
            pass

    return None, ""


def _find_writeup(run_dir: Path) -> tuple[str | None, str]:
    """Return (text, relative_label) for the best available writeup.

    Discovery order:
      1. run_dir/submission/README.md
      2. run_dir/stage-19*/paper_revised.md  (glob, newest)
      3. run_dir/stage-17*/paper_draft.md    (glob, newest)
    """
    readme = run_dir / "submission" / "README.md"
    if readme.is_file() and readme.stat().st_size > 0:
        try:
            return readme.read_text(encoding="utf-8", errors="ignore"), "submission/README.md"
        except OSError:
            pass

    for pat, label_suffix in [("stage-19*/paper_revised.md", "paper_revised.md"),
                               ("stage-17*/paper_draft.md", "paper_draft.md")]:
        matches = sorted(run_dir.glob(pat))
        if matches:
            p = matches[-1]
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                if text.strip():
                    return text, str(p.relative_to(run_dir))
            except OSError:
                continue

    return None, ""


# ---------------------------------------------------------------------------
# LLM backend
# ---------------------------------------------------------------------------

_CODE_CAP = 14000
_SUMMARY_CAP = 8000
_WRITEUP_CAP = 6000

_SYSTEM_PROMPT = (
    "You are a rigorous scientific code reviewer grading AI-generated experiment submissions "
    "against a structured rubric. Your job is to read the provided artifacts and assign a "
    "score in [0.0, 1.0] for each requested rubric leaf.\n\n"
    "Return ONLY valid JSON in exactly this schema:\n"
    "{\n"
    '  "grades": [\n'
    '    {"leaf_id": "<id>", "score": <float 0-1>, "reasoning": "<1-2 sentences>"},\n'
    "    ...\n"
    "  ]\n"
    "}\n\n"
    "Scoring guide:\n"
    "  1.0 — requirement fully met with clear evidence\n"
    "  0.7 — mostly met, minor gaps\n"
    "  0.5 — partially met or unclear from available artifacts\n"
    "  0.3 — attempted but substantially incomplete\n"
    "  0.0 — requirement not met or absent\n\n"
    "Be strict but fair. If the artifact is truncated, score what you can see."
)


def _build_llm_client():
    """Build an LLMClient from environment variables.

    Required env vars:
      OPENAI_API_KEY   — API key
      OPENAI_BASE_URL  — provider base URL (e.g. https://…/v1)
    Optional:
      ARC_JUDGE_MODEL  — override model (default: OPENAI_MODEL or gpt-4o)
      ARC_WIRE_API     — "responses" or "chat_completions" (default: responses)
    """
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from researchclaw.llm.client import LLMClient, LLMConfig
    except ImportError as exc:
        raise RuntimeError(
            "Cannot import researchclaw.llm.client; ensure REPO_ROOT is on PYTHONPATH"
        ) from exc

    model = os.environ.get("ARC_JUDGE_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o"
    cfg = LLMConfig(
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        primary_model=model,
        fallback_models=[os.environ.get("OPENAI_SMALL_FAST_MODEL", model)],
        wire_api=os.environ.get("ARC_WIRE_API", "responses"),
        max_tokens=4096,
        temperature=0.1,
    )
    return LLMClient(cfg)


def _truncate(text: str, cap: int) -> str:
    if len(text) <= cap:
        return text
    return text[:cap] + f"\n... [truncated at {cap} chars]"


def _call_llm_round(
    client: Any,
    prompt: str,
    leaf_ids: set[str],
    *,
    max_tokens: int = 4096,
) -> list[dict[str, Any]]:
    """Call the LLM and return a list of validated grade dicts.

    On any exception returns an empty list (caller fills 0.5 defaults).
    """
    try:
        resp = client.chat(
            [{"role": "user", "content": prompt}],
            system=_SYSTEM_PROMPT,
            json_mode=True,
            max_tokens=max_tokens,
            temperature=0.1,
        )
        raw = json.loads(resp.content)
        grades = raw.get("grades") or []
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"[judge] LLM call failed: {exc}", stacklevel=2)
        return []

    validated: list[dict[str, Any]] = []
    for g in grades:
        lid = str(g.get("leaf_id", "")).strip()
        if lid not in leaf_ids:
            continue
        try:
            score = float(g.get("score", 0.5))
        except (TypeError, ValueError):
            score = 0.5
        score = max(0.0, min(1.0, score))
        validated.append({
            "leaf_id": lid,
            "score": score,
            "reasoning": str(g.get("reasoning", "")).strip(),
        })
    return validated


def _format_leaves_for_prompt(leaves: list[dict[str, Any]]) -> str:
    lines = []
    for lf in leaves:
        lines.append(f"  - id: {lf['id']}")
        lines.append(f"    category: {lf.get('task_category', '')}")
        lines.append(f"    requirements: {lf.get('requirements', '')}")
    return "\n".join(lines)


def _format_manifest_context(manifest: dict[str, Any]) -> str:
    """Compact manifest summary for LLM prompts.

    Includes the research question, hypotheses, expected conditions, metrics
    and datasets so the LLM understands what a correct submission looks like
    before reading the rubric leaves and artifacts.
    """
    tid = manifest.get("id", "?")
    title = manifest.get("title", "")
    ed = manifest.get("experiment_design") or {}
    research_q = ed.get("research_question", manifest.get("synthesis", ""))[:400]
    conditions = [c.get("name", "") for c in (ed.get("conditions") or [])]
    metrics = [m.get("name", "") for m in (ed.get("metrics") or [])]
    datasets = [d.get("name", "?") for d in (ed.get("datasets") or [])]
    hypotheses = manifest.get("hypotheses") or []

    lines = [
        f"Topic {tid}: {title}",
        f"Research question: {research_q}",
        f"Expected conditions: {', '.join(conditions) if conditions else '(see rubric)'}",
        f"Expected metrics:    {', '.join(metrics) if metrics else '(see rubric)'}",
        f"Datasets:            {', '.join(datasets) if datasets else '(see rubric)'}",
        "Hypotheses to evaluate:",
    ]
    for h in hypotheses:
        lines.append(f"  {h.get('id', '?')}: {h.get('statement', '')}")
    return "\n".join(lines)


def run_llm_judge(
    run_dir: Path,
    submission_dir: Path,
    manifest: dict[str, Any],
    rubric: dict[str, Any],
    *,
    debug: bool = False,
    results_only: bool = False,
) -> dict[str, Any]:
    """LLM judge with two evaluation modes.

    Default (results_only=False):
      Round 1 — code → Code Development leaves.
      Round 2 — summary + writeup → Execution + Result Analysis leaves.

    results_only=True:
      Single round — summary + writeup only, ALL leaves graded from results.
      Code is not fetched.  Avoids truncation problems with multi-file packages
      and is the recommended mode until code-round truncation is solved.

    debug=True writes judge_debug.json next to judge_result.json:
      artifact paths, first-100-char previews, leaf grades — NO full prompts.
    """
    topic_id = manifest["id"]
    manifest_ctx = _format_manifest_context(manifest)
    all_leaves = list(_iter_leaves(rubric))

    # Discover results artifacts (always needed)
    summary_dict, summary_label = _find_experiment_summary(run_dir)
    writeup_text, writeup_label = _find_writeup(run_dir)
    has_summary = summary_dict is not None
    has_writeup = writeup_text is not None

    # Code only fetched when not results_only
    code_text: str | None = None
    code_label: str = ""
    if not results_only:
        code_text, code_label = _find_primary_code(run_dir)
    has_code = code_text is not None

    # ---- debug record: paths as top-level fields, 500-char previews -----
    debug_log: dict[str, Any] = {
        "topic_id": topic_id,
        "mode": "results_only" if results_only else "full",
        "resolved_run_dir": str(run_dir),
        # File paths as flat top-level fields for easy tracing
        "summary_path": summary_label,
        "writeup_path": writeup_label,
        "code_path": code_label if not results_only else "(skipped — results_only)",
        # 500-char previews of what was actually injected into the prompt
        "summary_chars": len(json.dumps(summary_dict)) if summary_dict else 0,
        "summary_preview_500": json.dumps(summary_dict)[:500] if summary_dict else "",
        "summary_condition_keys": list(
            (summary_dict.get("condition_summaries") or {}).keys()
        ) if summary_dict else [],
        "writeup_chars": len(writeup_text) if writeup_text else 0,
        "writeup_preview_500": (writeup_text or "")[:500],
        "leaf_grades": [],
    }

    artifacts = {
        "has_code": has_code,
        "code_path": code_label,
        "has_summary": has_summary,
        "experiment_summary_path": summary_label,
        "has_writeup": has_writeup,
        "writeup_path": writeup_label,
    }

    client = _build_llm_client()
    grade_map: dict[str, dict[str, Any]] = {}

    # ----------------------------------------------------------------
    # Shared results snippets (used in Round 2 and results_only round)
    # ----------------------------------------------------------------
    summary_snippet = "(no experiment_summary.json found)"
    if has_summary:
        summary_snippet = _truncate(json.dumps(summary_dict, indent=2), _SUMMARY_CAP)

    writeup_snippet = "(no writeup found)"
    if has_writeup:
        writeup_snippet = _truncate(writeup_text, _WRITEUP_CAP)

    if results_only:
        # ----------------------------------------------------------------
        # RESULTS-ONLY: Code Development leaves are SKIPPED entirely.
        # Only Code Execution + Result Analysis leaves are graded,
        # using experiment_summary + writeup as the sole evidence.
        # ----------------------------------------------------------------
        exec_result_leaves = [
            lf for lf in all_leaves
            if not (lf.get("task_category") or "").lower().startswith("code dev")
        ]
        skipped_leaves = [
            lf for lf in all_leaves
            if (lf.get("task_category") or "").lower().startswith("code dev")
        ]

        exec_leaf_ids = {lf["id"] for lf in exec_result_leaves}
        leaves_desc = _format_leaves_for_prompt(exec_result_leaves)
        prompt = (
            f"## Topic Context\n{manifest_ctx}\n\n"
            f"## Rubric leaves to grade (Code Execution + Result Analysis only)\n"
            f"{leaves_desc}\n\n"
            f"## Experiment Summary\n"
            f"  path: {summary_label}\n"
            f"```json\n{summary_snippet}\n```\n\n"
            f"## Writeup / README\n"
            f"  path: {writeup_label}\n"
            f"{writeup_snippet}\n\n"
            "Grade each rubric leaf above based solely on the experiment summary "
            "and writeup. For hypothesis leaves verify numeric thresholds against "
            "what the hypothesis states. Return JSON with a 'grades' array."
        )

        debug_log["prompt_info"] = {
            "summary_injected_path": summary_label,
            "summary_injected_preview_500": summary_snippet[:500],
            "writeup_injected_path": writeup_label,
            "writeup_injected_preview_500": writeup_snippet[:500],
            "prompt_preview_500": prompt[:500],
            "leaves_graded": [lf["id"] for lf in exec_result_leaves],
            "leaves_skipped_code_dev": [lf["id"] for lf in skipped_leaves],
        }

        _max_tok = max(8192, len(exec_result_leaves) * 600)
        grades = _call_llm_round(client, prompt, exec_leaf_ids, max_tokens=_max_tok)
        scored_ids = {g["leaf_id"] for g in grades}
        for g in grades:
            grade_map[g["leaf_id"]] = g
        for lf in exec_result_leaves:
            if lf["id"] not in scored_ids:
                warnings.warn(
                    f"[judge] LLM did not grade leaf {lf['id']}; defaulting to 0.5")
                grade_map[lf["id"]] = {
                    "leaf_id": lf["id"],
                    "score": 0.5,
                    "reasoning": "(ungraded — LLM did not return a score)",
                }

    else:
        # ----------------------------------------------------------------
        # Round 1: CODE → Code Development leaves
        # ----------------------------------------------------------------
        code_leaves = [lf for lf in all_leaves
                       if (lf.get("task_category") or "").lower().startswith("code dev")]
        exec_result_leaves = [lf for lf in all_leaves if lf not in code_leaves]

        if code_leaves:
            code_leaf_ids = {lf["id"] for lf in code_leaves}
            code_snippet = (
                _truncate(code_text, _CODE_CAP) if has_code
                else "(no experiment code found in this submission)"
            )
            leaves_desc = _format_leaves_for_prompt(code_leaves)
            prompt_r1 = (
                f"## Topic Context\n{manifest_ctx}\n\n"
                f"## Rubric leaves to grade (Code Development)\n{leaves_desc}\n\n"
                f"## Experiment Code ({code_label})\n```python\n{code_snippet}\n```\n\n"
                "Grade each rubric leaf above based solely on the code provided. "
                "Use the topic context to understand expected conditions, datasets and "
                "metrics. Return JSON with a 'grades' array."
            )
            r1_grades = _call_llm_round(client, prompt_r1, code_leaf_ids)
            scored_ids = {g["leaf_id"] for g in r1_grades}
            for g in r1_grades:
                grade_map[g["leaf_id"]] = g
            for lf in code_leaves:
                if lf["id"] not in scored_ids:
                    warnings.warn(
                        f"[judge] LLM did not grade leaf {lf['id']} in Round 1; defaulting to 0.5")
                    grade_map[lf["id"]] = {
                        "leaf_id": lf["id"],
                        "score": 0.5,
                        "reasoning": "(ungraded — LLM did not return a score for this leaf)",
                    }

        # ----------------------------------------------------------------
        # Round 2: RESULTS + WRITEUP → Execution + Result Analysis leaves
        # ----------------------------------------------------------------
        exec_result_leaves = [lf for lf in all_leaves
                              if lf not in (code_leaves if code_leaves else [])]
        if exec_result_leaves:
            exec_leaf_ids = {lf["id"] for lf in exec_result_leaves}
            leaves_desc = _format_leaves_for_prompt(exec_result_leaves)
            prompt_r2 = (
                f"## Topic Context\n{manifest_ctx}\n\n"
                f"## Rubric leaves to grade (Code Execution + Result Analysis)\n{leaves_desc}\n\n"
                f"## Experiment Summary ({summary_label})\n```json\n{summary_snippet}\n```\n\n"
                f"## Writeup / README ({writeup_label})\n{writeup_snippet}\n\n"
                "Grade each rubric leaf above based on the experiment summary and writeup. "
                "For hypothesis leaves verify numeric thresholds from the summary. "
                "Return JSON with a 'grades' array."
            )
            r2_grades = _call_llm_round(client, prompt_r2, exec_leaf_ids)
            scored_ids = {g["leaf_id"] for g in r2_grades}
            for g in r2_grades:
                grade_map[g["leaf_id"]] = g
            for lf in exec_result_leaves:
                if lf["id"] not in scored_ids:
                    warnings.warn(
                        f"[judge] LLM did not grade leaf {lf['id']} in Round 2; defaulting to 0.5")
                    grade_map[lf["id"]] = {
                        "leaf_id": lf["id"],
                        "score": 0.5,
                        "reasoning": "(ungraded — LLM did not return a score for this leaf)",
                    }

    # ----------------------------------------------------------------
    # Score aggregation — Code Dev leaves excluded from score in results_only
    # ----------------------------------------------------------------
    leaf_grades: list[dict[str, Any]] = []
    total_weight = 0.0
    weighted_sum = 0.0
    for lf in all_leaves:
        is_code_dev = (lf.get("task_category") or "").lower().startswith("code dev")
        if results_only and is_code_dev:
            # Record leaf as skipped, not counted in score
            leaf_grades.append({
                "id": lf["id"],
                "category": lf.get("task_category", ""),
                "weight": float(lf.get("weight", 1) or 1),
                "score": None,
                "reasoning": "(skipped — results_only mode does not evaluate code)",
            })
            continue
        weight = float(lf.get("weight", 1) or 1)
        gd = grade_map.get(lf["id"], {})
        score = float(gd.get("score", 0.5))
        score = max(0.0, min(1.0, score))
        reasoning = gd.get("reasoning", "(ungraded)")
        leaf_grades.append({
            "id": lf["id"],
            "category": lf.get("task_category", ""),
            "weight": weight,
            "score": score,
            "reasoning": reasoning,
        })
        total_weight += weight
        weighted_sum += weight * score

    overall = weighted_sum / total_weight if total_weight else 0.0

    if debug:
        debug_log["leaf_grades"] = [
            {
                "id": g["id"],
                "score": g["score"],
                "reasoning": (g["reasoning"] or "")[:120],
            }
            for g in leaf_grades
        ]
        debug_path = run_dir / "judge_debug.json"
        debug_path.write_text(json.dumps(debug_log, indent=2, ensure_ascii=False),
                              encoding="utf-8")
        print(f"  [judge] debug → {debug_path}")

    return {
        "backend": "llm",
        "mode": "results_only" if results_only else "full",
        "topic_id": topic_id,
        "summary_path": summary_label,
        "writeup_path": writeup_label,
        "code_path": code_label if not results_only else "(skipped — results_only)",
        "artifacts": artifacts,
        "leaf_grades": leaf_grades,
        "overall_score": overall,
    }


# ---------------------------------------------------------------------------
# Local (heuristic) backend — kept for offline / CI use
# ---------------------------------------------------------------------------

def _submission_text(submission_dir: Path) -> str:
    parts: list[str] = []
    for p in submission_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in {".md", ".py", ".json", ".txt", ".log"}:
            continue
        try:
            parts.append(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
    return "\n".join(parts).lower()


def _keyword_hits(requirement: str, haystack: str) -> int:
    # Extract quoted identifiers + CamelCase/snake_case tokens as anchors.
    anchors = re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", requirement)
    # Drop common English words; keep the technical-looking ones.
    stop = {
        "the", "a", "an", "and", "or", "of", "for", "with", "without", "each",
        "has", "have", "been", "are", "that", "this", "those", "these", "least",
        "most", "more", "less", "implements", "implementation", "implemented",
        "reports", "report", "produces", "produced", "produce", "include",
        "includes", "including", "either", "across", "over", "multiple", "pair",
        "pairs", "one", "two", "three", "condition", "conditions", "dataset",
        "datasets", "dataset", "metric", "metrics", "metric", "result",
        "results", "submission", "submissions", "number", "numbers", "value",
        "values",
    }
    hits = 0
    for a in anchors:
        al = a.lower()
        if al in stop or len(al) < 4:
            continue
        if al in haystack:
            hits += 1
    return hits


def _score_rubric(submission_dir: Path, rubric: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    """Heuristic per-leaf scoring based on keyword overlap.

    NOT a replacement for SimpleJudge — only a deterministic signal that
    lets ``evaluate.py`` compare runs without burning LLM tokens. A leaf
    is scored 1.0 if ≥5 anchor keywords appear, 0.5 if 2-4 appear, else 0.
    The old ≥3 threshold saturated at ~1.000 across all rc_full runs
    (keyword-dense writeups always exceeded it); ≥5 restores headroom.
    """
    text = _submission_text(submission_dir)
    leaves = list(_iter_leaves(rubric))
    details: list[dict[str, Any]] = []
    total_weight = 0.0
    weighted_sum = 0.0
    for leaf in leaves:
        weight = float(leaf.get("weight", 1) or 1)
        hits = _keyword_hits(leaf.get("requirements", ""), text)
        if hits >= 5:
            score = 1.0
        elif hits >= 2:
            score = 0.5
        else:
            score = 0.0
        details.append({
            "id": leaf.get("id"),
            "category": leaf.get("task_category"),
            "weight": weight,
            "hits": hits,
            "score": score,
        })
        total_weight += weight
        weighted_sum += weight * score
    overall = weighted_sum / total_weight if total_weight else 0.0
    return overall, details


def _locate_experiment_summary(run_dir: Path, topic_id: str) -> Path | None:
    """Find stage-14/experiment_summary.json either in-place or in the log archive.

    Judge is normally called before archive-and-trim, so stage-14 lives at
    ``run_dir/stage-14/``. If a re-judge happens after trim, we fall back to
    the archived copy under ``log/<mode>/<topic>/<run>/full_run/``.
    """
    primary = run_dir / "stage-14" / "experiment_summary.json"
    if primary.is_file():
        return primary
    any_stage = sorted(run_dir.glob("stage-14*/experiment_summary.json"))
    if any_stage:
        return any_stage[-1]
    log_root = run_dir.parents[3] / "log" if len(run_dir.parents) >= 4 else None
    if log_root and log_root.is_dir():
        cand = sorted(log_root.rglob(
            f"{topic_id}/*/full_run/stage-14/experiment_summary.json"
        ))
        if cand:
            return cand[-1]
    # P0-C fallback: submission/results/metrics.json may embed the
    # experiment_summary under the 'stage-14/experiment_summary.json' key
    # (paperbench_bridge's collect_results() snapshot). Use it when the
    # raw stage-14/ tree isn't available locally (e.g. re-judging an
    # archived submission without the full pipeline workspace).
    sub_metrics = run_dir / "submission" / "results" / "metrics.json"
    if sub_metrics.is_file():
        try:
            blob = json.loads(sub_metrics.read_text())
        except json.JSONDecodeError:
            blob = {}
        inner = blob.get("stage-14/experiment_summary.json") if isinstance(blob, dict) else None
        if isinstance(inner, dict) and inner:
            # Write a sidecar so downstream readers (_correctness_signal)
            # can load it like a normal file. Placed in the submission
            # dir to keep run_dir immutable.
            sidecar = run_dir / "submission" / "results" / "_experiment_summary_from_metrics.json"
            try:
                sidecar.write_text(json.dumps(inner, indent=2))
                return sidecar
            except OSError:
                return None
    return None


def _correctness_signal(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Detect broken experiments from the experiment_summary.json schema.

    Returns a dict with:
      score        — [0, 1], lower = more likely broken
      zero_variance — bool, fires if ablation_warnings flags zero variance
      cond_count   — number of conditions summarised
      primary_std_ratio — std(primary metric) / max|value|, or None
    """
    topic_id = manifest["id"]
    sum_path = _locate_experiment_summary(run_dir, topic_id)
    if sum_path is None:
        return {"score": 0.0, "zero_variance": None, "cond_count": 0,
                "primary_std_ratio": None, "note": "no experiment_summary.json"}
    try:
        summary = json.loads(sum_path.read_text())
    except json.JSONDecodeError:
        return {"score": 0.0, "zero_variance": None, "cond_count": 0,
                "primary_std_ratio": None, "note": "unparseable summary"}

    warnings_list = summary.get("ablation_warnings") or []
    zero_variance = any("zero variance" in str(w).lower() for w in warnings_list)

    # Primary metric from manifest
    metrics = (manifest.get("experiment_design") or {}).get("metrics") or []
    primary_key = metrics[0].get("name") if metrics else None
    cs = summary.get("condition_summaries") or {}
    primary_vals: list[float] = []
    if primary_key:
        # BUG-FIX: Prefer `<primary>_mean` over the single-value
        # `<primary>` field. The single-value field is populated by
        # experiment_repair.py line 841 with the last-seen seed during
        # metric iteration (dict-insertion order artifact), which can
        # collapse to an identical value across conditions when the
        # final dataset/seed pair happens to saturate (e.g. breast_cancer
        # seed=2 hits 0.982 on all 5 dropout variants in T01).
        # `<primary>_mean` is the explicit per-condition seed-averaged
        # value and is the correct signal. Falling back to single-value
        # keeps compatibility with frameworks (e.g. AIS-v2) that don't
        # emit `_mean` fields.
        for cond in cs.values():
            m = (cond or {}).get("metrics") or {}
            for k in (f"{primary_key}_mean", primary_key, primary_key.lower()):
                if k in m and isinstance(m[k], (int, float)):
                    primary_vals.append(float(m[k]))
                    break

    std_ratio: float | None = None
    if len(primary_vals) >= 2:
        import statistics as _st
        mean_val = sum(primary_vals) / len(primary_vals)
        denom = max(abs(mean_val), 1e-9)
        std_ratio = _st.pstdev(primary_vals) / denom

    # Score assembly — start at 1.0 and deduct for detected failures
    score = 1.0
    if len(cs) == 0:
        score -= 0.5
    if zero_variance:
        score -= 0.4
    if primary_vals and std_ratio is not None and std_ratio < 1e-4:
        # Zero variance even if warning wasn't emitted
        score -= 0.3
    if primary_key and not primary_vals:
        # Primary metric never reported — probably wrong experiment
        score -= 0.2
    score = max(0.0, min(1.0, score))

    return {
        "score": score,
        "zero_variance": zero_variance,
        "cond_count": len(cs),
        "primary_key": primary_key,
        "primary_vals": primary_vals,
        "primary_std_ratio": std_ratio,
    }


VERDICT_ALIASES = {
    # canonical: supported
    "supported": "supported",
    "confirmed": "supported",
    "backed": "supported",
    # canonical: refuted (definitive negative)
    "refuted": "refuted",
    "rejected": "refuted",
    "contradicted": "refuted",
    "disproven": "refuted",
    "not_supported": "refuted",
    "unsupported": "refuted",
    "not supported": "refuted",
    # canonical: partially_supported
    "partially_supported": "partially_supported",
    "partially_refuted": "partially_supported",
    "partial": "partially_supported",
    "mixed": "partially_supported",
    # canonical: inconclusive
    "inconclusive": "inconclusive",
    "unclear": "inconclusive",
    "insufficient_evidence": "inconclusive",
    "indeterminate": "inconclusive",
}


def _normalize_verdict(v: str) -> str:
    return VERDICT_ALIASES.get(str(v).strip().lower(), "unknown")


def _verdict_signal(submission_dir: Path) -> dict[str, Any]:
    """Score the claims.json verdict coverage.

    Definitive verdicts (supported / refuted / partially_supported) count
    as 1.0; inconclusive as 0.3; unknown/missing as 0. Final score is the
    mean over claims.

    Verdict strings are normalized via VERDICT_ALIASES so common agent
    synonyms (not_supported, rejected, mixed, ...) are classified
    consistently.
    """
    claims_path = submission_dir / "claims.json"
    if not claims_path.is_file():
        return {"score": 0.0, "claims_total": 0, "definitive": 0,
                "note": "no claims.json"}
    try:
        blob = json.loads(claims_path.read_text())
    except json.JSONDecodeError:
        return {"score": 0.0, "claims_total": 0, "definitive": 0,
                "note": "unparseable claims.json"}
    claims = blob.get("claims") or []
    if not claims:
        return {"score": 0.0, "claims_total": 0, "definitive": 0}
    definitive = {"supported", "refuted", "partially_supported"}
    total_score = 0.0
    n_def = 0
    raw_verdicts: list[str] = []
    normalized: list[str] = []
    for c in claims:
        raw = str(c.get("verdict", "")).strip().lower()
        raw_verdicts.append(raw)
        v = _normalize_verdict(raw)
        normalized.append(v)
        if v in definitive:
            total_score += 1.0
            n_def += 1
        elif v == "inconclusive":
            total_score += 0.3
    return {
        "score": total_score / len(claims),
        "claims_total": len(claims),
        "definitive": n_def,
        "raw_verdicts": raw_verdicts,
        "normalized_verdicts": normalized,
    }


def run_local_judge(run_dir: Path, submission_dir: Path,
                    manifest: dict[str, Any],
                    rubric: dict[str, Any]) -> dict[str, Any]:
    code_dir = submission_dir / "code"
    has_code = any(p.is_file() and p.stat().st_size > 0
                   for p in code_dir.rglob("*.py"))

    metrics_path = submission_dir / "results" / "metrics.json"
    metrics_blob = ""
    has_results = False
    if metrics_path.is_file():
        try:
            data = json.loads(metrics_path.read_text())
            has_results = bool(data)
            metrics_blob = json.dumps(data).lower()
        except json.JSONDecodeError:
            pass

    readme = submission_dir / "README.md"
    has_writeup = (
        readme.is_file()
        and "agent-produced writeup" in readme.read_text().lower()
    )
    expected = [m.get("name", "") for m in
                (manifest.get("experiment_design") or {}).get("metrics") or []]
    claims_cover = (
        sum(1 for n in expected if n and n.lower() in metrics_blob) / len(expected)
    ) if expected else 0.0

    rubric_score, leaf_details = _score_rubric(submission_dir, rubric)

    booleans = {
        "has_code":     1.0 if has_code else 0.0,
        "has_results":  1.0 if has_results else 0.0,
        "has_writeup":  1.0 if has_writeup else 0.0,
        "claims_cover": claims_cover,
    }
    heuristic_mean = sum(booleans.values()) / len(booleans)

    # Correctness + verdict signals — the new discriminators
    correctness = _correctness_signal(run_dir, manifest)
    verdicts = _verdict_signal(submission_dir)

    # Weighted blend — rebalanced after the rc_full sweep saturated the
    # keyword rubric (mean 0.998 across 25 topics). Verdict coverage is the
    # only signal that actually measures "did the experiment answer its
    # hypothesis", so it now carries 0.30. Correctness catches zero-variance
    # and no-condition failures. Rubric keeps a small weight as a sanity
    # check but no longer dominates.
    overall = (
        0.25 * heuristic_mean
        + 0.20 * rubric_score
        + 0.25 * correctness["score"]
        + 0.30 * verdicts["score"]
    )

    return {
        "backend": "local",
        "topic_id": manifest["id"],
        "booleans": booleans,
        "heuristic_mean": heuristic_mean,
        "rubric_weighted": rubric_score,
        "rubric_leaves": leaf_details,
        "correctness": correctness,
        "verdicts": verdicts,
        "overall_score": overall,
    }


# ---------------------------------------------------------------------------
# Archive resolution
# ---------------------------------------------------------------------------

def _resolve_live_or_archive(run_dir: Path, topic_id: str) -> Path:
    """If run_dir is trimmed (no stage-14/), prefer the archive full_run.

    Avoids re-running build_submission on a trimmed directory, which would
    overwrite submission/results/metrics.json with ``{}`` and falsely drop
    the ``has_results`` boolean.
    """
    if (run_dir / "stage-14").is_dir():
        return run_dir
    # run_dir looks like .../results/<mode>/<topic>/<run_id>/
    try:
        mode = run_dir.parents[1].name
        run_id = run_dir.name
        archive = ROOT / "log" / mode / topic_id / run_id / "full_run"
        if archive.is_dir():
            print(f"  [judge] run_dir trimmed; judging against archive {archive}")
            return archive
    except IndexError:
        pass
    return run_dir


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def grade(run_dir: Path, topic_id: str, *, backend: str = "llm",
          debug: bool = False, results_only: bool = True) -> dict[str, Any]:
    manifest = load_manifest(topic_id)
    rubric = load_rubric(topic_id)
    original_run_dir = run_dir
    run_dir = _resolve_live_or_archive(run_dir, topic_id)
    submission_dir = run_dir / "submission"
    # build_submission is idempotent and preserves a finalize-produced README.
    build_submission(run_dir, submission_dir, manifest)

    if backend == "local":
        result = run_local_judge(run_dir, submission_dir, manifest, rubric)
    elif backend == "llm":
        result = run_llm_judge(run_dir, submission_dir, manifest, rubric,
                               debug=debug, results_only=results_only)
    else:
        raise ValueError(f"Unknown backend: {backend!r}. Choose 'llm' or 'local'.")

    result_path = run_dir / "judge_result.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    # Mirror judge_result and judge_debug to the original (live) run_dir so
    # results/ always has the latest scores even when we fell back to the archive.
    if original_run_dir != run_dir:
        try:
            (original_run_dir / "judge_result.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
        except OSError:
            pass
        if debug:
            src = run_dir / "judge_debug.json"
            dst = original_run_dir / "judge_debug.json"
            if src.is_file():
                try:
                    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                except OSError:
                    pass

    # Print summary line
    if backend == "llm":
        n_leaves = len(result.get("leaf_grades", []))
        print(f"  {topic_id}: overall={result['overall_score']:.3f} "
              f"(llm, {n_leaves} leaves)")
    else:
        print(f"  {topic_id}: overall={result['overall_score']:.3f} "
              f"(rubric={result['rubric_weighted']:.3f}, "
              f"heur={result['heuristic_mean']:.3f})")

    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Grade an ARC-Bench submission")
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--backend", choices=["llm", "local"], default="llm")
    ap.add_argument("--debug", action="store_true",
                    help="Save artifact paths + leaf grades to judge_debug.json")
    ap.add_argument("--results-only", action="store_true", default=True,
                    help="Grade all leaves from summary+writeup only (no code; default on)")
    ap.add_argument("--full", action="store_true",
                    help="Use two-round mode: code round + results round")
    args = ap.parse_args()
    results_only = not args.full  # --full overrides the default results-only
    grade(args.run_dir, args.topic, backend=args.backend,
          debug=args.debug, results_only=results_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
