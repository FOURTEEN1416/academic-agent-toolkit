# -*- coding: utf-8 -*-
"""竞赛提交打包沙演（确定性、零依赖硬要求：标准库；页数/元数据检查可选依赖 PyMuPDF）。

口径分支（2026-09-22 G2；B-02 修订）：**赛事口径必须显式指定**——
--compliance-profile 为必填参数（comp_rules.json 顶层键，如 comp_cumcm /
comp_huawei），缺省不再默认国赛（"未知默认国赛"通道已删除，B窗 B-02）；
口径解析统一经 engine/contest_profile 唯一加载器，未知键报错并列出可用赛事。

用途：把"融合自检清单 第五/六部分"从人工记忆变成可执行检查——
组包语料收集 → 身份扫描（文件名/目录名/PDF 元数据）→ 体积校验（论文与包均 ≤20MB）
→ MD5 → 流程 checklist。**不代替官方客户端上传**，只做提交前防呆。

用法：
    python scripts/pack_submission.py --workspace <论文工程目录> --compliance-profile comp_cumcm
    python scripts/pack_submission.py --workspace <...> --compliance-profile comp_huawei
    python scripts/pack_submission.py --workspace <...> --zip --out <目录>  # 另生成 .zip 沙演包
    python scripts/pack_submission.py --workspace <...> --json              # 机读输出

退出码：0 = 全部硬项通过；1 = 有硬项失败（体积超限/首页判据不符/身份命中/论文缺失）。

⛔ 关于 .rar：清单要求 WinRAR 单文件 RAR，本脚本**不生成 .rar**（无 rar.exe 时不可行）；
   --zip 仅作**沙演**（验证语料清单、身份、体积、MD5），正式提交仍用 WinRAR 手工压 RAR。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MAX_BYTES = 20 * 1024 * 1024  # 官方：论文与支撑材料各 ≤20MB

# 身份信息线索（通用词 + 学号/队号类数字串）；命中即报警，交由人工确认
IDENTITY_WORDS = [
    "大学", "学院", "学校", "中学", "附中", "校区", "赛区",
    "姓名", "学号", "队号", "队名", "指导老师", "指导教师", "教练",
    "班", "专业", "年级",
]
ID_NUM_RE = re.compile(r"(?<!\d)(?:20\d{2}\d{4,}|[0-9]{8,})(?!\d)")
META_KEYS = ("title", "author", "subject", "keywords", "creator", "producer")

RESULT_NAME_RE = re.compile(r"result[0-9]*\.xlsx$", re.IGNORECASE)
# `_tmp` 是工作区过程稿/探针脚本约定目录：支撑材料硬项要求"内容与论文相符"，
# 过程稿混入语料本身即违规（还夹带时间戳文件名），不得进支撑材料
SKIP_DIRS = {"__pycache__", ".git", ".mh", ".engine", "node_modules", "_archive", "_tmp", "visual_review"}

# 合规数据唯一加载器（G2→B-02）：与 S14/quick_gates 同一 comp_rules.json，
# 经 engine/contest_profile 解析；本脚本不写死任何一族口径、不设默认赛事
CONTEST_PROFILE_FILE = Path(__file__).resolve().parents[3] / "engine" / "contest_profile.py"


def _contest_profile_module():
    import importlib.util
    if not CONTEST_PROFILE_FILE.is_file():
        return None
    spec = importlib.util.spec_from_file_location("engine_contest_profile", CONTEST_PROFILE_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass 处理要求模块已注册
    spec.loader.exec_module(module)
    return module


def load_entry(name: str) -> tuple[object, dict | None, str | None]:
    """按赛事键读档案条目（唯一加载器）；未知ID显式报错，不默认任何赛事。"""
    cp_mod = _contest_profile_module()
    if cp_mod is None:
        return None, None, f"唯一加载器不可达: {CONTEST_PROFILE_FILE}"
    try:
        return cp_mod, cp_mod.load_entry(name), None
    except cp_mod.ContestProfileError as exc:
        return cp_mod, None, str(exc)


def pledge_verdict(page_texts: list[str], profile: dict) -> tuple[str, str]:
    """承诺书页方向判定（纯函数，口径与 skills/_utils/quick_gates.py G1 分支一致）：
    required 前页必须命中标记；forbidden_in_electronic（国赛）与 absent_in_official_template
    （华为杯，官方模板全无承诺书页）必须不命中。"""
    markers = profile.get("pledge_markers") or ["承诺书"]
    mode = str(profile.get("pledge_page") or "")
    scan = page_texts[: int(profile.get("preface_scan_pages", 3))]
    hit = next((m for m in markers for text in scan if m in text), None)
    if mode.startswith("required"):
        if hit:
            return "PASS", f"前 {len(scan)} 页命中承诺书标记「{hit}」（{mode}）"
        return "FAIL", (f"前 {len(scan)} 页未命中承诺书标记（{'/'.join(markers)}）——"
                        f"口径 {mode} 要求承诺书页存在，缺失为交付红线")
    if mode.startswith("forbidden"):
        if hit:
            return "FAIL", f"前 {len(scan)} 页命中「{hit}」——国赛电子版不得含承诺书/编号专用页（系统另收），移除后重编译"
        return "PASS", "电子版前页无承诺书/编号专用页（国赛口径）"
    if mode.startswith("absent"):
        if hit:
            return "FAIL", (f"前 {len(scan)} 页命中「{hit}」——华为杯官方模板无承诺书页（首页为封皮、"
                            "第二页起为摘要/正文；承诺书为校级材料签字盖章扫描件交培养单位，不入论文），"
                            "出现即偏离官方格式，移除后重编译")
        return "PASS", "前页无承诺书（华为杯官方模板结构：封皮+摘要/正文）"
    if not mode:
        return "SKIP", ("档案未提供承诺书方向口径（schema v2 口径在 profiles 维度，"
                        "脚本路径未选择届次/提交形态，或档案记载为 unknown）——"
                        "不判通过/失败，人工确认")
    return "SKIP", f"compliance.pledge_page 口径未识别: {mode!r}（不判通过/失败）"


def _human(n: int) -> str:
    return f"{n/1048576:.2f} MB" if n >= 1048576 else f"{n/1024:.1f} KB"


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _hits(text: str) -> list[str]:
    out = [w for w in IDENTITY_WORDS if w in text]
    if ID_NUM_RE.search(text):
        out.append("长数字串(疑学号/队号)")
    return out


# ------------------------------------------------------------------ 论文电子版
def check_paper(ws: Path, report: dict, profile: dict | None = None,
                has_profiles: bool = False) -> Path | None:
    cands = [ws / "paper" / "main.pdf", ws / "main.pdf"]
    pdf = next((p for p in cands if p.is_file()), None)
    block = {"found": bool(pdf), "path": str(pdf) if pdf else None}
    report["paper"] = block
    if pdf is None:
        block["hard_fail"] = "论文电子版缺失（找 paper/main.pdf 或 main.pdf）"
        return None

    size = pdf.stat().st_size
    block["size"] = size
    block["size_human"] = _human(size)
    block["md5"] = _md5(pdf)
    if size > MAX_BYTES:
        block["hard_fail"] = f"论文 {_human(size)} > 20MB"
    if pdf.suffix.lower() != ".pdf":
        block["hard_fail"] = "电子版必须是 PDF"

    block["identity_in_filename"] = _hits(pdf.name)

    try:  # 可选：页数 / 首页判据 / 承诺书方向 / 元数据（依赖 PyMuPDF）
        try:  # 新版 PyMuPDF 对旧名 fitz 往 stdout 打 deprecation warning，会污染 --json 输出
            import pymupdf as fitz  # type: ignore
        except ImportError:
            import fitz  # type: ignore

        doc = fitz.open(pdf)
        block["pages"] = doc.page_count
        n_scan = int((profile or {}).get("preface_scan_pages", 3))
        texts = [doc[i].get_text() for i in range(min(n_scan, doc.page_count))]
        first = texts[0] if texts else ""
        # cumcmthesis 常把标题排成「摘 要」（中间空格）——去掉空白后再匹配，避免误报 hard_fail
        first_compact = re.sub(r"\s+", "", first)
        block["page1_has_abstract"] = ("摘要" in first_compact) or ("Abstract" in first)
        mode = str((profile or {}).get("pledge_page", ""))
        first_page = str((profile or {}).get("first_page", ""))
        if profile and mode:  # G2：承诺书方向数据驱动（禁含/必含由 comp_rules 裁决）
            verdict, detail = pledge_verdict(texts, profile)
            block["pledge_check"] = {"mode": mode, "verdict": verdict, "detail": detail}
            if verdict == "FAIL":
                block.setdefault("hard_fail", detail)
        else:
            # schema v2：contest 层条目无顶层 compliance 块（口径在 profiles 维度，
            # 脚本路径未选择形态）；如实记 SKIP，不冒充通过也不计失败
            block["pledge_check"] = {"mode": "", "verdict": "SKIP",
                                     "detail": "承诺书方向未机检（档案口径在 profiles 维度"
                                               "未选择或记载为 unknown）——人工确认"}
        if first_page.startswith("cover"):
            # 华为杯首页是封皮页（官方模板：不可删除、4 logo 不能替换），"首页必须是摘要页"
            # 是国赛专属口径，不反向套用
            block["page1_abstract_note"] = (
                "华为杯口径：电子版首页为封皮页（官方模板，4 logo 不能替换），摘要不要求在第 1 页")
        elif mode == "forbidden_in_electronic":
            # 国赛电子版族（数据声明 forbidden_in_electronic 才适用）：第一页必须是摘要专用页
            block["page1_abstract_judged"] = True
            if not block["page1_has_abstract"]:
                block.setdefault("hard_fail", "电子版第一页未检出'摘要'（CUMCM 官方：第一页必须是摘要专用页）")
        else:
            # B-02：档案未声明首页判据的赛事不再套用国赛口径硬判；
            # v2 分档赛事（profiles）未选择形态时如实说明，不冒充已判
            block["page1_abstract_note"] = (
                "该赛事档案按届次/提交形态分档，脚本路径未选择形态——首页判据不机检"
                "（电子版/纸质版口径可能相反）" if has_profiles
                else "该赛事档案未声明首页判据——不套用国赛'首页=摘要页'口径")
        meta = {k: v for k, v in (doc.metadata or {}).items() if v and k.lower() in META_KEYS}
        block["metadata"] = meta
        dirty = {k: _hits(str(v)) for k, v in meta.items() if _hits(str(v))}
        block["metadata_identity_hits"] = dirty
        if dirty:
            block["hard_fail"] = "PDF 文档属性含身份线索（须清空元数据）"
        doc.close()
    except ImportError:
        block["pages"] = None
        block["note"] = "未安装 PyMuPDF，跳过页数/首页/元数据检查（pip install pymupdf）"

    return pdf


# ------------------------------------------------------------------ 支撑材料语料
def collect_support(ws: Path) -> list[Path]:
    files: list[Path] = []

    def add(p: Path) -> None:
        if p.is_file() and not any(part in SKIP_DIRS for part in p.parts):
            files.append(p)

    for p in sorted((ws / "code").rglob("*.py")) if (ws / "code").is_dir() else []:
        add(p)
    for base in (ws, ws / "output"):
        if base.is_dir():
            for p in sorted(base.glob("*.xlsx")):
                if RESULT_NAME_RE.search(p.name):
                    add(p)
    for p in sorted((ws / "figures").glob("*.json")) if (ws / "figures").is_dir() else []:
        add(p)
    for p in sorted((ws / "figures").glob("*.pdf")) if (ws / "figures").is_dir() else []:
        add(p)
    detail = ws / "AI工具使用详情.pdf"
    if detail.is_file():
        add(detail)
    # 去重保序
    seen, uniq = set(), []
    for p in files:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def check_support(ws: Path, report: dict) -> list[Path]:
    files = collect_support(ws)
    total = sum(p.stat().st_size for p in files)
    ident = []
    for p in files:
        rel = p.relative_to(ws).as_posix()
        h = _hits(rel)
        if h:
            ident.append({"path": rel, "hits": h})
    has_ai_detail = any(p.name == "AI工具使用详情.pdf" for p in files)
    report["support"] = {
        "count": len(files),
        "total_size": total,
        "total_size_human": _human(total),
        "has_ai_disclosure_pdf": has_ai_detail,
        "identity_in_names": ident,
        "files": [p.relative_to(ws).as_posix() for p in files],
    }
    if total > MAX_BYTES:
        report["support"]["hard_fail"] = f"支撑材料 {_human(total)} > 20MB"
    if ident:
        report["support"]["hard_fail"] = "支撑材料路径包含身份线索"
    return files


# ------------------------------------------------------------------ 沙演打包
def make_zip(ws: Path, files: list[Path], out_dir: Path, report: dict) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    zp = out_dir / "支撑材料_沙演.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, p.relative_to(ws).as_posix())
    if str(report.get("compliance_profile", "")) != "comp_cumcm":
        note = ("仅沙演；本赛事正式提交格式/上传系统以当届规程为准，"
                "勿默认套用国赛 WinRAR-RAR（云南赛区）口径")
    else:
        note = "仅沙演；正式提交须用 WinRAR 压 .rar（云南赛区要求）"
    report["sandbox_zip"] = {
        "path": str(zp),
        "size": zp.stat().st_size,
        "size_human": _human(zp.stat().st_size),
        "md5": _md5(zp),
        "note": note,
    }
    if zp.stat().st_size > MAX_BYTES:
        report["sandbox_zip"]["hard_fail"] = f"沙演包 {_human(zp.stat().st_size)} > 20MB"
    return zp


# ------------------------------------------------------------------ 输出
def print_report(ws: Path, report: dict) -> None:
    p, s = report.get("paper", {}), report.get("support", {})
    prof = report.get("compliance_profile") or "（未指定）"
    print("=" * 66)
    print("竞赛提交打包沙演 —", ws, " 口径:", prof)
    print("=" * 66)

    print("\n[论文电子版]")
    if p.get("found"):
        print(f"  路径      : {p['path']}")
        print(f"  大小      : {p.get('size_human')}  (限 20MB)")
        if str(prof) != "comp_cumcm":
            print("  ※ 20MB 为 CUMCM 官方上限（清单第五部分）；本赛事当届限额未入库真源，"
                  "此处按防呆底线执行，正式限额以当届规程为准")
        print(f"  MD5       : {p.get('md5')}")
        print(f"  页数      : {p.get('pages')}")
        print(f"  首页含摘要: {p.get('page1_has_abstract')}")
        if p.get("page1_abstract_note"):
            print(f"  ※ {p['page1_abstract_note']}")
        pc = p.get("pledge_check")
        if pc:
            mark = {"PASS": "✅", "FAIL": "⛔"}.get(pc["verdict"], "·")
            print(f"  承诺书页  : {mark} [{pc['verdict']}] {pc['detail']}")
        if p.get("metadata") is not None:
            print(f"  元数据    : {p.get('metadata') or '（空）'}")
    else:
        print("  ⛔ 未找到论文电子版")

    print(f"\n[支撑材料语料]  {s.get('count')} 个文件 / {s.get('total_size_human')} (限 20MB)")
    print(f"  含 AI工具使用详情.pdf : {s.get('has_ai_disclosure_pdf')}")
    if s.get("identity_in_names"):
        print("  ⛔ 路径含身份线索：")
        for it in s["identity_in_names"]:
            print(f"     - {it['path']}  ← {it['hits']}")

    if report.get("sandbox_zip"):
        z = report["sandbox_zip"]
        print(f"\n[沙演包] {z['path']}  {z['size_human']}  MD5={z['md5']}")
        print(f"  ※ {z['note']}")

    print("\n[硬项]")
    fails = [v["hard_fail"] for v in (p, s, report.get("sandbox_zip") or {})
             if isinstance(v, dict) and v.get("hard_fail")]
    if fails:
        for f in fails:
            print(f"  ⛔ {f}")
        print("  结论：存在硬项失败，先修再提交。")
    else:
        # 汇总只宣称实跑过的检查（schema v2 下未选择形态时承诺书/首页判据不机检）
        pc = p.get("pledge_check") or {}
        pledge_ran = pc.get("verdict") in {"PASS", "FAIL"}
        first_ran = bool(p.get("page1_abstract_judged"))
        print("  ✅ 体积/身份 硬检查通过（人工项见 references/submission_checklist.md 对应口径分节）")
        pending = []
        if not pledge_ran:
            pending.append(f"承诺书方向（{pc.get('detail') or '档案无承诺书方向口径'}）")
        if not first_ran:
            pending.append(f"首页摘要判据（{p.get('page1_abstract_note') or '档案未声明首页判据'}）")
        for item in pending:
            print(f"  ⚠ 未机检: {item}——不冒充通过，人工确认")


def main() -> int:
    ap = argparse.ArgumentParser(description="竞赛提交打包沙演（论文+支撑材料；口径按 compliance_profile 分支）")
    ap.add_argument("--workspace", required=True, help="论文工程目录，如 workspaces/cumcm2026A")
    ap.add_argument("--compliance-profile", required=True, metavar="COMP_KEY",
                    help="（必填）按赛事取合规口径（comp_rules.json 顶层键）："
                         "comp_cumcm（国赛：首页摘要、禁承诺书页）/ comp_huawei（华为杯："
                         "承诺书页必含、首页非摘要判据不适用）等。无默认值——"
                         "未指明赛事不得静默套用任何一族口径")
    ap.add_argument("--out", default=None, help="--zip 时的输出目录（默认 <workspace>/_submit）")
    ap.add_argument("--zip", action="store_true", help="另生成沙演 .zip（正式提交仍需 WinRAR 压 RAR）")
    ap.add_argument("--json", action="store_true", help="输出机读 JSON")
    args = ap.parse_args()

    ws = Path(args.workspace).resolve()
    if not ws.is_dir():
        print(f"⛔ 工作区不存在：{ws}")
        return 1

    cp_mod, entry, entry_error = load_entry(args.compliance_profile)
    if entry is None:
        print(f"⛔ 无法解析 compliance profile：{args.compliance_profile}")
        if entry_error:
            print(f"   {entry_error}")
        if cp_mod is not None:
            try:
                print(f"   可用赛事键: {', '.join(cp_mod.known_contest_ids())}")
            except Exception:  # noqa: BLE001
                pass
        return 1
    # schema v2：contest 层条目无顶层 compliance 块，口径经唯一解析器的等效视图派生
    # （当前数据约束带在 profiles 维度，未选择形态时如实 None——下方分档提示承接）
    profile = cp_mod.compliance_profile(entry) if cp_mod is not None else None
    profiled = entry.get("profiles") if isinstance(entry.get("profiles"), list) else []
    if profile is None and profiled:
        forms = "、".join(
            f"{pf.get('edition') or '?'}/{pf.get('submission_form') or '?'}"
            for pf in profiled if isinstance(pf, dict))
        print(f"⚠ 该赛事档案按届次/提交形态分档（{forms}），脚本路径未选择形态——"
              "承诺书方向/首页判据/页数口径不机检（以引擎绑定快照与人工确认承接，不冒充通过）")

    report: dict = {"workspace": str(ws), "compliance_profile": args.compliance_profile}
    pdf = check_paper(ws, report, profile, has_profiles=bool(profiled))
    files = check_support(ws, report)
    if args.zip and files:
        make_zip(ws, files, Path(args.out) if args.out else ws / "_submit", report)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(ws, report)

    hard = any(
        isinstance(v, dict) and v.get("hard_fail")
        for v in (report.get("paper", {}), report.get("support", {}), report.get("sandbox_zip") or {})
    )
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
