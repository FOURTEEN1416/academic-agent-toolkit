#!/usr/bin/env python3
"""密钥与路径卫生扫描门禁（secret_scan，2026-09-20 建立）。

**为什么需要**：本仓是 PUBLIC 仓且曾有密钥注入面（旧 `pyc_loader` 曾注入
vision provider key——2026-09-23 换驱动后拆除、v2.0 收尾随 pyc 退役整体删除；
`.env` 本地配置、MCP 本地覆盖仍在）——但此前密钥卫生只有
gitignore 单层防护，无任何机检。根 AGENTS.md 硬性规则 6（tracked 配置与文档
不得写入本机绝对路径）也只靠人工遵守。

**上游模式（批判式吸收）**：gitleaks / TruffleHog 的"高精度正则 + CI 纵深"
思路（GitHub 官方安全实践亦建议 push protection + CI 扫描双保险）。不引入
外部二进制（本仓自包含原则），自建正则面：只收"几乎必然是凭证"的模式，
宁缺毋滥——误报泛滥的扫描器会像狼来了一样被绕过。

**两个检查类**：
  1. secret（FAIL）：tracked 文本文件中的高置信凭证模式（OpenAI/Anthropic/
     GitHub/AWS/Google/Slack/私钥/JWT/泛化赋值）+ 占位符豁免。
  2. path（FAIL）：硬性规则 6 的机检化——
     - tracked **配置文件**中出现任何 Windows 盘符绝对路径 → FAIL（配置必须可移植）；
     - tracked 文本文件中的家目录形态（`X:[\\/]Users\\<name>` 与
       `X:[\\/]Desktop\\<user>`，正反斜杠均可）→ **FAIL**（2026-09-22 B1-5 由
       WARN 升档：个人路径泄漏不是风格问题；历史叙述行经横幅豁免，
       个别误伤走 data/secret_scan_allowlist.json 逐条台账）。

**边界（TOOL_GAP 如实声明）**：仅扫 tracked 文本文件（`git ls-files`），不扫
二进制（.pyc 内嵌字符串、图片隐写不可检）、不扫 git 历史（已泄露须换钥匙+
改写历史，本工具管不住）、无熵分析（纯模式精度）。releases/ 为 dated 发布
快照（不可变历史），不在扫描面——若其中发现密钥属事件响应范畴。

用法：
  python tools/secret_scan.py             # 人读报告（WARN 只报告不拦截）
  python tools/secret_scan.py --strict    # 有 FAIL 级发现 → exit 1
  python tools/secret_scan.py --json      # 机读
  python tools/secret_scan.py --emit-allowlist  # 为当前发现生成豁免条目草稿

豁免台账：data/secret_scan_allowlist.json（逐行 sha256 锚定，防行号漂移；
每条必须给 reason——"无理由豁免"等于没有扫描器）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

TOOLBOX_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLBOX_ROOT.parent
ALLOWLIST_PATH = TOOLBOX_ROOT / "data" / "secret_scan_allowlist.json"

# 不扫描的 tracked 路径前缀（dated 快照 = 不可变历史，见模块 docstring）
EXCLUDED_PREFIXES = ("releases/",)

# 二进制/不可文本审阅的扩展名（与 tools 审查口径一致：pyc 读同名 .py 真源）
BINARY_SUFFIXES = {
    ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".tif", ".tiff", ".bmp",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".zip", ".rar", ".7z", ".gz", ".tar",
    ".xlsx", ".xls", ".docx", ".pptx", ".pdf",
    ".sqlite", ".db", ".dll", ".exe", ".jar", ".node", ".vsdx",
}

# 高置信凭证模式（吸收 gitleaks 规则面，全部要求长token压误报）
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]{0,30}PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{15,}\.eyJ[A-Za-z0-9_\-]{15,}\.")),
    # 泛化赋值：key/secret/token/password = '<20+位无空格值>'（占位符豁免见下）
    ("generic-assignment",
     re.compile(r"(?i)\b(api[_-]?key|apikey|secret|token|passwd|password)\b"
                r"[\s\"']*[:=][\s\"']*[\"']([A-Za-z0-9_\-]{20,})[\"']")),
)

# 泛化模式的占位符豁免（值里含这些片段 = 示例文本，非真钥匙）
PLACEHOLDER_MARKERS = ("YOUR", "XXXX", "PLACEHOLDER", "EXAMPLE", "CHANGEME",
                       "DUMMY", "TESTTEST", "<", ">", "${")

# 泛化模式不查超长行（minified js 的超长字符串会制造不可读误报；
# 高置信模式不受此限——真钥匙在 minified 里也是真钥匙）
GENERIC_MAX_LINE = 400

# 配置文件（硬性规则 6 的机检面：tracked 配置必须可移植，出现盘符绝对路径即 FAIL）
CONFIG_SUFFIXES = {".json", ".yml", ".yaml", ".ini", ".toml", ".cfg", ".txt"}
CONFIG_DIR_MARKERS = (".github", ".opencode", ".zcode")
CONFIG_NAME_EXACT = {"opencode.json", "pytest.ini", "requirements-dev.txt"}

# 家目录路径（B1-5 扩展）：Users/<name> 与 Desktop/<user> 两族，正反斜杠均可；
# 段内必须含字母数字（规则文档引用的 "C:\Users\..." 示例段为纯点、
# 中文项目目录如 "D:\Desktop\学术工作流" 均不命中——真实泄漏必然带具体用户段）
HOME_PATH = re.compile(r"[A-Za-z]:[\\/](?:Users|Desktop)[\\/](?=[A-Za-z0-9_.\-]*[A-Za-z0-9])"
                       r"[A-Za-z0-9_.\-]+")
# 盘符绝对路径（配置可移植性检查）：断言盘符前是单词边界——否则 JSON 内嵌
# Python 源码的 "exc:\n"、"root:\n"（冒号+字面反斜杠n）会全部误命中
ANY_DRIVE_PATH = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/][A-Za-z0-9_\-]")

# 历史横幅（与健康检查同款判据）：命中的行视为合规历史留痕
HISTORICAL_MARKERS = ("保留作历史", "上一时点", "保留原文", "已失效", "历史值",
                      "快照", "仅供追溯")


def _is_config(rel_posix: str, path: Path) -> bool:
    name = path.name
    if name in CONFIG_NAME_EXACT:
        return True
    if name.startswith("requirements") and name.endswith(".txt"):
        return True
    if any(rel_posix.startswith(m + "/") for m in CONFIG_DIR_MARKERS):
        return True
    return False


def _line_sha256(line: str) -> str:
    return hashlib.sha256(line.strip().encode("utf-8", "ignore")).hexdigest()


def scan_text(text: str, rel_posix: str, is_config: bool) -> list[dict]:
    """纯函数：单文件文本 → 发现列表（可单测）。"""
    findings: list[dict] = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        for pid, pattern in SECRET_PATTERNS:
            hits = pattern.findall(line) if pattern.groups else pattern.findall(line)
            for hit in hits:
                value = hit[-1] if isinstance(hit, tuple) and hit else str(hit)
                if pid == "generic-assignment" and any(
                        m in str(value).upper() or m in str(value) for m in PLACEHOLDER_MARKERS):
                    continue  # 占位符，非凭证
                if pid == "generic-assignment" and len(line) > GENERIC_MAX_LINE:
                    continue
                findings.append({"kind": "secret", "pattern": pid, "file": rel_posix,
                                 "line": idx, "evidence": _mask(str(value)),
                                 "line_sha256": _line_sha256(line)})
        window = line
        if HOME_PATH.search(window):
            if any(m in window for m in HISTORICAL_MARKERS):
                continue
            findings.append({"kind": "home-path", "pattern": "home-path",
                             "file": rel_posix, "line": idx,
                             "evidence": _mask(HOME_PATH.search(window).group(0)),
                             "line_sha256": _line_sha256(line)})
        if is_config and (m := ANY_DRIVE_PATH.search(line)):
            findings.append({"kind": "config-abs-path", "pattern": "config-abs-path",
                             "file": rel_posix, "line": idx,
                             "evidence": _mask(line.strip()[:60]) + f" ← 命中 {m.group(0)!r}",
                             "line_sha256": _line_sha256(line)})
    return findings


def _mask(value: str) -> str:
    """证据脱敏：只保留首尾 4 字符，中间折叠（报告可读且不二次泄密）。"""
    if len(value) <= 8:
        return value[:2] + "***"
    return f"{value[:4]}…{value[-4:]}（len={len(value)}）"


def _tracked_files() -> list[str]:
    # -z + core.quotepath=false：中文路径（academic-toolkit/**）默认被 git 转成
    # 八进制转义串，REPO_ROOT/rel 会全部落空 → 曾致 2317 个文件被误判跳过
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "-c", "core.quotepath=false", "ls-files", "-z"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        print(f"[secret-scan] git ls-files 失败: {(proc.stderr or '')[:200]}",
              file=sys.stderr)
        raise SystemExit(1)
    return [f for f in (proc.stdout or "").split("\0") if f.strip()]


def _load_allowlist() -> list[dict]:
    if not ALLOWLIST_PATH.is_file():
        return []
    return json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))


def run() -> dict:
    allowlist = _load_allowlist()
    allowed = {(a.get("file"), a.get("line_sha256")) for a in allowlist}
    findings, scanned, skipped = [], 0, 0
    for rel in _tracked_files():
        rel_posix = rel.replace("\\", "/")
        if any(rel_posix.startswith(p) for p in EXCLUDED_PREFIXES):
            continue
        path = REPO_ROOT / rel
        if path.suffix.lower() in BINARY_SUFFIXES:
            skipped += 1
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            skipped += 1
            continue
        scanned += 1
        for f in scan_text(text, rel_posix, _is_config(rel_posix, path)):
            if (f["file"], f["line_sha256"]) in allowed:
                f["suppressed"] = True
            findings.append(f)
    active = [f for f in findings if not f.get("suppressed")]
    # B1-5 升档：home-path 由 WARN 升 FAIL——个人路径泄漏一律拦截（豁免走台账）
    blocked = [f for f in active if f["kind"] in ("secret", "config-abs-path", "home-path")]
    warned = [f for f in active if f["kind"] not in ("secret", "config-abs-path", "home-path")]
    return {"scanned": scanned, "skipped_binary_or_unreadable": skipped,
            "allowlisted": len(findings) - len(active),
            "blocked": blocked, "warned": warned, "ok": not blocked}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="密钥与路径卫生扫描（tracked 面机检）")
    parser.add_argument("--strict", action="store_true", help="有 FAIL 级发现 → exit 1")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--emit-allowlist", action="store_true",
                        help="为当前未豁免发现打印豁免条目草稿（人工补 reason 后入台账）")
    args = parser.parse_args(argv)
    res = run()
    if args.as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.emit_allowlist:
        for f in [*res["blocked"], *res["warned"]]:
            print(json.dumps({"file": f["file"], "line": f["line"],
                              "line_sha256": f["line_sha256"],
                              "pattern": f["pattern"], "reason": "TODO-人工补理由"},
                             ensure_ascii=False))
    else:
        print("=" * 64)
        print("密钥与路径卫生扫描（secret_scan）")
        print("=" * 64)
        print(f"扫描 {res['scanned']} 个 tracked 文本文件"
              f"（跳过二进制/不可读 {res['skipped_binary_or_unreadable']}，"
              f"豁免 {res['allowlisted']}）")
        if res["blocked"]:
            print(f"\n❌ FAIL 级发现 {len(res['blocked'])} 项（--strict 将拦截）：")
            for f in res["blocked"]:
                print(f"    [{f['pattern']}] {f['file']}:{f['line']} {f['evidence']}")
        else:
            print("\n✅ 无 FAIL 级发现（密钥 / 配置绝对路径 / 文档家目录路径）")
        if res["warned"]:
            print(f"\n⚠️ WARN 级 {len(res['warned'])} 项：")
            for f in res["warned"][:10]:
                print(f"    {f['file']}:{f['line']} {f['evidence']}")
    return 1 if (args.strict and not res["ok"]) else 0


if __name__ == "__main__":
    sys.exit(main())
