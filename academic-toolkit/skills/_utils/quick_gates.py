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
- 页数检查直接数 PDF（pypdf），口径（上限/范围/性质）来自唯一真源
  engine/contest_profile（comp_rules.json，E窗独占数据）——本文件**不再内置
  任何默认口径**（原 DEFAULT_MAX_PAGES=30 兜底即"未知默认国赛"，B-02 已删）；
  无口径时页检 SKIP 并明示原因；
- 合规口径检查按 compliance 块数据驱动（承诺书页方向等），无块即 SKIP；
- 早跑阶段产物未齐是常态：输入缺失一律 SKIP（不计失败），工具自身异常记
  ERROR（也不计失败）——只有真实检查 FAIL 才使整体 ok=false、退出码 1。

同步副本说明：本文件与 skills/shared-scripts/quick_gates.py 为**逐字节同步
副本**（md5 必须一致），加载逻辑唯一真源在 engine/contest_profile.py；
修改任一副本必须同步另一份，禁止再次分叉维护。

用法（cwd 任意）：
  python quick_gates.py --workspace ./ws                 # 三类全跑
  python quick_gates.py --workspace ./ws --max-pages 30  # 显式正文页数上限
  python quick_gates.py --workspace ./ws --skip page     # 跳过某类（可重复）
  python quick_gates.py --workspace ./ws --compliance-profile comp_huawei
      # 按赛事取合规口径（comp_rules.json 顶层键，页数上限/范围/性质 +
      # 承诺书页判定），口径解析统一经 engine/contest_profile。
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
# 唯一加载器：skills/_utils 与 skills/shared-scripts 同深度 → ../../engine/
CONTEST_PROFILE_FILE = UTILS.parent.parent / "engine" / "contest_profile.py"

APPENDIX_MARKERS = ("附录", "appendix", "appendices")


def _contest_profile_module():
    """加载唯一赛事档案解析器（engine/contest_profile.py，std-only 可独立引入）。"""
    import importlib.util
    if not CONTEST_PROFILE_FILE.is_file():
        return None
    spec = importlib.util.spec_from_file_location("engine_contest_profile", CONTEST_PROFILE_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass 处理要求模块已注册
    spec.loader.exec_module(module)
    return module


def _load_entry(name: str) -> tuple[object, dict | None, str | None]:
    """返回 (cp模块, entry, 错误)；未知ID显式报错，不做名称推断、不默认任何赛事。"""
    cp_mod = _contest_profile_module()
    if cp_mod is None:
        return None, None, f"唯一加载器不可达: {CONTEST_PROFILE_FILE}"
    try:
        return cp_mod, cp_mod.load_entry(name), None
    except cp_mod.ContestProfileError as exc:
        return cp_mod, None, str(exc)


def _contest_env_contract(workspace: Path) -> dict | None:
    """读执行环境注入文件 <workspace>/.engine/contest_env（B-CLOSE-01 C→B 接口）。

    由引擎 workflow_runner 在工作流启动时自 bound 档案快照程序写入（五字段），
    LLM 不转录机械字段。PAGE_CAP 为空 = 快照无口径（如实返回 None，页检走
    SKIP 路径，不回退任何默认页限）。文件缺席/不可解析 → None（不猜）。"""
    env_file = workspace / ".engine" / "contest_env"
    if not env_file.is_file():
        return None
    fields: dict[str, str] = {}
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            fields[key.strip()] = value.strip()
    except (OSError, UnicodeDecodeError):
        return None
    raw_cap = fields.get("PAGE_CAP", "")
    if not raw_cap:
        return None
    try:
        cap = int(raw_cap)
    except ValueError:
        return None
    return {"cap": cap, "scope": fields.get("PAGE_SCOPE") or "total",
            "status": fields.get("PAGE_CAP_STATUS") or "unverified",
            "reason": f"执行环境注入口径（bound 快照 {fields.get('CONTEST_ID', '')}）；"
                      "LLM 不转录，引擎程序写入"}


def page_contract(cli_value: int | None, entry: dict | None,
                  cp_mod=None) -> dict:
    """页数口径合同（唯一裁决点在 contest_profile.resolve_operative_cap）。

    优先级：显式 --max-pages（任务显式声明）> 档案 operative 口径。
    任何路径都没有缺省值——无口径返回 cap=None（页检 SKIP，不默认国赛/不猜）。
    """
    if entry is not None and cp_mod is not None:
        return cp_mod.resolve_operative_cap(cp_mod.page_cap_contract(entry), cli_value)
    if cli_value is not None:
        return {"cap": cli_value, "scope": "body", "status": "explicit_argument", "reason": ""}
    return {"cap": None, "scope": "total", "status": "unconfigured",
            "reason": "未配置页数合规口径（--max-pages/--compliance-profile 均未提供；"
                      "不默认任何赛事口径）"}


def _appendix_start_from_outline(reader) -> int | None:
    r"""附录起始的权威锚：hyperref 书签里标题以附录标记起始者取最小程序号。

    「页首行以附录标记起始」启发式在附录标题页版式不匹配时会错锚到更晚的
    标题页（实测同一 PDF 正文 45 页被报成 157 页）；书签由 \appendix 章节
    真源生成，不受版式影响，且不会误撞目录页。"""
    best = None

    def walk(nodes):
        nonlocal best
        for it in nodes:
            if isinstance(it, list):
                walk(it)
                continue
            try:
                title = (it.title or "").strip().lower()
            except Exception:  # noqa: BLE001
                continue
            if title.startswith(APPENDIX_MARKERS):
                try:
                    pg = reader.get_destination_page_number(it)
                except Exception:  # noqa: BLE001
                    continue
                if best is None or pg < best:
                    best = pg

    try:
        walk(reader.outline)
    except Exception:  # noqa: BLE001
        return None
    return best


def _page_check(workspace: Path, paper_pdf: Path, contract: dict) -> tuple[str, str]:
    """页数前移检查：口径感知（body=正文页数 / total=总页数），无口径 SKIP。"""
    cap = contract.get("cap")
    if not cap:
        return "SKIP", contract.get("reason") or "未配置页数合规口径（不默认任何赛事）"
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
    scope = str(contract.get("scope") or "total")
    status_tag = f"［口径性质: {contract.get('status', 'unverified')}］"
    if scope != "body":
        ok = total <= cap
        detail = f"总页数 {total}（上限 {cap}，全PDF计口径）{status_tag}"
        return ("PASS", detail) if ok else ("FAIL", detail + "——超过总页数上限，现在压页比终审时压便宜得多")
    body_pages = _appendix_start_from_outline(reader)
    anchor = "（附录起始取 PDF 书签最早者）" if body_pages is not None else ""
    if body_pages is None:
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
        detail += f"；正文约 {body_pages} 页{anchor or '（附录起始页启发式定位，第 ' + str(body_pages + 1) + ' 页起为附录）'}"
        if body_pages > cap:
            return "FAIL", detail + f"；超过正文上限 {cap} 页——现在压页比终审时压便宜得多，尽快处理{status_tag}"
        return "PASS", detail + f"（正文上限 {cap}）{status_tag}"
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


def _pledge_verdict(page_texts: list[str], profile: dict) -> tuple[str, str]:
    """纯函数：给定 PDF 前 N 页文本，按 profile 判定承诺书页合规。

    - pledge_page=required：前 N 页必须出现承诺书标记；
    - pledge_page=forbidden_in_electronic（国赛 CUMCM）：前 N 页不得出现（系统另收）；
    - pledge_page=absent_in_official_template（华为杯 GMCM）：官方模板全无承诺书页
      （首页为封皮、第二页起为摘要/正文；承诺书为校级材料不入论文），前 N 页不得出现。
    """
    markers = profile.get("pledge_markers") or ["承诺书"]
    mode = str(profile.get("pledge_page") or "")
    scan = page_texts[: int(profile.get("preface_scan_pages", 3))]
    hit = next((m for m in markers for text in scan if m in text), None)
    if mode.startswith("required"):
        if hit:
            return "PASS", (f"前 {len(scan)} 页命中承诺书标记「{hit}」"
                            f"（{mode}）——参赛承诺书页必须存在")
        return "FAIL", (f"前 {len(scan)} 页未找到承诺书标记（{'/'.join(markers)}）——"
                        f"口径 {mode} 要求承诺书页存在，缺失为交付红线")
    if mode.startswith("forbidden"):
        if hit:
            return "FAIL", (f"前 {len(scan)} 页命中「{hit}」——国赛电子版不得含承诺书/编号专用页"
                            "（系统另收），请移除后重编译")
        return "PASS", "电子版前页无承诺书/编号页（国赛口径）"
    if mode.startswith("absent"):
        if hit:
            return "FAIL", (f"前 {len(scan)} 页命中「{hit}」——华为杯官方模板无承诺书页"
                            "（首页为封皮、第二页起为摘要/正文；承诺书为校级材料签字盖章扫描件"
                            "交培养单位，不入论文），出现即偏离官方格式，请移除后重编译")
        return "PASS", "前页无承诺书（华为杯官方模板结构：封皮+摘要/正文）"
    if not mode:
        return "SKIP", ("档案未提供承诺书方向口径（schema v2 口径在 profiles 维度，"
                        "脚本路径未选择届次/提交形态，或档案记载为 unknown）——"
                        "不判通过/失败，人工确认")
    return "SKIP", f"compliance.pledge_page 口径未识别: {mode!r}（不判通过/失败）"


def _pledge_check(workspace: Path, paper_pdf: Path, profile: dict) -> tuple[str, str]:
    """承诺书页判定（需终稿 PDF）：PDF/解析器缺席一律 SKIP，不计失败。"""
    if not paper_pdf.is_file():
        return "SKIP", (f"未找到 {paper_pdf.name}（承诺书页检查需已编译 PDF，"
                        "终审前缺席是常态）")
    try:
        from pypdf import PdfReader
    except ImportError:
        return "SKIP", "pypdf 不可用（pip install pypdf），承诺书页检查跳过"
    try:
        reader = PdfReader(str(paper_pdf))
        n = min(len(reader.pages), int(profile.get("preface_scan_pages", 3)))
        texts = [(reader.pages[i].extract_text() or "") for i in range(n)]
    except Exception as exc:  # noqa: BLE001 —— 损坏 PDF 不炸编排器
        return "ERROR", f"PDF 解析失败: {exc}"
    return _pledge_verdict(texts, profile)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D3 门禁前移轻量编排器（页数/图字号/泄漏）")
    parser.add_argument("--workspace", required=True, type=Path, help="工作区根目录")
    parser.add_argument("--paper-pdf", type=Path, default=None,
                        help="论文 PDF 路径（默认 <workspace>/paper/main.pdf）")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="任务显式页数上限（只影响本次检查；缺省时按 --compliance-profile "
                             "的档案口径；两者皆无则页检 SKIP——无任何默认口径）")
    parser.add_argument("--compliance-profile", default=None, metavar="COMP_KEY",
                        help="按赛事取口径（comp_rules.json 顶层键，如 comp_huawei/"
                             "comp_cumcm）：页数上限/范围/性质 + 承诺书页检查；"
                             "解析统一经 engine/contest_profile，未知键显式报错")
    parser.add_argument("--skip", action="append", default=[],
                        choices=["page", "figures", "leakage", "pledge"],
                        help="跳过某类检查（可重复）")
    args = parser.parse_args(argv)

    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        parser.error(f"工作区不存在: {workspace}")
    paper_pdf = args.paper_pdf or (workspace / "paper" / "main.pdf")
    if paper_pdf and not paper_pdf.is_absolute():
        paper_pdf = workspace / paper_pdf

    entry: dict | None = None
    profile_error: str | None = None
    if args.compliance_profile:
        _, entry, profile_error = _load_entry(args.compliance_profile)
    contract = page_contract(args.max_pages, entry, _contest_profile_module())
    # 口径优先级（B-CLOSE-01）：显式 --max-pages（任务显式声明）> .engine/contest_env
    # （bound 快照冻结口径，引擎程序注入）> --compliance-profile 现盘解析 > SKIP。
    # 快照优先于现盘：任务内一切消费同一份启动时冻结的档案，现盘中途变化不回灌旧任务。
    if args.max_pages is None:
        env_contract = _contest_env_contract(workspace)
        if env_contract is not None:
            contract = env_contract

    checks: list[dict[str, str]] = []
    plan = []
    if "page" not in args.skip:
        plan.append(("page_count",
                     lambda: _page_check(workspace, paper_pdf, contract)))
    if "figures" not in args.skip:
        plan.append(("figure_font", lambda: _figure_check(workspace)))
    if "leakage" not in args.skip:
        plan.append(("leakage", lambda: _leakage_check(workspace)))
    if args.compliance_profile and "pledge" not in args.skip:
        if entry is None:
            plan.append(("pledge_page", lambda msg=profile_error: ("ERROR", msg)))
        elif not isinstance(entry.get("compliance"), dict):
            plan.append(("pledge_page", lambda: ("SKIP",
                "档案条目无顶层 compliance 块（schema v2 合规口径在 profiles 维度，"
                "脚本路径未选择届次/提交形态）——如实跳过不冒充通过；"
                "绑定快照或人工确认承接")))
        else:
            plan.append(("pledge_page",
                         lambda: _pledge_check(workspace, paper_pdf, entry["compliance"])))

    for name, fn in plan:
        try:
            status, detail = fn()
        except Exception as exc:  # noqa: BLE001 —— 编排器自身异常降级为 ERROR 不阻断
            status, detail = "ERROR", f"quick_gates 编排异常: {exc}"
        checks.append({"name": name, "status": status, "detail": detail})

    ok = all(c["status"] != "FAIL" for c in checks)
    report = {
        "tool": "quick_gates",
        "version": "B02-1",
        "workspace": str(workspace),
        "compliance_profile": args.compliance_profile,
        "page_contract": contract,
        "max_pages_effective": contract.get("cap"),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": "门禁前移轻检：SKIP/ERROR 不计失败；正式全量闸（step 10/11/14）保持不动；"
                "无口径页检 SKIP（不默认任何赛事）",
        "ok": ok,
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
