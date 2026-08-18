---
name: latex-cleanup
user_invocable: true
description: Review LaTeX documents for common issues, style consistency, typography, cross-references, draft artifacts, and debugging code. Use after editing LaTeX documents or before submission.
---

# latex-cleanup — LaTeX Document Review

Systematically review LaTeX documents and identify issues that need attention.

## When to Use

- "check my latex", "clean up the paper", "review formatting"
- After editing a LaTeX document
- Called by the `presubmit-checks` skill as one of its checks

## Workflow

### 1. Find the paper

Same search logic as other skills:
1. User-provided path
2. `paper/current/main.tex`
3. `paper/main.tex`
4. `main.tex`
5. Glob for `**/*.tex` with `\begin{document}`

### 2. Read the document

Identify all `.tex` files in the project (main file + `\input`/`\include` targets). Read the main document and any included files.

### 3. Run checks

Go through each checklist category below.

### 4. Report findings

Report organized by category with specific line references. Offer to fix issues when possible.

## Checklist Categories

### 1. Common Issues

- [ ] **Orphan/widow lines**: Check for single lines at top/bottom of pages (look for manual `\newpage` or `\clearpage` that might help)
- [ ] **Non-breaking spaces (`~`)**: Verify `~` before `\cite{}`, `\ref{}`, units (`100~kg`), and after titles (`Dr.~Smith`). Do NOT use `~` before `\footnote{}` (superscripts attach directly)
- [ ] **Citation formatting**: Ensure consistent citation style (e.g., `\citep` vs `\cite`, multiple citations in one command)
- [ ] **Figure/table placement**: Check `[htbp]` specifiers are appropriate, verify all figures/tables are referenced in text
- [ ] **Overfull/underfull boxes**: Look for potential causes (long words, improper hyphenation)

### 2. Style Consistency

- [ ] **Capitalization**: Title case vs sentence case in section headings, figure/table captions
- [ ] **Abbreviations**: First use spelled out, consistent usage (e.g., "Figure" vs "Fig.")
- [ ] **Math notation**: Consistent variable names, proper use of `\text{}` for non-variable words in math mode (e.g., `$P_{\text{data}}$` not `$P_{data}$`)
- [ ] **Math operators**: Use predefined operators (`\log`, `\exp`, `\sin`, `\max`, `\min`, `\Pr`, etc.) not italic text. For custom operators use `\operatorname{}` (e.g., `\operatorname{PMI}(x, y)` not `$PMI(x, y)$`)
- [ ] **Minus signs**: Use math mode for negative numbers (`$-10$` not `-10`)
- [ ] **Reference styles**: Consistent "Section~\ref{}" vs "Sec.~\ref{}" usage
- [ ] **Lists**: Consistent punctuation and capitalization in itemize/enumerate environments

### 3. Draft Artifacts and Cleanup

- [ ] **Remove comments**: Find `%` comments that should be removed (especially TODO, FIXME, NOTE)
- [ ] **Remove draft artifacts**: Check for `\lipsum`, placeholder text, `[draft]` options
- [ ] **Draft leftovers**: `TODO`, `FIXME`, `XXX`, `HACK` (case-insensitive)
- [ ] **Draft commands**: `\todo{`, `\note{`, `\marginpar{`
- [ ] **Debug packages**: `\usepackage{showkeys}`, `\usepackage{lineno}`
- [ ] **Draft mode**: `draft` option in `\documentclass`
- [ ] **Placeholder text**: `Lorem ipsum`, `TBD`, `PLACEHOLDER`
- [ ] **Commented-out sections**: Blocks longer than 5 lines
- [ ] **Check hyperlinks**: Verify URLs are valid and properly escaped
- [ ] **Verify bibliography**: All citations have corresponding bib entries, no unused entries
- [ ] **Check margins**: Verify document class options match submission requirements
- [ ] **Remove unused packages**: Identify `\usepackage` that may not be needed
- [ ] **Check for debugging code**: Remove `\showkeys`, `\overfullrule`, etc.

### 4. Cross-references

- [ ] **Undefined references**: Search for `??` in output or `\ref` to undefined labels
- [ ] **Duplicate labels**: Check for labels used more than once, including figures, tables, equations, sections, and appendices
- [ ] **Unused labels**: Labels defined but never referenced
- [ ] **Float reference order**: For each float family separately (figures, tables, algorithms, etc.), verify that items are first referenced in the same order they appear in the paper. Flag cases where, for example, Figure~`\ref{fig:third}` is first mentioned before Figure~`\ref{fig:second}`
- [ ] **Broken cross-file references**: For multi-file documents

For float reference-order checks, identify labeled floats in source order, then scan the manuscript text in reading order for the first reference to each label. Compare the two sequences within each float type separately; do not require one global order across figures, tables, algorithms, etc.

### 5. Typography

- [ ] **Quotation marks**: Use ``` `` ``` and `''` instead of `"`. Same for single quotes.
- [ ] **Dashes**: Proper use of `-`, `--`, `---` (hyphen, en-dash, em-dash). No space around em-dash.
- [ ] **Ellipsis**: Use `\ldots` or `\dots` instead of `...`
- [ ] **Percent symbol**: Use `\%` in text
- [ ] **Special characters**: Proper escaping of `&`, `#`, `$`, `_`

### 6. Source Formatting

- [ ] **One sentence per line**: Each sentence should start on its own line in the source. This produces cleaner git diffs, makes reordering easy, and allows easier commenting out individual sentences with `%`

### 7. Grammar and Language

- [ ] **General grammar check**: Read through the text and fix grammatical errors. Pay special attention to:
- [ ] **Subject-verb agreement**: Check for mismatches, especially in long sentences with intervening clauses
- [ ] **Article usage**: Missing or incorrect articles (a/an/the), common in non-native English writing
- [ ] **Tense consistency**: Verify consistent tense within sections. 
- [ ] **Dangling modifiers**: Participial phrases that don't attach to the intended subject
- [ ] **Parallel structure**: Items in lists, comparisons, and coordinating conjunctions should use parallel grammatical forms
- [ ] **Common academic writing errors**: "which" vs "that", "less" vs "fewer", "between" vs "among", "compared to" vs "compared with"
- [ ] **Redundancies**: e.g., "in order to" → "to", "a total of N" → "N", "the fact that" → "that"
- [ ] **Sentence fragments and run-ons**: Incomplete sentences or comma splices

## Output Format

Report findings in this format:

```
## [Category Name]

### [Issue Type]
- `filename.tex:123` - Description of issue
- `filename.tex:456` - Description of issue

**Suggested fix**: [If applicable]
```

## Rules

- Preserve the author's writing style and voice
- Focus on technical correctness, not stylistic preferences
- Prioritize issues that would cause compilation errors or submission rejection
- For borderline cases, ask the user for their preference
- Don't modify files without asking
