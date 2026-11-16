# PaperSpine5 for DSH

This native DSH Bundle registers the official MCP client and the existing
`paper-spine` Skill through DSH's filesystem Skill provider. Research and writing
remain the host Agent's work; the shared Web/core handles configuration, choices,
previews, downloads and same-task feedback.

## Install a built bundle

Choose the bundle matching your platform. Extract the entire ZIP, then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Profile web
```

```sh
sh ./install.sh web
```

DSH and its Node/pnpm prerequisites must already be installed. The installer uses
bundled Python and never downloads or upgrades DSH. If DSH is not on PATH, set
`DSH_BIN` to its executable or official `lib/bin.js` entry, or use `-DshBin` on
PowerShell / `--dsh-bin` on POSIX. Restart the selected DSH profile, then ask it to
use paper-spine. No manual MCP path or separate web-core installation is needed.

The installer verifies the core suite, prepares and health-checks a new copy,
then binds it at `~/.paperspine5/releases/<version>/dsh-paperspine5`. An existing
bundle is retained in an adjacent backup directory. Configuration/link failure
restores that directory; DSH/pnpm's own profile mutations are not a transactional
part of this rollback. User task data remains outside the release bundle.

Use `-Target <directory> -NoLink` or `--target <directory> --no-link` to prepare an
isolated installation without changing a profile. Close running PaperSpine MCP
processes before replacing their bundle. Keep backups until a new DSH session
has been checked. Re-run the installer for an explicit upgrade; background
auto-update is not enabled.

For maintainers, the normal canonical Skill update command
`python -B 01_PaperSpine4/src/scripts/sync_local_installs.py` also rebuilds and
replaces recognized existing DSH installs from the current source. It does not
create a new DSH installation when none exists. `--dist-only` only generates
files; `--skip-dsh` omits DSH; `--dsh-target <installed-directory>` selects one
recognized installation. Close its running PaperSpine processes before syncing,
then start a new DSH session to load the update. This is synchronization during
the normal update command, not a background watcher or remote update service.

For a DSH-only source update, run
`python -B 06_插件化/release/sync_dsh_install.py --source-root <checkout>`.
The helper builds one verified suite and DSH archive, reuses the installer at
the same stable path with `--no-link`, and preserves adjacent backups. It leaves
profile links and model settings in place. A failure stops the sync before its
success state is recorded; already-updated other hosts are not rolled back.

## Reproducible maintenance

The only adapter source is this directory. The standard suite builder includes
it as `adapters/dsh`. `release_cli.py build --dsh-output <dsh.zip>` and
`build_portable_suite.py --dsh-output <dsh.zip>` project it with a verified suite
into one complete package. Portable builds refresh both canonical Skill
projections from current source, including removed resources, before computing
the new manifest. `release_cli.py build-dsh --bundle <suite.zip>
--output <dsh.zip>` also works for suites built with the current adapter.

The DSH package's `core/` is the unmodified platform suite: the same runtime,
Web and `core/standalone/paper-spine` used by other hosts. Version, build ID,
platform and checksums come from that suite. Builders never bind developer
paths. `configure_dsh.py` chooses the included interpreter and rebinds owned
paths after a move. A source checkout remains usable for development but is
not a self-contained distribution.

This local candidate does not replace previously published assets. Windows
installation and real MCP readiness are checked separately from native POSIX
execution and DSH model/whole-paper acceptance.
