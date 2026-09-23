"""宿主中性化存量棘轮（2026-09-23 宿主引用修复批）。

钉住 B1/B2/B3 三族已清零的口径，防止回潮：
  - B2: capabilities/catalog.json 不得再出现"需在 OpenCode 会话中确认"；
  - B1: skills/**/SKILL.md 不得再以宿主绑定配置文件 CLAUDE.md 作为工作区参数文件
        （2026-09-23 清零收口：在途工作流已不存在，原 5 技能豁免集与基线文件移除，
        现为全库零容忍——工作区参数文件一律用 AGENTS.md）；
  - B3: 评审桥技能不得绑定 mcp__codex__ / Codex MCP。
"""
from __future__ import annotations

from pathlib import Path

TOOLBOX = Path(__file__).resolve().parents[1]
REPO = TOOLBOX.parent
CATALOG = REPO / "capabilities" / "catalog.json"
SKILLS = TOOLBOX / "skills"


def _hits(keyword: str, files: list[Path]) -> list[str]:
    out = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            if keyword in line:
                # 全文保留（供豁免注记匹配），仅显示时截断
                out.append(f"{f.relative_to(REPO)}:{i}: {line.strip()[:200]}")
    return out


def _skill_md_files() -> list[Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))


def test_catalog_no_opencode_session_phrase():
    hits = _hits("需在 OpenCode 会话中确认", [CATALOG])
    assert not hits, f"catalog.json B2 族回潮（{len(hits)} 处）: {hits[:3]}"


def test_skill_md_no_codex_review_binding():
    """B3 族：mcp__codex__ 全局清零；13 个评审桥技能内不得再出现 Codex 评审绑定表述。
    （宿主安装路径/宿主对照表如 visio README、lit-multi-db-search 属合法多宿主说明，不在禁列。）"""
    files = _skill_md_files()
    hits = [h for h in _hits("mcp__codex__", files) + _hits("Codex MCP", files)
            if "宿主中性表述" not in h]
    assert not hits, f"SKILL.md 出现宿主 MCP 评审绑定（B3 回潮，{len(hits)} 行）: {hits[:5]}"
    b3_skills = ["ablation-planner", "auto-paper-improvement-loop", "paper-figure-nature",
                 "paper-figure", "paper-plan", "paper-write", "paper-write-docx",
                 "paper-write-nature", "paper-write-nature-docx", "paper-writing",
                 "rebuttal", "result-to-claim", "training-check"]
    b3_hits = _hits("Codex", [SKILLS / s / "SKILL.md" for s in b3_skills])
    assert not b3_hits, f"B3 评审技能残留 Codex 绑定（{len(b3_hits)} 行）: {b3_hits[:5]}"


def test_skill_md_host_config_file_neutralized():
    hits = _hits("CLAUDE.md", _skill_md_files())
    assert not hits, (
        f"SKILL.md 出现宿主绑定配置文件 CLAUDE.md（{len(hits)} 行，B1 族回潮；"
        f"2026-09-23 起全库零容忍，工作区参数文件必须用 AGENTS.md）: {hits[:5]}")
