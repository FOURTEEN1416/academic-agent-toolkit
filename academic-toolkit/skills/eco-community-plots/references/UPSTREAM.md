# Upstream Source Record

- Upstream: https://github.com/Changchao-Li/plastisphere_microalgae
- Fork (fork-first rule): https://github.com/FOURTEEN1416/plastisphere_microalgae
- Pinned commit: 843e5b6b217d2ae3e61e3d92ed54aa84f727303e
- Checklist date: 2026-09-11
- License: **none declared upstream** (no LICENSE file) → whole skill directory is
  .gitignore-isolated, local use only, no redistribution.
- Vendored: 6 R scripts under `scripts/` copied byte-identical from the pinned commit;
  `Enrich species compare.R` renamed to `enrich_species_compare.R` (filename only, content
  untouched). Upstream study data files (CSV/TXT) intentionally NOT vendored.
- Local adaptation: `SKILL.md` is original ACAT authoring (template catalog / contracts /
  workflow wrapped around the upstream scripts); scripts themselves are unmodified.

## Upgrade rule

Re-fetch the fork after upstream updates, diff the 6 scripts against this directory,
re-sync only what changed, then refresh the Pinned commit and Checklist date here.
