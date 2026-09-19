"""CUMCM 实战经验库回归（P1 沉淀资产，2026-09-19 建立）。

守护四件事：
  1. 工具自身：schema / 强制点在位 / 双向一致 / 强制点过度集中告警的判定逻辑；
  2. 真仓零空话：`data/contest_lessons.json` 全条目 enforced_by 必须真实存在——
     经验不许写成"应当建立 XXX"这类无落点承诺；
  3. 真仓双向锁死：JSON 与 `data/contest_lessons.md` 的 ID 集合完全一致；
  4. 内容下限：坑条目必须带 severity 与 impact（防退化成现象清单）。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import contest_lessons_check as clc  # noqa: E402

LESSONS = ROOT / "data" / "contest_lessons.json"
LESSONS_MD = ROOT / "data" / "contest_lessons.md"


def _minimal_lessons() -> dict:
    return {
        "schema_version": 1,
        "meta": {"stages": {"day1": "x"}, "topics": {"audit": "y"}},
        "scenarios": [{
            "id": "S1", "stage": "day1", "topic": "audit", "title": "t",
            "trigger": "a", "decision": "b", "rationale": "c",
            "enforced_by": "科研工具箱/engine/quality_gates.py",
        }],
        "pitfalls": [{
            "id": "P01", "severity": "P0", "stage": "day1", "topic": "audit", "title": "t",
            "symptom": "a", "root_cause": "b", "impact": "c", "prevention": "d",
            "enforced_by": "科研工具箱/engine/quality_gates.py",
        }],
        "checklists": [{
            "id": "CL1", "stage": "day1", "title": "t", "items": ["a"],
            "enforced_by": "科研工具箱/engine/quality_gates.py",
        }],
    }


# ---------- 真仓机检 ----------

def test_real_lessons_check_passes() -> None:
    """真仓经验库必须全过（schema + 强制点在位 + 双向一致）。"""
    result = clc.run(REPO)
    assert result["ok"], f"经验库机检失败: {result['errors']}"


def test_real_pitfalls_carry_severity_and_impact() -> None:
    """每个坑必须带 severity（P0/P1/P2）与非空 impact——防退化成现象清单。"""
    data = json.loads(LESSONS.read_text(encoding="utf-8"))
    assert data["pitfalls"], "坑清单不得为空"
    for entry in data["pitfalls"]:
        assert entry["severity"] in clc.SEVERITIES, entry["id"]
        assert entry["impact"].strip(), entry["id"]


def test_real_checklists_have_actionable_items() -> None:
    """清单条目必须可执行（非空且不少于 4 项）——防退化成口号。"""
    data = json.loads(LESSONS.read_text(encoding="utf-8"))
    for entry in data["checklists"]:
        assert len(entry["items"]) >= 4, f"{entry['id']} 条目过少"


def test_real_meta_points_to_existing_human_readable() -> None:
    """meta.human_readable 必须指向真实存在的人读真源。"""
    data = json.loads(LESSONS.read_text(encoding="utf-8"))
    rel = data["meta"]["human_readable"]
    assert (REPO / rel).is_file(), rel


# ---------- 判定逻辑（负例） ----------

def test_schema_rejects_missing_field() -> None:
    data = _minimal_lessons()
    del data["pitfalls"][0]["impact"]
    result = clc.check_schema(data)
    assert not result["ok"]
    assert any("impact" in e for e in result["errors"])


def test_schema_rejects_unknown_stage_and_topic() -> None:
    data = _minimal_lessons()
    data["scenarios"][0]["stage"] = "day99"
    data["pitfalls"][0]["topic"] = "nope"
    result = clc.check_schema(data)
    assert not result["ok"]
    assert any("stage='day99'" in e for e in result["errors"])
    assert any("topic='nope'" in e for e in result["errors"])


def test_schema_rejects_duplicate_ids() -> None:
    data = _minimal_lessons()
    data["pitfalls"][0]["id"] = "S1"
    result = clc.check_schema(data)
    assert not result["ok"]
    assert any("ID 重复" in e for e in result["errors"])


def test_schema_rejects_bad_severity() -> None:
    data = _minimal_lessons()
    data["pitfalls"][0]["severity"] = "P9"
    result = clc.check_schema(data)
    assert not result["ok"]
    assert any("severity" in e for e in result["errors"])


def test_enforced_by_missing_path_is_flagged() -> None:
    """强制点指向不存在文件 = 空话，必须报错。"""
    data = _minimal_lessons()
    data["pitfalls"][0]["enforced_by"] = "科研工具箱/engine/does_not_exist.py"
    result = clc.check_enforced_by(data, REPO)
    assert not result["ok"]
    assert any("强制点不存在" in e for e in result["errors"])


def test_enforced_by_absolute_path_is_flagged() -> None:
    data = _minimal_lessons()
    data["pitfalls"][0]["enforced_by"] = "D:/abs/path.py"
    result = clc.check_enforced_by(data, REPO)
    assert not result["ok"]
    assert any("仓库根相对路径" in e for e in result["errors"])


def test_bidirectional_flags_missing_and_ghost_ids(tmp_path: Path) -> None:
    """MD 缺写条目 / MD 出现幽灵 ID 都要被拦。"""
    data = _minimal_lessons()
    md = tmp_path / "lessons.md"
    md.write_text("只有 S1，没有 P01；另有一个幽灵 P99", encoding="utf-8")
    result = clc.check_bidirectional(data, md)
    assert not result["ok"]
    assert any("未写" in e for e in result["errors"])          # P01 / CL1 缺失
    assert any("幽灵条目" in e for e in result["errors"])       # P99
    assert result["md_only"] == ["P99"]


def test_bidirectional_passes_on_synced_pair(tmp_path: Path) -> None:
    data = _minimal_lessons()
    md = tmp_path / "lessons.md"
    md.write_text("S1 / P01 / CL1 三条都在", encoding="utf-8")
    result = clc.check_bidirectional(data, md)
    assert result["ok"], result["errors"]


def test_concentration_warning_triggers_on_single_hotspot() -> None:
    """单一文件覆盖 >60% 条目时告警（覆盖度虚高信号）。"""
    enforced = {"per_file": {"a.py": 7, "b.py": 1, "c.py": 1}}
    assert clc.concentration_warning(enforced) is not None


def test_concentration_warning_silent_when_spread() -> None:
    enforced = {"per_file": {"a.py": 3, "b.py": 3, "c.py": 3, "d.py": 1}}
    assert clc.concentration_warning(enforced) is None


def test_missing_lessons_file_is_reported(tmp_path: Path) -> None:
    """经验库缺失时给出明确错误而非抛栈。"""
    original = clc.LESSONS_JSON
    try:
        clc.LESSONS_JSON = tmp_path / "nope.json"
        result = clc.run(REPO)
        assert not result["ok"]
        assert any("经验库缺失" in e for e in result["errors"])
    finally:
        clc.LESSONS_JSON = original
