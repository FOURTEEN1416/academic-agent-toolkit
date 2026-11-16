---
name: paper-self-review
description: "Use when the user asks to ”review paper quality”, ”check paper completeness”, or ”validate paper structure”."
version: 0.1.0
---

# Paper Self-Review

A systematic paper quality checking tool that helps researchers conduct comprehensive self-review before submission.

## Core Features

### 1. Structure Review

Check whether all sections of the paper are complete and conform to academic standards:
- Does the Abstract include problem, method, results, and contributions?
- Does the Introduction clearly articulate research motivation and background?
- Is the Method detailed enough to be reproducible?
- Do the Results sufficiently support the conclusions?
- Does the Discussion address limitations and future work?

### 2. Logic Consistency Check

Verify the logical coherence of the paper:
- Do research questions match the methodology?
- Does the experimental design support the research hypotheses?
- Are result interpretations reasonable?
- Are conclusions supported by evidence?

### 3. Citation Completeness

Check the completeness and accuracy of citations:
- Are all citations present in the references?
- Is the reference format consistent?
- Are key related works cited?
- Do citations accurately reflect the original content?

### 4. Research Claim Audit

Check whether the paper's claims are supported by the available evidence:
- Are the main claims supported by results, citations, or analysis artifacts?
- Are speculative observations clearly marked as tentative?
- Does the paper avoid stronger wording than the evidence allows?
- Are negative results, limitations, and missing baselines presented honestly?
- Do conclusions stay inside the tested scope?

This audit does not replace `results-analysis` for statistics or `paper-citation-verify` for bibliographic verification. It checks whether paper claims correctly use the available evidence.

### 5. Figure/Table Quality

Evaluate the quality and effectiveness of figures and tables:
- Do all figures/tables have clear titles and captions?
- Do figures/tables support the text narrative?
- Are figures/tables clear and readable?
- Do formats comply with journal/conference requirements?

### 6. Writing Clarity

Check writing clarity and readability:
- Is the language concise and clear?
- Is technical terminology used appropriately?
- Are sentence structures clear?
- Is paragraph organization logical?

## Quality Checklist

Use this checklist for systematic paper self-review:

```
Paper Quality Checklist:
- [ ] Abstract includes problem, method, results, contributions
- [ ] Introduction clearly states research motivation
- [ ] Method is reproducible
- [ ] Results support conclusions
- [ ] Main claims are supported by named evidence
- [ ] Over-strong claims are weakened or removed
- [ ] Discussion addresses limitations
- [ ] All figures/tables have captions
- [ ] Citations are complete and accurate
```

## When to Use

Use this skill in the following scenarios:

- **Pre-submission check** - Final review before submitting to a journal or conference
- **After first draft** - Systematic review after completing the first draft
- **Before advisor review** - Self-check before requesting advisor feedback to improve quality
- **Post-revision verification** - After revising based on reviewer comments, verify all issues are addressed
- **Collaborator review** - Quality check before sending to collaborators

## Review Process

Follow these steps for systematic paper review:

### Step 1: Structure Review
Start with the overall structure, checking if all sections are complete and logically coherent.

### Step 2: Content Review
Dive into each section, checking content accuracy and completeness.

### Step 3: Research Claim Audit
Check whether each major claim is supported by the evidence available in the draft, analysis bundle, citations, or project notes.

Use this output shape:

```md
## Claim Audit

Claim:
Verdict: keep | weaken | revise | remove
Evidence used:
Missing evidence:
Overclaim risk:
Suggested wording:
```

### Step 4: Citation Check
Verify the completeness and accuracy of all citations.

### Step 5: Figure/Table Review
Check the quality and captions of all figures and tables.

### Step 6: Writing Quality
Review language expression and writing clarity.

### Step 7: Final Checklist
Use the quality checklist for final verification.

## Best Practices

### Review Timing
- **Spaced review** - Wait 1-2 days after completing the draft before reviewing to maintain objectivity
- **Multiple rounds** - Conduct multiple review rounds, focusing on different aspects each time
- **Print review** - Print a hard copy for review; issues are easier to spot on paper

### Review Techniques
- **Reverse reading** - Read from conclusion backwards to check logical coherence
- **Read aloud** - Reading the paper aloud helps identify language issues
- **Reviewer perspective** - Assume you are a reviewer and read critically

### Common Issues
- Abstract too brief or too verbose
- Introduction lacks clear research question statement
- Method lacks sufficient detail for reproduction
- Results lack statistical significance tests
- Discussion doesn't address research limitations
- Figures/tables lack clear titles and captions
- Inconsistent citation formatting

## Summary

The Paper Self-Review skill provides a systematic paper quality checking process, helping researchers identify and resolve issues before submission, improving paper quality and acceptance rates.


## Reference Files

原上游 3 份必读件未随仓（登记见 ASSET-GAP.md），要点已极简内联于下，正文不依赖缺失文件即可执行：

- **section-checklist（内联）**：逐节过检——摘要四要素（问题/方法/结果/贡献）、引言动机明确、方法可复现、结果支持结论、讨论含局限与未来工作；每节先问「这节要证明什么」再挑错。
- **final-verdict（内联）**：收尾给三档结论——`ready`（无阻断项）/ `ready-after-fixes`（列阻断项+最小修复）/ `not-ready`（结构性缺陷）；阻断项=编译失败、主张无证据、图表缺标注、引用存疑。
- **example-self-review（内联）**：输出样例形态=按上述 Claim Audit 表 + 质量清单 + 三档结论组织，每条发现给位置与最小修复。

获得上游来源后按原路径回填：
- `references/SECTION-CHECKLIST.md`（缺失——要点已内联）
- `references/FINAL-VERDICT.md`（缺失——要点已内联）
- `examples/example-self-review.md`（缺失——要点已内联）
