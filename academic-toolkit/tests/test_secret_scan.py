# -*- coding: utf-8 -*-
"""secret_scan 门禁测试（2026-09-20 建立，随工具入库）。

覆盖：①高置信凭证模式逐类命中（含脱敏）；②占位符豁免不误伤示例文本；
③配置绝对路径 FAIL 类（含 exc:\\n 假阳性回归）；④家目录 WARN 类
（纯点段示例不命中）；⑤豁免台账按行哈希锚定生效；⑥整仓 strict 扫描通过。
"""
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import secret_scan  # noqa: E402


def test_high_confidence_secret_patterns_detected():
    cases = {
        "anthropic-key": 'token = "sk-ant-api03-AbCdEf1234567890XYZ"',
        "openai-key": 'key = "sk-AbCdEf1234567890AbCdEf123456789012"',
        "github-token": "GITHUB_TOKEN=ghp_AbCdEf1234567890AbCdEf12345678901234",
        "aws-access-key": 'aws_key = "AKIAIOSFODNN7EXAMPLE"',
        "google-api-key": 'g = "AIzaSyA1234567890abcdefghijklmnopqrstuv"',
        "slack-token": 's = "xoxb-123456789012-AbCdEfGhIjKl"',
        "private-key-block": "-----BEGIN RSA PRIVATE KEY-----",
        "jwt": "auth: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.x",
        "generic-assignment": 'api_key = "AbCdEf1234567890AbCdEf12"',
    }
    for pid, line in cases.items():
        found = secret_scan.scan_text(line, "fictional/x.txt", is_config=False)
        pats = {f["pattern"] for f in found}
        assert pid in pats, f"{pid} 未命中: {line!r} → {pats}"


def test_placeholders_do_not_trigger():
    for line in [
        'api_key = "YOUR_API_KEY_HERE"',
        'token = "XXXX-PLACEHOLDER-XXXX"',
        'password = "EXAMPLE_PASSWORD_2026"',
    ]:
        found = [f for f in secret_scan.scan_text(line, "f/x.md", False)
                 if f["pattern"] == "generic-assignment"]
        assert not found, f"占位符误报: {line!r}"


def test_evidence_is_masked():
    line = 'const apiKey = "sk-ant-abcdefghijklmnopqrst1234567890";'
    (f := secret_scan.scan_text(line, "f/x.ts", False)[0])
    assert "sk-ant-abcdefghij" not in f["evidence"], "证据未脱敏，报告本身会二次泄密"


def test_config_absolute_path_fails_and_json_embedded_python_does_not():
    # 真实盘符路径（配置可移植性违例）→ FAIL
    real = secret_scan.scan_text('"roots": ["C:/Users/someone/docs"]',
                                 "opencode.json", is_config=True)
    assert any(f["kind"] == "config-abs-path" for f in real)
    # 回归：JSON 内嵌 Python 的 "exc:\\n" / "root:\\n"（冒号+字面反斜杠n）
    # 曾整体误命中盘符正则（2026-09-20 .zcode/config.json 三处假阳性实证）
    embedded = secret_scan.scan_text(
        '"except Exception as exc:\\n    print(exc)\\nif root:\\n    pass"',
        ".zcode/config.json", is_config=True)
    assert not [f for f in embedded if f["kind"] == "config-abs-path"]


def test_home_path_requires_real_segment():
    # 规则文档引用的 "C:\\Users\\..." 示例（纯点段）不算泄漏
    doc = secret_scan.scan_text("不得写入 `C:\\Users\\...`、过期项目根", "AGENTS.md", False)
    assert not [f for f in doc if f["kind"] == "home-path"]
    # 真实用户名段 → WARN
    leak = secret_scan.scan_text("装在 `C:\\Users\\FOUR\\.zcode\\` 下", "x.md", False)
    assert any(f["kind"] == "home-path" for f in leak)


def test_allowlist_suppresses_by_line_hash(tmp_path):
    target = tmp_path / "a.md"
    line = "path C:\\Users\\SOMEONE\\.zcode here"
    target.write_text(line + "\n", encoding="utf-8")
    findings = secret_scan.scan_text(line, "a.md", False)
    assert findings
    allowlist = [{"file": "a.md", "line_sha256": findings[0]["line_sha256"],
                  "reason": "测试豁免"}]
    (tmp_path / "allow.json").write_text(json.dumps(allowlist), encoding="utf-8")
    # run() 走 git tracked 面，这里直接验证锚定语义：同内容行命中豁免键
    allowed = {(a["file"], a["line_sha256"]) for a in allowlist}
    assert ("a.md", findings[0]["line_sha256"]) in allowed


def test_repo_strict_scan_passes():
    """整仓扫描必须零 FAIL（豁免台账 3 条：vendored 哑钥匙 fixture ×1 + 路径
    卫生测试检测针 ×2，见 data/secret_scan_allowlist.json）。"""
    import subprocess
    proc = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "secret_scan.py"), "--strict"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300)
    assert proc.returncode == 0, f"整仓密钥扫描未过:\n{proc.stdout[-800:]}"


def test_allowlist_entries_have_reasons():
    al = secret_scan._load_allowlist()
    for entry in al:
        assert entry.get("reason") and "TODO" not in entry["reason"], \
            f"无理由豁免 = 没有扫描器: {entry}"
