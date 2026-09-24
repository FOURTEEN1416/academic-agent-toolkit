"""模型配置契约测试（**宿主无关**，2026-09-24 自 test_zcode_host_compat.py 拆出）。

⚠️ 拆分缘由（2026-09-24 审计裁决 D3）：本文件守的是 **engine.quality_gates 的宿主无关
契约**——模型三级解析（contest 配置槽 > 宿主 agents > 无配置）与 strict 门禁联动。
原先与 ZCode 专有面（L1 hook 行为 + .zcode/config.json 注册契约）混装在一个宿主命名
文件里，将来"去宿主化"整文件删除会连带丢掉本契约守卫。C/D 段仍留
`test_zcode_host_compat.py`（ZCode 可选适配器守护）。

覆盖：
  A. 模型配置三级解析，仓库出厂零预设；
  B. strict 门禁在"配置槽填了模型"后恢复硬拦截、在"两处皆空"时降级 warn。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUITE_ROOT))

from engine.quality_gates import (  # noqa: E402
    QualityGate,
    load_configured_role_models,
    model_config_provenance,
)

ROLES = ["reviewer", "visual_reviewer", "editor", "final_reviewer"]


# ---------------- A. 三级解析 ----------------

def test_contest_slot_ships_with_zero_preset_models():
    """配置槽状态契约（2026-09-10 演化）：出厂态必须零预设；比赛配置态（configured_at
    非空或任一角色已填）则验证配置形态合法——roles 四键齐全且值为非空字符串。
    '不预设模型'守的是出厂仓库，不禁止比赛时配置（填写正是该槽的设计用途）。"""
    data = json.loads((SUITE_ROOT / "engine" / "modex-core" / "contest_models.json")
                      .read_text(encoding="utf-8"))
    roles = data.get("roles", {})
    configured = bool(data.get("configured_at")) or any(roles.get(r) for r in ROLES)
    if not configured:
        for role in ROLES:
            assert not roles.get(role), f"出厂态配置槽不得预设 {role} 模型（比赛时再配置）"
    else:
        assert set(roles.keys()) >= set(ROLES), "配置态必须覆盖全部四个角色键"
        for role in ROLES:
            value = roles.get(role)
            assert isinstance(value, str) and value.strip(), f"{role} 已配置态下必须是非空字符串"
        # 2026-09-10 用户裁定（第二次）：独立审稿走 Agnes 外部通道，四角色 agnes/agnes-2.5-flash；
        # 具体模型名随用户调整而变，此处只验声明格式（provider/model 或裸 model）。
        import re as _re
        for role in ROLES:
            assert _re.fullmatch(r"[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)?", roles[role]), \
                f"{role} 模型声明格式非法: {roles[role]}"


def test_contest_slot_wins_over_agents_dir(tmp_path, monkeypatch):
    contest = tmp_path / "models.json"
    contest.write_text(json.dumps({"roles": {r: f"contest/{r}-model" for r in ROLES}}),
                       encoding="utf-8")
    agents = tmp_path / "agents"
    agents.mkdir()
    for f in ("数模审稿人.md", "数模视觉审查.md", "数模编辑.md", "数模专家.md"):
        (agents / f).write_text("---\nmodel: host/wrong-model\n---\n", encoding="utf-8")
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(contest))
    monkeypatch.setenv("OPENCODE_AGENTS_DIR", str(agents))

    models = load_configured_role_models()
    assert models == {r: f"contest/{r}-model" for r in ROLES}
    assert set(model_config_provenance().values()) == {"contest_models"}


def test_fallback_to_agents_per_role(tmp_path, monkeypatch):
    """配置槽只填一个角色 → 该角色用配置槽，其余回退宿主 agents 目录。"""
    contest = tmp_path / "models.json"
    contest.write_text(json.dumps({"roles": {"visual_reviewer": "glm/glm-vision-flash"}}),
                       encoding="utf-8")
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "数模审稿人.md").write_text("---\nmodel: host/reviewer-x\n---\n", encoding="utf-8")
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(contest))
    monkeypatch.setenv("OPENCODE_AGENTS_DIR", str(agents))

    models = load_configured_role_models()
    assert models["visual_reviewer"] == "glm/glm-vision-flash"
    assert models["reviewer"] == "host/reviewer-x"
    assert models["editor"] == ""
    prov = model_config_provenance()
    assert prov["visual_reviewer"] == "contest_models"
    assert prov["reviewer"] in {"host_adapter", "opencode_agents"}
    assert prov["editor"] == "none"


def test_missing_slot_file_degrades_to_agents(tmp_path, monkeypatch):
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(tmp_path / "not_exist.json"))
    monkeypatch.setenv("OPENCODE_AGENTS_DIR", str(tmp_path / "no_agents"))
    assert load_configured_role_models() == {r: "" for r in ROLES}


# ---------------- B. strict 门禁联动 ----------------

def _review_files(ws: Path):
    for name in ("COMP_REVIEW.md", "VISUAL_REVIEW.md", "EDITOR_CHANGELOG.md", "FINAL_REVIEW.md"):
        (ws / name).write_text(f"# {name}\n", encoding="utf-8")
    (ws / "COMP_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (ws / "VISUAL_REVIEW_VERDICT.json").write_text(
        '{"findings": [], "fatal_count": 0, "status": "pass"}', encoding="utf-8")
    (ws / "FINAL_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")


def _provenance(ws: Path, models: dict) -> dict:
    files = {"reviewer": "COMP_REVIEW_VERDICT.json",
             "visual_reviewer": "VISUAL_REVIEW_VERDICT.json",
             "editor": "EDITOR_CHANGELOG.md",
             "final_reviewer": "FINAL_REVIEW_VERDICT.json"}
    roles = {}
    for role, fname in files.items():
        roles[role] = {
            "session_id": f"sess_{role}", "model": models[role],
            "output_file": fname, "completed_at": "2026-09-09T00:00:00+00:00",
            "output_sha256": hashlib.sha256((ws / fname).read_bytes()).hexdigest(),
        }
    return {"schema_version": 1, "roles": roles}


def test_strict_blocks_against_contest_slot_model(tmp_path, monkeypatch):
    """比赛时配置槽填了模型 → strict 比对硬拦截（防线不因去预设而失效）。"""
    contest = tmp_path / "models.json"
    contest.write_text(json.dumps({"roles": {r: "contest/right-model" for r in ROLES}}),
                       encoding="utf-8")
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(contest))
    _review_files(tmp_path)
    models = {r: "contest/right-model" for r in ROLES}
    models["reviewer"] = "contest/wrong-model"
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(
        json.dumps(_provenance(tmp_path, models)), encoding="utf-8")

    result = QualityGate(tmp_path).check_review_evidence("full", strict_model_match=True)
    assert result["ok"] is False, result.get("reason")
    assert "wrong-model" in result.get("reason", "")


def test_strict_warns_without_blocking_when_unconfigured(tmp_path, monkeypatch):
    """两处皆空（未做比赛配置）→ strict 无从比对：warn 留痕、不阻断、更不默认放行成静默。"""
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(tmp_path / "absent.json"))
    monkeypatch.setenv("OPENCODE_AGENTS_DIR", str(tmp_path / "no_agents"))
    _review_files(tmp_path)
    models = {r: "whatever/model-at-contest" for r in ROLES}
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(
        json.dumps(_provenance(tmp_path, models)), encoding="utf-8")

    result = QualityGate(tmp_path).check_review_evidence("full", strict_model_match=True)
    assert result["ok"] is True, "未配置时不得拿假想模型阻断"
    assert any("无配置模型" in w for w in result.get("warnings", []))
