"""批次三 B3-7：适配器三方对账锁。

三方 = engine/agent_protocol.OPTIONAL_ADAPTERS（boot 契约清单）、
engine/capability_probe.ADAPTER_MARKERS（探测标记，唯一真相源）、
agents/adapters/*/adapter.json（适配器元数据目录）。
2026-09-22 对账前：清单 7（含无标记的 gemini-cli）、标记 6、目录 5（缺 cursor）。
agents/adapters/ 元数据目录缺席为合法态；始终在隔离目录调用真实生成器验证
全部内建契约，本地有元数据时追加目录侧对账，不能用缺目录跳过生成器。
"""
import json
import sys
from pathlib import Path

TOOLBOX = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLBOX.parent
sys.path.insert(0, str(TOOLBOX))

from engine.agent_protocol import OPTIONAL_ADAPTERS  # noqa: E402
from engine.capability_probe import ADAPTER_MARKERS  # noqa: E402

ADAPTERS_DIR = REPO_ROOT / "agents" / "adapters"


def _marker_ids() -> set[str]:
    return {adapter_id for adapter_id, _markers, _note in ADAPTER_MARKERS}


def _manifest_ids() -> set[str]:
    ids = set()
    for manifest in sorted(ADAPTERS_DIR.glob("*/adapter.json")):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        ids.add(data["adapter_id"])
        assert data["adapter_id"] == manifest.parent.name, (
            f"adapter_id 与目录名不一致: {manifest}"
        )
    return ids


def test_adapter_triple_sources_are_aligned():
    assert set(OPTIONAL_ADAPTERS) == _marker_ids(), (
        f"boot 清单与探测标记不一致: 清单独有={set(OPTIONAL_ADAPTERS) - _marker_ids()}, "
        f"标记独有={_marker_ids() - set(OPTIONAL_ADAPTERS)}"
    )
    if not ADAPTERS_DIR.exists():
        # 元数据目录缺席为合法态，无需对账
        return
    assert _manifest_ids() == _marker_ids(), (
        f"目录元数据与探测标记不一致: 目录独有={_manifest_ids() - _marker_ids()}, "
        f"标记独有={_marker_ids() - _manifest_ids()}"
    )


def test_adapter_manifest_probe_paths_agree_with_markers(tmp_path):
    """总是验证真实生成器；本地已有配置时再对账，不为跑测试重建宿主目录。"""
    from engine.tool_forge import forge_adapter

    suite = tmp_path / "academic-toolkit"
    for adapter_id, markers, _note in ADAPTER_MARKERS:
        result = forge_adapter(adapter_id, "适配器契约回归", project_root=suite)
        data = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        assert data["adapter_id"] == adapter_id
        assert set(data["config_paths"]) == set(markers)
        assert data["required_for_drive"] is (adapter_id == "generic")
        assert not forge_adapter(adapter_id, "不覆盖", project_root=suite)["created"]

    manifests = {
        m.parent.name: json.loads(m.read_text(encoding="utf-8"))
        for m in sorted(ADAPTERS_DIR.glob("*/adapter.json"))
    }
    for adapter_id, markers, _note in ADAPTER_MARKERS:
        if not manifests:
            break
        data = manifests.get(adapter_id)
        assert data is not None, f"探测标记 {adapter_id} 缺 adapter.json"
        if not markers:
            assert data.get("required_for_drive") is True
        else:
            assert set(markers) & set(data.get("config_paths") or []), adapter_id
