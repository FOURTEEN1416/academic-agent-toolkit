#!/usr/bin/env python3
"""评分脚本：comp-modeling P0 基准。读取工作区 MODELING_REPORT.md 并评分。"""
import json, sys, re
from pathlib import Path

def score(workspace: Path) -> dict:
    results = {}
    report = workspace / "MODELING_REPORT.md"
    results["file_MODELING_REPORT.md"] = report.is_file()
    if report.exists():
        text = report.read_text(encoding="utf-8")
        # 1. 子问题覆盖：问题一/二/三 或 "### 问题 N" 标题（归一化空白后去重）
        raw = re.findall(r'问题\s*[一二三123]', text)
        raw += re.findall(r'(?m)^#{2,4}\s*问题\s*[一二三123]', text)
        mentions = sorted({re.sub(r'\s+', '', m) for m in raw})
        results["subproblem_mentions"] = mentions
        results["subproblem_coverage"] = len(mentions)
        results["subproblem_coverage_ok"] = len(mentions) >= 3
        # 2. 能力认领：P1-C1 / P2-C1 / P3-C1 等模式（去重）
        claims = sorted({m for m in re.findall(r'P[1-9]-C[1-9]\d*', text)})
        results["capability_claims"] = claims
        results["capability_claim"] = len(claims)
        results["capability_claim_ok"] = len(claims) >= 3
        # 3. 公式：$$ 块公式 + $ 行内公式
        block = len(re.findall(r'\$\$[^$]+\$\$', text, re.S))
        inline = len(re.findall(r'(?<![$\w])\$[^$\n]+?\$(?!\$)', text))
        results["formula_count"] = block + inline
        results["formula_ok"] = results["formula_count"] >= 2
        # 4. 符号说明表
        results["has_symbols"] = ("符号" in text) or (re.search(r'(?i)\bsymbol', text) is not None)
        # 5. 大小
        results["size_bytes"] = len(text.encode("utf-8"))
        results["size_ok"] = results["size_bytes"] >= 2000
    required_checks = ["file_MODELING_REPORT.md", "subproblem_coverage_ok",
                       "capability_claim_ok", "formula_ok", "has_symbols", "size_ok"]
    results["all_pass"] = all(results.get(c, False) for c in required_checks)
    results["required_checks"] = required_checks
    return results

if __name__ == "__main__":
    ws = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    r = score(ws)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r.get("all_pass") else 1)