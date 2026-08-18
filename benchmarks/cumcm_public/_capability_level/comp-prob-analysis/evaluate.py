#!/usr/bin/env python3
"""评分脚本：comp-prob-analysis P0 基准。读取工作区文件并评分。"""
import json, sys, re
from pathlib import Path

def score(workspace: Path) -> dict:
    results = {}
    # 1. 文件存在性
    required = ["PROBLEM_ANALYSIS.md", "CAPABILITY_CHECKLIST.json", "DATA_FACTS.json", "DATA_PROFILE.json"]
    for f in required:
        results[f"file_{f}"] = (workspace / f).is_file()
    # 2. 子问题数（兼容多种标题格式：问题一/Problem 1/### P1）
    pa = (workspace / "PROBLEM_ANALYSIS.md")
    if pa.exists():
        text = pa.read_text(encoding="utf-8")
        subprob_count = len(re.findall(
            r'(?m)^#{1,4}\s*(?:问题\s*\d|Problem\s*\d|P\d[^\n]*)',
            text
        ))
        results["subproblem_count"] = subprob_count
        results["subproblem_ok"] = subprob_count >= 3
        # 3. FIGURE_MANIFEST
        results["figure_manifest"] = "<!-- BEGIN FIGURE_MANIFEST -->" in text and "<!-- END FIGURE_MANIFEST -->" in text
        # 4. 大小
        results["size_bytes"] = len(text.encode("utf-8"))
        results["size_ok"] = results["size_bytes"] >= 1500
    # 5. CAPABILITY_CHECKLIST
    if (workspace / "CAPABILITY_CHECKLIST.json").exists():
        ccl = json.loads((workspace / "CAPABILITY_CHECKLIST.json").read_text(encoding="utf-8"))
        caps = ccl.get("capabilities", [])
        results["capability_count"] = len(caps)
        results["capability_ok"] = len(caps) >= 3
    # 6. DATA_FACTS
    if (workspace / "DATA_FACTS.json").exists():
        df = json.loads((workspace / "DATA_FACTS.json").read_text(encoding="utf-8"))
        results["data_facts"] = bool(df.get("variables"))
    # 7. DATA_PROFILE
    if (workspace / "DATA_PROFILE.json").exists():
        dp = json.loads((workspace / "DATA_PROFILE.json").read_text(encoding="utf-8"))
        results["data_profile"] = dp.get("_meta", {}).get("n_files", 0) > 0
    # 综合
    required_checks = ["file_PROBLEM_ANALYSIS.md", "file_CAPABILITY_CHECKLIST.json", "file_DATA_FACTS.json", "file_DATA_PROFILE.json", "subproblem_ok", "figure_manifest", "capability_ok", "size_ok"]
    results["all_pass"] = all(results.get(c, False) for c in required_checks)
    results["required_checks"] = required_checks
    return results

if __name__ == "__main__":
    ws = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    r = score(ws)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r.get("all_pass") else 1)