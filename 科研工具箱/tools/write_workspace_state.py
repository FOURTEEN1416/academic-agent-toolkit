"""write_workspace_state —— workspace 状态标记生成/更新（原仓库缺陷修复建议 D6）。

背景（2026-09-12 P0-C / D6 实锤）：workspaces/{ws}/ 旧稿与后续产物同名共存、
数值全线不同、无任何状态声明——从仓库路径取稿必拿错版本；且多智能体点评
任务要求旧稿保留，"标记隔离"比删除更必要。

用法：
  python write_workspace_state.py --workspace ./ws --agent "窗口名" \\
      [--workflow <workflow_id>] [--version <版本标签>] \\
      [--superseded-by "被谁取代/取代对象说明"] [--note "补充说明"]

效果：workspace 根写入/更新 STATE.txt（KEY: VALUE 机器可读格式）。
重复调用 = 更新（updated_at 刷新），不产生多余文件。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

TEMPLATE = """# D6 workspace 状态标记（机器可读 + 人读；由 tools/write_workspace_state.py 生成/更新）
# 取稿前先读本文件：确认版本、归属与取代关系，避免同名工程拿错稿。
workspace: {workspace}
agent: {agent}
workflow_id: {workflow_id}
version: {version}
superseded_by: {superseded_by}
authority: {authority}
updated_at: {updated_at}
note: {note}
"""


def write_state(workspace: Path, agent: str, workflow_id: str = "", version: str = "",
                superseded_by: str = "", note: str = "", authority: str = "本 workspace 内 HANDOVER/交接文档（如有）") -> Path:
    """写/更新 workspace 根的 STATE.txt，返回文件路径。"""
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise SystemExit(f"workspace 不存在: {workspace}")
    content = TEMPLATE.format(
        workspace=str(workspace),
        agent=agent.strip() or "(未署名)",
        workflow_id=workflow_id.strip() or "(未关联引擎工作流)",
        version=version.strip() or "(未标注)",
        superseded_by=superseded_by.strip() or "(无——本 workspace 为最新产物)",
        authority=authority.strip(),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        note=(note.strip() or "(无)"),
    )
    state_path = workspace / "STATE.txt"
    state_path.write_text(content, encoding="utf-8")
    return state_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D6 workspace 状态标记生成/更新")
    parser.add_argument("--workspace", required=True, help="workspace 目录")
    parser.add_argument("--agent", required=True, help="产出/值守该 workspace 的 agent 或窗口名")
    parser.add_argument("--workflow", default="", help="关联引擎 workflow_id（如有）")
    parser.add_argument("--version", default="", help="版本标签（如 v2-91p）")
    parser.add_argument("--superseded-by", default="", help="被谁取代（空 = 本 workspace 为最新）")
    parser.add_argument("--authority", default="", help="版本权威文档（默认指向 HANDOVER/交接文档）")
    parser.add_argument("--note", default="", help="补充说明")
    args = parser.parse_args(argv)
    path = write_state(
        Path(args.workspace), agent=args.agent, workflow_id=args.workflow,
        version=args.version, superseded_by=args.superseded_by,
        note=args.note, authority=args.authority or "本 workspace 内 HANDOVER/交接文档（如有）",
    )
    print(f"STATE.txt 已写入: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
