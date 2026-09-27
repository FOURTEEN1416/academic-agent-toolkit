---
name: doi-bibtex
user_invocable: true
description: "Fetches BibTeX from a DOI and adds it to a .bib file. Use when the user provides a DOI needing a bibliography entry."
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
