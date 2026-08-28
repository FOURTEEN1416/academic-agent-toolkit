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
