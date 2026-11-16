from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "skill"
HOSTS = (
    ROOT / "dist" / "claude" / "skills" / "paper-spine",
    ROOT / "dist" / "codex" / "skills" / "paper-spine",
    ROOT / "dist" / "openclaw" / "skills" / "paper-spine",
)
KEY_FILES = (
    "SKILL.md",
    "references/journal-learning.md",
    "references/manuscript-format.md",
    "references/scientific-figure-workflow.md",
)

def normalized(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")

def main() -> int:
    for host in HOSTS:
        for relative in KEY_FILES:
            source = SOURCE / relative
            target = host / relative
            if not source.is_file() or not target.is_file():
                raise RuntimeError(f"missing public Skill projection: {target}")
            if normalized(source) != normalized(target):
                raise RuntimeError(f"public Skill projection drift: {target}")
    for source, target in (
        (ROOT / "src/adapters/claude/commands/paperspine.md", ROOT / "dist/claude/commands/paperspine.md"),
        (ROOT / "src/adapters/codex/prompts/paperspine.md", ROOT / "dist/codex/prompts/paperspine.md"),
    ):
        if normalized(source) != normalized(target):
            raise RuntimeError(f"public host entry drift: {target}")
    hermes = normalized(ROOT / "dist/hermes/skills/academic-writing/paper-spine/SKILL.md")
    body = normalized(SOURCE / "SKILL.md").split("---", 2)[2].lstrip("\n")
    if not hermes.endswith(body):
        raise RuntimeError("Hermes public Skill body drift")
    print("public Skill projections: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
