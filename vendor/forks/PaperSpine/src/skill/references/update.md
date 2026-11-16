# PaperSpine5 invocation checks and updates

Before paper production/resume, run the installed Skill's existing helper with
its verified Python (the bundled interpreter is sufficient):

```text
python -B scripts/paperspine_update.py --preflight --yes
```

It checks on each invocation, continues immediately when current, and applies a
newer full suite transactionally when available. Explicitly disabling automatic
updates with `--disable-auto-update` remains effective. The older opt-in `--auto`
mode retains its interval behavior. `--preflight --check-only` does not install.
A metadata network failure may continue the existing installation with a notice;
a corrupt package or install failure is an error, never a successful update.

## Stable channel and platform selection

The automatic suite channel is:

```text
https://raw.githubusercontent.com/WUBING2023/PaperSpine/main/website/downloads/update-channel.json
```

The channel supplies separate Windows x64, Linux glibc x86_64, macOS arm64 and
macOS x86_64 bundles. Unknown systems/architectures are rejected instead of falling
back to the Windows ZIP. Local diagnostics can use `--source <channel.json>`,
`--skill-root <paper-spine>` and `--control-root <updater-directory>`.
Never substitute a developer checkout for an installed release.

The installed wrapper uses the same canonical stable bootstrap bundled with the
Skill. Existing managed installs retain their configured update control directory.
An older public Skill without an installed-suite pointer can migrate through this
same transaction, preserving its previous files as a rollback backup. Paper data
and saved profiles are not moved or cleared. After an update reread the installed
Skill and current tool schemas. Gracefully restart a running old Web service on
its existing profile before using the new code; do not start duplicate writers.

## Getting the patch through an old entry

The published `paperspine-updater/1` apply protocol remains supported. An old
stable updater can install the new platform-specific channel (or exact ZIP plus
SHA-256), which carries both the workflow patch and new updater. Then invoke the
new installed `scripts/paperspine_update.py --preflight --yes` once: it also
refreshes the external old bootstrap from the verified installed bundle, without
redownloading when already current. Historical Linux/macOS bootstraps need the
matching `update-channel-<platform>.json` for this first hop because they do not
understand the new `bundles` mapping. The universal channel keeps a Windows
compatibility `bundle` for historical Windows bootstraps.

The older V4 component updater still discovers `dist/paperspine_version.json`.
Compatibility version 4.0.1 carries the new wrapper/bootstrap; the actual V5
product version is 0.4.0-alpha.2. These are separate version sequences. After
that one-time component update, the preflight selects the full suite for the
current operating system. It must not compare V5 0.4.x as a downgrade of V4 4.x.

The website manifest and install.ps1/install.sh remain supported explicit
installation/update entries. Verify manifest hashes and sizes before executing
downloaded code. A successful installer transaction, a reloaded host and a running
Web process are distinct observations; report only what actually ran.
