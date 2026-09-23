"""项目健康检查回归（吸收 Observability + Drift Detection，2026-09-19 建立）。

守护四件事：
  1. 真仓整体健康（7 个组件全 PASS + 文档基线无漂移）；
  2. **漂移检测真的能抓**：合成"文档写 999 实测 1"必须报不一致；
  3. **历史横幅豁免无误伤**：项目铁律 21 要求历史口径保留原文并加横幅，
     命中横幅的行必须跳过，否则每次口径更替都会产生假报警（狼来了）；
  4. **DEGRADED 不折算为 PASS**（TOOL_GAP 原则）：检查件因缺依赖跑不起来时必须
     单独标注，不允许当成通过。
"""
import subprocess

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import project_health_check as phc  # noqa: E402


# 真仓体检含 pytest 收集（~5s）+ 7 个子进程，整个文件只跑一次并缓存
_REAL: dict = {}


def _real() -> dict:
    if "res" not in _REAL:
        _REAL["res"] = phc.run()
    return _REAL["res"]


# ---------- 真仓机检 ----------

def test_real_repo_all_components_pass() -> None:
    res = _real()
    failed = [c["name"] for c in res["components"] if c["status"] != "PASS"]
    assert failed == [], f"组件未通过: {failed}"


def test_real_repo_components_cover_expected_set() -> None:
    """组件清单必须覆盖既有检查件（新增检查件时应同步登记，防"检查件没人跑"）。"""
    res = _real()
    names = {c["name"] for c in res["components"]}
    assert {"provenance", "skill_library", "asset_utilization", "contest_lessons",
            "skill_triggers", "context_budget", "palette_registry"} <= names


def test_real_repo_drift_clean() -> None:
    res = _real()
    assert res["drift"]["available"], res["drift"]["reason"]
    assert res["drift"]["mismatches"] == [], res["drift"]["mismatches"]


def test_real_repo_pytest_count_is_reported() -> None:
    res = _real()
    assert res["pytest"]["available"]
    assert res["pytest"]["count"] >= 527


# ---------- 漂移检测逻辑（正反例） ----------

def test_drift_detects_mismatch(tmp_path: Path, monkeypatch) -> None:
    """文档写 999 而实测 1 → 必须报不一致（漂移检测不是装饰）。"""
    (tmp_path / "README.md").write_text("![Tests](badge/tests-999_passing)", encoding="utf-8")
    monkeypatch.setattr(phc, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(phc, "DRIFT_SOURCES", (("README.md", r"badge/tests-(\d+)_passing"),))
    out = phc._drift({"available": True, "count": 1, "reason": ""})
    assert len(out["mismatches"]) == 1
    assert out["mismatches"][0]["documented"] == 999
    assert out["mismatches"][0]["line"] == 1


def test_drift_passes_on_agreement(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("badge/tests-527_passing", encoding="utf-8")
    monkeypatch.setattr(phc, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(phc, "DRIFT_SOURCES", (("README.md", r"badge/tests-(\d+)_passing"),))
    out = phc._drift({"available": True, "count": 527, "reason": ""})
    assert out["mismatches"] == []


def test_drift_exempts_historical_banner_lines(tmp_path: Path, monkeypatch) -> None:
    """带历史横幅的行必须豁免（铁律 21：历史记录保留原文）。"""
    (tmp_path / "truth.md").write_text(
        "- 当前基线：**463 passed / 0 failed**（保留作历史，见下方横幅）\n", encoding="utf-8")
    monkeypatch.setattr(phc, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(phc, "DRIFT_SOURCES",
                        (("truth.md", r"\*\*(\d+) passed / 0 failed\*\*"),))
    out = phc._drift({"available": True, "count": 527, "reason": ""})
    assert out["mismatches"] == [], out["mismatches"]
    assert out["exempted"] == 1


def test_drift_skips_when_actual_unavailable(tmp_path: Path) -> None:
    """实测不可得时如实标注 unavailable，不产生假漂移（TOOL_GAP）。"""
    out = phc._drift({"available": False, "reason": "collect-only 失败", "count": None})
    assert out["available"] is False
    assert out["mismatches"] == []
    assert "collect-only" in out["reason"]


# ---------- 多指标漂移（2026-09-23 止血批 C10：badge 技能/能力数机检） ----------

def test_drift_strict_metric_catches_off_by_one(tmp_path: Path, monkeypatch) -> None:
    """skills 指标严格等值：差 1（275 vs 276）必须报——2% 容差抓不住这类真漂移
    （2026-09-23 实锤：badge 275 在 fig-plot-edit-lite 入库后立刻过期）。"""
    (tmp_path / "README.md").write_text("badge/skills-275_tracked", encoding="utf-8")
    monkeypatch.setattr(phc, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(phc, "DRIFT_SOURCES",
                        (("README.md", r"badge/skills-(\d+)_tracked", "skills"),))
    out = phc._drift({"skills": {"available": True, "reason": "", "count": 276}})
    assert len(out["mismatches"]) == 1, out["mismatches"]
    assert out["mismatches"][0]["metric"] == "skills"
    assert out["mismatches"][0]["documented"] == 275
    assert out["mismatches"][0]["actual"] == 276


def test_drift_multi_metric_agrees_across_sources(tmp_path: Path, monkeypatch) -> None:
    """三元组 DRIFT_SOURCES + 多指标 actual：各指标各自比对，全对则零 mismatch。"""
    (tmp_path / "README.md").write_text(
        "badge/tests-789_passing badge/skills-276_tracked badge/capabilities-314-",
        encoding="utf-8")
    monkeypatch.setattr(phc, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(phc, "DRIFT_SOURCES", (
        ("README.md", r"badge/tests-(\d+)_passing", "tests"),
        ("README.md", r"badge/skills-(\d+)_tracked", "skills"),
        ("README.md", r"badge/capabilities-(\d+)-", "capabilities"),
    ))
    out = phc._drift({
        "tests": {"available": True, "reason": "", "count": 791},
        "skills": {"available": True, "reason": "", "count": 276},
        "capabilities": {"available": True, "reason": "", "count": 314},
    })
    assert out["mismatches"] == [], out["mismatches"]
    assert out["actual"] == {"tests": 791, "skills": 276, "capabilities": 314}


# ---------- TOOL_GAP：DEGRADED 不折算为 PASS ----------

def test_missing_dependency_is_degraded_not_pass(tmp_path: Path) -> None:
    """检查件因缺依赖跑不起来 → DEGRADED（不是 PASS，也不是把它当 FAIL 掩盖原因）。"""
    script = tmp_path / "broken.py"
    script.write_text("import definitely_not_installed_module_xyz\n", encoding="utf-8")
    comp = phc._run_component("broken", [str(script)])
    assert comp["status"] == "DEGRADED", comp
    assert "缺依赖" in comp["detail"]


def test_failing_check_is_fail_not_degraded(tmp_path: Path) -> None:
    """真实失败（非缺依赖）必须是 FAIL——不能全部降级成 DEGRADED 来逃避拦截。"""
    script = tmp_path / "fails.py"
    script.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    comp = phc._run_component("fails", [str(script)])
    assert comp["status"] == "FAIL", comp


def test_timeout_is_degraded(tmp_path: Path) -> None:
    script = tmp_path / "slow.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    comp = phc._run_component("slow", [str(script)], timeout=1)
    assert comp["status"] == "DEGRADED"
    assert "超时" in comp["detail"]


# ---------- CLI 契约 ----------

@pytest.fixture(scope="module")
def cli_health_proc() -> subprocess.CompletedProcess:
    """B3-8（2026-09-22）：两个 CLI 用例此前各起一个全量检查子进程（×2 ≈ 20s），
    合并为一次 `--strict --skip-slow --json` 运行共享结果（strict 管 rc、json 管输出，
    两个用例的断言面合并不减）。CI 独立 step 的双保险不受影响。"""
    return subprocess.run([sys.executable, str(ROOT / "tools" / "project_health_check.py"),
                           "--strict", "--skip-slow", "--json"], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)


def test_cli_skip_slow_runs_fast(cli_health_proc) -> None:
    # rc 的 strict 判定归 test_cli_strict 专属（共享进程带 --strict，组件 FAIL 时 rc=1
    # 是如实反映）；本用例验证 --skip-slow 快速模式可完整产出 JSON 报告。
    assert cli_health_proc.returncode in (0, 1)
    assert '"drift"' in cli_health_proc.stdout


def test_cli_strict_returns_zero_on_healthy_repo(cli_health_proc) -> None:
    assert cli_health_proc.returncode == 0, cli_health_proc.stdout[-500:]
