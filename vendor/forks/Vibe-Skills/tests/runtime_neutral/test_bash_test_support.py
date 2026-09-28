from __future__ import annotations

from tests import bash_test_support


def test_normalize_bash_command_args_converts_windows_paths(monkeypatch) -> None:
    monkeypatch.setattr(bash_test_support, "resolve_bash_for_tests", lambda: "bash")
    monkeypatch.setattr(
        bash_test_support,
        "to_bash_path",
        lambda path: "/converted/" + str(path).replace("\\", "/").replace(":", ""),
    )

    normalized = bash_test_support.normalize_bash_command_args(
        [
            "bash",
            r"F:\repo\install.sh",
            "--target-root",
            r"C:\Users\tester\.codex",
            "--profile",
            "minimal",
        ]
    )

    assert normalized == [
        "bash",
        "/converted/F/repo/install.sh",
        "--target-root",
        "/converted/C/Users/tester/.codex",
        "--profile",
        "minimal",
    ]


def test_normalize_bash_command_args_preserves_windows_trailing_separators(monkeypatch) -> None:
    monkeypatch.setattr(bash_test_support, "resolve_bash_for_tests", lambda: "bash")
    monkeypatch.setattr(
        bash_test_support,
        "to_bash_path",
        lambda path: "/converted/" + str(path).replace("\\", "/").replace(":", ""),
    )

    normalized = bash_test_support.normalize_bash_command_args(
        [
            "bash",
            r"C:\Users\tester\AppData\Local\Temp\case\downloads/",
            "D:\\work\\output\\",
        ]
    )

    assert normalized == [
        "bash",
        "/converted/C/Users/tester/AppData/Local/Temp/case/downloads/",
        "/converted/D/work/output/",
    ]


def test_normalize_bash_command_args_preserves_non_bash_commands() -> None:
    args = ["git", "status", r"F:\repo"]

    assert bash_test_support.normalize_bash_command_args(args) is args


def test_is_bash_command_args_matches_bash_executables_only() -> None:
    assert bash_test_support.is_bash_command_args(["bash", "script.sh"])
    assert bash_test_support.is_bash_command_args([r"D:\tool\Git\usr\bin\bash.exe", "script.sh"])
    assert not bash_test_support.is_bash_command_args(["python", "-m", "pytest"])


def test_normalize_bash_command_args_preserves_windows_bash_executable(monkeypatch) -> None:
    monkeypatch.setattr(bash_test_support, "resolve_bash_for_tests", lambda: r"D:\tool\Git\usr\bin\bash.exe")
    monkeypatch.setattr(
        bash_test_support,
        "to_bash_path",
        lambda path: "/converted/" + str(path).replace("\\", "/").replace(":", ""),
    )

    normalized = bash_test_support.normalize_bash_command_args(
        [
            "bash",
            r"F:\repo\install.sh",
            r"C:\Users\tester\.codex",
        ]
    )

    assert normalized == [
        r"D:\tool\Git\usr\bin\bash.exe",
        "/converted/F/repo/install.sh",
        "/converted/C/Users/tester/.codex",
    ]


def test_bash_test_env_prepends_python_shim(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(bash_test_support, "ensure_bash_test_python_bin", lambda: tmp_path)

    env = bash_test_support.bash_test_env({"PATH": "original", "KEEP": "1"})

    assert env["PATH"].startswith(str(tmp_path))
    assert env["PATH"].endswith("original")
    assert env["KEEP"] == "1"
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_bash_test_env_respects_explicit_python_path_override(monkeypatch, tmp_path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "python3").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    monkeypatch.setenv("PATH", "base")
    monkeypatch.setattr(bash_test_support, "ensure_bash_test_python_bin", lambda: tmp_path / "shim")

    env = bash_test_support.bash_test_env({"PATH": f"{fake_bin}:base"})

    assert env["PATH"] == f"{fake_bin}:base"
