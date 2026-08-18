---
name: doi-bibtex
user_invocable: true
description: Fetch BibTeX citation from DOI and add to .bib file. Use when user provides a DOI and needs BibTeX entry added to their bibliography, especially when working on academic papers.
---

# DOI to BibTeX

## Fetch BibTeX

```bash
./scripts/doi2bib.sh <DOI>
```

> Paths are relative to this skill's directory.

Accepts bare DOIs (`10.1038/nature12373`) or full URLs.

## Workflow

1. Fetch the BibTeX entry
2. Find .bib file (check current dir, then parents; common names: `references.bib`, `main.bib`)
3. Show the entry and ask user: add to found file, specify different file, or just display
4. If adding: check for duplicate DOI first, then append
