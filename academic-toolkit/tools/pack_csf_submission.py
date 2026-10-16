#!/usr/bin/env python3
"""CSF（全国大学生仿真建模应用挑战赛）四件套命名与形态校验 + 沙演打包。

背景：该赛事要求以**四个独立文件**提交（论文 PDF / 承诺书 / 支撑材料 / 仿真视频），
命名规则为「题号+队伍号+后缀」，后缀分别是 空（论文 pdf）/ cns / fj / fz。
机器可读真源：engine/modex-core/comp_rules.json → contests.comp_csf profiles 约束带。

本工具**只做命名与形态校验**，不判断内容质量；不代填队伍号，不代签承诺书。

用法：
    python tools/pack_csf_submission.py --dir <提交件目录> --track A --team ACSF2600001
    python tools/pack_csf_submission.py --dir ... --track A --team ACSF2600001 --json
    python tools/pack_csf_submission.py --dir ... --track A --team ACSF2600001 --zip <支撑材料目录>

退出码：0 = 全部通过；1 = 有 FAIL 项；2 = 输入不可用（目录缺失等，不冒充通过）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

TRACKS = {"A", "B", "C"}
PAPER_EXT = ".pdf"
PLEDGE_EXT = {".pdf", ".jpg", ".png"}
SUPPORT_EXT = {".zip", ".rar"}
VIDEO_EXT = {".mp4"}
# 匿名红线：出现在任何提交件文件名/PDF 文本属性中的身份信号
IDENTITY_TOKENS = ("姓名", "学号", "学校", "学院", "指导教师", "大学", "学院", "邮箱")


def _fail(problems: list[dict], item: str, msg: str) -> None:
    problems.append({"item": item, "problem": msg})


def _expected(team: str, suffix: str, exts: set[str]) -> list[str]:
    return [team + suffix + e for e in sorted(exts)]


def _find(directory: Path, team: str, suffix: str, exts: set[str]) -> list[Path]:
    return [p for p in directory.iterdir()
            if p.is_file() and p.name in _expected(team, suffix, exts)]


def _pdf_text_hint(path: Path) -> str | None:
    """尽力取 PDF 文本层（pymupdf 缺席则返回 None，不阻断）。"""
    try:
        import fitz  # pymupdf
    except Exception:  # noqa: BLE001
        return None
    try:
        with fitz.open(path) as doc:
            head = doc[0].get_text() if doc.page_count else ""
            return head
    except Exception:  # noqa: BLE001
        return None


def _ffprobe(path: Path) -> dict | None:
    exe = "ffprobe"
    try:
        res = subprocess.run(
            [exe, "-v", "error", "-show_entries",
             "stream=width,height,codec_name", "-show_entries",
             "format=duration,size", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            return None
        data = json.loads(res.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        fmt = data.get("format") or {}
        return {"width": stream.get("width"), "height": stream.get("height"),
                "codec": stream.get("codec_name"),
                "duration_s": float(fmt.get("duration") or 0),
                "size_mb": round(float(fmt.get("size") or 0) / 1048576, 2)}
    except Exception:  # noqa: BLE001
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CSF 四件套命名/形态校验与沙演打包（只读 + 可选 zip）")
    ap.add_argument("--dir", required=True, help="提交件所在目录")
    ap.add_argument("--track", required=True, help="赛道字母 A/B/C（题号的首字母）")
    ap.add_argument("--team", required=True, help="队伍号，如 ACSF2600001（不代填，须用户提供）")
    ap.add_argument("--zip", help="把该目录打成支撑材料包（<队伍号>fj.zip）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    directory = Path(args.dir)
    if not directory.is_dir():
        print(f"[SKIP] 目录不存在：{directory} —— 不冒充通过")
        return 2

    track = args.track.strip().upper()
    team = args.team.strip()
    problems: list[dict] = []
    notes: list[str] = []

    if track not in TRACKS:
        _fail(problems, "track", f"赛道须为 A/B/C，实得 {track!r}")
    if not team.upper().startswith(f"{track}CSF"):
        _fail(problems, "team", f"队伍号 {team!r} 与赛道前缀不匹配（应形如 {track}CSF26xxxxx）")

    # 论文
    papers = _find(directory, team, "", {PAPER_EXT})
    if len(papers) != 1:
        _fail(problems, "论文", f"应恰有 1 个 {team}.pdf，实得 {[p.name for p in papers]}")
    else:
        paper = papers[0]
        head = _pdf_text_hint(paper)
        if head is None:
            notes.append("pymupdf 缺席：跳过论文身份信息与「摘要第一页」文本核验（记为未执行，不冒充通过）")
        else:
            hits = [t for t in IDENTITY_TOKENS if t in head]
            if hits:
                _fail(problems, "论文", f"首页文本含身份信号 {hits}（该赛事要求匿名）")
            if "摘要" not in head:
                _fail(problems, "论文", "首页未见「摘要」——赛事要求摘要必须是论文文件第一页")

    # 承诺书
    pledges = _find(directory, team, "cns", PLEDGE_EXT)
    if len(pledges) != 1:
        _fail(problems, "承诺书", f"应恰有 1 个 {team}cns.(pdf|jpg|png)，实得 {[p.name for p in pledges]}")

    # 视频
    videos = _find(directory, team, "fz", VIDEO_EXT)
    if len(videos) != 1:
        _fail(problems, "视频", f"应恰有 1 个 {team}fz.mp4，实得 {[p.name for p in videos]}")
    else:
        info = _ffprobe(videos[0])
        if info is None:
            notes.append("ffprobe 缺席或读取失败：视频规格未机检（记为未执行）")
        else:
            if info.get("codec") not in (None, "h264", "hevc"):
                _fail(problems, "视频", f"编码 {info.get('codec')} 非 MP4 常规编码")
            if (info.get("height") or 0) < 720:
                _fail(problems, "视频", f"分辨率 {info.get('width')}x{info.get('height')} 低于 1280x720")
            if info.get("duration_s", 0) > 180.5:
                _fail(problems, "视频", f"时长 {info['duration_s']:.1f}s 超过 3 分钟")
            if info.get("size_mb", 0) > 300:
                _fail(problems, "视频", f"大小 {info['size_mb']}MB 超过建议上限 300MB")

    # 支撑材料（可选）
    supports = _find(directory, team, "fj", SUPPORT_EXT)
    if not supports:
        notes.append("未发现支撑材料包（该件官方为可选，确无则可空缺）")

    # 沙演打包
    if args.zip:
        target = Path(args.zip)
        if not target.is_dir():
            _fail(problems, "支撑材料", f"--zip 目录不存在：{target}")
        else:
            out = directory / f"{team}fj.zip"
            import shutil
            try:
                shutil.make_archive(str(out.with_suffix("")), "zip", root_dir=target)
                notes.append(f"已生成支撑材料包：{out.name}")
            except Exception as exc:  # noqa: BLE001
                _fail(problems, "支撑材料", f"打包失败：{exc}")

    result = {"ok": not problems, "dir": str(directory), "track": track, "team": team,
              "problems": problems, "notes": notes}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("[csf-pack] 四件套校验")
        print(f"  目录 {directory} / 赛道 {track} / 队伍号 {team}")
        if problems:
            print(f"  FAIL {len(problems)} 项：")
            for i, item in enumerate(problems, 1):
                print(f"    {i}. [{item['item']}] {item['problem']}")
        else:
            print("  OK 命名与形态合规")
        for note in notes:
            print(f"  · {note}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
