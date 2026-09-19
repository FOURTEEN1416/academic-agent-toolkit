"""双副本镜像一致性守护（_utils ↔ shared-scripts）。

背景
----
`科研工具箱/skills/_utils/` 与 `科研工具箱/skills/shared-scripts/` 是同一批脚本的
两个分发副本：技能经 `_utils` 引用，共享层经 `shared-scripts` 引用。历史上同步
**纯靠人工纪律**（提交信息里频繁出现"双副本同步"字样）。

2026-09-19 治理扫描确认：当时**没有任何机检守护**（`test_dual_copy_consistency.py`
在 git 全历史中从未入库；既有的 `test_skill_smoke.py` 只断言两个目录存在）。
一旦只改一侧就会静默漂移——两个入口行为不一致，且只能靠人眼发现。

语义
----
1. 两目录的**同名文件必须逐字节一致**（sha256）；
2. 允许 `shared-scripts` 独有的 `UPSTREAM.md`（上游溯源台账，仅共享层需要）；
3. 任一方向出现"仅一方存在"的其他文件 → 失败（提示需同步）。

修法：以其中一份为准覆盖另一份，然后复跑本测试。若两侧都有独立编辑，
先人工合并，再同步（不要仅让测试变绿而保留分叉）。
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "skills" / "_utils"
SHARED = ROOT / "skills" / "shared-scripts"

# 仅存在于 shared-scripts 侧（溯源台账，不属于镜像面）
SHARED_ONLY_ALLOWED = frozenset({"UPSTREAM.md"})

# 镜像面：脚本与随附文档（__pycache__ 等缓存不参与）
MIRRORED_SUFFIXES = frozenset({".py", ".md", ".json", ".txt"})


def _names(d: Path) -> set:
    return {f.name for f in d.iterdir()
            if f.is_file() and f.suffix in MIRRORED_SUFFIXES}


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_dual_copy_dirs_present():
    assert UTILS.is_dir(), f"缺目录: {UTILS}"
    assert SHARED.is_dir(), f"缺目录: {SHARED}"


def test_dual_copy_has_no_one_sided_files():
    """任一侧独有的文件 → 说明漏同步。"""
    only_utils = _names(UTILS) - _names(SHARED)
    only_shared = _names(SHARED) - _names(UTILS) - SHARED_ONLY_ALLOWED
    assert not only_utils, (
        f"仅 _utils 有（需同步到 shared-scripts）: {sorted(only_utils)}")
    assert not only_shared, (
        f"仅 shared-scripts 有（需同步到 _utils）: {sorted(only_shared)}")


def test_dual_copy_files_are_byte_identical():
    """同名文件逐字节一致（sha256）。本仓以逐字节自证为原则，不做内容级"等价"判定。"""
    common = sorted((_names(UTILS) & _names(SHARED)))
    assert common, "两个副本目录没有任何共同文件，疑似结构被破坏"
    diffs = [n for n in common
             if _sha256(UTILS / n) != _sha256(SHARED / n)]
    assert not diffs, (
        f"双副本内容不一致（sha256 不同，需同步）: {diffs}")
