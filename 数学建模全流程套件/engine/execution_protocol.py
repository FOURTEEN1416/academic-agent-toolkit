"""Versioned, workspace-contained execution evidence for workflow steps."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from .opencode_bridge import StepAction, StepResult


SCHEMA_VERSION = 1
_REQUIRED_FIELDS = {
    "schema_version", "agent", "step_id", "skill_name", "skill_sha256",
    "commands", "inputs", "outputs",
}

# 描述性伪命令检测：真正的 shell 命令应以可执行程序/解释器开头。
# 例如 "python tools/x.py --flag" 合法；"python workbook inspection for ..." 是描述文本。
_COMMAND_EXECUTABLE_RE = (
    r"^\s*(?P<exe>[A-Za-z0-9_./\\-]+(?:\.[Ee][Xx][Ee])?)\s+"
    r"(?:-[A-Za-z]|--[A-Za-z]|[/\w.-])"
)
_SHELL_TOKEN_RE = re.compile(r"^\s*[A-Za-z0-9_./\\-]+(?:\.[Ee][Xx][Ee])?(\s+.*)?$")


def _looks_like_descriptive_command(command: str) -> bool:
    """启发式判断命令是否为描述性文本（伪命令）。

    判定为伪命令的条件（任一）：
    1. 命令文本包含句子性标点（句号+空格、中文句号、逗号后接中文等），
       且不以可执行文件/脚本路径开头；
    2. 首词不是已知可执行程序/解释器/脚本且包含空格后接自然语言动词
       （inspection/check/review/generation/verification 等名词短语）。
    保守起见：仅当同时满足「首词可执行」与「命令不含 shell 元字符/重定向/管道」
    之外的描述性特征时才判伪——宁可放行不可误伤。
    """
    text = command.strip()
    if not text:
        return True
    # 描述性箭头（-> / →）优先检测——"main.docx -> main.pdf" 是流程描述，
    # 且其中的 ">" 会与 shell 重定向元字符混淆，必须先于 shell 检查处理。
    if "->" in text or "→" in text:
        return True
    # 允许常见的 shell 结构（管道/重定向/逻辑符/子 shell）——这些是真实命令
    shell_constructs = ("|", ">", "<", "&&", "||", ";", "$(", "`")
    if any(c in text for c in shell_constructs):
        return False
    # 描述性句子特征：以句号/中文句号结尾
    if text.endswith((".", "。", "！", "？")):
        return True
    # 解析首词与剩余部分
    parts = text.split(None, 1)
    first_token = parts[0]
    rest = parts[1].strip() if len(parts) > 1 else ""
    # `-c` / `-m` / `--flag` 等立即参数：解释器直接执行代码/模块 → 真实命令；
    # 但 `-c` 后只有注释文本（# 开头、无实际代码）属于伪命令。
    if rest.startswith(("-c", "-m", "--")):
        if rest.startswith("-c"):
            code = rest[2:].strip().strip('"').strip("'")
            if code.startswith("#") or not code:
                return True
        return False
    # "python xxx inspection for ..." 这类描述（首词可执行但后续是自然语言）
    executable_roots = {
        "python", "python3", "py", "bash", "sh", "cmd", "powershell", "pwsh",
        "node", "npm", "npx", "pip", "git", "dotnet", "java", "ruby", "perl",
        "xelatex", "pdflatex", "latexmk", "drawio", "soffice", "word", "excel",
        "rscript", "Rscript", "tesseract", "magick", "convert", "ffmpeg",
    }
    if first_token in executable_roots:
        if first_token.lower() == "word":
            # "Word COM main.docx -> main.pdf" 是文档流程描述，不是命令
            return True
        if not rest:
            return False  # 裸解释器不判伪
        if rest.startswith(("/", "\\", ".", "..", "@")):
            return False
        if " " not in rest and "." in rest:
            return False  # 单个脚本文件（如 solve.py）
        natural_language_words = (
            "inspection", "check", "review", "verification", "verifying",
            "analysis", "analyzing", "generation", "generating", "for the",
            "for four", "capability", "coverage", "workbook", "script that",
            "to ", "the ", "and ", "with ",
        )
        lowered = rest.lower()
        if any(lowered.startswith(w) or f" {w} " in f" {lowered} " for w in natural_language_words):
            return True
        return False
    # 首词不是已知可执行程序：含括号说明/冒号等描述性特征 → 伪命令
    if "(" in text or ")" in text or ":" in text:
        return True
    # 首词带路径/扩展名（如 C:\...\xelatex.EXE、./tools/x.py）→ 真实命令
    if "/" in first_token or "\\" in first_token or "." in first_token:
        return False
    # 无法判定：保守放行（宁可放行不可误伤）
    return False


def _relative_path(workspace: Path, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("evidence paths must be non-empty strings")
    candidate = Path(value)
    if candidate.is_absolute() or os.path.isabs(value):
        raise ValueError(f"evidence path must be workspace-relative: {value}")
    root = workspace.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"evidence path escapes workspace: {value}") from exc
    return candidate.as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_execution_evidence(
    workspace: Path, action: StepAction, result: StepResult
) -> dict[str, Any]:
    """Validate and normalize version 1 evidence reported by the executing agent."""
    evidence = result.metadata.get("execution_evidence")
    if not isinstance(evidence, dict):
        raise ValueError("execution evidence must be an object")
    missing = sorted(_REQUIRED_FIELDS - evidence.keys())
    if missing:
        raise ValueError(f"execution evidence missing required fields: {', '.join(missing)}")
    if evidence["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported execution evidence schema version: {evidence['schema_version']!r}")
    if not isinstance(evidence["agent"], str) or not evidence["agent"].strip():
        raise ValueError("execution evidence agent must be a non-empty string")
    if evidence["step_id"] != action.step_id or evidence["skill_name"] != action.skill_name:
        raise ValueError("execution evidence does not match the active step")
    if not action.skill_path.is_file() or evidence["skill_sha256"] != _file_sha256(action.skill_path):
        raise ValueError("execution evidence skill_sha256 does not match the skill file")

    normalized = dict(evidence)
    for field in ("inputs", "outputs"):
        paths = evidence[field]
        if not isinstance(paths, list):
            raise ValueError(f"execution evidence {field} must be a list")
        normalized[field] = [_relative_path(Path(workspace), value) for value in paths]

    claimed_artifacts = [_relative_path(Path(workspace), value) for value in result.artifacts]
    if set(normalized["outputs"]) != set(claimed_artifacts):
        raise ValueError("execution evidence outputs must match claimed artifacts")

    commands = evidence["commands"]
    if not isinstance(commands, list) or not commands:
        raise ValueError("execution evidence commands must be a non-empty list")
    normalized_commands = []
    for command in commands:
        if not isinstance(command, dict):
            raise ValueError("execution evidence command records must be objects")
        if not isinstance(command.get("command"), str) or not command["command"].strip():
            raise ValueError("execution evidence command record requires command")
        if _looks_like_descriptive_command(command["command"]):
            raise ValueError(
                f"execution evidence command is descriptive text, not an executable command: "
                f"{command['command'][:120]!r}"
            )
        if not isinstance(command.get("returncode"), int):
            raise ValueError("execution evidence command record requires integer returncode")
        if command["returncode"] != 0:
            raise ValueError("successful execution evidence commands must have returncode 0")
        normalized_command = dict(command)
        normalized_command["cwd"] = _relative_path(Path(workspace), command.get("cwd", "."))
        normalized_commands.append(normalized_command)
    normalized["commands"] = normalized_commands
    return normalized


def write_execution_evidence(
    workspace: Path, action: StepAction, evidence: dict[str, Any], manifest: dict[str, Any]
) -> str:
    """Write validated evidence and its declared-artifact manifest under the workspace."""
    root = Path(workspace).resolve()
    directory = root / ".engine" / "evidence"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{action.step_id}.json"
    payload = {"schema_version": SCHEMA_VERSION, "action": {
        "workflow_id": action.workflow_id,
        "step_id": action.step_id,
        "skill_name": action.skill_name,
    }, "evidence": evidence, "manifest": manifest}
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    return path.relative_to(root).as_posix()
