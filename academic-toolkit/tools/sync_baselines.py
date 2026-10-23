#!/usr/bin/env python3
"""基线数字单源同步器（sync_baselines，2026-10-23 建立）。

**为什么需要**：测试 / 技能 / 能力三个基线数字常年分散在 `pytest.ini` 注释、README
徽章与基线表、根 `AGENTS.md` 测试口径表、内部 `dev-docs/truth-index.md` 四处。历史
批次靠人工同步，实证出现过 20+ 次过期基线（漂移检测器 project_health_check 就是为此
而建）。人工同步既慢又容易漏行——本工具把口径收敛成一条链：

    pytest.ini 注释（唯一确认点）
        │  ←--check：比对实测（pytest collect / git ls-files / catalog.json）
        ├─ ←--accept：以实测值重写 DRIFT_SOURCES 捕获组
        └─→ README / 根 AGENTS.md / truth-index 等权威文档

**边界（有意为之，防误伤）**：
- `--accept` 只替换 `project_health_check.DRIFT_SOURCES` 命中的**第 1 捕获组数字**，
  不改任何 prose、不动行内其他数字、不新增/删除行；
- 命中 `HISTORICAL_MARKERS`（保留作历史 / 上一时点 / 快照 …）的行整体跳过——历史
  记录保留原文是项目铁律；
- 文件缺失（公开 clone 没有 `dev-docs/truth-index.md`）按"跳过"处理，不判失败；
- 原样保留行尾（CRLF/LF）与文件末尾换行，避免制造整文件 diff。

用法：
  python academic-toolkit/tools/sync_baselines.py --check              # 实测 vs 单源 vs 传播
  python academic-toolkit/tools/sync_baselines.py --accept             # 写回（实测值）
  python academic-toolkit/tools/sync_baselines.py --accept --dry-run   # 只看会改什么
  python academic-toolkit/tools/sync_baselines.py --check --json       # 机读

退出码：`--check` 有任何不一致 / 锚点缺失 → 1；`--accept` 成功 → 0（`--dry-run` 恒 0）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOOLBOX_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLBOX_ROOT.parent
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:  # 脚本直跑 / 作为包被导入两种形态都能找到同目录工具
    sys.path.insert(0, str(TOOLS_DIR))

import project_health_check as phc  # noqa: E402  （复用其 DRIFT_SOURCES / 实测原语）

METRICS = ("tests", "skills", "capabilities")


# ---------- 实测（唯一实现入口，project_health_check 反向复用本函数） ----------

def measure(skip_slow: bool = False) -> dict:
    """三个指标的实测值：tests = pytest collect-only；skills = git ls-files；capabilities = catalog.json。

    `skip_slow` 只跳过最慢的 pytest 收集（技能/能力数为毫秒级，始终实测）。
    """
    tests = ({"available": False, "reason": "已跳过（--skip-slow）", "count": None}
             if skip_slow else phc._actual_test_count())
    return {
        "tests": tests,
        "skills": phc._actual_skill_count(),
        "capabilities": phc._actual_capability_count(),
    }


# ---------- 权威文档读写（保留原始行尾） ----------

def _read_lines(path: Path) -> list[str]:
    """按原始行尾切行（keepends=True）。

    必须走 bytes 解码：`Path.read_text()` 默认做 universal-newline 转换，会把 CRLF
    折成 LF，写回时整文件行尾被改写（2026-10-23 首跑实测：README/AGENTS/pytest.ini
    全量 CRLF→LF）。这里保留原始字节形态，配合 `newline=""` 写回。
    """
    return path.read_bytes().decode("utf-8").splitlines(keepends=True)


def _write_lines(path: Path, lines: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write("".join(lines))


def _is_historical(lines: list[str], idx: int) -> bool:
    """历史横幅豁免：与本行及前两行比对（与 project_health_check._drift 同口径）。"""
    window = "".join(lines[max(0, idx - 2): idx + 1])
    return any(marker in window for marker in phc.HISTORICAL_MARKERS)


def _sources() -> list[tuple[str, str, str]]:
    """DRIFT_SOURCES 归一化为三元组 (文件, 行内模式, 指标)。"""
    return [(item[0], item[1], item[2] if len(item) > 2 else "tests")
            for item in phc.DRIFT_SOURCES]


def _scan(rel: str, pattern: str) -> dict:
    """扫描一个权威文档：返回 {status, lines, hits}（hits = 未豁免的 [(行号, 数字)]）。"""
    path = REPO_ROOT / rel
    if not path.is_file():
        return {"status": "missing", "path": path, "lines": [], "hits": []}
    lines = _read_lines(path)
    hits, exempted = [], 0
    for idx, line in enumerate(lines):
        for match in re.finditer(pattern, line):
            if _is_historical(lines, idx):
                exempted += 1
                continue
            hits.append((idx + 1, int(match.group(1))))
    return {"status": "ok", "path": path, "lines": lines,
            "hits": hits, "exempted": exempted}


def authoritative() -> dict:
    """单源：pytest.ini 注释里的 tests 基线（skills/capabilities 无 pytest.ini 条目）。"""
    for rel, pattern, metric in _sources():
        if rel == "pytest.ini" and metric == "tests":
            scan = _scan(rel, pattern)
            if scan["status"] == "ok" and scan["hits"]:
                line, value = scan["hits"][0]
                return {"available": True, "file": rel, "line": line, "value": value}
            return {"available": False, "file": rel, "reason": "pytest.ini 未找到基线锚点"}
    return {"available": False, "file": "pytest.ini", "reason": "DRIFT_SOURCES 缺 pytest.ini 锚点"}


def _within(documented: int, actual: int, metric: str) -> bool:
    """与 project_health_check 漂移判定同口径（tests 0.5%，skills/capabilities 严格等值）。"""
    tol = phc.METRIC_TOLERANCES.get(metric, phc.DRIFT_TOLERANCE)
    return abs(documented - actual) <= max(1 if tol > 0 else 0, int(actual * tol))


# ---------- check ----------

def check(skip_slow: bool = False) -> dict:
    counts = measure(skip_slow=skip_slow)
    auth = authoritative()
    measured = {m: counts[m]["count"] for m in METRICS}
    rows, problems = [], []
    seen: set[tuple[str, int]] = set()

    for metric in METRICS:
        if not counts[metric]["available"]:
            problems.append(f"{metric} 未实测：{counts[metric]['reason']}")
            continue
        actual = measured[metric]
        if metric == "tests" and auth.get("available"):
            ok = _within(auth["value"], actual, metric)
            rows.append({"metric": metric, "file": auth["file"], "line": auth["line"],
                         "source": True, "documented": auth["value"], "actual": actual, "ok": ok})
            seen.add((auth["file"], auth["line"]))
            if not ok:
                problems.append(f"{auth['file']}:{auth['line']} 单源 {auth['value']} ≠ 实测 {actual}")
        for rel, pattern, src_metric in _sources():
            if src_metric != metric:
                continue
            scan = _scan(rel, pattern)
            if scan["status"] == "missing":
                continue  # 公开 clone 无内部文档：跳过，不判失败
            if not scan["hits"]:
                problems.append(f"{rel} 未找到可更新的 {metric} 锚点（模式：{pattern}）")
                continue
            for line, documented in scan["hits"]:
                if (rel, line) in seen:  # 单源行已单独判定，不重复报
                    continue
                ok = _within(documented, actual, metric)
                rows.append({"metric": metric, "file": rel, "line": line,
                             "source": False, "documented": documented,
                             "actual": actual, "ok": ok})
                if not ok:
                    problems.append(f"{rel}:{line} 文档 {documented} ≠ 实测 {actual}（{metric}）")

    return {"ok": not problems, "measured": measured, "authoritative": auth,
            "rows": rows, "problems": problems}


# ---------- accept ----------

def accept(dry_run: bool = False, skip_slow: bool = False) -> dict:
    """以实测值重写 DRIFT_SOURCES 捕获组；返回逐处变更。"""
    counts = measure(skip_slow=skip_slow)
    changes, skipped, missing = [], [], []
    for rel, pattern, metric in _sources():
        status = counts.get(metric, {})
        if not status.get("available"):
            skipped.append(f"{rel}: {metric} 未实测（{status.get('reason', '不可用')}）")
            continue
        want = status["count"]
        scan = _scan(rel, pattern)
        if scan["status"] == "missing":
            continue
        lines = scan["lines"]
        file_changed = False
        for idx, line in enumerate(lines):
            if _is_historical(lines, idx):
                continue
            matches = list(re.finditer(pattern, line))
            if not matches:
                continue
            new_line = line
            # 逆序替换，保证前面 match 的偏移不失效
            for match in reversed(matches):
                old = int(match.group(1))
                if old == want:
                    continue
                new_line = new_line[:match.start(1)] + str(want) + new_line[match.end(1):]
                changes.append({"file": rel, "line": idx + 1, "metric": metric,
                                "old": old, "new": want})
            if new_line != line:
                lines[idx] = new_line
                file_changed = True
        if file_changed and not dry_run:
            _write_lines(scan["path"], lines)
    if not changes:
        missing = ["已是最新：所有捕获组与实测一致"]
    return {"dry_run": dry_run, "measured": {m: counts[m]["count"] for m in METRICS},
            "changes": changes, "skipped": skipped, "notes": missing}


# ---------- CLI ----------

def _fmt(value) -> str:
    return "unknown" if value is None else str(value)


def _print_check(res: dict) -> None:
    print("=" * 72)
    print("基线单源检查（sync_baselines --check）")
    print("=" * 72)
    print("实测：" + "  ".join(f"{m}={_fmt(res['measured'].get(m))}" for m in METRICS))
    auth = res["authoritative"]
    if auth.get("available"):
        print(f"单源：{auth['file']}:{auth['line']} tests={auth['value']}")
    else:
        print(f"单源：❌ {auth.get('reason', '不可用')}")
    print("\n传播面：")
    for row in res["rows"]:
        mark = "✅" if row["ok"] else "❌"
        tag = "（单源）" if row["source"] else ""
        print(f"    {mark} {row['file']}:{row['line']}  {row['metric']}="
              f"{row['documented']}（实测 {row['actual']}）{tag}")
    print("\n结论：" + ("✅ 单源与传播面全部一致" if res["ok"] else
                      f"❌ {len(res['problems'])} 处不一致"))
    for problem in res["problems"]:
        print(f"    - {problem}")


def _print_accept(res: dict) -> None:
    mode = "DRY-RUN（未写盘）" if res["dry_run"] else "已写盘"
    print("=" * 72)
    print(f"基线同步（sync_baselines --accept，{mode}）")
    print("=" * 72)
    print("实测：" + "  ".join(f"{m}={_fmt(res['measured'].get(m))}" for m in METRICS))
    if res["changes"]:
        print("\n变更：")
        for change in res["changes"]:
            print(f"    {change['file']}:{change['line']}  {change['metric']} "
                  f"{change['old']} → {change['new']}")
    else:
        print("\n无变更（所有捕获组已与实测一致）")
    for note in res["notes"]:
        print(f"    {note}")
    for skip in res["skipped"]:
        print(f"    ⚠️ 跳过 {skip}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="基线数字单源同步器（--check 比对 / --accept 传播）")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="实测 vs 单源 vs 权威文档（默认）")
    action.add_argument("--accept", action="store_true", help="以实测值重写 DRIFT_SOURCES 捕获组")
    parser.add_argument("--dry-run", action="store_true", help="配合 --accept：只打印不写盘")
    parser.add_argument("--skip-slow", action="store_true", help="跳过 pytest 收集（仅 skills/capabilities）")
    parser.add_argument("--json", action="store_true", dest="as_json", help="机读 JSON")
    args = parser.parse_args(argv)

    if args.accept:
        res = accept(dry_run=args.dry_run, skip_slow=args.skip_slow)
        if args.as_json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            _print_accept(res)
        return 0

    # --check 需要 tests 实测；--skip-slow 下 tests 未实测 → problems 如实报出并 exit 1
    res = check(skip_slow=args.skip_slow)
    if args.as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        _print_check(res)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
