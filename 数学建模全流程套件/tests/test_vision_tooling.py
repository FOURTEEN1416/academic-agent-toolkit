import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import tikz_vision_check


def test_vision_endpoint_preserves_single_v1_segment():
    assert tikz_vision_check.chat_completions_path("https://example.test/v1") == "/v1/chat/completions"
    assert tikz_vision_check.chat_completions_path("https://example.test") == "/v1/chat/completions"
    assert tikz_vision_check.chat_completions_path("https://example.test/v1/chat/completions") == "/v1/chat/completions"


# ── RED→GREEN：STOP_VISION_LOOP 容量修复 ──────────────────────────────
# 缺陷 1（数据图误伤）：_count_real_tikz_figs 只数 tikz_*.pdf，把 fig_*.png 数据图当 0 张，
#   导致 cap = 0×2+2 = 2，8 张数据图一轮审核就撞全局上限。
# 修复：同目录的 fig_*.png 数据图也应计入真实图数 → cap = 图数×2+2 覆盖全部视觉产物。


def test_count_real_vision_figs_counts_data_pngs(tmp_path):
    """数据图( fig_*.png )必须计入真实图数，否则 8 张图 cap 只有 2、审核被误阻塞。"""
    ws = tmp_path / "ws"
    figdir = ws / "figures"
    figdir.mkdir(parents=True)
    for name in ["fig_q1.png", "fig_q2.png", "fig_q3.png", "fig_q4.png"]:
        (figdir / name).write_bytes(b"fake-png")
    cf = ws / "_tmp" / ".tikz_vision_calls.json"
    n = tikz_vision_check._count_real_tikz_figs(cf)
    # 修复前：只数 tikz_*.pdf → 返回 0；修复后：4 张 fig_*.png 计入 → 返回 4
    assert n == 4, f"期望数据图计入真实图数(4)，实际 {n}"


def test_global_cap_covers_all_vision_products(tmp_path):
    """全局上限必须覆盖 tikz + fig 全部视觉产物：8 张数据图 → cap = 8×2+2 = 18。
    修复前 cap=2（只数 tikz），8 张图在合法两轮审核内就撞上限。"""
    ws = tmp_path / "ws"
    figdir = ws / "figures"
    figdir.mkdir(parents=True)
    for i in range(8):
        (figdir / f"fig_q{i}.png").write_bytes(b"png")
    cf = ws / "_tmp" / ".tikz_vision_calls.json"
    nfig = tikz_vision_check._count_real_tikz_figs(cf)
    cap = nfig * 2 + 2 if nfig > 0 else 6
    assert cap == 18, f"期望 8 张图 cap=18，实际 cap={cap}"


# 缺陷 2（审核被开发额度阻塞）：计数器跨"开发迭代/最终审核"共享，开发耗尽后审核无法再调视觉。
# 修复：_bump_and_check 增加 mode 参数——mode="review" 时不累计、不拦截（审核必须真实调用）。


def test_review_mode_bypasses_global_cap(tmp_path):
    """审核模式(mode=review)必须不受开发迭代的全局上限阻塞——最终审核必须实际调用视觉。"""
    ws = tmp_path / "ws"
    figdir = ws / "figures"
    figdir.mkdir(parents=True)
    img = figdir / "fig_final.png"
    img.write_bytes(b"png")
    cf = ws / "_tmp" / ".tikz_vision_calls.json"
    # 先模拟开发阶段已耗尽：全局计数远超 cap
    cf.parent.mkdir(parents=True, exist_ok=True)
    cf.write_text('{"__total__": 9999, "fig_final": 99}', encoding="utf-8")
    # 审核模式调用必须放行（返回 allowed=True）
    allowed, n, global_hit = tikz_vision_check._bump_and_check(img, mode="review")
    assert allowed, f"审核模式不应被全局上限阻塞：allowed={allowed}, n={n}, global_hit={global_hit}"
    # 审核调用不应继续累计 total（避免一次性审核污染后续开发计数）
    data = json.loads(cf.read_text(encoding="utf-8"))
    assert data.get("__total__") == 9999, f"审核模式不应累计 __total__，实际 {data.get('__total__')}"
