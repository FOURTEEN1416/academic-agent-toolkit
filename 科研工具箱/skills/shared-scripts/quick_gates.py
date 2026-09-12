"""quick_gates —— 门禁前移轻量编排器（原仓库缺陷修复建议 D3，2026-09-13）。

背景（2026-09-12 工具链审计 §2.4 教训）：直到加载 comp-final-audit 才发现
正文 32 页 > 30 页硬上限；图字号 3.8pt 问题也是晚期才发现导致返工——合规
风险在成稿晚期才暴露，修复成本最高（压页数=动全文）。

定位：把**页数 / 图字号 / 泄漏**三类机检从 step 10/11/14 提取为早跑轻检，
设计挂在 step 5（paper-figure 出图后）与 step 8（comp-paper-zh 成文后）各跑
一次；正式 step 10/11/14 全量闸保持不动（本工具不替代终检）。

实现原则：
- 子进程复用现有闸件（figure_pdf_quality_check / leakage_audit），闸件逻辑
  演进时本编排器自动跟上，不重复造轮子；
- 页数检查直接数 PDF（pypdf），并按"附录/Appendix 标题页"启发式估计正文
  页数（正文 ≤ max-pages，附录官方不限）；
- 早跑阶段产物未齐是常态：输入缺失一律 SKIP（不计失败），工具自身异常记
  ERROR（也不计失败）——只有真实检查 FAIL 才使整体 ok=false、退出码 1。

用法（cwd 任意）：
  python quick_gates.py --workspace ./ws                 # 三类全跑
  python quick_gates.py --workspace ./ws --max-pages 30  # 显式正文页数上限
  python quick_gates.py --workspace ./ws --skip page     # 跳过某类（可重复）
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

UTILS = Path(__file__).resolve().parent
FIGURE_CHECK = UTILS / "figure_pdf_quality_check.py"
LEAKAGE_CHECK = UTILS / "leakage_audit.py"

APPENDIX_MARKERS = ("附录", "appendix", "appendices")


def _page_check(workspace: Path, paper_pdf: Path, max_pages: int) -> tuple[str, str]:
    """页数前移检查：总页数 + 正文页数启发式（附录标题页定位）。"""
    if not paper_pdf.is_file():
        return "SKIP", f"未找到 {paper_pdf.relative_to(workspace) if paper_pdf.is_relative_to(workspace) else paper_pdf}（成文后先编译再跑，或 --paper-pdf 指定路径）"
    try:
        from pypdf import PdfReader
    except ImportError:
        return "SKIP", "pypdf 不可用（pip install pypdf），页数前移检查跳过"
    try:
        reader = PdfReader(str(paper_pdf))
        total = len(reader.pages)
    except Exception as exc:  # noqa: BLE001 —— 损坏 PDF 不该炸掉整个轻检
        return "ERROR", f"PDF 解析失败: {exc}"
    body_pages = None
    for idx, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            continue
        head_lines = [ln.strip().lower() for ln in text[:300].splitlines() if ln.strip()]
        if head_lines and head_lines[0].startswith(APPENDIX_MARKERS):
            body_pages = idx  # 附录标题所在页 = 正文结束后的第一页（0 起计）
            break
    detail = f"总页数 {total}"
    if body_pages is not None:
        detail += f"；正文约 {body_pages} 页（附录起始页启发式定位，第 {body_pages + 1} 页起为附录）"
        if max_pages and body_pages > max_pages:
            return "FAIL", detail + f"；超过正文上限 {max_pages} 页——现在压页比终审时压便宜得多，尽快处理"
        if max_pages:
            detail += f"（上限 {max_pages}）"
        return "PASS", detail
    detail += "；未在前 300 字符内找到附录/Appendix 标题页，正文页数未知——请人工核对（附录很长时本启发式也会漏判）"
    return "WARN", detail


def _figure_check(workspace: Path) -> tuple[str, str]:
    """图字号前移检查：子进程复用 figure_pdf_quality_check（含 D4 豁免逻辑）。"""
    fig_dir = workspace / "figures"
    if not fig_dir.is_dir():
        return "SKIP", "无 figures 目录（出图前跑无意义）"
    proc = subprocess.run(
        [sys.executable, str(FIGURE_CHECK), "figures", "--paper", "paper"],
        cwd=str(workspace), capture_output=True, text=True, timeout=600,
    )
    tail = "\n".join((proc.stdout or "").strip().splitlines()[-6:])
    if proc.returncode == 0:
        return "PASS", "图 PDF 字号/边界/对比度轻检通过" + (f"\n{tail}" if "WARN" in (proc.stdout or "") else "")
    return "FAIL", f"figure_pdf_quality_check 退出码 {proc.returncode}\n{tail}"


def _leakage_check(workspace: Path) -> tuple[str, str]:
    """泄漏前移检查：子进程复用 leakage_audit（code/ + RESULTS.md）。"""
    if not (workspace / "code").is_dir() and not (workspace / "RESULTS.md").is_file():
        return "SKIP", "无 code/ 与 RESULTS.md（无可查泄漏面）"
    proc = subprocess.run(
        [sys.executable, str(LEAKAGE_CHECK), "--codedir", "code", "--results", "RESULTS.md"],
        cwd=str(workspace), capture_output=True, text=True, timeout=300,
    )
    tail = "\n".join((proc.stdout or "").strip().splitlines()[-6:])
    if proc.returncode == 0:
        return "PASS", "泄漏轻检通过"
    if proc.returncode == 2:
        return "SKIP", (proc.stdout or "").strip() or "无 RESULTS/代码/结果JSON 可查"
    return "FAIL", f"leakage_audit 退出码 {proc.returncode}\n{tail}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D3 门禁前移轻量编排器（页数/图字号/泄漏）")
    parser.add_argument("--workspace", required=True, type=Path, help="工作区根目录")
    parser.add_argument("--paper-pdf", type=Path, default=None,
                        help="论文 PDF 路径（默认 <workspace>/paper/main.pdf）")
    parser.add_argument("--max-pages", type=int, default=30,
                        help="正文页数上限（0 = 只报页数不判超限；默认 30，CUMCM 正文规范）")
    parser.add_argument("--skip", action="append", default=[],
                        choices=["page", "figures", "leakage"],
                        help="跳过某类检查（可重复）")
    args = parser.parse_args(argv)

    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        parser.error(f"工作区不存在: {workspace}")
    paper_pdf = args.paper_pdf or (workspace / "paper" / "main.pdf")
    if paper_pdf and not paper_pdf.is_absolute():
        paper_pdf = workspace / paper_pdf

    checks: list[dict[str, str]] = []
    plan = []
    if "page" not in args.skip:
        plan.append(("page_count",
                     lambda: _page_check(workspace, paper_pdf, args.max_pages)))
    if "figures" not in args.skip:
        plan.append(("figure_font", lambda: _figure_check(workspace)))
    if "leakage" not in args.skip:
        plan.append(("leakage", lambda: _leakage_check(workspace)))

    for name, fn in plan:
        try:
            status, detail = fn()
        except Exception as exc:  # noqa: BLE001 —— 编排器自身异常降级为 ERROR 不阻断
            status, detail = "ERROR", f"quick_gates 编排异常: {exc}"
        checks.append({"name": name, "status": status, "detail": detail})

    ok = all(c["status"] != "FAIL" for c in checks)
    report = {
        "tool": "quick_gates",
        "version": "D3-1",
        "workspace": str(workspace),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": "门禁前移轻检：SKIP/ERROR 不计失败；正式全量闸（step 10/11/14）保持不动",
        "ok": ok,
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
