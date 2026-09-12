"""D6 write_workspace_state 工具回归测试（STATE.txt 生成/更新语义）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from write_workspace_state import write_state  # noqa: E402


def test_state_txt_created_with_all_fields(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    path = write_state(ws, agent="窗口A", workflow_id="wf-123 (completed)",
                       version="v2-91p", superseded_by="",
                       note="点评素材保留", authority="HANDOVER.md")
    assert path == ws / "STATE.txt"
    text = path.read_text(encoding="utf-8")
    assert "agent: 窗口A" in text
    assert "workflow_id: wf-123 (completed)" in text
    assert "version: v2-91p" in text
    assert "superseded_by: (无——本 workspace 为最新产物)" in text
    assert "authority: HANDOVER.md" in text
    assert "点评素材保留" in text
    assert "updated_at:" in text


def test_state_txt_update_refreshes_not_duplicates(tmp_path):
    """重复调用 = 更新覆盖（不产生第二个状态文件/历史残留）。"""
    ws = tmp_path / "ws"
    ws.mkdir()
    write_state(ws, agent="窗口A", version="v1")
    write_state(ws, agent="窗口B", version="v2", superseded_by="已被 v2 取代")
    text = (ws / "STATE.txt").read_text(encoding="utf-8")
    assert text.count("agent:") == 1
    assert "窗口B" in text
    assert "窗口A" not in text
    assert "已被 v2 取代" in text


def test_missing_workspace_fails_loudly(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        write_state(tmp_path / "不存在", agent="x")
