# Skill Packaging Context-On-Demand Policy v3.2.15f

Reusable skill packages should minimize always-loaded context while preserving all runtime rules.

## Packaging Rules

- Keep `SKILL.md` as the compact controller and highest-priority rule index.
- Put detailed policies in `references/` and load them only when the current request needs that rule family.
- Put reusable helpers and validators in `scripts/`.
- Keep project-specific paper facts, module names, variables, datasets, candidate descriptions, generated images, and audit outputs out of the reusable skill package; they belong in run outputs and cumulative checkpoints.
- Preserve UTF-8 exact text for fixed Chinese reply/origin strings.
- Do not retain stale release-validation files, patch reports, build caches, `__pycache__`, temporary work directories, or project run outputs in the clean release package.

## Recommended Release-Retained Files

- `SKILL.md`
- `README.md`
- `CHANGELOG.md`
- `VERSION`
- `metadata.json`
- `agents/`
- `assets/`
- `examples/`
- `publish/`
- `references/`
- `scripts/`
- `templates/`
- `LICENSE`

Historical patch reports and prior release validation reports are not runtime dependencies. A clean 3.2.15f release should not carry them unless the user explicitly asks for a development archive.
