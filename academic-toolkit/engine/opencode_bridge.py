"""兼容 shim：canonical 定义已迁至 agent_bridge.py。

历史模块名保留，避免既有 import / 测试 / 外部脚本断裂。
新代码请直接 `from engine.agent_bridge import StepAction, StepResult`。
"""
from __future__ import annotations

from .agent_bridge import StepAction, StepResult

__all__ = ["StepAction", "StepResult"]
