---
name: generating-test-reports
description: |
  Generate structured test reports with pass/fail rollups, coverage summaries, and test artifacts.
  Use when the user is asking for test-result packaging or delivery, not for root-cause debugging or feature implementation.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(test:report-*)
version: 1.0.0
author: Jeremy Longshore <jeremy@intentsolutions.io>
license: MIT
---
# Test Report Generator

## Purpose

Use this skill when the next deliverable is a readable test report rather than another round of debugging.

## When to Use

Use this skill when:
- Summarizing pass/fail status, flaky tests, or coverage output for others to read
- Turning raw `pytest`, JUnit, or coverage artifacts into a concise report
- Producing release, QA, or review-facing test documentation

## Not For / Boundaries

- Root-cause debugging of a failure: use `systematic-debugging`
- Code review of the underlying implementation: use `code-reviewer`
- Implementing a new test suite from scratch: use `tdd-guide`

## Typical Outputs

- Test execution summary with totals and failure clusters
- Coverage snapshot and quality-gate status
- Follow-up action list for the most important failures

## Related Skills

- `systematic-debugging` before report packaging if failures are still unexplained
- `verification-before-completion` when the report is part of a completion gate
