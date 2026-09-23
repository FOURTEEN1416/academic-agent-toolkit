#!/usr/bin/env python3
"""技能库补充验证审计器（2026-08-29 起为常驻工具）。

对 skills/ 全库做五类机检，输出结构化报告（JSON）与退出码：
  1. frontmatter 完整：每个 SKILL.md 可解析且有 name/description；
  2. 体积健康：SKILL.md 非空壳（≥200B）；
  3. 编码健康：UTF-8 可解码、无 U+FFFD 替换符堆积（污染检测）；
  4. 引用完整性：SKILL.md 中引用的本仓库相对路径（skills/ tools/ engine/）真实存在；
     并检查技能内部相对引用（references/ scripts/ assets/ 等开头）——未声明断链计 FAIL，
     有 ACAT-GOVERNANCE 内联标记或 UPSTREAM.md 溯源台账的断链计入 acknowledged（透明列出，不 FAIL）；
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
REF = re.compile(r"(?<![A-Za-z0-9_\-./])(?:skills|tools|engine)/[A-Za-z0-9_\-./\u4e00-\u9fff]+\.(?:py|md|json|sh|tex|drawio|mjs|ttf|geojson)")
# 2026-09-23 v2.0 收尾：加左侧标识符边界——否则 `references/mml-skills/x.md` 这类
# 路径中的子串 `skills/x.md` 会被截胡命中成幽灵断链（mml-skills 收编批实测）。
# 技能内部相对引用（references/ scripts/ assets/ 三个 skills 生态标准目录开头，
# 外加 _utils/ 与 shared-scripts/ 两个 skills 级共享脚本目录——2026-09-09 独立审计
# P1-4 扩展：此前 _utils/ 前缀引用不在机检范围，dev-selfcheck 等真实断链漏网；
# 2026-09-22 B3-6 ①扩展：技能自带数据目录 data/ 同样入机检（此前 data/ 引用静默跳过））；
# (?<![\w./-]) 防止从 "subscripts/superscripts" 这类正文单词中截出 "scripts/superscripts" 伪引用。
# docs/ templates/ knowledge/ 等歧义前缀（可能相对仓库根）不在机检范围，靠人工审计兜底。
INNER_REF = re.compile(
    r"(?<![\w./\-])((?:references|scripts|assets|_utils|shared-scripts|data)"
    r"/[A-Za-z0-9_][A-Za-z0-9_{}*./\-]*)"
)
# B3-6 ③：上游版式路径（shared/ docs/ ~/.claude/... 等指向上游仓库结构的引用）。
# 目标不随本仓分发，无法机检存在性，但不再静默跳过——显式登记进报告 upstream_refs。
UPSTREAM_REF = re.compile(
    r"(?<![\w./\-])((?:shared|docs|~/\.claude|~/.claude)"
    r"/[A-Za-z0-9_][A-Za-z0-9_{}*./\-]*)"
)
MOJIBAKE_MARKS = ("锟斤拷", "烫烫烫", "\ufffd\ufffd")


def _dynamic_placeholder(ref: str) -> bool:
    """通配符/模板变量/动态拼接导致的伪断链（figure_recipes_*.md、sample_{lang}...）。"""
    return "{" in ref or "*" in ref or ref.endswith(("_", "-"))


def _load_gap_register() -> dict:
    """棘轮登记册：2026-09-09 基线内的已知内部断链（存量豁免，新增必 FAIL）。"""
    path = Path(__file__).resolve().parent / "asset_gap_register.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("gaps", {})


def audit() -> dict:
    report = {"skills_total": 0, "failures": {}, "summary": {}}
    fails = {k: [] for k in ("frontmatter", "too_small", "encoding", "broken_ref", "broken_inner_ref", "name_mismatch", "name_duplicate")}
    acknowledged = []  # 有 UPSTREAM.md 溯源台账或 ACAT-GOVERNANCE 内联声明的内部断链（透明列出，不计 FAIL）
    upstream_refs = []  # B3-6 ③：上游版式路径（shared/ docs/ ~/.claude/...），显式登记不计 FAIL
    gap_register = _load_gap_register()
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
            # B3-6 ②：文件级校验——"父目录存在即放行"是断链盲区（目录在、文件没了照样漏网）。
            # 目标缺失时先查登记册棘轮（存量透明豁免），其余一律 FAIL。
            if ref in gap_register.get(name, []):
                acknowledged.append(f"{name}: {ref} (登记册棘轮存量)")
            else:
                fails["broken_ref"].append(f"{name}: {ref}")

        # 技能内部相对引用完整性（references/ scripts/ assets/ 等）
        # ASSET-GAP.md 声明采用清单制：仅豁免其"缺失资产清单"中列出的条目，
        # 声明之后新增的断链不在清单内，必须 FAIL（防文件级声明掩盖新断链）。
        gap_file = d / "ASSET-GAP.md"
        declared_gaps = set()
        if gap_file.is_file():
            declared_gaps = set(re.findall(r"^- `(.+?)`", gap_file.read_text(encoding="utf-8"), re.M))
        seen_inner = set()
        for m in INNER_REF.finditer(text):
            ref = m.group(1).rstrip(".,);:”\"'")
            if ref in seen_inner:
                continue
            seen_inner.add(ref)
            # 解析顺序：①技能目录内相对路径；②skills/ 级共享目录（_utils/、shared-scripts/
            # 从技能正文引用时实际指向 skills/_utils/…，2026-09-09 审计 P1-4）；③通配符目录。
            if (d / ref).exists() or (ROOT / "skills" / ref).exists() \
                    or (ref.startswith("data/") and (ROOT / "data" / ref[len("data/"):]).exists()) \
                    or (d / ref.split("/")[0]).is_dir() and "*" in ref:
                continue
            if _dynamic_placeholder(ref):
                continue
            # 豁免顺序（防线语义）：①内联标记=就地精确声明；②登记册棘轮=2026-09-09
            # 存量豁免（新增断链必 FAIL）；③ASSET-GAP.md 清单制声明（仅豁免其清单内条目）。
            # UPSTREAM.md 台账是溯源文档，不参与机检豁免——断链豁免统一走登记册。
            if "ACAT-GOVERNANCE" in text[max(0, m.start() - 80): m.end() + 150]:
                acknowledged.append(f"{name}: {ref} (内联标记)")
            elif ref in gap_register.get(name, []):
                acknowledged.append(f"{name}: {ref} (登记册棘轮存量)")
            elif ref in declared_gaps:
                acknowledged.append(f"{name}: {ref} (ASSET-GAP.md 清单)")
            else:
                fails["broken_inner_ref"].append(f"{name}: {ref}")

        # B3-6 ③：上游版式路径显式登记（shared/ docs/ ~/.claude/... 指向上游仓库结构，
        # 目标不随本仓分发，不参与 FAIL 机检，但从"静默跳过"改为报告可见）。
        for m in UPSTREAM_REF.finditer(text):
            ref = m.group(1).rstrip(".,);:”\"'")
            if (ROOT / ref).exists() or (d / ref).exists():
                continue  # 仓库内真实存在的同名路径（如 docs/ 指仓库根 docs）不算上游引用
            upstream_refs.append(f"{name}: {ref}")

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
    report["acknowledged_inner_refs"] = acknowledged
    report["upstream_refs"] = upstream_refs
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
        ack = rep.get("acknowledged_inner_refs") or []
        if ack:
            print(f"[acknowledged_inner_refs] {len(ack)} (有声明，不计 FAIL)")
            for item in ack[:10]:
                print("  -", item)
            if len(ack) > 10:
                print(f"  ... 共 {len(ack)} 条")
        print("OK" if rep["ok"] else "FAIL")
    sys.exit(0 if rep["ok"] else 1)
