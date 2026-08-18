---
name: critique-manuscript
user_invocable: true
description: Structured self-review of your manuscript before submission. Systematic evaluation across review criteria.
---

# critique-manuscript

Systematically critique your own manuscript before submission. Evaluates the paper across several criteria, identifies weaknesses, and suggests improvements.

This skill is for reviewing your own work. Do not use it on others' unpublished manuscripts — uploading someone else's unpublished work to an AI system raises serious ethical concerns.

## When to Use

- "critique my manuscript", "review my preprint", "find weaknesses in my paper"
- "what will reviewers flag?", "is my paper ready for submission?"
- Once you have a rough draft up to the point of submission 
- As a follow-up (or prior) to `/presubmit-checks` (which covers formatting and technical issues)

## Workflow

### Phase 1: Setup

#### 1. Find the paper

Search in this order:
1. User-provided path
2. `paper/current/main.tex`
3. `paper/main.tex`
4. `main.tex`
5. Glob for `**/*.tex` with `\begin{document}`

#### 2. Setup via AskUserQuestion

Use the `AskUserQuestion` tool to collect setup in one step. Two questions:

1. **"Is this your own manuscript?"** (header: "Ownership")
   - Options: "Yes, it's mine" / "No"
   - If "No": decline to proceed and explain why — uploading someone else's unpublished manuscript to an AI system without their consent risks exposing unpublished ideas, methods, and results. The content may be used for model training or retained in logs, potentially compromising the authors' ability to publish first or maintain confidentiality during peer review.

2. **"Should I search for potentially missing literature via OpenAlex?"** (header: "Lit search")
   - Options: "No, stay local" (recommended) / "Yes, search OpenAlex"
   - Default is local-only. If opted in, the literature criterion will use `/openalex`.

### Phase 2: Read and summarize

Read the manuscript thoroughly. Write a brief neutral summary covering:
- The research question
- The approach / method
- Key findings
- The claimed contribution

This step ensures understanding before critiquing. Do not evaluate yet — just demonstrate that the work has been understood.

### Phase 3: Evaluate against review criteria

Work through each criterion. For each one that applies, identify specific weaknesses and suggest fixes. Skip criteria that are not relevant to the paper.

#### 1. Literature and novelty

Is the paper well-situated in prior work? Key questions:
- Are there obvious gaps in the literature review?
- Is the claimed contribution clearly distinguished from existing work?
- Could a reviewer argue the contribution is too incremental or already known?
- Are the most relevant and recent references cited?

If literature gaps are suspected, note them and guide the user on what to ask Claude to search for. For example: "You could ask me to search OpenAlex for papers on [specific topic] by [specific authors/groups] to check whether key references are missing." Provide concrete query suggestions — topics, author names, keywords — so the user can decide whether to follow up.

If the user explicitly requests a literature search, use `/openalex` to run targeted queries derived from:
- The paper's title and key claims
- Specific novelty claims that seem under-supported
- Author names or research groups working in the same area

Present results as "potentially relevant papers to review" — clearly distinguish suspected gaps from confirmed missing prior work.

#### 2. Methodological rigor

Are the methods appropriate and well-validated? Key questions:
- Are measurements and proxies valid? Do they capture what they claim to capture?
- Are the choices of methods valid? 
- Are baselines and null models appropriate and up-to-date?
- Are robustness checks warranted & present (sensitivity to parameters, assumptions)?
- Is uncertainty quantified?
- Is the sample size adequate?

#### 3. Causal claims and confounders

Does the paper make claims that outrun the evidence? Key questions:
- Does it claim or imply causation from correlational evidence?
- Are plausible confounders identified and addressed?
- Are claims appropriately hedged (associational vs. causal language)?
- Could a simpler explanation (e.g., selection bias, a null model) account for the findings?

#### 4. Data quality and limitations

Is the data appropriate for the research question? Key questions:
- Is the dataset representative, or is there selection bias?
- What are the systematic biases in the data? How could they affect the results? Could the biases in data or methodologies explain some of the results?
- Are there temporal artifacts or period-specific distortions?
- Are limitations discussed honestly and prominently?
- Is the data publicly available or reproducible?

#### 5. Generalizability

How broadly do the findings apply? Key questions:
- Are boundary conditions discussed?
- Would the findings hold in other contexts, datasets, or populations?
- If narrow, should the paper be reframed as a case study?

#### 6. Mechanism

Does the paper explain *how* and *why*, not just *what*? Key questions:
- Is there a theoretical framework or mechanistic explanation?
- Are the findings purely descriptive, or is there insight into underlying processes?
- Could the paper benefit from additional analysis to unpack the "why"?

#### 7. Clarity and presentation

Is the paper well-written and self-contained? Key questions:
- Does the abstract accurately reflect the paper's actual content and findings?
- Is the title accurate and specific?
- Is notation consistent throughout?
- Are figures informative, well-labeled, and referenced in the text?
- Does the narrative have a clear driving question?
- Does the framing in the introduction match what the results actually show?
- Does the discussion add insight beyond restating results?
- Is the paper an appropriate length for the content?

### Phase 4: Write the critique report

Before writing, confirm with the user: "I'll save the critique as `YYYY-MM-DD-critique-report.md` next to the paper — okay?"

Use this structure:

```markdown
# Manuscript Critique

**Date**: YYYY-MM-DD
**Paper**: [title or filename]

## Summary

(1-3 sentences)

## Top findings

### Top risks
The 3 most important weaknesses that reviewers are likely to flag.

### What to preserve
Key strengths that should survive revisions.

### Anticipated reviewer questions
Questions reviewers are likely to ask. Preparing answers strengthens the paper and cover letter.

## Detailed comments

(Criterion-by-criterion assessment. For each, note strengths, flag weaknesses with suggested fixes. Skip criteria that don't apply.)

### Literature and novelty

...

### Methodological rigor

...

### Causal claims and confounders

...

### Data quality and limitations

...

### Generalizability

...

### Mechanism

...

### Clarity and presentation

...
```

For each criterion section, anchor every critique point to a specific location in the manuscript (section, figure, table, paragraph, or quoted claim). Vague feedback like "the literature review has gaps" is not useful — instead: "Section 2 does not cite any work on [topic], despite claiming novelty in this area (paragraph 3)."

After writing the file, print a brief summary to the conversation highlighting the top findings. When flagging literature gaps, suggest specific keywords, author names, or research areas the user can ask Claude to search for.

## Rules

- This skill is for critiquing the user's own manuscript. Do not use it on others' unpublished work.
- Summarize before critiquing — demonstrate understanding first.
- Be candid and forthright about weaknesses — the whole point is to find them before reviewers do.
- Frame issues constructively with actionable suggestions for each weakness.
- Do not fabricate references — if you suspect missing literature, say so and suggest keywords, author names, or research areas to check.
- Keep the critique proportional to the paper — a short workshop paper does not need pages of feedback.
- Present strengths alongside weaknesses — the author needs to hear suggestions regarding what to preserve, not just what to fix.
- In the critique report, use author-directed language ("your methods", "your claims", "your literature review").
- Anchor every critique point to a specific location in the manuscript — cite the section, figure, table, or quoted claim. Generic feedback without evidence is not actionable.
