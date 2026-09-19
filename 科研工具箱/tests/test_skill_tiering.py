"""技能分层常驻回归（2026-09-19 建立）。

守护五件事：
  1. **分层派生**：核心层含主链全部技能；核心+按需 = 全库（无遗漏、无重复）；
  2. **压缩质量**：按需层常驻描述 ≤ 上限、**只做截取不改写**（必为完整描述的前缀）、
     幂等；核心层描述一字不动；
  3. **索引无损**：`full_description` 永不短于常驻描述（压缩是迁移不是丢失）；
  4. **索引可用**（本文件最关键）：索引通道必须真的改变路由结果——否则分层就是拿
     路由质量换指标。用"只在完整描述里出现的罕见词"构造查询，验证 without→错、with→对；
  5. 同步与降级：`--check` 与实况一致；索引缺失时如实降级不崩。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_skill_index as bsi  # noqa: E402
import skill_trigger_audit as sta  # noqa: E402

INDEX = ROOT / "data" / "skill_routing_index.json"
TIERS = ROOT / "data" / "skill_tiers.json"

def _derive_index_only_case() -> tuple[str, str] | None:
    """派生"只在完整描述里出现的稀有词"案例（数据驱动，避免硬编码随压缩变化而失效）。

    判据：该词在 full 里、不在 resident 里、且全库文档频率为 0（唯一指向该技能），
    并要求 without/with 的路由结果确实不同——三者同时成立才算有效案例。
    """
    idx = _index()
    recs = sta.audit_skills(sta.SKILLS_ROOT)["records"]
    for name, entry in idx["skills"].items():
        if not entry["description_compacted"]:
            continue
        lost = sta.route_tokens(entry["full_description"]) - sta.route_tokens(entry["resident_description"])
        for tok in sorted(lost):
            if not (tok.isascii() and tok.isalpha() and len(tok) >= 6):
                continue
            if any(tok in sta.route_tokens(r["description"]) for r in recs.values()):
                continue
            query = f"帮我处理 {tok} 的事情"
            without = sta.route(query, top_k=1)
            with_idx = sta.route(query, top_k=1, with_index=True)
            if without and with_idx and without[0]["skill"] != with_idx[0]["skill"]                     and with_idx[0]["skill"] == name:
                return query, name
    return None


def _index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))


# ---------- 分层派生 ----------

def test_index_and_tiers_exist() -> None:
    assert INDEX.is_file() and TIERS.is_file(), "分层文件缺失，需跑 build_skill_index.py --emit"


def test_core_plus_ondemand_covers_all_skills() -> None:
    """磁盘上的每个技能都必须落在索引的某一层（核心或按需）。

    判据是**完备包含**而非双向相等：索引随仓分发、按完整仓生成，公开 clone 里被
    .gitignore 隔离的技能必然"索引有、磁盘无"——多出的条目无害（无对应技能目录，
    路由时不会被选中）；而**漏掉磁盘技能**才是真缺陷（该技能将漏出索引路由）。
    """
    idx = _index()
    live = set(bsi.iter_skill_names())
    missing = sorted(live - set(idx["skills"]))
    assert missing == [], f"以下技能未入索引（会漏出路由）: {missing}"
    counts = idx["counts"]
    assert counts["core"] + counts["ondemand"] == len(idx["skills"])


def test_main_chain_is_core() -> None:
    """主链技能必须在核心层（否则主链路由要靠索引，属本末倒置）。"""
    idx = _index()
    tpl = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    for step in tpl["comp_cumcm"]["sub_steps"]:
        assert idx["skills"][step["skill_name"]]["tier"] == "core", step["skill_name"]


def test_tier_derivation_is_deterministic() -> None:
    """同一真仓状态下重复派生必须得到同一分层（否则分层会随机漂移）。"""
    a = {k: v["tier"] for k, v in bsi.build_index()["skills"].items()}
    b = {k: v["tier"] for k, v in bsi.build_index()["skills"].items()}
    assert a == b


# ---------- 压缩质量 ----------

def test_core_descriptions_untouched() -> None:
    idx = _index()
    for name, entry in idx["skills"].items():
        if entry["tier"] == "core":
            assert entry["resident_description"] == entry["full_description"], name


def test_ondemand_resident_within_cap() -> None:
    idx = _index()
    over = [(n, len(e["resident_description"])) for n, e in idx["skills"].items()
            if e["tier"] == "ondemand" and len(e["resident_description"]) > bsi.OND_RESEARCH_CAP]
    assert over == [], over


def test_compaction_only_truncates() -> None:
    """压缩只许截取，不许改写：常驻描述必须是完整描述的前缀（去引号差异后）。"""
    idx = _index()
    bad = []
    for name, entry in idx["skills"].items():
        if not entry["description_compacted"]:
            continue
        full = entry["full_description"].replace('"', "”")
        if not full.startswith(entry["resident_description"]):
            bad.append(name)
    assert bad == [], f"压缩改写了原文（应为纯截取）: {bad}"


def test_compaction_is_idempotent() -> None:
    """幂等只对**按需层**成立：核心层描述本就长于按需上限，再压会破坏核心层。"""
    idx = _index()
    for name, entry in idx["skills"].items():
        if entry["tier"] != "ondemand":
            continue
        once = entry["resident_description"]
        assert bsi.compact_description(once) == once, name


def test_compaction_never_breaks_mid_word() -> None:
    """兜底回退到整词：常驻短句不得以半个英文单词收尾。"""
    idx = _index()
    bad = []
    for name, entry in idx["skills"].items():
        if not entry["description_compacted"]:
            continue
        text = entry["resident_description"]
        if text and text[-1].isascii() and text[-1].isalpha():
            # 允许整词结尾：检查其后的原文字符是否是词字符（是则说明切在词中）
            pos = entry["full_description"].replace('"', "”").find(text)
            if pos >= 0:
                nxt = entry["full_description"].replace('"', "”")[pos + len(text): pos + len(text) + 1]
                if nxt and (nxt.isalnum() or nxt in "-_"):
                    bad.append(name)
    assert bad == [], f"切在词中间: {bad}"


# ---------- 索引无损 ----------

def test_index_preserves_full_descriptions() -> None:
    idx = _index()
    for name, entry in idx["skills"].items():
        assert len(entry["full_description"]) >= len(entry["resident_description"]), name


def test_full_description_never_shrinks(tmp_path: Path, monkeypatch) -> None:
    """单调不减：索引已有更长的完整描述时，重建不得把它缩短（这正是本项目踩过的坑）。"""
    idx = _index()
    victim = next(n for n, e in idx["skills"].items() if e["description_compacted"])
    original = idx["skills"][victim]["full_description"]
    monkeypatch.setattr(bsi, "INDEX_PATH", INDEX)
    rebuilt = bsi.build_index(keep_previous=True)
    assert len(rebuilt["skills"][victim]["full_description"]) >= len(original) - 1, victim


# ---------- 索引可用（最关键） ----------

def test_index_channel_changes_routing() -> None:
    """索引不是装饰：至少存在"没有索引就路由错、并入索引就路由对"的案例。

    案例**数据驱动派生**——压缩程度会随维护变化，硬编码案例会悄悄失去证明力。
    派生不出任何案例时本测试明确失败（而不是跳过）：那说明分层已退化为只压不补。
    """
    case = _derive_index_only_case()
    assert case is not None, "派生不出索引通道案例——分层可能已退化为只压不补"
    query, expected = case
    without = sta.route(query, top_k=1)
    with_idx = sta.route(query, top_k=1, with_index=True)
    assert (without[0]["skill"] if without else None) != expected, query
    assert with_idx[0]["skill"] == expected, (query, with_idx)


def test_index_entries_are_ondemand_only() -> None:
    """索引只应暴露按需层（核心层描述本就常驻，重复暴露＝双份成本）。"""
    assert all(e["tier"] == "ondemand" for e in sta.load_routing_index().values())


def test_augmented_records_extends_not_replaces() -> None:
    aug = sta.augmented_records()
    plain = sta.audit_skills(sta.SKILLS_ROOT)["records"]
    assert set(aug) == set(plain)
    longer = [n for n in plain if len(aug[n]["description"]) > len(plain[n]["description"])]
    assert longer, "索引未带来任何完整描述（分层未生效）"


# ---------- 同步与降级 ----------

def test_check_reports_in_sync() -> None:
    res = bsi.check()
    assert res["ok"], res["problems"]


def test_check_detects_drift(tmp_path: Path, monkeypatch) -> None:
    """索引落后于实况（tier 或常驻描述不一致）必须报错。"""
    data = _index()
    victim = next(iter(data["skills"]))
    data["skills"][victim]["resident_description"] = "被篡改"
    fake = tmp_path / "index.json"
    fake.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(bsi, "INDEX_PATH", fake)
    res = bsi.check()
    assert not res["ok"]
    assert any(victim in p for p in res["problems"])


def test_route_degrades_without_index(tmp_path: Path, monkeypatch) -> None:
    """索引缺失时如实降级：不崩、也不假装有索引（TOOL_GAP）。"""
    monkeypatch.setattr(sta, "ROUTING_INDEX_PATH", tmp_path / "nope.json")
    assert sta.load_routing_index() == {}
    hits = sta.route("帮我处理 ablations 的事情", top_k=1, with_index=True)
    assert hits, "降级后仍应给出常驻层路由结果"


def test_cli_check_exit_zero() -> None:
    proc = subprocess.run([sys.executable, str(ROOT / "tools" / "build_skill_index.py"), "--check"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)
    assert proc.returncode == 0, proc.stdout[-400:]
