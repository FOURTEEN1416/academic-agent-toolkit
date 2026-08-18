"""M4 修复测试：tex 回退应估算页数而非 section 计数（与 PDF 页数门禁语义一致）。

背景（COMP_REVIEW.md M4 + LESSONS）：check_paper_pages 的 tex 回退用 `sections >= 3` 判定
"至少 3 个 section"——这与页数上限门禁（max_pages）语义无关：一篇 2 页但有 5 个 section
的论文会被放行，一篇 40 页只有 2 个 section 的论文会被误拒。
修复：tex 回退改为按内容量估算页数（每页约 3500 字符），与 max_pages 比较。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.quality_gates import QualityGate


def _write_tex(tmp_path, content):
    paper = tmp_path / "paper"
    paper.mkdir(parents=True, exist_ok=True)
    (paper / "main.tex").write_text(content, encoding="utf-8")


def test_tex_fallback_estimates_pages_for_short_paper(tmp_path):
    """短论文（约 1 页内容量）应估算为 ~1 页，CUMCM 30 页上限下放行。"""
    # 约 3000 字符 ≈ 1 页
    content = "\\section{问题重述}\n" + ("中文正文内容占位。" * 400) + "\n"
    _write_tex(tmp_path, content)
    result = QualityGate(tmp_path).check_paper_pages("comp_cumcm")
    assert result["ok"] is True, f"短论文应放行: {result}"
    assert "estimated_pages" in result, f"应返回 estimated_pages: {result}"
    assert result["estimated_pages"] <= 30


def test_tex_fallback_rejects_very_long_paper(tmp_path):
    """超长 tex（估算 > 30 页）应被拒绝——section 计数无法发现此类问题。"""
    # 每 section 内容量巨大：200 个 section × 每 section 600 字符 ≈ 120000 字符 ≈ 34 页
    content = "\n".join(
        f"\\section{{{i}}}" + ("中文正文内容占位。" * 100) for i in range(200)
    )
    _write_tex(tmp_path, content)
    result = QualityGate(tmp_path).check_paper_pages("comp_cumcm")
    assert result["ok"] is False, f"超长论文应被拒绝: {result}"
    assert result["estimated_pages"] > 30


def test_tex_fallback_uses_estimated_pages_not_section_count(tmp_path):
    """M4 核心：判定依据是估算页数而非 section 数——section 数不决定页数。"""
    # 1 个 section 但内容量 200000 字符（超长，约 58 页）
    content = "\\section{唯一章节}\n" + ("中文正文内容占位。" * 25000) + "\n"
    _write_tex(tmp_path, content)
    result = QualityGate(tmp_path).check_paper_pages("comp_cumcm")
    # 旧逻辑 sections=1 < 3 → 拒绝；新逻辑估算页数 > 30 → 拒绝（但原因不同）
    assert result["ok"] is False
    assert result["estimated_pages"] > 30
    assert "section" not in result.get("reason", ""), f"不应再用 section 计数判定: {result}"