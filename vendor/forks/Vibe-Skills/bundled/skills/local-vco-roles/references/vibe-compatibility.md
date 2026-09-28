# vibe Compatibility Notes for local-vco-roles

## Purpose

This document defines how `local-vco-roles` integrates with local `vibe` behavior without conflicting with its routing model.

## Compatibility Matrix

| Condition | Action |
|---|---|
| `/vibe` + M | Use lightweight single-agent analysis. Do not run TeamCreate workflow. |
| `/vibe` + L | Use design-first flow and limited role decomposition. |
| `/vibe` + XL | Use full role pack with lead + 4 analysts. |
| User explicit tool command | Bypass role pack defaults and respect user command. |

## Required Shared Conventions

1. Severity ordering: `CRITICAL > HIGH > MEDIUM > LOW`
2. Decision format: `keep / simplify / remove`
3. Evidence-first claims (no speculative completion statements)

## Team Role Coverage

1. team-lead: integration and final synthesis
2. bug-analyst: defects, contradictions, dead references
3. arch-critic: over-engineering and simplification
4. integration-analyst: dependency and runtime integration risk
5. usability-analyst: friction, routing clarity, user ROI

## Failure Safety

If any analyst output is missing:
1. Mark missing role explicitly.
2. Continue with available roles.
3. Downgrade confidence in final synthesis.

