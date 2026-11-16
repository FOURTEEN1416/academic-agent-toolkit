---
name: dev-verification-loop
description: "Use when the user asks to ”verify code”, ”run verification”, ”check quality”, or ”validate changes” before a PR."
version: 1.0.0
---

# Verification Loop Skill

A comprehensive verification system for agent coding sessions.

## When to Use

Invoke this skill:
- After completing a feature or significant code change
- Before creating a PR
- When you want to ensure quality gates pass
- After refactoring

## Verification Phases

Choose the commands adaptively for the current project instead of running every example blindly. Use the stack-appropriate command from the minimal table below when the repo does not match the default examples.

### Minimal Stack Detection (inline)

| Repo marker | Build | Types / Lint | Tests |
|---|---|---|---|
| `pyproject.toml` / `uv.lock`（Python） | `uv build`（兜底 `python -m build`） | `pyright .` / `ruff check .` | `pytest` |
| `package.json`（Node/TS） | `npm run build` | `npx tsc --noEmit` / `npm run lint` | `npm run test` |
| 两者皆有（monorepo） | 两套都跑 | 两套都跑 | 两套都跑 |
| 皆无 | 跳过 build，按项目入口做脚本冒烟 | 跳过 | 按现有入口冒烟 |

`references/STACK-DETECTION.md` 为可选深读材料（当前未随仓，见 ASSET-GAP.md）；栈判断以上表为准。


### Phase 1: Build Verification
```bash
# Python projects (uv)
uv build 2>&1 | tail -20
# OR
python -m build 2>&1 | tail -20

# Node.js projects
npm run build 2>&1 | tail -20
# OR
pnpm build 2>&1 | tail -20
```

If build fails, STOP and fix before continuing.

### Phase 2: Type Check
```bash
# TypeScript projects
npx tsc --noEmit 2>&1 | head -30

# Python projects
pyright . 2>&1 | head -30
```

Report all type errors. Fix critical ones before continuing.

### Phase 3: Lint Check
```bash
# JavaScript/TypeScript
npm run lint 2>&1 | head -30

# Python
ruff check . 2>&1 | head -30
```

### Phase 4: Test Suite
```bash
# Python projects
pytest --cov=src --cov-report=term-missing 2>&1 | tail -50

# Node.js projects
npm run test -- --coverage 2>&1 | tail -50
```

Report:
- Total tests: X
- Passed: X
- Failed: X
- Coverage: X%

### Phase 5: Security Scan
```bash
# Python: Check for secrets
grep -rn "sk-" --include="*.py" . 2>/dev/null | head -10
grep -rn "api_key" --include="*.py" . 2>/dev/null | head -10
pip-audit

# Node.js: Check for secrets
grep -rn "sk-" --include="*.ts" --include="*.js" . 2>/dev/null | head -10
grep -rn "api_key" --include="*.ts" --include="*.js" . 2>/dev/null | head -10

# Check for debug statements
grep -rn "print(" --include="*.py" src/ 2>/dev/null | head -10
grep -rn "console.log" --include="*.ts" --include="*.tsx" src/ 2>/dev/null | head -10
```

### Phase 6: Diff Review
```bash
# Show what changed
git diff --stat
git diff HEAD~1 --name-only
```

Review each changed file for:
- Unintended changes
- Missing error handling
- Potential edge cases

## Output Format

After running all phases, produce a verification report:

```
VERIFICATION REPORT
==================

Build:     [PASS/FAIL]
Types:     [PASS/FAIL] (X errors)
Lint:      [PASS/FAIL] (X warnings)
Tests:     [PASS/FAIL] (X/Y passed, Z% coverage)
Security:  [PASS/FAIL] (X issues)
Diff:      [X files changed]

Overall:   [READY/NOT READY] for PR

Issues to Fix:
1. ...
2. ...
```

## Continuous Mode

For long sessions, run verification every 15 minutes or after major changes:

```markdown
Set a mental checkpoint:
- After completing each function
- After finishing a component
- Before moving to next task

Run: /verify
```

## Integration with Hooks

This skill complements PostToolUse hooks but provides deeper verification.
Hooks catch issues immediately; this skill provides comprehensive review.


## Reference Files

> ⚠️ 以下参考文件**未随仓集成**（缺口见 [ASSET-GAP.md](ASSET-GAP.md)）。栈判断用上方内联最小栈判断表，报告结构用正文 Output Format 节；下列条目仅供追踪补齐进度。

Load only what is needed:
- `references/STACK-DETECTION.md` - how to choose the right verification command set for the current repo *(未随仓，可选深读)*
- `references/REPORT-TEMPLATE.md` - report structure for final verification output *(未随仓)*
- `examples/example-verification-report.md` - example final report *(未随仓)*
