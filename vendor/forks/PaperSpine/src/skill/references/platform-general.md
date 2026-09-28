# General AIGC Risk Strategy (Default / Unknown Platform)

This document defines the **default conservative strategy** for manuscripts
where the target AIGC detection platform is unknown, or when targeting
general-purpose detectors (Turnitin-like, GPT-detector-like, or other commercial
AIGC checkers).  It does **not** target any single commercial detector's
internal algorithm.

## Dimension Mapping

| Platform risk dimension | Machine-checkable PaperSpine metric | Revision strategy |
|---|---|---|
| Burstiness / sentence variety is too low | D1 `sentence_length_stddev`, `sentence_length_cv`, `short_sentence_ratio`, `long_sentence_ratio` | Mix short, medium, and long sentences. Ensure both short (< 18 char) and long (> 80 char) sentences appear. Vary sentence openings. |
| Paragraph template similarity | D2 `adjacent_paragraph_similarity_mean`, `adjacent_paragraph_similarity_max`, `paragraph_length_stddev` | Use varied paragraph structures. Avoid repeating the same opening phrase across paragraphs. Vary paragraph length. |
| Lexical diversity is too low | D3 `ttr`, `token_count`, `unique_token_count` | Expand vocabulary range. Reduce word/phrase repetition. Remove filler phrases and replace with specific terminology. |
| Transition / connector overuse | D4 `connector_density`, `max_paragraph_connector_density` | Reduce explicit discourse markers. Use semantic transitions. |
| Generic term context | D5 `generic_context_ratio`, `risky_terms` | Anchor key terms with mechanism descriptions, quantitative data, experimental conditions, or citations. |

## When To Use This Profile

- The user has not specified a target AIGC detection platform.
- The manuscript will be submitted to a venue that uses an unspecified or
  multi-vendor detection pipeline.
- Cross-platform compatibility is the primary goal.

## Tier Guidance

- **light**: D1 + D4.
- **medium**: D1 + D2 + D3 + D4 (recommended default for general use).
- **heavy**: D1–D5.

## Post-Detection Calibration

Without a specific platform to calibrate against, use `humanize_report.md`
dimension scores as the primary signal.  If a detector score becomes available
later, record it in `humanize_calibration/platform_runs.md` with
`platform=general` and the detector name.

**Do not:**
- Claim this profile targets any specific commercial detector's internals.
- Promise that a manuscript will pass any specific AIGC detector.
- Output a fabricated "AI detection rate" or percentage.
