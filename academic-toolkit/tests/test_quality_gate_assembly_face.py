"""装配面解析（assembly_faces）契约：体量/引用两道判据读同一个面，且判据仍有牙。

来源：华为杯 2026D 工作区第 7 步假红——章节平铺在 paper/ 下，而旧实现只认
`sections/` 目录约定，导致 1863B 装配壳被判过薄、正文 14 处引用被判为零。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.quality_gates import QualityGate, assembly_faces  # noqa: E402

SKILL = "comp-paper-zh"
MIN_SIZE = 10000


def _write(path: Path, nbytes: int, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = text or "%"
    pad = "x" * max(0, nbytes - len(body) - 1)
    path.write_text(f"{body} {pad}\n", encoding="utf-8", newline="\n")


def _ws(tmp_path: Path, main_body: str) -> Path:
    (tmp_path / "paper").mkdir(parents=True, exist_ok=True)
    (tmp_path / "paper" / "main.tex").write_text(main_body, encoding="utf-8", newline="\n")
    return tmp_path


def test_flat_layout_is_measured(tmp_path):
    """扁平布局（章节与 main.tex 同目录）体量必须被读到。"""
    ws = _ws(tmp_path, "\\input{01_intro}\n\\input{02_method}\n")
    _write(ws / "paper" / "01_intro.tex", 6000)
    _write(ws / "paper" / "02_method.tex", 6000)
    got = QualityGate(ws).check_min_size(SKILL, "paper/main.tex")
    assert got["ok"] is True, got
    assert got["size"] > MIN_SIZE


def test_sections_layout_still_measured(tmp_path):
    """原 sections/ 约定不得因本次修正而退化。"""
    ws = _ws(tmp_path, "\\input{sections/01_intro}\n")
    _write(ws / "paper" / "sections" / "01_intro.tex", 12000)
    got = QualityGate(ws).check_min_size(SKILL, "paper/main.tex")
    assert got["ok"] is True, got


def test_no_assembly_face_added(tmp_path):
    """反向用例（牙）：只有薄壳、无装配时仍必须判不过，不得被修正顺带放行。"""
    ws = _ws(tmp_path, "\\begin{document}\n\\end{document}\n")
    got = QualityGate(ws).check_min_size(SKILL, "paper/main.tex")
    assert got["ok"] is False and got["size"] < MIN_SIZE, got


def test_input_outside_root_not_read(tmp_path):
    """反向用例（边界）：\\input 越出主 tex 目录的文件不得计入计量面。"""
    outside = tmp_path / "outside_big.tex"
    _write(outside, 20000)
    ws = _ws(tmp_path, "\\input{../outside_big}\n")
    assert assembly_faces(ws / "paper" / "main.tex") == []
    got = QualityGate(ws).check_min_size(SKILL, "paper/main.tex")
    assert got["ok"] is False, got


def test_dedup_union_counts_once(tmp_path):
    """\\input 目标与 sections/ 目录并集时同一文件只计一次（重复计数会虚增体量）。"""
    _write(tmp_path / "paper" / "sections" / "01_intro.tex", 12000)
    ws = _ws(tmp_path, "\\input{sections/01_intro}\n")
    faces = assembly_faces(ws / "paper" / "main.tex")
    assert len(faces) == 1
    assert QualityGate(ws).check_min_size(SKILL, "paper/main.tex")["size"] < 2 * 12000


def test_missing_target_does_not_crash(tmp_path):
    ws = _ws(tmp_path, "\\input{nope_chapter}\n\\input{01_intro}\n")
    _write(ws / "paper" / "01_intro.tex", 300)
    assert [p.name for p in assembly_faces(ws / "paper" / "main.tex")] == ["01_intro.tex"]
