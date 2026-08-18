---
name: verify-math
description: Verify mathematical derivations step-by-step using SymPy
version: 1.0.0
---

# Math Derivation Skill

Verify mathematical derivations step-by-step using SymPy.

## When to Use

- Deriving equations (differentiation, integration, algebraic manipulation)
- Verifying mathematical identities
- Step-by-step proofs where each step should be validated

## Workflow

For each derivation step:
1. State the transformation being applied
2. Write the result
3. Verify with `./verify.py` before proceeding

## Verification Commands

```bash
# Check two expressions are equal
./verify.py eq "EXPR1" "EXPR2"

# Compute derivative
./verify.py diff "EXPR" [VAR]

# Compute integral
./verify.py int "EXPR" [VAR]

# Simplify/expand expression
./verify.py simp "EXPR"

# Solve equation (EXPR = 0)
./verify.py solve "EXPR" [VAR]
```

> Paths are relative to this skill's directory.

## Expression Syntax

- Powers: `x**2` or `x^2`
- Functions: `sin(x)`, `cos(x)`, `exp(x)`, `log(x)`, `sqrt(x)`
- Pre-defined symbols: `x y z t s n k a b c C`
- Reserved symbols handled: `E I S N O` (treated as variables, not SymPy constants)

## Example Derivation

**Problem**: Find dF/ds where F(s) = s - log(e^s + C)

**Step 1**: Apply derivative rule
```
dF/ds = 1 - d/ds[log(e^s + C)]
      = 1 - e^s/(e^s + C)
```

```bash
./verify.py diff "s - log(exp(s) + C)" s
```

**Step 2**: Simplify to single fraction
```
= (e^s + C - e^s)/(e^s + C)
= C/(e^s + C)
```

```bash
./verify.py eq "1 - exp(s)/(exp(s) + C)" "C/(exp(s) + C)"
```
