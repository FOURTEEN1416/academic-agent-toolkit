from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_english_readme_keeps_internal_runtime_roles_out_of_default_navigation() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    runtime_contract = (
        REPO_ROOT / "docs" / "governance" / "current-runtime-field-contract.md"
    ).read_text(encoding="utf-8")
    forbidden_overclaims = (
        "PowerShell stays only as a thin host wrapper",
        "PowerShell owns launcher wrappers, host receipts, shell-native checks, and leaf execution only",
    )
    runtime_contract_claims = (
        "Python and PowerShell resolve the same relative fields",
        "primary release-artifact sink",
        "module-execution.json",
        "PowerShell",
    )
    forbidden_claims = (
        "Do not let PowerShell own task semantics.",
    )

    assert "[architecture guide](./docs/architecture/local-agent-kernel-v2.md)" not in readme
    assert "roles of Python and PowerShell" not in readme
    assert '<a href="./docs/README.md">Documentation</a>' in readme

    internal_phrases = (
        "canonical validation",
        "truth chain",
        "stage orchestration",
        "transitional orchestration surfaces",
    )
    for phrase in internal_phrases:
        assert phrase not in readme
    for claim in runtime_contract_claims:
        assert claim in runtime_contract
    for content in (readme, runtime_contract):
        for claim in forbidden_overclaims:
            assert claim not in content
        for claim in forbidden_claims:
            assert claim not in content


def test_chinese_readme_keeps_internal_runtime_roles_out_of_default_navigation() -> None:
    content = (REPO_ROOT / "README.zh.md").read_text(encoding="utf-8")

    assert "[架构说明](./docs/architecture/local-agent-kernel-v2.md)" not in content
    assert "Python 和 PowerShell 分别负责什么" not in content
    assert '<a href="./docs/README.md">文档索引</a>' in content

    internal_phrases = (
        "canonical validation",
        "真相链",
        "阶段编排",
        "迁移期编排面",
    )
    for phrase in internal_phrases:
        assert phrase not in content
