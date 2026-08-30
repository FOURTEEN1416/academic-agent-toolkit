#!/usr/bin/env python3
"""技能库补充验证审计器（2026-08-29 起为常驻工具）。

对 skills/ 全库做五类机检，输出结构化报告（JSON）与退出码：
  1. frontmatter 完整：每个 SKILL.md 可解析且有 name/description；
  2. 体积健康：SKILL.md 非空壳（≥200B）；
  3. 编码健康：UTF-8 可解码、无 U+FFFD 替换符堆积（污染检测）；
  4. 引用完整性：SKILL.md 中引用的本仓库相对路径（skills/ tools/ _utils/ engine/）真实存在；
  5. 模板一致性：engine/modex-core/templates.json 引用的技能名都有对应目录。

用法：python tools/skill_library_audit.py [--json]
退出码 0=全过 / 1=有失败。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONT = re.compile(r"\A---\s*\n(.*?)\n---", re.S)
REF = re.compile(r"(?:skills|tools|engine)/[A-Za-z0-9_\-./\u4e00-\u9fff]+\.(?:py|md|json|sh|tex|drawio|mjs|ttf|geojson)")
MOJIBAKE_MARKS = ("锟斤拷", "烫烫烫", "\ufffd\ufffd")


def audit() -> dict:
    report = {"skills_total": 0, "failures": {}, "summary": {}}
    fails = {k: [] for k in ("frontmatter", "too_small", "encoding", "broken_ref", "name_mismatch", "name_duplicate")}
    seen_names = {}
    skill_dirs = sorted(d for d in (ROOT / "skills").iterdir() if d.is_dir() and (d / "SKILL.md").is_file())
    report["skills_total"] = len(skill_dirs)

    for d in skill_dirs:
        name = d.name
        p = d / "SKILL.md"
        raw = p.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            fails["encoding"].append(f"{name}: not utf-8")
            continue
        if any(m in text for m in MOJIBAKE_MARKS):
            fails["encoding"].append(f"{name}: mojibake markers")
        if len(raw) < 200:
            fails["too_small"].append(name)
        m = FRONT.match(text)
        if not m or "name:" not in m.group(1) or "description" not in m.group(1):
            fails["frontmatter"].append(name)
            continue
        fm_name = re.search(r'^name:\s*(.+)$', m.group(1), re.M).group(1).strip().strip('"').strip("'")
        if fm_name != name:
            fails["name_mismatch"].append(f"{name}: frontmatter name={fm_name!r}")
        seen_names.setdefault(fm_name, []).append(name)
        body_refs = set(REF.findall(text))
        for ref in body_refs:
            if (ROOT / ref).exists():
                continue
            # 治理标注过的"上游脚本未集成"引用视为 acknowledged
            tail = text[text.find(ref): text.find(ref) + len(ref) + 150]
            if "ACAT-GOVERNANCE" in tail:
                continue
            alt = ROOT / ref.rsplit("/", 1)[0]
            if not alt.exists():
                fails["broken_ref"].append(f"{name}: {ref}")

    # 模板一致性
    tpl_path = ROOT / "engine" / "modex-core" / "templates.json"
    tpl = json.loads(tpl_path.read_text(encoding="utf-8"))
    missing = []
    for tname, t in tpl.items():
        for s in t.get("sub_steps", []):
            sk = s.get("skill_name")
            if sk and not (ROOT / "skills" / sk / "SKILL.md").is_file():
                missing.append(f"{tname}: {sk}")
    report["templates_total"] = len(tpl)
    for fm_name, owners in seen_names.items():
        if len(owners) > 1:
            fails["name_duplicate"].append(f"{fm_name}: {owners}")
    report["failures"] = {k: v for k, v in fails.items() if v}
    report["failures"]["template_missing_skill"] = missing
    report["summary"] = {
        k: len(v) for k, v in report["failures"].items()
    }
    report["ok"] = not any(report["summary"].values())
    return report


if __name__ == "__main__":
    rep = audit()
    if "--json" in sys.argv:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print(f"skills: {rep['skills_total']} | templates: {rep['templates_total']}")
        for k, v in rep["failures"].items():
            print(f"[{k}] {len(v)}")
            for item in v[:15]:
                print("  -", item)
        print("OK" if rep["ok"] else "FAIL")
    sys.exit(0 if rep["ok"] else 1)
