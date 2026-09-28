from __future__ import annotations

from tests import conftest
from tests import bash_test_support


def test_text_subprocess_wrapper_keeps_default_encoding_for_non_bash(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(conftest, "_RAW_SUBPROCESS_RUN", fake_run)

    conftest._utf8_text_subprocess_run(["python", "-c", "print('ok')"], text=True)

    assert "encoding" not in captured
    assert captured["errors"] == "replace"


def test_text_subprocess_wrapper_forces_utf8_for_bash(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(bash_test_support, "resolve_bash_for_tests", lambda: "bash")
    monkeypatch.setattr(conftest, "bash_test_env", lambda env: {"PATH": "shim", **(env or {})})
    monkeypatch.setattr(conftest, "_RAW_SUBPROCESS_RUN", fake_run)

    conftest._utf8_text_subprocess_run(["bash", "script.sh"], text=True, env={"KEEP": "1"})

    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert captured["env"]["PATH"] == "shim"
    assert captured["env"]["KEEP"] == "1"


def test_text_subprocess_wrapper_forces_utf8_for_powershell(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(conftest, "_RAW_SUBPROCESS_RUN", fake_run)

    conftest._utf8_text_subprocess_run(["pwsh", "-NoLogo", "-Command", "'ok'"], text=True)

    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
