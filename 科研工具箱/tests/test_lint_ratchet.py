# -*- coding: utf-8 -*-
"""lint_ratchet 棘轮测试（2026-09-20 建立，随工具入库）。

覆盖：①evaluate 纯函数棘轮语义（等量过/超量拦/降量提示收紧）；②逐规则
回退检测（总量持平但规则迁移也算回退）；③版本漂移警告；④基线文件健康
（schema/total/by_rule 自洽 + ruff 版本与 requirements-dev 锁定一致）；
⑤整仓棘轮检查实跑通过。
"""
import json
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import lint_ratchet  # noqa: E402

BASE = {"schema": 1, "ruff_version": "0.16.8", "total": 8,
        "by_rule": {"F841": 8}}


def _findings(codes):
    return [{"code": c} for c in codes]


def test_equal_count_passes():
    v = lint_ratchet.evaluate({"findings": _findings(["F841"] * 8),
                               "ruff_version": "0.16.8"}, BASE)
    assert v["ok"] and not v["tighten_hint"]


def test_increase_blocks():
    v = lint_ratchet.evaluate({"findings": _findings(["F841"] * 9),
                               "ruff_version": "0.16.8"}, BASE)
    assert not v["ok"] and v["regressions"] == {"F841": 1}


def test_decrease_hints_tighten():
    v = lint_ratchet.evaluate({"findings": _findings(["F841"] * 5),
                               "ruff_version": "0.16.8"}, BASE)
    assert v["ok"] and v["tighten_hint"]


def test_rule_migration_counts_as_regression():
    """总量持平但新规则出现 = 回退（不能拿"删 A 规则存量"抵"新增 B 规则"）。"""
    v = lint_ratchet.evaluate({"findings": _findings(["F841"] * 7 + ["F401"]),
                               "ruff_version": "0.16.8"}, BASE)
    assert not v["ok"] and "F401" in v["regressions"]


def test_version_drift_warns():
    v = lint_ratchet.evaluate({"findings": _findings(["F841"] * 8),
                               "ruff_version": "0.17.0"}, BASE)
    assert v["ok"] and "版本漂移" in v["version_warning"]


def test_baseline_file_healthy():
    data = json.loads((lint_ratchet.BASELINE_PATH).read_text(encoding="utf-8"))
    assert data["schema"] == lint_ratchet.BASELINE_SCHEMA
    assert data["total"] == sum(data["by_rule"].values()), "基线自洽性"
    assert data["select"] == lint_ratchet.SELECT
    # 基线锁定的 ruff 版本必须与 requirements-dev.txt 声明一致
    req = (lint_ratchet.REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    m = re.search(r"ruff==([0-9.]+)", req)
    assert m, "requirements-dev.txt 须锁定 ruff==<版本>（版本漂移会动摇计数可比性）"
    assert m.group(1) == data["ruff_version"], \
        f"基线 ruff {data['ruff_version']} ≠ requirements-dev 锁定 {m.group(1)}"


def test_repo_ratchet_check_passes():
    import subprocess
    proc = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "lint_ratchet.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300)
    assert proc.returncode == 0, f"整仓 lint 棘轮未过:\n{proc.stdout[-800:]}"
