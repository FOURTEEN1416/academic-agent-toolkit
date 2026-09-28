#!/usr/bin/env python3
"""ARC-Bench manual-judge driver.

Wraps the ``manual_strict_audit_prompt.md`` workflow for any single
(framework × topic) cell. Three modes:

* ``--dispatch claude`` — prints the fully-resolved prompt + paths so a
  Claude Code subagent (or any LLM agent) can execute the audit. Does
  NOT call the LLM itself; the operator pipes the output to a chat
  client or pastes it into a subagent dispatch tool.
* ``--dispatch codex`` — same prompt, but formatted as a system+user pair
  for the Codex CLI.
* ``--dispatch human`` — produces a checklist .md + a blank judge
  template the human reviewer fills in.

In all three modes the OUTPUT location is the same:
``results/legacy/judges_T??_T??/<framework>_<topic>_strict.json`` (matches
the canonical evidence layout under ``results/legacy/``).

Usage:
    python scripts/judge_manual.py \\
        --framework rc_full --topic T01 --dispatch claude

    python scripts/judge_manual.py \\
        --framework aide_ml --topic T17 --dispatch human
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
RESULTS_DIR = ROOT / "results"
LEGACY_JUDGES_T05 = ROOT / "results" / "legacy" / "judges_T01_T05"
LEGACY_JUDGES_T25 = ROOT / "results" / "legacy" / "judges_T06_T25"
PROMPT_PATH = ROOT / "scripts" / "prompts" / "manual_strict_audit_prompt.md"


def _topic_int(topic: str) -> int:
    return int(topic[1:])


def _judges_dir(topic: str) -> Path:
    return LEGACY_JUDGES_T05 if _topic_int(topic) <= 5 else LEGACY_JUDGES_T25


def _latest_run_dir(framework: str, topic: str) -> Path | None:
    base = RESULTS_DIR / framework / topic
    if not base.is_dir():
        return None
    runs = sorted([p for p in base.iterdir() if p.is_dir()])
    return runs[-1] if runs else None


def _build_paths_section(framework: str, topic: str) -> dict[str, str]:
    return {
        "rubric": str(CONFIG_DIR / "rubrics" / f"{topic}.json"),
        "manifest": str(CONFIG_DIR / "manifests" / f"{topic}.yaml"),
        "run_dir": str(_latest_run_dir(framework, topic) or "(NO RUN — verify results/{framework}/{topic} exists)"),
        "output_judge": str(_judges_dir(topic) / f"{framework}_{topic}_strict.json"),
        "reference_judges_dir": str(_judges_dir(topic)),
    }


def render_dispatch(framework: str, topic: str, dispatch: str) -> str:
    paths = _build_paths_section(framework, topic)
    prompt_body = PROMPT_PATH.read_text(encoding="utf-8")

    paths_md = "\n".join(f"- **{k}**: `{v}`" for k, v in paths.items())
    header = (
        f"# Strict manual audit dispatch: {framework} × {topic}\n\n"
        f"## Files for this cell\n\n{paths_md}\n\n"
        f"## Output\n\nWrite the resulting JSON to:\n`{paths['output_judge']}`\n\n"
        "---\n\n"
    )

    if dispatch == "claude":
        return header + prompt_body
    elif dispatch == "codex":
        # Same content, just labeled with role headers for Codex CLI use.
        return (
            "[SYSTEM]\n" + prompt_body + "\n\n[USER]\n" + header
        )
    elif dispatch == "human":
        # Produce a stripped-down checklist + a blank judge template.
        rubric = json.load(open(paths["rubric"]))
        leaves = []
        def walk(node):
            if not node.get("sub_tasks"):
                leaves.append(node)
            else:
                for s in node["sub_tasks"]:
                    walk(s)
        walk(rubric)
        template_grades = [
            {
                "id": L["id"],
                "category": L.get("task_category"),
                "weight": L["weight"],
                "score": None,
                "reasoning": "TODO: 50-200 words citing files/lines/numbers"
            }
            for L in leaves
        ]
        template = {
            "backend": "manual_strict",
            "judged_by": "human:<your-name>",
            "topic_id": topic,
            "framework": framework,
            "run_dir": paths["run_dir"],
            "scoring_methodology": "Each leaf scored 0.0-1.0 against rubric requirements PLUS strict additions: (1) implementation correctness verified by reading the actual code, not just claims; (2) writeup numbers cross-checked against captured experiment_summary or log artifacts — fabricated numbers severely penalize the relevant H-leaf and the writeup leaf; (3) verdict-data consistency required — claimed support of H must be backed by measured evidence; (4) coverage gaps (missing conditions/datasets/seeds) penalize exec leaves even if partial cells are correct.",
            "leaf_grades": template_grades,
            "scoring_summary": {
                "category_normalized": {"Code Development": None, "Code Execution": None, "Result Analysis": None},
                "category_weights": {"Code Development": 25.0, "Code Execution": 25.0, "Result Analysis": 50.0},
                "overall_strict": None,
                "results_only": None,
                "weighting_scheme": "CD:CE:RA = 25:25:50",
                "timeout_zero_exec_applied": False
            },
            "notes": ""
        }
        return (
            header
            + "## Reviewer checklist (read in order)\n\n"
            + "1. Read this prompt:\n```\n" + prompt_body[:1000] + "\n... (full text in scripts/prompts/manual_strict_audit_prompt.md)\n```\n"
            + "2. Read the rubric, manifest, run dir, and reference judges (paths above).\n"
            + "3. Apply the four strict criteria leaf-by-leaf.\n"
            + "4. Fill in the JSON template below; write to `output_judge` path.\n\n"
            + "## JSON template (fill in scores + reasoning)\n\n```json\n"
            + json.dumps(template, indent=2)
            + "\n```\n"
        )
    raise SystemExit(f"unknown --dispatch: {dispatch}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--framework", required=True,
                    choices=["rc_full", "rc_copilot", "ais_v2", "agent_lab", "aide_ml"])
    ap.add_argument("--topic", required=True, help="e.g. T01")
    ap.add_argument("--dispatch", required=True,
                    choices=["claude", "codex", "human"])
    args = ap.parse_args()
    print(render_dispatch(args.framework, args.topic, args.dispatch))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
