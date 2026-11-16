#!/usr/bin/env python3
"""Probe Codex's implicit skill catalog filtering (issue #433).

This does not make API/model calls and does not write invocation policies to ARIS.
The experiment uses two disposable scratch skills and Codex's debug surface.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


def catalog_visibility(stdout: str) -> dict[str, bool]:
    payload = json.loads(stdout)
    if not isinstance(payload, list):
        raise ValueError("expected a list of prompt messages")
    # A skill name in the user's prompt is not evidence of discovery.
    catalogs = [
        block["text"]
        for item in payload if isinstance(item, dict) and item.get("role") == "developer"
        for block in item.get("content", []) if isinstance(block, dict)
        if isinstance(block.get("text"), str) and "<skills_instructions>" in block["text"]
    ]
    if not catalogs:
        raise ValueError("no <skills_instructions> catalog in Codex debug output")
    return {
        skill: any(f"- {skill}:" in catalog for catalog in catalogs)
        for skill in ("plain-probe", "policy-probe")
    }


def run_codex(project: Path, home: Path, prompt: str) -> tuple[int, str, str]:
    env = {**os.environ, "CODEX_HOME": str(home)}
    result = subprocess.run(
        ["codex", "debug", "prompt-input", prompt],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    version = subprocess.run(["codex", "--version"], capture_output=True, text=True, check=True)
    print("Codex version:", version.stdout.strip())
    with tempfile.TemporaryDirectory(prefix="aris-codex-skill-probe-") as tmp:
        root = Path(tmp)
        project = root / "project"
        home = root / "codex-home"
        skills = project / ".agents" / "skills"
        home.mkdir()
        skills.mkdir(parents=True)
        # Codex project-scoped skill discovery requires a project trust context.
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        for name in ("plain-probe", "policy-probe"):
            skill_dir = skills / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: Disposable catalog probe.\n---\n\n"
                "This skill is used only to inspect catalog discovery.\n",
                encoding="utf-8",
            )
            if name == "policy-probe":
                metadata = skill_dir / "agents"
                metadata.mkdir()
                (metadata / "openai.yaml").write_text(
                    "policy:\n  allow_implicit_invocation: false\n", encoding="utf-8"
                )
        rc, stdout, stderr = run_codex(project, home, "Confirm skill catalog discovery.")
        if rc:
            print(f"Debug command failed rc={rc}; stderr={stderr[-1100:]!r}")
            return 2
        try:
            visibility = catalog_visibility(stdout)
        except ValueError as error:
            print(f"INCONCLUSIVE: {error}")
            return 2
        print("Observed skill metadata filtering:", json.dumps(visibility, sort_keys=True))
        if not visibility["plain-probe"]:
            print("INCONCLUSIVE: control skill not discovered")
            return 2
        if visibility["policy-probe"]:
            print("FAIL: explicit-only policy did not hide skill from implicit catalog")
            return 3
        print("PASS: policy suppresses implicit skill metadata in actual Codex CLI")
        print("LIMITATION: explicit parent-to-child invocation is not tested by debug prompt-input")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
