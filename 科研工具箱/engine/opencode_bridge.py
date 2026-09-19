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
    companion_skills: list[str] = field(default_factory=list)
    # 本步引擎显式给出的非技能资产（数据/参考论文/工具脚本/参考图集），
    # 每项 {"name", "path", "note"}；path 为仓库根相对路径（2026-09-12 C2 资产机制）。
    assets: list[dict[str, str]] = field(default_factory=list)
    # D3 门禁前移（2026-09-13）：本步完成后必须先跑 quick_gates 轻检（页数/图字号/泄漏），
    # 由模板步骤 metadata.quick_gates=true 声明，设计挂 step 5（出图后）与 step 8（成文后）。
    quick_gates: bool = False
    # P4 技能强制绑定（2026-09-19）：本步显式绑定技能的声明，由模板步骤 metadata.skill_binding
    # 给出。结构 {"main": 技能名, "main_required": bool, "mandatory": [技能名...]}；缺省为 {}，
    # 即退回"仅按 C1/M5 既有机制"的行为（向后兼容）。
    skill_binding: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)

    def binding_requirements(self) -> list[str]:
        """把绑定声明渲染成人类可读的强制要求行（供指令与错误信息复用）。"""
        binding = self.skill_binding or {}
        if not isinstance(binding, dict) or not binding:
            return []
        lines = []
        main = str(binding.get("main") or self.skill_name)
        if binding.get("main_required", True):
            lines.append(
                f"主技能 {main} 的契约必须被真实读取——执行证据的命令/输入中须出现 "
                f"skills/{main}/SKILL.md（或该技能名）；只填 skill_sha256 不算")
        for skill in binding.get("mandatory") or []:
            name = str(skill).strip()
            if name:
                lines.append(
                    f"绑定技能 {name} 为**必用**：不得申报 skipped，须申报 used 并留真实 "
                    f"consult 命令痕迹（如读取 skills/{name}/SKILL.md 或执行其 scripts/）")
        return lines

    def execution_instructions(self) -> str:
        """转成给 agent 的文字指令（可直接用于 prompt）。"""
        lines = [
            f"【执行第 {self.position} 步】技能: {self.skill_name}",
            f"  工作区: {self.workspace}",
            f"  技能文件: {self.skill_path}",
            f"  产出文件: {', '.join(self.output_files) if self.output_files else '(按技能说明)'}",
            f"  主产出: {self.primary_output or '(无)'}",
        ]
        for requirement in self.binding_requirements():
            lines.append(f"  ⛔ 技能绑定（强制，complete 时校验）: {requirement}")
        if self.companion_skills:
            lines.append(f"  推荐辅助技能(按需加载1-3个,全库地图见 CONTEST_SKILL_MAP.md): {', '.join(self.companion_skills)}")
        if self.assets:
            rendered = "; ".join(
                f"{a.get('name', '')}[{a.get('path', '')}]" + (f" {a['note']}" if a.get("note") else "")
                for a in self.assets if isinstance(a, dict)
            )
            lines.append(f"  本步资产(路径为仓库根相对;用则留痕,完成申报 used/skipped): {rendered}")
        if self.quick_gates:
            lines.append(
                "  ⛔ D3 门禁前移轻检（本步完成后、回报 complete 前必跑）: "
                f"python skills/_utils/quick_gates.py --workspace {self.workspace}"
                "（FAIL 先处理再回报——页数/字号问题越早暴露修复越便宜）")
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
