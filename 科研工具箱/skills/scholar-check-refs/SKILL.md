---
name: check-refs
user_invocable: true
description: Verify citation references in a LaTeX paper. Checks that all cited papers exist in academic databases, flags suspicious entries, and suggests missing DOIs/URLs. Use when the user wants to check references, verify citations, or before submission.
---

# check-refs — Citation Reference Check

Verify all references in a LaTeX paper against academic databases.

## When to Use

- "check my references", "verify citations", "check refs"
- Called by the `presubmit-checks` skill as one of its checks
- Before submitting a paper draft

## Workflow

### 1. Find the paper files

Look for `.tex` and `.bib` files. Common project structures:

- `paper/current/main.tex` + `paper/current/main.bib` (standard project template)
- `paper/current/main.tex` + `paper/current/references.bib`
- `paper/main.tex` + `paper/main.bib` (flat layout)
- `main.tex` + `references.bib` (root-level)

Search order:
1. If user provides a path, use it
2. Look for `paper/current/main.tex`
3. Look for `paper/main.tex`
4. Look for `main.tex` in current directory
5. Glob for `**/*.tex` and pick the main file (the one with `\begin{document}`)

For `.bib`: look for `main.bib` or `references.bib` next to the `.tex` file, or let bibsleuth auto-detect from `\bibliography{}`.

### 2. Run existence check (fast, no API key needed)

Run in the background with a 10-minute timeout — bibsleuth queries multiple academic APIs and can take several minutes for large bibliographies. Bibsleuth writes `bibsleuth-report.json` and `bibsleuth-report.md` next to the input file by default.

```bash
# Use Bash tool with run_in_background: true, timeout: 600000
uvx bibsleuth check <TEX_FILE> --bib <BIB_FILE> --no-llm
```

Tell the user the check is running in the background and continue with other work. You will be notified when it completes.

### 3. Present results

Once notified that the command finished, read the `bibsleuth-report.md` file (in the same directory as the input file) and summarize:
- The report is grouped by verdict (verified, likely, unverified, error) and entry category (academic papers, books, software/data)
- Focus on **unverified** entries — these need attention
- List **suggested patches** (missing DOIs, URLs) from the patches section
- Tell the user where the full report file is

### 4. Offer next steps

- **Apply patches**: offer to add suggested DOIs/URLs to the `.bib` file (ask before editing)
- **Full LLM analysis**: if user wants mis-citation detection and missing citation suggestions, run without `--no-llm` (requires `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`). Also run in background with 10-minute timeout:
  ```bash
  uvx bibsleuth check <TEX_FILE> --bib <BIB_FILE>
  ```
- **Save to library**: `uvx bibsleuth library add <BIB_FILE>`

### 5. LLM analysis results (if run)

Summarize additional findings:
- **Mis-citations**: cited paper may not support the claim made in the text
- **Suggested papers**: candidates for claims that could use stronger citations
- **Contradictions**: well-cited papers that argue against claims in the paper

## Rules

- Always run `--no-llm` first — it's fast and free
- Don't automatically edit the `.bib` — ask before applying patches
- If bibsleuth is not installed, run `uv tool install bibsleuth` first
