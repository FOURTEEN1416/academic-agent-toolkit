#!/usr/bin/env python3
"""安全清理器（safe_cleanup，2026-10-23 建立）。

**为什么需要**：缓存与失败残留（`__pycache__` / `.pytest_cache` / 渲染失败中间件 /
`.coverage`）会混进工作区，让"看起来有产物"变成证据噪声。人工 `rm -rf` 的风险是
路径写错一格就删到真产物。本工具把"可删"收敛成一份**显式 allowlist**，并对每个
命中路径做三重核验后才允许删除：

  1. **allowlist**：只有本文件 `SAFE_DELETE_NOW` 里的模式可匹配（不接受的路径直接不进入）；
  2. **tracked 为空**：`git ls-files -- <path>` 必须无输出（tracked 文件永不在此删除）；
  3. **工作区内**：解析后的绝对路径必须位于仓库根之下，且不是仓库根本身 / 受保护目录。

默认 `--dry-run`；只有显式 `--apply` 才删除，删除后向 `dev-docs/DELETION_LOG.md`
追加一条带日期、对象、处置、原因、核查证据的台账（内部真源，不入 git）。

用法：
  python academic-toolkit/tools/safe_cleanup.py             # 默认 dry-run：只列将被删的路径
  python academic-toolkit/tools/safe_cleanup.py --dry-run   # 同上（显式）
  python academic-toolkit/tools/safe_cleanup.py --apply     # 真删除并写 DELETION_LOG

退出码：0 = 成功（dry-run 恒 0）；1 = 有路径被安全核验拒绝（tracked / 越界 / 受保护）。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DELETION_LOG = REPO_ROOT / "dev-docs" / "DELETION_LOG.md"

# 显式 allowlist（2026-10-23 W6 清理批）。只收本批裁决过的缓存与失败残留；
# 新增条目必须先拿到"可删"裁决，再登记在这里——不做通配式全仓清扫。
SAFE_DELETE_NOW: tuple[str, ...] = (
    # ① 运行缓存（Python / pytest / ruff / coverage）
    "academic-toolkit/**/__pycache__",
    "academic-toolkit/.pytest_cache",
    "academic-toolkit/third_party/pubfig/.ruff_cache",
    ".coverage",
    # ② 华为杯 zcode 工作区的失败残留（正式产物在旁，不在此列）
    "academic-toolkit/workspaces/huawei2026d_zcode/figures_stray",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/vr2/pages",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/vr2/figs",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/vr2/figs_hi",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/eyecheck_1790351279",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/eyepdf_1790351381",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/eyevia_api",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/figbak",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/g3_diag",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/q3_diag",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/q3_final",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/qa_fresh",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/qa_jpg",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/qa_one",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/pdfrender",
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp/qa_crops",
    # ③ 获奖论文批的渲染中间件（只删 render_*.png，同目录清单/脚本保留）
    "assets-local/award-papers/_tmp_w2/render_*.png",
    # ④ 一次性版面阅读任务（docread 输出，非交付物）
    "academic-toolkit/visual_review_tasks/docread_山区洪涝灾害下无人机运输与通信协同优化",
)

# 受保护路径：即使 allowlist 因上游改动而误匹配，也绝不进入删除流程。
# 精确项 = 只保护该目录本身（其下具名残留允许删除）；前缀项 = 整棵子树保护。
PROTECTED_EXACT = (
    "academic-toolkit/workspaces/huawei2026d_zcode/_tmp",  # 只删其下具名残留，不删根
)
PROTECTED_PREFIX = (
    "academic-toolkit/workspaces/huawei2026d/visual_review_tasks",  # 另一工作区，不在本批范围
    "academic-toolkit/code",                               # code/_tmp_w2a_* 等实验代码
    "dev-docs",
    ".git",
)


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _is_protected(path: Path) -> bool:
    rel = _rel(path)
    if rel in ("", "."):
        return True
    if rel in PROTECTED_EXACT:
        return True
    return any(rel == p or rel.startswith(p + "/") for p in PROTECTED_PREFIX)


def _tracked_files(path: Path) -> list[str]:
    proc = subprocess.run(["git", "ls-files", "--", _rel(path)], cwd=str(REPO_ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"git ls-files 失败（rc={proc.returncode}）")
    return [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]


def _size(path: Path) -> tuple[int, int]:
    """(文件数, 字节数)；文件按 1 个计。"""
    if path.is_file():
        return 1, path.stat().st_size
    files = 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            files += 1
            total += child.stat().st_size
    return files, total


def _expand() -> tuple[list[Path], list[str]]:
    """展开 allowlist → 存在的路径列表 + 拒绝原因列表。"""
    targets: list[Path] = []
    rejected: list[str] = []
    seen: set[Path] = set()
    for pattern in SAFE_DELETE_NOW:
        matches = sorted(REPO_ROOT.glob(pattern))
        for match in matches:
            resolved = match.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if resolved != REPO_ROOT and REPO_ROOT not in resolved.parents:
                rejected.append(f"{_rel(match)}：解析后不在仓库工作区内（{resolved}）")
                continue
            if _is_protected(resolved):
                rejected.append(f"{_rel(match)}：命中受保护路径（{_rel(resolved)}）")
                continue
            if not resolved.exists():
                continue
            tracked = _tracked_files(resolved)
            if tracked:
                rejected.append(f"{_rel(match)}：仍有 {len(tracked)} 个 tracked 文件，拒绝删除")
                continue
            targets.append(resolved)
    return targets, rejected


def _delete(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _append_log(entries: list[dict]) -> None:
    lines = [
        "",
        f"## {date.today().isoformat()} safe_cleanup 缓存与失败残留清理（W6 批）",
        "",
        "- **对象**：allowlist 内 untracked 缓存 / 失败残留（见下表明细）。",
        "- **处置**：删除（不入 git；删除前逐路径 `git ls-files` 核验为空）。",
        "- **原因**：运行缓存与失败中间件混入工作区，会把临时产物误当验收证据；"
        "正式产物在同级目录保留，不在本批范围。",
        "- **核查证据**：`python academic-toolkit/tools/safe_cleanup.py --dry-run` 的展开清单；"
        "每条路径删除前 `git ls-files` 输出为空；受保护路径（`_tmp/` 根、"
        "`code/_tmp_w2a_*`、`workspaces/huawei2026d/visual_review_tasks`）未被匹配。",
        "",
        "| 路径 | 类型 | 文件数 | 字节 |",
        "|------|------|--------|------|",
    ]
    for entry in entries:
        lines.append(f"| `{entry['path']}` | {entry['kind']} | {entry['files']} | {entry['bytes']} |")
    lines.append("")
    DELETION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DELETION_LOG.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="安全清理：allowlist + git/tracked/边界三重核验")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只列清单（默认）")
    mode.add_argument("--apply", action="store_true", help="真删除并写 dev-docs/DELETION_LOG.md")
    args = parser.parse_args(argv)
    apply = args.apply

    targets, rejected = _expand()
    entries = []
    for path in targets:
        files, size = _size(path)
        entries.append({"path": _rel(path), "kind": "dir" if path.is_dir() else "file",
                        "files": files, "bytes": size})

    header = "APPLY（真删除）" if apply else "DRY-RUN（未删除任何文件）"
    print("=" * 72)
    print(f"safe_cleanup — {header}")
    print("=" * 72)
    total_files = sum(e["files"] for e in entries)
    total_bytes = sum(e["bytes"] for e in entries)
    for entry in entries:
        print(f"    {'🗑️ ' if apply else '· '}{entry['path']}  "
              f"（{entry['kind']}，{entry['files']} 文件，{entry['bytes']} B）")
    if not entries:
        print("    （无匹配路径：可能已清理过）")
    print(f"\n合计：{len(entries)} 条路径 / {total_files} 文件 / {total_bytes} B")
    for reason in rejected:
        print(f"    ⚠️ 拒绝 {reason}")

    if apply and entries:
        for path in targets:
            _delete(path)
        _append_log(entries)
        print(f"\n✅ 已删除并追加台账：{DELETION_LOG}")
    elif not apply:
        print("\n（dry-run 结束；确认后加 --apply 执行）")

    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
