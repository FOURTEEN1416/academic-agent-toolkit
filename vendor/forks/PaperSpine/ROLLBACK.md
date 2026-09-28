# PaperSpine5 release rollback

The immutable rollback point for this candidate is the commit referenced by tag
`v0.3.0-rc.1`.  Release ZIP files must never be replaced in place.

If the website is faulty, redeploy the preceding successful GitHub Pages artifact
or revert only the website commit and rerun the Pages workflow.  If an artifact is
faulty, mark this prerelease as withdrawn and publish a new version with new
filenames and checksums.  Do not delete or overwrite evidence needed to explain
the withdrawal.

PaperSpine V4 remains available from the repository root and its established
`dist/paperspine_version.json` update source.  V5 is opt-in, so rolling back the V5
page or prerelease does not require changing the V4 user-data identity.
