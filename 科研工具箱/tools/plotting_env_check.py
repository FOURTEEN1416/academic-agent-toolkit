#!/usr/bin/env python3
"""科研绘图环境检测器（plotting env doctor）。

一次性回答："这台机器上，哪些绘图技能现在就能用？缺什么？怎么装？"
用法：python tools/plotting_env_check.py [--json]

检测项：
  - graphviz（dot 二进制）：PATH 或默认安装位置
  - mermaid-cli（mmdc）：PATH / ~/.bun/bin / npm 全局；puppeteer 浏览器配置
  - 多模态 LLM 图像生成后端：OPENROUTER_API_KEY 等环境变量（不打印值）
  - 套件 .env 中的视觉/图像后端线索（只报存在性）
对应技能可用性结论 + 一行安装指引。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOT_FALLBACKS = [
    r"C:\Program Files\Graphviz\bin\dot.exe",
    r"C:\Program Files (x86)\Graphviz\bin\dot.exe",
]
MMDC_FALLBACKS = [
    Path.home() / ".bun" / "bin" / "mmdc.exe",
    Path.home() / ".bun" / "bin" / "mmdc",
    Path.home() / ".npm-global" / "mmdc.cmd",
    Path.home() / "AppData" / "Roaming" / "npm" / "mmdc.cmd",
]
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]
ENV_KEYS_IMAGEGEN = ["OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "DASHSCOPE_API_KEY"]


def _find(cands: list[str], which: str) -> str | None:
    p = shutil.which(which)
    if p:
        return p
    for c in cands:
        if Path(c).is_file():
            return c
    return None


def _version(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        out = (r.stdout + r.stderr).strip().splitlines()
        return out[0] if out else None
    except Exception:
        return None


def check() -> dict:
    r: dict = {}

    dot = _find(DOT_FALLBACKS, "dot")
    r["graphviz"] = {
        "found": bool(dot), "path": dot,
        "version": _version([dot, "-V"]) if dot else None,
        "enables": ["graphviz"],
        "install_hint": 'winget install --id Graphviz.Graphviz -e（装后若 PATH 未刷新，重启终端或用全路径）',
    }

    mmdc = _find([str(p) for p in MMDC_FALLBACKS], "mmdc")
    browser = next((b for b in BROWSERS if Path(b).is_file()), None)
    pp = Path.home() / ".mermaid-puppeteer.json"
    r["mermaid_cli"] = {
        "found": bool(mmdc), "path": mmdc, "browser": browser,
        "puppeteer_config_hint": str(pp),
        "enables": ["mermaid-diagram"],
        "install_hint": 'PUPPETEER_SKIP_DOWNLOAD=true bun install -g @mermaid-js/mermaid-cli；'
                        '用系统 Edge/Chrome 时写 ~/.mermaid-puppeteer.json：{"executablePath": "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"}，'
                        '调用加 -p 参数',
    }

    imagegen = {k: bool(os.environ.get(k)) for k in ENV_KEYS_IMAGEGEN}
    r["imagegen_backend"] = {
        "env_detected": imagegen,
        "any": any(imagegen.values()),
        "enables": ["infographics", "scientific-schematics"],
        "note": "生成类 AI 绘图必须有多模态 LLM 图像生成后端（如 OpenRouter 上的 Nano Banana Pro；"
                "质量评审可复用免费视觉模型，如 OpenCode 的 agnes/agnes-2.5-flash）",
        "setup_hint": "export OPENROUTER_API_KEY=sk-...（或配置宿主原生 generate_image 后端）",
    }

    env_file = ROOT / ".env"
    r["kit_env_file"] = {"exists": env_file.is_file(), "note": "存在则可能含宿主视觉后端配置（内容不读取）"}

    per_skill = {}
    for skill, ok in [("graphviz", bool(dot)), ("mermaid-diagram", bool(mmdc)),
                      ("infographics", any(imagegen.values())), ("scientific-schematics", any(imagegen.values()))]:
        per_skill[skill] = "✅ 可用" if ok else "❌ 缺后端（见 install_hint）"
    r["skill_availability"] = per_skill
    r["ok"] = bool(dot) and bool(mmdc) and any(imagegen.values())
    return r


if __name__ == "__main__":
    rep = check()
    if "--json" in sys.argv:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print("== 科研绘图环境检测 ==")
        for k in ("graphviz", "mermaid_cli", "imagegen_backend"):
            info = rep[k]
            print(f"[{'OK' if info.get('found', info.get('any')) else 'MISS'}] {k}")
            for kk, vv in info.items():
                if kk in ("found", "any", "env_detected"):
                    continue
                if isinstance(vv, str) and len(vv) > 110:
                    vv = vv[:110] + "…"
                print(f"    {kk}: {vv}")
        if rep["imagegen_backend"]["env_detected"]:
            print("    env_detected:", rep["imagegen_backend"]["env_detected"])
        print("-- 技能可用性 --")
        for s, v in rep["skill_availability"].items():
            print(f"  {s}: {v}")
        print("总体：", "全部可用" if rep["ok"] else "存在缺失项（见上）")
    sys.exit(0)
