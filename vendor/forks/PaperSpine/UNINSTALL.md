# PaperSpine5 V5 uninstall and legacy cleanup

Close the host first. V5 installation keeps the active profile and paper task data
under `.paperspine5`; uninstalling the Skill does not delete that data.

To remove the active host Skill manually, move only:

- `%USERPROFILE%\\.codex\\skills\\paper-spine`
- `%USERPROFILE%\\.claude\\skills\\paper-spine`

Older V3/V4 names are archived, not deleted, when `-CleanLegacy` is passed to the
V5 installer. Restore a timestamped backup only when you intentionally need the
older host behavior.
