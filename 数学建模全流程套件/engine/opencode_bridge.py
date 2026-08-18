"""Agent 驱动模型：引擎不执行，只编排。

定位澄清：本系统由 OpenCode 桌面版（当前 agent）直接驱动。
引擎（本模块 + workflow_store/runner）只负责两件事：
  1. 告诉 agent「下一步做什么」—— next_action()
  2. 记录 agent 回报的「做完了」结果 —— complete_step()

绝对不存在「调用另一个 opencode」的子进程逻辑。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StepAction:
    """引擎下发给 agent 的「下一步动作」—— agent 只需按此执行。"""

    workflow_id: str
    step_id: str
    position: int
    skill_name: str
    display_name: str
    workspace: Path
    skill_path: Path
    output_files: list[str]
    primary_output: str
    has_checkpoint: bool
    checkpoint_type: str | None
    params: dict[str, Any] = field(default_factory=dict)

    def execution_instructions(self) -> str:
        """转成给 agent 的文字指令（可直接用于 prompt）。"""
        lines = [
            f"【执行第 {self.position} 步】技能: {self.skill_name}",
            f"  工作区: {self.workspace}",
            f"  技能文件: {self.skill_path}",
            f"  产出文件: {', '.join(self.output_files) if self.output_files else '(按技能说明)'}",
            f"  主产出: {self.primary_output or '(无)'}",
        ]
        if self.has_checkpoint:
            lines.append(f"  ⚠️ 完成后需暂停等待用户{'批准' if self.checkpoint_type == 'approve' else '反馈'}")
        return "\n".join(lines)


@dataclass(frozen=True)
class StepResult:
    """agent 回报给引擎的「执行结果」。"""

    ok: bool
    stdout: str = ""
    stderr: str = ""
    artifacts: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence_path: str | None = None
