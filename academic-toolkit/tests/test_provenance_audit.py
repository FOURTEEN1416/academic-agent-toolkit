import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_provenance():
    path = ROOT / "tools" / "check_provenance.py"
    spec = importlib.util.spec_from_file_location("check_provenance_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_provenance_registry_validates_existing_upstream_files():
    module = load_provenance()
    result = module.run("upstream")

    assert result["ok"] is True
    assert len(result["reports"]) == len(module.UPSTREAM_REGISTRY)
    assert all(report["ok"] for report in result["reports"])


def test_provenance_registry_covers_phase5_minimum_scope():
    module = load_provenance()
    registered = {path.relative_to(module.ROOT).as_posix() for path in module.UPSTREAM_REGISTRY}

    assert len(module.UPSTREAM_REGISTRY) >= 15
    assert "skills/paper-write/templates/UPSTREAM.md" in registered
    assert "tools/docx_style_profiles/UPSTREAM.md" in registered
    assert "tools/docx-cn-engine/UPSTREAM.md" in registered
    assert "tools/humanize_chinese/UPSTREAM.md" in registered
    assert "tools/codesucker-core/UPSTREAM.md" in registered


def test_provenance_detects_missing_upstream_fields(tmp_path):
    module = load_provenance()
    broken = tmp_path / "broken.md"
    broken.write_text("no upstream fields here", encoding="utf-8")

    report = module.check_upstream(broken)

    assert report["ok"] is False
    assert "Upstream:" in report["missing"] or "Upstream" in report["missing"]


def test_provenance_vendor_requires_license_notice_upstream(tmp_path):
    module = load_provenance()
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "LICENSE").write_text("MIT", encoding="utf-8")

    report = module.check_vendor(vendor)

    assert report["ok"] is False
    assert "NOTICE" in report["missing"]
    assert "UPSTREAM.md" in report["missing"]


def test_pinned_commit_semantics_positive_and_negative(tmp_path):
    """2026-09-09 审计 P3-2 收紧回归：URL 源必须哈希；非 URL 源接受哈希/日期/official-*/无外部*。"""
    module = load_provenance()
    check = module._check_pinned_semantics
    # 正路
    assert check("- Upstream: https://github.com/foo/bar\n- Pinned commit: 5debcd2efb686dce0205ba9094b6413dae5f89c0") is None
    assert check("- Upstream: https://github.com/foo/bar\n- Pinned commit: `b065a1825f4e32dca4c4b7fd8bccf3e020a77c5`") is None  # 反引号包裹
    assert check("- Upstream: 官方规则\n- Pinned commit: official-rules-2026-08-18") is None
    assert check("- Upstream: 官方规范\n- Pinned commit: official-release-neurips2025-icml2025") is None
    assert check("- Upstream: 本地\n- Pinned commit: 无外部 git 源（官方材料要求文档）") is None
    assert check("- Upstream: 组委会\n- Pinned commit: 不可固定（每届规则随赛题公告发布）") is None
    # 反路：URL 源写散文/日期 → 必须拦
    bad = check("- Upstream: https://github.com/foo/bar\n- Pinned commit: latest-main-branch")
    assert bad is not None, "URL 源的非哈希 Pinned commit 必须被拦"
    bad2 = check("- Upstream: https://github.com/foo/bar\n- Pinned commit: 2026-08-18")
    assert bad2 is not None, "URL 源的日期不能替代哈希"
    # 反路：非 URL 源写任意散文 → 必须拦
    assert check("- Upstream: 官方\n- Pinned commit: 随便写的") is not None
    # 反路：缺 Pinned commit 值
    assert check("- Upstream: https://github.com/foo/bar\n- Pinned commit:") is not None


def test_local_only_upstream_missing_is_skip_not_fail(monkeypatch):
    """local-only 台账件（gitignored 技能随仓豁免）缺位 = 语义 SKIP，不得 FAIL
    （2026-09-22 #16 批：V1 注册 eco-community-plots 曾令公开 clone CI 全红）。"""
    module = load_provenance()
    fake = module.ROOT / "skills" / "__no_such_local_only__" / "UPSTREAM.md"
    monkeypatch.setattr(module, "UPSTREAM_REGISTRY", [fake])
    monkeypatch.setattr(module, "LOCAL_ONLY_UPSTREAM", frozenset([fake]))
    result = module.run("upstream")
    assert result["ok"] is True
    assert result["failures"] == []
    assert result["reports"][0].get("skip")


def test_non_local_only_missing_still_fails(monkeypatch):
    """未标 local-only 的注册件缺位必须照旧 FAIL（SKIP 语义不得变成万能后门）。"""
    module = load_provenance()
    fake = module.ROOT / "skills" / "__no_such_public__" / "UPSTREAM.md"
    monkeypatch.setattr(module, "UPSTREAM_REGISTRY", [fake])
    result = module.run("upstream")
    assert result["ok"] is False


def test_eco_community_ledger_is_local_only_registered():
    module = load_provenance()
    rel = "skills/eco-community-plots/references/UPSTREAM.md"
    registered = {path.relative_to(module.ROOT).as_posix() for path in module.UPSTREAM_REGISTRY}
    local_only = {p.relative_to(module.ROOT).as_posix() for p in module.LOCAL_ONLY_UPSTREAM}
    assert rel in registered and rel in local_only
