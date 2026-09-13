# -*- coding: utf-8 -*-
"""CUMCM 提交打包沙演（确定性、零依赖硬要求：标准库；页数/元数据检查可选依赖 PyMuPDF）。

用途：把"融合自检清单 第五/六部分"从人工记忆变成可执行检查——
组包语料收集 → 身份扫描（文件名/目录名/PDF 元数据）→ 体积校验（论文与包均 ≤20MB）
→ MD5 → 流程 checklist。**不代替官方客户端上传**，只做提交前防呆。

用法：
    python scripts/pack_submission.py --workspace <论文工程目录>            # 只检查，不打包
    python scripts/pack_submission.py --workspace <...> --zip --out <目录>  # 另生成 .zip 沙演包
    python scripts/pack_submission.py --workspace <...> --json              # 机读输出

退出码：0 = 全部硬项通过；1 = 有硬项失败（体积超限/首页非摘要/身份命中/论文缺失）。

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
SKIP_DIRS = {"__pycache__", ".git", ".mh", ".engine", "node_modules", "_archive"}


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
def check_paper(ws: Path, report: dict) -> Path | None:
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

    try:  # 可选：页数 / 首页摘要 / 元数据（依赖 PyMuPDF）
        import fitz  # type: ignore

        doc = fitz.open(pdf)
        block["pages"] = doc.page_count
        first = doc[0].get_text() if doc.page_count else ""
        # cumcmthesis 常把标题排成「摘 要」（中间空格）——去掉空白后再匹配，避免误报 hard_fail
        first_compact = re.sub(r"\s+", "", first)
        block["page1_has_abstract"] = ("摘要" in first_compact) or ("Abstract" in first)
        if not block["page1_has_abstract"]:
            block["hard_fail"] = "电子版第一页未检出'摘要'（官方：第一页必须是摘要专用页）"
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
    report["sandbox_zip"] = {
        "path": str(zp),
        "size": zp.stat().st_size,
        "size_human": _human(zp.stat().st_size),
        "md5": _md5(zp),
        "note": "仅沙演；正式提交须用 WinRAR 压 .rar（云南赛区要求）",
    }
    if zp.stat().st_size > MAX_BYTES:
        report["sandbox_zip"]["hard_fail"] = f"沙演包 {_human(zp.stat().st_size)} > 20MB"
    return zp


# ------------------------------------------------------------------ 输出
def print_report(ws: Path, report: dict) -> None:
    p, s = report.get("paper", {}), report.get("support", {})
    print("=" * 66)
    print("CUMCM 提交打包沙演 —", ws)
    print("=" * 66)

    print("\n[论文电子版]")
    if p.get("found"):
        print(f"  路径      : {p['path']}")
        print(f"  大小      : {p.get('size_human')}  (限 20MB)")
        print(f"  MD5       : {p.get('md5')}")
        print(f"  页数      : {p.get('pages')}")
        print(f"  首页含摘要: {p.get('page1_has_abstract')}")
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
        print("  ✅ 体积/首页/身份 三项硬检查通过（人工项见 references/submission_checklist.md）")


def main() -> int:
    ap = argparse.ArgumentParser(description="CUMCM 提交打包沙演（论文+支撑材料）")
    ap.add_argument("--workspace", required=True, help="论文工程目录，如 workspaces/cumcm2026A")
    ap.add_argument("--out", default=None, help="--zip 时的输出目录（默认 <workspace>/_submit）")
    ap.add_argument("--zip", action="store_true", help="另生成沙演 .zip（正式提交仍需 WinRAR 压 RAR）")
    ap.add_argument("--json", action="store_true", help="输出机读 JSON")
    args = ap.parse_args()

    ws = Path(args.workspace).resolve()
    if not ws.is_dir():
        print(f"⛔ 工作区不存在：{ws}")
        return 1

    report: dict = {"workspace": str(ws)}
    pdf = check_paper(ws, report)
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
