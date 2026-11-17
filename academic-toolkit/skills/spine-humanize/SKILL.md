---
name: spine-humanize
description: "Reduces AI detection rates via tiered stylistic constraints mapped to real AIGC detection dimensions. Produces a teaching matrix of applied constraints."
---


<!--ACAT-ADAPTED: 资产回填自 WUBING2023/PaperSpine@1fe46f0e76aa（单技能拆分重组编排）。溯源见 references/UPSTREAM.md。2026-09-09 专项治理。-->
# PaperSpine Humanize

**Self-contained skill** — can be used standalone on any academic text, or as
part of the PaperSpine suite.  Applies tier-specific writing constraints based
on real AIGC detection dimensions and produces a teaching matrix that documents
every change.

## When To Use

- In PaperSpine: auto-invoked by rewrite/build when `humanize_tier` is not `none`
- Standalone: invoke directly on any academic text that needs AI detection reduction

## Configuration

Read `paper_spine_config.json` for `humanize_tier` (none/light/medium/heavy)
and `output_language` (zh/en).  When used standalone, default to `medium` / `zh`
if no config found.

## Required Output: humanize_matrix.md

This is the **primary deliverable** — produce `paper_rewriting_output/humanize_matrix.md`.
Every humanization change must be recorded, not applied silently:

| Row ID | Manuscript Unit | AI Pattern Found | Detection Dim | Severity | Applied Change | Expected Effect | Teaching Note |
|--------|----------------|------------------|---------------|----------|---------------|-----------------|---------------|

- **Manuscript Unit**: paragraph number or section name
- **AI Pattern Found**: specific AI feature detected
- **Detection Dim**: D1-D5 (see reference document)
- **Severity**: High (>50% contribution to detection) / Medium (20-50%) / Low (<20%)
- **Applied Change**: what specific change was made
- **Expected Effect**: which dimension this reduces
- **Teaching Note**: why detectors flag this pattern

### Matrix Rules

- Write rows **during writing**, one per unit processed — not after the fact
- At least one row per writing unit for D1 (sentence length)
- At least one row per paragraph for D2 (paragraph structure)
- At least one row per connector replaced (D4)
- At least one row per density adjustment (D3, medium+)
- At least one row per term substitution (D5, heavy only)
- Fill all 8 columns for every row — no empty cells

## Boundaries And Honest No-Op

The capability is restoring the author's own scholarly voice while preserving
scientific meaning — removing empty framing, mechanical paragraph roles,
unsupported evaluative language, false polish, and repeated scaffolding. It is
not mechanical evasion, and its results are diagnostics, not verdicts:

- Do not promise a pass on any specific AIGC detector or output a fabricated
  "AI rate" / percentage.
- Do not optimize prose against a classifier or a word blacklist; pattern
  matches alone do not force a change.
- Clear, accurate, section-appropriate text is a legitimate no-op even when it
  uses a common connector, repeated procedural syntax, or low sentence-length
  variance. Record a no-op row rather than inventing a change; a no-op is
  precision evidence, not a missed opportunity to lower a score.
- Do not add errors, slang, rhetorical questions, first person, or
  sentence-length variation merely to look human.
- Do not use multi-hop translation or back-translation as the final rewrite.
- Preserve the author's meaning, terminology, evidence, and claim strength;
  compare revised meaning against the original rather than chasing a metric.

## Instructions

Read `references/humanize-tiers-{output_language}.md` for the complete
tier-specific directives mapped to the 5 detection dimensions:
D1-Sentence Length / D2-Paragraph Structure / D3-Information Density /
D4-Connector Frequency / D5-Term-Context Matching.

**Fallback when the reference file is missing:** `humanize-tiers-{en,zh}.md`
is not present in this repository (registered as missing upstream in
`spine/references/UPSTREAM.md`). If the file cannot be found, apply the
inlined tier directives below instead of stopping — they are the authoritative
substitute and are aligned with the thresholds enforced by
`scripts/humanize_check.py`.

### Detection Dimensions (D1–D5)

- **D1 — Sentence Structure (sentence length variation / burstiness):** vary
  sentence lengths deliberately; avoid runs of near-identical sentence lengths
  and repeated sentence openings.
- **D2 — Paragraph Structure (paragraph similarity):** vary paragraph lengths;
  avoid template paragraph openings, repeated 4-gram phrases, and
  near-duplicate adjacent paragraphs.
- **D3 — Information Density (vocabulary diversity / info anchors):** keep
  type–token ratio healthy (EN ≥ 0.32, ZH ≥ 0.42 on ≥80-token samples); anchor
  prose with concrete numbers, citations, and named entities instead of
  generic filler.
- **D4 — Connector Frequency:** keep AI-favorite connectors (EN: "however",
  "moreover", "furthermore", "in conclusion"; ZH: "然而", "此外", "综上所述")
  sparse — global density well under ~8 per 1,000 characters and under ~14
  per 1,000 characters in any single paragraph; replace them with concrete
  logical links (data, causality, referential cohesion).
- **D5 — Term-Context Matching:** attach domain terms to specific mechanisms,
  quantities, conditions, and results; avoid pairing technical terms with
  generic, interchangeable context.

### Tier Directives (light / medium / heavy)

| Dim | light | medium | heavy |
|---|---|---|---|
| D1 | Enforce: vary sentence lengths and openings. | Enforce: plus avoid consecutive same-length sentence runs. | Enforce: plus mix short/medium/long rhythm in every paragraph. |
| D2 | Advisory: report findings only. | Enforce: no repeated 4-gram clusters; vary paragraph openings and lengths. | Enforce: plus rewrite near-duplicate adjacent paragraphs. |
| D3 | Advisory: report findings only. | Enforce: add information anchors; purge generic filler sentences. | Enforce: plus raise vocabulary diversity and claim specificity throughout. |
| D4 | Enforce: prune the densest AI connectors. | Enforce: respect global and per-paragraph connector ceilings. | Enforce: plus replace mechanical transitions with content-bearing links. |
| D5 | Advisory: report findings only. | Advisory: report findings only. | Enforce: every term use must carry specific context. |

Required dimensions per tier (`light` = D1+D4, `medium` = D1–D4, `heavy` =
D1–D5) match `TIER_REQUIRED_DIMENSIONS` in `scripts/humanize_check.py`; all
tiers still report D1–D5 findings. Every applied change produces a matrix row:
one row per writing unit for D1, per paragraph for D2, per density adjustment
for D3 (medium+), per connector replaced for D4, and per term substitution
for D5 (heavy only).

## Verification

```bash
# Resolve the script from this repository checkout, not the user's project cwd
# (a bare `python scripts/...` path is the most common reason the command fails).
REPO="$(git rev-parse --show-toplevel)"
python "$REPO/academic-toolkit/skills/spine-humanize/scripts/humanize_check.py" paper_rewriting_output --markdown --write
```

Same-name guard scripts exist in several spine skill directories (registered
in `academic-toolkit/data/duplicate_assets_registry.json`); use this skill's
own copy shown above.

Produces `paper_rewriting_output/humanize_report.md`.  Checks matrix coverage
against total paragraphs, scans sentence-length distribution and connector
density, and flags remaining AI patterns.

## Integration

In PaperSpine: called internally by rewrite and build.  Standalone in this repo:
keep the skill directory in place under `skills/` and invoke via the repo driving protocol.

Scope vs. same-domain skills: this skill is the PaperSpine-pipeline,
tier-driven humanization step (driven by `humanize_tier`, producing
`humanize_matrix.md` plus the `humanize_check.py` guard report). For one-off
de-AI rewriting outside this pipeline, use `paper-humanize`; for Chinese
8-dimension AI-feature diagnosis and competition "AI usage statement"
generation, use `anti-ai-detection`.
