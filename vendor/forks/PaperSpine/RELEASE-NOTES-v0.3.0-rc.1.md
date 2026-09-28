# PaperSpine5 0.3.0-rc.1

PaperSpine5 is a local-first research production workspace that connects paper
configuration, contribution confirmation, scientific-figure review, and final
delivery inspection.  This prerelease adds the five-stage workspace UI while
preserving the existing `WUBING2023/PaperSpine` repository and update identity.

## Included packages

- Universal Skill package (recommended starting point)
- Codex plugin distribution
- Claude Code plugin distribution
- DSH package distribution

All four packages contain the same reviewed 176-file core with aggregate digest
`9eed412bf2a40b1e00787cd04de2adf696a662055ea31152ebc8f2899e2ba95f`.
See `manifest.json`, `checksums.sha256`, and the release evidence assets for the
exact byte counts and SHA-256 hashes.

## Accepted evidence

- PaperSpine accepted checkpoint: 267 tests
- PaperFigure: 60 tests
- V5 integration: 19 tests
- Package validation: 43 checks
- Workspace UI: 5 stages

The separately deferred Open Release Beta / 276-test branch is not part of this
release candidate.

## Boundaries

Automatic update remains disabled by default and requires explicit opt-in at
launch.  This RC has no independent cryptographic signature, second clean-machine
validation, macOS/Linux host run, or real remote old-to-new update validation.
Publishing this software never authorizes an external manuscript submission.

Scientific-figure export acknowledges the open-source
[img2ppt](https://github.com/tonytonyjan/img2ppt) project.  The Community Atlas
shows public GitHub stargazer aggregates only; it is not an install count,
active-user count, capability metric, paper count, or adoption claim.
