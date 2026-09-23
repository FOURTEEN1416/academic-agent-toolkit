#!/usr/bin/env python3
"""Structured Peer Review for PaperSpine manuscripts.

Produces a teaching-oriented review where every finding is mapped to a specific
row in the writing_rationale_matrix, linked to supporting (or missing) evidence,
and accompanied by a concrete revision command.  The editor synthesis prioritizes
changes by impact and flags inter-reviewer agreement/disagreement patterns.

Pattern: follows the writing_rationale_matrix philosophy — every review finding
teaches *why* something needs to change and *how* to fix it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paper_spine_utils import (
    make_canon,
    markdown_tables,
    normalize_tex,
    read_text,
    similarity_canon,
    split_paragraphs,
)

SECTION_RE = re.compile(r"\\(?:section|subsection|subsubsection)\*?\{([^{}]+)\}", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Stage 5g: scene-aware reviewer personas
# ---------------------------------------------------------------------------

SCENE_VALID = {"journal", "conference", "report_review", "competition"}

SCENE_PERSONA_DEFAULTS: dict[str, dict[str, str]] = {
    "journal": {
        "methods": "Focus on originality, method rigor, evidence strength, reproducibility, and fit for the target journal.",
        "contribution": "Assess the contribution's significance, differentiation from prior work, citation credibility, and alignment with journal standards.",
        "clarity": "Evaluate structure clarity, argument coherence, figure/table quality, and adherence to journal conventions.",
        "venue_hint": "journal",
    },
    "conference": {
        "methods": "Focus on novelty, technical contribution, correctness under time-limited presentation constraints, and clarity for a conference audience.",
        "contribution": "Assess whether the contribution is compelling for a conference track, properly scoped, and supported by clear evidence.",
        "clarity": "Evaluate presentation quality, conciseness, visual clarity of figures/tables, and suitability for oral or poster presentation.",
        "venue_hint": "conference",
    },
    "report_review": {
        "methods": "Focus on coverage, logic, source synthesis, readability, and practical value for the report's stated purpose.",
        "contribution": "Assess whether the report synthesizes sources effectively, presents a coherent argument, and delivers practical insights.",
        "clarity": "Evaluate document organization, readability, heading structure, and whether findings are accessible to the intended audience.",
        "venue_hint": "report or review",
    },
    "competition": {
        "methods": "Focus on rubric alignment, deliverable completeness, visual/result clarity, innovation claim, and adherence to competition constraints.",
        "contribution": "Assess the innovation claim, solution originality, and whether the entry satisfies competition evaluation criteria.",
        "clarity": "Evaluate solution presentation, visual quality, result formatting, and overall persuasiveness for competition judges.",
        "venue_hint": "competition",
    },
}


@dataclass
class ReviewerPersona:
    role: str           # methods | contribution | clarity
    title: str = ""
    venue_context: str = ""
    standards: str = ""
    red_flags: str = ""
    review_style: str = ""


@dataclass
class ReviewFinding:
    id: str
    reviewer_role: str              # methods | contribution | clarity | editor
    severity: str                   # CRITICAL | MAJOR | MINOR | OBSERVATION
    what: str                       # what was found
    rationale_row: str | None       # which rationale matrix row(s) this maps to
    evidence_status: str            # supported / missing / weak / n/a
    evidence_detail: str            # which evidence (or why missing)
    revision_command: str           # concrete action: "In paragraph 3, replace X with Y because Z"
    teaching_note: str              # why this revision pattern matters


@dataclass
class ReviewerSection:
    role: str
    title: str
    focus: str
    rubric_dimensions: list[str]
    findings: list[ReviewFinding] = field(default_factory=list)


@dataclass
class EditorSynthesis:
    agreement_points: list[str] = field(default_factory=list)
    disagreement_points: list[str] = field(default_factory=list)
    revision_priority: list[str] = field(default_factory=list)
    overall_score: int = 0
    recommendation: str = ""


@dataclass
class StructuredReviewReport:
    manuscript_path: str
    sections: list[dict] = field(default_factory=list)
    reviewers: list[ReviewerSection] = field(default_factory=list)
    editor: EditorSynthesis | None = None
    total_findings: int = 0
    reviewer_personas: list[ReviewerPersona] = field(default_factory=list)
    persona_warnings: list[str] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for r in self.reviewers for f in r.findings if f.severity == "CRITICAL")


def load_reviewer_personas(out_dir: Path) -> tuple[list[ReviewerPersona], list[str]]:
    warnings: list[str] = []
    config_path = out_dir / "paper_spine_config.json"
    if not config_path.exists():
        return _default_personas("journal"), warnings
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_personas("journal"), warnings
    scene = str(config.get("scene", "journal"))
    if scene not in SCENE_VALID:
        scene = "journal"
    target_name = str(config.get("target_name", "")).strip()
    defs = SCENE_PERSONA_DEFAULTS.get(scene, SCENE_PERSONA_DEFAULTS["journal"])
    venue_hint = defs.get("venue_hint", scene)
    personas: list[ReviewerPersona] = []
    for role_key in ("methods", "contribution", "clarity"):
        p = ReviewerPersona(
            role=role_key,
            title=f"{role_key.title()} Reviewer ({venue_hint})",
            venue_context=f"Target context: {target_name}" if target_name else f"Target venue type: {venue_hint}.",
            standards=defs.get(role_key, ""),
            review_style="Scene-aware structured review.",
        )
        personas.append(p)
    rp = config.get("reviewer_persona")
    if rp is not None:
        if isinstance(rp, str) and rp.strip():
            for p in personas:
                p.review_style = rp.strip()
        elif isinstance(rp, dict):
            for role_key in ("methods", "contribution", "clarity"):
                override = rp.get(role_key)
                if isinstance(override, str) and override.strip():
                    for p in personas:
                        if p.role == role_key:
                            p.review_style = override.strip()
                elif override is not None:
                    warnings.append(f"reviewer_persona['{role_key}']: expected string, ignored.")
        else:
            warnings.append(f"reviewer_persona: expected string or dict, got {type(rp).__name__} — ignored.")
    return personas, warnings


def _default_personas(scene: str = "journal") -> list[ReviewerPersona]:
    if scene not in SCENE_VALID:
        scene = "journal"
    defs = SCENE_PERSONA_DEFAULTS[scene]
    venue_hint = defs.get("venue_hint", scene)
    personas: list[ReviewerPersona] = []
    for role_key in ("methods", "contribution", "clarity"):
        personas.append(ReviewerPersona(
            role=role_key,
            title=f"{role_key.title()} Reviewer ({venue_hint})",
            venue_context=f"Target venue type: {venue_hint}.",
            standards=defs.get(role_key, ""),
            review_style="Scene-aware structured review.",
        ))
    return personas


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Structured peer review for PaperSpine manuscripts.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--manuscript", help="Path to .tex manuscript (default: final_paper/main.tex under output_dir)")
    parser.add_argument("--dispatch", action="store_true", help="Generate independent reviewer prompts for multi-agent dispatch")
    parser.add_argument("--validate", help="Validate an existing review file (single) or directory (multi-agent)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write structured_review.md")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# section extraction and rationale matrix parsing
# ---------------------------------------------------------------------------

def extract_sections(manuscript_path: Path) -> list[dict]:
    raw = read_text(manuscript_path)
    sections: list[dict] = []
    if manuscript_path.suffix.lower() == ".tex":
        parts = SECTION_RE.split(raw)
        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                title = parts[i].strip()
                body = normalize_tex(parts[i + 1]) if i + 1 < len(parts) else ""
                paras = split_paragraphs(body)
                sections.append({"title": title, "paragraphs": paras, "word_count": sum(len(p.split()) for p in paras)})
            return sections
    text = normalize_tex(raw) if manuscript_path.suffix.lower() == ".tex" else raw
    paras = split_paragraphs(text)
    sections.append({"title": "Full Manuscript", "paragraphs": paras, "word_count": sum(len(p.split()) for p in paras)})
    return sections


def parse_rationale_matrix(out_dir: Path) -> list[dict]:
    matrix_path = out_dir / "writing_rationale_matrix.md"
    if not matrix_path.exists():
        return []
    text = matrix_path.read_text(encoding="utf-8", errors="ignore")
    tables = markdown_tables(text)
    if not tables:
        return []
    rows = tables[0]
    if len(rows) < 2:
        return []
    header = rows[0]
    result: list[dict] = []
    for i, row in enumerate(rows[1:], start=1):
        entry: dict = {"row_id": str(i)}
        for j, cell in enumerate(row):
            if j < len(header):
                entry[header[j].lower()] = cell
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# evidence bank check helper
# ---------------------------------------------------------------------------

def check_evidence_available(out_dir: Path) -> dict[str, bool]:
    evidence_path = out_dir / "evidence_bank.md"
    if not evidence_path.exists():
        return {"exists": False, "has_content": False}
    text = evidence_path.read_text(encoding="utf-8", errors="ignore")
    return {"exists": True, "has_content": len(text) > 300}


# ---------------------------------------------------------------------------
# review generation (prepares structure — LLM fills findings)
# ---------------------------------------------------------------------------

def generate_structured_review(out_dir: Path, manuscript_path: Path,
                             personas: list[ReviewerPersona] | None = None,
                             persona_warnings: list[str] | None = None) -> StructuredReviewReport:
    sections = extract_sections(manuscript_path)
    rationale = parse_rationale_matrix(out_dir)
    evidence = check_evidence_available(out_dir)

    if personas is None:
        personas = _default_personas("journal")
    if persona_warnings is None:
        persona_warnings = []

    report = StructuredReviewReport(str(manuscript_path), sections=sections,
                                    reviewer_personas=personas, persona_warnings=persona_warnings)

    # Build a manuscript overview
    total_paras = sum(len(s["paragraphs"]) for s in sections)
    total_words = sum(s["word_count"] for s in sections)

    # ---- Methods Reviewer ----
    methods = ReviewerSection(
        role="methods",
        title="Methods & Reproducibility Reviewer",
        focus=(
            "Assess methodological clarity, reproducibility, assumption justification, "
            "experimental design quality, and limitations acknowledgment."
        ),
        rubric_dimensions=[
            "Method description completeness (1=insufficient detail to replicate, 5=fully replicable)",
            "Assumption justification (1=unstated, 5=explicit with rationale)",
            "Experimental design (1=flawed, 5=rigorous)",
            "Limitations acknowledgment (1=none, 5=thorough with impact analysis)",
        ],
    )
    # Seed a finding template if rationale rows for methods exist
    methods_rows = [r for r in rationale if any(w in " ".join(r.values()).lower() for w in ("method", "experiment", "model", "design"))]
    if methods_rows:
        for mr in methods_rows[:3]:
            row_id = mr.get("row_id", "?")
            methods.findings.append(ReviewFinding(
                id=f"MET-{row_id}", reviewer_role="methods", severity="MAJOR",
                what=f"Method unit at rationale row {row_id} needs review",
                rationale_row=row_id,
                evidence_status="supported" if evidence["has_content"] else "missing",
                evidence_detail="Evidence bank has content — verify specific evidence for this method claim."
                if evidence["has_content"] else "evidence_bank.md is missing or empty — methods cannot be verified.",
                revision_command=f"[LLM: assess method at row {row_id} for replicability, assumption clarity, "
                                 f"and limitations. Suggest specific improvements.]",
                teaching_note="Methods are the most-read section after the abstract. "
                              "A reviewer who cannot replicate your work from the methods section will recommend rejection.",
            ))

    # ---- Contribution Reviewer ----
    contribution = ReviewerSection(
        role="contribution",
        title="Contribution & Novelty Reviewer",
        focus=(
            "Assess whether the contribution is clearly stated, properly scoped, "
            "adequately differentiated from prior work, and supported by evidence."
        ),
        rubric_dimensions=[
            "Contribution clarity (1=vague, 5=crystal clear)",
            "Novelty (1=purely incremental, 5=genuinely new contribution)",
            "Evidence-to-claim strength (1=unsupported assertion, 5=conclusive evidence)",
            "Venue appropriateness (1=mismatched, 5=perfect fit for venue)",
        ],
    )
    # Find rationale rows about contribution/claims
    contrib_rows = [r for r in rationale if any(w in " ".join(r.values()).lower()
                   for w in ("contribution", "claim", "novel", "result", "finding", "propos"))]
    for cr in contrib_rows[:3]:
        row_id = cr.get("row_id", "?")
        contribution.findings.append(ReviewFinding(
            id=f"CON-{row_id}", reviewer_role="contribution", severity="MAJOR",
            what=f"Contribution/claim at rationale row {row_id} needs review",
            rationale_row=row_id,
            evidence_status="check",
            evidence_detail="Verify that evidence_bank.md contains specific data supporting this claim.",
            revision_command=f"[LLM: evaluate the claim at row {row_id}: is it clearly stated? scoped properly? "
                             f"differentiated from SOTA? supported by evidence?]",
            teaching_note="A contribution is not what you did — it's what the community gains. "
                          "Frame every claim in terms of its value to the reader, not its effort to the author.",
        ))

    # ---- Clarity Reviewer ----
    clarity = ReviewerSection(
        role="clarity",
        title="Structure & Clarity Reviewer",
        focus=(
            "Assess organization, argument flow, readability, figure/table integration, "
            "section transitions, and whether the paper tells a coherent story."
        ),
        rubric_dimensions=[
            "Overall narrative structure (1=disjointed, 5=seamless story)",
            "Section transitions (1=abrupt/jarring, 5=smooth with logical bridges)",
            "Figure/table quality and integration (1=poor/cluttered, 5=excellent)",
            "Writing clarity (1=confusing/ambiguous, 5=crystal clear)",
        ],
    )
    # Structural findings based on section count
    if total_paras < 20:
        clarity.findings.append(ReviewFinding(
            id="CLR-001", reviewer_role="clarity", severity="MINOR",
            what=f"Manuscript has {total_paras} paragraphs across {len(sections)} sections — fairly concise",
            rationale_row=None,
            evidence_status="n/a",
            evidence_detail="",
            revision_command="[LLM: check whether any sections are underdeveloped. Short sections in a journal "
                             "paper may need expansion or merging.]",
            teaching_note="Concision is a virtue, but underdeveloped sections leave arguments incomplete. "
                          "A paragraph should make one point well, not three points shallowly.",
        ))

    if total_words < 3000:
        clarity.findings.append(ReviewFinding(
            id="CLR-002", reviewer_role="clarity", severity="MAJOR",
            what=f"Total word count ({total_words}) is below typical journal/conference expectations (4000-8000)",
            rationale_row=None,
            evidence_status="n/a",
            evidence_detail="",
            revision_command="[LLM: identify which sections are too thin. A typical Introduction is 500-1000 words, "
                             "Methods 800-1500, Results 1000-2000, Discussion 800-1500.]",
            teaching_note="Word count is a proxy, not a target. But papers far below venue norms "
                          "usually lack depth in literature coverage or discussion of implications.",
        ))

    report.reviewers = [methods, contribution, clarity]

    # ---- Editor Synthesis ----
    report.editor = EditorSynthesis(
        agreement_points=["[LLM: identify 2-3 points where reviewers agree]"],
        disagreement_points=["[LLM: note any conflicting reviewer assessments]"],
        revision_priority=[
            "[LLM: rank the top 3-5 revisions by impact on the paper's quality]",
        ],
        overall_score=0,
        recommendation="[LLM: Accept / Minor Revision / Major Revision / Reject]",
    )
    report.total_findings = sum(len(r.findings) for r in report.reviewers)

    return report


# ---------------------------------------------------------------------------
# validation (checks an LLM-produced review for completeness)
# ---------------------------------------------------------------------------

def validate_review(review_path: Path) -> dict:
    if not review_path.exists():
        return {"ok": False, "findings": ["Review file not found"]}

    text = review_path.read_text(encoding="utf-8", errors="ignore")
    findings: list[str] = []

    required_sections = [
        "Methods & Reproducibility Reviewer",
        "Contribution & Novelty Reviewer",
        "Structure & Clarity Reviewer",
        "Editor Synthesis",
    ]
    for section in required_sections:
        if section not in text:
            findings.append(f"Missing section: {section}")

    placeholders = ["[LLM:", "[FINDING REQUIRED]", "[PRIORITY REQUIRED]",
                    "[AGREEMENT REQUIRED]", "[SCORE REQUIRED]"]
    for ph in placeholders:
        if ph in text:
            findings.append(f"Unfilled placeholder: {ph}")

    # Check for evidence-status tags
    if "evidence_status" not in text.lower() and "supported" not in text.lower():
        findings.append("Review should reference evidence status for key claims")

    return {"ok": not findings, "findings": findings}


def validate_independence(review_dir: Path) -> dict:
    """Check that three reviewer outputs are genuinely independent."""
    if not review_dir.is_dir():
        return {"ok": False, "findings": ["Not a directory"], "independence_score": 0}

    roles = ["methods_reviewer.md", "contribution_reviewer.md", "clarity_reviewer.md"]
    texts: dict[str, str] = {}
    for role_file in roles:
        path = review_dir / role_file
        if not path.exists():
            return {"ok": False, "findings": [f"Missing: {role_file}"], "independence_score": 0}
        texts[role_file] = path.read_text(encoding="utf-8", errors="ignore")

    findings: list[str] = []
    pairs = [(roles[0], roles[1]), (roles[0], roles[2]), (roles[1], roles[2])]
    scores: list[float] = []

    for a, b in pairs:
        ca = make_canon(texts[a])
        cb = make_canon(texts[b])
        sim = similarity_canon(ca, cb)
        scores.append(sim)
        if sim > 0.3:
            findings.append(
                f"Independence concern: {a} and {b} similarity = {sim:.2f}. "
                f"High similarity suggests these reviews were not written independently."
            )

    # Check for cross-reference contamination
    role_names = [r.replace("_reviewer.md", "") for r in roles]
    for i, role_file in enumerate(roles):
        other_names = [n for j, n in enumerate(role_names) if j != i]
        for other in other_names:
            if other in texts[role_file]:
                findings.append(f"Cross-contamination: {role_file} references '{other}' review")

    avg_sim = sum(scores) / len(scores) if scores else 0
    return {
        "ok": not findings,
        "findings": findings,
        "independence_score": round(1.0 - avg_sim, 2),
        "pairwise_similarities": {f"{a} vs {b}": round(s, 4) for (a, b), s in zip(pairs, scores, strict=False)},
    }


def dispatch_review(out_dir: Path, manuscript_path: Path,
                    personas: list[ReviewerPersona] | None = None) -> dict:
    """Generate three independent reviewer prompt files for multi-agent execution."""
    sections = extract_sections(manuscript_path)
    prompts_dir = out_dir / "review_prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    if personas is None:
        personas = _default_personas("journal")

    # Build manuscript section summary
    section_text = "\n\n".join(
        f"### {s['title']}\n{chr(10).join(s.get('paragraphs', [s.get('content', '')]))[:3000]}"
        for s in sections
    )

    reviewer_configs = [
        {
            "file": "methods_reviewer.md",
            "role": "Methods & Reproducibility Reviewer",
            "role_key": "methods",
            "focus": (
                "Assess methodological clarity, reproducibility, assumption "
                "justification, experimental design, and limitations."
            ),
            "rubric": [
                "Method description completeness (1=insufficient, 5=fully replicable)",
                "Assumption justification (1=unstated, 5=explicit with rationale)",
                "Experimental design (1=flawed, 5=rigorous)",
                "Limitations acknowledgment (1=none, 5=thorough)",
            ],
        },
        {
            "file": "contribution_reviewer.md",
            "role": "Contribution & Novelty Reviewer",
            "role_key": "contribution",
            "focus": (
                "Assess novelty, significance, differentiation from prior work, "
                "and evidence-to-claim strength."
            ),
            "rubric": [
                "Contribution clarity (1=vague, 5=crystal clear)",
                "Novelty (1=incremental, 5=genuine contribution)",
                "Evidence-to-claim strength (1=unsupported, 5=conclusive)",
                "Venue appropriateness (1=mismatched, 5=perfect fit)",
            ],
        },
        {
            "file": "clarity_reviewer.md",
            "role": "Structure & Clarity Reviewer",
            "role_key": "clarity",
            "focus": (
                "Assess organization, argument flow, figure/table integration, "
                "section transitions, and writing clarity."
            ),
            "rubric": [
                "Overall structure (1=disjointed, 5=seamless narrative)",
                "Section transitions (1=abrupt, 5=smooth)",
                "Figure/table integration (1=poor, 5=excellent)",
                "Writing clarity (1=confusing, 5=crystal clear)",
            ],
        },
    ]

    file_list: list[str] = []
    for cfg in reviewer_configs:
        # Look up persona for this role
        persona = next((p for p in personas if p.role == cfg["role_key"]), None)
        persona_block = ""
        if persona:
            persona_block = (
                f"## Reviewer Persona\n\n"
                f"**Venue context:** {persona.venue_context}\n\n"
                f"**Standards:** {persona.standards}\n\n"
                f"**Review style:** {persona.review_style}\n\n"
                f"Do not fabricate specific submission rules for the target venue. "
                f"Only use what is known from the research stage or user-provided materials.\n\n"
            )

        prompt = (
            f"# {cfg['role']}\n\n"
            f"{persona_block}"
            f"## Role\n\n{cfg['focus']}\n\n"
            f"**IMPORTANT:** You are an independent reviewer. Do NOT read or "
            f"reference the other reviewers' work. Your assessment must stand "
            f"entirely on its own. Do not mention what other reviewers might say.\n\n"
            f"## Rubric (score 1-5 for each)\n\n"
        )
        for dim in cfg["rubric"]:
            prompt += f"- {dim}\n"
        prompt += (
            f"\n## Manuscript Sections\n\n{section_text}\n\n"
            f"## Instructions\n\n"
            f"1. Score each rubric dimension (1-5) with a brief justification.\n"
            f"2. List at least 3 specific findings. Reference section names.\n"
            f"3. Recommend: Accept / Minor Revision / Major Revision / Reject.\n"
            f"4. Write your review in clear, structured Markdown.\n\n"
            f"Write only your review. Do NOT produce other files.\n"
        )
        out_path = prompts_dir / cfg["file"]
        out_path.write_text(prompt, encoding="utf-8")
        file_list.append(str(out_path.relative_to(out_dir)))

    # Write dispatch instructions for the main Claude
    dispatch_md = (
        "# Review Dispatch Instructions\n\n"
        "Launch **three sub-agents in parallel** using the Agent tool. "
        "Each agent reads only its own prompt file and the manuscript — "
        "they must NOT see each other's outputs or the other prompts.\n\n"
        "### Agent 1: Methods Reviewer\n"
        "Read `review_prompts/methods_reviewer.md` and produce `review_prompts/methods_review_output.md`\n\n"
        "### Agent 2: Contribution Reviewer\n"
        "Read `review_prompts/contribution_reviewer.md` and produce `review_prompts/contribution_review_output.md`\n\n"
        "### Agent 3: Clarity Reviewer\n"
        "Read `review_prompts/clarity_reviewer.md` and produce `review_prompts/clarity_review_output.md`\n\n"
        "### After all three complete:\n"
        "Run `python scripts/structured_review.py paper_rewriting_output --validate review_prompts` "
        "to check independence. Then produce the Editor Synthesis.\n"
    )
    (prompts_dir / "dispatch.md").write_text(dispatch_md, encoding="utf-8")

    return {
        "status": "dispatched",
        "prompts_dir": str(prompts_dir.relative_to(out_dir)),
        "files": file_list,
    }


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def to_markdown(report: StructuredReviewReport) -> str:
    lines = [
        "# Structured Peer Review",
        "",
        f"- Manuscript: `{report.manuscript_path}`",
        f"- Sections: {len(report.sections)}",
        f"- Total findings: {report.total_findings} ({report.critical_count} critical)",
        "",
        "> Each finding maps to a rationale matrix row, links to evidence status, "
        "and provides a concrete revision command — not just 'improve this'.",
        "",
    ]

    # Reviewer Personas section
    if report.reviewer_personas:
        lines.append("## Reviewer Personas")
        lines.append("")
        for p in report.reviewer_personas:
            lines.append(f"### {p.title}")
            lines.append(f"- **Context:** {p.venue_context}")
            lines.append(f"- **Standards:** {p.standards}")
            if p.red_flags:
                lines.append(f"- **Red flags:** {p.red_flags}")
            lines.append(f"- **Style:** {p.review_style}")
            lines.append("")
        if report.persona_warnings:
            lines.append("### Persona Warnings")
            lines.append("")
            for w in report.persona_warnings:
                lines.append(f"- {w}")
            lines.append("")

    lines.extend([
        "---",
        "",
    ])

    # Reviewers
    for reviewer in report.reviewers:
        lines.append(f"## {reviewer.title}")
        lines.append("")
        lines.append(f"**Focus:** {reviewer.focus}")
        lines.append("")
        lines.append("### Scoring Rubric (1-5)")
        lines.append("")
        for dim in reviewer.rubric_dimensions:
            lines.append(f"- {dim}")
        lines.append("")

        if not reviewer.findings:
            lines.append("*No findings — this reviewer has nothing to flag.*")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        lines.append("### Findings")
        lines.append("")
        lines.append("| ID | Severity | What | Rationale Row | Evidence | Revision Command |")
        lines.append("|---|---|---|---|---|---|")
        for f in reviewer.findings:
            lines.append(
                f"| {f.id} | {f.severity} | {f.what[:80]} | {f.rationale_row or '—'} | "
                f"{f.evidence_status} | {f.revision_command[:100]} |"
            )
        lines.append("")

        for f in reviewer.findings:
            if f.severity == "OBSERVATION":
                continue
            icon = "🔴" if f.severity == "CRITICAL" else "🟡" if f.severity == "MAJOR" else "🔵"
            lines.append(f"#### {icon} {f.id}")
            lines.append("")
            lines.append(f"**Finding:** {f.what}")
            lines.append("")
            if f.rationale_row:
                lines.append(f"**Rationale matrix row:** {f.rationale_row} — compare against the planned function, "
                             "motivation link, and evidence anchor in writing_rationale_matrix.md.")
                lines.append("")
            lines.append(f"**Evidence status:** {f.evidence_status}")
            if f.evidence_detail:
                lines.append(f"  {f.evidence_detail}")
            lines.append("")
            lines.append(f"**Revision command:** {f.revision_command}")
            lines.append("")
            if f.teaching_note:
                lines.append(f"> {f.teaching_note}")
                lines.append("")

        lines.append("---")
        lines.append("")

    # Editor Synthesis
    if report.editor:
        ed = report.editor
        lines.append("## Editor Synthesis")
        lines.append("")
        lines.append("### Points of Agreement")
        lines.append("")
        for point in ed.agreement_points:
            lines.append(f"- {point}")
        lines.append("")
        lines.append("### Points of Disagreement")
        lines.append("")
        for point in ed.disagreement_points:
            lines.append(f"- {point}")
        lines.append("")
        lines.append("### Revision Priority")
        lines.append("")
        lines.append("> Ordered by impact: fixing item 1 improves the paper more than fixing item 5.")
        lines.append("")
        for i, item in enumerate(ed.revision_priority, start=1):
            lines.append(f"{i}. {item}")
        lines.append("")
        lines.append(f"**Overall score:** {ed.overall_score}/100")
        lines.append("")
        lines.append(f"**Recommendation:** {ed.recommendation}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    manuscript_path = Path(args.manuscript) if args.manuscript else out_dir / "final_paper" / "main.tex"

    personas, persona_warnings = load_reviewer_personas(out_dir)

    if args.dispatch:
        if not manuscript_path.exists():
            print(f"Manuscript not found: {manuscript_path}", file=sys.stderr)
            return 2
        result = dispatch_review(out_dir, manuscript_path, personas)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.validate:
        validate_path = Path(args.validate)
        if validate_path.is_dir():
            result = validate_independence(validate_path)
        else:
            result = validate_review(validate_path)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    report = generate_structured_review(out_dir, manuscript_path, personas, persona_warnings)

    if args.json:
        print(json.dumps({
            "manuscript": str(manuscript_path),
            "sections": len(report.sections),
            "total_findings": report.total_findings,
            "critical": report.critical_count,
            "reviewers": [
                {"role": r.role, "findings_count": len(r.findings)}
                for r in report.reviewers
            ],
            "reviewer_personas": [
                {"role": p.role, "title": p.title, "venue_context": p.venue_context,
                 "standards": p.standards, "review_style": p.review_style}
                for p in report.reviewer_personas
            ],
            "persona_warnings": report.persona_warnings,
        }, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(to_markdown(report))

    if args.write:
        report_path = out_dir / "structured_review.md"
        report_path.write_text(to_markdown(report), encoding="utf-8")
        print(f"Wrote {report_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
