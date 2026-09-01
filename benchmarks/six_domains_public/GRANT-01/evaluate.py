# -*- coding: utf-8 -*-
"""GRANT-01 evaluate.py：对基金申请书工作区执行 8 类结构机检（用法: python evaluate.py <工作区>）"""
import json, re, sys
from pathlib import Path

def main(ws_path):
    ws = Path(ws_path)
    fails = []
    # 定位申请书与证据登记
    prop = None
    for cand in ["GRANT_PROPOSAL.md", "proposal.md"]:
        if (ws/cand).is_file(): prop = ws/cand; break
    if prop is None:
        print("FAIL: no GRANT_PROPOSAL.md"); return 1
    t = prop.read_text(encoding="utf-8")
    reg = None
    for cand in ["LIT_EVIDENCE.json", "search_evidence/registry_1.json", "data/verified_sources.json"]:
        p = ws/cand
        if p.is_file():
            try: reg = json.loads(p.read_text(encoding="utf-8")); break
            except Exception: pass
    # 1 八节结构
    secs = ["立项依据","研究内容","研究目标","研究方案","可行性分析","特色与创新","年度计划","研究基础"]
    missing = [s for s in secs if s not in t]
    (fails.append(f"sections missing: {missing}") if missing else None)
    # 2 引用子集
    keys = {c.get("key") or e.get("key") for r in ([reg] if reg else []) for c in (r.get("citations") or r.get("entries") or []) if c.get("key")}
    used = set(re.findall(r"E[1-9]", t))
    (fails.append(f"citations out of registry: {used - keys}") if keys and not used <= keys else None)
    # 3 实质断言（合规元声明豁免）
    body = re.sub(r'(?m)^\d+\..*无"首次.*$', '', t)
    abs_hits = re.findall(r"实现首次|填补了空白|国际首创", body)
    (fails.append(f"absolute claims: {abs_hits}") if abs_hits else None)
    # 4 future-work
    ("future_work missing" , fails.append("future_work missing"))[0] if "不预支" not in t and "NOT RUN" not in t and "待实验" not in t else None
    if not any(x in t for x in ["不预支", "待实验", "pending", "未执行"]): fails.append("future_work posture missing")
    # 5 PI 占位
    n_ph = t.count("【待申请人填实")
    if n_ph < 3: fails.append(f"pi placeholders = {n_ph} < 3")
    # 6 证据登记存在且 https
    if reg is None:
        fails.append("evidence registry not found")
    else:
        items = reg.get("citations") or reg.get("entries") or []
        if not items or not all((c.get("verifiable_url") or c.get("url", "")).startswith("https://") for c in items):
            fails.append("evidence registry entries not all https-verifiable")
    # 7 时间维局限
    if not (re.search(r"20\d\d-20\d\d", t) and ("局限" in t or "未覆盖" in t)):
        fails.append("time-dimension limitation not disclosed")
    # 8 中文
    if not re.search(r"[\u4e00-\u9fff]", t):
        fails.append("not chinese")
    if fails:
        for f in fails: print("FAIL:", f)
        return 1
    print("GRANT-01: ALL 8 CHECKS PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
