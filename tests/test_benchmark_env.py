"""Browser-free tests for tools/benchmark_env.py.

The fingerprint exists because the 2.0 benchmark recorded 101 contrast
failures on pages that now measure 105, stably, with nothing in the pages or
the audit changed. That is an environmental difference, and without recording
the environment nobody can tell it from a regression.

So what is pinned here is that every field which can move a measurement is
captured, and that a diff reports the change rather than silently matching.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "skills" / "polishkit" / "scripts"))

import benchmark_env  # noqa: E402


class FingerprintTests(unittest.TestCase):
    def setUp(self):
        self.data = benchmark_env.fingerprint()

    def test_every_measurement_moving_field_is_present(self):
        # The browser build and the colour math are what change a contrast
        # number; a fingerprint missing either cannot explain a drift.
        for key in ("recorded_at", "plugin_version", "python", "platform",
                    "machine", "browser_path", "browser_version", "tool_digests"):
            self.assertIn(key, self.data, f"{key} missing from the fingerprint")

    def test_the_timestamp_is_iso_utc(self):
        stamp = self.data["recorded_at"]
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_tool_digests_cover_every_audit_script(self):
        scripts = {p.name for p in (ROOT / "skills" / "polishkit" / "scripts").glob("*.py")}
        self.assertEqual(set(self.data["tool_digests"]), scripts)

    def test_a_tool_digest_is_a_short_stable_hash(self):
        for name, digest in self.data["tool_digests"].items():
            self.assertEqual(len(digest), 16, name)
            int(digest, 16)  # must be hexadecimal

    def test_the_manifest_version_is_read(self):
        self.assertEqual(self.data["plugin_version"],
                         benchmark_env.manifest_version())
        self.assertIsNotNone(self.data["plugin_version"])

    def test_a_missing_manifest_reports_none(self):
        with mock.patch.object(benchmark_env, "ROOT", Path(tempfile.gettempdir())):
            self.assertIsNone(benchmark_env.manifest_version())


class BrowserVersionTests(unittest.TestCase):
    def test_no_browser_reports_none(self):
        self.assertIsNone(benchmark_env.browser_version(None))

    def test_a_chrome_banner_is_returned(self):
        completed = mock.Mock(stdout="Google Chrome 157.0.1.2\n", returncode=0)
        with mock.patch("subprocess.run", return_value=completed):
            self.assertEqual(benchmark_env.browser_version("/fake/chrome"),
                             "Google Chrome 157.0.1.2")

    def test_a_bare_version_is_returned(self):
        completed = mock.Mock(stdout="157.0.8103.79\n", returncode=0)
        with mock.patch("subprocess.run", return_value=completed):
            self.assertEqual(benchmark_env.browser_version("/fake/chrome"),
                             "157.0.8103.79")

    def test_an_unhelpful_answer_is_not_mistaken_for_a_version(self):
        completed = mock.Mock(stdout="Usage: chrome [options]\n", returncode=0)
        with mock.patch("subprocess.run", return_value=completed):
            self.assertIsNone(benchmark_env.browser_version("/fake/chrome"))

    def test_a_browser_that_will_not_run_reports_none(self):
        with mock.patch("subprocess.run", side_effect=OSError("nope")):
            self.assertIsNone(benchmark_env.browser_version("/fake/chrome"))


class DiffTests(unittest.TestCase):
    def record(self, **overrides):
        data = benchmark_env.fingerprint()
        data.update(overrides)
        return data

    def run_diff(self, recorded):
        path = Path(tempfile.mkdtemp()) / "ENVIRONMENT.json"
        path.write_text(json.dumps(recorded), encoding="utf-8")
        return benchmark_env.diff_against(path)

    def test_an_identical_environment_reports_no_change(self):
        result = self.run_diff(self.record())
        self.assertEqual(result["changed"], {})
        self.assertEqual(result["changed_tools"], [])

    def test_a_different_browser_is_reported(self):
        result = self.run_diff(self.record(browser_version="Google Chrome 150.0"))
        self.assertIn("browser_version", result["changed"])

    def test_a_different_python_is_reported(self):
        result = self.run_diff(self.record(python="3.9.0"))
        self.assertIn("python", result["changed"])

    def test_an_edited_tool_is_reported_by_name(self):
        digests = dict(benchmark_env.fingerprint()["tool_digests"])
        first = sorted(digests)[0]
        digests[first] = "0" * 16
        result = self.run_diff(self.record(tool_digests=digests))
        self.assertEqual(result["changed_tools"], [first])

    def test_the_previous_timestamp_is_carried_through(self):
        result = self.run_diff(self.record(recorded_at="2026-01-01T00:00:00Z"))
        self.assertEqual(result["previous_recorded_at"], "2026-01-01T00:00:00Z")

    def test_a_missing_record_reports_none(self):
        missing = Path(tempfile.mkdtemp()) / "absent.json"
        self.assertIsNone(benchmark_env.diff_against(missing))

    def test_an_unreadable_record_reports_none(self):
        path = Path(tempfile.mkdtemp()) / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(benchmark_env.diff_against(path))


if __name__ == "__main__":
    unittest.main()
