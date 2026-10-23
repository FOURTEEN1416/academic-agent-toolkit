# -*- coding: utf-8 -*-
"""获奖论文版面卡索引契约（W2 发现账本批次）。

守护四件事：
  1. 索引只收 `status=done` 的卡——todo/partial 不得混入（partial 卡可能是半张表）；
  2. 每张卡必带六个消费字段 + 可溯源的 source_path/sha256；
  3. 覆盖数必须等于 progress.json 的 done 计数（允许源卡扩充后同比变化，不允许静默缩水）；
  4. 磁盘索引与源卡可重放一致（`build_award_layout_index.py --check` 的测试等价物）。

源卡在 `assets-local/`（gitignored 私有区）：公开 clone 缺席时，依赖源卡的断言 skip，
但对已交付索引自身的结构断言照常执行。
"""
import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SUITE_ROOT = TESTS_DIR.parent
REPO_ROOT = SUITE_ROOT.parent
sys.path.insert(0, str(SUITE_ROOT))
sys.path.insert(0, str(SUITE_ROOT / "tools"))

import build_award_layout_index as bali  # noqa: E402

INDEX_PATH = SUITE_ROOT / "data" / "award_layout_cards.json"
LAYOUT_DIR = REPO_ROOT / "assets-local" / "award-papers" / "layout-distill"
PROGRESS_PATH = LAYOUT_DIR / "progress.json"

REQUIRED_FIELDS = {
    "problem_type",
    "section_tree",
    "abstract_slots",
    "figure_table_conventions",
    "sentence_templates",
    "transferable_points",
}

requires_sources = pytest.mark.skipif(
    not PROGRESS_PATH.is_file(),
    reason="assets-local 版面卡真源缺席（公开 clone 语义缺位）",
)

# 索引登记为 local_only（由私有语料派生，公开 clone 不交付）：缺席时整体 skip，
# 不能让公开 clone 以"文件缺失"红掉——这与台账的 local_only 语义保持一致。
pytestmark = pytest.mark.skipif(
    not INDEX_PATH.is_file(),
    reason="版面卡索引缺席（local_only 生成物，公开 clone 不交付）",
)


def _load_index() -> dict:
    assert INDEX_PATH.is_file(), f"索引缺失: {INDEX_PATH}"
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _progress_statuses() -> dict[str, str]:
    progress = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    return {str(item["paper_id"]): str(item.get("status", "")).lower()
            for item in progress.get("papers", []) if item.get("paper_id")}


def test_index_schema_and_card_fields():
    index = _load_index()
    assert index["schema"] == "award-layout-cards:v1"
    cards = index["cards"]
    assert cards, "索引不得为空"
    for card in cards:
        missing = REQUIRED_FIELDS - set(card)
        assert not missing, f"{card.get('paper_id')} 缺字段: {sorted(missing)}"
        assert card["source_path"] and len(card["source_sha256"]) == 64
        assert card["abstract_slots"], f"{card['paper_id']} 摘要槽位为空，不应收进索引"
        assert len(card["transferable_points"]) >= 2, \
            f"{card['paper_id']} 可迁移要点过少，无法支撑写作参照"


def test_coverage_ratio_is_consistent():
    index = _load_index()
    coverage = index["coverage"]
    assert coverage["cards"] == len(index["cards"])
    assert coverage["ratio"] == f"{coverage['cards']}/{coverage['total']}"
    assert coverage["cards"] <= coverage["total"]


@requires_sources
def test_card_count_equals_progress_done():
    index = _load_index()
    statuses = _progress_statuses()
    done = {pid for pid, status in statuses.items() if status == "done"}
    todo = {pid for pid, status in statuses.items() if status == "todo"}
    ids = {card["paper_id"] for card in index["cards"]}
    assert len(index["cards"]) == len(done), \
        f"索引 {len(index['cards'])} 张 ≠ progress.done {len(done)} 张"
    assert ids == done
    assert not ids & todo, f"todo 卡混入索引: {sorted(ids & todo)}"


@requires_sources
def test_partial_cards_are_skipped_and_counted():
    index = _load_index()
    statuses = _progress_statuses()
    partial = {pid for pid, status in statuses.items() if status == "partial"}
    ids = {card["paper_id"] for card in index["cards"]}
    assert not ids & partial, f"partial 卡混入索引: {sorted(ids & partial)}"
    expected_partial = len(partial)
    assert index["skipped"]["partial"] == expected_partial


@requires_sources
def test_source_sha256_matches_card_file():
    for card in _load_index()["cards"]:
        card_path = REPO_ROOT / card["source_path"]
        assert card_path.is_file(), f"卡源不存在: {card['source_path']}"
        assert bali.sha256_file(card_path) == card["source_sha256"], \
            f"{card['paper_id']} sha256 漂移，索引已过期"


@requires_sources
def test_disk_index_is_reproducible_from_sources():
    rebuilt = bali.dump_index(bali.build_index(REPO_ROOT))
    # 归一化行尾：git checkout 在 Windows 可能把产物落成 CRLF，内容仍应等价。
    on_disk = INDEX_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert on_disk == rebuilt, "磁盘索引与源卡不同步，重跑 build_award_layout_index.py"
