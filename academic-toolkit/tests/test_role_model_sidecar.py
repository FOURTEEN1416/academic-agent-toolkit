"""A6-F4 回归测试：审稿模型 fallback 写回 sidecar + strict 闸按实际值交叉核对。

敌意审计 A6 实测：RoleAgent 主通道失败自动 fallback 到 SENSENOVA 等备用通道时不改写
证据声明，strict 闸只比对自申报串——"实际调用模型 ≠ 声明模型"测不出。
修复：RoleAgent 每次成功调用把"角色→实际 base_url/model"写入工作区
.engine/role_calls_actual.json；check_review_evidence 在 sidecar 存在时交叉核对，
不符即硬拦（证据失实，与 strict 开关无关）。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.quality_gates import QualityGate, RoleAgent, record_role_call_actual, ROLE_CALLS_SIDECAR
import engine.quality_gates as qg


def _isolate_model_config(monkeypatch, tmp_path):
    """隔离机器真实配置：竞赛配置槽置空 + 宿主 agents 目录置空。"""
    empty_slot = tmp_path / "empty_contest_models.json"
    empty_slot.write_text(json.dumps({"configured_at": "", "roles": {
        r: "" for r in ("reviewer", "visual_reviewer", "editor", "final_reviewer")}}),
        encoding="utf-8")
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(empty_slot))
    agents_dir = tmp_path / "agents_empty"
    agents_dir.mkdir()
    monkeypatch.setenv("OPENCODE_AGENTS_DIR", str(agents_dir))


class _FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def read(self):
        return self._body


def _patch_http_fallback(monkeypatch):
    """主 provider（primary.example.com）恒 500（含重试），备用 provider 成功——
    复现 A6 的 fallback 场景；压掉指数退避 sleep 保持测试快速。"""
    import http.client as _hc

    class FakeConn:
        def __init__(self, host=None, *a, **k):
            self.host = str(host)

        def request(self, *a, **k):
            pass

        def getresponse(self):
            if "primary.example.com" in self.host:
                return _FakeResponse(500, b'{"error":"boom"}')
            return _FakeResponse(200, json.dumps(
                {"choices": [{"message": {"content": "fallback审稿输出"}}]}).encode())

        def close(self):
            pass

    monkeypatch.setattr(_hc, "HTTPSConnection", FakeConn)
    monkeypatch.setattr(_hc, "HTTPConnection", FakeConn)
    monkeypatch.setattr("time.sleep", lambda seconds: None)


def test_fallback_call_records_actual_model_sidecar(tmp_path, monkeypatch):
    """主通道失败走 fallback → sidecar 必须记录实际使用的 base_url/model。"""
    _patch_http_fallback(monkeypatch)
    agent = RoleAgent(api_key="k1", base_url="https://primary.example.com/v1",
                      model="primary-model", workspace=tmp_path)
    monkeypatch.setattr(qg, "env_get", lambda k, d="": {
        "SENSENOVA_BASE_URL": "https://sensenova.example.com/v1",
        "SENSENOVA_API_KEY": "k2",
        "SENSENOVA_MODEL": "deepseek-v4-flash",
    }.get(k, d))

    result = agent.call("reviewer", "请复核")
    assert "fallback审稿输出" in result

    sidecar = json.loads((tmp_path / ROLE_CALLS_SIDECAR).read_text(encoding="utf-8"))
    record = sidecar["roles"]["reviewer"]
    assert record["model"] == "deepseek-v4-flash", "sidecar 必须记录 fallback 实际模型"
    assert "sensenova.example.com" in record["base_url"], "sidecar 必须记录实际 base_url"
    assert record["called_at"]


def test_no_workspace_no_sidecar(tmp_path, monkeypatch):
    """未传 workspace（也未设 ACAT_WORKSPACE）时不落 sidecar（向后兼容）。"""
    _patch_http_fallback(monkeypatch)
    agent = RoleAgent(api_key="k1", base_url="https://primary.example.com/v1",
                      model="primary-model")
    monkeypatch.setattr(qg, "env_get", lambda k, d="": {
        "SENSENOVA_BASE_URL": "https://sensenova.example.com/v1",
        "SENSENOVA_API_KEY": "k2",
        "SENSENOVA_MODEL": "deepseek-v4-flash",
    }.get(k, d))
    agent.call("reviewer", "请复核")
    assert not (tmp_path / ROLE_CALLS_SIDECAR).exists()


def _write_full_review_workspace(ws, claimed_models):
    """构造 full 模式审稿工作区：7 件套 + REVIEW_EXECUTION_EVIDENCE.json。"""
    for name in ("COMP_REVIEW.md", "VISUAL_REVIEW.md", "EDITOR_CHANGELOG.md", "FINAL_REVIEW.md"):
        (ws / name).write_text(f"# {name}\n", encoding="utf-8")
    (ws / "COMP_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (ws / "VISUAL_REVIEW_VERDICT.json").write_text(
        '{"findings": [], "fatal_count": 0, "status": "pass"}', encoding="utf-8")
    (ws / "FINAL_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")

    outputs = {
        "reviewer": "COMP_REVIEW_VERDICT.json",
        "visual_reviewer": "VISUAL_REVIEW_VERDICT.json",
        "editor": "EDITOR_CHANGELOG.md",
        "final_reviewer": "FINAL_REVIEW_VERDICT.json",
    }
    roles = {}
    for i, (role, output) in enumerate(outputs.items()):
        roles[role] = {
            "session_id": f"session-{role}",
            "model": claimed_models.get(role, "some-model"),
            "completed_at": "2026-09-11T00:00:00Z",
            "output_file": output,
            "output_sha256": hashlib.sha256((ws / output).read_bytes()).hexdigest(),
        }
    (ws / "REVIEW_EXECUTION_EVIDENCE.json").write_text(
        json.dumps({"schema_version": 1, "roles": roles}, ensure_ascii=False), encoding="utf-8")


def test_strict_gate_blocks_when_sidecar_model_differs_from_claim(tmp_path, monkeypatch):
    """fallback 实际模型 ≠ 证据声明模型 → review 闸硬拦（A6-F4 主场景）。"""
    _isolate_model_config(monkeypatch, tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    _write_full_review_workspace(ws, {"reviewer": "primary-model"})
    # 引擎侧记录：reviewer 实际由 fallback 通道产生
    record_role_call_actual(ws, "reviewer", "https://sensenova.example.com/v1", "deepseek-v4-flash")

    result = QualityGate(ws).check_review_evidence("full", strict_model_match=True)
    assert result["ok"] is False, "声明模型与实际调用模型不符必须硬拦"
    assert "deepseek-v4-flash" in result["reason"] and "primary-model" in result["reason"], \
        f"reason 应指出实际与声明模型: {result['reason']}"
    assert ROLE_CALLS_SIDECAR in result["reason"]


def test_gate_blocks_on_sidecar_mismatch_even_without_strict_flag(tmp_path, monkeypatch):
    """实际调用模型不符 = 客观证据失实，默认（软校验）模式也必须硬拦。"""
    _isolate_model_config(monkeypatch, tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    _write_full_review_workspace(ws, {"reviewer": "primary-model"})
    record_role_call_actual(ws, "reviewer", "https://sensenova.example.com/v1", "deepseek-v4-flash")

    result = QualityGate(ws).check_review_evidence("full")
    assert result["ok"] is False


def test_gate_passes_when_claim_matches_recorded_actual(tmp_path, monkeypatch):
    """证据如实申报实际（fallback）模型 → 闸放行（软校验无配置不告警）。"""
    _isolate_model_config(monkeypatch, tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    _write_full_review_workspace(ws, {"reviewer": "deepseek-v4-flash"})
    record_role_call_actual(ws, "reviewer", "https://sensenova.example.com/v1", "deepseek-v4-flash")

    result = QualityGate(ws).check_review_evidence("full")
    assert result["ok"] is True, f"如实申报实际通道应放行: {result['reason']}"


def test_sidecar_recorder_merges_and_survives_corrupt_file(tmp_path):
    """sidecar 写入：多角色合并 + 损坏文件可自愈。"""
    sidecar = tmp_path / ROLE_CALLS_SIDECAR
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text("not-json{{", encoding="utf-8")
    record_role_call_actual(tmp_path, "reviewer", "https://a.example.com", "m-a")
    record_role_call_actual(tmp_path, "editor", "https://b.example.com", "m-b")
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["roles"]["reviewer"]["model"] == "m-a"
    assert data["roles"]["editor"]["model"] == "m-b"
