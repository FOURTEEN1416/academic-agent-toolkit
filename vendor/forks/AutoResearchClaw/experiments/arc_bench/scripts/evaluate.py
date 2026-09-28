#!/usr/bin/env python3
"""Aggregate ARC-Bench scores across modes × topics × frameworks.

Reads:
  results/<mode>/<topic>/<run>/judge_result.json           (autoclaw)
  results_baseline/<framework>/<topic>/<run>/judge_result.json  (baselines)

Produces:
  analysis/arc_bench_scores.md        — markdown scoreboard
  analysis/arc_bench_scores.json      — machine-readable aggregate

For autoclaw cells we ALSO compute the copilot-gain = copilot − full_auto
per topic, sorted by absolute gain so it's easy to see where the HITL
suggestor moved the needle.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
# After 2026-05-02 restructure all baselines live under results/ — keep
# BASELINE for backwards-compat reads of any legacy results_baseline/ tree.
BASELINE = RESULTS
ANALYSIS = ROOT / "analysis"


def _load_latest(run_root: Path) -> dict | None:
    if not run_root.is_dir():
        return None
    runs = sorted(run_root.iterdir())
    if not runs:
        return None
    jr = runs[-1] / "judge_result.json"
    if not jr.is_file():
        return None
    try:
        return json.loads(jr.read_text())
    except json.JSONDecodeError:
        return None


def _topics_with_manifest() -> list[str]:
    return sorted(p.stem for p in (ROOT / "manifests").glob("T*.yaml"))


def _collect() -> dict:
    topics = _topics_with_manifest()
    out = {
        "topics": topics,
        "autoclaw": {},     # mode → topic → judge
        "baselines": {},    # framework → topic → judge
    }
    for mode in ("rc_full", "rc_copilot"):
        out["autoclaw"].setdefault(mode, {})
        for t in topics:
            judge = _load_latest(RESULTS / mode / t)
            if judge is not None:
                out["autoclaw"][mode][t] = judge
    if BASELINE.is_dir():
        for fw_dir in BASELINE.iterdir():
            if not fw_dir.is_dir():
                continue
            out["baselines"].setdefault(fw_dir.name, {})
            for t in topics:
                judge = _load_latest(fw_dir / t)
                if judge is not None:
                    out["baselines"][fw_dir.name][t] = judge
    return out


def _overall(judge: dict | None) -> float | None:
    if judge is None:
        return None
    return float(judge.get("overall_score", 0.0))


def _format_scoreboard(data: dict) -> str:
    topics = data["topics"]
    modes = sorted(data["autoclaw"].keys())
    frameworks = sorted(data["baselines"].keys())
    cols = modes + frameworks

    # Per-topic table
    header = ["Topic"] + cols
    lines = ["# ARC-Bench scoreboard", "", "## Per-topic", "",
             "| " + " | ".join(header) + " |",
             "|" + "|".join(["---"] * len(header)) + "|"]
    for t in topics:
        row = [t]
        for mode in modes:
            s = _overall(data["autoclaw"][mode].get(t))
            row.append(f"{s:.3f}" if s is not None else "—")
        for fw in frameworks:
            s = _overall(data["baselines"].get(fw, {}).get(t))
            row.append(f"{s:.3f}" if s is not None else "—")
        lines.append("| " + " | ".join(row) + " |")

    # Aggregates
    def _avg(d: dict[str, dict]) -> float | None:
        vals = [_overall(v) for v in d.values() if _overall(v) is not None]
        return statistics.mean(vals) if vals else None

    lines += ["", "## Aggregate (mean overall_score across topics)", "",
              "| Cell | Mean | #topics |", "|---|---:|---:|"]
    for mode in modes:
        avg = _avg(data["autoclaw"][mode])
        n = len([v for v in data["autoclaw"][mode].values()
                 if _overall(v) is not None])
        lines.append(
            f"| autoclaw.{mode} | {avg:.3f} | {n} |"
            if avg is not None else f"| autoclaw.{mode} | — | {n} |"
        )
    # rc_copilot_guarded — reflects the realistic HITL practice of rolling
    # back an intervention that regresses vs full-auto by more than 0.05.
    # This is a per-topic max(rc_full, rc_copilot) with a regression
    # threshold; the user would keep the full-auto result in that case.
    if "rc_full" in data["autoclaw"] and "rc_copilot" in data["autoclaw"]:
        guarded_vals = []
        regressions = 0
        for t in topics:
            f = _overall(data["autoclaw"]["rc_full"].get(t))
            c = _overall(data["autoclaw"]["rc_copilot"].get(t))
            if f is None and c is None:
                continue
            if f is None:
                guarded_vals.append(c)
            elif c is None:
                guarded_vals.append(f)
            elif c < f - 0.05:
                guarded_vals.append(f)  # rollback
                regressions += 1
            else:
                guarded_vals.append(c)
        if guarded_vals:
            avg_g = statistics.mean(guarded_vals)
            lines.append(
                f"| autoclaw.rc_copilot_guarded | {avg_g:.3f} | "
                f"{len(guarded_vals)} (rolled back {regressions}) |"
            )
    for fw in frameworks:
        d = data["baselines"].get(fw, {})
        avg = _avg(d)
        n = len([v for v in d.values() if _overall(v) is not None])
        lines.append(
            f"| baseline.{fw} | {avg:.3f} | {n} |"
            if avg is not None else f"| baseline.{fw} | — | {n} |"
        )

    # Copilot gain per topic
    if "rc_full" in data["autoclaw"] and "rc_copilot" in data["autoclaw"]:
        gains = []
        for t in topics:
            f = _overall(data["autoclaw"]["rc_full"].get(t))
            c = _overall(data["autoclaw"]["rc_copilot"].get(t))
            if f is not None and c is not None:
                gains.append((t, c - f, f, c))
        gains.sort(key=lambda x: -abs(x[1]))
        if gains:
            lines += ["", "## Copilot gain (copilot − full_auto)", "",
                      "| Topic | full_auto | copilot | Δ |",
                      "|---|---:|---:|---:|"]
            for t, d, f, c in gains:
                lines.append(f"| {t} | {f:.3f} | {c:.3f} | {d:+.3f} |")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Aggregate ARC-Bench scores")
    ap.add_argument("--out", type=Path, default=ANALYSIS / "arc_bench_scores.md")
    args = ap.parse_args()
    ANALYSIS.mkdir(parents=True, exist_ok=True)

    data = _collect()
    md = _format_scoreboard(data)
    args.out.write_text(md, encoding="utf-8")
    (args.out.with_suffix(".json")).write_text(
        json.dumps(data, indent=2, default=str), encoding="utf-8"
    )
    print(md)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
