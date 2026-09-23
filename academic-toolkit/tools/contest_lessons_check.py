#!/usr/bin/env python3
"""CUMCM 实战经验库机检（P1 沉淀资产的反馈闭环件）。

经验库不是散文集——它必须能被机器验证"没写空话"。本工具做四件事：

  1. schema      —— `data/contest_lessons.json` 结构、ID 唯一性、枚举合规
                    （stage 必须属于 meta.stages；topic 必须属于 meta.topics；
                    severity 仅限 P0/P1/P2）。
  2. enforced_by —— **每条经验的强制点路径必须真实存在**（仓库根相对）。
                    这是本库的核心纪律：没有强制点的教训不算沉淀完成——
                    禁止写"应当建立 XXX"这类无落点的空承诺。
  3. bidirectional —— JSON 与 `data/contest_lessons.md` 的 ID 集合必须完全一致
                    （人读真源与机读真源双向锁死，防止只改一边）。
  4. distribution —— 强制点分布统计：单一文件覆盖过多条目时告警（过度集中 =
                    经验其实只落在一个机制上，覆盖度虚高）。

用法：
  python tools/contest_lessons_check.py               # 人读输出
  python tools/contest_lessons_check.py --json        # 机读 JSON
  python tools/contest_lessons_check.py --strict      # 任一错误即 exit 1

退出码：默认 0（报告件）；--strict 时发现错误 exit 1。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLBOX_ROOT = Path(__file__).resolve().parents[1]

LESSONS_JSON = TOOLBOX_ROOT / "data" / "contest_lessons.json"
LESSONS_MD = TOOLBOX_ROOT / "data" / "contest_lessons.md"

# 条目 ID 形态：场景 S<n>、坑 P<两位>、清单 CL<n>（与真源写法一致）
ID_RE = re.compile(r"\b(?:S\d{1,2}|P\d{2}|CL\d{1,2})\b")

KIND_FIELDS: dict[str, tuple[str, ...]] = {
    "scenarios": ("id", "stage", "topic", "title", "trigger", "decision", "rationale", "enforced_by"),
    "pitfalls": ("id", "severity", "stage", "topic", "title", "symptom", "root_cause",
                 "impact", "prevention", "enforced_by"),
    "checklists": ("id", "stage", "title", "items", "enforced_by"),
}
SEVERITIES = {"P0", "P1", "P2"}
# 强制点过度集中阈值：单个文件覆盖超过该比例即告警（覆盖度虚高的信号）
CONCENTRATION_LIMIT = 0.60


def load_lessons(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_schema(data: dict) -> dict:
    """结构与枚举校验。"""
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append(f"schema_version 必须为整数 1，实际 {data.get('schema_version')!r}")
    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append("缺少 meta 对象")
        return {"ok": False, "errors": errors, "counts": {}, "ids": []}
    stages = set((meta.get("stages") or {}).keys())
    topics = set((meta.get("topics") or {}).keys())
    if not stages:
        errors.append("meta.stages 为空（stage 枚举真源）")
    if not topics:
        errors.append("meta.topics 为空（topic 枚举真源）")

    counts: dict[str, int] = {}
    ids: list[str] = []
    for kind, fields in KIND_FIELDS.items():
        entries = data.get(kind)
        if not isinstance(entries, list) or not entries:
            errors.append(f"{kind} 必须是非空数组")
            continue
        counts[kind] = len(entries)
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append(f"{kind} 存在非对象条目")
                continue
            missing: list[str] = []
            for field in fields:
                value = entry.get(field)
                if field == "items":
                    # items 是数组字段：要求是非空字符串数组
                    if not isinstance(value, list) or not value:
                        missing.append("items(非空数组)")
                    elif not all(str(v).strip() for v in value):
                        missing.append("items(含空项)")
                elif not str(value or "").strip():
                    missing.append(field)
            eid = str(entry.get("id", "")).strip()
            if missing:
                errors.append(f"{kind}/{eid or '<无 id>'} 缺字段或为空: {missing}")
            if eid:
                ids.append(eid)
            stage = str(entry.get("stage", "")).strip()
            if stage and stages and stage not in stages:
                errors.append(f"{kind}/{eid} stage={stage!r} 不在 meta.stages 中")
            topic = str(entry.get("topic", "")).strip()
            if topic and topics and topic not in topics:
                errors.append(f"{kind}/{eid} topic={topic!r} 不在 meta.topics 中")
            severity = entry.get("severity")
            if severity is not None and severity not in SEVERITIES:
                errors.append(f"{kind}/{eid} severity={severity!r} 非法（仅 P0/P1/P2）")

    dupes = [i for i, n in Counter(ids).items() if n > 1]
    if dupes:
        errors.append(f"ID 重复: {sorted(dupes)}")
    return {"ok": not errors, "errors": errors, "counts": counts, "ids": ids,
            "stages": sorted(stages), "topics": sorted(topics)}


def check_enforced_by(data: dict, repo_root: Path) -> dict:
    """强制点必须在位（仓库根相对路径）。"""
    errors: list[str] = []
    checked = 0
    per_file: Counter[str] = Counter()
    for kind in KIND_FIELDS:
        for entry in data.get(kind) or []:
            if not isinstance(entry, dict):
                continue
            rel = str(entry.get("enforced_by", "")).strip()
            if not rel:
                continue
            checked += 1
            per_file[rel] += 1
            if Path(rel).is_absolute():
                errors.append(f"{entry.get('id')} enforced_by 必须是仓库根相对路径: {rel}")
                continue
            if not (repo_root / rel).exists():
                errors.append(f"{entry.get('id')} 强制点不存在（空话风险）: {rel}")
    return {"ok": not errors, "errors": errors, "checked": checked,
            "per_file": dict(per_file.most_common())}


def check_bidirectional(data: dict, md_path: Path) -> dict:
    """JSON 与 MD 的 ID 集合必须完全一致。"""
    if not md_path.is_file():
        return {"ok": False, "errors": [f"人读真源缺失: {md_path}"],
                "json_only": [], "md_only": [], "md_count": 0}
    md_ids = set(ID_RE.findall(md_path.read_text(encoding="utf-8")))
    json_ids = {
        str(entry.get("id", "")).strip()
        for kind in KIND_FIELDS
        for entry in (data.get(kind) or [])
        if isinstance(entry, dict) and str(entry.get("id", "")).strip()
    }
    json_only = sorted(json_ids - md_ids)
    md_only = sorted(md_ids - json_ids)
    errors = []
    if json_only:
        errors.append(f"JSON 有条目但人读真源未写: {json_only}")
    if md_only:
        errors.append(f"人读真源有 ID 但 JSON 无对应条目（幽灵条目）: {md_only}")
    return {"ok": not errors, "errors": errors, "json_only": json_only,
            "md_only": md_only, "md_count": len(md_ids)}


def concentration_warning(enforced: dict) -> str | None:
    """强制点过度集中告警：覆盖度可能是假的。"""
    total = sum(enforced.get("per_file", {}).values())
    if not total:
        return None
    top_file, top_n = next(iter(enforced["per_file"].items()))
    if top_n / total > CONCENTRATION_LIMIT:
        return (f"强制点过度集中：{top_file} 覆盖 {top_n}/{total} 条"
                f"（>{CONCENTRATION_LIMIT:.0%}）。经验看似都落了地，实际只落在一个机制上；"
                "请复核是否仍有条目缺真实强制点。")
    return None


def run(repo_root: Path) -> dict:
    if not LESSONS_JSON.is_file():
        return {"ok": False, "errors": [f"经验库缺失: {LESSONS_JSON}"],
                "schema": {"ok": False, "errors": [], "counts": {}},
                "enforced_by": {"ok": False, "errors": [], "checked": 0, "per_file": {}},
                "bidirectional": {"ok": False, "errors": [], "json_only": [], "md_only": []},
                "concentration_warning": None}
    data = load_lessons(LESSONS_JSON)
    schema = check_schema(data)
    enforced = check_enforced_by(data, repo_root)
    bidi = check_bidirectional(data, LESSONS_MD)
    warn = concentration_warning(enforced)
    ok = bool(schema["ok"] and enforced["ok"] and bidi["ok"])
    errors = list(schema["errors"]) + list(enforced["errors"]) + list(bidi["errors"])
    return {"ok": ok, "errors": errors, "schema": schema, "enforced_by": enforced,
            "bidirectional": bidi, "concentration_warning": warn}


def _print_report(result: dict) -> None:
    print("=" * 72)
    print("CUMCM 实战经验库机检（contest_lessons_check）")
    print("=" * 72)
    schema = result["schema"]
    counts = schema.get("counts", {})
    print(f"\n[1] schema：场景 {counts.get('scenarios', 0)} / 坑 {counts.get('pitfalls', 0)} / "
          f"清单 {counts.get('checklists', 0)} —— {'OK' if schema['ok'] else 'FAIL'}")
    enforced = result["enforced_by"]
    print(f"[2] 强制点在位：校验 {enforced.get('checked', 0)} 条 / "
          f"{'全部在位' if enforced['ok'] else '存在空话'} —— {'OK' if enforced['ok'] else 'FAIL'}")
    for rel, n in (enforced.get("per_file") or {}).items():
        print(f"      {n:>2}× {rel}")
    bidi = result["bidirectional"]
    print(f"[3] 双向一致（JSON ↔ MD）：MD 侧 ID {bidi.get('md_count', 0)} 个 —— "
          f"{'OK' if bidi['ok'] else 'FAIL'}")
    if result.get("concentration_warning"):
        print(f"\n    ⚠️ {result['concentration_warning']}")
    if result["errors"]:
        print("\n    错误明细：")
        for err in result["errors"]:
            print(f"      ✗ {err}")
    print(f"\n结论：{'全部通过' if result['ok'] else '存在错误'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CUMCM 实战经验库机检（schema/强制点在位/双向一致）")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="仓库根（强制点路径解析基准）")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出机读 JSON")
    parser.add_argument("--strict", action="store_true", help="存在错误时 exit 1")
    args = parser.parse_args(argv)

    result = run(Path(args.repo).resolve())
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_report(result)
    if args.strict and not result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
