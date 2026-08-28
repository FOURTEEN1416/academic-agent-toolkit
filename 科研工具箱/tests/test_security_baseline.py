import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import env_loader
from tools import reviewer_client


def test_env_example_has_no_secret_like_values():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    pattern = r"(?i)(?:sk-[A-Za-z0-9]{16,}|AIza[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,})"
    assert not re.search(pattern, text)


def test_env_loader_accepts_explicit_path(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# comment\nA=one\n\nB='two'\n", encoding="utf-8")
    assert env_loader.load_env(path) == {"A": "one", "B": "two"}


def test_reviewer_client_keeps_default_tls_verification_source():
    source = Path(reviewer_client.__file__).read_text(encoding="utf-8")
    assert "ssl.create_default_context()" in source
    assert "CERT_NONE" not in source
    assert "check_hostname = False" not in source


def test_reviewer_client_loads_project_env_before_reading_provider_settings(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=from-file\nOPENAI_BASE_URL=https://example.test/v1\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    reviewer_client.load_project_env(env_path)

    assert reviewer_client.os.environ["OPENAI_API_KEY"] == "from-file"
    assert reviewer_client.os.environ["OPENAI_BASE_URL"] == "https://example.test/v1"
