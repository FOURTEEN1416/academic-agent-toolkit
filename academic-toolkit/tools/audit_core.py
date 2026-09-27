#!/usr/bin/env python3
"""核心审计：CodeSucker 融合设计完整性（自包含，无网络无副作用）。

退出码语义：任何一项 ❌ 即退出 1（供脚本化消费）；全绿退出 0。
"""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.quality_gates import QualityGate, NAMED_CHECKS_REGISTRY


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_materials_gate():
    """按现行 source_materials 合同构造最小工作区，验证 gate 的通过路径。

    夹具字段与 engine.quality_gates.check_source_materials 的校验项一一对应
    （7 件必备产物 + manifest 溯源字段 + outputSha256 全覆盖 + 非空渲染）。
    """
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        base = ws / "source-materials"
        base.mkdir()
        page_lines = [{"text": f"line {i}", "kind": "code"} for i in range(50)]
        (base / "files.json").write_text(json.dumps(
            {"files": [{"path": "src/main.py"}]}, ensure_ascii=False), encoding="utf-8", newline="\n")
        (base / "cleaned.json").write_text(json.dumps(
            {"cleaned": [{"path": "src/main.py"}]}, ensure_ascii=False), encoding="utf-8", newline="\n")
        (base / "selection.json").write_text(json.dumps(
            {"pages": [{"lines": page_lines}]}, ensure_ascii=False), encoding="utf-8", newline="\n")
        (base / "audit.json").write_text(json.dumps(
            [{"name": "contract", "status": "ok"}], ensure_ascii=False), encoding="utf-8", newline="\n")
        (base / "stats.json").write_text(json.dumps(
            {"estimatedPages": 1}, ensure_ascii=False), encoding="utf-8", newline="\n")
        (base / "SOURCE_MATERIALS_REPORT.md").write_text(
            "# 源码材料报告\n", encoding="utf-8", newline="\n")
        rendered_rel = "output/paper.docx"
        rendered = ws / rendered_rel
        rendered.parent.mkdir()
        rendered.write_bytes(b"PK\x03\x04minimal-rendered-payload")

        output_files = [
            "source-materials/files.json",
            "source-materials/cleaned.json",
            "source-materials/selection.json",
            "source-materials/audit.json",
            "source-materials/stats.json",
            "source-materials/SOURCE_MATERIALS_REPORT.md",
            rendered_rel,
        ]
        manifest = {
            "schemaVersion": 1,
            "backend": "vendored-codesucker-core",
            "coreVersion": "audit-fixture",
            "coreCommit": "0" * 40,
            "rulesVersion": "audit-fixture",
            "configSha256": "0" * 64,
            "coreSha256": "0" * 64,
            "outputSha256": {rel: _sha256(ws / rel) for rel in output_files},
            "rendered": [rendered_rel],
        }
        (base / "SOURCE_MATERIALS_MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

        return QualityGate(ws).check_source_materials()


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


def find_upstream_files(root: Path) -> list[Path]:
    """rglob 的防护版：悬空 reparse point / 无权限目录跳过而不中断遍历。

    （2026-09-27 实证：workspaces 下一个悬空 junction 让 Path.rglob 直接
    FileNotFoundError，整条审计链崩溃。）
    """
    found: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root, onerror=lambda _exc: None):
        if "UPSTREAM.md" in filenames:
            found.append(Path(dirpath) / "UPSTREAM.md")
    return found


def main() -> int:
    failures = 0
    print("=" * 60)
    print("核心审计：CodeSucker 融合设计完整性")
    print("=" * 60)

    # 审计 1: source_materials gate
    print("\n【审计 1】source_materials gate（CodeSucker 标准）")
    try:
        result = test_source_materials_gate()
        status = "✅" if result["ok"] else "❌"
        failures += 0 if result["ok"] else 1
        print(f"  {status} source_materials gate: ok={result['ok']}")
        if not result["ok"]:
            print(f"      reason: {result.get('reason', '')}")
    except Exception as e:
        failures += 1
        print(f"  ❌ source_materials gate 测试失败: {e}")

    # 审计 2: bridge 模式一致性
    print("\n【审计 2】bridge 模式一致性")
    bridge_results = test_bridge_consistency()
    for name, ok, error in bridge_results:
        status = "✅" if ok else "❌"
        failures += 0 if ok else 1
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
        failures += 0 if exists else 1
        print(f"  {status} {gate}")

    # 审计 4: 三件套完整度
    print("\n【审计 4】UPSTREAM.md 台账完整度")
    upstream_files = find_upstream_files(ROOT)
    print(f"  UPSTREAM.md 文件数: {len(upstream_files)}")
    required_dirs = [
        ROOT / "third_party" / "codesucker-core",
        ROOT / "skills" / "paper-write" / "references",
        ROOT / "skills" / "paper-write-zh" / "references",
        ROOT / "skills" / "paper-write-nature" / "references",
        ROOT / "skills" / "comp-paper-zh" / "references",
        ROOT / "skills" / "comp-paper-en" / "references",
        ROOT / "skills" / "paper-figure-nature" / "references",
        ROOT / "skills" / "patent-draft" / "references",
        ROOT / "skills" / "copyright-draft" / "references",
        ROOT / "data",
    ]
    missing = [d for d in required_dirs if not any(
        up.parent == d or up.parent.parent == d for up in upstream_files
    )]
    if missing:
        failures += 1
        print(f"  ❌ 缺少 UPSTREAM.md 的目录: {missing}")
    else:
        print("  ✅ 所有关键目录都有 UPSTREAM.md")

    print("\n" + "=" * 60)
    print(f"核心审计完成（{'全部通过' if failures == 0 else f'{failures} 项未通过'}）")
    print("=" * 60)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
