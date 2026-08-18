import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = REPO_ROOT / "benchmarks" / "cumcm_public"
PRIVATE_DIR = REPO_ROOT / "benchmarks" / "cumcm_private"


def _problems():
    meta = json.loads((PUBLIC_DIR / "META.json").read_text(encoding="utf-8"))
    return meta["problems"]


def test_public_benchmark_present():
    assert PUBLIC_DIR.exists(), f"公开基准集缺失: {PUBLIC_DIR}"
    assert (PUBLIC_DIR / "META.json").exists()
    assert (PUBLIC_DIR / "README.md").exists()


@pytest.mark.parametrize("pid", [p["id"] for p in _problems()])
def test_problem_structure(pid):
    d = PUBLIC_DIR / pid
    for fn in ("problem.md", "delivery_contract.md", "scoring_rubric.md"):
        assert (d / fn).exists(), f"{pid} 缺 {fn}"
    assert (d / "baseline" / "expected_outputs.md").exists(), f"{pid} 缺基线"
    assert (d / "data").is_dir(), f"{pid} 缺 data/"


@pytest.mark.parametrize("pid", [p["id"] for p in _problems()])
def test_problem_data_parses(pid):
    d = PUBLIC_DIR / pid / "data"
    if pid == "P01":
        import csv
        for fn in ("candidates.csv", "demands.csv", "cost_matrix.csv"):
            with open(d / fn, encoding="utf-8") as f:
                rows = list(csv.reader(f))
            assert len(rows) >= 2, f"{pid}/{fn} 数据为空"
    elif pid == "P02":
        params = json.loads((d / "params.json").read_text(encoding="utf-8"))
        assert {"S0", "I0", "beta", "gamma", "N"} <= set(params)
    elif pid == "P03":
        import csv
        with open(d / "indicators.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) >= 5, f"{pid} 省份样本过少"


def test_private_benchmark_pointer():
    """私有基准指向真实演练工作区 (design §7 私有层)；不公开题面。"""
    assert PRIVATE_DIR.exists(), f"私有基准指针缺失: {PRIVATE_DIR}"
    readme = (PRIVATE_DIR / "README.md").read_text(encoding="utf-8")
    assert "cumcm-2026-practice" in readme
    practice = REPO_ROOT / "workspaces" / "cumcm-2026-practice"
    assert (practice / "AUDIT_REPORT.json").exists(), "私有基准真实演练产物缺失"
    assert (practice / "REVIEW_EXECUTION_EVIDENCE.json").exists(), "私有基准审查证据缺失"


CAPABILITY_LEVEL_CAPS = [
    "comp-prob-analysis", "comp-literature", "comp-modeling",
    "comp-code", "comp-paper-zh", "comp-review", "comp-final-audit",
]


@pytest.mark.parametrize("cap", CAPABILITY_LEVEL_CAPS)
def test_capability_level_benchmark_present(cap):
    """能力级基准完整性：fixtures + contract.json + evaluate.py + README.md 齐全。"""
    d = PUBLIC_DIR / "_capability_level" / cap
    assert d.is_dir(), f"能力级基准缺失: {cap}"
    for fn in ("contract.json", "evaluate.py", "README.md"):
        assert (d / fn).exists(), f"{cap} 缺 {fn}"
    assert (d / "fixtures").is_dir(), f"{cap} 缺 fixtures/"


@pytest.mark.parametrize("cap", CAPABILITY_LEVEL_CAPS)
def test_capability_level_evaluate_rejects_empty(cap):
    """能力级 evaluate.py 对空工作区必须拒绝（exit 1）——验收脚本本身有效。"""
    import subprocess
    import sys
    import tempfile
    ev = PUBLIC_DIR / "_capability_level" / cap / "evaluate.py"
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(
            [sys.executable, str(ev), td], capture_output=True, text=True, timeout=60
        )
    assert r.returncode == 1, f"{cap} 空工作区应 exit 1，实际 {r.returncode}"


def test_four_class_metrics_report():
    """四类指标报告骨架：输出初值结构（B4 专家校准前占位）。

    当前仅校验结构存在与可计算性；具体门槛由 B4 校准后回填计划 §3。
    """
    report = {
        "capability": "comp_problem_analysis",
        "benchmark": "cumcm_public",
        "quality": {"expert_rubric_score": None, "baseline_compare": "pending(B4)"},
        "reliability": {"e2e_pass": None, "n_runs": 0},
        "efficiency": {"wall_min": None, "tool_calls": None},
        "cost": {"external_calls": None, "local_resources": "CPU-only"},
    }
    # 结构完整性断言（保证后续验收可写入）
    for k in ("quality", "reliability", "efficiency", "cost"):
        assert k in report
    assert report["cost"]["local_resources"] == "CPU-only"


def test_private_benchmark_metrics_available():
    """B3 增强：私有基准（真实演练工作区）应产出可消费的四类指标数据。"""
    practice = REPO_ROOT / "workspaces" / "cumcm-2026-practice"
    c5 = practice / "C5_METRICS.json"
    assert c5.is_file(), "私有基准缺 C5_METRICS.json（四类指标记录）"
    metrics = json.loads(c5.read_text(encoding="utf-8"))
    # 四类维度齐全
    for k in ("quality", "reliability", "efficiency", "cost"):
        assert k in metrics, f"C5_METRICS 缺 {k} 维度"
    # 可靠性：14/14 步完成
    assert metrics["reliability"]["steps_total"] >= 14, "演练步骤数不足"
    assert metrics["reliability"]["steps_completed"] == metrics["reliability"]["steps_total"], "演练未全部完成"
    # 质量：关键指标有值
    assert metrics["quality"]["p1_accuracy"] > 0, "P1 准确率缺失"
    assert metrics["quality"]["p4_snr_gain"] > 0, "P4 SNR 增益缺失"
    # 成本：外部 API 记录
    assert isinstance(metrics["cost"]["external_apis"], list), "外部 API 记录格式错误"


def test_private_benchmark_2025b_registered():
    """B2 增强：私有基准应登记真实高难题面（2025 国赛 B 题）。"""
    readme = (PRIVATE_DIR / "README.md").read_text(encoding="utf-8")
    assert "2025B_problem.md" in readme, "私有基准 README 未指向 2025B 题面登记"
    pb = PRIVATE_DIR / "2025B_problem.md"
    assert pb.is_file(), "私有基准缺 2025B_problem.md"
    text = pb.read_text(encoding="utf-8")
    assert "法医物证多人身份鉴定" in text, "2025B 题面登记缺题名"
    assert "验收基线" in text, "2025B 题面登记缺验收基线"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
