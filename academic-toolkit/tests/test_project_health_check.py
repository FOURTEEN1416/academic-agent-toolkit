"""项目健康检查回归（吸收 Observability + Drift Detection，2026-09-19 建立）。

守护四件事：
  1. 真仓整体健康（7 个组件全 PASS + 文档基线无漂移）；
  2. **漂移检测真的能抓**：合成"文档写 999 实测 1"必须报不一致；
  3. **历史横幅豁免无误伤**：项目铁律 21 要求历史口径保留原文并加横幅，
     命中横幅的行必须跳过，否则每次口径更替都会产生假报警（狼来了）；
  4. **DEGRADED 不折算为 PASS**（TOOL_GAP 原则）：检查件因缺依赖跑不起来时必须
     单独标注，不允许当成通过。
"""
import re
import subprocess

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import project_health_check as phc  # noqa: E402
import sync_baselines as sb  # noqa: E402


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


def test_collected_baseline_drift_is_detected_in_all_authoritative_docs(tmp_path, monkeypatch):
    (tmp_path / "dev-docs").mkdir()
    fixtures = {
        "README.md": "badge/tests-999_collected\n仓库根 **999 collected**",
        "AGENTS.md": "仓库根 `pytest -q` | **999 collected**",
        "pytest.ini": "# 本机完整仓 **999 collected**",
        "dev-docs/truth-index.md": "**本机完整仓** `pytest -q` = **999 collected**",
    }
    for name, text in fixtures.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    monkeypatch.setattr(phc, "REPO_ROOT", tmp_path)
    out = phc._drift({"available": True, "count": 100, "reason": ""})
    assert {m["file"] for m in out["mismatches"]} == set(fixtures)


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


def test_actual_skill_count_ignores_nested_bundled_skills() -> None:
    """计数口径守卫：`skills/*/SKILL.md` 的 **Git 默认通配符会跨越 `/`**，必须用
    `:(glob)` 单级匹配——否则捆绑在技能内的子技能会被计为顶级技能，指标虚高并
    与"clone 即所见"口径脱钩。嵌套面有两类：

    - `<技能>/modules/<模块>/SKILL.md`（paper-writing-clinical 15 件，2026-09-23 实锤：
      默认通配 265 vs `:(glob)` 真值 250，徽章曾被"同步"到虚高值）；
    - `<技能>/references/<收编参考>/.../SKILL.md`（a0e7f79 收编批带入 8 件：
      arc-stat-research 内 6 件 + nature-experiment-log / nature-statistics 各 1 件）。
    """
    proc = subprocess.run(["git", "ls-files", "--", "academic-toolkit/skills/*/SKILL.md"],
                          cwd=str(ROOT.parent), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60)
    naive = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    nested = [p for p in naive if "/modules/" in p or "/references/" in p]
    if not nested:
        pytest.skip("本仓当前无捆绑子技能/收编参考 SKILL.md，无需守护单级匹配")
    counted = phc._actual_skill_count()
    assert counted["available"], counted
    assert counted["count"] == len(naive) - len(nested), (
        f"嵌套捆绑子技能被误计为顶级技能：通配 {len(naive)} 命中含 {len(nested)} 件嵌套，"
        f"实际报 {counted['count']}，应为 {len(naive) - len(nested)}")
    assert counted["count"] > 0


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


# ---------- 基线单源同步器（sync_baselines，2026-10-23 W6 批） ----------

def _fake_repo(tmp_path: Path) -> None:
    """最小权威文档面：当前基线 999 + 一条历史横幅行（790）。

    README 用 CRLF 写入：`--accept` 必须原样保留行尾（2026-10-23 首跑实测曾把
    整文件 CRLF 折成 LF，本 fixture 钉住该回归）。
    """
    (tmp_path / "dev-docs").mkdir()
    readme = (
        "![Tests](https://img.shields.io/badge/tests-999_collected-22c55e)\n"
        "![Capabilities](https://img.shields.io/badge/capabilities-320-0ea5e9)\n"
        "![Skills](https://img.shields.io/badge/skills-262_tracked-8b5cf6)\n"
        "> **一句话**：262 个随仓技能\n"
        "# 口径一（仓库根，回归门禁口径）：999 collected（散文保持不变）\n"
        "| ✅ **测试基线** | 仓库根 **999 collected**（散文保持不变） |\n"
    )
    (tmp_path / "README.md").write_bytes(readme.replace("\n", "\r\n").encode("utf-8"))
    (tmp_path / "AGENTS.md").write_text(
        "| 仓库根 `pytest -q` | x | **999 collected** | y |\n"
        "| `academic-toolkit/` 内 `pytest -q` | 工具箱自有 tests | **999 collected** | y |\n",
        encoding="utf-8")
    (tmp_path / "pytest.ini").write_text(
        "# 本机完整仓 **999 collected**（当前基线）\n"
        "# 历史：本机完整仓 **790 passed / 0 failed**（保留作历史）\n",
        encoding="utf-8")
    (tmp_path / "dev-docs" / "truth-index.md").write_text(
        "- 测试：**本机完整仓** `pytest -q` = **999 collected**\n"
        "- 主控收口轮记录保留作历史：**本机完整仓** `pytest -q` = **790 passed / 0 failed**\n",
        encoding="utf-8")


def _fake_counts(tests: int = 1085, skills: int = 263, capabilities: int = 321) -> dict:
    return {name: {"available": True, "reason": "", "count": value}
            for name, value in (("tests", tests), ("skills", skills),
                                ("capabilities", capabilities))}


def test_sync_baselines_check_reports_every_authoritative_location(tmp_path, monkeypatch) -> None:
    _fake_repo(tmp_path)
    monkeypatch.setattr(sb, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sb, "measure", lambda skip_slow=False: _fake_counts())
    res = sb.check()
    assert not res["ok"]
    failing = {(row["file"], row["line"]) for row in res["rows"] if not row["ok"]}
    assert ("pytest.ini", 1) in failing
    assert ("README.md", 6) in failing       # 仓库根 **999 collected**
    assert ("AGENTS.md", 2) in failing       # 工具箱内口径行（2026-10-23 前的锚点盲区）
    assert ("dev-docs/truth-index.md", 1) in failing
    assert res["measured"] == {"tests": 1085, "skills": 263, "capabilities": 321}


def test_sync_baselines_accept_rewrites_only_capture_groups(tmp_path, monkeypatch) -> None:
    _fake_repo(tmp_path)
    monkeypatch.setattr(sb, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sb, "measure", lambda skip_slow=False: _fake_counts())

    dry = sb.accept(dry_run=True)
    assert dry["changes"]
    assert (tmp_path / "pytest.ini").read_text(encoding="utf-8").count("999") == 1, \
        "dry-run 不得写盘"

    sb.accept(dry_run=False)
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    pytest_ini = (tmp_path / "pytest.ini").read_text(encoding="utf-8")
    truth = (tmp_path / "dev-docs" / "truth-index.md").read_text(encoding="utf-8")
    # 捕获组数字全部换成实测值
    assert "tests-1085_collected" in readme
    assert "capabilities-321-" in readme
    assert "skills-263_tracked" in readme
    assert "263 个随仓技能" in readme
    assert "：1085 collected" in readme and "仓库根 **1085 collected**" in readme
    assert "工具箱自有 tests | **1085 collected**" in agents
    assert "本机完整仓 **1085 collected**" in pytest_ini
    assert "= **1085 collected**" in truth
    # prose 与历史横幅原样保留
    assert "散文保持不变" in readme
    assert "（当前基线）" in pytest_ini
    assert "本机完整仓 **790 passed / 0 failed**（保留作历史）" in pytest_ini
    assert "记录保留作历史：**本机完整仓** `pytest -q` = **790 passed / 0 failed**" in truth
    # 同步后 check 必须自洽
    after = sb.check()
    assert after["ok"], after["problems"]
    # 行尾必须原样保留（README fixture 为 CRLF）
    raw = (tmp_path / "README.md").read_bytes()
    assert raw.count(b"\r\n") == 6, "CRLF 行尾被改写"
    assert b"\n" not in raw.replace(b"\r\n", b""), "混入裸 LF"


def test_drift_sources_anchor_readme_install_line_and_agents_toolbox_row() -> None:
    """2026-10-23 实测：这两行曾无任何漂移锚点（regex 扫描零命中），
    sync_baselines --accept 因此传播不到——本用例钉住锚点覆盖。"""
    readme = (ROOT.parent / "README.md").read_text(encoding="utf-8")
    agents = (ROOT.parent / "AGENTS.md").read_text(encoding="utf-8")
    readme_targets = [ln for ln in readme.splitlines() if "回归门禁口径" in ln]
    agents_targets = [ln for ln in agents.splitlines() if "工具箱自有 tests" in ln]
    assert readme_targets and agents_targets

    def anchored(rel: str, line: str) -> bool:
        return any(re.search(pattern, line)
                   for src, pattern, _metric in sb._sources() if src == rel)

    assert all(anchored("README.md", ln) for ln in readme_targets)
    assert all(anchored("AGENTS.md", ln) for ln in agents_targets)


def test_print_baselines_cli_emits_one_machine_readable_line() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "project_health_check.py"),
         "--print-baselines", "--skip-slow"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120)
    assert proc.returncode == 0, proc.stderr[-400:]
    assert re.fullmatch(r"tests=unknown skills=\d+ capabilities=\d+", proc.stdout.strip()), \
        proc.stdout
