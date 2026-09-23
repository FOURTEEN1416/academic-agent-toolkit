---
name: comp-final-audit
description: "数模竞赛交付前的最终审计：核对证据链、质量检查结论、审稿记录与交付文件，产出可追溯的审计结论。触发词：交付审计、最终审计、AUDIT_REPORT、交付前检查。"
---

# Competition Final Audit

Read the persisted workflow report, manifests, gate results, review verdicts, and final PDF. Write `AUDIT_REPORT.json` with this machine-readable contract: `workflow_id` (string), non-empty `artifacts` (`path` plus 64-character `sha256`), `gate_outcomes` (each required gate exactly `pass`), `waivers` (array), and `delivery_decision` (`ready` only when all required gates pass). Never mark delivery ready when a required gate is missing, a waiver is undocumented, or fatal findings remain.

Delivery conformance (data-driven per family): read this step's `metadata.compliance_profile` and apply the matching `compliance` block in `engine/modex-core/comp_rules.json` as the machine source of truth — never hardcode one family's caliber for another. **CUMCM profile**: check the final PDF against `_utils/cumcm_2026_format.md` (official CUMCM 2026 format-spec digest, verified against the official source): margins ≥2.5cm; electronic version starts at the abstract page (no commitment/ID pages); page numbers from the abstract page, footer center; no TOC; body ≤30 pages; appendix lists support files and full runnable source; no identity information anywhere; single PDF ≤20MB; support archive ≤20MB. **GMCM (华为杯) profile**: differs on two points that must not be cross-applied — the 承诺书 page is *required* in the electronic submission (`pledge_page: required`), and the body limit is 50 pages (`max_body_pages: 50`, target 40-60 per comp_rules); figure-count floor per `figure_total_range` in the same block. Record any violation as a fatal finding.

Similarity red line: per CUMCM 2026 duplication policy, a paper with either similarity (CNKI literature base or contest self-built base) ≥25% is in principle barred from national review; unofficial stricter community targets are ≤15% similarity and ≤20% AIGC. The audit cannot measure this itself — verify the delivery notes record a plagiarism self-check and flag its absence as a finding.

Companion-skill ledger (C1 gate companion check): read the per-step execution evidence under `.engine/evidence/` and verify every step that carried `companion_skills` recommendations declared its `companion_skills` decision (used and/or skipped with reasons). List any gap as a finding with the step name; the runner blocks completion before step 14, so a gap here indicates evidence tampering — treat it as fatal.

AI-disclosure red line (CUMCM 2026 hard compliance; the same 双件套 mechanism is mandatory on the GMCM/华为杯 chain since its S14 shares this skill): verify the deterministic AI 双件套 end to end — `paper/main.tex` must contain the "AI工具使用声明" section placed before the references, and `python skills/_utils/build_ai_disclosure.py --check-only --paper-source <工作区>/paper/main.tex` must exit 0 against the workspace's `.mh/ai_disclosure.json` manifest. A hand-written declaration with no script-backed manifest/detail PDF, or a failing `--check-only`, is a fatal finding (the declaration text must originate from the user-confirmed tool list, never authored freely by a language model).

Reference and consistency final sweep: run `python tools/citation_checker.py <工作区>/paper/main.tex` for a reference-entry machine sweep and `python tools/paper_data_check.py <工作区>` for number-vs-ledger cross-checking; report any mismatch as a finding (fatal when it touches headline numbers, page-limit items, or the reference list). The audit is their mandatory consumer.

Asset-declaration ledger (C2 gate companion check): for every step whose evidence carries an `assets` declaration, verify coverage of the step's StepAction.assets list (same rule as the companion ledger). For workflows started before the C2 mechanism, `assets` is legitimately absent from both StepAction and evidence — absence is not a finding; only steps that carry the field must satisfy it. A machine sweep is available: `python tools/check_asset_utilization.py` (utilization ledger + map coverage + template asset paths).

Integrity anchor (anti-Goodhart): every gate, template, and test lives inside the agent's write scope, so internal checks can themselves be gamed by editing the checker. The final `approve` of this step belongs to the human operator; before `delivery_decision=ready`, the operator must verify repo integrity from outside the agent's session: `git status` clean, `git log` reviewed for any contest-window modification to `engine/`, `tests/`, `engine/modex-core/templates.json`, or quality-gate scripts without a logged justification, and optionally `pytest -q` re-run from a fresh clone/worktree. Any unexplained gate-file modification = fatal finding; document the check in `AUDIT_REPORT.json` notes.

## 退出判据（Verification）

本步完成前逐项自检（不达标即视为未完成）：

- [ ] 证据链完整：每步有产物、命令、哈希与事件
- [ ] 门禁结论逐项列出，不得只写一句「通过」
- [ ] 交付文件清单与实际文件一致（含体积与格式合规）
- [ ] 不得存在 skip_ 类豁免参数；存在即判定交付阻断

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "门禁都过了就交付" | 门禁只覆盖检查项全集，不覆盖本次风险面；审计要给出逐项结论。 |
| "审计报告写个通过就行" | 手写散文式「审计」过不了产物规格（需含门禁逐项结论字段）。 |
| "这条豁免先留着" | skip_ 类豁免只留痕不放行：存在即阻断交付，须以不含豁免的流程重跑。 |

> 本段与 `skills/_utils/anti_rationalization.md`（全局版）配套：本表是本步专属，
> 全局版覆盖跨步骤通用借口。新增借口时优先落到本表（更贴岗位），能泛化再上升。
