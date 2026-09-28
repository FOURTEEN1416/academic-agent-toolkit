# Release Absolute-Path Scan Checklist

Run this checklist before shipping a skill package.

## Required command

```bash
python scripts/figure_studio_release_check_paths.py scan --target <package-dir-or-zip> --fail-on-match
```

## What the check protects against

- build-machine user directories;
- local Codex install paths;
- sandbox or temporary runtime paths;
- absolute paths embedded in examples, metadata, manifests, templates, markdown, JSON, or generated artifacts;
- atlas board links that only work on the release builder's machine.

## Passing criteria

- All persisted package references are package-relative.
- Atlas board references use `assets/subtype-atlas/boards/...` or another package-relative path.
- No host-specific paths are present in package files.
- The release report is saved or attached to the release checklist.
- PR descriptions may mention that absolute paths were replaced, but must not paste the original host-specific absolute paths.

## Failure behavior

If any absolute-path hit is found:

1. Do not publish the zip.
2. Replace the offending reference with a package-relative path or a runtime-resolved path that is not persisted.
3. Re-run the scanner.
4. Record the cleaned release in `publish/release_checklist.md`.

## Python cache artifacts

Release packages must not contain `__pycache__/` directories or `*.pyc` files. These files can embed build-machine paths and must be treated as release blockers. The reusable scanner reports them as `python_cache_artifact`.

## Required cleanup command before packaging

For project output packaging, run a state health check first:

```bash
python scripts/figure_studio_state.py doctor --project-id <project_id>
```

Run this before creating a skill release zip:

```bash
python scripts/figure_studio_release_check_paths.py clean-caches --target <release-staging-dir>
python scripts/figure_studio_release_check_paths.py scan --target <release-staging-dir-or-zip> --fail-on-match
```

The release zip must fail if `python_cache_artifact` findings are reported.
