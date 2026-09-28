#!/usr/bin/env python3
"""Validate PaperSpine humanize_matrix.md and scan for remaining AI patterns.

Self-contained — standard library only, no dependencies on other PaperSpine
modules.  Can be distributed standalone with paper-spine-humanize skill.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import statistics
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

# --- self-contained table helpers (no _paper_spine_utils import) ---

def _split_table_line(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_sep(cells: list[str]) -> bool:
    return bool(cells) and all(c and set(c) <= {"-", ":", " "} for c in cells)


def _table_rows(text: str) -> tuple[list[str], list[list[str]]]:
    rows: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = _split_table_line(line)
        if _is_sep(cells):
            continue
        rows.append(cells)
    return (rows[0], rows[1:]) if rows else ([], [])


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n+", text)
    return [re.sub(r"\s+", " ", p).strip() for p in parts if len(p.strip()) > MIN_PARAGRAPH_CHARS]


def _split_sentences(text: str) -> list[str]:
    return [
        s.strip()
        for s in re.split(r"(?<=[。！？!?；;.!?])\s*|\n+", text)
        if SENTENCE_MIN_CHARS < len(s.strip()) < SENTENCE_MAX_CHARS
    ]


def _sentence_start(sentence: str, lang: str) -> str:
    cleaned = re.sub(r"^[\s\"'""''（(【\\[]+", "", sentence).strip()
    if lang == "en":
        words = re.findall(r"[A-Za-z]+", cleaned.lower())
        return " ".join(words[:2])
    return cleaned[:8]


# --- AI pattern detection ---

AI_CONNECTORS_ZH = [
    "首先", "其次", "再次", "最后", "综上所述", "总而言之", "总的来说",
    "此外", "另外", "不仅如此", "值得注意的是", "需要指出的是", "不容忽视的是",
    "具有重要意义", "具有重要的理论意义", "具有重要的现实意义",
    "为……奠定基础", "在……的过程中",
    "因此", "由此可见", "与此同时", "进一步而言", "从这个意义上说",
    "换言之", "也就是说", "基于此", "显然", "不可否认的是",
]
AI_CONNECTORS_EN = [
    "firstly", "secondly", "thirdly", "finally", "in conclusion", "to sum up",
    "furthermore", "moreover", "additionally", "it is worth noting",
    "it should be pointed out", "it cannot be ignored", "plays a crucial role",
    "has significant implications",
    "therefore", "thus", "consequently", "meanwhile", "in this regard",
    "in other words", "on the one hand", "on the other hand",
]

GENERIC_PHRASES_ZH = [
    "具有重要意义", "具有重要作用", "具有重要价值", "提供理论基础",
    "提供参考", "奠定基础", "值得关注", "不容忽视", "越来越受到关注",
    "具有广阔前景", "发挥重要作用", "产生深远影响", "有待进一步研究",
]
GENERIC_PHRASES_EN = [
    "plays an important role", "is of great significance", "has important significance",
    "provides a theoretical basis", "provides reference", "lays a foundation",
    "deserves attention", "cannot be ignored", "has broad prospects",
    "further research is needed", "important implications",
]
MECHANISM_TERMS_ZH = [
    "机制", "通路", "受体", "蛋白", "基因", "表达", "调控", "抑制", "激活",
    "膜", "细胞", "炎症", "免疫", "耐药", "浓度", "剂量", "模型", "试验",
    "结果", "作用于", "结合", "破坏", "靶点", "病原", "菌株",
]
MECHANISM_TERMS_EN = [
    "mechanism", "pathway", "receptor", "protein", "gene", "expression", "regulation",
    "inhibit", "activate", "membrane", "cell", "inflammation", "immune", "resistance",
    "concentration", "dose", "model", "assay", "result", "target", "strain",
]
ANCHOR_PATTERNS = (
    re.compile(r"\d+(?:\.\d+)?\s*(?:%|mg|g|kg|ml|l|μg|ug|mm|cm|fold|倍)?", re.IGNORECASE),
    re.compile(r"\\cite[a-zA-Z]*\s*\{"),
    re.compile(r"\[@[\w:.\-]+"),
    re.compile(r"\[[0-9,\-\s;]+\]"),
    re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,}\b"),
)

CNKI_DIMENSIONS = (
    "sentence structure", "paragraph similarity", "information density",
    "connector frequency", "term-context matching",
)
DIMENSION_CODE_TO_NAME = {
    "D1": "sentence structure",
    "D2": "paragraph similarity",
    "D3": "information density",
    "D4": "connector frequency",
    "D5": "term-context matching",
}
DIMENSION_ALIASES = {
    "D1": {"d1", "sentence structure", "sentence length", "sentence length variation", "burstiness"},
    "D2": {"d2", "paragraph similarity", "paragraph structure", "repeated n-gram", "4-gram"},
    "D3": {"d3", "information density", "ttr", "vocabulary diversity"},
    "D4": {"d4", "connector frequency", "connector density", "transition density"},
    "D5": {"d5", "term-context matching", "term context", "structural predictability"},
}

# --- tier-based required dimensions ---
# All tiers still report D1-D5 findings. PASS/FAIL verdict depends on this map.
TIER_REQUIRED_DIMENSIONS = {
    "none": set(),
    "light": {"D1", "D4"},
    "medium": {"D1", "D2", "D3", "D4"},
    "heavy": {"D1", "D2", "D3", "D4", "D5"},
}

# --- configurable threshold profile (Stage 5e) ---

@dataclass
class HumanizeThresholds:
    min_paragraph_chars: int = 50
    min_coverage_ratio: float = 0.5
    coverage_min_paragraphs: int = 2
    sentence_min_chars: int = 5
    sentence_max_chars: int = 300
    min_sentence_length_stddev: float = 6
    max_connector_density: float = 8
    max_paragraph_connector_density: float = 14
    min_info_anchor_density: float = 2.5
    max_generic_density: float = 7
    min_paragraph_length_stddev: float = 25
    max_repeated_start_ratio: float = 0.35
    max_term_generic_context_ratio: float = 0.45
    sentence_length_cv_warning: float = 0.35
    sentence_length_cv_fail: float = 0.25
    adjacent_similarity_mean_warning: float = 0.45
    adjacent_similarity_max_fail: float = 0.65
    max_4gram_count_warning: int = 5
    repeated_4gram_ratio_warning: float = 0.08
    repeated_4gram_ratio_fail: float = 0.15
    ttr_warning_en: float = 0.32
    ttr_fail_en: float = 0.25
    ttr_warning_zh: float = 0.42
    ttr_fail_zh: float = 0.35
    ttr_min_token_count: int = 80

DEFAULT_THRESHOLDS = HumanizeThresholds()

# Mapping from config JSON keys to dataclass attribute names
_THRESHOLD_KEY_MAP: dict[str, str] = {
    "min_sentence_length_stddev": "min_sentence_length_stddev",
    "sentence_length_cv_warning": "sentence_length_cv_warning",
    "sentence_length_cv_fail": "sentence_length_cv_fail",
    "adjacent_similarity_mean_warning": "adjacent_similarity_mean_warning",
    "adjacent_similarity_max_fail": "adjacent_similarity_max_fail",
    "max_4gram_count_warning": "max_4gram_count_warning",
    "repeated_4gram_ratio_warning": "repeated_4gram_ratio_warning",
    "repeated_4gram_ratio_fail": "repeated_4gram_ratio_fail",
    "ttr_warning_en": "ttr_warning_en",
    "ttr_fail_en": "ttr_fail_en",
    "ttr_warning_zh": "ttr_warning_zh",
    "ttr_fail_zh": "ttr_fail_zh",
    "max_connector_density": "max_connector_density",
    "max_paragraph_connector_density": "max_paragraph_connector_density",
    "min_info_anchor_density": "min_info_anchor_density",
    "max_generic_density": "max_generic_density",
    "min_paragraph_length_stddev": "min_paragraph_length_stddev",
    "max_repeated_start_ratio": "max_repeated_start_ratio",
    "max_term_generic_context_ratio": "max_term_generic_context_ratio",
}


def load_thresholds(output_dir: Path) -> tuple[HumanizeThresholds, list[str]]:
    """Load threshold overrides from paper_spine_config.json.
    Returns (thresholds, warnings).  Default thresholds are used when no
    config exists or individual keys are missing/invalid.
    """
    thresholds = HumanizeThresholds()
    warnings: list[str] = []
    config_path = output_dir / "paper_spine_config.json"
    if not config_path.exists():
        return thresholds, warnings
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return thresholds, warnings
    overrides = config.get("humanize_thresholds")
    if not isinstance(overrides, dict):
        return thresholds, warnings
    for key, attr in _THRESHOLD_KEY_MAP.items():
        if key not in overrides:
            continue
        value = overrides[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            warnings.append(
                f"humanize_thresholds.{key}: expected int or float, got {type(value).__name__} — using default."
            )
            continue
        if isinstance(value, (int, float)) and value < 0:
            warnings.append(
                f"humanize_thresholds.{key}: negative value ({value}) ignored — using default."
            )
            continue
        setattr(thresholds, attr, float(value) if isinstance(value, float) else int(value))
    unknown = set(overrides.keys()) - set(_THRESHOLD_KEY_MAP.keys())
    for uk in sorted(unknown):
        warnings.append(
            f"humanize_thresholds.{uk}: unknown key — ignored."
        )
    return thresholds, warnings


# --- legacy constant aliases (kept for module-level backward compat) ---
# These are initialised from DEFAULT_THRESHOLDS so they match the defaults.
# Dimension functions now use the *thresholds* parameter instead.
MIN_PARAGRAPH_CHARS = DEFAULT_THRESHOLDS.min_paragraph_chars
MIN_COVERAGE_RATIO = DEFAULT_THRESHOLDS.min_coverage_ratio
COVERAGE_MIN_PARAGRAPHS = DEFAULT_THRESHOLDS.coverage_min_paragraphs
SENTENCE_MIN_CHARS = DEFAULT_THRESHOLDS.sentence_min_chars
SENTENCE_MAX_CHARS = DEFAULT_THRESHOLDS.sentence_max_chars
MIN_SENTENCE_LENGTH_STDDEV = DEFAULT_THRESHOLDS.min_sentence_length_stddev
MAX_CONNECTOR_DENSITY = DEFAULT_THRESHOLDS.max_connector_density
MAX_PARAGRAPH_CONNECTOR_DENSITY = DEFAULT_THRESHOLDS.max_paragraph_connector_density
MIN_INFO_ANCHOR_DENSITY = DEFAULT_THRESHOLDS.min_info_anchor_density
MAX_GENERIC_DENSITY = DEFAULT_THRESHOLDS.max_generic_density
MIN_PARAGRAPH_LENGTH_STDDEV = DEFAULT_THRESHOLDS.min_paragraph_length_stddev
MAX_REPEATED_START_RATIO = DEFAULT_THRESHOLDS.max_repeated_start_ratio
MAX_TERM_GENERIC_CONTEXT_RATIO = DEFAULT_THRESHOLDS.max_term_generic_context_ratio
SENTENCE_LENGTH_CV_WARNING = DEFAULT_THRESHOLDS.sentence_length_cv_warning
SENTENCE_LENGTH_CV_FAIL = DEFAULT_THRESHOLDS.sentence_length_cv_fail
ADJACENT_SIMILARITY_MEAN_WARNING = DEFAULT_THRESHOLDS.adjacent_similarity_mean_warning
ADJACENT_SIMILARITY_MAX_FAIL = DEFAULT_THRESHOLDS.adjacent_similarity_max_fail
MAX_4GRAM_COUNT_WARNING = DEFAULT_THRESHOLDS.max_4gram_count_warning
REPEATED_4GRAM_RATIO_WARNING = DEFAULT_THRESHOLDS.repeated_4gram_ratio_warning
REPEATED_4GRAM_RATIO_FAIL = DEFAULT_THRESHOLDS.repeated_4gram_ratio_fail
TTR_WARNING_EN = DEFAULT_THRESHOLDS.ttr_warning_en
TTR_FAIL_EN = DEFAULT_THRESHOLDS.ttr_fail_en
TTR_WARNING_ZH = DEFAULT_THRESHOLDS.ttr_warning_zh
TTR_FAIL_ZH = DEFAULT_THRESHOLDS.ttr_fail_zh
TTR_MIN_TOKEN_COUNT = DEFAULT_THRESHOLDS.ttr_min_token_count


@dataclass
class DimensionResult:
    code: str
    name: str
    status: str = "PASS"
    metrics: dict[str, float | int | str] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    affected_units: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "PASS"


@dataclass
class HumanizeCheckResult:
    path: str
    ok: bool
    humanize_tier: str = "medium"
    matrix_rows: int = 0
    manuscript_paragraphs: int = 0
    coverage_ratio: float = 0.0
    sentence_length_stddev: float = 0.0
    connector_density: float = 0.0
    dimension_results: dict[str, DimensionResult] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    required_findings: list[str] = field(default_factory=list)
    advisory_findings: list[str] = field(default_factory=list)
    thresholds: dict[str, float | int] = field(default_factory=dict)
    threshold_warnings: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PaperSpine humanize_matrix.md")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write humanize_report.md")
    return parser.parse_args()


def sentence_lengths(text: str) -> list[int]:
    sents = re.split(r"[.。!！?？;；\n]+", text)
    return [
        len(s.strip())
        for s in sents
        if SENTENCE_MIN_CHARS < len(s.strip()) < SENTENCE_MAX_CHARS
    ]


def count_connectors(text: str, lang: str) -> int:
    pool = AI_CONNECTORS_ZH if lang == "zh" else AI_CONNECTORS_EN
    lowered = text.lower()
    return sum(lowered.count(c.lower()) for c in pool)


def per_1k(count: int, text: str) -> float:
    if not text:
        return 0.0
    return round(count / max(len(text) / 1000, 0.001), 2)


def status_from_findings(warnings: int, failures: int) -> str:
    if failures:
        return "FAIL"
    if warnings:
        return "WARNING"
    return "PASS"


def repeated_ratio(items: list[str]) -> float:
    filtered = [item for item in items if item]
    if not filtered:
        return 0.0
    counts = Counter(filtered)
    repeated = sum(count for count in counts.values() if count > 1)
    return round(repeated / len(filtered), 2)


def generic_count(text: str, lang: str) -> int:
    phrases = GENERIC_PHRASES_ZH if lang == "zh" else GENERIC_PHRASES_EN
    lowered = text.lower()
    return sum(lowered.count(phrase.lower()) for phrase in phrases)


def mechanism_count(text: str, lang: str) -> int:
    terms = MECHANISM_TERMS_ZH if lang == "zh" else MECHANISM_TERMS_EN
    lowered = text.lower()
    return sum(lowered.count(term.lower()) for term in terms)


def anchor_count(text: str) -> int:
    return sum(len(pattern.findall(text)) for pattern in ANCHOR_PATTERNS)


def connector_count_by_paragraph(paragraph: str, lang: str) -> int:
    return count_connectors(paragraph, lang)


def dimension_sentence_structure(text: str, lang: str, thresholds: HumanizeThresholds = DEFAULT_THRESHOLDS) -> DimensionResult:
    result = DimensionResult("D1", "sentence structure")
    sentences = _split_sentences(text)
    lengths = [len(sentence) for sentence in sentences]
    if not lengths:
        result.metrics["sentence_count"] = 0
        return result

    warnings = 0
    failures = 0
    starts = [_sentence_start(sentence, lang) for sentence in sentences]
    repeat_ratio = repeated_ratio(starts)
    uniform_runs: list[str] = []
    for index in range(max(0, len(lengths) - 2)):
        window = lengths[index : index + 3]
        if max(window) - min(window) <= 4:
            uniform_runs.append(f"S{index + 1}-S{index + 3}")

    stddev = round(statistics.stdev(lengths), 2) if len(lengths) > 1 else 0.0
    mean_len = round(statistics.mean(lengths), 2) if len(lengths) > 1 else 0.0
    cv = round(stddev / mean_len, 3) if mean_len > 0 and len(lengths) > 1 else 0.0
    short_ratio = round(sum(1 for length in lengths if length < 18) / len(lengths), 2)
    long_ratio = round(sum(1 for length in lengths if length > 80) / len(lengths), 2)
    result.metrics.update(
        {
            "sentence_count": len(sentences),
            "length_stddev": stddev,
            "sentence_length_cv": cv,
            "repeated_start_ratio": repeat_ratio,
            "uniform_length_runs": len(uniform_runs),
            "short_sentence_ratio": short_ratio,
            "long_sentence_ratio": long_ratio,
        }
    )

    if len(lengths) > 2 and stddev < thresholds.min_sentence_length_stddev:
        failures += 1
        result.findings.append(
            f"D1 sentence lengths are too uniform: stddev {stddev} < {thresholds.min_sentence_length_stddev}."
        )
    if len(lengths) >= 3 and cv < thresholds.sentence_length_cv_fail and cv > 0:
        failures += 1
        result.findings.append(
            f"D1 sentence length CV is critically low: {cv} < {thresholds.sentence_length_cv_fail}. "
            "Sentence rhythm is too uniform — vary short, medium, and long sentences."
        )
    elif len(lengths) >= 3 and cv < thresholds.sentence_length_cv_warning and cv > 0:
        warnings += 1
        result.findings.append(
            f"D1 sentence length CV is low: {cv} < {thresholds.sentence_length_cv_warning}. "
            "Sentence rhythm is somewhat uniform — consider mixing sentence lengths."
        )
    if repeat_ratio > thresholds.max_repeated_start_ratio:
        failures += 1 if repeat_ratio >= 0.5 else 0
        warnings += 0 if repeat_ratio >= 0.5 else 1
        result.findings.append(f"D1 sentence openings repeat too often: {repeat_ratio:.0%}.")
    if uniform_runs:
        warnings += 1
        result.findings.append(f"D1 consecutive sentences have near-identical lengths: {uniform_runs[:5]}.")
        result.affected_units.extend(uniform_runs[:5])
    if short_ratio < 0.1 and long_ratio < 0.1 and len(sentences) >= 6:
        warnings += 1
        result.findings.append("D1 sentence mix lacks both short and long sentences.")

    result.status = status_from_findings(warnings, failures)
    return result


def _extract_4grams(text: str, lang: str) -> list[str]:
    """Extract token-level 4-grams from text.

    English: split by words, produce 4-word n-grams.
    Chinese: split contiguous Chinese characters into 4-char n-grams.
    """
    if lang == "en":
        words = re.findall(r"[A-Za-z]+", text.lower())
        return [" ".join(words[i : i + 4]) for i in range(max(0, len(words) - 3))]
    # Chinese: extract contiguous Chinese-character runs, slide 4-char windows
    grams: list[str] = []
    for run in re.findall(r"[一-鿿]{4,}", text):
        for i in range(len(run) - 3):
            grams.append(run[i : i + 4])
    return grams


def _ttr_tokens(text: str, lang: str) -> list[str]:
    """Tokenize text for TTR calculation.

    English: word tokens (alphabetic sequences).
    Chinese: 2-gram character tokens from contiguous Chinese-character runs.
    """
    if lang == "en":
        return [w.lower() for w in re.findall(r"[A-Za-z]+", text)]
    tokens: list[str] = []
    for run in re.findall(r"[一-鿿]+", text):
        for i in range(len(run) - 1):
            tokens.append(run[i : i + 2])
    return tokens


def _check_repeated_4grams(result: DimensionResult, text: str, lang: str, thresholds: HumanizeThresholds = DEFAULT_THRESHOLDS) -> tuple[int, int]:
    """Detect repeated 4-grams in the full text. Mutates result.metrics and result.findings in place.

    Returns (warnings, failures) to be incorporated into the dimension status.
    """
    w = 0
    f = 0
    all_grams = _extract_4grams(text, lang)
    if all_grams:
        gram_counts = Counter(all_grams)
        repeated = {gram: count for gram, count in gram_counts.items() if count >= 2}
        max_count = max(repeated.values()) if repeated else 0
        total_grams = len(all_grams)
        repeated_instances = sum(count - 1 for count in repeated.values())
        gram_ratio = round(repeated_instances / total_grams, 4) if total_grams > 0 else 0.0
    else:
        max_count = 0
        gram_ratio = 0.0
        total_grams = 0
    result.metrics["max_4gram_count"] = max_count
    result.metrics["repeated_4gram_ratio"] = gram_ratio
    if max_count >= thresholds.max_4gram_count_warning and total_grams >= 20:
        if gram_ratio > thresholds.repeated_4gram_ratio_fail:
            f += 1
            result.findings.append(
                f"D2 repeated 4-gram ratio is high: {gram_ratio:.3f} > {thresholds.repeated_4gram_ratio_fail} "
                f"(max repeat count {max_count})."
            )
        elif gram_ratio > thresholds.repeated_4gram_ratio_warning:
            w += 1
            result.findings.append(
                f"D2 repeated 4-gram ratio is elevated: {gram_ratio:.3f} > {thresholds.repeated_4gram_ratio_warning} "
                f"(max repeat count {max_count})."
            )
        elif max_count >= thresholds.max_4gram_count_warning:
            w += 1
            result.findings.append(
                f"D2 repeated 4-gram found {max_count} occurrences of same phrase — consider rephrasing."
            )
    return w, f


def dimension_paragraph_similarity(text: str, lang: str, thresholds: HumanizeThresholds = DEFAULT_THRESHOLDS) -> DimensionResult:
    result = DimensionResult("D2", "paragraph similarity")
    paragraphs = _split_paragraphs(text)
    lengths = [len(paragraph) for paragraph in paragraphs]
    result.metrics["paragraph_count"] = len(paragraphs)

    # 4-gram check runs on the full text regardless of paragraph count
    gram_w, gram_f = _check_repeated_4grams(result, text, lang, thresholds)

    if len(paragraphs) < 2:
        result.status = status_from_findings(gram_w, gram_f)
        return result

    warnings = gram_w
    failures = gram_f
    starts = [
        re.sub(r"^[\s\"'\"\"''（([【\[]+", "", paragraph).strip()[:12]
        if lang == "zh"
        else " ".join(re.findall(r"[A-Za-z]+", paragraph.lower())[:2])
        for paragraph in paragraphs
    ]
    repeat_ratio = repeated_ratio(starts)
    stddev = round(statistics.stdev(lengths), 2) if len(lengths) > 1 else 0.0
    result.metrics.update(
        {
            "paragraph_length_stddev": stddev,
            "repeated_opening_ratio": repeat_ratio,
            "min_paragraph_length": min(lengths),
            "max_paragraph_length": max(lengths),
        }
    )

    if len(paragraphs) > 2 and stddev < thresholds.min_paragraph_length_stddev:
        warnings += 1
        result.findings.append(
            f"D2 paragraph lengths are unusually even: stddev {stddev} < {thresholds.min_paragraph_length_stddev}."
        )
    if repeat_ratio > thresholds.max_repeated_start_ratio:
        failures += 1 if repeat_ratio >= 0.5 else 0
        warnings += 0 if repeat_ratio >= 0.5 else 1
        result.findings.append(f"D2 paragraph openings repeat too often: {repeat_ratio:.0%}.")
        repeated = [start for start, count in Counter(starts).items() if start and count > 1]
        result.affected_units.extend(repeated[:5])

    template_hits = []
    generic_starts = ("本文", "本研究", "此外", "因此", "首先", "其次") if lang == "zh" else (
        "this study", "this review", "furthermore", "therefore", "firstly", "secondly"
    )
    lowered = [paragraph.lower() for paragraph in paragraphs]
    for index, paragraph in enumerate(lowered, start=1):
        if any(paragraph.startswith(start.lower()) for start in generic_starts):
            template_hits.append(f"P{index}")
    if len(template_hits) >= max(2, len(paragraphs) // 2):
        warnings += 1
        result.findings.append(f"D2 repeated paragraph-level template openings: {template_hits[:8]}.")
        result.affected_units.extend(template_hits[:8])

    # --- adjacent paragraph similarity (difflib, first 300 chars) ---
    adj_sims: list[float] = []
    similar_pairs: list[str] = []
    for i in range(len(paragraphs) - 1):
        a = paragraphs[i][:300]
        b = paragraphs[i + 1][:300]
        sim = difflib.SequenceMatcher(None, a, b).ratio()
        adj_sims.append(sim)
        if sim > thresholds.adjacent_similarity_max_fail:
            similar_pairs.append(f"P{i + 1}-P{i + 2}")
    adj_mean = round(statistics.mean(adj_sims), 3) if adj_sims else 0.0
    adj_max = round(max(adj_sims), 3) if adj_sims else 0.0
    result.metrics["adjacent_paragraph_similarity_mean"] = adj_mean
    result.metrics["adjacent_paragraph_similarity_max"] = adj_max
    if adj_max > thresholds.adjacent_similarity_max_fail:
        failures += 1
        result.findings.append(
            f"D2 adjacent paragraphs are near-duplicates (similarity {adj_max} > {thresholds.adjacent_similarity_max_fail}): "
            f"{similar_pairs[:8]}."
        )
        result.affected_units.extend(similar_pairs[:8])
    elif adj_mean > thresholds.adjacent_similarity_mean_warning:
        warnings += 1
        result.findings.append(
            f"D2 adjacent paragraph similarity is elevated: mean {adj_mean} > {thresholds.adjacent_similarity_mean_warning}."
        )

    result.status = status_from_findings(warnings, failures)
    return result


def dimension_information_density(text: str, lang: str, thresholds: HumanizeThresholds = DEFAULT_THRESHOLDS) -> DimensionResult:
    result = DimensionResult("D3", "information density")
    if not text.strip():
        return result

    warnings = 0
    failures = 0
    generic = generic_count(text, lang)
    anchors = anchor_count(text)
    mechanisms = mechanism_count(text, lang)
    generic_density = per_1k(generic, text)
    anchor_density = per_1k(anchors + mechanisms, text)
    result.metrics.update(
        {
            "generic_phrase_density": generic_density,
            "information_anchor_density": anchor_density,
            "generic_phrase_count": generic,
            "anchor_count": anchors,
            "mechanism_term_count": mechanisms,
        }
    )

    # --- TTR information density ---
    tokens = _ttr_tokens(text, lang)
    token_count = len(tokens)
    unique_token_count = len(set(tokens))
    ttr = round(unique_token_count / token_count, 4) if token_count > 0 else 0.0
    result.metrics["ttr"] = ttr
    result.metrics["token_count"] = token_count
    result.metrics["unique_token_count"] = unique_token_count

    if token_count >= thresholds.ttr_min_token_count:
        ttr_warn = thresholds.ttr_warning_zh if lang == "zh" else thresholds.ttr_warning_en
        ttr_fail = thresholds.ttr_fail_zh if lang == "zh" else thresholds.ttr_fail_en
        if ttr < ttr_fail:
            failures += 1
            result.findings.append(
                f"D3 TTR information density is critically low: {ttr} < {ttr_fail}. "
                "Text has excessive word repetition — introduce more varied vocabulary."
            )
        elif ttr < ttr_warn:
            warnings += 1
            result.findings.append(
                f"D3 TTR information density is low: {ttr} < {ttr_warn}. "
                "Consider using more diverse vocabulary."
            )

    if generic_density > thresholds.max_generic_density:
        failures += 1
        result.findings.append(
            f"D3 generic phrase density is high: {generic_density}/1k chars > {thresholds.max_generic_density}."
        )
    elif generic_density > thresholds.max_generic_density * 0.6:
        warnings += 1
        result.findings.append(f"D3 generic phrase density is elevated: {generic_density}/1k chars.")

    if len(text) > 500 and anchor_density < thresholds.min_info_anchor_density:
        warnings += 1
        result.findings.append(
            f"D3 information anchors are sparse: {anchor_density}/1k chars < {thresholds.min_info_anchor_density}."
        )

    paragraphs = _split_paragraphs(text)
    affected = []
    for index, paragraph in enumerate(paragraphs, start=1):
        if generic_count(paragraph, lang) >= 2 and anchor_count(paragraph) + mechanism_count(paragraph, lang) == 0:
            affected.append(f"P{index}")
    if affected:
        warnings += 1
        result.findings.append(f"D3 generic low-anchor paragraphs: {affected[:8]}.")
        result.affected_units.extend(affected[:8])

    result.status = status_from_findings(warnings, failures)
    return result


def dimension_connector_frequency(text: str, lang: str, thresholds: HumanizeThresholds = DEFAULT_THRESHOLDS) -> DimensionResult:
    result = DimensionResult("D4", "connector frequency")
    if not text.strip():
        return result

    warnings = 0
    failures = 0
    total = count_connectors(text, lang)
    density = per_1k(total, text)
    paragraphs = _split_paragraphs(text)
    dense_paragraphs: list[str] = []
    max_para_density = 0.0
    for index, paragraph in enumerate(paragraphs, start=1):
        para_density = per_1k(connector_count_by_paragraph(paragraph, lang), paragraph)
        max_para_density = max(max_para_density, para_density)
        if para_density > thresholds.max_paragraph_connector_density:
            dense_paragraphs.append(f"P{index}")

    result.metrics.update(
        {
            "connector_count": total,
            "connector_density": density,
            "max_paragraph_connector_density": round(max_para_density, 2),
        }
    )

    if density > thresholds.max_connector_density:
        failures += 1
        result.findings.append(
            f"D4 connector density is high: {density}/1k chars > {thresholds.max_connector_density}."
        )
    if dense_paragraphs:
        warnings += 1
        result.findings.append(f"D4 connector use is concentrated in paragraphs: {dense_paragraphs[:8]}.")
        result.affected_units.extend(dense_paragraphs[:8])

    result.status = status_from_findings(warnings, failures)
    return result


def _candidate_terms(text: str, lang: str) -> list[str]:
    if lang == "en":
        words = [w.lower() for w in re.findall(r"\b[A-Za-z][A-Za-z-]{4,}\b", text)]
        stop = {
            "study", "review", "research", "important", "significant", "therefore",
            "however", "because", "results", "future", "paper", "these", "those",
        }
        return [word for word in words if word not in stop]

    sequences = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    grams: list[str] = []
    stop = {
        "本文", "研究", "重要", "意义", "作用", "因此", "此外", "首先", "其次",
        "最后", "综上", "相关", "提供", "基础", "进一步",
    }
    for seq in sequences:
        for size in (2, 3, 4):
            for index in range(0, max(0, len(seq) - size + 1)):
                gram = seq[index : index + size]
                if gram not in stop:
                    grams.append(gram)
    return grams


def dimension_term_context(text: str, lang: str, thresholds: HumanizeThresholds = DEFAULT_THRESHOLDS) -> DimensionResult:
    result = DimensionResult("D5", "term-context matching")
    if not text.strip():
        return result

    warnings = 0
    failures = 0
    counts = Counter(_candidate_terms(text, lang))
    terms = [term for term, count in counts.most_common(12) if count >= 3]
    risky_terms: list[str] = []
    checked_contexts = 0
    generic_contexts = 0
    mechanism_contexts = 0
    for term in terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        positions = [match.start() for match in pattern.finditer(text)]
        if not positions:
            continue
        term_generic = 0
        term_mechanism = 0
        for position in positions[:8]:
            window = text[max(0, position - 35) : position + len(term) + 35]
            checked_contexts += 1
            has_generic = generic_count(window, lang) > 0
            has_mechanism = mechanism_count(window, lang) > 0 or anchor_count(window) > 0
            if has_generic:
                term_generic += 1
                generic_contexts += 1
            if has_mechanism:
                term_mechanism += 1
                mechanism_contexts += 1
        if term_generic and term_mechanism == 0:
            risky_terms.append(term)

    ratio = round(generic_contexts / checked_contexts, 2) if checked_contexts else 0.0
    result.metrics.update(
        {
            "frequent_terms_checked": len(terms),
            "contexts_checked": checked_contexts,
            "generic_context_ratio": ratio,
            "mechanism_contexts": mechanism_contexts,
            "risky_terms": ", ".join(risky_terms[:8]),
        }
    )

    if ratio > thresholds.max_term_generic_context_ratio and mechanism_contexts == 0:
        failures += 1
        result.findings.append(
            f"D5 frequent terms appear in generic contexts without mechanism anchors: ratio {ratio:.0%}."
        )
    elif risky_terms:
        warnings += 1
        result.findings.append(f"D5 terms need more specific context: {risky_terms[:8]}.")
        result.affected_units.extend(risky_terms[:8])

    result.status = status_from_findings(warnings, failures)
    return result


def evaluate_dimensions(text: str, lang: str, thresholds: HumanizeThresholds = DEFAULT_THRESHOLDS) -> dict[str, DimensionResult]:
    dimensions = [
        dimension_sentence_structure(text, lang, thresholds),
        dimension_paragraph_similarity(text, lang, thresholds),
        dimension_information_density(text, lang, thresholds),
        dimension_connector_frequency(text, lang, thresholds),
        dimension_term_context(text, lang, thresholds),
    ]
    return {dimension.code: dimension for dimension in dimensions}


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def check_matrix(matrix_path: Path, manuscript_text: str, lang: str, humanize_tier: str = "medium", thresholds: HumanizeThresholds | None = None, threshold_warnings: list[str] | None = None) -> HumanizeCheckResult:
    """Evaluate humanize output with tier-aware hard gates.

    Light tier hard-gates only structural validity plus D1/D4 FAIL findings.
    D1/D4 WARNING findings and all D2/D3/D5 findings remain visible as
    advisory so the report is useful without blocking a light pass.
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    if threshold_warnings is None:
        threshold_warnings = []

    result = HumanizeCheckResult(str(matrix_path), False)
    result.humanize_tier = humanize_tier
    result.thresholds = {
        k: getattr(thresholds, k) for k in _THRESHOLD_KEY_MAP.values()
        if hasattr(thresholds, k)
    }
    result.threshold_warnings = list(threshold_warnings)

    structural_required: list[str] = []
    structural_advisory: list[str] = []
    required_set = TIER_REQUIRED_DIMENSIONS.get(humanize_tier, TIER_REQUIRED_DIMENSIONS["medium"])

    if not matrix_path.exists():
        structural_required.append("humanize_matrix.md not found")
        result.required_findings = structural_required
        result.findings = list(structural_required)
        return result

    text = matrix_path.read_text(encoding="utf-8", errors="ignore")
    header, rows = _table_rows(text)
    if not header:
        structural_required.append("humanize_matrix.md has no parseable table")
        result.required_findings = structural_required
        result.findings = list(structural_required)
        return result

    result.matrix_rows = len(rows)
    result.manuscript_paragraphs = len(_split_paragraphs(manuscript_text))
    if result.manuscript_paragraphs > 0:
        result.coverage_ratio = result.matrix_rows / result.manuscript_paragraphs

    if (
        result.coverage_ratio < thresholds.min_coverage_ratio
        and result.manuscript_paragraphs > thresholds.coverage_min_paragraphs
    ):
        coverage_finding = (
            f"Coverage {result.coverage_ratio:.0%}: {result.matrix_rows} rows for "
            f"{result.manuscript_paragraphs} paragraphs. Minimum {thresholds.min_coverage_ratio:.0%}."
        )
        if humanize_tier in {"medium", "heavy"}:
            structural_required.append(coverage_finding)
        else:
            structural_advisory.append(coverage_finding)

    header_text = " ".join(c.lower() for c in header)
    for col in ("ai pattern", "detection dim", "severity", "applied change", "teaching"):
        if col not in header_text:
            structural_required.append(f"Missing column: {col}")

    empty_rows = [i for i, row in enumerate(rows, start=1) if any(not c.strip() for c in row)]
    if empty_rows:
        structural_required.append(f"Rows with empty cells: {empty_rows[:8]}")

    severity_counts = {"high": 0, "medium": 0, "low": 0}
    dim_hits: set[str] = set()
    for row in rows:
        joined = " ".join(row).lower()
        for sev in severity_counts:
            if sev in joined:
                severity_counts[sev] += 1
        for code, aliases in DIMENSION_ALIASES.items():
            if any(alias in joined for alias in aliases):
                dim_hits.add(code)

    if result.matrix_rows > 2 and severity_counts["high"] == 0:
        high_finding = "No high-severity patterns found - matrix may be under-reporting"
        if humanize_tier in {"medium", "heavy"}:
            structural_required.append(high_finding)
        else:
            structural_advisory.append(high_finding)

    required_missing = sorted(DIMENSION_CODE_TO_NAME[code] for code in required_set if code not in dim_hits)
    advisory_missing = sorted(
        DIMENSION_CODE_TO_NAME[code]
        for code in DIMENSION_CODE_TO_NAME
        if code not in dim_hits and code not in required_set
    )
    if required_missing:
        structural_required.append(f"Required dimensions not covered: {', '.join(required_missing)}")
    if advisory_missing and humanize_tier in {"medium", "heavy"}:
        structural_advisory.append(f"Advisory dimensions not covered: {', '.join(advisory_missing)}")

    lengths = sentence_lengths(manuscript_text)
    if len(lengths) > 2:
        result.sentence_length_stddev = round(statistics.stdev(lengths), 2)
        if result.sentence_length_stddev < thresholds.min_sentence_length_stddev:
            structural_required.append(
                f"Sentence length stddev = {result.sentence_length_stddev} - too uniform. "
                f"AI text typically < {thresholds.min_sentence_length_stddev}; human text > 10."
            )

    char_count = len(manuscript_text)
    conn_count = count_connectors(manuscript_text, lang)
    if char_count > 0:
        result.connector_density = round(conn_count / (char_count / 1000), 2)
        if result.connector_density > thresholds.max_connector_density:
            structural_required.append(
                f"Connector density = {result.connector_density}/1k chars "
                f"(threshold: {thresholds.max_connector_density}). High connector density is a strong AI signal."
            )

    if re.search(r"(?m)^\s*(?:[-—–―]\s*){3,}$", manuscript_text):
        structural_required.append(
            "Long dash separators detected (e.g. '---' or '———'). "
            "These are a strong AI-generation signal - replace with section headings or blank lines."
        )

    result.dimension_results = evaluate_dimensions(manuscript_text, lang, thresholds)
    required_dim: list[str] = []
    advisory_dim: list[str] = []
    for dimension in result.dimension_results.values():
        if dimension.status == "PASS":
            continue
        if dimension.code in required_set and dimension.status == "FAIL":
            required_dim.extend(dimension.findings)
        else:
            advisory_dim.extend(dimension.findings)

    result.required_findings = dedupe(structural_required + required_dim)
    result.advisory_findings = dedupe(structural_advisory + advisory_dim)
    result.findings = dedupe(structural_required + required_dim + structural_advisory + advisory_dim)
    result.ok = not result.required_findings
    return result


def to_markdown(result: HumanizeCheckResult) -> str:
    lines = [
        "# Humanize Check Report",
        "",
        f"- Matrix path: `{result.path}`",
        f"- Humanize tier: {result.humanize_tier}",
        f"- Matrix rows: {result.matrix_rows}",
        f"- Manuscript paragraphs: {result.manuscript_paragraphs}",
        f"- Coverage: {result.coverage_ratio:.0%}",
        f"- Sentence length stddev: {result.sentence_length_stddev}",
        f"- Connector density: {result.connector_density}/1k chars",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        "",
        "## Dimension Scores",
        "",
    ]

    required_set = TIER_REQUIRED_DIMENSIONS.get(result.humanize_tier, TIER_REQUIRED_DIMENSIONS["medium"])

    if result.dimension_results:
        for dimension in result.dimension_results.values():
            tag = "[required]" if dimension.code in required_set else "[advisory]"
            lines.append(f"### {dimension.code} {dimension.name}: {dimension.status} {tag}")
            if dimension.metrics:
                metric_text = ", ".join(f"{key}={value}" for key, value in dimension.metrics.items())
                lines.append(f"- Metrics: {metric_text}")
            if dimension.affected_units:
                lines.append(f"- Affected units: {', '.join(dimension.affected_units[:10])}")
            if dimension.findings:
                lines.extend(f"- {finding}" for finding in dimension.findings)
            else:
                lines.append("- No dimension-specific risk found.")
            lines.append("")
    else:
        lines.append("- None")
        lines.append("")

    lines.extend([
        "## Required Findings",
        "",
    ])
    lines.extend(f"- {f}" for f in result.required_findings) if result.required_findings else lines.append("- None")
    lines.append("")

    lines.extend([
        "## Advisory Findings",
        "",
    ])
    lines.extend(f"- {f}" for f in result.advisory_findings) if result.advisory_findings else lines.append("- None")
    lines.append("")

    # Threshold Profile
    lines.extend([
        "## Threshold Profile",
        "",
    ])
    if result.thresholds:
        for key in sorted(result.thresholds.keys()):
            lines.append(f"- {key}: {result.thresholds[key]}")
    else:
        lines.append("- Using built-in defaults.")
    lines.append("")

    if result.threshold_warnings:
        lines.extend([
            "## Threshold Warnings",
            "",
        ])
        lines.extend(f"- {w}" for w in result.threshold_warnings)
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    matrix_path = out_dir / "humanize_matrix.md"

    if not matrix_path.exists():
        print(f"Matrix not found: {matrix_path}", file=sys.stderr)
        return 2

    lang = "zh"
    humanize_tier = "medium"
    config_path = out_dir / "paper_spine_config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            lang = config.get("output_language", "zh")
            humanize_tier = config.get("humanize_tier", "medium")
            if humanize_tier not in ("none", "light", "medium", "heavy"):
                humanize_tier = "medium"
        except json.JSONDecodeError:
            pass

    manuscript_text = ""
    final_paper = out_dir / "final_paper"
    if final_paper.is_dir():
        for f in final_paper.glob("*.tex"):
            manuscript_text += f.read_text(encoding="utf-8", errors="ignore") + "\n"

    thresholds, threshold_warnings = load_thresholds(out_dir)
    result = check_matrix(matrix_path, manuscript_text, lang, humanize_tier, thresholds, threshold_warnings)

    if args.json:
        print(json.dumps({
            "ok": result.ok, "humanize_tier": result.humanize_tier,
            "matrix_rows": result.matrix_rows,
            "paragraphs": result.manuscript_paragraphs,
            "coverage": result.coverage_ratio,
            "sentence_stddev": result.sentence_length_stddev,
            "connector_density": result.connector_density,
            "dimension_results": {
                code: asdict(dimension) for code, dimension in result.dimension_results.items()
            },
            "findings": result.findings,
            "required_findings": result.required_findings,
            "advisory_findings": result.advisory_findings,
            "thresholds": result.thresholds,
            "threshold_warnings": result.threshold_warnings,
        }, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(to_markdown(result))

    if args.write:
        report_path = out_dir / "humanize_report.md"
        report_path.write_text(to_markdown(result), encoding="utf-8")
        print(f"Wrote {report_path}", file=sys.stderr)

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
