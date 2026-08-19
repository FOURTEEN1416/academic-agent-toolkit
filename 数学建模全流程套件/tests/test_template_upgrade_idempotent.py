"""P2 债务修复：模板迁移脚本进入 pytest 回归链。

验证 tools/upgrade_templates.py 的幂等性——已满足升级规则的模板不应被重复修改。
若未来模板被回退/新模板未按规范填写，此测试会立刻失败，防止迁移状态漂移。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "engine" / "modex-core" / "templates.json"


@pytest.fixture(scope="module")
def upgrade_module():
    spec = importlib.util.spec_from_file_location(
        "upgrade_templates", ROOT / "tools" / "upgrade_templates.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_template_upgrade_is_idempotent(upgrade_module, tmp_path):
    """迁移脚本重复运行不应再产生任何变更（changed_steps == 0）。"""
    # 复制一份模板到临时目录，避免测试直接写原文件
    target = tmp_path / "templates.json"
    target.write_bytes(TEMPLATES.read_bytes())

    result = upgrade_module.upgrade(target)

    assert result["ok"] is True
    assert result["changed_steps"] == 0, (
        f"模板未满足迁移规范，changed_steps = {result['changed_steps']}；"
        "请运行 python tools/upgrade_templates.py 并提交变更"
    )
    assert result["unknown_checks"] == [], f"存在未注册门禁: {result['unknown_checks']}"


def test_template_upgrade_does_not_modify_file_when_satisfied(upgrade_module, tmp_path):
    """幂等性：满足规范时文件内容应完全不变（字节级）。"""
    target = tmp_path / "templates.json"
    target.write_bytes(TEMPLATES.read_bytes())
    before = target.read_bytes()

    upgrade_module.upgrade(target)

    assert target.read_bytes() == before


def test_all_template_steps_have_metadata(upgrade_module):
    """Phase 6 标准：每个模板步骤都有嵌套 metadata。"""
    import json

    catalog = json.loads(TEMPLATES.read_text(encoding="utf-8"))
    missing = []
    for tname, tpl in catalog.items():
        for step in tpl.get("sub_steps", []):
            meta = step.get("metadata")
            if not isinstance(meta, dict):
                missing.append(f"{tname}/{step.get('skill_name', '?')}")
    assert not missing, f"缺少 metadata 的步骤: {missing}"


def test_registered_gates_cover_migration_mapping(upgrade_module):
    """SKILL_CHECKS 中引用的门禁必须全部已注册（防名称漂移）。"""
    from engine.quality_gates import NAMED_CHECKS_REGISTRY

    registered = set(NAMED_CHECKS_REGISTRY)
    referenced = set()
    for checks in upgrade_module.SKILL_CHECKS.values():
        referenced.update(checks)
    unknown = referenced - registered
    assert not unknown, f"SKILL_CHECKS 引用了未注册门禁: {sorted(unknown)}"
