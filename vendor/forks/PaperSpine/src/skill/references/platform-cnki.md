# CNKI-Oriented AIGC Risk Strategy

**Important:** This document is **not** a description of CNKI's internal
algorithm.  It is a PaperSpine revision strategy that maps publicly-known or
experience-based AIGC text risk dimensions to the machine-checkable metrics that
`humanize_check.py` measures.  Final thresholds must be calibrated against
actual CNKI detection results — do not assume any single threshold guarantees a
pass.

## Dimension Mapping

| Platform risk dimension | Machine-checkable PaperSpine metric | Revision strategy |
|---|---|---|
| Sentence-length distribution is too uniform (bell-shaped) | D1 `sentence_length_stddev`, `sentence_length_cv`, `uniform_length_runs` | Mix short (8–15 char), medium (30–50 char), and long (60–120+ char) sentences. Vary sentence openings. Break consecutive same-length runs. |
| Paragraph structure similarity across the manuscript | D2 `adjacent_paragraph_similarity_mean`, `adjacent_paragraph_similarity_max`, paragraph opening repeat ratio | Reorder internal argument flow within paragraphs. Merge short or split long paragraphs. Avoid the same logical template in every paragraph. |
| Template phrase / 4-gram repetition | D2 `max_4gram_count`, `repeated_4gram_ratio` | Delete or rewrite repeated boilerplate phrases. Recast paragraph transitions instead of mechanical synonym swaps. |
| Information density too uniform or too low | D3 `ttr`, `information_anchor_density`, `generic_phrase_density` | Add specific objects, mechanisms, conditions, quantitative data, and citation anchors. Remove filler phrases such as "具有重要意义", "为……奠定基础", "在……的过程中". |
| Connector overuse (explicit discourse markers) | D4 `connector_density`, `max_paragraph_connector_density` | Remove or replace template connectors (首先/其次/此外/综上所述/值得注意的是). Use semantic progression instead of explicit markers. |
| Terms appear only in generic/standard contexts | D5 `generic_context_ratio`, `risky_terms` | Surround high-frequency terms with mechanism descriptions, experimental conditions, quantitative results, or citation support. |

## Tier Guidance for CNKI-Oriented Revision

- **light**: focus on D1 (sentence structure) and D4 (connector frequency).
- **medium**: focus on D1, D2, D3, D4.
- **heavy**: focus on D1–D5.

## Post-Detection Calibration

If a real CNKI detection report returns a risk score that is still high after
revision, record the run in `humanize_calibration/platform_runs.md`.  Do **not**
blindly continue adjusting prose style.  See `references/humanize-calibration.md`
for the calibration workflow.

**Do not:**
- Claim knowledge of CNKI's internal model architecture or training data.
- Promise that a manuscript will pass CNKI AIGC detection.
- Output a fabricated "AI detection rate" or percentage.
