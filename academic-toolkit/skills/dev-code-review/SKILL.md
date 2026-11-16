---
name: dev-code-review
description: "Multi-language code review methodology and checklists for reviewing pull requests, analyzing code quality, and identifying issues. Use when reviewing code changes."
---

# Code Reviewer

Generic multi-language code review methodology and checklists for analyzing pull requests, detecting code quality and security issues, and producing structured review verdicts.

> **Asset gap notice / 资产降级声明**: The automated tooling assets referenced by earlier versions of this skill (3 analysis scripts, the per-language rule files, and the regression fixtures — 19 items in total) are missing from this repository; see [ASSET-GAP.md](ASSET-GAP.md) for the itemized list. 自动化工具资产缺失（见 ASSET-GAP.md），当前为通用评审指引：按下方方法论与检查清单执行人工评审；自动化分析待资产补齐后恢复。

---

## Division of Labor Among Review Skills

| Skill | Role | Use when |
|---|---|---|
| **dev-code-review** (this skill) | Generic review methodology, checklists, and verdict criteria | You need a structured manual review of any diff / PR in any language |
| **dev-code-review-guide** | Review communication and team process ("Code Review Excellence") | You are writing review comments, setting team review standards, or mentoring reviewers |
| **dev-adversarial-code-review** | Adversarial personas (Saboteur / New Hire / Security Auditor) | You need a genuinely critical pass that breaks the author's self-review blind spots |
| [references/merged-ars-pr-review-expert.md](references/merged-ars-pr-review-expert.md) | Deep-dive PR review reference (blast radius, security scan, breaking-change detection, coverage delta, 30+ item checklist) | Large or cross-service PRs, release-blocking reviews |

---

## Review Workflow

1. **Frame the change** — read the diff/PR intent first (commit message, linked ticket, stated goal) before reading code.
2. **Prioritize by risk** — core logic > boundary handling > configuration > docs. Review the riskiest files first.
3. **Apply the checklists below** per file, adjusted to the language's idioms; the universal items apply to every language.
4. **Summarize findings** — classify each by severity (critical / high / medium / low) with an actionable fix suggestion.
5. **Give a verdict** using the criteria at the end of this file.

---

## Universal Checklists

### Security (check on every change)

- Hardcoded secrets: passwords, API keys, tokens, connection strings
- Injection surfaces: SQL / command / path injection, unsafe deserialization
- Unvalidated external input (request bodies, query params, file uploads, redirects)
- Sensitive data leaked into logs, exception messages, or API responses
- Auth/authz gaps: missing ownership checks, privilege escalation via IDs or roles

### Correctness & Robustness

- Boundary conditions: empty collections, zero, negatives, overflow, timezone, concurrency
- Error handling: swallowed exceptions, lost error context, failure paths without cleanup/rollback
- Resource management: files, connections, locks, goroutines/tasks/threads not closed or cancelled
- Data integrity: transactions, idempotency, migration safety

### Maintainability (universal thresholds)

| Signal | Suggested threshold |
|---|---|
| Long function | >50 lines — extract |
| Large file | >500 lines — split by responsibility |
| God class | >20 methods — decompose |
| Too many params | >5 — introduce a config/options object |
| Deep nesting | >4 levels — early returns / guard clauses |
| High complexity | >10 branches — split or table-drive |

### Engineering Hygiene

- Debug statements (`print` / `console.log` / `fmt.Println` / `dbg!`) left in production paths
- Lint/analyzer suppression annotations (`# noqa`, `nolint`, `@SuppressWarnings`, `#[allow]`) without justification
- TODO/FIXME comments without an owner or ticket
- New code without tests, or tests covering only the happy path

---

## Verdict Criteria

| Situation | Verdict |
|---|---|
| No high-or-above issues; only style/suggestions | Approve |
| ≤2 high issues with clear fixes | Approve with suggestions |
| Unresolved high issues or several medium ones | Request changes |
| Any critical issue (security hole, data corruption, contract break) | Block |

---

## Writing Review Comments

- Each comment states: location (`file:line`) → problem → impact → suggested fix.
- Distinguish **blocking** (must fix) from **non-blocking** (suggest) feedback.
- For uncertain design tradeoffs, ask questions instead of asserting; lead with what works, critique the code not the author.
- For tone, phrasing, and team-process guidance, use **dev-code-review-guide**; for a forced-critical second pass, use **dev-adversarial-code-review**.
