# -*- coding: utf-8 -*-
"""工具链冒烟闸（2026-09-20 建立）。

**为什么需要**：2026-09-20 普查实测 8 个工具脚本零测试引用（含 711 行的
derive_reference_from_docx）——它们静默腐烂无人知：语法坏了、CLI 契约变了，
都要到赛时现场才炸。本闸两层契约：

  1. **编译层（全量）**：tools/ 下全部 140 个 .py 必须 py_compile 通过
     （不执行，零副作用——2026-09-20 实测 data_init --help 会真写文件，
     case_fetcher --help 会重生成数据，故裸跑脚本只做编译级冒烟）；
  2. **CLI 层（argparse 子集）**：声明了 argparse 的工具 `--help` 必须 rc=0
     ——CLI 契约存在且可发现。

附 data_init 防覆盖回归：本工具曾在 2026-09-20 把已演进的 data/README.md
覆盖回 8 月旧模板（34 行现行文档被毁，git checkout 恢复）——修复为默认
不覆盖 + --data-dir 可测化，此处钉住该行为。
"""
import py_compile
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
VENDORED_MARKER = "codesucker-core"  # vendored node 项目内嵌 py 不属本仓工具面

# CLI 层名单：实测 --help rc=0 且无副作用的 argparse 工具。
# 2026-09-22 批次三扩容：11 → 33，每个新入名单工具均逐一实测（rc=0 + 无 traceback
# + git 面无副作用），实测记录见 dev-docs/board/reports/batch3-report.md。
#
# 【裸跑型豁免】（"无参数即执行"形态，不允许在测试中触发）：
#   case_fetcher / codesucker_end_to_end_demo / pdf_ocr / markdown_utils
#     —— 历史豁免（2026-09-20 实测会写文件/重生成数据）；
#   run_cumcm_e2e —— --help 被无视，直接在 Temp 起工作流跑 E2E（批次三实测）；
#   fix_bare_latex_in_md —— 无 --help 契约，位置参数缺省把 "--help" 当文件名（pyc 包装器）。
# 【契约破损豁免】：
#   assets_codesucker_adapter —— 脚本形态 `python tools/xxx.py --help` 即 ModuleNotFoundError
#     （顶层 `from tools.codesucker_bridge import ...` 假设包形态）；
#     `python -m tools.assets_codesucker_adapter --help` 可用（rc=0）。修复归后续轮次。
# 【暂缓】plotting_env_check：--help 实测 rc=0 安全，待批次一（B1-9 argparse 改造）合并后收编。
CLI_HELP_TOOLS = (
    # —— 2026-09-20 首批（11）——
    "derive_reference_from_docx.py", "codesucker_python.py",
    "model_recommender.py", "novelty_checker.py", "check_ledger_drift.py",
    "analyze_latex_template.py", "derive_profile.py",
    "generate_format_reference.py", "secret_scan.py", "lint_ratchet.py",
    "check_duplicate_assets.py",
    # —— 2026-09-22 批次三：检索/治理/检查类（12）——
    "scholar_fetch.py", "citation_checker.py", "arxiv_miner.py",
    "contest_lessons_check.py", "doc_reader.py", "check_provenance.py",
    "context_budget_check.py", "project_health_check.py",
    "check_asset_utilization.py", "watchdog.py", "timeline_96h.py", "score.py",
    # —— 2026-09-22 批次三：docx 链 / 修复器 / 其他零覆盖件（10，与 B3-9 分档合并）——
    "docx_precheck.py", "docx_template_analyze.py", "paper_data_check.py",
    "humanities_review.py", "count_chapter_words.py", "arxiv_fetch.py",
    "screenshot_capture.py", "check_codesucker_licenses.py",
    "fix_skill_manifest_placement.py", "sync_codesucker_core.py",
)


def test_all_tools_compile():
    files = [p for p in sorted(TOOLS_DIR.rglob("*.py"))
             if VENDORED_MARKER not in str(p)]
    assert len(files) >= 100, f"工具面意外缩水: 仅 {len(files)} 个 .py"
    broken = []
    for p in files:
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as exc:
            broken.append(f"{p}: {exc}")
    assert not broken, "编译层冒烟失败:\n" + "\n".join(broken)


def test_cli_help_contract():
    broken = []
    for name in CLI_HELP_TOOLS:
        proc = subprocess.run(
            [sys.executable, str(TOOLS_DIR / name), "--help"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60)
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0 or "Traceback" in out:
            broken.append(f"{name}: rc={proc.returncode}")
    assert not broken, "CLI 契约（--help rc=0）破坏:\n" + "\n".join(broken)


def test_data_init_does_not_clobber_existing(tmp_path):
    """data_init 默认只写缺失文件；--force 才覆盖（2026-09-20 事故回归）。"""
    target = tmp_path / "README.md"
    target.write_text("# 人工维护的现行文档\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "data_init.py"),
         "--data-dir", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60)
    assert proc.returncode == 0, proc.stdout[-400:]
    assert target.read_text(encoding="utf-8") == "# 人工维护的现行文档\n", \
        "data_init 无 --force 仍覆盖了已存在文件"
    assert (tmp_path / "reference_models.json").is_file(), "缺失文件应正常写入"


def test_data_init_dry_run_writes_nothing(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "data_init.py"),
         "--data-dir", str(tmp_path), "--dry-run"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60)
    assert proc.returncode == 0 and "DRY-RUN" in proc.stdout
    assert not list(tmp_path.iterdir()), "dry-run 不得写任何文件"
