# PaperSpine5 0.4.0-alpha.2

Fixes for a paper progressing locally while its workbench remains at an earlier
stage, unclear continuation after saving, and material file locks stopping work.

- The host must publish/read back the previous segment in the same workbench
  before starting the next segment or stage. No artificial review completion.
- A persistent save/phase dialog tells the user to return to the same host task.
- Explicit material selection, replaceable roots and visible per-file warnings
  preserve successful inputs and saved scope. A verified prior copy is identified
  honestly when a temporary read fails.
- The existing updater can bridge to this patch and refresh itself. Invocation
  checks the platform channel; current installations do not redownload a suite.
  Windows x64, Linux glibc x86_64, macOS arm64 and Intel use separate bundles.

Use the full suite for your operating system. Skill-only and compatibility ZIPs
are advanced migration assets and do not include a runtime or Web workspace.

Local evidence: material/stage regressions 8 PASS; updater 25 PASS; original
wrapper tests 19 PASS and preflight 15 PASS; relevant UI checks 21 + 8 PASS;
unchanged published old updater to final Windows candidate and bundled Python
Web/host smoke PASS. All four platforms passed native old-updater upgrades, updater self-refresh,
and bundled Python workspace/host startup: [CI evidence](https://github.com/WUBING2023/PaperSpine/actions/runs/35599624088).
Task data and configuration were retained in isolated upgrade replays.
This remains an alpha prerelease. macOS packages are unsigned/unnotarized.
