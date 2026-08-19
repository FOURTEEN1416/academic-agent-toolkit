#!/usr/bin/env python3
"""核心审计：CodeSucker 融合设计完整性"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.quality_gates import QualityGate, NAMED_CHECKS_REGISTRY


def test_source_materials_gate():
    """验证 source_materials gate（CodeSucker 标准）正常工作"""
    ws = Path(tempfile.mkdtemp())
    base = ws / "source-materials"
    base.mkdir()
    (base / "SOURCE_MATERIALS_MANIFEST.json").write_text(
        '{"schemaVersion": 1, "backend": "vendored-codesucker-core"}',
        encoding="utf-8",
    )
    (base / "files.json").write_text('{"files": []}', encoding="utf-8")
    (base / "selection.json").write_text('{"pages": []}', encoding="utf-8")
    (base / "audit.json").write_text("[]", encoding="utf-8")
    (base / "stats.json").write_text("{}", encoding="utf-8")

    gate = QualityGate(ws)
    result = gate.check_source_materials()
    return result


def test_bridge_consistency():
    """验证 bridge 模式一致性"""
    bridges = ["latex_bridge", "solver_bridge", "citation_bridge", "visual_bridge"]
    results = []
    for name in bridges:
        path = ROOT / "tools" / f"{name}.py"
        if not path.exists():
            results.append((name, False, "文件不存在"))
            continue
        content = path.read_text(encoding="utf-8")
        has_bridge_common = "bridge_common" in content
        has_manifest = "finalize_step_manifest" in content or "write_manifest" in content
        results.append((name, has_bridge_common and has_manifest, None))
    return results


def main() -> int:
    print("=" * 60)
    print("核心审计：CodeSucker 融合设计完整性")
    print("=" * 60)

    # 审计 1: source_materials gate
    print("\n【审计 1】source_materials gate（CodeSucker 标准）")
    try:
        result = test_source_materials_gate()
        status = "✅" if result["ok"] else "❌"
        print(f"  {status} source_materials gate: ok={result['ok']}")
    except Exception as e:
        print(f"  ❌ source_materials gate 测试失败: {e}")

    # 审计 2: bridge 模式一致性
    print("\n【审计 2】bridge 模式一致性")
    bridge_results = test_bridge_consistency()
    for name, ok, error in bridge_results:
        status = "✅" if ok else "❌"
        detail = f" - {error}" if error else ""
        print(f"  {status} {name}: bridge_common + manifest{detail}")

    # 审计 3: 新 gate 覆盖
    print("\n【审计 3】新增 named gates 注册情况")
    new_gates = [
        "paper_consistency",
        "citation_integrity",
        "experiment_reproduc",
        "figure_provenance",
        "compilation_log",
    ]
    for gate in new_gates:
        exists = gate in NAMED_CHECKS_REGISTRY
        status = "✅" if exists else "❌"
        print(f"  {status} {gate}")

    # 审计 4: 三件套完整度
    print("\n【审计 4】UPSTREAM.md 台账完整度")
    upstream_files = list(ROOT.rglob("UPSTREAM.md"))
    print(f"  UPSTREAM.md 文件数: {len(upstream_files)}")
    required_dirs = [
        ROOT / "tools" / "codesucker-core",
        ROOT / "skills" / "paper-write" / "references",
        ROOT / "skills" / "paper-write-zh" / "references",
        ROOT / "skills" / "paper-write-nature" / "references",
        ROOT / "skills" / "comp-paper-zh" / "references",
        ROOT / "skills" / "comp-paper-en" / "references",
        ROOT / "skills" / "nature-figure" / "references",
        ROOT / "skills" / "patent-draft" / "references",
        ROOT / "skills" / "copyright-draft" / "references",
        ROOT / "data",
    ]
    missing = [d for d in required_dirs if not any(
        up.parent == d or up.parent.parent == d for up in upstream_files
    )]
    if missing:
        print(f"  ❌ 缺少 UPSTREAM.md 的目录: {missing}")
    else:
        print(f"  ✅ 所有关键目录都有 UPSTREAM.md")

    print("\n" + "=" * 60)
    print("核心审计完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())