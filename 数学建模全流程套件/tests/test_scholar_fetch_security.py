import importlib.util
import ssl
import sys
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
MODULE_PATH = TOOLS_DIR / "scholar_fetch.py"


def load_scholar_fetch():
    spec = importlib.util.spec_from_file_location("scholar_fetch_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_aminer_is_disabled_when_no_api_key_is_configured(monkeypatch):
    monkeypatch.delenv("AMINER_API_KEY", raising=False)

    module = load_scholar_fetch()

    assert module._AMINER_API_KEY == ""


def test_http_get_does_not_retry_tls_errors_without_certificate_validation():
    module = load_scholar_fetch()

    with patch.object(module.urllib.request, "urlopen", side_effect=ssl.SSLError("bad certificate")) as urlopen:
        result = module._http_get("https://example.test")

    assert result is None
    assert urlopen.call_count == 1


def test_http_post_does_not_retry_tls_errors_without_certificate_validation():
    module = load_scholar_fetch()

    with patch.object(module.urllib.request, "urlopen", side_effect=ssl.SSLError("bad certificate")) as urlopen:
        result = module._http_post("https://example.test", {"query": "test"})

    assert result is None
    assert urlopen.call_count == 1
