# Error Recovery Strategies

Comprehensive error handling and recovery patterns for autonomous development.

## Error Classification

### By Type

| Category | Examples | Recovery Strategy |
|----------|----------|-------------------|
| Syntax | ParseError, UnexpectedToken | Auto-fix based on language rules |
| Type | TypeError, ClassCastException | Infer correct type, add conversion |
| Reference | NameError, NullPointerException | Check scope, add imports |
| Runtime | DivisionByZero, IndexError | Add validation, boundary checks |
| Network | Timeout, ConnectionRefused | Retry with backoff, fallback |
| Permission | AccessDenied, Unauthorized | Check permissions, escalate |
| Dependency | ModuleNotFound, PackageMissing | Install missing, fix imports |
| Configuration | ConfigError, EnvMissing | Use defaults, prompt user |

### By Severity

```
FATAL: Application cannot continue
  -> Log, save state, request user intervention

ERROR: Feature cannot complete
  -> Apply 3-strike protocol, try alternative

WARNING: Suboptimal but functional
  -> Log, continue, fix later if needed

INFO: Informational
  -> Log and continue
```

## 3-Strike Protocol Implementation

### Strike 1: Direct Fix

```python
def strike_1_fix(error: Error, code: str) -> FixResult:
    """Attempt direct fix based on error analysis."""

    # Step 1: Classify error
    error_type = classify_error(error)

    # Step 2: Get pattern match
    pattern = match_error_pattern(error)

    if pattern:
        # Apply known fix
        fix = pattern.solution
        new_code = apply_fix(code, fix)
        return FixResult(code=new_code, confidence=pattern.confidence)

    # Step 3: If no pattern, use LLM-based fix
    fix = analyze_and_fix(error, code)
    return FixResult(code=fix.code, confidence=fix.confidence)
```

### Strike 2: Alternative Approach

```python
def strike_2_alternative(error: Error, context: Context) -> AlternativeResult:
    """Try different implementation approach."""

    alternatives = [
        try_different_library,
        try_different_algorithm,
        try_different_pattern,
        simplify_implementation,
    ]

    for alt in alternatives:
        result = alt(error, context)
        if result.success:
            return result

    return AlternativeResult(success=False)
```

### Strike 3: Rethink

```python
def strike_3_rethink(error: Error, context: Context) -> RethinkResult:
    """Question assumptions and redesign."""

    questions = [
        "Is this feature necessary in current form?",
        "Can we use a simpler implementation?",
        "Are there external constraints we missed?",
        "Is the architecture appropriate?",
    ]

    # Research solutions
    solutions = search_solutions(error)

    # Consider partial implementation
    partial = identify_partial_implementation(context)

    return RethinkResult(
        questions=questions,
        solutions=solutions,
        partial=partial
    )
```

## Error Pattern Database

### Python Patterns

```yaml
# patterns/python.yaml
- id: "py-import-error"
  pattern: "ModuleNotFoundError: No module named '(\\w+)'"
  category: dependency
  solutions:
    immediate: "pip install {module}"
    proper: "Add to requirements.txt, run pip install"

- id: "py-type-error-none"
  pattern: "TypeError: '(\\w+)' is None"
  category: type
  solutions:
    immediate: "Add None check: if {var} is not None:"
    proper: "Use Optional type hint and validate"

- id: "py-key-error"
  pattern: "KeyError: '(\\w+)'"
  category: reference
  solutions:
    immediate: "Use dict.get('{key}', default)"
    proper: "Validate key existence or use defaultdict"
```

### Node.js Patterns

```yaml
# patterns/nodejs.yaml
- id: "js-cannot-read-property"
  pattern: "Cannot read property '(\\w+)' of (undefined|null)"
  category: type
  solutions:
    immediate: "Add null check: obj?.{property}"
    proper: "Use optional chaining and default values"

- id: "js-module-not-found"
  pattern: "Cannot find module '(\\w+)'"
  category: dependency
  solutions:
    immediate: "npm install {module}"
    proper: "Add to package.json dependencies"
```

## Recovery State Management

### Error Log Schema

```json
{
  "errors": [
    {
      "id": "err-001",
      "timestamp": "2026-02-13T10:30:00Z",
      "feature_id": "feat-003",
      "error_type": "TypeError",
      "error_message": "Cannot read property 'id' of undefined",
      "file": "src/services/task.service.ts",
      "line": 45,
      "stack_trace": "...",
      "attempts": [
        {
          "strike": 1,
          "approach": "direct_fix",
          "solution": "Added null check",
          "result": "failed",
          "reason": "Error persisted in different location"
        },
        {
          "strike": 2,
          "approach": "alternative",
          "solution": "Used optional chaining",
          "result": "success",
          "reason": "Error resolved"
        }
      ],
      "resolution": "Used optional chaining throughout codebase",
      "resolved_at": "2026-02-13T10:35:00Z"
    }
  ]
}
```

## Automatic Recovery Actions

### Build Errors

```bash
# TypeScript compilation error
npx tsc --noEmit 2>&1 | parse_errors
for error in errors:
    if "Property does not exist":
        add_property_declaration()
    elif "Type is not assignable":
        add_type_conversion()
    elif "Cannot find module":
        npm_install_or_add_declaration()

# Python import error
python -c "import {module}" 2>&1 || pip install {module}
```

### Test Failures

```python
def recover_test_failure(test_output: str):
    """Analyze test failure and attempt fix."""

    failures = parse_test_failures(test_output)

    for failure in failures:
        if "AssertionError":
            # Check expected vs actual
            expected = extract_expected(failure)
            actual = extract_actual(failure)
            suggest_fix(expected, actual)

        elif "TypeError" in failure:
            # Type mismatch in test
            fix_test_type_annotation(failure)

        elif "Fixture not found":
            # Missing pytest fixture
            create_missing_fixture(failure)
```

### Runtime Errors

```python
def recover_runtime_error(error: Exception, context: dict):
    """Handle runtime errors during execution."""

    if isinstance(error, ConnectionError):
        # Network error - retry with backoff
        return retry_with_backoff(context['operation'])

    elif isinstance(error, PermissionError):
        # Permission issue - check and fix
        return fix_permissions(context['path'])

    elif isinstance(error, MemoryError):
        # Memory issue - optimize or chunk
        return optimize_or_chunk(context['operation'])
```

## Escalation Protocol

When 3 strikes fail:

```markdown
## Escalation Report

**Feature**: {feature_id} - {feature_name}
**Error**: {error_message}
**Attempts**:
1. Strike 1: {approach} - {result}
2. Strike 2: {approach} - {result}
3. Strike 3: {approach} - {result}

**Current State**:
- Files modified: {files}
- Tests status: {tests}
- Blockers: {blockers}

**Options for User**:
1. Accept partial implementation
2. Provide additional context
3. Modify requirements
4. Manual intervention

**Checkpoint saved to**: .builder/checkpoints/checkpoint-{id}.json
```

## Best Practices

1. **Always log errors** to errors.json with full context
2. **Never repeat** the exact same failing action
3. **Document recovery attempts** for learning
4. **Create checkpoints** before risky changes
5. **Escalate gracefully** when stuck
