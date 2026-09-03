---
name: anti-defensive-writing
description: Reduce defensive writing in drafts and revisions by removing unnecessary caveats, disclaimers, hedges, apology-like framing, negative self-limiting statements, and over-explanations while preserving necessary scope, accuracy, safety, legal, ethical, and methodological limits. Use when drafting or revising academic writing, papers, essays, abstracts, introductions, contribution statements, discussions, conclusions, technical explanations, grant writing, product writing, policy writing, professional reports, or any text the user wants to be clearer, stronger, more direct, more concise, more confident, less verbose, less caveated, less apologetic, or less defensive.
---
<!-- ==================== 本仓适配块（Academic Agent Toolkit, 2026-09-03） ==================== -->
<!-- 上游: Kiterlin/anti-defensive-writing (MIT, pinned @ 2026-09-03); 以下正文为上游原文，仅头部/尾部适配 -->

## 本仓适配：输入/输出契约与触发条件

**触发条件（本仓场景）**：论文修订轮（auto-review-loop 之后）、摘要/引言/贡献声明定稿前、审稿回复信起草、任何"想让文本更直接自信"的改写需求。

**输入契约**：待清理的文本（md/tex 片段均可）+ 上下文声明（该文本的章节位置与所属主张编号，用于判定"必要限定"）。

**输出契约（三件套，缺一不可）**：
1. 改写后文本（diff 或整段）；
2. 六类防御句分类清单（不必要免责/必要范围条件/真实方法学限定/有用概念对比/基于证据的限定/冗余澄清——每句一归类）；
3. 保留限定理由表（凡未删除的限定句，注明其命中的五项必要条件之一：论断有效性/证据解释/应用范围/研究设计/读者正确使用）。

**质量铁律（Preserve Necessary Precision 强化版）**：本仓论文有 10 条 Limitations、三层口径标注、[CITATION-NEEDED] 标记、首次性边界声明——这些属于"真实方法学限定"，**一律保留**。清理对象仅限"防御假想批评家"式多余对冲。拿不准时保留并归类为第 3 类，不删。

<!-- ==================== 适配块结束 ==================== -->


# Anti-Defensive Writing

## Core Rule

Advance the claim directly.

Say what is true, what the text argues, what the evidence shows, or what the method does. Do not default to explaining what the text does not claim, does not prove, does not imply, does not cover, or does not attempt.

Use a calm, competent authorial posture. Write as an author explaining an argument to the reader, not as an author negotiating with an imagined critic.

## Preserve Necessary Precision

Keep limitations when they are necessary for accuracy, ethics, law, safety, or methodological transparency.

A limitation is necessary when it affects:

- the validity of the claim;
- the interpretation of the evidence;
- the scope of application;
- the research design;
- the reader's ability to use the result correctly.

Write necessary limitations once, clearly and calmly. Place them in the appropriate section, usually methods, discussion, or limitations. Do not scatter them through abstracts, introductions, contribution paragraphs, topic sentences, conclusions, or executive summaries unless the limitation is essential to that exact sentence.

## Detection Checklist

Before finalizing a draft or revision, check for:

- unnecessary disclaimers;
- repeated statements of what the text does not claim;
- excessive hedging;
- caveats in high-impact positions;
- paragraphs that start with limitations;
- negative framing where positive framing would work;
- explanations added only to prevent hypothetical misunderstanding;
- self-undermining contribution statements;
- unnecessary "not X but Y" structures;
- redundant "however", "nevertheless", or "although" transitions.

Revise any item that weakens the text without improving accuracy.

## Rewrite Procedure

1. Identify the function of the defensive sentence.

Classify it as one of:

- unnecessary disclaimer;
- necessary scope condition;
- real methodological limitation;
- useful conceptual contrast;
- evidence-based qualification;
- redundant clarification.

2. Delete unnecessary disclaimers.

Remove any sentence that does not add evidence, scope, logic, conceptual precision, or necessary reader guidance.

3. Convert defensive limitation into positive scope.

Prefer:

> The analysis focuses on urban governance cases from 2015 to 2023.

Avoid:

> We do not claim that these cases are representative of all urban governance contexts.

4. Replace hedging with precision.

Prefer:

> The evidence indicates that X influences Y in these cases.

Avoid:

> This may suggest that X could potentially influence Y.

If uncertainty is real, specify its source:

> The available evidence supports this interpretation, although the design does not estimate population-level effects.

5. Rebuild the paragraph around the main point.

Ensure the paragraph has:

- a clear topic sentence;
- one main job;
- a logical sequence;
- no repeated caveats;
- no apology-like framing;
- a direct connection to the larger argument.

## Writing Principles

Lead with the claim. Start paragraphs with the point, not with a caveat.

Use positive scope. State what the text examines, explains, tests, compares, or contributes.

Strengthen with evidence, not apology. When a claim feels too broad, improve the concepts, evidence, causal logic, scope, or paragraph structure instead of adding protective caveats.

Keep one paragraph, one job. Do not mix argument, caveat, apology, exception, and clarification in the same paragraph.

Use contrast only when the contrast itself is part of the argument. Avoid reflexive "not X but Y", "rather than", "instead of", "to be clear", and "it should be noted that" structures.

## Preferred Patterns

Use patterns like:

- "This paper examines..."
- "This study shows..."
- "The analysis focuses on..."
- "The evidence indicates..."
- "This design allows..."
- "The results suggest..."
- "The central contribution is..."
- "This section explains..."
- "The argument proceeds in three steps..."
- "In this setting, X shapes Y by..."

## Discouraged Patterns

Avoid these unless they are necessary for accuracy:

- "This paper does not claim..."
- "We do not attempt to..."
- "This is not to say that..."
- "This should not be taken to mean..."
- "The goal is not X but Y..."
- "Rather than arguing X, this paper argues Y..."
- "Although this study has limitations..."
- "Of course, this does not fully capture..."
- "It is worth noting that..."
- "To be clear..."

## Examples

Defensive:

> We do not claim that these cases are representative of all contexts.

Stronger:

> The cases show how the mechanism operates across three institutional settings.

Defensive:

> This paper is not intended to provide a comprehensive theory of platform governance, but rather to examine one specific mechanism.

Stronger:

> This paper identifies a mechanism through which platform governance reshapes participation.

Defensive:

> This does not mean that policy design alone determines implementation outcomes.

Stronger:

> Implementation outcomes depend on how policy design interacts with administrative capacity.

Defensive:

> While the sample is limited and cannot capture every variation, it still offers useful insights.

Stronger:

> The sample captures the variation most relevant to the study's theoretical question.

Defensive:

> We are not arguing that this model is superior in every situation.

Stronger:

> The model is most useful when the task requires interpretable comparisons across cases.

## Final Pass

Before producing the final answer, remove any sentence that exists mainly to protect against a hypothetical objection rather than to advance the text. Deliver text that is concise, direct, confident, logically organized, and free of unnecessary disclaimers.


## STEP_MANIFEST 产出声明

- artifacts: 改写后文本（diff/整段）、六类防御句分类清单、保留限定理由表
- gates: 输出契约三件套完整性；Preserve Necessary Precision 五项必要条件逐条核对
- evidence: 分类清单即执行证据，落盘至工作区 .engine/evidence/
