"""D3 quick_gates 门禁前移轻量编排器回归测试。

覆盖：输入缺失自动 SKIP（早跑阶段产物未齐是常态）；真实 FAIL 传播为
整体 ok=false 与退出码 1；--skip 参数生效；页数检查在无 pypdf/PDF 时
降级 SKIP 不炸。真实闸件联动（字号/泄漏）走子进程，不 mock 内部逻辑。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "skills" / "_utils"
sys.path.insert(0, str(UTILS))

import quick_gates  # noqa: E402


QUICK_GATES = UTILS / "quick_gates.py"


def _run(tmp_path, *extra):
    proc = subprocess.run(
        [sys.executable, str(QUICK_GATES), "--workspace", str(tmp_path), *extra],
        capture_output=True, text=True, timeout=600,
    )
    return proc


def test_all_skip_when_workspace_empty(tmp_path):
    """空工作区（无 paper/figures/code）→ 三类全 SKIP，ok=true 退出码 0。"""
    proc = _run(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["ok"] is True
    statuses = {c["name"]: c["status"] for c in report["checks"]}
    assert statuses == {"page_count": "SKIP", "figure_font": "SKIP", "leakage": "SKIP"}


def test_leakage_fail_propagates_to_exit_code(tmp_path):
    """结果 JSON 含 ≥0.99 指标且无去泄漏举证 → leakage FAIL → ok=false 退出码 1。"""
    code = tmp_path / "code"
    code.mkdir()
    (code / "metrics.json").write_text(
        json.dumps({"accuracy": 0.995, "f1": 0.999}, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "RESULTS.md").write_text("# 结果\naccuracy 0.995，直接对全部样本计算，口径从简。\n",
                                         encoding="utf-8")
    proc = _run(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    by_name = {c["name"]: c for c in report["checks"]}
    assert by_name["leakage"]["status"] == "FAIL"
    assert "泄漏" in by_name["leakage"]["detail"] or "0.99" in by_name["leakage"]["detail"]


def test_skip_flag_excludes_check(tmp_path):
    """--skip leakage → 泄漏检查不出现在报告（泄漏 FAIL 不再影响退出码）。"""
    code = tmp_path / "code"
    code.mkdir()
    (code / "metrics.json").write_text(json.dumps({"accuracy": 0.995}), encoding="utf-8")
    (tmp_path / "RESULTS.md").write_text("# 结果\n无举证。\n", encoding="utf-8")
    proc = _run(tmp_path, "--skip", "leakage")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert {c["name"] for c in report["checks"]} == {"page_count", "figure_font"}


def test_page_check_missing_pdf_skips(tmp_path):
    """--paper-pdf 指向不存在文件 → SKIP（不算失败）。"""
    status, detail = quick_gates._page_check(tmp_path, tmp_path / "paper" / "main.pdf", 30)
    assert status == "SKIP"
    assert "未找到" in detail or "pypdf" in detail


def test_page_check_bad_pdf_errors_without_raising(tmp_path):
    """损坏 PDF → ERROR 状态（编排器不炸，退出码不受影响）。"""
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.4 not really a pdf")
    status, detail = quick_gates._page_check(tmp_path, bad, 30)
    assert status == "ERROR"
    assert "PDF 解析失败" in detail


# ── 引擎挂载：StepAction.quick_gates 透传与指令下发 ─────────────────────

def test_step_action_quick_gates_instruction_line():
    """quick_gates=True 的 StepAction，instructions 必含轻检命令提示行。"""
    from engine.opencode_bridge import StepAction
    action = StepAction(
        workflow_id="w", step_id="s", position=4, skill_name="paper-figure",
        display_name="图表生成", workspace=Path("D:/ws"), skill_path=Path("D:/ws/skill.md"),
        output_files=["figures/latex_includes.tex"], primary_output="figures/",
        has_checkpoint=False, checkpoint_type=None, quick_gates=True)
    text = action.execution_instructions()
    assert "quick_gates.py" in text
    assert "回报 complete 前必跑" in text


def test_real_template_flags_quick_gates_steps(tmp_path):
    """comp_cumcm 模板仅 paper-figure / comp-paper-zh 两步声明 quick_gates=true。"""
    from engine.workflow_runner import WorkflowRunner
    from engine.workflow_store import WorkflowStore
    catalog = json.loads(
        (ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    store = WorkflowStore(tmp_path / "db.sqlite")
    runner = WorkflowRunner(store, catalog, tmp_path / "skills")
    wf = runner.start("comp_cumcm", tmp_path / "ws", {})
    rows = store._connection.execute(
        "SELECT name, metadata FROM workflow_steps WHERE workflow_id = ?",
        (wf.id,)).fetchall()
    flagged = {r["name"] for r in rows if json.loads(r["metadata"]).get("quick_gates")}
    assert flagged == {"paper-figure", "comp-paper-zh"}
