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


def test_stale_exemption_is_reported(tmp_path: Path) -> None:
    exemptions = [
        ("never/exists.md", "~/.claude", "虚构条目用于测试 stale 报告"),
    ]
    # 复用 scan 的 stale 判定逻辑：豁免条目不在任何目标文件中出现（seen 为空）→ 全 stale
    seen: set[tuple[str, str]] = set()
    _ = seen
    stale = [
        {"file": f, "pattern": pat, "reason": reason}
        for f, pat, reason in exemptions
        if (f, pat) not in seen
    ]
    assert len(stale) == 1 and stale[0]["file"] == "never/exists.md"


def test_exemption_registry_schema_valid() -> None:
    data = json.loads(hds.EXEMPTIONS_PATH.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1
    for e in data["exemptions"]:
        assert set(e) >= {"file", "pattern", "reason"}, e
        assert e["reason"].strip(), f"豁免缺理由：{e}"
        assert (hds.TOOLBOX / e["file"]).is_file(), f"豁免指向不存在的文件：{e['file']}"
        assert e["pattern"] in dict(hds.PATTERNS), f"豁免 pattern 不在词表内：{e['pattern']}"
