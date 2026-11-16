# PaperSpine5 rollback

Current prerelease: `v0.4.0-alpha.2`. Stop the workbench at a saved boundary before
rollback, preserving its profile and paper task data. Use the rollback path for
the installer that performed the update; do not create a replacement paper task.

For an invocation update through `scripts/paperspine_update.py --preflight`, use
the stable updater and the exact control directory recorded by that update:

```text
python <control-root>/paperspine_update.py rollback --control-root <control-root> --yes
```

The common control directory is `~/.paperspine5/updater`; some installations use
a distinct directory, so use the actual recorded path. For an interrupted update,
use `recover` in place of `rollback`. The transaction verifies and restores its
previous Skill, updater and settings without migrating paper task data.

For a profile installation performed by the full-suite installer, run the suite
launcher with the same profile and an existing installed build ID:

```powershell
.\paperspine.cmd rollback --profile-root "<existing-profile>" --target-build-id "<previous-build-id>" --operation-id rollback
```

```sh
./paperspine rollback --profile-root "<existing-profile>" --target-build-id "<previous-build-id>" --operation-id rollback
```

Reload the host and restart the same profile after rollback. Retain the backup
until the restored installation has been checked. Never overwrite an existing
published binary; publish a new patch version for a corrected package. Older
release tags and assets remain available as historical versions.
