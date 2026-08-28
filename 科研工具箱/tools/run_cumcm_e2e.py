#!/usr/bin/env python3
"""comp_cumcm 端到端工作流执行脚本。"""
import sys
import json
import hashlib
import tempfile
from pathlib import Path

sys.path.insert(0, '.')

from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from engine.opencode_bridge import StepResult


def create_skill_dirs(base):
    skills = [
        "comp-prob-analysis", "comp-literature", "comp-modeling", "comp-code",
        "paper-figure", "paper-figure-drawio", "comp-review", "comp-paper-zh",
        "comp-consistency", "comp-compile-zh", "comp-visual-review", "comp-editor",
        "comp-final-review", "comp-final-audit"
    ]
    for skill in skills:
        (base / skill).mkdir(parents=True, exist_ok=True)
        (base / skill / "SKILL.md").write_text(f"skill: {skill}", encoding="utf-8")
    return base


def write_large_file(path, min_bytes, prefix="# File\n\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = prefix * (min_bytes // len(prefix.encode()) + 1)
    path.write_text(content, encoding="utf-8")
    return path.stat().st_size


def main():
    workspace = Path(tempfile.mkdtemp(prefix="cumcm-e2e-"))
    workspace.mkdir(parents=True, exist_ok=True)
    
    print(f"工作区: {workspace}")
    skills_root = create_skill_dirs(workspace.parent / "skills")
    catalog = json.loads((Path("engine/modex-core/templates.json")).read_text(encoding="utf-8"))
    
    db = workspace / ".engine" / "workflow.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    
    with WorkflowStore(db) as store:
        runner = WorkflowRunner(store, catalog, skills_root)
        workflow = runner.start("comp_cumcm", workspace, {"language": "zh"})
        print(f"工作流启动: {workflow.id}")
        
        # 预先创建所有需要的文件（因为门禁会检查这些文件是否存在）
        (workspace / 'LITERATURE.md').write_text("# 文献调研\n\n" + "\n内容 " * 200, encoding="utf-8")
        (workspace / 'literature').mkdir(parents=True, exist_ok=True)
        (workspace / 'literature' / 'search_evidence.json').write_text(
            json.dumps([{"key": "test2024", "results": [{"title": "Test Paper", "key": "test2024"}]}], indent=2),
            encoding="utf-8"
        )
        (workspace / 'paper').mkdir(parents=True, exist_ok=True)
        (workspace / 'paper' / 'references.bib').write_text(
            "@book{test2024, title={Test Title}, author={Test Author}, year={2024}}\n", encoding="utf-8"
        )
        (workspace / 'figures').mkdir(parents=True, exist_ok=True)
        (workspace / 'figures' / 'all_results.json').write_text(
            json.dumps({"objective": 42.5, "error_rate": 0.1234}), encoding="utf-8"
        )
        (workspace / 'RESULTS.md').write_text("Objective: 42.5\nError rate: 0.1234\n", encoding="utf-8")
        # 注意：不预创建审稿文件。check_review_evidence auto 模式会检测已存在文件决定 solo/full 模式。
        # 预创建 multi-role 文件会导致 comp-review（第一步审稿）被强制进入 full 模式但只产出 solo 文件。
        # 正确做法：comp-review 步骤只创建 solo 文件 → comp-visual-review 补充 full 文件。
        (workspace / 'CONSISTENCY_REPORT.json').write_text(json.dumps({"ok": True, "claims": []}), encoding="utf-8")
        
        step_count = 0
        while True:
            result = runner.next_action(workflow.id)
            
            if result.status == "completed":
                print(f"工作流完成! 共执行 {step_count} 步")
                break
            elif result.status == "failed":
                print(f"工作流失败: {result.message}")
                break
            elif result.status == "waiting_checkpoint":
                print(f"步骤 {step_count}: {result.action.skill_name} 等待检查点批准")
                cp = store._connection.execute(
                    "SELECT id FROM checkpoints WHERE workflow_id = ? ORDER BY created_at DESC LIMIT 1",
                    (workflow.id,)
                ).fetchone()
                if cp:
                    result = runner.approve_checkpoint(cp["id"], {"approved": True})
                    print(f"检查点已批准: {result.status}")
                continue
            elif result.status == "advanced":
                step_count += 1
                action = result.action
                print(f"\n执行步骤 {step_count}: {action.skill_name}")
                
                ws = action.workspace
                
                # 创建所有输出文件（确保足够大）
                for output in action.output_files:
                    path = ws / output
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if output.endswith('.md'):
                        write_large_file(path, 1500, f"# {output}\n\n")
                    elif output.endswith('.json'):
                        # 对于特定JSON文件，创建足够大的内容
                        if 'results' in output.lower() or 'all_results' in output.lower():
                            path.write_text(json.dumps({"status": "ok", "data": "x" * 200, "objective": 42.5, "error_rate": 0.1234}), encoding="utf-8")
                        else:
                            path.write_text(json.dumps({"status": "ok", "data": "x" * 100}), encoding="utf-8")
                    elif output.endswith('.py'):
                        write_large_file(path, 1000, "print('hello')\n")
                    elif output.endswith('.tex'):
                        write_large_file(path, 500, "\\usepackage{amsfonts}\n")
                    elif output.endswith('.pdf'):
                        path.write_bytes(b"%PDF-1.4 test" * 100)
                    else:
                        write_large_file(path, 500, "content\n")
                
                # 确保 RESULTS.md 足够大（comp-code 步骤需要）
                results_md = ws / 'RESULTS.md'
                if results_md.exists() and results_md.stat().st_size < 1000:
                    results_md.write_text("# Results\n\n" + "\n结果数据 " * 200, encoding="utf-8")
                
                # 特殊辅助文件
                if action.skill_name == "comp-literature":
                    (ws / 'literature').mkdir(parents=True, exist_ok=True)
                    (ws / 'literature' / 'search_evidence.json').write_text(
                        json.dumps([{"queries": ["test"], "results": [{"title": "Test"}]}], indent=2), encoding="utf-8"
                    )
                    (ws / 'paper').mkdir(parents=True, exist_ok=True)
                    (ws / 'paper' / 'references.bib').write_text(
                        "@book{test2024, title={Test Title}, author={Test Author}, year={2024}}", encoding="utf-8"
                    )
                
                if action.skill_name == "comp-modeling":
                    modeling_md = ws / 'MODELING_REPORT.md'
                    content = "# 建模报告\n\n## METHOD_CLAIMS_MACHINE\nassumptions:\n  - 数据服从正态分布\n  - 模型在给定约束下最优\nscope:\n  - 适用于小规模优化问题\n  - 计算复杂度 O(n^2)\n\n## 模型推导\n\n"
                    while len(content.encode('utf-8')) < 3000:
                        content += "\n更多扩展内容用于确保文件大小足够 " * 20
                    modeling_md.write_text(content, encoding="utf-8")
                    print(f"  MODELING_REPORT.md size: {modeling_md.stat().st_size} bytes")
                
                # paper-figure 步骤需要创建 PNG 图表
                if action.skill_name in ["paper-figure", "paper-figure-drawio"]:
                    (ws / 'figures').mkdir(parents=True, exist_ok=True)
                    # 尝试使用 PIL 创建有效 PNG
                    try:
                        from PIL import Image
                        img = Image.new('RGB', (100, 100), color='red')
                        img.save(ws / 'figures' / 'figure_1.png', 'PNG')
                    except ImportError:
                        # 如果 PIL 不可用，创建一个有效的最小 PNG
                        import struct, zlib
                        def make_png():
                            sig = b'\x89PNG\r\n\x1a\n'
                            # IHDR
                            ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
                            crc = zlib.crc32(b'IHDR' + ihdr) & 0xffffffff
                            ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr + struct.pack('>I', crc)
                            # IDAT - compressed scanline
                            raw = b'\x00\xff\x00\x00'  # filter byte + RGB
                            comp = zlib.compress(raw)
                            crc = zlib.crc32(b'IDAT' + comp) & 0xffffffff
                            idat_chunk = struct.pack('>I', len(comp)) + b'IDAT' + comp + struct.pack('>I', crc)
                            # IEND
                            crc = zlib.crc32(b'IEND') & 0xffffffff
                            iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', crc)
                            return sig + ihdr_chunk + idat_chunk + iend_chunk
                        (ws / 'figures' / 'figure_1.png').write_bytes(make_png())
                    
                    (ws / 'figures' / 'latex_includes.tex').write_text(
                        "\\usepackage{graphicx}\n\\includegraphics{figure_1}\n" + "\n扩展 " * 50,
                        encoding="utf-8"
                    )
                    print(f"  MODELING_REPORT.md size: {modeling_md.stat().st_size} bytes")
                
                if action.skill_name == "comp-review":
                    (ws / 'COMP_REVIEW.md').write_text("# 审查报告\n\n" + "\n内容 " * 200, encoding="utf-8")
                    (ws / 'COMP_REVIEW_VERDICT.json').write_text(
                        json.dumps({"verdict": "PASS", "fatal_count": 0, "findings": []}), encoding="utf-8"
                    )
                
                if action.skill_name == "comp-visual-review":
                    (ws / 'VISUAL_REVIEW.md').write_text("# 视觉审查报告\n\n" + "\n内容 " * 200, encoding="utf-8")
                    (ws / 'VISUAL_REVIEW_VERDICT.json').write_text(
                        json.dumps({"verdict": "PASS", "status": "pass", "fatal_count": 0, "findings": []}), encoding="utf-8"
                    )
                    # 确保其他审稿文件存在
                    if not (ws / 'EDITOR_CHANGELOG.md').exists():
                        (ws / 'EDITOR_CHANGELOG.md').write_text("# 编辑日志\n\n" + "\n内容 " * 100, encoding="utf-8")
                    if not (ws / 'FINAL_REVIEW.md').exists():
                        (ws / 'FINAL_REVIEW.md').write_text("# 最终复审\n\n" + "\n内容 " * 100, encoding="utf-8")
                    if not (ws / 'FINAL_REVIEW_VERDICT.json').exists():
                        (ws / 'FINAL_REVIEW_VERDICT.json').write_text(
                            json.dumps({"verdict": "PASS", "fatal_count": 0, "findings": []}), encoding="utf-8"
                        )
                    # 创建 REVIEW_EXECUTION_EVIDENCE.json（full 模式需要），使用实际文件哈希
                    _files = {
                        "reviewer": "COMP_REVIEW_VERDICT.json",
                        "visual_reviewer": "VISUAL_REVIEW_VERDICT.json",
                        "editor": "EDITOR_CHANGELOG.md",
                        "final_reviewer": "FINAL_REVIEW_VERDICT.json",
                    }
                    _roles = {}
                    for role, fname in _files.items():
                        fp = ws / fname
                        _hash = hashlib.sha256(fp.read_bytes()).hexdigest()
                        _roles[role] = {
                            "session_id": f"session-{role}",
                            "model": "mock-model",
                            "completed_at": "2026-08-18T00:00:00Z",
                            "output_file": fname,
                            "output_sha256": _hash,
                        }
                    (ws / 'REVIEW_EXECUTION_EVIDENCE.json').write_text(
                        json.dumps({"schema_version": 1, "roles": _roles}, ensure_ascii=False), encoding="utf-8"
                    )
                
                if action.skill_name == "comp-paper-zh":
                    (ws / 'paper').mkdir(parents=True, exist_ok=True)
                    # 创建足够大的论文文件 (至少12000字节)，包含引用和结果数字
                    tex_content = "\\documentclass{ctexart}\n\\begin{document}\n# 论文标题\n\n"
                    tex_content += "\\cite{test2024}\n"  # 添加引用
                    tex_content += "The objective is 42.5 and error rate is 0.1234.\n"  # 添加结果数字
                    # 填充到至少12000字节
                    while len(tex_content.encode('utf-8')) < 12000:
                        tex_content += "\n更多论文内容用于填充文件大小 " * 20
                    tex_content += "\n\\end{document}\n"
                    (ws / 'paper' / 'main.tex').write_text(tex_content, encoding="utf-8")
                    
                    # 确保文献证据文件存在
                    (ws / 'LITERATURE.md').write_text("# 文献调研\n\n" + "\n内容 " * 200, encoding="utf-8")
                    (ws / 'literature').mkdir(parents=True, exist_ok=True)
                    (ws / 'literature' / 'search_evidence.json').write_text(
                        json.dumps([{"key": "test2024", "results": [{"title": "Test Paper", "key": "test2024"}]}], indent=2),
                        encoding="utf-8"
                    )
                    if not (ws / 'paper' / 'references.bib').exists():
                        (ws / 'paper' / 'references.bib').write_text(
                            "@book{test2024, title={Test Title}, author={Test Author}, year={2024}}\n",
                            encoding="utf-8"
                        )
                    
                    # 创建结果文件
                    (ws / 'figures').mkdir(parents=True, exist_ok=True)
                    (ws / 'figures' / 'all_results.json').write_text(
                        json.dumps({"objective": 42.5, "error_rate": 0.1234}), encoding="utf-8"
                    )
                    (ws / 'RESULTS.md').write_text("Objective: 42.5\nError rate: 0.1234\n", encoding="utf-8")
                    
                    print(f"  paper/main.tex size: {(ws / 'paper' / 'main.tex').stat().st_size} bytes")
                
                if action.skill_name == "comp-consistency":
                    (ws / 'CONSISTENCY_REPORT.json').write_text(
                        json.dumps({"ok": True, "claims": []}), encoding="utf-8"
                    )
                
                if action.skill_name == "comp-compile-zh":
                    (ws / 'paper').mkdir(parents=True, exist_ok=True)
                    # 创建一个足够大的 PDF 文件 (至少35000字节)
                    # 直接创建一个大的二进制文件
                    pdf_content = b"%PDF-1.4\n"
                    # 添加足够的伪内容以达到35000字节
                    while len(pdf_content) < 40000:
                        pdf_content += b"stream\nBT /F1 12 Tf 100 700 Td (Page content for testing purposes with lots of text to ensure the PDF is large enough) Tj ET\nendstream\n"
                    pdf_content += b"\nxref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n%d\n%%EOF" % len(pdf_content)
                    (ws / 'paper' / 'main.pdf').write_bytes(pdf_content)
                    
                    # 创建编译日志
                    (ws / 'paper' / 'main.log').write_text("Output written on main.pdf (many pages).\n", encoding="utf-8")
                    print(f"  Created PDF: {(ws / 'paper' / 'main.pdf').stat().st_size} bytes")
                
                if action.skill_name == "comp-final-review":
                    (ws / 'FINAL_REVIEW.md').write_text("# 最终复审\n\n" + "\n内容 " * 200, encoding="utf-8")
                    (ws / 'FINAL_REVIEW_VERDICT.json').write_text(
                        json.dumps({"verdict": "PASS", "fatal_count": 0, "findings": []}), encoding="utf-8"
                    )
                    # 使用实际配置的模型名称（comp-final-review 启用 strict_model_match）
                    from engine.quality_gates import load_configured_role_models
                    configured = load_configured_role_models()
                    _files = {
                        "reviewer": "COMP_REVIEW_VERDICT.json",
                        "visual_reviewer": "VISUAL_REVIEW_VERDICT.json",
                        "editor": "EDITOR_CHANGELOG.md",
                        "final_reviewer": "FINAL_REVIEW_VERDICT.json",
                    }
                    _roles = {}
                    for role, fname in _files.items():
                        fp = ws / fname
                        _hash = hashlib.sha256(fp.read_bytes()).hexdigest()
                        _roles[role] = {
                            "session_id": f"session-{role}",
                            "model": configured.get(role, "mock-model"),
                            "completed_at": "2026-08-18T00:00:00Z",
                            "output_file": fname,
                            "output_sha256": _hash,
                        }
                    (ws / 'REVIEW_EXECUTION_EVIDENCE.json').write_text(
                        json.dumps({"schema_version": 1, "roles": _roles}, ensure_ascii=False), encoding="utf-8"
                    )
                
                if action.skill_name == "comp-final-audit":
                    (ws / 'AUDIT_REPORT.json').write_text(
                        json.dumps({
                            "workflow_id": workflow.id,
                            "artifacts": [{"path": "paper/main.pdf", "sha256": "e" * 64}],
                            "gate_outcomes": {"final_audit": "pass"},
                            "waivers": [],
                            "delivery_decision": "ready"
                        }), encoding="utf-8"
                    )
                
                # 完成步骤
                evidence = {
                    "schema_version": 1,
                    "agent": "OpenCode Desktop",
                    "step_id": action.step_id,
                    "skill_name": action.skill_name,
                    "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
                    "commands": [{"command": "python tools/reviewer_client.py --prompt 审查", "returncode": 0, "cwd": "."}],
                    "inputs": [],
                    "outputs": action.output_files or [],
                }
                # requires_subagent 步骤需要 subagent_session
                if action.skill_name in ["comp-review", "comp-visual-review", "comp-final-review"]:
                    evidence["subagent_session"] = f"ses_{action.skill_name}_test"
                step_result = StepResult(
                    ok=True,
                    artifacts=action.output_files or [],
                    metadata={"execution_evidence": evidence}
                )
                r = runner.complete_step(workflow.id, step_result)
                print(f"  -> {r.status}: {r.message[:100]}")
                
                if r.status == "failed":
                    print(f"步骤失败")
                    break
            else:
                print(f"未知状态: {result.status}")
                break
    
    print(f"\n最终审计报告: {workspace}/AUDIT_REPORT.json")
    if (workspace / "AUDIT_REPORT.json").is_file():
        report = json.loads((workspace / "AUDIT_REPORT.json").read_text(encoding="utf-8"))
        print(f"交付决策: {report.get('delivery_decision')}")
        print(f"产物数量: {len(report.get('artifacts', []))}")
    
    return 0 if (workspace / "AUDIT_REPORT.json").is_file() else 1


if __name__ == "__main__":
    sys.exit(main())
