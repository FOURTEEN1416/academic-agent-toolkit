# Mathematical Proof Template

## Proof Structure

### Theorem Statement
**Theorem:** [State what you want to prove]

### Proof Type
- [ ] Direct Proof
- [ ] Proof by Contradiction
- [ ] Proof by Induction
- [ ] Proof by Contrapositive

---

## Direct Proof Template

**Theorem:** If P, then Q.

**Proof:**
1. Assume P is true.
2. [Show logical steps]
3. Therefore, Q is true. QED

---

## Proof by Contradiction Template

**Theorem:** Statement S is true.

**Proof:**
1. Assume S is false (assume NOT S).
2. [Derive logical consequences]
3. Reach a contradiction.
4. Therefore, S must be true. QED

---

## Mathematical Induction Template

**Theorem:** P(n) is true for all n >= k.

**Proof:**

**Base Case (n = k):**
Show P(k) is true.
[Verification]

**Inductive Hypothesis:**
Assume P(n) is true for some arbitrary n >= k.

**Inductive Step:**
Show P(n) => P(n+1).
[Using inductive hypothesis, prove P(n+1)]

Therefore, by mathematical induction, P(n) is true for all n >= k. QED

---

## Example: Sum Formula

**Theorem:** 1 + 2 + ... + n = n(n+1)/2 for all n >= 1

**Base Case (n = 1):**
LHS = 1
RHS = 1(1+1)/2 = 1
LHS = RHS ✓

**Inductive Hypothesis:**
Assume 1 + 2 + ... + k = k(k+1)/2 for some k >= 1

**Inductive Step:**
1 + 2 + ... + k + (k+1) = k(k+1)/2 + (k+1)
                        = (k+1)(k/2 + 1)
                        = (k+1)(k+2)/2 ✓

By induction, the formula holds for all n >= 1. QED
