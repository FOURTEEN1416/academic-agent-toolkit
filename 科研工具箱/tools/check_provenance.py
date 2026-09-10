#!/usr/bin/env python3
"""通用 provenance 审计器 — 检查 UPSTREAM.md 台账与配置文件来源记录。

Phase 5 通用化 check_codesucker_licenses.py：
- 扫描注册的 UPSTREAM.md 清单，校验必填字段（Upstream / Pinned commit / License）；
- 检查 vendored/core 外部依赖目录的 LICENSE / NOTICE 完整性；
- 输出结构化审计报告（JSON），退出码 0=通过 / 1=有失败。

用法：
    python tools/check_provenance.py
    python tools/check_provenance.py --scope upstream   # 只查 UPSTREAM.md
    python tools/check_provenance.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# UPSTREAM.md 台账注册表（Phase 5.1 清单，可扩展）
UPSTREAM_REGISTRY: list[Path] = [
    ROOT / "tools" / "codesucker-core" / "UPSTREAM.md",
    ROOT / "tools" / "pubfig" / "UPSTREAM.md",
    ROOT / "tools" / "docx-cn-engine" / "UPSTREAM.md",
    ROOT / "tools" / "docx_style_profiles" / "UPSTREAM.md",
    ROOT / "tools" / "humanize_chinese" / "UPSTREAM.md",
    ROOT / "skills" / "shared-scripts" / "UPSTREAM.md",
    ROOT / "skills" / "paper-write" / "templates" / "UPSTREAM.md",
    ROOT / "skills" / "paper-write" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "paper-write-zh" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "paper-write-nature" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "comp-paper-zh" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "comp-paper-en" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "comp-compile-zh" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "comp-compile-en" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "nature-figure" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "latex-document" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "patent-draft" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "copyright-draft" / "references" / "UPSTREAM.md",
    ROOT / "data" / "UPSTREAM.md",
    # 科研绘图能力扩展（2026-08-28，9 项）
    ROOT / "skills" / "scientific-visualization" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "matplotlib" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "seaborn" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "infographics" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "plotly" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "scientific-schematics" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "figure-spec" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "graphviz" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "excalidraw-diagram" / "references" / "UPSTREAM.md",
    # 科研绘图扩展追加（2026-08-29）
    ROOT / "skills" / "diagram-design" / "references" / "UPSTREAM.md",
    # claude-scientific-writer 资产补齐（2026-09-09）
    ROOT / "skills" / "claude-scientific-writer" / "references" / "UPSTREAM.md",
    # 专项治理批次 2：latexpap-*/spine-* 资产补齐（2026-09-09）
    ROOT / "skills" / "latexpap-arxiv-paper-writer" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "latexpap-check-collaborators" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "latexpap-collaborating-with-claude" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "latexpap-collaborating-with-gemini" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "latexpap-empirical-paper-writer" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "latexpap-latex-rhythm-refiner" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "latexpap-paper-from-zero" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "latexpap-results-backfill" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "spine-paper-spine" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "spine-paper-spine-audit" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "spine-paper-spine-build" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "spine-paper-spine-citation" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "spine-paper-spine-humanize" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "spine-paper-spine-intake" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "spine-paper-spine-latex" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "spine-paper-spine-research" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "spine-paper-spine-rewrite" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "spine-paper-spine-translate" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "spine-paper-spine-ui" / "references" / "UPSTREAM.md",
    # 专项治理批次 2：latex-document 资产补齐（2026-09-09）
    ROOT / "skills" / "latex-document" / "references" / "UPSTREAM.md",
    # 专项治理批次 1c：ars-* 资产补齐（2026-09-09）
    ROOT / "skills" / "ars-academic-paper" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "ars-academic-paper-reviewer" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "ars-academic-pipeline" / "references" / "UPSTREAM.md",
    # 专项治理批次 1b：nature-* 资产补齐（2026-09-09）
    ROOT / "skills" / "nature-data-availability" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "nature-scientific-writing" / "references" / "UPSTREAM.md",
    # 专项治理批次 1a：sci-* 资产补齐（2026-09-09）
    ROOT / "skills" / "sci-citation-management" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "sci-exploratory-data-analysis" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "sci-latex-posters" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "sci-literature-review" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "sci-networkx" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "sci-paper-lookup" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "sci-scientific-writing" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "sci-statistical-analysis" / "references" / "UPSTREAM.md",
    ROOT / "skills" / "sci-sympy" / "references" / "UPSTREAM.md",
    # figures4papers 收编：语义调色板+构图五模式（2026-09-09，CC BY-NC-4.0）
    ROOT / "skills" / "paper-figure" / "references" / "UPSTREAM.md",
]

# 需要完整许可文件的 vendored 外部依赖目录（含 LICENSE/NOTICE/UPSTREAM.md 三件套）
VENDOR_DIRS: list[Path] = [
    ROOT / "tools" / "codesucker-core",
]

REQUIRED_FIELDS = ("Upstream:", "Pinned commit:", "License:")
REQUIRED_VENDOR_FILES = ("LICENSE", "NOTICE", "UPSTREAM.md")

# 2026-09-09 独立审计 P3-2 收紧：Pinned commit 字段语义校验（旧版只查字段存在，
# "Pinned commit: 随便写点什么" 也能过）。规则：
#   · Upstream 含 github.com → Pinned commit 必须是 7-40 位十六进制哈希（可带反引号）
#   · 非 URL 源（官方规则/本地维护）→ 接受 哈希 / ISO 日期 / official-* 发布标识 /
#     "无外部*" / "不可固定" 显式声明
_PINNED_HASH_RE = re.compile(r"^\s*`?([0-9a-fA-F]{7,40})\b")
_PINNED_NONURL_RE = re.compile(
    r"^\s*`?(?:([0-9a-fA-F]{7,40})\b|\S*\d{4}-\d{2}-\d{2}|official-\S+|无外部|不可固定)"
)


def _check_pinned_semantics(text: str) -> str | None:
    """返回 None=合规；否则返回违规说明。"""
    mu = re.search(r"Upstream:\s*(.+)", text)
    mc = re.search(r"Pinned commit:\s*(.+)", text)
    if not mc:
        return "缺 Pinned commit 值"
    pin = mc.group(1)
    is_url = bool(mu and "github.com" in mu.group(1).lower())
    if is_url:
        return None if _PINNED_HASH_RE.match(pin) else "URL 源的 Pinned commit 必须是 7-40 位十六进制哈希"
    return None if _PINNED_NONURL_RE.match(pin) else (
        "非 URL 源的 Pinned commit 须为哈希/ISO 日期/official-* 发布标识/无外部*/不可固定"
    )


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def check_upstream(path: Path) -> dict:
    if not path.is_file():
        return {"path": _display(path), "ok": False, "missing": ["file"]}
    text = path.read_text(encoding="utf-8", errors="ignore")
    missing = [field.rstrip(":") for field in REQUIRED_FIELDS if field not in text]
    pinned_issue = _check_pinned_semantics(text)
    if pinned_issue:
        missing.append(pinned_issue)
    has_license_note = ("license" in text.lower())
    return {
        "path": _display(path),
        "ok": not missing and has_license_note,
        "missing": missing,
    }


def check_vendor(path: Path) -> dict:
    missing = [name for name in REQUIRED_VENDOR_FILES if not (path / name).is_file()]
    prior_ok = True
    upstream = path / "UPSTREAM.md"
    if upstream.is_file():
        prior = check_upstream(upstream)
        prior_ok = prior["ok"]
    return {
        "path": _display(path),
        "ok": not missing and prior_ok,
        "missing": missing + (["UPSTREAM.md 字段不完整"] if not prior_ok else []),
    }


def run(scope: str) -> dict:
    reports: list[dict] = []
    failures: list[str] = []
    if scope in ("upstream", "all"):
        for path in UPSTREAM_REGISTRY:
            result = check_upstream(path)
            reports.append({"kind": "upstream", **result})
            if not result["ok"]:
                failures.append(_display(path))
    if scope in ("vendor", "all"):
        for path in VENDOR_DIRS:
            result = check_vendor(path)
            reports.append({"kind": "vendor", **result})
            if not result["ok"]:
                failures.append(_display(path))
    return {"ok": not failures, "failures": failures, "reports": reports}


def main() -> int:
    parser = argparse.ArgumentParser(description="通用 provenance 审计器")
    parser.add_argument("--scope", choices=("all", "upstream", "vendor"), default="all")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()
    result = run(args.scope)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        total = len(result["reports"])
        print(f"Provenance 审计: {total - len(result['failures'])}/{total} 通过")
        for report in result["reports"]:
            status = "OK" if report["ok"] else "FAIL"
            detail = f" ({', '.join(report.get('missing', []))})" if report.get("missing") else ""
            print(f"  [{status}] {report['kind']}: {report['path']}{detail}")
        if result["failures"]:
            print("失败项:")
            for failure in result["failures"]:
                print(f"  - {failure}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
