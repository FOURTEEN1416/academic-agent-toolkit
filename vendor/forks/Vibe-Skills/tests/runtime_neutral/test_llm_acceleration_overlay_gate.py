from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / "scripts" / "verify" / "vibe-llm-acceleration-overlay-gate.ps1"
POLICY_PATH = REPO_ROOT / "config" / "llm-acceleration-policy.json"


def resolve_powershell() -> str | None:
    candidates = [
        shutil.which("pwsh"),
        shutil.which("pwsh.exe"),
        r"C:\Program Files\PowerShell\7\pwsh.exe",
        r"C:\Program Files\PowerShell\7-preview\pwsh.exe",
        shutil.which("powershell"),
        shutil.which("powershell.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


class LlmAccelerationOverlayGateTests(unittest.TestCase):
    def test_task_type_git_diff_gating_is_implemented_and_verified(self) -> None:
        powershell = resolve_powershell()
        if powershell is None:
            self.skipTest("PowerShell executable not available in PATH")

        with tempfile.TemporaryDirectory() as tempdir:
            script_path = Path(tempdir) / "probe-git-diff-gate.ps1"
            script_path.write_text(
                "\n".join(
                    [
                        "$ErrorActionPreference = 'Stop'",
                        f"$repoRoot = '{REPO_ROOT.as_posix()}'",
                        f". '{(REPO_ROOT / 'scripts' / 'router' / 'modules' / '00-core-utils.ps1').as_posix()}'",
                        f". '{(REPO_ROOT / 'scripts' / 'router' / 'modules' / '48-llm-acceleration-overlay.ps1').as_posix()}'",
                        f"$policy = Get-Content -LiteralPath '{POLICY_PATH.as_posix()}' -Raw -Encoding UTF8 | ConvertFrom-Json",
                        "$policy.context.mode = 'diff_snippets_ok'",
                        "$policy.context.include_git_status = $false",
                        "$policy.context.include_git_diff = $true",
                        "$policy.context.git_diff_task_allow = @('coding','debug','review')",
                        "$resolved = Get-LlmAccelerationPolicy -Policy $policy",
                        "Push-Location $repoRoot",
                        "try {",
                        "  $planning = Get-VcoGitContextSnippet -PolicyResolved $resolved -VcoRepoRoot $repoRoot -QueryText 'inspect policy drift' -TaskType 'planning'",
                        "  $coding = Get-VcoGitContextSnippet -PolicyResolved $resolved -VcoRepoRoot $repoRoot -QueryText 'fix policy drift' -TaskType 'coding'",
                        "  [pscustomobject]@{ planning = $planning.diff_mode; coding = $coding.diff_mode } | ConvertTo-Json -Compress",
                        "} finally {",
                        "  Pop-Location",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    powershell,
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)
        self.assertIn('"planning":"skipped_task_type"', result.stdout)
        self.assertIn('"coding":"full"', result.stdout)

        gate_text = GATE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("[planning] git diff context is skipped by task type", gate_text)
        self.assertIn("[coding] git diff context remains eligible", gate_text)


if __name__ == "__main__":
    unittest.main()
