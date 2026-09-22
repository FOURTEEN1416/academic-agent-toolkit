import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import host_visual_review

# ── 2026-09-23 换驱动（第三次用户裁定）：外部 vision API → 宿主独立窗口 └──
# 旧实现的 API 端点归一化（chat_completions_path）随 HTTP 驱动一并移除：
# 宿主独立窗口驱动不发起任何网络调用、不读取任何 API key。


def test_no_api_key_semantics_in_driver_sources():
    """换驱动锁定：视觉质检工具源码不得再含外部 API key / HTTP 端点语义。"""
    for name in ("tikz_vision_check.py", "data_fig_vision_check.py",
                 "drawio_vision_check.py", "host_visual_review.py"):
        text = (ROOT / "tools" / name).read_text(encoding="utf-8")
        for banned in ("EDITOR_AI_API_KEY", "OPENAI_API_KEY", "SENSENOVA_API_KEY",
                       "image_url", "chat/completions", "Bearer"):
            assert banned not in text, f"{name} 不应再含外部 API 语义: {banned}"


# ── STOP_VISION_LOOP 防死循环治理（自旧实现原样保留，回归锁定） ──────────


def test_count_real_vision_figs_counts_data_pngs(tmp_path):
    """数据图( fig_*.png )必须计入真实图数，否则 8 张图 cap 只有 2、审核被误阻塞。"""
    ws = tmp_path / "ws"
    figdir = ws / "figures"
    figdir.mkdir(parents=True)
    for name in ["fig_q1.png", "fig_q2.png", "fig_q3.png", "fig_q4.png"]:
        (figdir / name).write_bytes(b"fake-png")
    cf = ws / "_tmp" / ".tikz_vision_calls.json"
    n = host_visual_review._count_real_tikz_figs(cf)
    assert n == 4, f"期望数据图计入真实图数(4)，实际 {n}"


def test_global_cap_covers_all_vision_products(tmp_path):
    """全局上限必须覆盖 tikz + fig 全部视觉产物：8 张数据图 → cap = 8×2+2 = 18。"""
    ws = tmp_path / "ws"
    figdir = ws / "figures"
    figdir.mkdir(parents=True)
    for i in range(8):
        (figdir / f"fig_q{i}.png").write_bytes(b"png")
    cf = ws / "_tmp" / ".tikz_vision_calls.json"
    nfig = host_visual_review._count_real_tikz_figs(cf)
    cap = nfig * 2 + 2 if nfig > 0 else 6
    assert cap == 18, f"期望 8 张图 cap=18，实际 cap={cap}"


def test_review_mode_bypasses_global_cap(tmp_path):
    """审核模式(mode=review)必须不受开发迭代的全局上限阻塞——最终审核必须真实产生视觉证据。"""
    ws = tmp_path / "ws"
    figdir = ws / "figures"
    figdir.mkdir(parents=True)
    img = figdir / "fig_final.png"
    img.write_bytes(b"png")
    cf = ws / "_tmp" / ".tikz_vision_calls.json"
    cf.parent.mkdir(parents=True, exist_ok=True)
    cf.write_text('{"__total__": 9999, "fig_final": 99}', encoding="utf-8")
    allowed, n, global_hit = host_visual_review._bump_and_check(img, mode="review")
    assert allowed, f"审核模式不应被全局上限阻塞：allowed={allowed}, n={n}, global_hit={global_hit}"
    data = json.loads(cf.read_text(encoding="utf-8"))
    assert data.get("__total__") == 9999, f"审核模式不应累计 __total__，实际 {data.get('__total__')}"


# ── 宿主独立窗口驱动契约：任务卡 → 独立窗口读图 → verdict 回写 → 收集 ────


def test_task_card_requires_independent_window(tmp_path):
    """任务卡必须锁定执行者=宿主独立窗口视觉模型，禁产图窗口自审。"""
    figdir = tmp_path / "figures"
    figdir.mkdir(parents=True)
    img = figdir / "fig_q1.png"
    img.write_bytes(b"png")
    card = host_visual_review.build_task_card("tikz", img, review=True)
    assert "fig_q1.png" in card
    assert "独立窗口" in card and "实际读图" in card
    assert "隔离" in card and "自审" in card
    assert host_visual_review.REVIEWED_BY_PREFIX in card
    assert "PASS" in card and "ISSUE" in card
    # TikZ 专属检查单进入任务卡
    tikz_card = host_visual_review.build_task_card(
        "tikz", img, review=False, checklist=host_visual_review.TIKZ_CHECKLIST)
    assert "节点间距" in tikz_card


def test_run_generates_task_card_and_pends_without_verdict(tmp_path):
    """无独立窗口 verdict → exit 2 + 任务卡落盘 + 派发提示。"""
    figdir = tmp_path / "figures"
    figdir.mkdir(parents=True)
    img = figdir / "fig_q1.png"
    img.write_bytes(b"png")
    code = host_visual_review.run("data-fig", str(img), review=True, workspace=str(tmp_path))
    assert code == 2
    card = host_visual_review.task_card_path(tmp_path, img)
    assert card.is_file(), "应生成独立窗口审核任务卡"
    assert "fig_q1.png" in card.read_text(encoding="utf-8")


def test_collect_pass_verdict(tmp_path):
    """独立窗口回写合规 PASS verdict → exit 0，输出携带 Reviewed-by。"""
    figdir = tmp_path / "figures"
    figdir.mkdir(parents=True)
    img = figdir / "fig_q1.png"
    img.write_bytes(b"png")
    vp = host_visual_review.verdict_path(tmp_path, img)
    vp.parent.mkdir(parents=True, exist_ok=True)
    vp.write_text(f"{host_visual_review.REVIEWED_BY_PREFIX} zcode-visual-judge\n\nPASS\n",
                  encoding="utf-8")
    code = host_visual_review.run("data-fig", str(img), review=True, workspace=str(tmp_path),
                                  collect_only=True)
    assert code == 0
    # 报告同时校验：run 输出含 PASS 与窗口标识
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        host_visual_review.run("data-fig", str(img), review=True, workspace=str(tmp_path),
                               collect_only=True)
    out = buf.getvalue()
    assert "PASS" in out and "zcode-visual-judge" in out


def test_collect_issue_verdict(tmp_path):
    """独立窗口发现 ISSUE → exit 1 并原样输出问题清单。"""
    figdir = tmp_path / "figures"
    figdir.mkdir(parents=True)
    img = figdir / "fig_q2.png"
    img.write_bytes(b"png")
    vp = host_visual_review.verdict_path(tmp_path, img)
    vp.parent.mkdir(parents=True, exist_ok=True)
    vp.write_text(f"{host_visual_review.REVIEWED_BY_PREFIX} win-2\n\n"
                  "ISSUE 1: [左下角] 图例遮挡曲线\n", encoding="utf-8")
    code = host_visual_review.run("data-fig", str(img), review=True, workspace=str(tmp_path),
                                  collect_only=True)
    assert code == 1


def test_collect_rejects_verdict_without_reviewer(tmp_path):
    """verdict 缺 Reviewed-by 窗口标识 → 证据无效（exit 2），不得冒充通过。"""
    figdir = tmp_path / "figures"
    figdir.mkdir(parents=True)
    img = figdir / "fig_q3.png"
    img.write_bytes(b"png")
    vp = host_visual_review.verdict_path(tmp_path, img)
    vp.parent.mkdir(parents=True, exist_ok=True)
    vp.write_text("PASS\n", encoding="utf-8")
    code = host_visual_review.run("data-fig", str(img), review=True, workspace=str(tmp_path),
                                  collect_only=True)
    assert code == 2


def test_tikz_entry_cli_contract(tmp_path):
    """tikz 工具入口 CLI 契约兼容：缺图 exit 2 + File not found。"""
    import subprocess

    missing = tmp_path / "missing.png"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "tikz_vision_check.py"), str(missing)],
        capture_output=True, text=True, timeout=30)
    assert completed.returncode == 2
    assert "File not found" in completed.stdout
