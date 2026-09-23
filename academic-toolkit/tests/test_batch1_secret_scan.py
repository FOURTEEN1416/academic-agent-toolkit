# -*- coding: utf-8 -*-
"""B1-5 升档回归：secret_scan 家目录形态扩展 + 文档命中由 WARN 升 FAIL。

升档内容：HOME_PATH 由 `X:\\Users\\<name>` 扩展为 `X:[\\/]Users\\<name>` 与
`X:[\\/]Desktop\\<user>`（正反斜杠两族）；run() 分档中 home-path 归入
blocked（FAIL 级）。豁免走 data/secret_scan_allowlist.json 逐条 sha256 台账。

（任务包 B1-5 原文写"test_secret_scan.py 加升档用例"，按全局纪律 §〇-3
白名单制落位于本 test_batch1_ 前缀文件。）
"""
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import secret_scan  # noqa: E402


def test_forward_slash_home_path_detected():
    """正斜杠形态 C:/Users/<name> 必须命中（B1-4 修复的那类泄漏再进不来）。"""
    found = secret_scan.scan_text("从 `C:/Users/FOUR/.workbuddy/skills/` 复制入库",
                                  "x.md", False)
    assert any(f["kind"] == "home-path" for f in found)


def test_desktop_user_path_detected():
    """Desktop/<user> 形态必须命中。"""
    found = secret_scan.scan_text(r"工程在 D:\Desktop\workbuddy_space\cumcm2026A",
                                  "x.md", False)
    assert any(f["kind"] == "home-path" for f in found)


def test_dot_and_chinese_segments_not_flagged():
    """纯点示例段与中文项目目录段不得误伤。"""
    assert not [f for f in secret_scan.scan_text(
        "不得写入 `C:\\Users\\...` 示例", "x.md", False) if f["kind"] == "home-path"]
    assert not [f for f in secret_scan.scan_text(
        "本仓检出在 D:/Desktop/学术工作流", "x.md", False)
        if f["kind"] == "home-path"]


def test_run_classifies_home_path_as_fail(monkeypatch, tmp_path):
    """run() 分档：home-path 归 blocked（FAIL），--strict 语义下 ok=False。"""
    (tmp_path / "leak.md").write_text("见 C:/Users/SOMEONE/notes\n", encoding="utf-8")
    monkeypatch.setattr(secret_scan, "_tracked_files", lambda: ["leak.md"])
    monkeypatch.setattr(secret_scan, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(secret_scan, "_load_allowlist", lambda: [])
    res = secret_scan.run()
    assert res["ok"] is False, "home-path 未按 FAIL 级分档（升档失效）"
    assert any(f["kind"] == "home-path" for f in res["blocked"])
    assert res["warned"] == []


def test_run_allowlist_still_suppresses(monkeypatch, tmp_path):
    """升档不破坏台账豁免：命中行按 (file, line_sha256) 锚定后不阻断。"""
    line = "见 C:/Users/SOMEONE/notes\n"
    (tmp_path / "leak.md").write_text(line, encoding="utf-8")
    f0 = secret_scan.scan_text(line, "leak.md", False)[0]
    allow = [{"file": "leak.md", "line_sha256": f0["line_sha256"], "reason": "测试豁免"}]
    monkeypatch.setattr(secret_scan, "_tracked_files", lambda: ["leak.md"])
    monkeypatch.setattr(secret_scan, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(secret_scan, "_load_allowlist", lambda: allow)
    res = secret_scan.run()
    assert res["ok"] is True
    assert res["allowlisted"] >= 1
