# PaperSpine5 0.4.0-alpha.3

Repair release for Windows workbench startup, long artifact paths, suite pointers,
and task-root preservation. Select the full suite for your platform; the current
release does not offer a separate Skill-only ZIP.

- Windows embedded Python includes pywin32 import paths. The normal HTTP
  workbench starts without an unconfigured reviewer identity; an explicit
  independent MCP reviewer remains separate.
- Artifact publication, verification, and replay read Windows extended paths,
  including task paths beyond MAX_PATH, without changing their logical receipts.
- Profile migration reuses populated `profile/user` task files and registry.
  If old and new roots both contain tasks, it stops for explicit inspection.
- The installer stages a verified Skill pointer only after suite first-start;
  `--clean-legacy` / `-CleanLegacy` skips archive writes when there is nothing
  to migrate. Existing task data and profile identity are retained.
- DSH has a local candidate adapter and component tests; no DSH-specific public
  package or generic Skill download is claimed for this release.

Windows local evidence: long-path publish/download/replay and P1 read PASS;
bundled pywintypes PASS; full install/update/rollback task retention PASS;
offline installer with a non-writable unused archive parent PASS. Four archives
passed exact manifest verification. After publication, [native CI on all four
platforms](https://github.com/WUBING2023/PaperSpine/actions/runs/35944185453)
passed the old-updater upgrade and bundled workspace startup checks. The exact
alpha.2-to-alpha.3 updater path was also tested locally on Windows.
This remains an alpha prerelease; macOS packages are unsigned and unnotarized.
