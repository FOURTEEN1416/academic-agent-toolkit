#!/usr/bin/env python3
"""评分脚本：comp-final-audit P0 基准。验收最终交付审计产物。"""
import json
import re
import sys
from pathlib import Path


def score(workspace: Path) -> dict:
    results = {}

    # 1. AUDIT_REPORT.json schema
    audit = workspace / "AUDIT_REPORT.json"
    results["file_AUDIT_REPORT.json"] = audit.is_file()
    audit_ok = False
    if audit.is_file():
        try:
            a = json.loads(audit.read_text(encoding="utf-8"))
            schema_keys = {"workflow_id", "artifacts", "gate_outcomes", "waivers", "delivery_decision"}
            results["audit_schema_keys"] = sorted(schema_keys - set(a.keys()))
            audit_ok = schema_keys <= set(a.keys())
            # artifacts sha256
            arts = a.get("artifacts", [])
            sha_ok = all(
                isinstance(x, dict) and x.get("path") and re.fullmatch(r"[0-9a-fA-F]{64}", str(x.get("sha256", "")))
                for x in arts
            ) if arts else False
            results["artifacts_sha256"] = sha_ok
            results["delivery_decision"] = a.get("delivery_decision")
            results["delivery_ready"] = a.get("delivery_decision") == "ready"
            # gate outcomes
            gates = a.get("gate_outcomes", {})
            results["gate_failures"] = [k for k, v in gates.items() if v != "pass"]
            audit_ok = audit_ok and sha_ok and results["delivery_ready"] and not results["gate_failures"]
        except json.JSONDecodeError:
            results["audit_schema_keys"] = ["invalid_json"]
    results["audit_ok"] = audit_ok

    # 2. REVIEW_EXECUTION_EVIDENCE.json（4 角色）
    rev = workspace / "REVIEW_EXECUTION_EVIDENCE.json"
    results["file_REVIEW_EXECUTION_EVIDENCE.json"] = rev.is_file()
    review_ok = False
    if rev.is_file():
        try:
            r = json.loads(rev.read_text(encoding="utf-8"))
            roles = r.get("roles", {})
            required_roles = {"reviewer", "visual_reviewer", "editor", "final_reviewer"}
            results["review_roles"] = sorted(required_roles - set(roles))
            review_ok = required_roles <= set(roles) and all(
                roles[rr].get("output_sha256") for rr in required_roles if rr in roles
            )
        except json.JSONDecodeError:
            results["review_roles"] = ["invalid_json"]
    results["review_ok"] = review_ok

    # 3. CONSISTENCY_REPORT.json
    cons = workspace / "CONSISTENCY_REPORT.json"
    results["file_CONSISTENCY_REPORT.json"] = cons.is_file()
    cons_ok = False
    if cons.is_file():
        try:
            c = json.loads(cons.read_text(encoding="utf-8"))
            cons_ok = c.get("ok") is True and isinstance(c.get("claims"), list) and len(c["claims"]) > 0
        except json.JSONDecodeError:
            pass
    results["consistency_ok"] = cons_ok

    results["all_pass"] = all([audit_ok, review_ok, cons_ok])
    results["required_checks"] = ["audit_ok", "review_ok", "consistency_ok"]
    return results


if __name__ == "__main__":
    ws = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    r = score(ws)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r.get("all_pass") else 1)