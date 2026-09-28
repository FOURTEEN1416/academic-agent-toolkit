# Proof Techniques Reference Guide

## Overview

Mathematical proofs are the foundation of computer science. Understanding proof techniques enables:
- Algorithm correctness verification
- Complexity analysis
- Security proofs
- Type system soundness

## Core Proof Techniques

### 1. Direct Proof

**When to Use:** Proving "If P, then Q" directly.

**Method:**
1. Assume P is true
2. Use definitions, axioms, and theorems
3. Derive Q

**Example:**
```
Theorem: If n is even, then n² is even.
Proof:
  Let n be even. Then n = 2k for some integer k.
  n² = (2k)² = 4k² = 2(2k²)
  Since 2k² is an integer, n² is even. ∎
```

### 2. Proof by Contradiction

**When to Use:** When direct proof is difficult; proving something must be true.

**Method:**
1. Assume the opposite of what you want to prove
2. Derive a logical contradiction
3. Conclude original statement must be true

**Example:**
```
Theorem: √2 is irrational.
Proof:
  Assume √2 = p/q where p,q are coprime integers.
  Then 2q² = p², so p² is even, so p is even.
  Let p = 2r. Then 2q² = 4r², so q² = 2r².
  Thus q is also even. Contradiction! p,q can't both be even if coprime.
  Therefore √2 is irrational. ∎
```

### 3. Mathematical Induction

**When to Use:** Proving statements about all natural numbers.

**Method:**
1. **Base Case:** Prove P(0) or P(1)
2. **Inductive Hypothesis:** Assume P(k) for arbitrary k
3. **Inductive Step:** Prove P(k) → P(k+1)

**Example:**
```
Theorem: Σᵢ₌₁ⁿ i = n(n+1)/2

Base: n=1: 1 = 1(2)/2 = 1 ✓

Inductive Step: Assume Σᵢ₌₁ᵏ i = k(k+1)/2
  Σᵢ₌₁ᵏ⁺¹ i = k(k+1)/2 + (k+1)
            = (k+1)(k/2 + 1)
            = (k+1)(k+2)/2 ✓
```

### 4. Strong Induction

**When to Use:** When P(k+1) depends on multiple previous cases.

**Method:**
1. Base Case(s): Prove P(0), P(1), ... as needed
2. Assume P(0), P(1), ..., P(k) all true
3. Prove P(k+1)

### 5. Proof by Contrapositive

**When to Use:** Proving "P → Q" by proving "¬Q → ¬P"

**Logical Equivalence:** (P → Q) ≡ (¬Q → ¬P)

**Example:**
```
Theorem: If n² is even, then n is even.
Contrapositive: If n is odd, then n² is odd.
Proof:
  Let n be odd. Then n = 2k+1.
  n² = (2k+1)² = 4k² + 4k + 1 = 2(2k² + 2k) + 1
  Thus n² is odd. ∎
```

### 6. Proof by Cases

**When to Use:** When different scenarios require different arguments.

**Method:**
1. Identify all possible cases (exhaustive)
2. Prove statement for each case
3. Conclude statement holds in all cases

## Common Pitfalls

### Induction Mistakes
- Forgetting base case
- Weak inductive hypothesis
- Circular reasoning

### Contradiction Mistakes
- Not reaching actual contradiction
- Assuming what you're trying to prove

### Logic Mistakes
- Affirming the consequent: P→Q, Q ∴ P (INVALID)
- Denying the antecedent: P→Q, ¬P ∴ ¬Q (INVALID)

## Proof Writing Guidelines

1. **State theorem clearly**
2. **Identify proof technique**
3. **Define all variables**
4. **Justify each step**
5. **End with clear conclusion** (QED, ∎, or "Therefore...")

## Computer Science Applications

| Technique | Application |
|-----------|-------------|
| Induction | Loop invariants, recursive algorithms |
| Contradiction | Security proofs, impossibility results |
| Direct | Algorithm correctness |
| Cases | Algorithm analysis by input type |

## Further Reading

- "How to Prove It" by Daniel Velleman
- "Discrete Mathematics and Its Applications" by Kenneth Rosen
- "Introduction to Algorithms" (CLRS) - Appendix on Proof Techniques
