#!/usr/bin/env python3
"""统一终检器（final_check，2026-10-23 建立）。

**为什么需要**：仓库三条终检命令（全量 pytest / provenance 台账 / 密钥与路径卫生）
此前靠人肉按记忆逐条拼：顺序、cwd、退出码口径各批次不一，失败时只看得到滚屏尾部，
事后无法回答"上一轮到底跑没跑 provenance"。本工具把它们固化为**一条可复现命令**：

    python -m pytest -q                                  （仓库根）
    python academic-toolkit/tools/check_provenance.py    （仓库根）
    python academic-toolkit/tools/secret_scan.py --strict（仓库根）

每次运行把命令、退出码、耗时、输出尾 40 行写 `dev-docs/FINAL_CHECK.json`（内部真源，
不入 git）；任一步非零 → 本脚本 exit 1。**全量 pytest 只允许由本脚本执行**——子代理
手工分段跑全量不能替代这条记录（JSON 里没有分段的"完成"叙事）。

用法：
  python academic-toolkit/tools/final_check.py                 # 前台跑，结果落 JSON
  python academic-toolkit/tools/final_check.py --background    # 分离进程后台跑，立即返回
  python academic-toolkit/tools/final_check.py --status        # 读最近一次结果（ok → exit 0）
  python academic-toolkit/tools/final_check.py --only pytest   # 调试单步（写 .partial.json，ok 恒 false）

退出码：三步全 0 → 0；任一步非零 / 超时 / 无法启动 → 1。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = REPO_ROOT / "dev-docs" / "FINAL_CHECK.json"
PARTIAL_PATH = REPO_ROOT / "dev-docs" / "FINAL_CHECK.partial.json"
LOG_PATH = REPO_ROOT / "dev-docs" / "final_check.log"
TAIL_LINES = 40
DEFAULT_TIMEOUT = 1800  # 单步超时；全量 pytest 实测 ~8 分钟，留足余量

# 固定检查序列：(名称, 展示命令, argv)。cwd 恒为仓库根，不随调用位置漂移。
STEPS: tuple[tuple[str, str, list[str]], ...] = (
    ("pytest", "python -m pytest -q", [sys.executable, "-m", "pytest", "-q"]),
    ("provenance", "python academic-toolkit/tools/check_provenance.py",
     [sys.executable, "academic-toolkit/tools/check_provenance.py"]),
    ("secret_scan", "python academic-toolkit/tools/secret_scan.py --strict",
     [sys.executable, "academic-toolkit/tools/secret_scan.py", "--strict"]),
)


def _tail(text: str, lines: int = TAIL_LINES) -> str:
    return "\n".join((text or "").strip().splitlines()[-lines:])


def _git_head() -> str:
    try:
        proc = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30)
        return (proc.stdout or "").strip() if proc.returncode == 0 else "unknown"
    except OSError:
        return "unknown"


def run(only: str | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    started = time.time()
    steps = []
    for name, label, argv in STEPS:
        if only and name != only:
            continue
        t0 = time.time()
        out = ""
        try:
            proc = subprocess.run(argv, cwd=str(REPO_ROOT), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
            rc, out = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired as exc:
            rc = -1
            partial = exc.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", "replace")
            out = (partial or "") + f"\n[final_check] 超时（>{timeout}s）"
        except OSError as exc:
            rc, out = -1, f"[final_check] 无法启动：{exc}"
        elapsed = round(time.time() - t0, 2)
        steps.append({
            "name": name,
            "command": label,
            "cwd": "repo-root",
            "exit": rc,
            "duration_s": elapsed,
            "ok": rc == 0,
            "tail": _tail(out),
        })
        print(f"[final_check] {name:<12} rc={rc:<3} {elapsed:>8.2f}s  {label}", flush=True)
        if rc != 0:
            print(_tail(out, 12), flush=True)

    result = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "git_head": _git_head(),
        "partial": bool(only),
        "ok": all(step["ok"] for step in steps) and bool(steps) and not only,
        "duration_s": round(time.time() - started, 2),
        "tail_lines": TAIL_LINES,
        "steps": steps,
    }
    # 调试用的 --only 绝不覆盖官方终检记录：分段跑不能冒充终检（写 .partial.json）。
    out_path = PARTIAL_PATH if only else RESULT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    return result


def _spawn_background(timeout: int) -> int:
    """分离进程跑自己；父进程立即返回（Windows DETACHED_PROCESS / POSIX setsid）。"""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG_PATH, "w", encoding="utf-8")
    kwargs: dict = {"cwd": str(REPO_ROOT), "stdin": subprocess.DEVNULL,
                    "stdout": log, "stderr": subprocess.STDOUT, "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = (subprocess.DETACHED_PROCESS
                                   | subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        kwargs["start_new_session"] = True
    try:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                  "--timeout", str(timeout)], **kwargs)
    finally:
        log.close()
    print(f"[final_check] 后台已启动 pid={child.pid}")
    print(f"[final_check] 日志：{LOG_PATH}")
    print(f"[final_check] 结果：{RESULT_PATH}（完成后读取，或 --status）")
    return 0


def _status() -> int:
    if not RESULT_PATH.is_file():
        print(f"[final_check] 未找到 {RESULT_PATH}（尚未运行）")
        return 1
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    print(f"generated_at={result.get('generated_at')} git={result.get('git_head')} "
          f"ok={result.get('ok')} duration={result.get('duration_s')}s")
    for step in result.get("steps", []):
        print(f"  {'✅' if step.get('ok') else '❌'} {step.get('name'):<12} "
              f"rc={step.get('exit')} {step.get('duration_s')}s")
    return 0 if result.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="统一终检（pytest + provenance + secret_scan）")
    parser.add_argument("--background", action="store_true", help="分离进程后台运行后立即返回")
    parser.add_argument("--status", action="store_true", help="读取最近一次 FINAL_CHECK.json")
    parser.add_argument("--only", choices=[name for name, _, _ in STEPS],
                        help="只跑指定一步（写 FINAL_CHECK.partial.json，ok 恒 false；不得冒充终检）")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="单步超时秒数")
    args = parser.parse_args(argv)

    if args.status:
        return _status()
    if args.background:
        return _spawn_background(args.timeout)
    result = run(only=args.only, timeout=args.timeout)
    out_path = PARTIAL_PATH if args.only else RESULT_PATH
    print(f"[final_check] 总耗时 {result['duration_s']}s；结果写入 {out_path}")
    if args.only:
        print("[final_check] 分段调试模式：不作为终检证据（exit 1）")
        return 1
    print(f"[final_check] 结论：{'✅ 全部通过' if result['ok'] else '❌ 存在失败步骤'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
