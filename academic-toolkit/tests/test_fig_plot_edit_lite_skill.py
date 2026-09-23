"""fig-plot-edit-lite 契约测试（2026-09-23 收编批次）。

覆盖四类门禁：静态契约（SKILL.md/catalog 映射/disposition）、列角色分类、
渲染 happy path（产物三件+verify-report）、门禁负面（哈希冻结/结构角色/未确认列/配色合同）。
渲染用 matplotlib Agg，rcParams 污染由 rc_context 隔离，不影响套件其他测试。
"""

import importlib.util
import json
import shutil
from pathlib import Path

import matplotlib
import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO / "skills" / "fig-plot-edit-lite"
SCRIPT = SKILL_DIR / "scripts" / "plot_lite.py"
EXAMPLE = SKILL_DIR / "examples" / "line_error_demo.csv"

CONFIRM_ROLES = {
    "时间 (h)": "x_axis",
    "对照组": "main_evidence",
    "对照组_SD": "error_of:对照组",
    "处理组": "main_evidence",
    "处理组_SEM": "error_of:处理组",
}


def _load_module():
    spec = importlib.util.spec_from_file_location("plot_lite_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lite():
    return _load_module()


def _make_confirm(mod, csv_path, **overrides):
    confirm = {
        "source_sha256": mod.sha256_file(Path(csv_path)),
        "intent": "契约测试",
        "user_confirmed": {"by": "pytest"},
        "column_roles": dict(CONFIRM_ROLES),
        "chart": "line",
        "palette_id": "blue_coral",
        "y_label": "响应值 (a.u.)",
        "rendered_at": "pytest",
    }
    confirm.update(overrides)
    return confirm


def test_skill_files_and_catalog_mapping():
    catalog = json.loads((REPO.parent / "capabilities" / "catalog.json").read_text(encoding="utf-8"))
    entry = next(
        e
        for items in catalog.values()
        for e in items
        if isinstance(e, dict) and e.get("capability_id") == "fig-plot-edit-lite"
    )
    assert entry["domain"] == "figures_and_document_production"
    assert entry["disposition"] == "routed"
    assert "fig-plot-edit-lite" in entry["associated_skills"]
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert 'name: fig-plot-edit-lite' in text
    assert (SKILL_DIR / "examples" / "line_error_demo.csv").exists()


def test_classify_columns_roles(lite):
    import pandas as pd

    df = pd.read_csv(EXAMPLE)
    roles = lite.classify_columns(df)
    assert roles == {
        "时间 (h)": "x_axis",
        "对照组": "uncertain",
        "对照组_SD": "error_of:对照组",
        "处理组": "uncertain",
        "处理组_SEM": "error_of:处理组",
    }


def test_render_happy_path_outputs_and_report(lite, tmp_path):
    work_csv = tmp_path / "demo.csv"
    shutil.copy(EXAMPLE, work_csv)
    confirm = _make_confirm(lite, work_csv)
    with matplotlib.rc_context():
        report = lite.render(work_csv, confirm)
    assert report["success"] is True
    assert all(report["checks"].values())
    assert set(report["outputs"]) == {"png", "pdf", "svg"}
    for out in report["outputs"].values():
        assert Path(out).stat().st_size > 0
    assert (work_csv.parent / "demo_lite_pytest" / "verify-report.json").exists()


def test_gates_reject_tampering(lite, tmp_path):
    work_csv = tmp_path / "demo.csv"
    shutil.copy(EXAMPLE, work_csv)
    with pytest.raises(SystemExit, match="源文件已变化"):
        lite.render(work_csv, _make_confirm(lite, work_csv, source_sha256="0" * 64))
    tampered_roles = dict(CONFIRM_ROLES)
    tampered_roles["时间 (h)"] = "main_evidence"
    with pytest.raises(SystemExit, match="角色被篡改"):
        lite.render(work_csv, _make_confirm(lite, work_csv, column_roles=tampered_roles))
    no_user = _make_confirm(lite, work_csv)
    del no_user["user_confirmed"]
    with pytest.raises(SystemExit, match="user_confirmed"):
        lite.render(work_csv, no_user)
    still_uncertain = dict(CONFIRM_ROLES)
    still_uncertain["处理组"] = "uncertain"
    with pytest.raises(SystemExit, match="未确认状态"):
        lite.render(work_csv, _make_confirm(lite, work_csv, column_roles=still_uncertain))
    with pytest.raises(SystemExit, match="配色"):
        lite.render(work_csv, _make_confirm(lite, work_csv, chart="radar"))
