#!/usr/bin/env python3
"""Lint 棘轮（baseline-gated enforcement，2026-09-20 建立）。

**为什么需要**：本仓 608 个 tracked .py 在此之前零 lint 覆盖——2026-09-20 首次引入
ruff 即抓到 1 个真实 NameError（`engine/run_logger.py` `__main__` 块调用尚未定义的
`_count_by`）、1 个重复字典键、1 个无效转义、1 个重复导入，以及 92 项可安全修复项
（已修复并经全量 pytest 验证）。

**上游模式（批判式吸收）**：NVIDIA tensorrt-llm 的 `ruff-legacy-baseline.json`
（github.com/nvidia/tensorrt-llm/issues/11469）——存量违规锁进快照，**新增即拦，
减少则提示收紧**。比"一次性清零再严防"更适合长期演进的仓：清理按独立 PR 推进，
棘轮只降不升。同类还有 astral-sh/ruff#1149（官方 baseline 提案，尚未实现）。

**规则集选择**：`F,E9,W605`（pyflakes 全家 + 语法错误 + 无效转义）——只抓
"几乎必然是缺陷"的类（未定义名/未使用导入/重复键/拼写层错误），不含风格类
（E501 行宽等），避免棘轮被格式噪声淹没。风格类待 ruff format 引入时另行决策。

用法：
  python tools/lint_ratchet.py            # 棘轮检查（新增违规 → exit 1）
  python tools/lint_ratchet.py --update   # 重新生成基线（清理后收紧棘轮时用）
  python tools/lint_ratchet.py --json     # 机读输出

退出码：0 = 棘轮内（含"可收紧"提示）；1 = 超基线或基线文件损坏；
       ruff 缺失时向 stderr 打 ModuleNotFoundError 后 exit 1（健康检查据此判 DEGRADED）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

TOOLBOX_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLBOX_ROOT.parent
BASELINE_PATH = TOOLBOX_ROOT / "data" / "lint_baseline.json"

# 检查范围：引擎 + 工具 + hooks + 两级测试（与 pytest 收集面同构的代码面）
SCOPE: tuple[str, ...] = (
    "engine", "tools", "hooks", "tests",          # 相对 TOOLBOX_ROOT
    str(REPO_ROOT / "tests"),                     # 仓库根门禁测试
)
SELECT = "F,E9,W605"

# 基线 schema 版本：未来语义变化时递增，旧基线拒绝加载
BASELINE_SCHEMA = 1


def _run_ruff() -> list[dict]:
    """运行 ruff，返回 JSON findings（每项含 code/filename/line）。

    --isolated：忽略任何散落配置，保证本机/CI/他人机器同一行为。
    --no-cache：避免 .ruff_cache 噪声（虽已 gitignore，检查件不该写缓存）。
    """
    cmd = [sys.executable, "-m", "ruff", "check", "--isolated", "--no-cache",
           "--select", SELECT, "--output-format", "json", *[str(p) for p in SCOPE]]
    try:
        proc = subprocess.run(cmd, cwd=str(TOOLBOX_ROOT), capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=300)
    except OSError as exc:
        print(f"ModuleNotFoundError: 无法执行 ruff: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if proc.returncode not in (0, 1):  # ruff: 0=干净 1=有 findings，其他=自身故障
        print(f"[lint-ratchet] ruff 自身故障 rc={proc.returncode}\n"
              f"{(proc.stderr or '')[:500]}", file=sys.stderr)
        if "No module named" in (proc.stderr or "") or "No module named" in (proc.stdout or ""):
            print("ModuleNotFoundError: ruff 未安装（requirements-dev.txt 已声明，"
                  "请 pip install -r requirements-dev.txt）", file=sys.stderr)
        raise SystemExit(1)
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        print(f"[lint-ratchet] ruff 输出无法解析为 JSON: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _ruff_version() -> str:
    try:
        proc = subprocess.run([sys.executable, "-m", "ruff", "--version"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60)
        return (proc.stdout or "").strip().replace("ruff ", "")
    except OSError:
        return ""


def _load_baseline() -> dict:
    if not BASELINE_PATH.is_file():
        print(f"[lint-ratchet] 基线不存在: {BASELINE_PATH}（首次请先 --update 生成）",
              file=sys.stderr)
        raise SystemExit(1)
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    if data.get("schema") != BASELINE_SCHEMA:
        print(f"[lint-ratchet] 基线 schema 不匹配（{data.get('schema')} ≠ "
              f"{BASELINE_SCHEMA}），请 --update 重新生成", file=sys.stderr)
        raise SystemExit(1)
    total = sum(data.get("by_rule", {}).values())
    if total != data.get("total"):
        print(f"[lint-ratchet] 基线损坏：total={data.get('total')} ≠ by_rule 求和 {total}",
              file=sys.stderr)
        raise SystemExit(1)
    return data


def evaluate(current: dict, baseline: dict) -> dict:
    """纯函数：现量 vs 基线 → 棘轮判定（可单测）。

    返回 {ok, regressions(逐规则新增数), tighten_hint, version_warning}。
    语义：任一规则现量 > 基线 → 不通过；总量 < 基线 → 提示收紧；
    ruff 版本漂移 → 警告（不同版本规则行为可能变化，计数不可直接比较）。
    """
    by_rule: dict[str, int] = {}
    for f in current.get("findings", []):
        code = str(f.get("code") or "?")
        by_rule[code] = by_rule.get(code, 0) + 1
    base_rules: dict[str, int] = baseline.get("by_rule", {})
    regressions = {code: n - base_rules.get(code, 0)
                   for code, n in by_rule.items() if n > base_rules.get(code, 0)}
    cur_total, base_total = len(current.get("findings", [])), baseline.get("total", 0)
    version_warning = ""
    if baseline.get("ruff_version") and current.get("ruff_version") not in (
            "", baseline.get("ruff_version")):
        version_warning = (f"ruff 版本漂移：基线 {baseline.get('ruff_version')} vs "
                           f"当前 {current.get('ruff_version')}——不同版本规则集行为可能"
                           f"不同，计数可比性存疑（requirements-dev.txt 已锁版本）")
    return {
        "ok": not regressions,
        "by_rule": by_rule,
        "total": cur_total,
        "regressions": regressions,
        "tighten_hint": cur_total < base_total,
        "version_warning": version_warning,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ruff lint 棘轮（基线锁存，新增即拦）")
    parser.add_argument("--update", action="store_true",
                        help="以当前实测重新生成基线（仅在清理后收紧棘轮时使用）")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="机读 JSON 输出")
    args = parser.parse_args(argv)

    findings = _run_ruff()
    version = _ruff_version()
    current = {"findings": findings, "ruff_version": version}

    if args.update:
        by_rule: dict[str, int] = {}
        for f in findings:
            code = str(f.get("code") or "?")
            by_rule[code] = by_rule.get(code, 0) + 1
        BASELINE_PATH.write_text(json.dumps({
            "schema": BASELINE_SCHEMA,
            "ruff_version": version,
            "select": SELECT,
            "scope": list(SCOPE),
            "total": len(findings),
            "by_rule": by_rule,
            "updated": date.today().isoformat(),
            "note": "棘轮基线：total/by_rule 只降不升；收紧请走独立清理 + --update",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[lint-ratchet] 基线已更新: total={len(findings)} by_rule={by_rule} "
              f"(ruff {version}) → {BASELINE_PATH.name}")
        return 0

    verdict = evaluate(current, _load_baseline())
    if args.as_json:
        print(json.dumps(verdict, ensure_ascii=False, indent=2))
    else:
        if verdict["version_warning"]:
            print(f"⚠️ {verdict['version_warning']}")
        print(f"[lint-ratchet] 实测 {verdict['total']} 项 "
              f"({verdict['by_rule']}) vs 基线 "
              f"{_load_baseline().get('total')} 项")
        if verdict["regressions"]:
            print("❌ 棘轮回退，以下规则新增违规：")
            for code, delta in verdict["regressions"].items():
                print(f"    {code}: +{delta}")
            print("    修复新增项，或清理存量后 --update 收紧（不允许直接抬基线）。")
        elif verdict["tighten_hint"]:
            print("✅ 棘轮内，且存量下降——可运行 --update 收紧基线。")
        else:
            print("✅ 棘轮内。")
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
