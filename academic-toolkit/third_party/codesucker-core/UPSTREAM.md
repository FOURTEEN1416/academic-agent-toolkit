# Vendored CodeSucker Core

- Upstream: https://github.com/fanbuz/codesucker
- Upstream version: `0.4.4`
- Pinned commit: `b065a1825f4e32dca4c4b7fd8bccf3e020a77c5c`
- Vendored on: `2026-08-18`
- Local use: only `packages/core/src`; Electron application code is not part of the execution path. Runtime dependencies are declared in the local minimal `package.json`.
- License: Apache-2.0; see `LICENSE` and `NOTICE`.

## Local adaptation

The upstream core is consumed through `third_party/codesucker-core/codesucker-cli.mjs`. The CLI owns
the JSON protocol, workspace-safe output paths, deterministic serialization, and
manifest generation. A local portability patch in
`packages/core/src/discover.ts` uses `**/*.ext` for a singleton extension
instead of `**/*.{ext}`, because the latter does not match on the supported
Windows runtime. Core algorithm files are not otherwise edited locally unless
this file is updated with the exact file, reason, and regression test.
The output hash map intentionally excludes the manifest file itself to avoid a
self-referential digest; the manifest hashes all other source-materials files.

## 2026-09-26 local publication hardening

- File: `codesucker-cli.mjs` (local adapter only; upstream core algorithms unchanged).
- Reason: an independent full regression observed Windows `EPERM` on the final
  temporary-directory rename after all nine material files had been written.
- Change: retry only the final rename for Windows `EPERM` / `EACCES` / `EBUSY`,
  up to five retries (25/50/100/200/400 ms). Never regenerate materials or suppress
  a permanent error; keep the temporary output on failure and refuse a conflicting
  destination. The existing generation and validation contract is unchanged.
- Regression: `tests/test_codesucker_materials.py::test_directory_publication_retries_only_transient_windows_locks`
  covers normal publication, three transient codes, exhaustion, other errors,
  non-Windows behavior and a competing destination. CLI import no longer executes
  its entrypoint, allowing direct tests of the same publication function.

## Upgrade rule

An upgrade must pin a commit, refresh this file and the license audit, then run
the core smoke tests plus the suite bridge and end-to-end tests. Runtime network
access is never required for source processing.
