# -*- coding: utf-8 -*-
"""B1-2 回归：anti_ai_detector 基线加载链接通 + 退出码契约。

修复前：main() 的 `baseline = None if args.no_baseline else None` 是双重死代码
（--no-baseline 与默认路径完全同义，基线永远不显式加载）；__init__ 的
`baseline or _load_baseline()` 让显式空基线 {} 也被自动加载覆盖；
main() 返回值被 `main()` 裸调用丢弃，无退出码语义。
"""
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import anti_ai_detector  # noqa: E402
from anti_ai_detector import AntiAIDetector, DetectionResult  # noqa: E402


def test_baseline_loaded_when_file_exists(monkeypatch, tmp_path):
    """基线文件存在时必须被加载（tmp 基线 + monkeypatch BASELINE_PATH）。"""
    baseline = {"paper_count": 3,
                "features": {"short_sent_pct": {"min": 50, "max": 80, "mean": 60}}}
    p = tmp_path / "human_paper_baseline.json"
    p.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(anti_ai_detector, "BASELINE_PATH", str(p))
    text = "这是一段用于触发统计特征层计算的测试文本。" * 30
    det = AntiAIDetector(text)
    assert det.baseline.get("paper_count") == 3, "默认路径未加载基线文件"
    assert det._feat("short_sent_pct")["mean"] == 60


def test_no_baseline_explicitly_disables_calibration(monkeypatch, tmp_path):
    """--no-baseline 语义：显式空基线 {} 不得被自动加载覆盖。"""
    baseline = {"paper_count": 99}
    p = tmp_path / "human_paper_baseline.json"
    p.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(anti_ai_detector, "BASELINE_PATH", str(p))
    det = AntiAIDetector("测试文本。基线被显式禁用。", baseline={})
    assert det.baseline == {}, "显式空基线被 _load_baseline() 覆盖（修复前行为）"


def test_main_exit_code_contract(monkeypatch):
    """退出码契约：risk_level ∈ {high, critical} → 1；否则 0。"""
    for risk, expected in [("low", 0), ("medium", 0), ("high", 1), ("critical", 1)]:
        result = DetectionResult(overall_score=0.9 if expected else 0.1,
                                 risk_level=risk, summary="fake")
        monkeypatch.setattr(
            anti_ai_detector, "AntiAIDetector",
            lambda text, lang, baseline=None, _r=result: _FakeDetector(_r))
        rc = anti_ai_detector.main(["某输入文本"])
        assert rc == expected, f"risk_level={risk} 期望退出码 {expected}，实得 {rc}"


class _FakeDetector:
    def __init__(self, result):
        self._result = result

    def detect(self):
        return self._result


def test_main_real_run_returns_int(tmp_path):
    """真实路径烟测：main 返回 int 退出码（不再是被丢弃的 result 对象）。"""
    rc = anti_ai_detector.main(["这只是几个字的短文本。"])
    assert isinstance(rc, int) and rc in (0, 1)


def test_help_documents_exit_codes(capsys):
    """--help 必须写明退出码契约（0/1/2）。"""
    try:
        anti_ai_detector.main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    out = capsys.readouterr().out
    assert "退出码" in out and "0" in out and "1" in out
