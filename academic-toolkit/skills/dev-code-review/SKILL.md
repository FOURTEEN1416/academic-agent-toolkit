---
name: dev-code-review
description: "Multi-language code review methodology and checklists for reviewing pull requests, analyzing code quality, and identifying issues. Use when reviewing code changes."
---

# Code Reviewer

Automated multi-language code review — analysis scripts, per-language rule packs, and structured review reports — plus the manual review methodology, checklists, and verdict criteria for analyzing pull requests and detecting code quality and security issues.

## How This Skill Is Organized

```
dev-code-review/
  SKILL.md                        ← you are here (tools + dispatch table)
  rules/
    universal.md                  ← security, async, resources, exceptions, performance — all languages
  languages/
    python.md                     ← Python-specific rules + idioms
    typescript.md                 ← TypeScript / JavaScript-specific rules + idioms
    go.md                         ← Go-specific rules + idioms
    swift.md                      ← Swift-specific rules + idioms
    kotlin.md                     ← Kotlin-specific rules + idioms
    csharp.md                     ← C# / .NET-specific rules + idioms
    java.md                       ← Java-specific rules + idioms
    c.md                          ← C-specific rules + idioms
    cpp.md                        ← C++-specific rules + idioms
    rust.md                       ← Rust-specific rules + idioms
    ruby.md                       ← Ruby-specific rules + idioms
    php.md                        ← PHP-specific rules + idioms
    dart.md                       ← Dart / Flutter-specific rules + idioms
  scripts/
    pr_analyzer.py                ← git-diff risk analysis (secrets, debug, TODO, complexity)
    code_quality_checker.py       ← quality score, smells, SOLID (14 languages)
    review_report_generator.py    ← combines both analyses into a text/markdown/json report
  assets/
    sample_java_smells.java       ← labelled regression fixture (intentional smells)
  expected_outputs/
    sample_java_smells_quality.json  ← committed --json baseline for the fixture
```

### Loading order for every review

1. This file (`SKILL.md`) — tools and thresholds
2. `rules/universal.md` — always, for every language
3. The matching `languages/*.md` — one file based on the extension table below

That is always exactly **2 additional files**, regardless of scope.

| Extension(s) | Load |
|---|---|
| `.py` | `languages/python.md` |
| `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs` | `languages/typescript.md` |
| `.go` | `languages/go.md` |
| `.swift` | `languages/swift.md` |
| `.kt`, `.kts` | `languages/kotlin.md` |
| `.cs`, `.csx`, `.razor`, `.cshtml` | `languages/csharp.md` |
| `.java` | `languages/java.md` |
| `.c`, `.h` | `languages/c.md` |
| `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hh`, `.hxx` | `languages/cpp.md` |
| `.rs` | `languages/rust.md` |
| `.rb`, `.rake`, `.gemspec`, `.ru` | `languages/ruby.md` |
| `.php`, `.phtml` | `languages/php.md` |
| `.dart` | `languages/dart.md` |

---

## Tools

### PR Analyzer

Analyzes git diff between branches to assess review complexity and identify risks.

```bash
# Analyze current branch against main
python scripts/pr_analyzer.py /path/to/repo

# Compare specific branches
python scripts/pr_analyzer.py . --base main --head feature-branch

# JSON output for integration
python scripts/pr_analyzer.py /path/to/repo --json
```

**What it detects (universal — see also language file for language-specific signals):**
- Hardcoded secrets (passwords, API keys, tokens, connection strings)
- SQL / query injection patterns
- Debug statements left in production code
- Lint / analyzer suppression annotations
- TODO/FIXME comments

**Language-specific detections** are defined in each `languages/*.md` file.

**Output includes:**
- Complexity score (1-10)
- Risk categorization (critical, high, medium, low)
- File prioritization for review order
- Commit message validation

---

### Code Quality Checker

Analyzes source code for structural issues, code smells, and SOLID violations.

```bash
# Analyze a directory
python scripts/code_quality_checker.py /path/to/code

# Analyze specific language
# Valid values: python, typescript, javascript, go, swift, kotlin, csharp, java, c, cpp, rust, ruby, php, dart
python scripts/code_quality_checker.py . --language java

# JSON output
python scripts/code_quality_checker.py /path/to/code --json
```

**Universal thresholds:**

| Issue | Threshold |
|-------|-----------|
| Long function | >50 lines |
| Large file | >500 lines |
| God class | >20 methods |
| Too many params | >5 |
| Deep nesting | >4 levels |
| High complexity | >10 branches |

Language-specific checks are defined in each `languages/*.md` file.

---

### Review Report Generator

Combines PR analysis and code quality findings into structured review reports.

```bash
# Generate report for current repo
python scripts/review_report_generator.py /path/to/repo

# Markdown output
python scripts/review_report_generator.py . --format markdown --output review.md

# Use pre-computed analyses
python scripts/review_report_generator.py . \
  --pr-analysis pr_results.json \
  --quality-analysis quality_results.json
```

**Verdicts:**

| Score | Verdict |
|-------|---------|
| 90+ with no high issues | Approve |
| 75+ with ≤2 high issues | Approve with suggestions |
| 50-74 | Request changes |
| <50 or critical issues | Block |

---

## Adding a New Language

**Reviewer guidance (required):**

1. Create `languages/<name>.md` using any existing language file as a template — it must have sections: PR Analyzer Signals, Code Quality Checks, Security, Async, Resource Management, Exception Handling, Performance, Idioms.
2. Add the extension row to the dispatch table above.

That is all the agent-driven review needs.

**Deterministic analyzer support (optional, recommended):** the bundled scripts
only flag a language they explicitly know. To make `code_quality_checker.py`
score the new language:

3. Add the extensions to `LANGUAGE_EXTENSIONS` in `scripts/code_quality_checker.py` (this also adds the `--language` choice).
4. Add `function` / `class` / `method` regex entries for the language in the same file; otherwise it falls back to the Python patterns.
5. Optionally add a `check_<name>_specific_smells(...)` detector (see the C#, Java, and C ones) and call it from `analyze_file`.
6. Add `assets/sample_<name>_smells.<ext>` + `_clean` fixtures and commit the expected `--json` output under `expected_outputs/` as a regression guard.

---

## Regression Fixtures

Labelled fixtures live in `assets/` with their committed `--json` output in
`expected_outputs/`. This repository bundles the Java pair
(`assets/sample_java_smells.java`); the upstream also ships C and C# pairs that
were not collected here (see [UPSTREAM.md](UPSTREAM.md)). Drift from the
committed JSON signals a behaviour change in the analyzer.

The `file` field of the JSON output is the analyzer's resolved **absolute**
path, so normalize it before comparing (run from this skill's directory):

```bash
python scripts/code_quality_checker.py assets/sample_java_smells.java --json \
  | python -c "import json,sys; d=json.load(sys.stdin); d['file']='assets/sample_java_smells.java'; print(json.dumps(d, indent=2, default=str))" \
  | diff --strip-trailing-cr - expected_outputs/sample_java_smells_quality.json
```

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
