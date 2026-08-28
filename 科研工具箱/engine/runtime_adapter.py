"""Discover optional runtimes from this suite or the system PATH."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


CommandName = Literal["xelatex", "drawio", "node", "npm"]
PROJECT_ROOT = Path(__file__).resolve().parent.parent

_GUIDANCE = {
    "xelatex": "Install XeLaTeX (TeX Live or MiKTeX), or add it under runtime/texlive.",
    "drawio": "Install draw.io desktop, or add it under runtime/draw.io.",
    "node": "Install Node.js, or add it under runtime/node.",
    "npm": "Install npm with Node.js, or add it under runtime/node.",
}


@dataclass(frozen=True)
class RuntimePaths:
    root: Path | None
    commands: dict[str, Path | None]
    source: str

    @classmethod
    def discover(cls, project_root: Path | None = None) -> "RuntimePaths":
        runtime_root = (Path(project_root) if project_root else PROJECT_ROOT) / "runtime"
        commands = {
            "xelatex": _first_existing(runtime_root / "texlive", ["bin/xelatex.exe", "bin/xelatex"]),
            "drawio": _first_existing(runtime_root / "draw.io", ["draw.io.exe", "draw.io"]),
            "node": _first_existing(runtime_root / "node", ["node.exe", "node"]),
            "npm": _first_existing(runtime_root / "node", ["npm.cmd", "npm"]),
        }
        path_commands = {name: _path_from_path(name) for name in commands}
        merged_commands = {
            name: commands[name] or path_commands[name]
            for name in commands
        }
        if any(commands.values()):
            return cls(runtime_root, merged_commands, "suite_runtime")
        return cls(None, merged_commands, "PATH")

    def command(self, name: CommandName) -> Path:
        command = self.commands.get(name)
        if command is None:
            raise FileNotFoundError(f"Runtime command is unavailable: {name}. {_GUIDANCE[name]}")
        return command

    def capabilities(self) -> dict[str, object]:
        unavailable = [name for name, path in self.commands.items() if path is None]
        return {
            "suite_runtime": self.source == "suite_runtime",
            "source": self.source,
            "root": str(self.root) if self.root else None,
            "commands": {name: path is not None for name, path in self.commands.items()},
            "paths": {name: str(path) if path else None for name, path in self.commands.items()},
            "guidance": {name: _GUIDANCE[name] for name in unavailable},
        }


def _first_existing(root: Path, relatives: list[str]) -> Path | None:
    for relative in relatives:
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None


def _path_from_path(name: str) -> Path | None:
    candidates = ("drawio", "draw.io") if name == "drawio" else (name,)
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return Path(found)
    return None
