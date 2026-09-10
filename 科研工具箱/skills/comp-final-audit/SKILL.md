---
name: comp-final-audit
description: Use when a mathematical modeling competition workflow needs a final manifest-backed audit of evidence, gates, reviews, and delivery files.
---

# Competition Final Audit

Read the persisted workflow report, manifests, gate results, review verdicts, and final PDF. Write `AUDIT_REPORT.json` with this machine-readable contract: `workflow_id` (string), non-empty `artifacts` (`path` plus 64-character `sha256`), `gate_outcomes` (each required gate exactly `pass`), `waivers` (array), and `delivery_decision` (`ready` only when all required gates pass). Never mark delivery ready when a required gate is missing, a waiver is undocumented, or fatal findings remain.

Delivery conformance (2026-09-11 wiring): check the final PDF against `_utils/cumcm_2026_format.md` (official CUMCM 2026 format-spec digest, verified against the official source): margins ≥2.5cm; electronic version starts at the abstract page (no commitment/ID pages); page numbers from the abstract page, footer center; no TOC; body ≤30 pages; appendix lists support files and full runnable source; no identity information anywhere; single PDF ≤20MB; support archive ≤20MB. Record any violation as a fatal finding.

Companion-skill ledger (2026-09-11, C1 gate companion check): read the per-step execution evidence under `.engine/evidence/` and verify every step that carried `companion_skills` recommendations declared its `companion_skills` decision (used and/or skipped with reasons). List any gap as a finding with the step name; the runner blocks completion before step 14, so a gap here indicates evidence tampering — treat it as fatal.

Integrity anchor (anti-Goodhart, 2026-09-11): every gate, template, and test lives inside the agent's write scope, so internal checks can themselves be gamed by editing the checker. The final `approve` of this step belongs to the human operator; before `delivery_decision=ready`, the operator must verify repo integrity from outside the agent's session: `git status` clean, `git log` reviewed for any contest-window modification to `engine/`, `tests/`, `engine/modex-core/templates.json`, or quality-gate scripts without a logged justification, and optionally `pytest -q` re-run from a fresh clone/worktree. Any unexplained gate-file modification = fatal finding; document the check in `AUDIT_REPORT.json` notes.
