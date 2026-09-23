#!/usr/bin/env python3
"""宿主依赖特征词全量扫描器（登记外零命中棘轮）。

背景（2026-09-24 用户裁决）：宿主清洗长期按"发现一批修一批"打补丁——B1/B2/B3 散装
棘轮各管一段，每轮审计都有新漏网。本工具把治理收口为**封闭清单制**：

  1. 词表固定（路径/配置绑定类特征词，见 PATTERNS）；
  2. skills/ 内一切命中，除 `data/host_dep_exemptions.json` 登记的 (file, pattern) 外，
     一律 FAIL——新命中没有"下次再修"，只有"改写掉或登记豁免"；
  3. 豁免条目命中归零时 WARN，提示收缩清单（豁免是裁决过的封闭集合，不是垃圾抽屉）。

词表口径（有意排除项）：
  - `opencode` / `OpenCode`：根级 opencode.json 是本仓合法可选适配器，comp-visual-review
    的模型枚举亦含该词——误报面大，不入默认词表（宿主适配器话题由 AGENTS.md 治理）；
  - `OPENROUTER_API_KEY` / `GEMINI_API_KEY` 等：外部 LLM API 依赖事实，非宿主绑定；
  - scope 只扫 skills/：engine/tests/tools 内的命中属守卫与审计工具自身
    （capability_probe 的适配器探测、棘轮测试词表、CHANGELOG 历史记录），用 --repo-wide
    只报告不拦截。

用法：
  python tools/host_dep_scan.py            # 人读报告
  python tools/host_dep_scan.py --strict   # 登记外命中 > 0 时 exit 1
  python tools/host_dep_scan.py --json     # 机读
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLBOX = Path(__file__).resolve().parents[1]
REPO = TOOLBOX.parent
SKILLS = TOOLBOX / "skills"
EXEMPTIONS_PATH = TOOLBOX / "tools" / "data" / "host_dep_exemptions.json"

# (pattern, 说明)。全部按字面子串匹配（与 grep -F 同口径，保证复现性）。
PATTERNS: tuple[tuple[str, str], ...] = (
    ("~/.claude", "宿主用户级技能/配置目录（已退役）"),
    (".claude/", "宿主项目级配置目录（已退役；repo-local 绑定层已中性化）"),
    ("CLAUDE.md", "宿主绑定参数文件（工作区参数文件一律 AGENTS.md）"),
    ("~/.codex", "Codex 宿主目录（已退役）"),
    ("mcp__codex", "Codex MCP 评审桥绑定（已退役）"),
    ("ANTHROPIC_API_KEY", "宿主系 API 密钥（仅在豁免登记为运行时依赖事实时放行）"),
)
PATTERN_NAMES = tuple(p for p, _ in PATTERNS)

TEXT_SUFFIXES = {
    ".md", ".py", ".sh", ".json", ".yaml", ".yml", ".html", ".htm", ".svg",
    ".txt", ".toml", ".cfg", ".tex", ".bib",
}


def _load_exemptions() -> list[dict]:
    data = json.loads(EXEMPTIONS_PATH.read_text(encoding="utf-8"))
    return [(e["file"], e["pattern"], e.get("reason", "")) for e in data["exemptions"]]


def iter_target_files() -> list[Path]:
    out = []
    for p in sorted(SKILLS.rglob("*")):
        if not p.is_file() or p.suffix not in TEXT_SUFFIXES:
            continue
        out.append(p)
    return out


def scan() -> dict:
    exemptions = _load_exemptions()
    exempt_keys = {(f, pat) for f, pat, _ in exemptions}
    fails: list[dict] = []
    exempt_hits: list[dict] = []
    seen_exempt_keys: set[tuple[str, str]] = set()
    per_pattern: dict[str, int] = {p: 0 for p in PATTERN_NAMES}

    for path in iter_target_files():
        rel = path.relative_to(TOOLBOX).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat, desc in PATTERNS:
            if pat not in text:
                continue
            lines = [i for i, line in enumerate(text.splitlines(), 1) if pat in line]
            per_pattern[pat] += len(lines)
            entry = {"file": rel, "pattern": pat, "lines": lines[:10],
                     "total_lines": len(lines), "desc": desc}
            if (rel, pat) in exempt_keys:
                seen_exempt_keys.add((rel, pat))
                exempt_hits.append(entry)
            else:
                fails.append(entry)

    stale = [
        {"file": f, "pattern": pat, "reason": reason}
        for f, pat, reason in exemptions
        if (f, pat) not in seen_exempt_keys
    ]
    return {
        "ok": not fails,
        "fails": fails,
        "exempt_hits": exempt_hits,
        "stale_exemptions": stale,
        "counts": {
            "fail_hits": sum(e["total_lines"] for e in fails),
            "fail_files": len(fails),
            "exempt_hits": sum(e["total_lines"] for e in exempt_hits),
            "exempt_files": len(exempt_hits),
            "per_pattern": per_pattern,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="宿主依赖特征词扫描（登记外零命中棘轮）")
    parser.add_argument("--strict", action="store_true", help="登记外命中时 exit 1")
    parser.add_argument("--json", action="store_true", help="机读输出")
    args = parser.parse_args(argv)

    res = scan()
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        c = res["counts"]
        print(f"词表 {len(PATTERNS)} 个；FAIL {c['fail_files']} 文件 / {c['fail_hits']} 处；"
              f"豁免命中 {c['exempt_files']} 文件 / {c['exempt_hits']} 处")
        for e in res["fails"]:
            print(f"  [FAIL] {e['file']} :: {e['pattern']}（{e['desc']}）行 {e['lines']}")
        for e in res["exempt_hits"]:
            print(f"  [豁免] {e['file']} :: {e['pattern']} ×{e['total_lines']}")
        for e in res["stale_exemptions"]:
            print(f"  [可收缩] {e['file']} :: {e['pattern']} 已零命中——理由：{e['reason']}")
        if res["stale_exemptions"]:
            print("  ⚠️ 存在零命中豁免条目：豁免是封闭集合，请收缩清单。")
        print("结论：", "登记外零命中" if res["ok"] else "登记外命中未清零")
    return 0 if res["ok"] or not args.strict else 1


if __name__ == "__main__":
    sys.exit(main())
