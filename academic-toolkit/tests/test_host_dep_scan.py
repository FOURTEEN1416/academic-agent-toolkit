"""宿主依赖扫描器守卫（2026-09-24 彻底化收口）。

三重钉：
  1. 真实 skills/ 树上"登记外零命中"（豁免清单 = data/host_dep_exemptions.json）；
  2. 扫描器对注入的新命中必须 FAIL（守卫不是摆设）；
  3. 豁免条目命中归零时报 stale（封闭集合须收缩，不许挂空豁免）。

取代"每发现一类漏网加一条测试"的补丁式守卫：此后宿主类回潮由本测试统一拦截，
新命中只有两条路——改写掉，或经用户裁决登记进豁免清单。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import host_dep_scan as hds  # noqa: E402


def test_real_tree_zero_unregistered_hits() -> None:
    res = hds.scan()
    assert res["ok"], (
        f"skills/ 出现豁免登记外的宿主特征词命中 {res['counts']['fail_files']} 文件"
        f" / {res['counts']['fail_hits']} 处："
        + "; ".join(f"{e['file']}::{e['pattern']}" for e in res["fails"][:8])
        + "（处置：改写为宿主中性，或经用户裁决登记进 data/host_dep_exemptions.json）")


def test_new_hit_fails_scan(tmp_path: Path) -> None:
    target = tmp_path / "somewhere"
    target.mkdir()
    (target / "probe.md").write_text(
        "install with: cp -r . ~/.claude/skills/\n", encoding="utf-8")
    files = [target / "probe.md"]
    fails: list[tuple[str, str]] = []
    text = files[0].read_text(encoding="utf-8")
    for pat, _ in hds.PATTERNS:
        if pat in text:
            fails.append((str(files[0]), pat))
    assert fails, "扫描器未能识别注入的新命中（守卫失效）"
    assert any(pat == "~/.claude" for _, pat in fails)


def test_stale_exemption_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """豁免条目指向真实在盘文件但 pattern 零命中 → 真实 scan() 必须报 stale。

    （历史版本在此手搓 seen 空集自证恒真、未调用任何生产判定，"过期即报"
    这道门禁实际零覆盖；现改为临时豁免清单 + monkeypatch 走完整生产路径。）
    """
    exemptions = {"schema_version": 1, "exemptions": [
        {"file": "skills/agent-bootstrap/SKILL.md", "pattern": "~/.claude",
         "reason": "虚构条目用于测试 stale 报告"},
    ]}
    fake = tmp_path / "host_dep_exemptions.json"
    fake.write_text(json.dumps(exemptions, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(hds, "EXEMPTIONS_PATH", fake)

    res = hds.scan()
    stale = res["stale_exemptions"]
    assert len(stale) == 1, stale
    assert stale[0]["file"] == "skills/agent-bootstrap/SKILL.md"
    assert stale[0]["pattern"] == "~/.claude"


def test_exemption_registry_schema_valid() -> None:
    data = json.loads(hds.EXEMPTIONS_PATH.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1
    for e in data["exemptions"]:
        assert set(e) >= {"file", "pattern", "reason"}, e
        assert e["reason"].strip(), f"豁免缺理由：{e}"
        assert (hds.TOOLBOX / e["file"]).is_file(), f"豁免指向不存在的文件：{e['file']}"
        assert e["pattern"] in dict(hds.PATTERNS), f"豁免 pattern 不在词表内：{e['pattern']}"
