# Weipu-Oriented AIGC Risk Strategy

**Important:** This document is **not** a description of Weipu's internal
algorithm.  PaperSpine treats the dimensions below as higher-priority risks for
Weipu-oriented revision based on publicly-available or experience-based patterns.
Final thresholds must be calibrated against actual Weipu detection results.

## Dimension Mapping

| Platform risk dimension | Machine-checkable PaperSpine metric | Revision strategy |
|---|---|---|
| Chinese academic boilerplate phrases | D3 `generic_phrase_density`, D5 `generic_context_ratio` | Remove phrases such as "具有重要意义", "为……奠定基础", "不仅……而且……". Replace with concrete claims, data, or mechanism descriptions. |
| Sentence-length uniformity | D1 `sentence_length_stddev`, `sentence_length_cv`, `uniform_length_runs` | Mix short, medium, and long sentences. Vary sentence openings. Avoid consecutive sentences of near-identical length. |
| Paragraph-length uniformity | D2 `paragraph_length_stddev` | Vary paragraph lengths. Core analysis paragraphs may be longer; transition or summary paragraphs should be shorter. |
| Connector density (threshold tends tighter for Chinese text) | D4 `connector_density`, `max_paragraph_connector_density` | Remove explicit discourse markers (首先/其次/最后/综上所述). Use logical progression instead. |
| Terms in generic contexts | D5 `risky_terms`, `generic_context_ratio` | Ensure high-frequency academic terms appear near mechanism terms, experimental conditions, or citation anchors. |

## Tier Guidance for Weipu-Oriented Revision

- **light**: focus on D1 and D4.
- **medium**: focus on D1, D2, D3, D4 — recommended minimum.
- **heavy**: focus on D1–D5.

## Post-Detection Calibration

If a real Weipu detection report returns a risk score that is still high after
revision, record the run in `humanize_calibration/platform_runs.md`.  See
`references/humanize-calibration.md`.

**Do not:**
- Claim that Weipu uses a specific model architecture or training dataset.
- Promise that a manuscript will pass Weipu AIGC detection.
- Output a fabricated "AI detection rate" or percentage.
