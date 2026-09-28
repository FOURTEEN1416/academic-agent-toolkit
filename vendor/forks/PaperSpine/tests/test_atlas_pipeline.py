import importlib.util
import json
import pathlib
import unittest
import urllib.error
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch = load_module("fetch_stargazers", ROOT / "atlas" / "fetch_stargazers.py")
validate = load_module("validate_atlas_data", ROOT / "atlas" / "validate_data.py")


class AtlasPipelineTests(unittest.TestCase):
    def test_committed_atlas_snapshot_is_valid(self):
        data = validate.load_atlas(ROOT / "atlas" / "data.js")
        validate.validate_atlas(data)

    def test_empty_atlas_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "totalStars"):
            validate.validate_atlas({"totalStars": 0, "cities": [], "countries": {}})

    def test_api_failure_is_not_converted_to_empty_data(self):
        error = urllib.error.HTTPError(
            "https://api.github.com/example", 403, "Forbidden", {}, None
        )
        with mock.patch.object(
            fetch.urllib.request, "urlopen", side_effect=error
        ) as mocked_urlopen:
            with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                fetch.api(
                    "https://api.github.com/example",
                    "test-token",
                    retries=3,
                    sleeper=lambda _seconds: None,
                )
            self.assertEqual(mocked_urlopen.call_count, 1)

    def test_atomic_json_writer_replaces_destination(self):
        path = ROOT / "tests" / ".atlas-test-data.json"
        try:
            path.write_text('{"old": true}', encoding="utf-8")
            fetch.write_json_atomic(str(path), [{"login": "octocat"}], indent=1)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))[0]["login"], "octocat")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
