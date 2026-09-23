"""工具铸造协议：驱动本项目的 Agent 可自适应构建为自己所用的工具。

触发：capability_probe 报出 TOOL_GAP，或任务缺少现成 tools/skills 覆盖。
产物：
  - tools/<name>.py          可执行 CLI 骨架（JSON 输出）
  - skills/<name>/SKILL.md   技能契约骨架
约束：
  - 默认不覆盖已有文件（--force 才覆盖）
  - 技能须登记 capabilities/catalog.json（短横线 capability_id）
  - 铸造内容必须遵守 TOOL_GAP：骨架不假装功能已完成
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")

TOOL_TEMPLATE = '''#!/usr/bin/env python3
"""{purpose}

铸造成分：agent 自适应工具骨架（TOOL_GAP 协议）。
当前仅为可调用契约骨架——实现前不得在证据中宣称功能已完成。
"""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="{purpose}")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--workspace", default="", help="可选工作区")
    args = parser.parse_args()
    payload = {{
        "tool": "{name}",
        "status": "scaffolded",
        "purpose": "{purpose}",
        "implemented": False,
        "note": "骨架已铸造；请按任务实现真实逻辑，并遵守无证据＝未执行",
    }}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"{{payload['tool']}}: {{payload['status']}} (implemented=false)")
        print(payload["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

SKILL_TEMPLATE = '''---
name: {name}
description: {purpose}
status: forged
---

# {name}

> 由 tool_forge 铸造的技能骨架。驱动 Agent 应按真实任务补全契约与步骤，
> 并在 `capabilities/catalog.json` 登记 capability_id=`{name}`（短横线命名）。

## 触发

当出现以下意图时路由到本技能：{purpose}

## 输入契约

- 由驱动 Agent 按任务补充（缺输入时向用户索取，不得空跑）

## 执行步骤

1. 探测能力：`python -m engine.workflow_cli probe`
2. 若工具已铸造：调用 `python tools/{tool_name}.py --json`
3. 按任务实现/调用真实逻辑，产物写入工作区
4. 自检质量铁律后回报

## 输出契约

- 由驱动 Agent 按任务补充；产出必须可复现、可指出路径

## 质量铁律

- TOOL_GAP：工具够不到就报状态未知，绝不伪造通过
- 无证据＝未执行
- 三振升级：同一思路失败 3 次必须换路或上报

## 关联

- 工具骨架: `tools/{tool_name}.py`（若存在）
- 能力探测: `python -m engine.workflow_cli probe`
'''

def _suite_root(project_root: Path | None) -> Path:
    return Path(project_root) if project_root else Path(__file__).resolve().parent.parent


def validate_name(name: str) -> str:
    value = (name or "").strip()
    if not NAME_RE.match(value):
        raise ValueError(
            f"非法名称 {name!r}：须匹配 [a-z0-9][a-z0-9-]{{1,63}}（技能/工具统一名）"
        )
    return value


def forge_tool(
    name: str,
    purpose: str,
    project_root: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """铸造 tools/<name>.py CLI 骨架。"""
    tool_name = validate_name(name)
    suite = _suite_root(project_root)
    path = suite / "tools" / f"{tool_name}.py"
    existed = path.exists()
    if existed and not force:
        return {
            "kind": "tool",
            "name": tool_name,
            "path": path.relative_to(suite.parent).as_posix() if suite.parent in path.parents else str(path),
            "status": "exists",
            "created": False,
            "message": "已存在，未覆盖（需要覆盖请加 force）",
        }
    purpose_text = (purpose or "").strip() or f"自适应铸造工具 {tool_name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        TOOL_TEMPLATE.format(name=tool_name, purpose=purpose_text),
        encoding="utf-8",
    )
    return {
        "kind": "tool",
        "name": tool_name,
        "path": str(path),
        "status": "created" if not existed else "overwritten",
        "created": True,
        "message": "工具骨架已铸造；实现前不得宣称功能完成",
        "invoke": f"python tools/{tool_name}.py --json",
    }


def forge_skill(
    name: str,
    purpose: str,
    project_root: Path | None = None,
    tool_name: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """铸造 skills/<name>/SKILL.md 技能契约骨架。"""
    skill_name = validate_name(name)
    suite = _suite_root(project_root)
    skill_dir = suite / "skills" / skill_name
    path = skill_dir / "SKILL.md"
    existed = path.exists()
    if existed and not force:
        return {
            "kind": "skill",
            "name": skill_name,
            "path": str(path),
            "status": "exists",
            "created": False,
            "message": "已存在，未覆盖（需要覆盖请加 force）",
        }
    purpose_text = (purpose or "").strip() or f"自适应铸造技能 {skill_name}"
    linked_tool = validate_name(tool_name) if tool_name else skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(
        SKILL_TEMPLATE.format(name=skill_name, purpose=purpose_text, tool_name=linked_tool),
        encoding="utf-8",
    )
    return {
        "kind": "skill",
        "name": skill_name,
        "path": str(path),
        "status": "created" if not existed else "overwritten",
        "created": True,
        "message": "技能骨架已铸造；请补全契约并登记 catalog.json",
        "catalog_capability_id": skill_name,
        "catalog_domain_hint": "figures_and_document_production",
        "register_hint": (
            "在 capabilities/catalog.json 对应 domain 列表中增加 "
            f"capability_id=\"{skill_name}\"（短横线=技能映射条目，无需聚合扩展字段）"
        ),
    }


def forge_adapter(
    name: str,
    purpose: str,
    project_root: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """铸造可选宿主适配器元数据 agents/adapters/<name>/adapter.json。"""
    adapter_name = validate_name(name)
    repo = _suite_root(project_root).parent
    path = repo / "agents" / "adapters" / adapter_name / "adapter.json"
    existed = path.exists()
    if existed and not force:
        return {
            "kind": "adapter",
            "name": adapter_name,
            "path": str(path),
            "status": "exists",
            "created": False,
            "message": "已存在，未覆盖",
        }
    purpose_text = (purpose or "").strip() or f"可选适配器 {adapter_name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    # 使用普通 dict + json.dump，避免模板字符串转义问题
    payload = {
        "adapter_id": adapter_name,
        "status": "optional",
        "kind": "host_config",
        "required_for_drive": False,
        "config_paths": [],
        "l1_audit": "none",
        "skill_discovery": "protocol (AGENTS.md + skills/)",
        "notes": purpose_text,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "kind": "adapter",
        "name": adapter_name,
        "path": str(path),
        "status": "created" if not existed else "overwritten",
        "created": True,
        "message": "可选适配器元数据已铸造；驱动协议不依赖它",
    }


def forge_from_gap(gap: dict[str, Any], project_root: Path | None = None, force: bool = False) -> dict[str, Any]:
    """根据 probe 的一条 gap 尝试铸造对应资产。

    - python_package/cli gap：不自动改系统环境，只返回安装/替代建议（不伪造可用）
    - 未知工具需求：建议 forge --tool/--skill
    """
    kind = str((gap or {}).get("kind") or "")
    gap_id = str((gap or {}).get("id") or "").strip()
    hint = str((gap or {}).get("hint") or "").strip()
    if kind in {"python_package", "cli"}:
        return {
            "action": "advise_only",
            "gap": gap,
            "message": "环境类缺口不由 forge 伪造安装；请按 hint 配置运行时或改用替代工具",
            "hint": hint,
            "forged": False,
        }
    if kind == "optional_adapter":
        name = gap_id or "custom-adapter"
        try:
            result = forge_adapter(name, hint or f"optional adapter {name}", project_root=project_root, force=force)
        except ValueError as exc:
            return {"action": "error", "gap": gap, "message": str(exc), "forged": False}
        result["action"] = "forge_adapter"
        result["forged"] = bool(result.get("created"))
        return result
    return {
        "action": "manual_forge",
        "gap": gap,
        "message": "请明确工具/技能名后调用 forge --tool 或 forge --skill",
        "example": f"python -m engine.workflow_cli forge --tool my-tool --purpose \"{hint or gap_id}\"",
        "forged": False,
    }
