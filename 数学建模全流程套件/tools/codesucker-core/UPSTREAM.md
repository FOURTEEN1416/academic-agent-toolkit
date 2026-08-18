# Vendored CodeSucker Core

- Upstream: https://github.com/fanbuz/codesucker
- Upstream version: `0.4.4`
- Pinned commit: `b065a1825f4e32dca4c4b7fd8bccf3e020a77c5c`
- Vendored on: `2026-08-18`
- Local use: only `packages/core/src`; Electron application code is not part of the execution path. Runtime dependencies are declared in the local minimal `package.json`.
- License: Apache-2.0; see `LICENSE` and `NOTICE`.

## Local adaptation

The upstream core is consumed through `tools/codesucker-cli.mjs`. The CLI owns
the JSON protocol, workspace-safe output paths, deterministic serialization, and
manifest generation. A local portability patch in
`packages/core/src/discover.ts` uses `**/*.ext` for a singleton extension
instead of `**/*.{ext}`, because the latter does not match on the supported
Windows runtime. Core algorithm files are not otherwise edited locally unless
this file is updated with the exact file, reason, and regression test.
The output hash map intentionally excludes the manifest file itself to avoid a
self-referential digest; the manifest hashes all other source-materials files.

## Upgrade rule

An upgrade must pin a commit, refresh this file and the license audit, then run
the core smoke tests plus the suite bridge and end-to-end tests. Runtime network
access is never required for source processing.
