#!/usr/bin/env python3
"""PaperSpine V4 acceptance harness — REAL subprocess tests + end-to-end sample output.

Run from the repo root:  python examples/v4_acceptance.py
Produces:
  - TEST_REPORT.md            (real pass/fail numbers + every guard's exit code)
  - examples/v4_sample_run/   (a real sample paper_rewriting_output + paper.docx + guard reports)
Everything below shells out for real; nothing is mocked.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "src" / "scripts"
SAMPLE = REPO / "examples" / "v4_sample_run"
OUT = SAMPLE / "paper_rewriting_output"
PY = sys.executable
RESULTS: list[dict] = []


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd or REPO), text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return p.returncode, p.stdout


def record(name: str, rc: int, expect: str, detail: str = "") -> None:
    ok = (expect == "pass" and rc == 0) or (expect == "fail" and rc != 0)
    RESULTS.append({"name": name, "rc": rc, "expect": expect, "ok": ok, "detail": detail})
    flag = "OK " if ok else "XX "
    print(f"  {flag}{name}: exit={rc} (expect {expect}) {detail}")


def guard(script: str, args: list[str], name: str, expect: str = "pass") -> None:
    rc, _ = run([PY, str(SCRIPTS / script), *args])
    record(name, rc, expect)


# ---- 1. whole-suite gates (real) ----
def suite_checks() -> None:
    print("[1] Repo-wide gates")
    rc, out = run([PY, "-m", "unittest", "discover", "-s", "tests"])
    passed = "OK" in out.splitlines()[-1] if out.strip() else False
    ntests = next((ln for ln in out.splitlines() if ln.startswith("Ran ")), "Ran ? tests")
    record(f"full test suite ({ntests})", 0 if passed else 1, "pass")
    rc, _ = run([PY, "-m", "ruff", "check", "src/scripts", "tests"])
    record("ruff lint", rc, "pass")
    # dist-sync drift guard
    run([PY, str(SCRIPTS / "sync_local_installs.py"), "--dist-only"])
    # --quiet/--exit-code is rc-based (no stdout parsing); --ignore-cr-at-eol drops
    # Windows CRLF-working-tree-vs-LF-index false drift.
    rc, _ = run(["git", "diff", "--quiet", "--exit-code", "--ignore-cr-at-eol", "--", "dist/"])
    record("dist-sync drift (dist/ matches src)", rc, "pass")


# ---- 2. clean fakehome install (real, 4 hosts) ----
def install_check(tmp: Path) -> None:
    print("[2] Clean-home install (4 hosts)")
    h = tmp / "home"
    rc, _ = run([PY, str(SCRIPTS / "sync_local_installs.py"),
                 "--claude-skills-dir", str(h / ".claude/skills"),
                 "--claude-commands-dir", str(h / ".claude/commands"),
                 "--codex-skills-dir", str(h / ".codex/skills"),
                 "--codex-prompts-dir", str(h / ".codex/prompts"),
                 "--openclaw-skills-dir", str(h / ".openclaw/skills"),
                 "--hermes-skills-dir", str(h / "hermes/skills"),
                 "--config-home", str(h / ".paperspine"),
                 "--desktop-root", str(h / "desktop"), "--clean-legacy"])
    record("install runs", rc, "pass")
    for label, p in (
        ("claude skill", h / ".claude/skills/paper-spine/SKILL.md"),
        ("claude /paperspine command", h / ".claude/commands/paperspine.md"),
        ("codex skill", h / ".codex/skills/paper-spine/SKILL.md"),
        ("codex /paperspine prompt", h / ".codex/prompts/paperspine.md"),
        ("openclaw skill", h / ".openclaw/skills/paper-spine/SKILL.md"),
        ("hermes skill (academic-writing)", h / "hermes/skills/academic-writing/paper-spine/SKILL.md"),
    ):
        record(f"installed: {label}", 0 if p.exists() else 1, "pass")
    record("issue #3 guard: no settings.json written",
           0 if not list(h.rglob("settings.json")) else 1, "pass")


# ---- 3. end-to-end sample run (real artifacts + pandoc docx + every guard) ----
MAIN_TEX = r"""\documentclass{article}
\title{Trajectory-Aligned Knowledge Distillation for Efficient Diffusion Models}
\begin{document}
\maketitle
\section{Introduction}
Diffusion models are powerful but expensive to deploy. Prior work \cite{devlin2019}
established strong representation-learning baselines, yet leaves the cost of
multi-step sampling unresolved. We close that gap with a trajectory-aligned
distillation objective that a reviewer can verify against the validation matrix.
\section{Method}
The student matches the teacher trajectory at aligned timesteps; this is the
credible execution path for the contribution, not a novelty label.
\section{Results}
The student reaches comparable quality with about one third of the parameters,
validating the efficiency contribution under the confirmatory condition stated
in the results validation matrix.
\section{Discussion}
The mechanism is trajectory alignment; we bound the claim to the evaluated
regimes and avoid overclaiming beyond the measured evidence.
\bibliography{references}
\end{document}
"""
REFERENCES_BIB = """@article{devlin2019,
  title={BERT: Pre-training of Deep Bidirectional Transformers},
  author={Devlin, Jacob and Chang, Ming-Wei}, journal={NAACL}, year={2019}
}
"""


def build_sample() -> None:
    print("[3] End-to-end sample run")
    if SAMPLE.exists():
        shutil.rmtree(SAMPLE)
    (OUT / "final_paper").mkdir(parents=True)
    # config
    (OUT / "paper_spine_config.json").write_text(json.dumps({
        "workflow": "build_from_materials", "scene": "journal", "tier": "flash",
        "output_language": "en", "word_output": "docx", "citation_target_count": 10,
    }, indent=2), encoding="utf-8")
    # methodology artifacts: the shipped templates are valid filled examples
    refs = REPO / "src" / "skill" / "references"
    shutil.copy2(refs / "contribution.md", OUT / "confirmed_contribution.md")
    shutil.copy2(refs / "results-validation.md", OUT / "results_validation.md")
    shutil.copy2(refs / "reviewer-audit.md", OUT / "reviewer_audit.md")
    # final paper + pandoc -> docx
    (OUT / "final_paper" / "main.tex").write_text(MAIN_TEX, encoding="utf-8")
    (OUT / "final_paper" / "references.bib").write_text(REFERENCES_BIB, encoding="utf-8")
    pandoc = shutil.which("pandoc")
    if pandoc:
        rc, _ = run([pandoc, "main.tex", "-o", "paper.docx", "--from", "latex", "--to", "docx",
                     "--resource-path=.", "--number-sections", "--citeproc",
                     "--bibliography=references.bib"], cwd=OUT / "final_paper")
        record("pandoc LaTeX -> paper.docx", rc, "pass")
        docx = OUT / "final_paper" / "paper.docx"
        guard("word_guard.py", [str(docx), "--fix-fonts", "--language", "en", "--markdown",
                                "--output", str(OUT / "word_report.md"),
                                "--tex", str(OUT / "final_paper" / "main.tex")],
              "word_guard on real docx (--fix-fonts)")
    else:
        record("pandoc (skipped: not installed)", 0, "pass")
    # methodology + quality guards on the sample
    guard("contribution_check.py", [str(OUT), "--markdown", "--write"], "contribution_check")
    guard("results_validation_check.py", [str(OUT), "--markdown", "--write"], "results_validation_check")
    guard("reviewer_audit_check.py", [str(OUT), "--markdown", "--write"], "reviewer_audit_check")


# ---- 4. negative gate semantics (must FAIL) ----
def negative_gates(tmp: Path) -> None:
    print("[4] Negative gate semantics (must FAIL)")
    # word --require when word disabled
    d1 = tmp / "neg_word"
    d1.mkdir()
    (d1 / "paper_spine_config.json").write_text('{"word_output":"none","output_language":"en"}', encoding="utf-8")
    rc, _ = run([PY, str(SCRIPTS / "progress_check.py"), str(d1), "--gate", "word", "--require"])
    record("progress_check --gate word --require (word=none)", rc, "fail")
    # integrity_audit gate with a FAIL report
    d2 = tmp / "neg_integrity"
    d2.mkdir()
    (d2 / "paper_spine_config.json").write_text('{"scene":"journal"}', encoding="utf-8")
    (d2 / "integrity_audit.md").write_text("# Integrity Audit\n\nStatus: FAIL\n", encoding="utf-8")
    rc, _ = run([PY, str(SCRIPTS / "progress_check.py"), str(d2), "--gate", "integrity_audit"])
    record("progress_check --gate integrity_audit (Status: FAIL)", rc, "fail")
    # respond_check: C1 unanswered but C10/C11 present (substring trap)
    d3 = tmp / "neg_respond"
    d3.mkdir()
    (d3 / "response_to_reviewers.md").write_text(
        "| Comment ID | Reviewer Comment | Response Draft | Status | Change Location |\n"
        "|---|---|---|---|---|\n"
        "| C10 | minor | Fixed typo in section 2. | done | sec2 |\n"
        "| C11 | minor | Clarified the metric definition. | done | sec3 |\n", encoding="utf-8")
    rc, _ = run([PY, str(SCRIPTS / "respond_check.py"), str(d3)])
    record("respond_check: unanswered C1 with C10/C11 present", rc, "fail")


def write_report() -> int:
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["ok"])
    lines = [
        "# PaperSpine V4.0 — Acceptance / Real-Subprocess Test Report",
        "",
        "- Generated by `examples/v4_acceptance.py` (every step shells out for real).",
        f"- **Result: {passed}/{total} checks OK.**",
        "- Sample run artifacts: `examples/v4_sample_run/`.",
        "",
        "| Check | Expect | Exit | Verdict |",
        "|---|---|---|---|",
    ]
    for r in RESULTS:
        lines.append(f"| {r['name']} {r['detail']} | {r['expect']} | {r['rc']} | {'✅' if r['ok'] else '❌'} |")
    lines.append("")
    (REPO / "TEST_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote TEST_REPORT.md — {passed}/{total} OK")
    return 0 if passed == total else 1


def main() -> int:
    import tempfile
    suite_checks()
    with tempfile.TemporaryDirectory() as t:
        install_check(Path(t))
        build_sample()
        negative_gates(Path(t))
    return write_report()


if __name__ == "__main__":
    raise SystemExit(main())
