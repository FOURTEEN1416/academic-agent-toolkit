"""批次三 B3-9：公共件/桥接层最小 happy path（tmp_path 沙盒，零副作用）。

17 个零覆盖工具分档（任务包 2026-09-22 B3-9）：
  - 本文件：bridge_common / audit_core / docx_export 三个公共件的 tmp_path 最小 happy path；
  - test_tool_smoke.py：docx 链与修复器等 10 件并入 --help 契约名单（批次三扩容 11 → 33）；
  - 豁免：run_cumcm_e2e / fix_bare_latex_in_md / assets_codesucker_adapter
    （裸跑型或契约破损，理由见 test_tool_smoke.py 名单注释）；
  - 缺陷钉住：docx_template_fill（见文件尾 skip 说明与 batch3-report.md 顺带发现 #4）。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLBOX))

from tools.bridge_common import (  # noqa: E402
    finalize_step_manifest,
    run_command,
    safe_path,
    safe_workspace,
    write_json,
)


# ---------- bridge_common（四条桥共用的基础设施） ----------

def test_bridge_common_safe_path_keeps_paths_inside_workspace(tmp_path):
    workspace = safe_workspace(tmp_path / "ws")
    inside = safe_path(workspace, "figures/fig1.png")
    assert inside == (workspace / "figures" / "fig1.png").resolve()

    with pytest.raises(ValueError, match="outside workspace"):
        safe_path(workspace, "../escape.txt")


def test_bridge_common_write_json_creates_parents_and_roundtrips(tmp_path):
    target = tmp_path / "deep" / "nested" / "manifest.json"
    payload = {"step": "comp-code", "ok": True, "中文键": "值"}
    write_json(target, payload)
    assert json.loads(target.read_text(encoding="utf-8")) == payload


def test_bridge_common_run_command_reports_structured_result(tmp_path):
    result = run_command([sys.executable, "-c", "print('bridge-ok')"], cwd=tmp_path)
    assert result["exitCode"] == 0
    assert "bridge-ok" in result["stdout"]
    assert result["cwd"] == str(tmp_path)


def test_bridge_common_finalize_step_manifest_writes_and_validates(tmp_path):
    workspace = safe_workspace(tmp_path / "ws")
    output = workspace / "figures" / "all_results.json"
    output.parent.mkdir(parents=True)
    output.write_text("{}", encoding="utf-8")

    result = finalize_step_manifest(
        workspace=workspace,
        step_name="comp-code",
        config={"engine": "python"},
        inputs=[],
        outputs=[output],
        backend="python",
        commands=[{"command": "python scripts/build_analysis.py", "returncode": 0}],
        dependencies={},
    )
    manifest_file = workspace / result["path"]
    assert manifest_file.is_file()
    assert result["validation"].get("ok") is True, result["validation"]


# ---------- audit_core（CodeSucker 融合设计审计，自包含 tempfile） ----------

def test_audit_core_runs_self_contained_audit():
    proc = subprocess.run(
        [sys.executable, str(TOOLBOX / "tools" / "audit_core.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    assert proc.returncode == 0, proc.stdout[-400:]
    assert "核心审计完成" in proc.stdout


# ---------- docx_export（Markdown → DOCX 中文学术格式） ----------

def test_docx_export_converts_minimal_markdown(tmp_path):
    source = tmp_path / "paper.md"
    source.write_text("# 测试论文\n\n## 一、引言\n\n这是用于冒烟测试的正文段落。\n", encoding="utf-8")
    output = tmp_path / "paper.docx"

    proc = subprocess.run(
        [sys.executable, str(TOOLBOX / "tools" / "docx_export.py"),
         "--source", str(source), "--output", str(output)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    assert proc.returncode == 0, (proc.stdout + proc.stderr)[-400:]
    assert output.is_file() and output.stat().st_size > 1000, "DOCX 产物缺失或异常小"


# ---------- docx_template_fill（契约测试） ----------
# 历史：旧 pyc 时代本用例因"marshal 回退路径命名空间串扰（docx_export parser 被
# 内嵌复用，--template 被拒）"而 skip（batch3-report.md #4）。2026-09-23 v2.0 收尾
# pyc 退役、真源码反编译重建后缺陷不复现——--template 被正确解析，走业务路径。
# 本机无 docx-cn-engine/node_modules，fill 依赖 Node 渲染 → RuntimeError rc=1。

def test_docx_template_fill_parses_args_and_reports_node_gap(tmp_path):
    """--template 契约：参数被正确解析（不再被串扰 parser 拒绝）；
    Node 引擎缺失时如实报 RuntimeError（rc=1），不伪造成功。"""
    template = tmp_path / "tpl.docx"
    source = tmp_path / "content.md"
    output = tmp_path / "filled.docx"
    template.write_bytes(b"PK\x03\x04")
    source.write_text("# 内容\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(TOOLBOX / "tools" / "docx_template_fill.py"),
         "--template", str(template), "--source", str(source), "--output", str(output)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    # 参数解析通过（旧缺陷是 unrecognized arguments 在解析层即死，走不到业务报错）
    assert "unrecognized arguments" not in combined, combined[-400:]
    assert not output.is_file(), "Node 缺失时不得伪造产物"
    # 业务层如实报 Node 引擎缺口
    assert proc.returncode != 0, combined[-400:]
    assert "Node" in combined or "node" in combined, combined[-400:]
