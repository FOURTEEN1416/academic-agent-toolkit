---
name: comp-final-audit
description: Use when a mathematical modeling competition workflow needs a final manifest-backed audit of evidence, gates, reviews, and delivery files.
---

# Competition Final Audit

Read the persisted workflow report, manifests, gate results, review verdicts, and final PDF. Write `AUDIT_REPORT.json` with this machine-readable contract: `workflow_id` (string), non-empty `artifacts` (`path` plus 64-character `sha256`), `gate_outcomes` (each required gate exactly `pass`), `waivers` (array), and `delivery_decision` (`ready` only when all required gates pass). Never mark delivery ready when a required gate is missing, a waiver is undocumented, or fatal findings remain.
