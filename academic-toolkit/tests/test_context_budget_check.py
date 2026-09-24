"""常驻上下文预算审计回归（吸收同类项目上下文税纪律，2026-09-19 建立）。

守护四件事：
  1. 真仓在预算内且**本地自研描述零污染**（description 是搜索索引而非文档）；
  2. 污染判据真的能抓（六类实施细节各一例负例，含"描述里塞仓库路径/步骤编号/门禁词"）；
  3. 预算上限真的能拦（合成超预算数据 → FAIL；上限不是摆设）；
  4. 上游豁免口径可解释：**外部族前缀 ∪ 溯源台账在位**，且本地自研六域技能
     不得靠前缀逃避（防"把自家技能伪装成上游来绕过罚则"）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import context_budget_check as cb  # noqa: E402


def _measure_texts(tmp_path: Path, entries: dict[str, str]) -> dict:
    """用临时技能树跑 measure（monkeypatch 根目录）。"""
    for name, desc in entries.items():
        d = tmp_path / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            f'---\nname: {name}\ndescription: "{desc}"\n---\n\n# {name}\n', encoding="utf-8")
    original = cb.SKILLS_ROOT
    try:
        cb.SKILLS_ROOT = tmp_path
        return cb.measure()
    finally:
        cb.SKILLS_ROOT = original


# ---------- 真仓机检 ----------

def test_real_repo_within_budget() -> None:
    res = cb.measure()
    assert res["total_chars"] <= res["ceilings"]["total_desc"], res["errors"]


def test_real_repo_has_no_local_pollution() -> None:
    """本地自研技能的描述不得含实施细节（路径/步骤编号/门禁词/箭头）。"""
    res = cb.measure()
    polluted = [r["skill"] for r in res["local_polluted"]]
    assert polluted == [], f"本地描述污染：{polluted}"


def test_real_repo_reports_resident_tax() -> None:
    """常驻税必须被量化报告（这是本工具存在的理由）。

    下限取公开交付口径 **250**（2026-09-24 实测 clone 即所见口径；本机盘面 255 =
    250 + 5 个被 gitignore 隔离的无 License 技能）。⚠️ 棘轮必须按 **clone 口径**
    设——硬编码本机盘面数会让 CI（clone 无隔离件）必红，且本机因隔离件垫高而
    假绿（2026-09-24 实锤：W3 清洗 255→250 后此断言未随批下调，CI 连续红一天）。
    """
    res = cb.measure()
    assert res["est_resident_tokens"] > 0
    assert 0 < res["share_of_200k"] < 100
    assert res["skills_total"] >= 250


def test_upstream_ledger_counts_as_upstream() -> None:
    """有 references/UPSTREAM.md 的技能必须判为上游集成件（口径可解释）。"""
    assert cb.has_upstream_ledger("scientific-visualization") or cb.has_upstream_ledger("matplotlib")


def test_local_domains_are_not_exempt(tmp_path: Path) -> None:
    """本地六域技能不得被当成上游（2026-09-23 v2.0 起按 UPSTREAM.md 溯源判定，
    名字前缀不再是豁免信号——无台账即本地件，计入罚则）。"""
    for name in ("course-one", "humanities-one", "patent-one", "copyright-one",
                 "research-one", "idea-one", "ars-one"):
        assert not cb.is_upstream(name), name
    (tmp_path / "course-two").mkdir(parents=True)
    (tmp_path / "course-two" / "UPSTREAM.md").write_text("Upstream: x", encoding="utf-8")
    original = cb.SKILLS_ROOT
    try:
        cb.SKILLS_ROOT = tmp_path
        assert cb.is_upstream("course-two"), "有溯源台账的才豁免"
    finally:
        cb.SKILLS_ROOT = original


# ---------- 污染判据（负例） ----------

def test_pollution_detects_repo_paths(tmp_path: Path) -> None:
    res = _measure_texts(tmp_path, {"x-one": "做某事的技能。见 skills/_utils/foo.py 的实现细节。"})
    assert any("仓库路径" in w for r in res["local_polluted"] for w in r["pollution"])


def test_pollution_detects_arrow_flow(tmp_path: Path) -> None:
    res = _measure_texts(tmp_path, {"x-one": "先读题 → 再建模 → 最后写论文，用于此处。"})
    assert any("流程箭头" in w for r in res["local_polluted"] for w in r["pollution"])


def test_pollution_detects_step_numbers(tmp_path: Path) -> None:
    res = _measure_texts(tmp_path, {"x-one": "本技能按步骤 1 到步骤 5 执行，用于处理。"})
    assert any("步骤编号" in w for r in res["local_polluted"] for w in r["pollution"])


def test_pollution_detects_gate_and_hash_detail(tmp_path: Path) -> None:
    res = _measure_texts(tmp_path, {"x-one": "产出后过门禁并记录 sha256 与 min_bytes 规格。"})
    assert any("门禁/哈希" in w for r in res["local_polluted"] for w in r["pollution"])


def test_clean_description_has_no_pollution(tmp_path: Path) -> None:
    res = _measure_texts(tmp_path, {"x-one": "做某事的技能。触发词：做某事、do-something。"})
    assert res["local_polluted"] == []


def test_upstream_pollution_is_counted_not_penalized(tmp_path: Path) -> None:
    """上游件描述含实施细节只计数不计罚（改了会与上游分叉）——以 UPSTREAM.md 判上游。"""
    d = tmp_path / "ars-one"
    d.mkdir(parents=True)
    (d / "UPSTREAM.md").write_text("Upstream: x", encoding="utf-8")
    (d / "SKILL.md").write_text(
        '---\nname: ars-one\ndescription: "上游技能，流程为 A → B，含 tools/x.py。"\n---\n\n# ars-one\n',
        encoding="utf-8")
    original = cb.SKILLS_ROOT
    try:
        cb.SKILLS_ROOT = tmp_path
        res = cb.measure()
    finally:
        cb.SKILLS_ROOT = original
    assert res["upstream_polluted"], "上游污染应被计入统计"
    assert res["local_polluted"] == [], "上游污染不得计入罚则"


# ---------- 预算门禁（负例） ----------

def test_budget_ceiling_is_enforced(tmp_path: Path) -> None:
    """超预算必须 FAIL（把临时根 + 临时上限一起收紧来验证，不依赖真仓规模）。"""
    entries = {f"x-{i:03d}": "描述" * 60 for i in range(30)}
    original_root, original_ceiling = cb.SKILLS_ROOT, cb.TOTAL_DESC_CEILING
    try:
        cb.SKILLS_ROOT = tmp_path
        cb.TOTAL_DESC_CEILING = 500
        for name, desc in entries.items():
            d = tmp_path / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(
                f'---\nname: {name}\ndescription: "{desc}"\n---\n', encoding="utf-8")
        res = cb.measure()
        assert not res["ok"]
        assert any("上限" in e for e in res["errors"])
    finally:
        cb.SKILLS_ROOT, cb.TOTAL_DESC_CEILING = original_root, original_ceiling


def test_per_skill_cap_flags_oversized_local_description(tmp_path: Path) -> None:
    res = _measure_texts(tmp_path, {"x-one": "正" * (cb.PER_SKILL_DESC_CEILING + 10)})
    assert res["over_cap"], "超单条上限的本地描述应被标记"
