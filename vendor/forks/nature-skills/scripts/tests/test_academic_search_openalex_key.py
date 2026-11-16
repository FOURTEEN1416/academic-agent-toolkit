from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[2] / "skills/nature-academic-search/scripts/academic_search.py"
SPEC = importlib.util.spec_from_file_location("academic_search_key_test", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def capture_request(api_key: str):
    seen = {}

    def fake_urlopen(req, timeout=30):
        seen["url"] = req.full_url
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        return FakeResponse(json.dumps({"results": []}).encode())

    with mock.patch.object(MODULE, "API_KEY", api_key), \
            mock.patch.object(MODULE.urllib.request, "urlopen", fake_urlopen):
        MODULE.search("graph neural network", limit=3)
        MODULE.fetch_author_candidates("Jane Doe")
        MODULE.resolve_by_orcid("0000-0002-1825-0097")
    return seen


class OpenAlexApiKeyTests(unittest.TestCase):
    def test_key_is_sent_as_bearer_header_not_in_url(self):
        seen = capture_request("secret-key")
        self.assertEqual(seen["headers"]["authorization"], "Bearer secret-key")
        self.assertNotIn("secret-key", seen["url"])

    def test_keyless_request_has_no_auth_header(self):
        seen = capture_request("")
        self.assertNotIn("authorization", seen["headers"])

    def test_mailto_is_no_longer_sent(self):
        seen = capture_request("")
        self.assertNotIn("mailto", seen["url"])

    def test_main_reads_key_from_env_and_flag(self):
        argv = ["academic_search.py", "graph", "--compact"]
        for env, flag, expected in (({"OPENALEX_API_KEY": "from-env"}, [], "from-env"),
                                    ({"OPENALEX_API_KEY": "from-env"}, ["--api-key", "flag"], "flag")):
            with mock.patch.object(sys, "argv", argv + flag), \
                    mock.patch.dict(MODULE.os.environ, env, clear=False), \
                    mock.patch.object(MODULE, "search", return_value=[]):
                MODULE.API_KEY = ""
                MODULE.main()
                self.assertEqual(MODULE.API_KEY, expected)
        MODULE.API_KEY = ""

    def test_http_429_hint_mentions_api_key(self):
        err = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["academic_search.py", "graph"]), \
                mock.patch.object(MODULE, "search", side_effect=err), redirect_stderr(stderr):
            code = MODULE.main()
        self.assertEqual(code, 1)
        self.assertIn("OPENALEX_API_KEY", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
