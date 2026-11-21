"""Browser-free tests for find_browser's POLISHKIT_BROWSER override.

The CI browser smoke runs on runner images whose preinstalled Chrome failed
three runs in a row (ubuntu) — the job now pins a Chrome-for-Testing build
through this environment variable instead of trusting whatever the image
ships. A stale pin must fail loudly: silently falling back would run the
smoke against a browser nobody pinned, and a check that passes for the wrong
reason proves nothing.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "polishkit" / "scripts"))

import visual_capture  # noqa: E402


class OverrideTests(unittest.TestCase):
    def test_an_existing_file_wins_over_every_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "chrome-under-test"
            fake.write_bytes(b"MZ")
            with mock.patch.dict(os.environ, {"POLISHKIT_BROWSER": str(fake)}):
                self.assertEqual(visual_capture.find_browser(), str(fake.resolve()))

    def test_a_stale_pin_fails_loudly(self):
        with mock.patch.dict(os.environ, {"POLISHKIT_BROWSER": "no-such-browser.exe"}):
            with self.assertRaises(ValueError):
                visual_capture.find_browser()

    def test_unset_behaves_as_before(self):
        with mock.patch.dict(os.environ, {}):
            os.environ.pop("POLISHKIT_BROWSER", None)
            result = visual_capture.find_browser()
            # On a machine with a browser this is its path; without one, None.
            self.assertTrue(result is None or Path(result).is_file())


if __name__ == "__main__":
    unittest.main()
