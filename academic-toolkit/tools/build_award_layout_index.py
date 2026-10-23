#!/usr/bin/env python3
"""获奖论文版面卡索引：把 layout-distill 的 done 卡汇编成可检索数据（W2 发现账本批次）。

背景
----
`assets-local/award-papers/layout-distill/` 里已有 62 篇获奖论文的版面蒸馏卡，但
progress.json 只记了"哪篇做过"，卡本身是一篇一个 JSON、字段深且措辞自由。写作步
（comp-paper-zh）需要"按题型取结构与密度参照"，却只能逐文件翻——等于没有索引。

本工具只做一件事：**把 status=done 的卡投影成一份稳定的、可被技能/测试消费的索引**，
不改写卡片内容、不补造字段。todo/partial 一律跳过并计数（partial 卡可能只有半张表，
例如 2021_C085 的 abstract.slots 为空）；done 卡缺文件或结构不合规 → 直接报错退出，
不允许索引静默缩水。

字段契约（每张卡）
------------------
    paper_id / problem_type / source_path / source_sha256
    section_tree / abstract_slots / figure_table_conventions
    sentence_templates / transferable_points / card_notes

`transferable_points` 全部由卡内已有结构化字段确定性派生（摘要槽位、章节顺序、标题
深度、图表题注、句式覆盖、未证实章节），不引入人工判断，保证重跑可复现。

用法
----
    python tools/build_award_layout_index.py             # 生成 data/award_layout_cards.json
    python tools/build_award_layout_index.py --check     # 校验磁盘产物与源卡同步（CI 用）
    python tools/build_award_layout_index.py --json      # 打印机读摘要

退出码：0 成功/同步；1 产物漂移（--check）；2 源数据缺失或卡结构不合规。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

TOOLBOX_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = TOOLBOX_ROOT.parent
DEFAULT_LAYOUT_DIR = REPO_ROOT / "assets-local" / "award-papers" / "layout-distill"
DEFAULT_OUT = TOOLBOX_ROOT / "data" / "award_layout_cards.json"

SCHEMA = "award-layout-cards:v1"
REQUIRED_CARD_KEYS = ("paper_id", "problem_type", "section_tree",
                      "abstract", "figures_tables", "sentence_patterns")
REQUIRED_RECORD_KEYS = ("paper_id", "problem_type", "source_path", "source_sha256",
                        "section_tree", "abstract_slots", "figure_table_conventions",
                        "sentence_templates", "transferable_points")

_HEADING_NUM = re.compile(r"(?<![\d.])\d+(?:\.\d+)+")


class SourceError(RuntimeError):
    """源卡缺失或结构不合规——索引不能靠猜补出来。"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _section_order(section_tree: list[dict]) -> list[str]:
    """顶层章节顺序（level<=1；摘要常记 level=0）。"""
    titles = []
    for node in section_tree or []:
        try:
            level = int(node.get("level", 1))
        except (TypeError, ValueError):
            level = 1
        title = str(node.get("title") or "").strip()
        if title and level <= 1:
            titles.append(title)
    return titles


def _deepest_heading(section_tree: list[dict]) -> tuple[int, str]:
    """卡内出现的最深编号标题级别及其示例（如 5.1.2.1 -> 4）。"""
    best_level, example = 0, ""
    for node in section_tree or []:
        for text in (str(node.get("title") or ""), str(node.get("function") or "")):
            for match in _HEADING_NUM.finditer(text):
                level = match.group(0).count(".") + 1
                if level > best_level:
                    best_level, example = level, match.group(0)
    return best_level, example


def _transferable_points(card: dict) -> list[str]:
    """从卡内结构化字段派生可迁移要点（确定性，不补造）。"""
    points: list[str] = []

    abstract = card.get("abstract") or {}
    slots = abstract.get("slots") or []
    abstract_bits = [f"摘要 {len(slots)} 个槽位"]
    if abstract.get("word_count_range"):
        abstract_bits.append(str(abstract["word_count_range"]))
    if abstract.get("keywords_count") is not None:
        abstract_bits.append(f"关键词 {abstract['keywords_count']} 个")
    if any("公式" in str(slot) for slot in slots):
        abstract_bits.append("槽位含内嵌展示公式")
    points.append("；".join(abstract_bits))

    order = _section_order(card.get("section_tree") or [])
    if order:
        points.append("章节顺序：" + " → ".join(order))

    level, example = _deepest_heading(card.get("section_tree") or [])
    if level >= 2:
        points.append(f"标题最深 {level} 级（如 {example}），可据此决定小节拆分粒度")

    ft = card.get("figures_tables") or {}
    if ft:
        points.append(
            "图表：图 {f} 个 / 表 {t} 个；图题 {fig}；表题 {tbl}；密度 {density}".format(
                f=ft.get("figures", "未标"), t=ft.get("tables", "未标"),
                fig=ft.get("fig_caption_format", "未标"),
                tbl=ft.get("table_caption_format", "未标"),
                density=ft.get("per_page_density", "未标")))

    patterns = card.get("sentence_patterns") or []
    if patterns:
        chapters: list[str] = []
        for pattern in patterns:
            chapter = str(pattern.get("chapter") or "").strip()
            if chapter and chapter not in chapters:
                chapters.append(chapter)
        points.append(f"可复用句式 {len(patterns)} 条，覆盖章节：{'、'.join(chapters)}")

    standard = card.get("standard_sections") or {}
    unverified = [name for name, state in standard.items()
                  if state is False or str(state).strip().lower() == "inferred"]
    if unverified:
        points.append(f"未证实章节：{'、'.join(unverified)}（卡内标 inferred/false，移植前需自行核实）")

    return points


def _build_record(card_path: Path, repo_root: Path) -> dict:
    try:
        card = json.loads(card_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SourceError(f"{card_path.name} 读取失败: {exc}") from exc
    missing = [key for key in REQUIRED_CARD_KEYS if key not in card]
    if missing:
        raise SourceError(f"{card_path.name} 缺字段: {missing}")

    abstract = card.get("abstract") or {}
    record = {
        "paper_id": card["paper_id"],
        "problem_type": card["problem_type"],
        "source_path": _rel(card_path, repo_root),
        "source_sha256": sha256_file(card_path),
        "section_tree": card["section_tree"],
        "abstract_slots": abstract.get("slots") or [],
        "figure_table_conventions": card["figures_tables"],
        "sentence_templates": card["sentence_patterns"],
        "transferable_points": _transferable_points(card),
    }
    pages_dir = (card.get("source") or {}).get("pages_dir")
    if pages_dir:
        record["pages_dir"] = pages_dir
    if card.get("notes"):
        record["card_notes"] = card["notes"]
    missing_record = [key for key in REQUIRED_RECORD_KEYS if key not in record]
    if missing_record:
        raise SourceError(f"{card_path.name} 投影缺字段: {missing_record}")
    return record


def build_index(repo_root: Path = REPO_ROOT,
                layout_dir: Path | None = None) -> dict:
    """读取 progress.json 与 done 卡，返回索引字典（不落盘）。"""
    layout_dir = Path(layout_dir) if layout_dir else DEFAULT_LAYOUT_DIR
    progress_path = layout_dir / "progress.json"
    if not progress_path.is_file():
        raise SourceError(f"找不到进度真源: {progress_path}")
    try:
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SourceError(f"progress.json 不可读: {exc}") from exc

    papers = progress.get("papers") or []
    if not papers:
        raise SourceError("progress.json 的 papers 为空，拒绝生成空索引")
    status_of = {str(item.get("paper_id")): str(item.get("status", "")).strip().lower()
                 for item in papers if item.get("paper_id")}
    total = int((progress.get("counts") or {}).get("total") or len(status_of))

    done_ids = sorted(pid for pid, status in status_of.items() if status == "done")
    skipped = Counter(status for pid, status in status_of.items() if status != "done")

    missing_cards: list[str] = []
    records: list[dict] = []
    for paper_id in done_ids:
        card_path = layout_dir / f"{paper_id}.json"
        if not card_path.is_file():
            missing_cards.append(paper_id)
            continue
        records.append(_build_record(card_path, repo_root))
    if missing_cards:
        raise SourceError(
            f"status=done 但缺卡文件: {missing_cards}——先补卡或修正 progress，不能静默跳过")

    return {
        "schema": SCHEMA,
        "note": ("由 tools/build_award_layout_index.py 从前序版面蒸馏卡投影生成；"
                 "只收录 status=done，卡片原文为真源，本索引不手工编辑。"),
        "source_progress": {
            "path": _rel(progress_path, repo_root),
            "sha256": sha256_file(progress_path),
            "updated": progress.get("updated"),
        },
        "coverage": {
            "cards": len(records),
            "total": total,
            "ratio": f"{len(records)}/{total}",
        },
        "skipped": {
            "todo": skipped.get("todo", 0),
            "partial": skipped.get("partial", 0),
            "failed": skipped.get("failed", 0),
            "other": sum(count for status, count in skipped.items()
                         if status not in {"todo", "partial", "failed"}),
        },
        "cards": records,
    }


def dump_index(index: dict) -> str:
    return json.dumps(index, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成/校验获奖论文版面卡索引")
    parser.add_argument("--check", action="store_true", help="只校验磁盘产物是否与源卡同步")
    parser.add_argument("--json", action="store_true", help="打印机读摘要")
    parser.add_argument("--layout-dir", default=None, help="版面卡目录（默认 assets-local 真源）")
    parser.add_argument("--out", default=None, help="输出路径（默认 data/award_layout_cards.json）")
    args = parser.parse_args(argv)

    layout_dir = Path(args.layout_dir) if args.layout_dir else DEFAULT_LAYOUT_DIR
    out_path = Path(args.out) if args.out else DEFAULT_OUT
    try:
        index = build_index(REPO_ROOT, layout_dir)
    except SourceError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    payload = dump_index(index)
    summary = {
        "status": "ok",
        "coverage": index["coverage"]["ratio"],
        "cards": index["coverage"]["cards"],
        "skipped": index["skipped"],
        "out": _rel(out_path, REPO_ROOT),
        "out_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }

    if args.check:
        if not out_path.is_file():
            print(f"❌ 产物缺失: {summary['out']}（运行无 --check 生成）", file=sys.stderr)
            return 1
        current = out_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if current != payload:
            print(f"❌ 产物与源卡不同步: {summary['out']}（重新生成并复查 diff）",
                  file=sys.stderr)
            return 1
        summary["status"] = "in-sync"
        print(json.dumps(summary, ensure_ascii=False) if args.json
              else f"✅ 索引同步：{summary['coverage']}（{summary['out']}）")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # 写字节而非文本：Windows 文本模式会把 \n 翻译成 \r\n，导致跨平台 sha256 漂移。
    out_path.write_bytes(payload.encode("utf-8"))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(f"✅ 生成版面卡索引 {summary['coverage']}：{summary['out']}")
        print(f"   跳过 todo={summary['skipped']['todo']} "
              f"partial={summary['skipped']['partial']} "
              f"failed={summary['skipped']['failed']}")
        print(f"   sha256={summary['out_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
