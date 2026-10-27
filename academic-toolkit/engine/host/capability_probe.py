"""能力探测：任意 Agent 驱动本项目前，先知道自己能做什么、缺什么。

原则（TOOL_GAP）：探测只报告事实，不伪造可用性。
缺 CLI/缺包都进入 gaps，供 tool_forge 或人工补齐。
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path
from typing import Any

# 关键 Python 包：学术工具链常用依赖
PROBE_PACKAGES: tuple[str, ...] = (
    "fitz",
    "docx",
    "openpyxl",
    "PIL",
    "pandas",
    "numpy",
    "yaml",
    "requests",
    "matplotlib",
)

# CLI 探测名 → 人类可读说明
PROBE_CLIS: tuple[tuple[str, str], ...] = (
    ("python", "Python 解释器"),
    ("git", "版本控制"),
    ("node", "Node.js"),
    ("npm", "npm"),
    ("xelatex", "XeLaTeX 编译"),
    ("pdflatex", "pdfLaTeX 编译"),
    ("drawio", "draw.io CLI"),
    ("soffice", "LibreOffice"),
)

# 仅检测是否存在，绝不读取/打印值
PROBE_ENV_KEYS: tuple[str, ...] = (
    "ACAT_AGENT_LABEL",
    "ACAT_CONTEST_MODELS",
    "ACAT_AGENT_ROLES_DIR",
    "ACAT_ADAPTER_AGENTS_DIRS",
    "ACAT_AUDIT_EXTRA_DIRS",
    "OPENAI_API_KEY",
    "REVIEWER_BASE_URL",
    "REVIEWER_MODEL_ID",
    "AGNES_API_KEY",
    "DOCSEARCH_ROOTS",
)

# 关键包缺失 → TOOL_GAP 提示
_PACKAGE_GAP_HINTS: dict[str, str] = {
    "fitz": "PyMuPDF：PDF 读写/页数门禁；pip install pymupdf",
    "docx": "python-docx：DOCX 读写；pip install python-docx",
    "openpyxl": "Excel 读写；pip install openpyxl",
    "PIL": "图像处理；pip install pillow",
    "pandas": "数据分析；pip install pandas",
    "yaml": "YAML/frontmatter；pip install pyyaml",
    "requests": "HTTP 客户端；pip install requests",
    "matplotlib": "科研绘图；pip install matplotlib",
}


def _package_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _cli_path(name: str) -> str | None:
    if name == "python":
        return sys.executable or shutil.which("python") or shutil.which("python3")
    return shutil.which(name)


def _asset_summary(suite: Path) -> dict[str, Any]:
    """资产台账摘要（W2 资产激活）：条目数/分区统计/高价值入口。

    台账缺失或损坏时如实降级（available=false），不阻断 probe——与 TOOL_GAP 纪律一致。
    """
    catalog_path = suite / "data" / "asset_catalog.json"
    summary: dict[str, Any] = {"path": "academic-toolkit/data/asset_catalog.json"}
    try:
        import json
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        assets = data.get("assets", [])
        zones: dict[str, int] = {}
        for entry in assets:
            zones[entry.get("zone", "?")] = zones.get(entry.get("zone", "?"), 0) + 1
        summary.update({
            "available": True,
            "entries": len(assets),
            "local_only_entries": sum(1 for e in assets if e.get("local_only")),
            "zones": zones,
            "usage": "按 when_to_use/owner_skills 检索；local_only 条目在私有资料区（公开 clone 缺席属语义缺位）",
        })
    except (OSError, ValueError):
        summary.update({"available": False, "note": "资产台账缺失或损坏：run check_asset_utilization 对账"})
    return summary


def probe(project_root: Path | None = None) -> dict[str, Any]:
    """完整能力探测。project_root 默认为套件根（academic-toolkit/）。"""
    from .._paths import TOOLBOX_ROOT

    suite = Path(project_root) if project_root else TOOLBOX_ROOT
    repo = suite.parent

    packages = {name: _package_available(name) for name in PROBE_PACKAGES}
    clis: dict[str, dict[str, Any]] = {}
    for name, desc in PROBE_CLIS:
        path = _cli_path(name)
        clis[name] = {"available": path is not None, "path": path, "description": desc}

    env_presence = {key: bool(os.environ.get(key)) for key in PROBE_ENV_KEYS}

    gaps: list[dict[str, str]] = []
    for name, ok in packages.items():
        if not ok:
            gaps.append({
                "kind": "python_package",
                "id": name,
                "hint": _PACKAGE_GAP_HINTS.get(name, f"pip install {name}"),
            })
    for name, info in clis.items():
        if not info["available"] and name != "python":
            gaps.append({
                "kind": "cli",
                "id": name,
                "hint": info["description"] + " 不在 PATH；按技能说明安装或改用替代工具",
            })
    return {
        "protocol_version": 1,
        "suite_root": str(suite),
        "repo_root": str(repo),
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "platform": sys.platform,
        },
        "packages": packages,
        "cli": clis,
        "env_presence": env_presence,
        "asset_catalog": _asset_summary(suite),
        "gaps": gaps,
        "drive_ready": True,
        "drive_ready_note": (
            "只要能读文件并调用 python -m engine.workflow_cli，即可驱动本项目；"
            "gaps 仅表示增强能力缺失，不阻断协议闭环。"
        ),
        "next_actions": [
            "python -m engine.workflow_cli boot",
            "python -m engine.workflow_cli probe",
            "存在工具缺口时: python -m engine.workflow_cli forge --tool <name> --purpose \"...\"",
            "竞赛: python -m engine.workflow_cli start --template comp_cumcm --workspace <ws>",
        ],
    }
