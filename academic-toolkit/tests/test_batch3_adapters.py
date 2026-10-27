"""批次三 B3-7：可选适配器子系统退役锁。

可选适配器（配置探测、boot 清单、适配器元数据铸造）已整体退休；
本文件锁定退役形态，防止任何一段被悄悄重新引入。
"""
import sys
from pathlib import Path

TOOLBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLBOX))

import engine.agent_protocol as agent_protocol  # noqa: E402
import engine.capability_probe as capability_probe  # noqa: E402
import engine.tool_forge as tool_forge  # noqa: E402


def test_boot_contract_has_no_optional_adapter_section():
    contract = agent_protocol.bootstrap(TOOLBOX)
    assert "optional_adapters" not in contract
    assert "adapter_note" not in contract


def test_adapter_probe_and_forge_helpers_are_retired():
    assert not hasattr(agent_protocol, "OPTIONAL_ADAPTERS")
    assert not hasattr(capability_probe, "ADAPTER_MARKERS")
    assert not hasattr(capability_probe, "_adapter_status")
    assert not hasattr(tool_forge, "forge_adapter")
