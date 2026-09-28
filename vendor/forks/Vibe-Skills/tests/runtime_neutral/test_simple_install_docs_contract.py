from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_DOCS = REPO_ROOT / "docs" / "install"
DOCS_INDEX = REPO_ROOT / "docs" / "README.md"
PUBLIC_READMES = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "README.zh.md",
)
ACTIVE_INSTALL_GUIDES = (
    INSTALL_DOCS / "README.md",
    INSTALL_DOCS / "README.en.md",
)
ONE_SHOT_BOOTSTRAPS = (
    REPO_ROOT / "scripts" / "bootstrap" / "one-shot-setup.sh",
    REPO_ROOT / "scripts" / "bootstrap" / "one-shot-setup.ps1",
)
REMOVED_PUBLIC_INSTALL_TERMS = (
    "-HostId",
    "-Profile",
    "-TargetRoot",
    "--host",
    "--profile",
    "--target-root",
    "--deep",
    "-Deep",
    "-StrictOffline",
    "uninstall.ps1",
    "uninstall.sh",
    "vibe-upgrade",
)


def test_active_install_docs_only_describe_simple_skills_dir_install() -> None:
    active_docs = {
        path.relative_to(INSTALL_DOCS).as_posix()
        for path in INSTALL_DOCS.rglob("*")
        if path.is_file()
    }

    assert active_docs == {"README.md", "README.en.md"}

    for doc_name in active_docs:
        text = (INSTALL_DOCS / doc_name).read_text(encoding="utf-8")
        assert "SkillsDir" in text or "--skills-dir" in text
        for term in REMOVED_PUBLIC_INSTALL_TERMS:
            assert term not in text


def test_internal_docs_define_one_installation_model() -> None:
    english_install = (INSTALL_DOCS / "README.en.md").read_text(encoding="utf-8")
    chinese_install = (INSTALL_DOCS / "README.md").read_text(encoding="utf-8")

    assert "## One Installation Model" in english_install
    assert "same runtime to `<SkillsDir>/vibe`" in english_install

    assert "## 一种安装模型" in chinese_install
    assert "同一份运行时写入 `<SkillsDir>/vibe`" in chinese_install


def test_public_readmes_do_not_advertise_missing_cli_commands() -> None:
    for path in PUBLIC_READMES:
        text = path.read_text(encoding="utf-8")
        assert "benchmark-kernel" not in text, path


def test_active_install_guides_point_to_simplified_skills_dir_install() -> None:
    for path in ACTIVE_INSTALL_GUIDES:
        text = path.read_text(encoding="utf-8")
        assert "--skills-dir" in text or "SkillsDir" in text, path
        for term in REMOVED_PUBLIC_INSTALL_TERMS:
            assert term not in text, path


def test_live_docs_indexes_do_not_route_current_install_to_retired_or_missing_pages() -> None:
    docs_index = DOCS_INDEX.read_text(encoding="utf-8")
    assert "install/README.md" in docs_index
    assert "one-click-install-release-copy" not in docs_index
    assert "runtime-freshness-install-sop.md" not in docs_index

    assert "docs/releases" not in docs_index


def test_public_readmes_keep_other_environments_as_one_auxiliary_install_note() -> None:
    english = PUBLIC_READMES[0].read_text(encoding="utf-8")
    assert "OpenClaw host notes" not in english
    assert "OpenCode host notes" not in english

    chinese = PUBLIC_READMES[1].read_text(encoding="utf-8")
    assert "OpenClaw 宿主说明" not in chinese
    assert "OpenCode 宿主说明" not in chinese


def test_quick_start_explains_install_run_and_delivery_records_without_legacy_status_terms() -> None:
    english = (INSTALL_DOCS / "README.en.md").read_text(encoding="utf-8")
    chinese = (INSTALL_DOCS / "README.md").read_text(encoding="utf-8")
    runtime_contract = (
        REPO_ROOT / "docs" / "governance" / "current-runtime-field-contract.md"
    ).read_text(encoding="utf-8")

    assert "`check` verifies the files recorded in the receipt." in english
    assert ".vibeskills/runs/<run_id>/" in runtime_contract
    assert "delivery-acceptance-report.json" in runtime_contract

    assert "`check` 只检查收据登记的文件是否仍然完整。" in chinese
    assert "`check` 证明的是 `installed locally`" in chinese

    for content in (english, chinese, runtime_contract):
        assert "vibe host-ready" not in content
        assert "online-ready" not in content

    assert "`minimal` is the recommended default" not in english
    assert "choose `full`" not in english
    assert "`minimal` 是默认推荐版本" not in chinese
    assert "再选 `full`" not in chinese


def test_install_readmes_keep_check_at_installed_locally_layer() -> None:
    english = (INSTALL_DOCS / "README.en.md").read_text(encoding="utf-8")
    chinese = (INSTALL_DOCS / "README.md").read_text(encoding="utf-8")

    assert "`check` proves `installed locally`." in english
    assert "It does not prove `runtime coherent` or `delivery accepted`." in english

    assert "`check` 证明的是 `installed locally`。" in chinese
    assert "它不证明 `runtime coherent`，也不证明 `delivery accepted`。" in chinese


def test_one_shot_bootstrap_scripts_are_retired_as_public_install_entrypoints() -> None:
    for path in ONE_SHOT_BOOTSTRAPS:
        text = path.read_text(encoding="utf-8")
        assert "retired" in text.lower(), path
        assert "--skills-dir" in text, path
        assert "install.sh" in text or "install.ps1" in text, path
        for term in REMOVED_PUBLIC_INSTALL_TERMS:
            assert term not in text, path
        assert "adapter_registry_query.py" not in text, path
