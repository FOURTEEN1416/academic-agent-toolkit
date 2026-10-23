# Upstream Source Record

- Upstream: https://github.com/Changchao-Li/plastisphere_microalgae
- Fork (fork-first rule): https://github.com/FOURTEEN1416/plastisphere_microalgae
- Pinned commit: 843e5b6b217d2ae3e61e3d92ed54aa84f727303e
- Checklist date: 2026-09-11
- License: **none declared upstream** (no LICENSE file) → no redistribution authorization
  is implied by that absence; the directory is maintained as a localized derivative
  (see `../ADAPTATION.md`).
- Vendored: 6 R scripts under `scripts/` taken from the pinned commit;
  `Enrich species compare.R` renamed to `enrich_species_compare.R` (filename change only).
  Upstream study data files (CSV/TXT) intentionally NOT vendored.
- Local adaptation: `SKILL.md` is original ACAT authoring (template catalog / contracts /
  workflow). The 6 R scripts are **no longer byte-identical upstream copies**: each one
  sources `scripts/_eco_style.R` (unified `theme_classic` theme, CJK font fallback chain,
  print-scale mm export, Okabe-Ito semantic palette) and keeps only template-specific logic.

## Upgrade rule

Re-fetch the fork after upstream updates, diff the 6 scripts against this directory,
re-apply the local style block (top-of-file `source("_eco_style.R")` + `theme_set(eco_theme(<mm>))`
+ `eco_*` sizing/palette calls) on top of any upstream change rather than overwriting the
localized files, then refresh the Pinned commit and Checklist date here.
