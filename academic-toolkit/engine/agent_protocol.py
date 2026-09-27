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
    "完成步骤用session finish，由程序从真实操作构造证据；无证据＝未执行",
    "TOOL_GAP：工具够不到世界就报状态未知，绝不伪造通过；可用 tool_forge 补齐",
    "三振升级：同一思路失败 3 次必须换路或上报",
)

_CLI_COMMANDS: tuple[tuple[str, str], ...] = (
    ("boot", "输出本协议契约 JSON"),
    ("probe", "能力探测（python/包/CLI/适配器/TOOL_GAP）"),
    ("forge", "按 TOOL_GAP 铸造工具或技能脚手架"),
    ("caps", "可选运行时命令能力（xelatex/node 等）"),
    ("start", "创建工作流"),
    ("session", "执行侧context/read/write/run/finish：自动记录证据、依赖复用、单次验收返修，不手填哈希/返回码"),
    ("next", "获取下一步 StepAction"),
    ("preflight", "只读批量验收，返回全部独立问题，不推进状态"),
    ("complete", "绑定 step_id/attempt_id/expected_revision 回报；同 request_id 幂等重放"),
    ("retry", "为 FAILED 或 BLOCKED 步骤建立新 attempt，旧检查点失效"),
    ("final-audit", "生成 eligible 预审或完成后的 DELIVERY_REPORT；blocked 返回非零"),
    ("approve", "批准检查点（--by 必填）"),
    ("audit", "生成操作审计报告"),
)


def project_root() -> Path:
    """仓库内套件根（academic-toolkit/）。"""
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


def bootstrap(root_path: Path | None = None) -> dict[str, Any]:
    """最小驱动契约：任意 Agent 启动时读这个即可驱动。

    root_path 缺省时按本文件位置自推套件根（参数名不得再叫 project_root——
    会遮蔽模块级 project_root() 函数，裸调用即 TypeError，2026-09-23 修复）。
    """
    root = Path(root_path) if root_path else project_root()
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
            "skills": "academic-toolkit/skills/",
            "tools": "academic-toolkit/tools/",
            "engine": "academic-toolkit/engine/",
            "data": "academic-toolkit/data/",
            "third_party": "academic-toolkit/third_party/",
            "asset_catalog": "academic-toolkit/data/asset_catalog.json",
            "assets_local": "assets-local/",
        },
        "assets": {
            "catalog": "data/asset_catalog.json（资产台账：非技能资产的唯一机器可读目录）",
            "how_to_use": (
                "按 when_to_use/owner_skills 检索资产；local_only=true 的条目在"
                "私有资料区（gitignored），公开 clone 缺席属语义缺位而非断链"
            ),
        },
        "required_reads": [
            "AGENTS.md",
            "academic-toolkit/AGENTS.md",
            "academic-toolkit/skills/agent-bootstrap/SKILL.md",
        ],
        "engine": {
            "module": "engine.workflow_cli",
            "cwd": "academic-toolkit",
            "commands": [{"name": n, "usage": d} for n, d in _CLI_COMMANDS],
            "example": (
                "cd academic-toolkit && python -m engine.workflow_cli boot && "
                "python -m engine.workflow_cli probe"
            ),
        },
        "completion_contract": {
            "preferred_execution": "session context --wf ID --db DB 返回真实技能正文与会话；session run --session FILE --plan PLAN --finish 自动记录并一次验收，needs_work保持当前身份修正",
            "incremental_execution": "执行计划节点显式inputs/outputs/argv；pure+complete_inputs才允许依赖内容、程序、环境和合同指纹一致时复用真实成功结果；非确定性/评审不缓存",
            "target": ["step_id", "attempt_id", "expected_revision"],
            "request_id": "同一语义提交重发用同一个 ID；修改 payload 后使用新 ID",
            "preflight": "可选只读批量预检；修复全部 diagnostics 后再 complete，避免逐项失败/重试",
            "resources": "推荐清单逐项 used/skipped；额外技能用 additional_skills [{skill, reason, contribution, output}]",
            "evidence_level": "技能读取痕迹不等于语义贡献；产物质量与独立评审另验",
            "checkpoint": "BLOCKED 需人类批准；产物变化后 retry 开新 attempt、重新验收，旧批准失效",
            "delivery": "eligible 仅为预审；complete/approve/backfill 后读取 DELIVERY_REPORT.json 的 ready 结论",
            "final_candidate": "L1 启用时，final-audit --wf <工作流> --evidence-file <真实证据.json> 对账当前 RUNNING 最终步骤；仅 eligible 预审，不提前接受产物，批准/交付仍只读已提交证据",
            "directory_receipts": "新目录回执保存逐文件摘要与成员集合；子文件重验不丢兄弟覆盖；旧无成员目录须完整重验",
            "control_calls": "final-audit/next/preflight/complete/backfill/retry/approve 独立调用并传绝对 --db，绑定当前工作流/检查点；审计单列 not_attested，不能预填未来命令成功；复合/截断调用不分类",
            "final_backfill": "PENDING 终审须先 next 领取，再生成候选预审并补录；仍需真实验收与人类批准",
            "delivery_recovery": "diagnostics.delivery.decision=pending 表示提交已落账而报告未发布；调用 next 或 final-audit --workspace <工作区> --db <数据库> --wf <工作流> 恢复，complete 也可用原 request_id 重放",
            "execution_manifest": "bridge 名称不同于步骤时，用 evidence.execution_manifest 显式引用工作区内原始清单；必须覆盖合同输出，额外日志/回执同样校验路径与哈希，保留真实输入/后端/依赖/config",
            "resource_statistics": "offered 来自下发清单，used 是申报而非已验证贡献；外置库使用 check_asset_utilization.py --workflow-db WORKSPACE=DB，只统计当前已接受尝试",
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
            {"intent": "写论文/文献/图表", "route": "academic-toolkit/AGENTS.md §三 入口路由"},
            {"intent": "找数据/模板/参考资产", "route": "data/asset_catalog.json 台账直查（boot paths.asset_catalog）"},
            {"intent": "自举与铸造", "route": "skills/agent-bootstrap + skills/tool-forge"},
        ],
    }
