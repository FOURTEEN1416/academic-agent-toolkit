"""Tests for tools/verify_papers.py Semantic Scholar access.

The title layer never sent SEMANTIC_SCHOLAR_API_KEY, so an issued key did not
reach it: unauthenticated callers share one pool and get 429 under any load,
which the helper reports as verify_pending. The key's documented limit is
1 request/second cumulative across all endpoints, so calls are also paced.
"""

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "verify_papers.py"

REAL_ID = "1706.03762"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_papers", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register before exec: the module's dataclasses resolve their annotations
    # through sys.modules (same pattern as test_review_gate.py).
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _patch_http_get(monkeypatch, mod, responses):
    """Each call to http_get pops one (status, body) pair from `responses`."""
    queue = list(responses)

    def fake_http_get(url, headers=None, timeout=30):
        return queue.pop(0)

    monkeypatch.setattr(mod, "http_get", fake_http_get)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

S2_HIT = '{"data": [{"title": "Attention Is All You Need", "year": 2017, "externalIds": {"ArXiv": "1706.03762"}}]}'


def _capture_http_get(monkeypatch, mod, responses):
    """Like _patch_http_get but records the headers each call was given."""
    queue = list(responses)
    seen = {"headers": []}

    def fake_http_get(url, headers=None, timeout=30):
        seen["headers"].append(headers)
        return queue.pop(0)

    monkeypatch.setattr(mod, "http_get", fake_http_get)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    return seen


def test_s2_sends_api_key_when_env_set(monkeypatch):
    mod = load_module()
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "s2k-test")
    seen = _capture_http_get(monkeypatch, mod, [(200, S2_HIT)])

    status, ids = mod.verify_title_s2("Attention Is All You Need", 0.7)

    assert status == "verified"
    assert ids["arxiv_id"] == REAL_ID
    assert seen["headers"][0]["x-api-key"] == "s2k-test"


def test_s2_stays_anonymous_without_env(monkeypatch):
    mod = load_module()
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    seen = _capture_http_get(monkeypatch, mod, [(200, S2_HIT)])

    mod.verify_title_s2("Attention Is All You Need", 0.7)

    assert "x-api-key" not in (seen["headers"][0] or {})


def test_s2_paces_successive_calls(monkeypatch):
    """The documented key limit is 1 request/second across all endpoints."""
    mod = load_module()
    slept = []
    monkeypatch.setattr(mod.time, "sleep", slept.append)
    ticks = iter([0.0, 0.0, 0.1, 0.1])  # second call arrives 0.1 s after the first
    monkeypatch.setattr(mod.time, "monotonic", lambda: next(ticks))

    mod._s2_throttle()
    mod._s2_throttle()

    assert slept and slept[-1] >= mod.S2_MIN_INTERVAL_SEC - 0.1 - 1e-9


def test_s2_retries_a_429_then_verifies(monkeypatch):
    """A 429 is the expected answer under a 1 req/s ceiling, not a verdict."""
    mod = load_module()
    _patch_http_get(monkeypatch, mod, [(429, None), (200, S2_HIT)])

    status, ids = mod.verify_title_s2("Attention Is All You Need", 0.7)

    assert status == "verified"
    assert ids["arxiv_id"] == REAL_ID


def test_s2_persistent_429_is_pending_not_unverified(monkeypatch):
    """Rate limiting must never be reported as "this paper does not exist"."""
    mod = load_module()
    _patch_http_get(monkeypatch, mod, [(429, None)] * 3)

    status, ids = mod.verify_title_s2("Attention Is All You Need", 0.7)

    assert status == "verify_pending"
    assert ids is None
