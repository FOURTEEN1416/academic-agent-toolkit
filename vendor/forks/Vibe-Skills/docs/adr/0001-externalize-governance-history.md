---
status: accepted
---

# Externalize governance history

Vibe-Skills will keep at most thirty live Markdown documents across the root, `docs`, and `references` surfaces, with executable contracts owning runtime truth and a single machine-readable index naming the live documents. Generated requirements, plans, status snapshots, and proof bundles will be retained as CI or release artifacts; completed historical material will be removed from the main branch after one explicit release-cycle compatibility window because reducing continuing maintenance cost outweighs keeping a browsable in-tree governance archive.

PR proof artifacts are retained for 30 days, main-branch and scheduled-audit artifacts for 90 days, and formal release proof with the corresponding GitHub Release. The tracked `current-state.md` summary will be retired in favor of CI, release metadata, and live `check` output.
