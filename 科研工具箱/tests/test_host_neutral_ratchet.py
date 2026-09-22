"""宿主中性化存量棘轮（2026-09-23 宿主引用修复批）。

钉住 B1/B2 两族已清零/受控的口径，防止回潮：
  - B2: capabilities/catalog.json 不得再出现"需在 OpenCode 会话中确认"；
  - B1: skills/**/SKILL.md 不得再以宿主绑定配置文件 CLAUDE.md 作为工作区参数文件
        （在途步骤技能暂豁免，见豁免基线文件，只减不增）。
"""
from __future__ import annotations

from pathlib import Path

TOOLBOX = Path(__file__).resolve().parents[1]
REPO = TOOLBOX.parent
CATALOG = REPO / "capabilities" / "catalog.json"
SKILLS = TOOLBOX / "skills"
RATCHET_FILE = TOOLBOX / "tests" / "data" / "host_neutral_inflight_baseline.txt"

# 在途（status=running）步骤对应技能：其 SKILL.md 本批禁改（sha256 闸），G3 收口后清零。
INFLIGHT_EXEMPT = {
    "comp-review",
    "comp-final-review",
    "comp-literature",
    "research-lit",
    "ars-research-summarizer",
}


def _hits(keyword: str, files: list[Path]) -> list[str]:
    out = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            if keyword in line:
                out.append(f"{f.relative_to(REPO)}:{i}: {line.strip()[:80]}")
    return out


def _skill_md_files() -> list[Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))


def _is_exempt(path: Path) -> bool:
    return path.parent.name in INFLIGHT_EXEMPT


def test_catalog_no_opencode_session_phrase():
    hits = _hits("需在 OpenCode 会话中确认", [CATALOG])
    assert not hits, f"catalog.json B2 族回潮（{len(hits)} 处）: {hits[:3]}"


def test_skill_md_host_config_file_neutralized():
    non_exempt = [f for f in _skill_md_files() if not _is_exempt(f)]
    hits = _hits("CLAUDE.md", non_exempt)
    assert not hits, (
        f"SKILL.md 出现宿主绑定配置文件 CLAUDE.md（{len(hits)} 行，B1 族回潮；"
        f"在途豁免 {sorted(INFLIGHT_EXEMPT)} 之外必须用 AGENTS.md）: {hits[:5]}")


def test_inflight_exempt_ratchet_shrinks():
    exempt_hits = _hits("CLAUDE.md", [f for f in _skill_md_files() if _is_exempt(f)])
    current = len(exempt_hits)
    if RATCHET_FILE.is_file():
        allowed = int(RATCHET_FILE.read_text(encoding="utf-8").strip() or "0")
        assert current <= allowed, (
            f"在途豁免 CLAUDE.md 命中 {current} 行 > 基线 {allowed} 行（棘轮只减不增，"
            f"G3 收口后应把豁免集清空）")
    else:
        RATCHET_FILE.parent.mkdir(exist_ok=True)
        RATCHET_FILE.write_text(str(current), encoding="utf-8")
        raise AssertionError(
            f"首次运行：已钉住 B1 在途豁免基线 {current} 行，复跑应通过")
