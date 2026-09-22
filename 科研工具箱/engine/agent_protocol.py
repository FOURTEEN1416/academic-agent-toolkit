"""宿主中立的 Agent 驱动协议。

任意能读文件、能调用 `python -m engine.workflow_cli` 的智能体，
读取 bootstrap() 返回的契约即可驱动本项目；无需 OpenCode/ZCode。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = 1
DEFAULT_AGENT_LABEL = "acat-agent"

# 可选宿主适配器：仅增强（技能发现/L1 hook/角色定义），不是驱动前提。
# 唯一真相源 = capability_probe.ADAPTER_MARKERS（B3-7 三方对账：清单/探测标记/目录须一致；
# gemini-cli 因无探测标记与 adapter.json 于 2026-09-22 移除，需要时按 cursor 先例补齐三件套）。
OPTIONAL_ADAPTERS: tuple[str, ...] = (
    "generic",
    "opencode",
    "zcode",
    "claude-code",
    "mimocode",
    "cursor",
)

HARD_RULES: tuple[str, ...] = (
    "引擎（engine/）只编排不执行；执行者 = 当前驱动本项目的 Agent",
    "同一时刻只有一个主控 Agent；引擎绝不启动/委派另一个 agent runtime",
    "完成步骤必须 complete_step 并附真实 execution_evidence；无证据＝未执行",
    "TOOL_GAP：工具够不到世界就报状态未知，绝不伪造通过；可用 tool_forge 补齐",
    "三振升级：同一思路失败 3 次必须换路或上报",
)

_CLI_COMMANDS: tuple[tuple[str, str], ...] = (
    ("boot", "输出本协议契约 JSON"),
    ("probe", "能力探测（python/包/CLI/适配器/TOOL_GAP）"),
    ("forge", "按 TOOL_GAP 铸造工具或技能脚手架"),
    ("caps", "可选运行时命令能力（xelatex/node 等）"),
    ("start", "创建工作流"),
    ("next", "获取下一步 StepAction"),
    ("complete", "回报步骤完成（附 execution_evidence）"),
    ("approve", "批准检查点（--by 必填）"),
    ("audit", "生成操作审计报告"),
)


def project_root() -> Path:
    """仓库内套件根（科研工具箱/）。"""
    return Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    """git clone 后的仓库根（套件父目录）。"""
    return project_root().parent


def default_agent_label(host_hint: str | None = None) -> str:
    """返回当前驱动方的 agent 标签；host_hint 优先，否则通用标签。

    证据 agent 字段是自由字符串，由驱动方自报宿主/工具名。
    """
    hint = (host_hint or os.environ.get("ACAT_AGENT_LABEL") or "").strip()
    return hint or DEFAULT_AGENT_LABEL


def bootstrap(project_root: Path | None = None) -> dict[str, Any]:
    """最小驱动契约：任意 Agent 启动时读这个即可。"""
    root = Path(project_root) if project_root else project_root()
    repo = root.parent
    return {
        "protocol_version": PROTOCOL_VERSION,
        "system": "Academic Agent Toolkit (host-agnostic)",
        "role": "executor",
        "agent_label_default": DEFAULT_AGENT_LABEL,
        "agent_label_hint": "在 evidence.agent 填入你的工具名（如 claude-code / cursor / mimo-desktop）",
        "paths": {
            "suite_root": str(root),
            "repo_root": str(repo),
            "skills": "科研工具箱/skills/",
            "tools": "科研工具箱/tools/",
            "engine": "科研工具箱/engine/",
            "adapters": "agents/adapters/",
        },
        "required_reads": [
            "AGENTS.md",
            "科研工具箱/AGENTS.md",
            "科研工具箱/skills/agent-bootstrap/SKILL.md",
        ],
        "engine": {
            "module": "engine.workflow_cli",
            "cwd": "科研工具箱",
            "commands": [{"name": n, "usage": d} for n, d in _CLI_COMMANDS],
            "example": (
                "cd 科研工具箱 && python -m engine.workflow_cli boot && "
                "python -m engine.workflow_cli probe"
            ),
        },
        "audit": {
            "L1": "可选宿主 hook/插件；无宿主时 unavailable，不阻断交付",
            "L2": "走 workflow_runner 时写入 .engine/audit/operations.jsonl",
            "L3": "complete_step 的 execution_evidence（强制，schema_version=1）",
        },
        "optional_adapters": list(OPTIONAL_ADAPTERS),
        "adapter_note": (
            "opencode.json / .zcode / .opencode 仅为可选适配器；"
            "无它们时协议与引擎功能完整可用。"
        ),
        "hard_rules": list(HARD_RULES),
        "adaptation": {
            "capability_probe": "python -m engine.workflow_cli probe",
            "tool_forge": (
                "python -m engine.workflow_cli forge --tool <name> --purpose \"...\" "
                "| forge --skill <name> --purpose \"...\""
            ),
            "skill_forge_policy": (
                "工具够不到就铸造；铸造后须遵守 TOOL_GAP/无证据未执行，"
                "技能目录须映射进 capabilities/catalog.json"
            ),
        },
        "routing_shortcuts": [
            {"intent": "竞赛全流程", "route": "workflow template comp_cumcm"},
            {"intent": "写论文/文献/图表", "route": "科研工具箱/AGENTS.md §三 入口路由"},
            {"intent": "自举与铸造", "route": "skills/agent-bootstrap + skills/tool-forge"},
        ],
    }
