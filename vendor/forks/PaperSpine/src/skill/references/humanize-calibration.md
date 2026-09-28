# Humanize Calibration Workflow

## Purpose

Calibrate `humanize_check.py` detection thresholds against real platform
detection results.  Thresholds are **not** derived from guesswork about any
vendor's internal algorithm — they must be adjusted based on actual back-testing
across multiple manuscripts.

## What the User Must Provide

- **Platform name**: CNKI / Weipu / General / other
- **Detection date**: ISO date
- **Detection score or risk level**: as reported by the platform
- **`humanize_tier`** used: light / medium / heavy
- **`humanize_report.md`** from the revision run
- **Manuscript metadata**: word count, language, discipline
- **Manual post-revision editing**: yes / no

## Recording Format

`humanize_calibration/platform_runs.md`:

| Date | Platform | Language | Discipline | Tier | Detector score/risk | D1 status | D2 status | D3 status | D4 status | D5 status | Residual issue | Threshold note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Calibration Principles

1. A single result does not justify a global threshold change. Accumulate
   multiple runs on the same platform/language/discipline first.
2. Adjust WARNING thresholds before FAIL thresholds.
3. Every threshold change must be documented with reason, old/new values,
   supporting run count, and date.
4. Do not promise that adjusted thresholds will pass any detector.

## Current Threshold Location

Default thresholds live in `DEFAULT_THRESHOLDS` (the `HumanizeThresholds`
dataclass) in `humanize_check.py`. At runtime `load_thresholds()` reads
per-run overrides from the `humanize_thresholds` block of
`paper_spine_config.json`; missing, non-numeric, negative, or unknown keys
fall back to the defaults and emit a warning. Edit the defaults in code for a
permanent change, or set `humanize_thresholds` in the config to override a
single run without touching the script.
