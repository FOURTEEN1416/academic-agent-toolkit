# -*- coding: utf-8 -*-
"""check_duplicate_assets 台账棘轮测试（2026-09-20 建立，随工具入库）。

覆盖：①evaluate 纯函数（未登记组拦截 / 已消解组提示 / 登记匹配放行）；
②find_duplicate_groups 的阈值与排除语义（.pyc、releases/、<4KB 不入组）；
③台账健康（无 TODO 理由、threshold 与工具常量一致）；④整仓 strict 通过。
"""
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import check_duplicate_assets as cda  # noqa: E402

REG = [{"paths": ["a.txt", "b.txt"], "reason": "有意"}]


def test_unregistered_group_blocks():
    groups = [{"paths": ["new/x.png", "new/y.png"], "size": 100, "md5": "m",
               "wasted_bytes": 100}]
    v = cda.evaluate(groups, REG)
    assert not v["ok"] and len(v["unregistered"]) == 1


def test_registered_group_passes():
    groups = [{"paths": ["a.txt", "b.txt"], "size": 100, "md5": "m",
               "wasted_bytes": 100}]
    v = cda.evaluate(groups, REG)
    assert v["ok"] and v["registered_ok"] == 1 and not v["resolved"]


def test_resolved_group_reported_not_blocked():
    """已消解 = 方向正确（重复消失），提示移除但不拦截。"""
    v = cda.evaluate([], REG)
    assert v["ok"] and len(v["resolved"]) == 1


def test_threshold_and_exclusions(tmp_path):
    (tmp_path / "small_a.txt").write_bytes(b"x" * 100)
    (tmp_path / "small_b.txt").write_bytes(b"x" * 100)       # <4KB 不入组
    (tmp_path / "big_a.bin").write_bytes(b"y" * 5000)
    (tmp_path / "big_b.bin").write_bytes(b"y" * 5000)         # ≥4KB 入组
    groups = cda.find_duplicate_groups([str(p) for p in tmp_path.iterdir()])
    assert len(groups) == 1
    assert groups[0]["size"] == 5000 and groups[0]["wasted_bytes"] == 5000

    pyc = ["x.pyc", "y.pyc", "releases/z/big_a.txt", "releases/z/big_b.txt"]
    assert cda.find_duplicate_groups(pyc) == [], "pyc/releases 排除失效"


def test_registry_has_no_todo_reasons():
    data = json.loads(cda.REGISTRY_PATH.read_text(encoding="utf-8"))
    assert data["threshold_bytes"] == cda.THRESHOLD_BYTES
    for g in data["groups"]:
        assert g.get("reason") and "TODO" not in g["reason"], \
            f"台账存在未定性条目: {g['paths'][:2]}"
        assert len(g["paths"]) >= 2 and g["paths"] == sorted(g["paths"])


def test_repo_strict_passes():
    import subprocess
    proc = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "check_duplicate_assets.py"), "--strict"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600)
    assert proc.returncode == 0, f"整仓重复资产守护未过:\n{proc.stdout[-800:]}"
