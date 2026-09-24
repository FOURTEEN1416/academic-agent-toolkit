#!/usr/bin/env python3
"""重复资产注册表守护（check_duplicate_assets，2026-09-20 建立）。

**为什么需要**：2026-09-20 普查实测——tracked 文件中存在大量字节级重复（双份
10.56MB 字体、claude-scientific-writer/modules（2026-09 改名 paper-writing-clinical/modules）
与 sci-* 族的多重复制等），其中
仅 `_utils↔shared-scripts` 一组有守护测试（test_dual_copy_consistency.py）。
其余重复**全部无登记、无守护**：新一轮误复制（如又一个 10MB 级资产被复制进
技能目录）不会被发现，仓库体积只涨不降。

**机制（台账棘轮，与 lint_ratchet 同哲学）**：
  1. 对 tracked 文件（git ls-files，≥4KB，排除 releases/ 快照与 .pyc 分发件）
     计算 md5，找出全部字节级重复组；
  2. 每个重复组必须已在 `data/duplicate_assets_registry.json` **登记并给出理由**
     （"有意为之"的重复：双副本设计/技能自包含分发/上游 vendor 形态……）；
  3. **未登记的新重复组 → FAIL**（棘轮：只拦截新增，不追溯存量）；
  4. 已登记但已消解的组 → 提示可从台账移除（方向正确，不拦截）。

**批判式不采纳**：不自动去重（改符号链接/共享目录会破坏"技能自包含可独立
拷走"的设计原则）；不按相似度查重（只有字节级重复是零歧义的）。

用法：
  python tools/check_duplicate_assets.py            # 人读报告
  python tools/check_duplicate_assets.py --strict   # 有未登记重复组 → exit 1
  python tools/check_duplicate_assets.py --json
  python tools/check_duplicate_assets.py --emit-registry   # 以当前实况生成台账草稿

台账条目 schema：{"paths": [...], "reason": "...", "wasted_bytes": N}
（paths 按字典序；wasted_bytes = size×(份数-1)，供清理优先级排序）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

TOOLBOX_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLBOX_ROOT.parent
REGISTRY_PATH = TOOLBOX_ROOT / "data" / "duplicate_assets_registry.json"

THRESHOLD_BYTES = 4096          # <4KB 的重复不值得台账治理（噪声大于收益）
EXCLUDED_PREFIXES = ("releases/",)   # dated 发布快照 = 不可变历史，不参与
EXCLUDED_SUFFIXES = (".pyc",)        # 分发件随同名 .py 真源走，重复属设计


def _tracked_files() -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "-c", "core.quotepath=false", "ls-files", "-z"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        print(f"[dup-assets] git ls-files 失败: {(proc.stderr or '')[:200]}",
              file=sys.stderr)
        raise SystemExit(1)
    return [f for f in (proc.stdout or "").split("\0") if f.strip()]


def _md5(path: Path) -> str:
    """内容哈希（**换行规范化**，2026-09-24）。

    ⚠️ 必须先规范化 CRLF→LF 再哈希：Windows 检出（core.autocrlf=true）为 CRLF、
    Linux/CI 检出为 LF——同一 tracked 文件在两平台磁盘内容不同，会导致
    "本机漏检、CI 命中"的假绿/假红分裂（2026-09-24 实锤：CI 自 W3e 起连续红，
    本机全绿，重复组全系 tracked 文本件）。规范化是确定性变换：两份文件规范化后
    相同 ⇔ 其 LF 形态相同，跨平台判定一致；二进制件内容真实不同时规范化后
    大概率仍不同，不引入误报。
    """
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk.replace(b"\r\n", b"\n"))
    return h.hexdigest()


def find_duplicate_groups(files: list[str]) -> list[dict]:
    """tracked 相对路径列表 → 重复组列表（每组 paths 字典序 + wasted_bytes）。"""
    by_hash: dict[str, list[tuple[int, str]]] = {}
    for rel in files:
        rel_posix = rel.replace("\\", "/")
        if any(rel_posix.startswith(p) for p in EXCLUDED_PREFIXES):
            continue
        if any(rel_posix.endswith(s) for s in EXCLUDED_SUFFIXES):
            continue
        path = REPO_ROOT / rel
        try:
            size = path.stat().st_size
            if size < THRESHOLD_BYTES:
                continue
            digest = _md5(path)
        except OSError:
            continue
        by_hash.setdefault(digest, []).append((size, rel_posix))
    groups = []
    for digest, entries in by_hash.items():
        if len(entries) < 2:
            continue
        size = entries[0][0]
        paths = sorted(p for _, p in entries)
        groups.append({"md5": digest, "size": size, "paths": paths,
                       "wasted_bytes": size * (len(paths) - 1)})
    groups.sort(key=lambda g: (-g["wasted_bytes"], g["paths"][0]))
    return groups


def _classify_reason(paths: list[str]) -> str:
    """emit 模式的理由草稿分类（人工复核后可改写）。"""
    all_paths = "\n".join(paths)
    if "_utils/" in all_paths and "shared-scripts/" in all_paths:
        return "双副本设计（_utils↔shared-scripts，已有 test_dual_copy_consistency 守护同步）"
    if "paper-writing-clinical/modules/" in all_paths:
        return "paper-writing-clinical 技能族自带模块的多技能复用（上游形态保持，不就地重构）"
    if all(p.rsplit("/", 1)[-1] == "LICENSE" for p in paths):
        return "同源开源许可证法定文本（逐字一致属合规要求）"
    if all(p.endswith(".ttf") or p.endswith(".otf") for p in paths):
        return "字体文件随技能自包含分发（技能可独立拷走的代价，有意为之）"
    if any(p.endswith((".png", ".jpg", ".svg", ".R")) for p in paths):
        return "示例图/示例脚本资产随技能自包含分发"
    if "/scripts/" in all_paths and all(p.endswith(".py") for p in paths):
        return "技能族共享脚本随技能自包含分发（spine/ars/sci 等族各持一份，可独立拷走）"
    if "/templates/" in all_paths or all(p.endswith((".html", ".md")) for p in paths):
        return "共享模板/参考文档随技能自包含分发"
    return "TODO-人工确认（emit 草稿分类未覆盖，请补真实理由）"


def evaluate(groups: list[dict], registry: list[dict]) -> dict:
    """纯函数：实况重复组 vs 台账 → 判定（可单测）。"""
    registered = {tuple(g.get("paths", [])) for g in registry}
    current = {tuple(g["paths"]) for g in groups}
    unregistered = [g for g in groups if tuple(g["paths"]) not in registered]
    resolved = [g for g in registry if tuple(g.get("paths", [])) not in current]
    return {"unregistered": unregistered, "resolved": resolved,
            "registered_ok": len(current) - len(unregistered),
            "ok": not unregistered}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="重复资产注册表守护（台账棘轮）")
    parser.add_argument("--strict", action="store_true", help="未登记重复组 → exit 1")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--emit-registry", action="store_true",
                        help="以当前实况生成台账草稿（理由为自动分类，须人工复核）")
    args = parser.parse_args(argv)

    groups = find_duplicate_groups(_tracked_files())
    if args.emit_registry:
        REGISTRY_PATH.write_text(json.dumps({
            "threshold_bytes": THRESHOLD_BYTES,
            "excluded_prefixes": list(EXCLUDED_PREFIXES),
            "excluded_suffixes": list(EXCLUDED_SUFFIXES),
            "groups": [{"paths": g["paths"], "size": g["size"],
                        "wasted_bytes": g["wasted_bytes"],
                        "reason": _classify_reason(g["paths"])} for g in groups],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        total_waste = sum(g["wasted_bytes"] for g in groups)
        print(f"[dup-assets] 台账草稿已生成：{len(groups)} 组，"
              f"重复体积 {total_waste / 1e6:.1f} MB → {REGISTRY_PATH.name}"
              f"（理由须人工复核，TODO-人工确认 条目必须改写）")
        return 0

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["groups"] \
        if REGISTRY_PATH.is_file() else []
    verdict = evaluate(groups, registry)
    if args.as_json:
        print(json.dumps({**verdict,
                          "total_groups": len(groups),
                          "total_wasted_bytes": sum(g["wasted_bytes"] for g in groups)},
                         ensure_ascii=False, indent=2))
        # json 模式下 groups 原样可序列化（已滤 md5? 保留无妨——jsonify 已含）
    else:
        waste = sum(g["wasted_bytes"] for g in groups)
        print("=" * 64)
        print("重复资产注册表守护（check_duplicate_assets）")
        print("=" * 64)
        print(f"实况：{len(groups)} 组字节级重复（≥{THRESHOLD_BYTES}B），"
              f"重复体积合计 {waste / 1e6:.1f} MB")
        if verdict["unregistered"]:
            print(f"\n❌ 未登记的新重复组 {len(verdict['unregistered'])} 组：")
            for g in verdict["unregistered"]:
                print(f"    [{g['wasted_bytes'] / 1e6:.2f} MB 浪费] "
                      f"{', '.join(g['paths'][:3])}"
                      f"{' …' if len(g['paths']) > 3 else ''}")
            print("    处置：确属有意 → 登记台账并给理由；无意 → 删除多余副本。")
        else:
            print("\n✅ 无未登记重复组（棘轮内）")
        if verdict["resolved"]:
            print(f"\nℹ️ 台账中 {len(verdict['resolved'])} 组已消解"
                  f"（文件分叉/删除），可从台账移除：")
            for g in verdict["resolved"][:5]:
                print(f"    {', '.join(g.get('paths', [])[:3])}")
    return 1 if (args.strict and not verdict["ok"]) else 0


if __name__ == "__main__":
    sys.exit(main())
