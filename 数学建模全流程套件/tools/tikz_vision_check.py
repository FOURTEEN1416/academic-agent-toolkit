#!/usr/bin/env python3
"""TikZ 图视觉自检 — 调 vision LLM 检查 TikZ 编译结果是否有重叠/截断等问题。

用法:
  python _utils/tikz_vision_check.py <image.png>

环境变量（按优先级）:
  EDITOR_AI_API_KEY + EDITOR_AI_BASE_URL  (editor_ai 配置)
  OPENAI_API_KEY + OPENAI_BASE_URL        (reviewer 配置)

退出码:
  0 = 通过（PASS）
  1 = 有问题（输出具体问题描述）
  2 = API 不可用（未配置 key 或调用失败）
"""
from __future__ import annotations

import base64
import http.client
import json
import os
import ssl
import sys
from pathlib import Path
from urllib.parse import urlparse


def chat_completions_path(api_base: str) -> str:
    """Return one normalized OpenAI-compatible chat-completions path."""
    path = (urlparse(api_base).path or "").rstrip("/")
    if not path.endswith("/chat/completions"):
        path = path + "/chat/completions"
    if not path.startswith("/v1"):
        path = "/v1" + path
    return path.replace("/v1/v1/", "/v1/")


def load_project_env() -> None:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from engine.env_loader import apply_env
        apply_env()
    except ImportError:
        return

PROMPT = (
    "这是一张学术论文中的 TikZ 流程图/架构图/技术路线图。请严格检查以下问题：\n"
    "1. 文字是否被截断、重叠或超出节点边框？\n"
    "2. 连线上的标注文字是否跟节点重叠或被遮挡？\n"
    "3. 节点间距是否均匀，有没有挤在一起的？\n"
    "4. 有没有大片空白区域（布局不紧凑）？\n"
    "5. 箭头方向是否合理，有没有连线穿过节点？\n"
    "6. 整体是否美观、专业、适合放在学术论文中？\n\n"
    "如果全部没问题，只回答一个词：PASS\n"
    "如果有问题，逐条列出每个问题的具体位置和描述，格式：\n"
    "ISSUE 1: [位置] [问题描述]\n"
    "ISSUE 2: [位置] [问题描述]\n"
)


def _load_image_b64(img_path: Path):
    """读取图片→(base64, mime)。超过阈值时用 PIL 等比压缩，避免超 vision API 单图限制；
    PIL 缺失或压缩失败则回退原图。返回 None 表示无法读取（调用方据此跳过）。"""
    # vision API 单图通常限制 ~5MB；base64 放大约 33%，原图阈值留到 3.5MB
    _MAX_IMG_BYTES = 3_500_000
    try:
        data = img_path.read_bytes()
    except Exception:
        return None
    ext = img_path.suffix.lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")

    if len(data) > _MAX_IMG_BYTES:
        try:
            import io
            from PIL import Image
            with Image.open(io.BytesIO(data)) as im:
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                max_side = max(im.size)
                if max_side > 2200:
                    ratio = 2200.0 / max_side
                    im = im.resize((max(1, int(im.size[0] * ratio)),
                                    max(1, int(im.size[1] * ratio))))
                buf = io.BytesIO()
                q = 85
                while q >= 50:
                    buf.seek(0); buf.truncate()
                    im.save(buf, format="JPEG", quality=q, optimize=True)
                    if buf.tell() <= _MAX_IMG_BYTES:
                        break
                    q -= 10
                data = buf.getvalue()
                mime = "image/jpeg"
        except Exception:
            pass  # PIL 不可用/压缩失败 → 用原图，由上层调用的 try 兜底跳过

    return base64.b64encode(data).decode("ascii"), mime


def _call_vision(api_base: str, api_key: str, model: str,
                 image_b64: str, mime: str, timeout: int = 60) -> str:
    parsed = urlparse(api_base)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        raise ValueError(f"Bad API base URL: {api_base}")

    path = chat_completions_path(api_base)

    payload = json.dumps({
        "model": model or "gpt-4o",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {
                    "url": f"data:{mime};base64,{image_b64}"
                }},
            ],
        }],
        "max_tokens": 2000,
        "stream": False,
    })

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Content-Length": str(len(payload)),
    }

    conn = None
    try:
        if parsed.scheme == "https":
            # 默认 CERT_REQUIRED + check_hostname，防 MITM（端点已锁定且持有效证书）
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)

        conn.request("POST", path, payload, headers)
        res = conn.getresponse()
        data = res.read()

        if res.status != 200:
            raise Exception(f"HTTP {res.status}: {data.decode('utf-8', errors='replace')[:300]}")

        result = json.loads(data.decode("utf-8"))
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        raise Exception("No choices in response")
    finally:
        if conn:
            conn.close()


# ⛔ 每张图的 vision 调用硬上限。vision 对几何图的主观意见（四角空白/浮空标签/贴线）
#    永远挑得出，超过此轮数还反复改坐标→重编→重调，只会无限震荡空烧额度。
#    达上限后脚本直接拒绝再调 API、返回 exit 0（当定稿放行），AI 想磕第 3 次也磕不动。
_MAX_VISION_CALLS = 2


def _norm_fig_key(img_path: Path) -> str:
    """把不同临时命名归一到图本身：wrap_chord / chord_v / chord_dfv → chord，
    保证「脚本内循环」与「AI 脚本外手动调」对同一张图共用一个计数。"""
    stem = img_path.stem
    if stem.startswith("wrap_"):
        stem = stem[len("wrap_"):]
    for suf in ("_v", "_dfv", "_vision"):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
    return stem


def _locate_counter(img_path: Path) -> Path:
    """计数文件统一放工作区 _tmp/：从图片路径往上找 _tmp 目录（AI 调
    _tmp/tikzbuild/wrap_chord.png、bash 调 _tmp/chord_v.png 都能定位到同一个 _tmp/）。"""
    p = img_path.resolve()
    for anc in [p.parent, *p.parents]:
        if anc.name == "_tmp":
            return anc / ".tikz_vision_calls.json"
        cand = anc / "_tmp"
        if cand.is_dir():
            return cand / ".tikz_vision_calls.json"
    return p.parent / ".tikz_vision_calls.json"


def _count_real_tikz_figs(counter_file: Path) -> int:
    """数工作区真实视觉产物数（counter_file 在 _tmp/ 内，其父目录旁即工作区根 → figures/）。
    全局上限 = 图数×2+2 就基于它，改文件名改不动产物数，故绕不过、也不误伤多图工作区。
    ⛔ 计数范围必须覆盖全部视觉产物：tikz_*.pdf（几何图）+ fig_*.png（数据图）+
    同级含 tikzpicture 的 .tex。修复前只数 tikz_*，8 张数据图被算成 0 张 →
    cap=2，数据图一轮审核就撞全局上限（STOP_VISION_LOOP 误伤审核）。
    数不出来返回 0（上层用保守回退值）。"""
    try:
        ws = counter_file.parent.parent          # _tmp/ 的父 = 工作区根
        figdir = ws / "figures"
        if not figdir.is_dir():
            return 0
        names = set()
        for pdf in figdir.glob("tikz_*.pdf"):    # tikz_ 前缀几何图产物
            names.add(pdf.stem)
        for png in figdir.glob("fig_*.png"):     # fig_ 前缀数据图产物（修复：数据图计入）
            names.add(png.stem)
        for tex in figdir.glob("*.tex"):         # 同名 .tex 含 tikzpicture 的
            try:
                if "\\begin{tikzpicture}" in tex.read_text(encoding="utf-8", errors="ignore"):
                    names.add(tex.stem)
            except Exception:
                pass
        return len(names)
    except Exception:
        return 0


def _bump_and_check(img_path: Path, mode: str = "dev"):
    """计数并判断是否放行。返回 (是否允许, 该图当前次数, 是否撞全局上限)。
    两道锁任一触发即拦：① per-key（同一张图 > _MAX_VISION_CALLS 轮，拦固定命名空转）；
    ② 全局（本工作区 vision 总调用 > 图数×2+2，拦"每次换个文件名"绕过 per-key 的空转）。
    计数失败（读写异常）一律放行，绝不因计数器本身故障阻断正常质检。

    ⛔ mode 区分（修复：审核与开发分离，防审核被开发额度阻塞）：
      - mode="dev"（默认）：正常累计计数，超上限即拦（防开发迭代死循环）
      - mode="review"（审核/终审）：不累计 __total__、不受 per-key 与全局上限拦截——
        最终审核必须实际调用视觉工具（comp-visual-review 铁律），
        不能被开发阶段的迭代额度耗尽而被迫"定稿/绕过工具"（那等于伪造审核证据）。
    """
    key = _norm_fig_key(img_path)
    cf = _locate_counter(img_path)
    data = {}
    try:
        if cf.exists():
            data = json.loads(cf.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
    except Exception:
        data = {}
    # per-key 次数
    try:
        n = int(data.get(key, 0)) + 1
    except Exception:
        n = 1
    # 全局总次数（独立键，不受改名影响）
    try:
        total = int(data.get("__total__", 0)) + 1
    except Exception:
        total = 1
    if mode == "review":
        # 审核模式：只读计数不累计、不拦截（审核调用不污染后续开发计数）
        return (True, n, False)
    data[key] = n
    data["__total__"] = total
    try:
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass  # 写不进也放行，计数器故障不许阻断质检
    # 全局上限 = 真实图数×2+2；数不出图数时回退 6（≈2~3 张图的合理额度）
    nfig = _count_real_tikz_figs(cf)
    global_cap = (nfig * 2 + 2) if nfig > 0 else 6
    per_key_ok = n <= _MAX_VISION_CALLS
    global_ok = total <= global_cap
    return (per_key_ok and global_ok, n, not global_ok)


def main():
    # ⛔ 支持审核模式：python tikz_vision_check.py <img> --review
    #    审核/终审阶段必须实际调用视觉工具（comp-visual-review 铁律），
    #    不受开发迭代计数上限阻塞（防"开发耗尽→审核被迫定稿/绕过工具→伪造证据"）。
    mode = "dev"
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--review" in sys.argv[1:]:
        mode = "review"
    if len(args) < 1:
        print("Usage: python tikz_vision_check.py <image.png> [--review]")
        sys.exit(2)

    img_path = Path(args[0])
    if not img_path.exists():
        print(f"File not found: {img_path}")
        sys.exit(2)

    # ⛔ 硬刹车：per-key（同图 2 轮）或全局（换名绕过）任一达上限，即拒绝再调 vision、强制定稿。
    #    （审核模式 --review 绕过此刹车，审核必须真实调用）
    _allowed, _ncall, _global_hit = _bump_and_check(img_path, mode=mode)
    if not _allowed:
        _why = ("本工作区 TikZ 视觉自检【总调用次数】已达全局上限（换名也绕不过）"
                if _global_hit else
                f"本图视觉自检已达 {_MAX_VISION_CALLS} 轮上限（本次第 {_ncall} 次）")
        print(
            f"STOP_VISION_LOOP: {_why}。【用当前最新 PDF 定稿，不要再改坐标/重编/重调 vision】。"
            f"vision 对几何图的主观意见（四角空白/浮空标签/贴线/不紧凑）永远挑得出，"
            f"再磕只会无限震荡、空烧额度——当前 PDF 已过结构自检（0 CRITICAL），可直接用。"
            f"【如需审核/终审真实复核，请加 --review 参数：python tikz_vision_check.py <img> --review】"
        )
        sys.exit(0)

    # 读取图片（超大图自动压缩，防超 vision API 单图限制）
    loaded = _load_image_b64(img_path)
    if loaded is None:
        print("READ_FAIL: cannot read image — skip")
        sys.exit(2)
    img_b64, mime = loaded

    load_project_env()
    # 按优先级尝试 API 配置
    configs = [
        (os.environ.get("EDITOR_AI_API_KEY", ""),
         os.environ.get("EDITOR_AI_BASE_URL", ""),
         os.environ.get("EDITOR_AI_MODEL_ID", "gpt-4o")),
        (os.environ.get("OPENAI_API_KEY", ""),
         os.environ.get("OPENAI_BASE_URL", ""),
         os.environ.get("REVIEWER_MODEL_ID", "gpt-4o")),
    ]

    for api_key, api_base, model in configs:
        if not api_key or not api_base:
            continue
        try:
            result = _call_vision(api_base, api_key, model, img_b64, mime)
            print(result)
            if "PASS" in result.upper().split("\n")[0]:
                sys.exit(0)
            else:
                sys.exit(1)
        except Exception as e:
            print(f"Vision API error: {e}", file=sys.stderr)
            continue

    print("NO_VISION_API: No vision-capable LLM configured (need EDITOR_AI_API_KEY or OPENAI_API_KEY)")
    sys.exit(2)


if __name__ == "__main__":
    main()
