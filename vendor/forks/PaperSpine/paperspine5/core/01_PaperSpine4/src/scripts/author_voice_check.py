#!/usr/bin/env python3
"""Validate an evidence-bound PaperSpine authorial-voice restoration pass.

The checker does not identify AI authorship and does not estimate an "AI rate".
It verifies revision provenance and hard semantic invariants, then reports
template-like prose patterns as advisory diagnostics only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CONTRACT = "paperspine.author-voice-restoration"
SCHEMA_VERSION = "1.0"
PASS = "PASS"
BLOCKED = "BLOCKED"

NEGATION_EN = ("not", "no", "never", "neither", "without", "lack", "lacks", "failed", "fails")
NEGATION_ZH = ("不", "未", "无", "没有", "并非", "不能", "不足", "缺乏", "失败")
CAUSAL_EN = (
    "cause", "causes", "caused", "causal", "because", "therefore", "resulted in",
    "leads to", "led to", "drives", "driven by", "due to", "attributable to",
    "associated with", "correlated with",
)
CAUSAL_ZH = ("导致", "引起", "造成", "因为", "因此", "归因于", "驱动", "因果", "相关", "关联")
MODAL_EN = (
    "may", "might", "could", "can", "suggest", "suggests", "suggested", "likely",
    "unlikely", "possibly", "potentially", "appears", "seems", "uncertain",
    "approximately", "about", "demonstrate", "demonstrates", "prove", "proves",
)
MODAL_ZH = (
    "可能", "或许", "可以", "提示", "表明", "似乎", "大约", "约", "不确定",
    "潜在", "倾向", "证明", "证实", "显示",
)

NUMBER_UNIT_RE = re.compile(
    r"(?<![\w.])[+\-−]?\d+(?:[.,]\d+)?(?:[eE][+\-]?\d+)?"
    r"(?:\s*(?:%|‰|pp|bp|bps|fold|x|×|mg|g|kg|μg|ug|ng|pg|mL|ml|L|l|"
    r"μL|uL|nm|μm|um|mm|cm|m|km|s|ms|min|h|Hz|kHz|MHz|°C|K|Pa|kPa|"
    r"mol|mmol|μmol|umol|nM|μM|uM|mM|M))?",
    re.IGNORECASE,
)
CITE_RE = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*)*\{([^{}]+)\}")
PANDOC_CITE_RE = re.compile(r"\[@([\w:./\-]+)")
INLINE_MATH_RE = re.compile(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$", re.DOTALL)
DISPLAY_MATH_RE = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
ENV_MATH_RE = re.compile(
    r"\\begin\{(equation\*?|align\*?|gather\*?|multline\*?)\}(.+?)"
    r"\\end\{\1\}",
    re.DOTALL,
)

DIAGNOSTIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "empty_framing": (
        "it is worth noting that", "it should be noted that", "it is important to note that",
        "值得注意的是", "需要指出的是", "不容忽视的是",
    ),
    "generic_importance": (
        "plays an important role", "is of great significance", "important implications",
        "具有重要意义", "具有重要作用", "具有广阔前景", "产生深远影响",
    ),
    "mechanical_enumeration": (
        "firstly", "secondly", "thirdly", "in conclusion", "to sum up",
        "首先", "其次", "再次", "最后", "综上所述", "总而言之",
    ),
    "writing_process_leak": (
        "this section discusses", "the following paragraph", "we have reorganized",
        "this manuscript has been revised", "本节将讨论", "下文将", "本文重新组织",
    ),
    "promotional_precision_gap": (
        "groundbreaking", "unprecedented", "comprehensive solution", "highly robust",
        "突破性的", "前所未有", "全面解决", "高度稳健",
    ),
}

STYLE_CONNECTORS_EN = ("however", "therefore", "thus", "moreover", "furthermore", "additionally")
STYLE_CONNECTORS_ZH = ("然而", "因此", "此外", "同时", "进一步", "综上")
FIRST_PERSON_EN = ("we", "our", "ours")
FIRST_PERSON_ZH = ("我们", "本文", "本研究")
HEDGES_EN = ("may", "might", "could", "suggest", "likely", "possibly", "approximately")
HEDGES_ZH = ("可能", "或许", "提示", "大约", "约", "不确定")


@dataclass
class Finding:
    code: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthorVoiceResult:
    ok: bool = False
    status: str = BLOCKED
    contract: str = CONTRACT
    schema_version: str = SCHEMA_VERSION
    mode: str = ""
    output_language: str = ""
    language_assessment: str = "not_assessed"
    assessment_language: str = ""
    original_path: str = ""
    revised_path: str = ""
    original_sha256: str = ""
    revised_sha256: str = ""
    hard_findings: list[Finding] = field(default_factory=list)
    advisory_findings: list[Finding] = field(default_factory=list)
    invariants: dict[str, Any] = field(default_factory=dict)
    style_deviation: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    authority_files: list[dict[str, str]] = field(default_factory=list)
    author_confirmation: str = "pending"
    semantic_audit: str = "missing"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _counter_diff(original: Counter[str], revised: Counter[str]) -> dict[str, dict[str, int]]:
    keys = sorted(set(original) | set(revised))
    return {
        key: {"original": original[key], "revised": revised[key]}
        for key in keys
        if original[key] != revised[key]
    }


def extract_numbers_units(text: str) -> Counter[str]:
    return Counter(_normalize_space(match.group(0)).lower().replace("−", "-") for match in NUMBER_UNIT_RE.finditer(text))


def extract_citations(text: str) -> Counter[str]:
    keys: list[str] = []
    for match in CITE_RE.finditer(text):
        keys.extend(key.strip() for key in match.group(1).split(",") if key.strip())
    keys.extend(match.group(1).strip() for match in PANDOC_CITE_RE.finditer(text))
    return Counter(keys)


def extract_formulas(text: str) -> Counter[str]:
    formulas = [_normalize_space(match.group(1)) for match in INLINE_MATH_RE.finditer(text)]
    formulas.extend(_normalize_space(match.group(1)) for match in DISPLAY_MATH_RE.finditer(text))
    formulas.extend(_normalize_space(match.group(2)) for match in ENV_MATH_RE.finditer(text))
    return Counter(formula for formula in formulas if formula)


def marker_counter(text: str, language: str, kind: str) -> Counter[str]:
    pools = {
        ("en", "negation"): NEGATION_EN,
        ("zh", "negation"): NEGATION_ZH,
        ("en", "causal_direction"): CAUSAL_EN,
        ("zh", "causal_direction"): CAUSAL_ZH,
        ("en", "modality_uncertainty"): MODAL_EN,
        ("zh", "modality_uncertainty"): MODAL_ZH,
    }
    if language not in {"en", "zh"}:
        raise ValueError(f"Unsupported marker assessment language: {language}")
    pool = pools[(language, kind)]
    lowered = text.casefold()
    counts: Counter[str] = Counter()
    for marker in pool:
        needle = marker.casefold()
        if language == "zh":
            count = lowered.count(needle)
        else:
            count = len(re.findall(rf"\b{re.escape(needle)}\b", lowered))
        if count:
            counts[marker] = count
    return counts


def protected_term_counter(text: str, terms: list[str]) -> Counter[str]:
    lowered = text.casefold()
    return Counter({term: lowered.count(term.casefold()) for term in terms if term.strip()})


def _resolve_local(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("path must be a non-empty project-relative string")
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"path escapes output root: {relative}") from exc
    return candidate


def _verify_file_spec(root: Path, spec: Any, label: str, findings: list[Finding]) -> tuple[Path | None, str]:
    if not isinstance(spec, dict):
        findings.append(Finding("invalid_file_spec", "BLOCKER", f"{label} must be a file object."))
        return None, ""
    relative = spec.get("path")
    expected = str(spec.get("sha256") or "").lower()
    try:
        path = _resolve_local(root, relative)
    except (TypeError, ValueError) as exc:
        findings.append(Finding("unsafe_path", "BLOCKER", f"{label}: {exc}"))
        return None, ""
    if not path.is_file():
        findings.append(Finding("missing_file", "BLOCKER", f"{label} is missing: {relative}"))
        return None, ""
    actual = sha256_file(path)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        findings.append(Finding("invalid_declared_hash", "BLOCKER", f"{label} has no valid declared SHA-256."))
    elif actual != expected:
        findings.append(
            Finding(
                "hash_mismatch", "BLOCKER", f"{label} hash does not match current bytes.",
                {"path": relative, "declared": expected, "actual": actual},
            )
        )
    return path, actual


def _sentence_lengths(text: str, language: str) -> list[int]:
    if language == "zh":
        sentences = re.split(r"[。！？；\n]+", text)
        return [len(re.sub(r"\s+", "", sentence)) for sentence in sentences if len(sentence.strip()) >= 6]
    sentences = re.split(r"(?<=[.!?;])\s+|\n+", text)
    return [len(re.findall(r"[A-Za-z]+", sentence)) for sentence in sentences if len(sentence.strip()) >= 12]


def _style_features(text: str, language: str) -> dict[str, float]:
    lengths = _sentence_lengths(text, language)
    mean = statistics.mean(lengths) if lengths else 0.0
    cv = statistics.pstdev(lengths) / mean if len(lengths) > 1 and mean else 0.0
    size = max(len(text) / 1000.0, 0.001)
    lower = text.casefold()
    connectors = STYLE_CONNECTORS_ZH if language == "zh" else STYLE_CONNECTORS_EN
    first_person = FIRST_PERSON_ZH if language == "zh" else FIRST_PERSON_EN
    hedges = HEDGES_ZH if language == "zh" else HEDGES_EN

    def count(pool: tuple[str, ...]) -> int:
        if language == "zh":
            return sum(lower.count(item.casefold()) for item in pool)
        return sum(len(re.findall(rf"\b{re.escape(item.casefold())}\b", lower)) for item in pool)

    return {
        "sentence_length_mean": round(mean, 3),
        "sentence_length_cv": round(cv, 3),
        "connector_per_1k_chars": round(count(connectors) / size, 3),
        "first_person_per_1k_chars": round(count(first_person) / size, 3),
        "hedge_per_1k_chars": round(count(hedges) / size, 3),
    }


def _style_deviation(author_text: str, revised_text: str, language: str) -> dict[str, Any]:
    baseline = _style_features(author_text, language)
    revised = _style_features(revised_text, language)
    components: dict[str, float] = {}
    for key, base_value in baseline.items():
        value = revised[key]
        scale = max(abs(base_value), 1.0)
        components[key] = round(min(abs(value - base_value) / scale, 5.0), 3)
    distance = round(math.sqrt(sum(value * value for value in components.values()) / len(components)), 3)
    return {
        "available": True,
        "interpretation": "descriptive_distance_only_not_authorship_evidence",
        "baseline": baseline,
        "revised": revised,
        "normalized_components": components,
        "distance": distance,
    }


def scan_diagnostics(text: str) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    lines = text.splitlines()
    for code, phrases in DIAGNOSTIC_PATTERNS.items():
        hits: list[dict[str, Any]] = []
        for line_number, line in enumerate(lines, start=1):
            lowered = line.casefold()
            matched = [phrase for phrase in phrases if phrase.casefold() in lowered]
            if matched:
                hits.append({
                    "line": line_number,
                    "patterns": matched,
                    "excerpt": _normalize_space(line)[:240],
                })
        if hits:
            diagnostics.append({"code": code, "count": len(hits), "hits": hits[:12]})
    return diagnostics


def _load_json(path: Path, label: str, findings: list[Finding]) -> dict[str, Any]:
    if not path.is_file():
        findings.append(Finding("missing_contract", "BLOCKER", f"{label} is missing: {path.name}"))
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(Finding("invalid_json", "BLOCKER", f"{label} is not valid JSON: {exc}"))
        return {}
    if not isinstance(data, dict):
        findings.append(Finding("invalid_contract", "BLOCKER", f"{label} must be a JSON object."))
        return {}
    return data


def validate_author_voice(
    output_dir: Path,
    request_path: Path | None = None,
    profile_path: Path | None = None,
) -> AuthorVoiceResult:
    root = output_dir.resolve()
    result = AuthorVoiceResult()
    hard = result.hard_findings
    advisory = result.advisory_findings
    request_path = request_path or root / "author_voice_revision.json"
    profile_path = profile_path or root / "author_voice_profile.json"
    request = _load_json(request_path, "author_voice_revision.json", hard)
    profile = _load_json(profile_path, "author_voice_profile.json", hard)
    if not request or not profile:
        return result

    for label, data, expected_contract in (
        ("revision", request, CONTRACT),
        ("profile", profile, "paperspine.author-voice-profile"),
    ):
        if data.get("contract") != expected_contract or data.get("schema_version") != SCHEMA_VERSION:
            hard.append(Finding("contract_version", "BLOCKER", f"{label} contract/version is not supported."))

    result.mode = str(request.get("mode") or "")
    if result.mode not in {"rewrite", "no_op"}:
        hard.append(Finding("invalid_mode", "BLOCKER", "mode must be rewrite or no_op."))

    # Preserve the output's declared language, including region/script subtags.
    # The profile cannot silently relabel a revision or choose an English fallback.
    declared = request.get("output_language", profile.get("output_language"))
    result.output_language = declared if isinstance(declared, str) else ""
    tag = result.output_language.strip().lower()
    match = re.fullmatch(r"(en|zh)(?:-[a-z0-9]{1,8})*", tag)
    language = match.group(1) if match else ""
    profile_tag = profile.get("output_language")
    if isinstance(profile_tag, str) and profile_tag.strip().lower() != tag:
        hard.append(Finding("language_declaration_mismatch", "BLOCKER", "Profile and revision declare different output languages; preserve and resolve the actual language before assessment."))
        language = ""
    result.assessment_language = language
    if not language:
        hard.append(Finding(
            "unsupported_language_assessment", "BLOCKER",
            f"Language-dependent voice and semantic-marker checks are not assessed for {result.output_language!r}. No English fallback was used; assess each concrete output language with a supported method.",
        ))
    else:
        result.language_assessment = "supported_method_selected"
    original_path, original_hash = _verify_file_spec(root, request.get("original"), "original", hard)
    revised_path, revised_hash = _verify_file_spec(root, request.get("revised"), "revised", hard)
    result.original_sha256 = original_hash
    result.revised_sha256 = revised_hash
    if isinstance(request.get("original"), dict):
        result.original_path = str(request["original"].get("path") or "")
    if isinstance(request.get("revised"), dict):
        result.revised_path = str(request["revised"].get("path") or "")

    authority_specs = request.get("authority_files")
    if not isinstance(authority_specs, list) or not authority_specs:
        hard.append(Finding("missing_authority_snapshot", "BLOCKER", "At least one frozen claim/evidence authority file is required."))
    else:
        for index, item in enumerate(authority_specs, start=1):
            if not isinstance(item, dict) or not str(item.get("purpose") or "").strip():
                hard.append(Finding("invalid_authority", "BLOCKER", f"authority_files[{index}] needs a purpose."))
                continue
            path, actual = _verify_file_spec(root, item, f"authority_files[{index}]", hard)
            if path is not None:
                result.authority_files.append({"purpose": str(item["purpose"]), "path": str(item["path"]), "sha256": actual})

    profile_status = str(profile.get("status") or "")
    sources = profile.get("authorized_sources")
    author_corpus_parts: list[str] = []
    if profile_status == "available":
        if not isinstance(sources, list) or not sources:
            hard.append(Finding("missing_author_voice_source", "BLOCKER", "Available profile requires authorized_sources."))
        else:
            for index, source in enumerate(sources, start=1):
                authorization = str(source.get("authorization") or "") if isinstance(source, dict) else ""
                if authorization not in {"author_owned", "explicitly_authorized"}:
                    hard.append(Finding("unauthorized_voice_source", "BLOCKER", f"authorized_sources[{index}] lacks valid authorization."))
                    continue
                path, _actual = _verify_file_spec(root, source, f"authorized_sources[{index}]", hard)
                if path is not None:
                    author_corpus_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    elif profile_status == "unavailable":
        if sources not in (None, []):
            hard.append(Finding("unavailable_profile_has_sources", "BLOCKER", "Unavailable profile must not contain unverified sources."))
        if not str(profile.get("unavailable_reason") or "").strip():
            hard.append(Finding("missing_profile_reason", "BLOCKER", "Unavailable author voice profile needs a reason."))
        advisory.append(Finding("voice_baseline_unavailable", "ADVISORY", "No authorized author corpus is available; do not imitate another scholar."))
    else:
        hard.append(Finding("invalid_profile_status", "BLOCKER", "profile status must be available or unavailable."))

    if original_path is not None and revised_path is not None:
        original_text = original_path.read_text(encoding="utf-8", errors="ignore")
        revised_text = revised_path.read_text(encoding="utf-8", errors="ignore")
        protected_terms = []
        for source in (profile.get("protected_terms"), request.get("protected_terms")):
            if isinstance(source, list):
                protected_terms.extend(str(item) for item in source if str(item).strip())
        protected_terms = sorted(set(protected_terms), key=str.casefold)
        invariant_extractors = {
            "numbers_units": lambda text: extract_numbers_units(text),
            "citations": lambda text: extract_citations(text),
            "formulas": lambda text: extract_formulas(text),
            "protected_terms": lambda text: protected_term_counter(text, protected_terms),
            "negation": lambda text: marker_counter(text, language, "negation"),
            "causal_direction": lambda text: marker_counter(text, language, "causal_direction"),
            "modality_uncertainty_claim_strength": lambda text: marker_counter(text, language, "modality_uncertainty"),
        }
        language_dependent = {"negation", "causal_direction", "modality_uncertainty_claim_strength"}
        for name, extractor in invariant_extractors.items():
            if not language and name in language_dependent:
                result.invariants[name] = {"preserved": None, "status": "not_assessed", "reason": "unsupported_or_conflicting_language"}
                continue
            before = extractor(original_text)
            after = extractor(revised_text)
            difference = _counter_diff(before, after)
            result.invariants[name] = {"preserved": not difference, "differences": difference}
            if difference:
                hard.append(Finding("semantic_invariant_drift", "BLOCKER", f"{name} changed during voice restoration.", difference))

        if result.mode == "no_op":
            if original_hash != revised_hash:
                hard.append(Finding("invalid_no_op", "BLOCKER", "no_op requires byte-identical original and revised hashes."))
            if request.get("changes") not in (None, []):
                hard.append(Finding("invalid_no_op_log", "BLOCKER", "no_op must have an empty changes list."))
        elif result.mode == "rewrite":
            if original_hash == revised_hash:
                hard.append(Finding("rewrite_without_change", "BLOCKER", "Identical files must be recorded as no_op, not rewrite."))
            changes = request.get("changes")
            if not isinstance(changes, list) or not changes:
                hard.append(Finding("missing_change_log", "BLOCKER", "rewrite requires a non-empty, locator-bound changes list."))
            else:
                required_change_fields = {"change_id", "source_locator", "revised_locator", "reason", "evidence_anchor"}
                for index, change in enumerate(changes, start=1):
                    if not isinstance(change, dict) or any(not str(change.get(field) or "").strip() for field in required_change_fields):
                        hard.append(Finding("invalid_change_log", "BLOCKER", f"changes[{index}] lacks a required locator/reason/evidence field."))

        result.language_assessment = "assessed_with_heuristics" if language else "not_assessed"
        result.diagnostics = scan_diagnostics(revised_text) if language else []
        if result.diagnostics:
            advisory.append(
                Finding(
                    "template_pattern_diagnostics", "ADVISORY",
                    "Pattern matches are diagnostic signals only; review them in section context and do not infer authorship.",
                    {"pattern_groups": len(result.diagnostics)},
                )
            )
        if not language:
            result.style_deviation = {"available": False, "reason": "unsupported_or_conflicting_language"}
        elif author_corpus_parts:
            result.style_deviation = _style_deviation("\n\n".join(author_corpus_parts), revised_text, language)
        else:
            result.style_deviation = {"available": False, "reason": "authorized_author_corpus_unavailable"}

    audit = request.get("semantic_audit")
    result.semantic_audit = str(audit.get("status") or "missing") if isinstance(audit, dict) else "missing"
    if not isinstance(audit, dict):
        hard.append(Finding("missing_semantic_audit", "BLOCKER", "A semantic audit receipt is required."))
    else:
        if audit.get("status") != "pass":
            hard.append(Finding("semantic_audit_blocked", "BLOCKER", "Semantic audit status must be pass."))
        if str(audit.get("original_sha256") or "").lower() != original_hash or str(audit.get("revised_sha256") or "").lower() != revised_hash:
            hard.append(Finding("stale_semantic_audit", "BLOCKER", "Semantic audit hashes do not match current files."))
        method = audit.get("audit_method")
        if result.mode == "rewrite":
            if method != "independent_agent" or audit.get("independent_from_rewriter") is not True:
                hard.append(Finding("non_independent_audit", "BLOCKER", "A rewrite requires an independent semantic auditor with veto authority."))
            if str(audit.get("reviewer_id") or "") == str(request.get("rewriter_id") or ""):
                hard.append(Finding("same_rewriter_reviewer", "BLOCKER", "Rewriter and semantic auditor must be different identities."))
        elif method not in {"independent_agent", "deterministic_identity"}:
            hard.append(Finding("invalid_audit_method", "BLOCKER", "no_op audit_method must be deterministic_identity or independent_agent."))
        zero_fields = (
            "unsupported_new_claims", "claim_strength_drift", "causal_direction_changes",
            "negation_changes", "modality_uncertainty_changes", "citation_meaning_changes",
        )
        for field_name in zero_fields:
            if audit.get(field_name) != 0:
                hard.append(Finding("semantic_audit_drift", "BLOCKER", f"semantic_audit.{field_name} must equal 0."))

    confirmation = request.get("author_confirmation")
    result.author_confirmation = str(confirmation.get("status") or "pending") if isinstance(confirmation, dict) else "pending"
    if not isinstance(confirmation, dict) or confirmation.get("status") != "confirmed":
        hard.append(Finding("author_confirmation_missing", "BLOCKER", "The author has not confirmed the current revised hash."))
    elif str(confirmation.get("confirmed_sha256") or "").lower() != revised_hash:
        hard.append(Finding("stale_author_confirmation", "BLOCKER", "Author confirmation is not bound to the current revised hash."))

    result.ok = not hard
    result.status = PASS if result.ok else BLOCKED
    return result


def to_json_dict(result: AuthorVoiceResult) -> dict[str, Any]:
    return asdict(result)


def to_markdown(result: AuthorVoiceResult) -> str:
    lines = [
        "# Authorial Voice Restoration Receipt",
        "",
        f"- Contract: `{result.contract}/{result.schema_version}`",
        f"- Status: **{result.status}**",
        f"- Mode: `{result.mode or 'unknown'}`",
        f"- Original: `{result.original_path}` / `{result.original_sha256 or 'unavailable'}`",
        f"- Revised: `{result.revised_path}` / `{result.revised_sha256 or 'unavailable'}`",
        f"- Semantic audit: `{result.semantic_audit}`",
        f"- Author confirmation: `{result.author_confirmation}`",
        "- Authorship inference: `not_performed`",
        "- Detector pass / AI percentage: `not_claimed`",
        "",
        "## Hard findings",
        "",
    ]
    if result.hard_findings:
        lines.extend(f"- **{item.code}** — {item.message}" for item in result.hard_findings)
    else:
        lines.append("- None")
    lines.extend(["", "## Semantic invariants", ""])
    if result.invariants:
        for name, value in result.invariants.items():
            state = "not assessed" if value.get("status") == "not_assessed" else ("preserved" if value.get("preserved") else "changed")
            lines.append(f"- `{name}`: {state}")
    else:
        lines.append("- Not evaluated")
    lines.extend(["", "## Author-voice deviation", ""])
    if result.style_deviation.get("available"):
        lines.append(f"- Descriptive normalized distance: `{result.style_deviation.get('distance')}`")
        lines.append("- Interpretation: descriptive only; not authorship evidence or an acceptance threshold.")
    else:
        lines.append(f"- Unavailable: `{result.style_deviation.get('reason', 'not evaluated')}`")
    lines.extend(["", "## Advisory pattern diagnostics", ""])
    if result.diagnostics:
        for diagnostic in result.diagnostics:
            lines.append(f"- `{diagnostic['code']}`: {diagnostic['count']} line(s)")
    else:
        lines.append("- None")
    if result.advisory_findings:
        lines.extend(["", "## Advisory findings", ""])
        lines.extend(f"- **{item.code}** — {item.message}" for item in result.advisory_findings)
    lines.extend([
        "",
        "Pattern matches are diagnostic signals, not authorship judgments. A clean-text no-op is valid.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PaperSpine Authorial Voice Restoration receipts.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--request", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write author_voice_receipt.json and author_voice_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    result = validate_author_voice(output_dir, args.request, args.profile)
    payload = to_json_dict(result)
    markdown = to_markdown(result)
    if args.write:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "author_voice_receipt.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (output_dir / "author_voice_report.md").write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
