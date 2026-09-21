# -*- coding: utf-8 -*-
"""B1-3 机检：historical_problems.json 统计面与明细面必须自洽。

修复前：export_historical_json 硬编码 type_distribution（合计 20）与
HISTORICAL_PROBLEMS 明细（15 题）矛盾，且 generated_at 每次运行漂移；
2025 年赛题缺席（本科 A-C + 专科 D-E 共五题，题名经 WebSearch 多来源核实）。
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import case_fetcher  # noqa: E402

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "historical_problems.json"


def _load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _counter_from(problems: dict) -> Counter:
    return Counter(hint for year in problems.values()
                   for hint in year["type_hint"].values())


def test_statistics_consistent_with_problem_details():
    data = _load_data()
    counter = _counter_from(data["problems"])
    stats = data["statistics"]
    assert stats["total_years"] == len(data["problems"])
    assert stats["total_problems"] == sum(counter.values()), \
        "total_problems 与明细题数不一致（硬编码分布残留）"
    assert stats["type_distribution"] == dict(sorted(counter.items())), \
        "type_distribution 与明细 type_hint 不一致（硬编码分布残留）"


def test_each_year_type_hint_covers_all_questions():
    for year, probs in _load_data()["problems"].items():
        questions = sorted(k for k in probs if k != "type_hint")
        assert sorted(probs["type_hint"]) == questions, \
            f"{year} 年 type_hint 键与题号不对齐"


def test_2025_problems_present():
    probs = _load_data()["problems"].get("2025")
    assert probs, "2025 年赛题缺失"
    assert sorted(k for k in probs if k != "type_hint") == ["A", "B", "C", "D", "E"]
    assert probs["A"] == "烟幕干扰弹的投放策略"
    assert probs["E"] == "AI辅助智能体测"


def test_generated_at_is_fixed_data_version():
    generated_at = _load_data()["generated_at"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", generated_at), \
        f"generated_at 应为固定数据版本日期，实为 {generated_at!r}（运行时间戳会漂移）"


def test_data_file_matches_code_constant():
    data = _load_data()
    assert data["problems"] == case_fetcher.HISTORICAL_PROBLEMS, \
        "data 文件与 case_fetcher 代码常量漂移（需重跑 export_historical_json）"
    counter = _counter_from(case_fetcher.HISTORICAL_PROBLEMS)
    assert data["statistics"]["type_distribution"] == dict(sorted(counter.items()))
    assert data["generated_at"] == case_fetcher.DATA_VERSION
